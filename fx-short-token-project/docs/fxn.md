https://github.com/AladdinDAO/aladdin-v3-contracts/blob/main/whitepapers/f(x)_whitepaper_v1.pdf



https://github.com/hylo-so/WhitePaper-Gitbook/blob/main/SUMMARY.md。

### f(x) 协议白皮书 v1 概述
根据 f(x) 协议 v1 白皮书（针对 ETH 的设计），该协议通过一个创新的衍生品机制，将抵押品（如 stETH）拆分为两个互补资产：
- **fETH**：低波动性稳定资产，类似于稳定币，吸收 ETH 价格波动的少部分（约 10%），目标 beta ≈ 0.1。
- **xETH**：杠杆做多 ETH 的永续代币，吸收大部分波动（约 90%），提供可变杠杆（v1 中最高约 4x），零融资成本且低清算风险。

核心机制基于公式：  
**n × s = n_f × f + n_x × x**  
- **n**：抵押品总量（单位）。  
- **s**：底层资产（ETH）现货价格（USD）。  
- **n_f**：fETH 铸造量。  
- **f**：fETH 净值（USD，接近稳定）。  
- **n_x**：xETH 铸造量。  
- **x**：xETH 净值（USD）。  

此公式确保协议整体 delta 中性：fETH 提供稳定性，xETH 捕捉放大后的价格变动。铸造时，用户存入 stETH，协议按当前比率铸造 fETH 和 xETH（初始比率基于目标 beta）。随着市场波动，xETH 的杠杆动态调整（价格下跌时杠杆增加），通过再平衡机制（燃烧多余稳定资产或调整抵押）维持 solvency，无需传统永续合约的资金费率。

### 基于 f(x) v1 逻辑，为其他代币（如 WBTC、其他 LST）设计做多逻辑
f(x) v1 的核心是“波动拆分”：将底层代币 T 的波动分配给稳定部分（fT，beta < 1）和杠杆部分（xT，beta > 1），总 beta = 1。v1 专为 ETH 设计，但逻辑通用，可扩展到其他代币（如 WBTC、rETH 等 LST）。以下是泛化做多逻辑，保持 v1 的零成本、低风险特性：

#### 1. **协议架构（Vault 机制）**
   - **抵押品**：使用代币 T 的流动性质押版本（LST，如 WBTC 的 cbBTC 或其他）。存入 n 单位 T 到 Vault。
   - **铸造资产**：
     - **fT**：稳定代币，目标 beta_T = 0.1（吸收 10% 波动），价值稳定于 T 的名义价值。
     - **xT**：杠杆做多代币，beta_T ≈ 0.9（初始），提供可变杠杆做多 T。
   - **初始比率**：铸造时，按目标 beta 分配，例如存入 1 T → 铸造 0.9 fT + 0.1 xT（调整以匹配 beta）。用户可选择只取 xT（卖出 fT 给市场）以纯做多。

#### 2. **做多逻辑（xT 持有者视角）**
   - **进入头寸**：用户存入 T 或购买 xT（从 Uniswap 等 DEX）。xT 立即提供杠杆暴露，无需借贷。
   - **杠杆计算**：动态杠杆 L = beta_x / (1 - beta_x)，其中 beta_x = n_x × x / (n × s)。  
     - 示例：若 beta_x = 0.9，则 L ≈ 9x（但 v1 限 4x，通过参数控制）。价格上涨时，xT 增值更快（杠杆放大收益）；下跌时，杠杆增加（xT 价值加速缩水，但协议再平衡防止清算）。
     - 公式推导：从核心公式推导，xT 的价格变动 Δx / x ≈ (Δs / s) × (n / n_x)，杠杆随 n_x / n 比率变化。
   - **收益来源**：
     - **价格暴露**：xT 捕捉 T 的 90%+ 波动，无资金费率（由 fT 持有者隐式补贴稳定性）。
     - **额外收益**：T 的 LST 收益（如 staking yield）按比例分配给 xT（约 90%）。
   - **退出头寸**：赎回 xT 为 T，无滑点（协议自动拆分）。

#### 3. **风险管理与再平衡**
   - **波动吸收**：fT 持有者承担少量下行（作为“稳定性溢价”），xT 持有者获上行杠杆。
   - **再平衡机制**（v1 风格）：
     - 若杠杆 > 阈值（e.g., 5x），协议自动燃烧多余 fT，注入抵押以降低 beta_x。
     - 若 T 价格暴跌 > 20%，触发 stabilization：部分 xT 转换为 fT，防止价值损失。
     - 无清算：杠杆动态调整，避免传统 perp 的强制平仓。
   - **参数设置**（针对不同代币调整）：
     | 代币 | 目标 beta_f | 初始杠杆上限 | 抵押品示例   | 适用场景                |
     | ---- | ----------- | ------------ | ------------ | ----------------------- |
     | WBTC | 0.1         | 4x           | cbBTC        | BTC 牛市杠杆            |
     | rETH | 0.15        | 3x           | rETH         | ETH LST 做多            |
     | UNI  | 0.2         | 2.5x         | UNI (无 LST) | 代币波动大，beta_f 稍高 |

