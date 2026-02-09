// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

interface IFxToken is IERC20 {
    function mint(address to, uint256 amount) external;
    function burn(address from, uint256 amount) external;
}

interface IPriceOracle {
    // 返回 BTC 价格，精度 1e18
    function getPrice() external view returns (uint256);
}

/**
 * @title ShortVaultV2
 * @notice 基于 f(x) 协议的 BTC 做空代币池
 * @dev 将抵押品拆分为 fBTC（稳定）和 sBTC（做空）两部分
 * 
 * 核心公式:
 * - n * P = n_f * V_f + n_s * V_s
 * - sBTC NAV: V_s_t = V_s_{t-1} * max(MIN_NAV, 1 - L * r_t)
 * - fBTC NAV: V_f_t = (n * P_t - n_s * V_s_t) / n_f
 */
contract ShortVaultV2 is Ownable, ReentrancyGuard {
    
    // ============ 状态枚举 ============
    enum Status {
        Normal,      // 正常状态
        Rebalancing, // 再平衡中
        Liquidation  // 清算状态
    }
    
    // ============ 常量 ============
    uint256 public constant PRECISION = 1e18;
    uint256 public constant BETA_F_TARGET = 1e17;      // 0.1 * 1e18, fBTC 目标占比 10%
    uint256 public constant BETA_S_TARGET = 9e17;      // 0.9 * 1e18, sBTC 目标占比 90%
    uint256 public constant MIN_NAV_S = 1e16;          // 0.01 * 1e18, sBTC 最低净值
    uint256 public constant MAX_LEVERAGE = 5e18;       // 5x 最大杠杆
    uint256 public constant TARGET_LEVERAGE = 2e18;    // 2x 目标杠杆
    
    // ============ 状态变量 ============
    IERC20 public immutable collateral;   // 抵押品 (wBTC 或 stETH)
    IFxToken public immutable fToken;     // fBTC 稳定代币
    IFxToken public immutable sToken;     // sBTC 做空代币
    IPriceOracle public oracle;           // 价格预言机
    
    uint256 public totalCollateral;       // 总抵押品数量
    uint256 public navF;                  // fBTC 当前净值 (1e18精度)
    uint256 public navS;                  // sBTC 当前净值 (1e18精度)
    uint256 public lastPrice;             // 上次更新价格
    uint256 public lastUpdateTime;        // 上次更新时间
    
    Status public status;
    
    // 风控参数
    uint256 public minCollateralRatio;    // 最低抵押率 (如 1.05e18)
    uint256 public liquidationRatio;      // 清算阈值 (如 1.0e18)
    uint256 public rebalanceThreshold;    // 再平衡触发阈值 (如 0.05e18 = 5%)
    
    // 保险池
    uint256 public insurancePool;         // 保险池余额
    uint256 public constant INSURANCE_FEE = 5e14;      // 0.05% 铸造费进入保险池
    
    // ============ 事件 ============
    event Mint(address indexed user, uint256 collateralIn, uint256 fOut, uint256 sOut);
    event Redeem(address indexed user, uint256 fIn, uint256 sIn, uint256 collateralOut);
    event NAVUpdated(uint256 oldPrice, uint256 newPrice, uint256 navF, uint256 navS, uint256 leverage);
    event Rebalanced(uint256 oldLeverage, uint256 newLeverage, uint256 burnAmount);
    event LiquidationTriggered(uint256 price, uint256 navS);
    event InsuranceFunded(uint256 amount);
    event InsuranceUsed(uint256 amount);
    
    // ============ 修饰器 ============
    modifier whenNormal() {
        require(status == Status.Normal, "Not normal status");
        _;
    }
    
    modifier updateNAV() {
        _updateNAV();
        _;
    }
    
    // ============ 构造函数 ============
    constructor(
        address _collateral,
        address _fToken,
        address _sToken,
        address _oracle,
        uint256 _minCollateralRatio,
        uint256 _liquidationRatio
    ) {
        require(_collateral != address(0), "Collateral=0");
        require(_fToken != address(0), "fToken=0");
        require(_sToken != address(0), "sToken=0");
        require(_oracle != address(0), "Oracle=0");
        require(_minCollateralRatio >= PRECISION, "minCR<1");
        require(_liquidationRatio >= PRECISION, "liqCR<1");
        require(_liquidationRatio <= _minCollateralRatio, "liqCR>minCR");
        
        collateral = IERC20(_collateral);
        fToken = IFxToken(_fToken);
        sToken = IFxToken(_sToken);
        oracle = IPriceOracle(_oracle);
        
        minCollateralRatio = _minCollateralRatio;
        liquidationRatio = _liquidationRatio;
        rebalanceThreshold = 5e16; // 默认 5%
        
        // 初始化 NAV
        navF = PRECISION;  // 初始 1.0
        navS = PRECISION;  // 初始 1.0
        lastPrice = oracle.getPrice();
        lastUpdateTime = block.timestamp;
        status = Status.Normal;
    }
    
    // ============ 核心函数 ============
    
    /**
     * @notice 铸造 fBTC 和 sBTC
     * @param collateralAmount 抵押品数量
     */
    function mint(uint256 collateralAmount) external nonReentrant whenNormal updateNAV {
        require(collateralAmount > 0, "Amount=0");
        
        uint256 price = oracle.getPrice();
        
        // 计算铸造数量
        // value = collateralAmount * price / PRECISION
        // fOut = value * BETA_F_TARGET / navF
        // sOut = value * BETA_S_TARGET / navS
        uint256 value = (collateralAmount * price) / PRECISION;
        uint256 fOut = (value * BETA_F_TARGET) / navF;
        uint256 sOut = (value * BETA_S_TARGET) / navS;
        
        require(fOut > 0 && sOut > 0, "Output=0");
        
        // 收取保险费
        uint256 insuranceFee = (collateralAmount * INSURANCE_FEE) / PRECISION;
        insurancePool += insuranceFee;
        emit InsuranceFunded(insuranceFee);
        
        // 转入抵押品
        uint256 actualCollateral = collateralAmount - insuranceFee;
        collateral.transferFrom(msg.sender, address(this), actualCollateral);
        totalCollateral += actualCollateral;
        
        // 铸造代币
        fToken.mint(msg.sender, fOut);
        sToken.mint(msg.sender, sOut);
        
        emit Mint(msg.sender, actualCollateral, fOut, sOut);
    }
    
    /**
     * @notice 按比例赎回抵押品
     * @param fAmount fBTC 数量
     * @param sAmount sBTC 数量
     */
    function redeem(uint256 fAmount, uint256 sAmount) external nonReentrant updateNAV {
        require(fAmount > 0 || sAmount > 0, "Amount=0");
        require(status != Status.Liquidation, "In liquidation");
        
        uint256 price = oracle.getPrice();
        
        // 计算赎回价值
        uint256 fValue = (fAmount * navF) / PRECISION;
        uint256 sValue = (sAmount * navS) / PRECISION;
        uint256 totalValue = fValue + sValue;
        
        // 计算对应抵押品数量
        uint256 collateralOut = (totalValue * PRECISION) / price;
        require(collateralOut > 0, "Out=0");
        require(collateral.balanceOf(address(this)) >= collateralOut, "Insufficient collateral");
        
        // 燃烧代币
        if (fAmount > 0) {
            fToken.burn(msg.sender, fAmount);
        }
        if (sAmount > 0) {
            sToken.burn(msg.sender, sAmount);
        }
        
        // 转出抵押品
        totalCollateral -= collateralOut;
        collateral.transfer(msg.sender, collateralOut);
        
        emit Redeem(msg.sender, fAmount, sAmount, collateralOut);
    }
    
    /**
     * @notice 更新 NAV（核心算法）
     */
    function _updateNAV() internal {
        uint256 currentPrice = oracle.getPrice();
        if (currentPrice == lastPrice || currentPrice == 0) {
            return;
        }
        
        // 计算收益率 r = (P_t - P_{t-1}) / P_{t-1}
        int256 priceDiff = int256(currentPrice) - int256(lastPrice);
        int256 r = (priceDiff * int256(PRECISION)) / int256(lastPrice);
        
        // 计算当前杠杆
        uint256 currentLeverage = getCurrentLeverage();
        
        // 更新 sBTC NAV: V_s_t = V_s_{t-1} * max(MIN_NAV, 1 - L * r_t)
        int256 leverageFactor = int256(currentLeverage);
        int256 changeFactor = (int256(PRECISION) - (leverageFactor * r) / int256(PRECISION));
        
        if (changeFactor <= 0) {
            // 极端情况：触发保护
            navS = MIN_NAV_S;
            _triggerLiquidation(currentPrice);
        } else {
            uint256 newNavS = (navS * uint256(changeFactor)) / PRECISION;
            navS = newNavS > MIN_NAV_S ? newNavS : MIN_NAV_S;
        }
        
        // 更新 fBTC NAV: V_f_t = (n * P_t - n_s * V_s_t) / n_f
        uint256 totalF = fToken.totalSupply();
        uint256 totalS = sToken.totalSupply();
        
        if (totalF > 0) {
            uint256 totalValue = (totalCollateral * currentPrice) / PRECISION;
            uint256 sValue = (totalS * navS) / PRECISION;
            
            if (totalValue > sValue) {
                navF = ((totalValue - sValue) * PRECISION) / totalF;
            } else {
                // 保险兜底
                uint256 deficit = sValue - totalValue;
                if (insurancePool >= deficit) {
                    insurancePool -= deficit;
                    emit InsuranceUsed(deficit);
                    navF = PRECISION / 100; // 最小值
                } else {
                    _triggerLiquidation(currentPrice);
                }
            }
        }
        
        emit NAVUpdated(lastPrice, currentPrice, navF, navS, currentLeverage);
        
        lastPrice = currentPrice;
        lastUpdateTime = block.timestamp;
    }
    
    /**
     * @notice 触发清算
     */
    function _triggerLiquidation(uint256 price) internal {
        if (status != Status.Liquidation) {
            status = Status.Liquidation;
            emit LiquidationTriggered(price, navS);
        }
    }
    
    /**
     * @notice 再平衡：调整杠杆回到目标范围
     */
    function rebalance() external nonReentrant {
        _updateNAV();
        require(status == Status.Normal, "Not normal");
        
        uint256 currentLeverage = getCurrentLeverage();
        require(currentLeverage > MAX_LEVERAGE, "Leverage OK");
        
        uint256 totalF = fToken.totalSupply();
        uint256 price = oracle.getPrice();
        
        // 计算目标 fBTC 价值
        uint256 targetFValue = (totalCollateral * price * BETA_F_TARGET) / PRECISION / PRECISION;
        uint256 currentFValue = (totalF * navF) / PRECISION;
        
        if (currentFValue > targetFValue) {
            uint256 excessValue = currentFValue - targetFValue;
            uint256 burnAmount = (excessValue * PRECISION) / navF;
            
            // 燃烧多余 fBTC
            fToken.burn(address(this), burnAmount);
            
            // 调整 navF
            uint256 newTotalF = totalF - burnAmount;
            if (newTotalF > 0) {
                uint256 totalValue = (totalCollateral * price) / PRECISION;
                uint256 totalS = sToken.totalSupply();
                uint256 sValue = (totalS * navS) / PRECISION;
                navF = ((totalValue - sValue) * PRECISION) / newTotalF;
            }
            
            uint256 newLeverage = getCurrentLeverage();
            emit Rebalanced(currentLeverage, newLeverage, burnAmount);
        }
        
        status = Status.Normal;
    }
    
    /**
     * @notice 结束清算状态（管理员）
     */
    function endLiquidation() external onlyOwner {
        require(status == Status.Liquidation, "Not in liquidation");
        
        uint256 price = oracle.getPrice();
        uint256 totalValue = (totalCollateral * price) / PRECISION;
        uint256 totalF = fToken.totalSupply();
        uint256 totalS = sToken.totalSupply();
        
        if (totalF > 0 && totalS > 0) {
            uint256 sValue = (totalS * navS) / PRECISION;
            if (totalValue > sValue) {
                navF = ((totalValue - sValue) * PRECISION) / totalF;
                status = Status.Normal;
            }
        }
    }
    
    // ============ 查询函数 ============
    
    /**
     * @notice 获取当前实际杠杆
     */
    function getCurrentLeverage() public view returns (uint256) {
        uint256 price = oracle.getPrice();
        if (price == 0) return 0;
        
        uint256 totalS = sToken.totalSupply();
        if (totalS == 0) return TARGET_LEVERAGE;
        
        uint256 sValue = (totalS * navS) / PRECISION;
        uint256 totalValue = (totalCollateral * price) / PRECISION;
        
        if (totalValue == 0) return 0;
        
        uint256 betaS = (sValue * PRECISION) / totalValue;
        if (betaS >= PRECISION) return type(uint256).max;
        
        // L = 1 / (1 - beta_s)
        return PRECISION * PRECISION / (PRECISION - betaS);
    }
    
    /**
     * @notice 获取抵押率
     */
    function getCollateralRatio() public view returns (uint256) {
        uint256 price = oracle.getPrice();
        uint256 totalValue = (totalCollateral * price) / PRECISION;
        
        uint256 totalF = fToken.totalSupply();
        uint256 totalS = sToken.totalSupply();
        
        uint256 fValue = (totalF * navF) / PRECISION;
        uint256 sValue = (totalS * navS) / PRECISION;
        uint256 totalLiability = fValue + sValue;
        
        if (totalLiability == 0) return type(uint256).max;
        return (totalValue * PRECISION) / totalLiability;
    }
    
    /**
     * @notice 计算铸造可获得的数量
     */
    function getMintAmounts(uint256 collateralAmount) external view returns (uint256 fOut, uint256 sOut) {
        uint256 price = oracle.getPrice();
        uint256 value = (collateralAmount * price) / PRECISION;
        
        fOut = (value * BETA_F_TARGET) / navF;
        sOut = (value * BETA_S_TARGET) / navS;
    }
    
    /**
     * @notice 计算赎回可获得的抵押品
     */
    function getRedeemAmount(uint256 fAmount, uint256 sAmount) external view returns (uint256 collateralOut) {
        uint256 price = oracle.getPrice();
        uint256 fValue = (fAmount * navF) / PRECISION;
        uint256 sValue = (sAmount * navS) / PRECISION;
        collateralOut = ((fValue + sValue) * PRECISION) / price;
    }
    
    // ============ 管理函数 ============
    
    function setOracle(address _oracle) external onlyOwner {
        require(_oracle != address(0), "Oracle=0");
        oracle = IPriceOracle(_oracle);
    }
    
    function setRiskParams(
        uint256 _minCollateralRatio, 
        uint256 _liquidationRatio,
        uint256 _rebalanceThreshold
    ) external onlyOwner {
        require(_minCollateralRatio >= PRECISION, "minCR<1");
        require(_liquidationRatio >= PRECISION, "liqCR<1");
        require(_liquidationRatio <= _minCollateralRatio, "liqCR>minCR");
        minCollateralRatio = _minCollateralRatio;
        liquidationRatio = _liquidationRatio;
        rebalanceThreshold = _rebalanceThreshold;
    }
    
    /**
     * @notice 提取多余保险费（仅管理员）
     */
    function withdrawInsurance(address to, uint256 amount) external onlyOwner {
        require(amount <= insurancePool, "Insufficient");
        insurancePool -= amount;
        collateral.transfer(to, amount);
    }
}
