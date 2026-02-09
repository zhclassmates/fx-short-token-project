# contracts/AGENTS.md - 智能合约文档

**技术领域**: Solidity智能合约  
**合约总数**: 10个  
**复杂度级别**: 高

---

## 合约一览表

| 合约名称 | 合约类型 | 功能描述 | 开发状态 |
|----------|----------|----------|----------|
| FxVaultV1.sol | 核心保险库 | 动态杠杆F/X代币分割 | 研究阶段 |
| ShortVaultV2.sol | 高级保险库 | 做空代币池 + 保险基金 | 生产就绪 |
| ShortVaultV1.sol | 研究原型 | 指数化虚拟权益机制 | ⚠️ 仅研究用途 |
| FToken.sol | ERC20代币 | 稳定代币（fToken） | 标准实现 |
| XToken.sol | ERC20代币 | 杠杆代币（xToken） | 标准实现 |
| ShortToken.sol | ERC20代币 | 做空代币（sToken） | 标准实现 |
| ChainlinkOracle.sol | 价格预言机 | Chainlink喂价适配器 | 需配置 |
| Mock*.sol | 模拟合约 | 测试环境专用 | 仅测试使用 |

---

## 继承关系架构

```
┌─────────────────────────────────────────┐
│           OpenZeppelin                 │
│  Ownable | ReentrancyGuard | ERC20    │
└──────────────┬──────────────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌──────────┐      ┌──────────┐
│ FxVault  │      │  Tokens  │
│  V1/V2   │      │F/X/Short │
└──────────┘      └──────────┘
```

---

## 核心状态变量

### 保险库合约通用变量
- `totalCollateral` - 总抵押品数量
- `BETA_F_TARGET` - 稳定资产目标比例 (0.1 * 1e18)
- `MAX_LEVERAGE` - 最大允许杠杆倍数 (5倍)
- `navF/navS` - 资产净值追踪（ShortVaultV2）

### ShortVaultV2特有变量
- `insurancePool` - 保险基金余额
- `status` - 合约状态（Normal/Rebalancing/Liquidation）
- `MIN_NAV_S` - sToken最小资产净值 (0.01)

---

## 安全防护机制

| 风险类型 | 防护措施 |
|----------|----------|
| 重入攻击 | 所有资金操作函数使用`nonReentrant`修饰符 |
| 权限控制 | 管理函数使用`onlyOwner`权限检查 |
| 零价格攻击 | Oracle价格必须大于0的校验 |
| 无限铸造 | 只有保险库合约可调用mint/burn |
| NAV归零保护 | MIN_NAV_S地板价机制 |

---

## 开发注意事项

1. **数值精度**: 全部计算使用`1e18`精度，禁止浮点数
2. **代码注释**: 业务逻辑注释使用中文，代码本身使用英文
3. **许可证声明**: 每个文件头部必须包含SPDX许可证
4. **事件触发**: 所有状态变更操作必须触发相应事件

---

## 合约部署顺序

```javascript
// 推荐的部署流程
1. 部署 MockCollateralToken（或使用真实抵押品合约）
2. 部署 FToken 和 XToken（或 ShortToken）
3. 部署 FxVaultV1 或 ShortVaultV2
4. 部署 ChainlinkOracle（配置喂价合约地址）
5. 调用 Vault.setToken() 关联代币合约
```

---

*适用范围: contracts/ 目录 | 父文档: ../AGENTS.md*
