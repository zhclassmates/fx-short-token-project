# 做空代币（sToken）机制草案

本文是 `fx-short-token-project` 的研究级设计说明，给出做空代币的公式、风控与合约接口草案。当前实现不包含真实对冲，仅用于模型推演与原型验证。

## 目标与前提

- 目标：给出一个“做空标的资产”的代币化产品（sToken），可通过存入稳定币获得做空敞口。
- 前提：需要可靠的价格预言机；若要真实落地，必须有对冲或风险准备金来实现 PnL 结算。

## 记号

- `P_t`：标的资产价格（1e18 精度）
- `L`：目标杠杆（1e18 表示 1x）
- `NAV_t`：sToken 净值（index）
- `S`：sToken 总供应
- `E_t`：资金池权益（研究中的“虚拟权益”）

## 做空指数化公式（研究版）

做空方向的离散指数（类似反向 ETF）：

```
r_t = (P_t - P_{t-1}) / P_{t-1}
NAV_t = NAV_{t-1} * (1 - L * r_t)
```

- 当 `P_t` 上涨，`r_t > 0`，`NAV_t` 下降（亏损）。
- 当 `P_t` 下跌，`r_t < 0`，`NAV_t` 上升（盈利）。

## 份额铸造与赎回

按 NAV 定价的“份额型”设计：

```
shares = collateral_in / NAV_t
collateral_out = shares * NAV_t
```

适用于“池化短仓”模型（全体 sToken 共享一个短仓指数）。

## 风控与结算

### 风控要点

- 价格跳空与高杠杆会导致 `NAV_t` 急剧下跌。
- `NAV_t` 在极端情况下可能趋近 0，需要下限保护（例如最小 1）。
- 建议将 `L` 设为可调参数，并设置最大杠杆上限。

### 抵押率与清算路径（合约内实现）

合约内加入了两层阈值：

- `minCollateralRatio`：健康阈值（例如 1.05）。当抵押率低于该值时，系统会“去杠杆”并下调 `NAV` 以恢复安全区。
- `liquidationRatio`：清算阈值（例如 1.0）。当抵押率低于该值时触发全局清算，`NAV` 固定为 `assets / supply`，用户按比例赎回。

### 真实落地的结算机制（需要补齐）

若要让 `NAV_t` 真实反映盈亏，需要额外资金或对冲工具：

- 方案 A：使用链下或链上衍生品（Perp）对冲
- 方案 B：设立保险/稳定池，负责在盈利时注入资金、亏损时回收资金
- 方案 C：与 f(x) 结构结合，由 fToken/xToken 侧为 sToken 提供对冲池

当前合约仅实现了“虚拟权益”与 `syncEquity` 操作（研究用途）。

## 合约草案（ShortVaultV1 / ShortToken）

文件位置：

- `fx-short-token-project/contracts/ShortToken.sol`
- `fx-short-token-project/contracts/ShortVaultV1.sol`

核心接口：

- `updateIndex()`：按预言机价格更新 NAV
- `deposit()`：以 NAV 铸造 sToken
- `redeem()`：以 NAV 赎回稳定币
- `syncEquity()`：研究用途，人工同步“虚拟权益”与实际资金池

## 下一步建议

1. 选择真实结算路径（对冲或保险池）
2. 明确清算与极端行情处理（断路器、强制减仓）
3. 把 CR / VaR 风控模型接入合约参数（例如动态杠杆/限额）
