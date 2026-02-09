// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

interface IFxToken is IERC20 {
    function mint(address to, uint256 amount) external;
    function burn(address from, uint256 amount) external;
}

contract FxVaultV1 is Ownable, ReentrancyGuard {
    IERC20 public immutable collateral;  // 抵押品 T
    IERC20 public immutable fToken;      // fT
    IERC20 public immutable xToken;      // xT
    
    uint256 public constant BETA_F_TARGET = 1e17;  // 0.1 * 1e18
    uint256 public constant MAX_LEVERAGE = 5e18;   // 5x * 1e18
    uint256 public totalCollateral;                // n
    uint256 public totalFT;                        // n_f (追踪流通)
    uint256 public totalXT;                        // n_x
    uint256 public lastPriceS;                     // 上次 s (for TWAP)
    
    // 简单 oracle (v1 用 Uniswap TWAP)
    function getCollateralPrice() public view returns (uint256) {
        // 实际: return IUniswapV3Pool(uniswapPool).slot0().sqrtPriceX96 ** 2 / (2**192); // 简化
        return 1e18;  // 占位，替换为真实 oracle
    }
    
    constructor(address _collateral, address _fToken, address _xToken) {
        collateral = IERC20(_collateral);
        fToken = IERC20(_fToken);
        xToken = IERC20(_xToken);
        lastPriceS = getCollateralPrice();
    }
    
    // mint: 初始分成 (不变)
    function mint(uint256 amount) external nonReentrant {
        require(amount > 0, "Amount > 0");
        collateral.transferFrom(msg.sender, address(this), amount);
        totalCollateral += amount;
        
        uint256 priceS = getCollateralPrice();
        lastPriceS = priceS;
        
        uint256 nF = (amount * BETA_F_TARGET) / 1e18;
        uint256 nX = amount - nF;
        
        // 铸造 (假设 fToken/xToken 有 mint 函数)
        IFxToken(address(fToken)).mint(msg.sender, nF);
        IFxToken(address(xToken)).mint(msg.sender, nX);
        
        totalFT += nF;
        totalXT += nX;
        
        emit Mint(msg.sender, amount, nF, nX);
    }
    
    // 动态杠杆查询
    function getLeverage() public view returns (uint256) {
        uint256 priceS = getCollateralPrice();
        if (priceS == 0) return 0;
        
        // β_x = (n_x * x) / (n * s) ≈ totalXT / totalCollateral (初始 x≈s=1, 动态需 oracle 更新净值)
        // 简化: 假设净值 x = priceS * (totalCollateral / totalXT) * (1 / (1 - BETA_F_TARGET)) 但 v1 用公式
        uint256 betaX = (totalXT * priceS * 1e18) / (totalCollateral * lastPriceS);  // 近似
        if (betaX >= 1e18) return type(uint256).max;  // 无限杠杆警告
        
        uint256 leverage = 1e18 / (1e18 - betaX);  // L = 1 / (1 - β_x)
        return leverage > MAX_LEVERAGE ? MAX_LEVERAGE : leverage;
    }
    
    // 再平衡: 防止爆仓 (anyone callable, v1 风格)
    function rebalance() external nonReentrant {
        uint256 leverage = getLeverage();
        require(leverage > MAX_LEVERAGE, "Leverage not exceeded");
        
        uint256 priceS = getCollateralPrice();
        // 计算多余 fT: excess = n_f * f - β_f * n * s (f≈s)
        uint256 targetValueF = (totalCollateral * priceS * BETA_F_TARGET) / 1e18;
        uint256 currentValueF = totalFT * priceS;  // 假设 f≈s
        uint256 excessF = currentValueF > targetValueF ? currentValueF - targetValueF : 0;
        
        if (excessF > 0) {
            uint256 burnAmount = excessF / priceS;  // 燃烧量
            IFxToken(address(fToken)).burn(address(this), burnAmount);  // 燃烧到池
            totalFT -= burnAmount;
            
            // 注入抵押 (从 Stability Pool, 简化: 假设池有抵押)
            // 实际: collateral.transferFrom(stabilityPool, address(this), injectAmount);
            
            emit Rebalance(leverage, burnAmount);
        }
    }
    
    // redeem (简化)
    function redeem(uint256 fAmount, uint256 xAmount) external nonReentrant {
        // 简化版：需要验证用户持有足够的fToken和xToken
        require(fAmount > 0 || xAmount > 0, "Amount > 0");
        
        // 先计算可赎回的抵押品数量（在燃烧代币之前）
        uint256 totalTokens = totalFT + totalXT;
        require(totalTokens > 0, "No tokens in circulation");
        uint256 redeemAmount = (fAmount + xAmount) * totalCollateral / totalTokens;
        
        // 然后燃烧代币
        if (fAmount > 0) {
            IFxToken(address(fToken)).burn(msg.sender, fAmount);
            totalFT -= fAmount;
        }
        
        if (xAmount > 0) {
            IFxToken(address(xToken)).burn(msg.sender, xAmount);
            totalXT -= xAmount;
        }
        
        // 转账抵押品给用户
        collateral.transfer(msg.sender, redeemAmount);
        totalCollateral -= redeemAmount;
    }
    
    event Mint(address indexed user, uint256 collateralAmount, uint256 fAmount, uint256 xAmount);
    event Rebalance(uint256 oldLeverage, uint256 burnedAmount);
}