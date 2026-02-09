// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

interface IShortToken is IERC20 {
    function mint(address to, uint256 amount) external;
    function burn(address from, uint256 amount) external;
}

interface IPriceOracle {
    // 返回标的资产价格，精度 1e18
    function getPrice() external view returns (uint256);
}

/// @notice 研究用途的做空代币池（示例实现）
/// @dev 该合约使用“指数化短仓”近似公式，并引入虚拟权益（virtualEquity）来记录PnL。
///      真实落地需要配套对冲或资金池来实现PnL结算，否则仅能作为研究/仿真。
contract ShortVaultV1 is Ownable, ReentrancyGuard {
    enum Status {
        Normal,
        Liquidation
    }

    IERC20 public immutable collateral;   // 计价资产（稳定币）
    IShortToken public immutable sToken;  // 做空代币（份额）
    IPriceOracle public oracle;           // 价格预言机

    uint256 public leverage;              // 杠杆倍率，1e18 表示 1x
    uint256 public index;                 // sToken NAV，1e18 精度
    uint256 public lastPrice;             // 上次价格，1e18
    uint256 public virtualEquity;         // 虚拟权益（用于研究）
    uint256 public minCollateralRatio;    // 最低健康抵押率（1e18）
    uint256 public liquidationRatio;      // 触发清算的抵押率（1e18）
    uint256 public liquidationIndex;      // 清算结算NAV
    Status public status;

    event Deposit(address indexed user, uint256 collateralIn, uint256 sharesOut);
    event Redeem(address indexed user, uint256 sharesIn, uint256 collateralOut);
    event IndexUpdated(uint256 oldIndex, uint256 newIndex, uint256 oldPrice, uint256 newPrice);
    event Deleveraged(uint256 oldIndex, uint256 newIndex, uint256 collateralRatio);
    event LiquidationTriggered(uint256 liquidationIndex, uint256 collateralRatio);
    event LiquidationEnded(uint256 newPrice);
    event OracleUpdated(address indexed newOracle);
    event LeverageUpdated(uint256 newLeverage);
    event RiskParamsUpdated(uint256 minCollateralRatio, uint256 liquidationRatio);
    event EquitySynced(uint256 oldEquity, uint256 newEquity, int256 delta, address indexed operator);

    constructor(
        address _collateral,
        address _sToken,
        address _oracle,
        uint256 _leverage,
        uint256 _minCollateralRatio,
        uint256 _liquidationRatio
    ) {
        require(_collateral != address(0), "Collateral=0");
        require(_sToken != address(0), "sToken=0");
        require(_oracle != address(0), "Oracle=0");
        require(_leverage > 0, "Leverage=0");
        require(_minCollateralRatio >= 1e18, "minCR<1");
        require(_liquidationRatio >= 1e18, "liqCR<1");
        require(_liquidationRatio <= _minCollateralRatio, "liqCR>minCR");

        collateral = IERC20(_collateral);
        sToken = IShortToken(_sToken);
        oracle = IPriceOracle(_oracle);
        leverage = _leverage;
        minCollateralRatio = _minCollateralRatio;
        liquidationRatio = _liquidationRatio;
        index = 1e18; // 初始NAV=1
        lastPrice = oracle.getPrice();
        status = Status.Normal;
    }

    function setOracle(address _oracle) external onlyOwner {
        require(_oracle != address(0), "Oracle=0");
        oracle = IPriceOracle(_oracle);
        emit OracleUpdated(_oracle);
    }

    function setLeverage(uint256 _leverage) external onlyOwner {
        require(_leverage > 0, "Leverage=0");
        leverage = _leverage;
        emit LeverageUpdated(_leverage);
    }

    function setRiskParams(uint256 _minCollateralRatio, uint256 _liquidationRatio) external onlyOwner {
        require(_minCollateralRatio >= 1e18, "minCR<1");
        require(_liquidationRatio >= 1e18, "liqCR<1");
        require(_liquidationRatio <= _minCollateralRatio, "liqCR>minCR");
        minCollateralRatio = _minCollateralRatio;
        liquidationRatio = _liquidationRatio;
        emit RiskParamsUpdated(_minCollateralRatio, _liquidationRatio);
    }

    function effectiveIndex() public view returns (uint256) {
        if (status == Status.Liquidation) {
            return liquidationIndex;
        }
        return index;
    }

    function liabilities() public view returns (uint256) {
        uint256 supply = sToken.totalSupply();
        if (supply == 0) return 0;
        return supply * effectiveIndex() / 1e18;
    }

    function collateralRatio() public view returns (uint256) {
        uint256 liab = liabilities();
        if (liab == 0) return type(uint256).max;
        uint256 assets = collateral.balanceOf(address(this));
        return assets * 1e18 / liab;
    }

    /// @notice 更新指数（做空方向）
    function updateIndex() public {
        uint256 price = oracle.getPrice();
        require(price > 0, "Price=0");

        if (status == Status.Liquidation) {
            lastPrice = price;
            return;
        }

        uint256 oldIndex = index;
        uint256 oldPrice = lastPrice;

        // r = (P_t - P_{t-1}) / P_{t-1}
        // newIndex = index * (1 - leverage * r)
        // 使用 1e18 精度，避免负值
        if (oldPrice > 0) {
            int256 r = (int256(price) - int256(oldPrice)) * int256(1e18) / int256(oldPrice);
            int256 factor = int256(1e18) - (int256(leverage) * r / int256(1e18));
            if (factor <= 0) {
                index = 1; // 极端情况下防止归零
            } else {
                index = uint256(int256(index) * factor / int256(1e18));
            }
        }

        lastPrice = price;

        uint256 supply = sToken.totalSupply();
        if (supply > 0) {
            uint256 assets = collateral.balanceOf(address(this));
            uint256 liab = supply * index / 1e18;
            uint256 cr = liab == 0 ? type(uint256).max : assets * 1e18 / liab;

            if (cr < liquidationRatio) {
                liquidationIndex = assets * 1e18 / supply;
                status = Status.Liquidation;
                emit LiquidationTriggered(liquidationIndex, cr);
                return;
            }

            if (cr < minCollateralRatio) {
                uint256 cappedIndex = assets * 1e18 / minCollateralRatio / supply;
                emit Deleveraged(index, cappedIndex, cr);
                index = cappedIndex;
            }
        }

        // 仅研究用途：虚拟权益 = supply * index
        virtualEquity = supply * index / 1e18;

        emit IndexUpdated(oldIndex, index, oldPrice, price);
    }

    function deposit(uint256 collateralAmount) external nonReentrant {
        require(status == Status.Normal, "Liquidation");
        require(collateralAmount > 0, "Amount=0");
        updateIndex();

        uint256 shares = collateralAmount * 1e18 / index;
        require(shares > 0, "Shares=0");

        collateral.transferFrom(msg.sender, address(this), collateralAmount);
        virtualEquity += collateralAmount;
        sToken.mint(msg.sender, shares);

        emit Deposit(msg.sender, collateralAmount, shares);
    }

    function redeem(uint256 shareAmount) external nonReentrant {
        require(shareAmount > 0, "Amount=0");
        updateIndex();

        uint256 currentIndex = effectiveIndex();
        uint256 collateralOut = shareAmount * currentIndex / 1e18;
        require(collateralOut > 0, "Out=0");
        require(collateral.balanceOf(address(this)) >= collateralOut, "Insufficient collateral");

        sToken.burn(msg.sender, shareAmount);
        virtualEquity = virtualEquity > collateralOut ? virtualEquity - collateralOut : 0;
        collateral.transfer(msg.sender, collateralOut);

        emit Redeem(msg.sender, shareAmount, collateralOut);
    }

    /// @notice 同步虚拟权益与实际资金池（研究用途）
    /// @dev delta > 0 表示需要补充资金；delta < 0 表示可提取多余资金
    function syncEquity(address to) external onlyOwner nonReentrant {
        uint256 balance = collateral.balanceOf(address(this));
        if (virtualEquity > balance) {
            uint256 need = virtualEquity - balance;
            collateral.transferFrom(msg.sender, address(this), need);
            emit EquitySynced(balance, virtualEquity, int256(need), msg.sender);
        } else if (balance > virtualEquity) {
            uint256 excess = balance - virtualEquity;
            collateral.transfer(to, excess);
            emit EquitySynced(balance, virtualEquity, -int256(excess), msg.sender);
        } else {
            emit EquitySynced(balance, virtualEquity, 0, msg.sender);
        }
    }

    function liquidate() external nonReentrant {
        require(status == Status.Normal, "Already");
        updateIndex();
        if (status == Status.Liquidation) {
            return;
        }
        uint256 cr = collateralRatio();
        require(cr < liquidationRatio, "Not eligible");
        uint256 supply = sToken.totalSupply();
        if (supply > 0) {
            liquidationIndex = collateral.balanceOf(address(this)) * 1e18 / supply;
        } else {
            liquidationIndex = index;
        }
        status = Status.Liquidation;
        emit LiquidationTriggered(liquidationIndex, cr);
    }

    function resume() external onlyOwner {
        require(status == Status.Liquidation, "Not in liquidation");
        require(collateralRatio() >= minCollateralRatio, "CR too low");
        status = Status.Normal;
        liquidationIndex = 0;
        lastPrice = oracle.getPrice();
        emit LiquidationEnded(lastPrice);
    }
}