#### 4. **实施步骤（智能合约伪代码逻辑）**
   - **铸造函数**：
     ```
     function mint(uint n, uint ratio_f) external {
         require(collateral >= n * price_T); // 存入 T
         uint n_f = n * ratio_f; // e.g., 0.9
         uint n_x = n - n_f;
         _mint(msg.sender, n_f, fT);
         _mint(msg.sender, n_x, xT);
         // 更新 beta: beta_x = n_x * value_x / (n * price_T)
     }
     ```
   - **再平衡**：
     ```
     function rebalance() external {
         uint current_leverage = beta_x / (1 - beta_x);
         if (current_leverage > MAX_LEVERAGE) {
             uint excess_f = calculate_excess(); // 基于公式
             _burn(excess_f, fT);
             // 调整抵押
         }
     }
     ```

此逻辑保持 f(x) v1 的简洁性：无 oracle 依赖（用链上价格），全抵押，无治理风险。扩展到其他代币需审计 LST 兼容性。对于高波动代币（如 meme coin），可调高 beta_f 以减风险。实际部署建议参考 v2 白皮书（支持多资产）。





### f(x) 协议 v1：动态杠杆变化与无清算机制

是的，在 f(x) 协议 v1 版本中，杠杆（leverage）是**动态变化的**，这正是其核心创新之一。它通过数学公式和再平衡机制，确保在可控条件下（例如价格波动不超过极端阈值，如 50% 暴跌）不会发生爆仓（liquidation）。不同于传统永续合约（perps），v1 无需资金费率或强制清算，而是让 xT（杠杆资产）的 beta（波动暴露）随市场调整，fT（稳定资产）隐式补贴稳定性。下面我基于白皮书逻辑详细解释，并提供代码实现（扩展之前的 Vault）。

#### 1. **动态杠杆变化机制**
- **核心公式回顾**：协议总价值守恒：**n × s = n_f × f + n_x × x**  
  - `n`：总抵押品数量（固定）。  
  - `s`：底层资产 T 现货价格（动态）。  
  - `n_f, n_x`：fT 和 xT 流通量（初始固定，但可再平衡）。  
  - `f ≈ s`（fT 稳定，beta_f ≈ 0.1，吸收 10% 波动）。  
  - `x`：xT 净值（动态）。  

- **杠杆定义**：xT 的杠杆 L = **1 / (1 - β_x)**，其中 β_x = (n_x × x) / (n × s) ≈ 0.9（初始）。  
  - **变化逻辑**：当 s（T 价格）上涨，x 增值更快（杠杆放大收益），β_x 略降，L 减小（更安全）。  
  - 当 s 下跌，x 缩水更快，β_x 升向 1，L 无限增加（但协议限阈值，如 4x-5x）。  
  - 示例（假设初始 n=1, s=1, β_f=0.1）：  
    - 初始：n_f=0.1, n_x=0.9, L ≈ 10x（但 v1 实际限 ~4x 通过参数）。  
    - s 涨 10% → x 涨 ~90%，L 降至 ~8x。  
    - s 跌 20% → x 跌 ~180%（但协议再平衡前），L 升至 ~15x（触发保护）。

- **可控条件**：白皮书强调，在“合理波动”下（e.g., 日波动 <20%），系统 solvency 保证：总价值始终 = n × s，无黑天鹅风险。极端情况下，fT 持有者承担少量损失（作为“稳定性溢价”），xT 持有者无清算。

#### 2. **防止爆仓的再平衡机制**
- **无清算设计**：v1 通过**Stability Pool**（稳定池）和自动再平衡维持 β_x < 阈值（e.g., 0.95）。  
  - 当 L > MAX_LEVERAGE（e.g., 5x），协议自动：  
    1. 计算多余价值：excess = n_f × f - β_f × (n × s)。  
    2. 燃烧多余 fT，注入额外抵押（从池中），降低 n_x / n 比率。  
  - 这确保 xT 价值不低于 0，且无强制平仓。fT 略微贬值补贴系统。

- **数学保证**：从公式推导，d(总价值)/ds = n（delta 中性）。xT 的 d x / x = (n / n_x) × (d s / s)，杠杆随 s 反比变化，但再平衡 cap L。

#### 3. **v1 代码实现（扩展 Vault：添加动态杠杆与再平衡）**
基于之前代码，我添加 `getLeverage()`（计算当前 L）和 `rebalance()`（自动调整，模拟 Stability Pool）。使用简单 oracle 更新 s。假设 18 decimals。

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

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
        // ... (类似之前)
    }
    
    event Mint(address indexed user, uint256 collateralAmount, uint256 fAmount, uint256 xAmount);
    event Rebalance(uint256 oldLeverage, uint256 burnedAmount);
}

interface IFxToken is IERC20 {
    function mint(address to, uint256 amount) external;
    function burn(address from, uint256 amount) external;
}
```

#### 4. **使用与测试建议**
- **做多流程**：mint 后，监控 `getLeverage()`。若 >5x，调用 `rebalance()`（任何人可调用，激励机制可选）。  
- **模拟**：在 Hardhat 测试中，mock oracle 改变 priceS，验证 L 变化（e.g., s 跌 10% → L 升 20%）。  
- **v1 局限**：Stability Pool 需单独合约（白皮书 Section 4）。实际部署参考 AladdinDAO v1 仓库（旧版）。

此机制确保 xT 持有者在牛市获杠杆收益，熊市杠杆渐增但协议自动护航，无爆仓风险。更多细节见白皮书 Section 3（Leverage Dynamics）。