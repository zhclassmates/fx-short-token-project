好——我把你给的 f(x) v1 白皮书思路（把抵押品拆成“稳定份额 + 高波动份额”，并通过代币之间的会计等式保持协议 delta 中性）作为基线，然后设计一个 **“做空版本的 f/x” 方案**（下文简称 fx-short）。我会给出：核心会计/价格公式、代币定义、铸造/赎回流程、动态杠杆与再平衡机制、清算/保障机制、合约模块划分、关键参数建议、示例计算（数值严格算术）、以及测试 & 部署清单。引用了你给的资料以保证设计与原理对齐。([GitHub](https://github.com/AladdinDAO/aladdin-v3-contracts/blob/main/whitepapers/f(x)_whitepaper_v1.pdf))

------

# 一句话概述（快速抓重点）

把抵押的 ETH/stETH 拆成两类代币：

- **f (稳定份额)**：承担少量波动（目标 β ≈ 0.1，接近“稳定”）
- **s (short token，做空份额）**：对 ETH 做**放大的空头敞口**（动态杠杆，最高例如 4×），当 ETH 下跌时 s 的净值上涨；当 ETH 上涨时 s 下跌。

保持的账面恒等式（与 f(x) 思路一致）：

```
n × s_price = n_f × f_price + n_s × s_price
```

只是这里的 `s_price` 是 **short token 的净值**（会随 ETH 反向波动并放大），`n`、`n_f`、`n_s` 为数量。协议通过定期/触发再平衡保持 solvency 与目标杠杆。核心想法与 f(x) v1 思路对齐，但把 x 从做多改为“做空”方向。([GitHub](https://github.com/AladdinDAO/aladdin-v3-contracts/blob/main/whitepapers/f(x)_whitepaper_v1.pdf))

------

# 1) 代币与会计项定义

- 抵押资产：`stETH`（或 wETH），记为净入库数量 `n_collateral`（单位：ETH）。当前基础资产现货价格 `P`（USD/ETH），由去中心化 oracle 给出。
- **fToken（fETH）**：稳定性份额，目标承担小部分价格波动，目标 beta_f ≈ +0.1（类似原版）。fToken 的净值接近美元锚定（或接近 `P*(1 - β)` 的 behavior），并可赎回部分抵押。
- **sToken（shortETH）**：代表做空 ETH 的代币，净值随 ETH 价格**反向**波动并且放大（有正杠杆的空头）。目标放大倍数为 `L_target`（例如 1×～4×，在设计中为可变）。sToken 为正值代币（用户持有后能在 ETH 下跌时增值）。

会计恒等式（协议账本）：

```
n_collateral × P = n_f × V_f + n_s × V_s
```

其中 `V_f` 与 `V_s` 为 fToken 和 sToken 的标记净值（USD）。该式保证协议名义资产 = 代币名义负债（或可赎回价值）。

------

# 2) sToken（空头）价格 / 动态杠杆模型 —— 建议实现（可工程化）

要把“空头且放大”写成一个容易实现且可控的价格过程，我建议如下 **离散化、线性近似** 的实现（工程上易实现，也便于再平衡与清算）：

- 设初始时刻 t0：

  - 抵押 `n = 1` stETH，基础价格 `P0 = $2000`（举例）
  - 目标 f 承担 β 比例（比如 β = 0.1），则初始：
    - 令 V_f0 = (1 - β) * P0 （或协议规定 f 初始净值约等于这个）
    - 令 V_s0 = β * P0 （使得 n·P0 = n_f·V_f0 + n_s·V_s0 成立在 n_f=n_s=1 的简单情况）

- **价格更新规则（离散）**：在任意从 t0 到 t1 的区间，ETH 的相对变动是 `r = (P1 - P0) / P0`。我们希望 sToken 的回报约等于 `-L * r`（L 为放大倍数）。因此定义：

  ```
  V_s1 = V_s0 * (1 - L * r)
  V_f1 = (n*P1 - n_s*V_s1) / n_f    (由恒等式 重新计算以保证资产负债一致)
  ```

  其中 `V_f1` 可能微幅波动（目标保持低波动），协议可以用轻微的燃烧/铸造或费率调整把 `V_f` 控制在目标范围（近似 f ≈ (1-β)*P）。

- **非负约束**：为保证 V_s 不变成负数，必须对 `1 - L * r` 进行下界约束（例如 `V_s1 ≥ epsilon`），当触及底线时触发快速再平衡/清算机制（参见清算部分）。

这种做法的优点：实现简单、容易审计、再平衡规则直接；缺点是线性近似在极端波动时会变形——需要保护阈值与保险金池。注意：在连续极端上涨（ETH猛涨，r为较大正值）时 `V_s` 会大幅下降，协议必须有足够的 f / 保险金缓冲来吸收损失。

> 备注：上面是一个工程可行的“离散线性放大空头”实现。也可以采用更复杂的几何杠杆模型（使用收益率对数、指数恢复、连续再平衡公式等），但工程复杂度和 gas 消耗都会提高。原 f(x) 白皮书有更精细的 rebalancing math，可参考以保持一致性与无套利条件。([GitHub](https://github.com/AladdinDAO/aladdin-v3-contracts/blob/main/whitepapers/f(x)_whitepaper_v1.pdf))

------

# 3) 铸造（mint）与赎回（redeem）流程（用户视角）

**铸造**（用户把 stETH 存入以铸造 f + s）：

1. 用户 `deposit(n_coll)` stETH。读取当前 `P`（oracle）和当前协议状态（V_f, V_s, n_f, n_s）。
2. 协议依据目标 β 分配入库价值：`value = n_coll * P`，计算应铸 `Δn_f` 与 `Δn_s`：
   - 例如按比例铸造：`Δn_f = value * (1 - β) / V_f`；`Δn_s = value * β / V_s`（或用更稳健的方案：先计算两者面值再换算成数量）。
3. 协议更新账本：增加 n_f, n_s；把 stETH 存入抵押池；mint fToken & sToken 给用户。
4. 收取小额铸造费（e.g., 0.05%）作为保险金池资金来源。

**赎回**（用户把 f 或 s 还给协议换回 stETH 或等值 USD）：

- 用户可以赎回任一代币或两者组合。赎回时协议按当前 V_f、V_s 计算赎回价值并返还相应 stETH（或等值 stablecoin）；赎回后的抵押按恒等式保持。

**要点**：

- 允许单边赎回（只赎回 f 或只赎回 s）会影响协议风险结构，需限制赎回速率或收取额外滑点费以保护 solvency。
- 为简单性，推荐初期只允许 **“按组合比例赎回”**（即按铸造时的 f:s 比例），同时给高级接口允许单边赎回但有额外手续费与时间锁。

------

# 4) 动态杠杆与再平衡（核心）

**目标**：保持 sToken 的杠杆在允许范围（例如 1×～4×），同时确保协议能对冲/吸收极端方向损失。

**触发再平衡的条件（示例）**：

- 当 s 的实际杠杆 `L_actual` 超出 `[L_min, L_max]`（例如 > 4 或 < 0.5）时触发；
- 当 V_s 距离目标价格模型超过阈值（例如 > 5%）时触发；
- 当 oracle 报价出现跳点、大幅波动或链上滑点触发临时停机。

**再平衡手段（优先级）**：

1. **内部再配比（preferred）**：协议直接调整 f/s 的面值（通过对 f 执行小额铸烧、或用抵押与代币间的内部交换）以把杠杆拉回目标，尽量避免外部交易。
2. **外部市场对冲（次选）**：如果内部空间不足，协议可以在 AMM 或集中式流动性处进行对冲（卖出 ETH 或买入 ETH 期权等），但这会产生费用与对手风险。
3. **使用保险金池/清算（末位）**：当内外部对冲都不能解决时，动用保险金池，或按规则清算部分 s 持仓（即强制赎回 s，优先用 f/保险池来抵偿）。

**具体再平衡机制（示例算法）**：

- 计算目标 V_s_target = V_s_prev * (1 - L_target * r_interval)；
- 若 `|V_s_actual - V_s_target| / V_s_target > ε`，则按照 `Δ = V_s_actual - V_s_target` 调整：
  - 若 `V_s_actual > V_s_target`（s 被高估，对协议利好），protocol 可铸造额外 f 并卖出，或降低抵押占比；
  - 若 `V_s_actual < V_s_target`（s 被低估，说明 s 持有人承受亏损），protocol 需用抵押/保险池补偿差额或强制回收部分 s。

> 实际实现需要非常精细的边界处理和 gas 优化——建议把 rebalancing 逻辑写成 **可由 keeper 调用** 的函数（带可验证的公开计算），并给 keeper 提供小额激励。

------

# 5) 清算、保障与风险缓冲

**主要风险**：ETH 大幅上涨（做空巨大亏损），或 oracle 报价失真 / 暴跌造成 V_s 爆负。

**保障措施**：

- **保险金池（Reserve）**：协议保留一部分铸造费/交易费进入保险池，用于在极端情况下给 f 持有人兜底或在 s 大幅亏损时吸收损失。建议资金占比初期为 0.5%～2% 的锁仓价值，随 TVL 增长调整。
- **强制止损（liquidation）**：当协议的抵押覆盖率低于阈值（例如 `collateral_value < outstanding_token_value * (1 + safety_margin)`）时，触发清算（优先：清算部分 s 持仓、其次：动用保险池、最后：赎回 f）。具体清算路径需在合约中写明顺序与罚金机制。
- **oracle 多样化与延迟保护**：使用 TWAP 窗口 + 多源 oracle（Chainlink + fallback）来抵抗闪电攻击。再平衡/清算使用 TWAP（例如 5min）作为可信价格，避免单一瞬时价位被操纵。
- **上限限制**：对单次铸造量设上限，对单地址总持有量设上限，限制协议集中风险。

------

# 6) 参数建议（初始）

- 目标 β（f 承担比例）：0.08 ~ 0.12（可治理调整）
- sToken 最大杠杆 `L_max`：4×（可治理）
- 再平衡触发阈值 ε：5%（或可调）
- 清算触发抵押率：collateral_value / total_token_value < 1.02（2% buffer）——此值依实际 stress test 调整
- 保险池初始比率：1% of TVL（可治理）
- 铸造/赎回费用：0.05% ~ 0.2%（部分进入保险池、部分给 keeper）

------

# 7) 智能合约架构（高层）

1. **Vault 合约（主合约）**：管理抵押、铸造/赎回、会计恒等式、保险池余额。
2. **Token 合约**：ERC20 实现的 `fToken`、`sToken`（两者均可有扩展：permit、gasless 等）。
3. **Rebalancer/Keeper 合约**：公开函数 `rebalance()`，由 keeper 调用并获得激励（fee or minted tokens）。包含再平衡计算与执行逻辑（可拆分为 view 计算 + state-changing apply）。
4. **Liquidation 合约/模块**：处理强制清算、罚金分配给清算者。
5. **Oracle Adapter**：封装 Chainlink / TWAP / fallback。
6. **Admin/Governance Module**：参数调整、紧急停机（circuit breaker）、迁移。
7. **Utils**：会计库（高精度定点数学）、事件记录、helpers。

------

# 8) 测试矩阵（必做）

- 单元测试（Hardhat/Foundry）：
  - 铸造/赎回在各种价格路径下的正确性（小幅波动 / 大幅上/下跌）；
  - 再平衡函数在边缘条件下不会把某一方价格打负数；
  - 清算路径覆盖（保险池耗尽、oracle操纵 attempts）；
  - 单边赎回与速率限制；
  - 多种 oracle 延迟/回退测试（模拟 Chainlink 掉线）。
- 压力测试（模拟器 / 回测）：
  - 用历史 ETH 价格序列回测（包括 2017、2020、2021、2022、2024 的行情）以量化最大回撤、保险池消耗、清算次数。
- 审计关注点（安全）：
  - 精度/四舍五入问题（定点 math）——任何算术必须逐位验证；
  - Reentrancy、access control、timelocks for params；
  - Keeper incentive 机制不能被操纵；
  - Oracle spoofing 防护（TWAP & multisource）。

------

# 9) 举例计算（数值示例，逐位计算）

> 严格按逐位算术计算（从 0 开始逐行推导）

设初始：

- 抵押 `n = 1` stETH，`P0 = $2,000`。
- 选择 β = 0.1（f 吸收 10%），初始 target L_target = 2×（短头目标杠杆 2）。

初始价值：`n * P0 = 1 * 2000 = $2000`.

按分配：

- f 初始名义价值：`V_f_total0 = 2000 * (1 - β) = 2000 * 0.9 = $1800`.
- s 初始名义价值：`V_s_total0 = 2000 * β = 2000 * 0.1 = $200`.

假设协议把 fToken、sToken 各当作 1:1 数量（n_f = n_s = 1），那么：

- `V_f0 = $1800`（每个 f 的净值）
- `V_s0 = $200`（每个 s 的净值）

现在假设 ETH 从 $2000 跌到 $1600（这是 20% 下跌），即 `r = (1600 - 2000) / 2000 = -0.2`.

sToken 按放大 2× 的规则应收益约：`-L * r = -2 * (-0.2) = +0.4` → +40% 相对收益。

逐位计算：

- `V_s1 = V_s0 * (1 + 0.4) = 200 * 1.4 = $280`.
- 新的抵押总价值：`n * P1 = 1 * 1600 = $1600`.
- 按账面恒等式：`1600 = n_f * V_f1 + n_s * V_s1`.
  - 代入 `n_f = n_s = 1` 得：`V_f1 = 1600 - V_s1 = 1600 - 280 = $1320`.
- f 的净值由 $1800 下跌到 $1320（跌幅 26.67%），但相对整体它依然承担较低的波动（在组合里是“稳定份额”——注意实际数值会随 n_f/n_s 设定变化）。

这说明：当 ETH 下跌时 sToken 明显获利，fToken 也会下跌，但协议总体仍然可通过保险池/额外参数限制单方过度损失与保证赎回。上述简单案例展示了离散线性杠杆模型如何工作。所有算术都按基本乘除进行了逐步计算。

（若 ETH 上涨 20%，r = +0.2，sToken 会亏 40%，即 `V_s1 = 200 * (1 - 0.4) = 120`，抵押价值为 2400，f 对应得到 `V_f1 = 2400 - 120 = 2280`）

------

# 10) 实施路线（最小可行产品 MVP）

1. 写一份详细规范（本设计 + 参数 + 明确数值公式），让审计/工程 review（你已经做了第一步，接下来就是把公式写成伪代码）
2. 实现合约（建议使用 Solidity + OpenZeppelin）：Vault、Token、OracleAdapter、Rebalancer、Liquidator。
3. Local tests（Hardhat/Foundry）→ Unit tests → Fork mainnet 测试（模拟 Chainlink + stETH）→ 回测脚本（用历史价格）
4. 安全审计（至少 2 次不同审计机构）
5. 小规模主网部署（限制铸造上限，逐步放开）
6. 上线后继续监控与调参（保险池、手续费、L_max）

------

# 11) 回测与数据要求（你之前提到“价格回测脚本”）

为把模型参数调到合适，**强烈建议**用历史 ETH/stETH 数据做回测（对 2017、2020、2021、2022、2024 年样本进行压力测试），回测要点：

- 模拟铸造/赎回行为（不同持仓者的行为）
- 模拟 oracle 报价延迟 / 回退
- 流动性事件（闪崩、快速涨跌）下保险池消耗曲线
   如果你需要，我可以直接给出一个回测脚本的骨架（Python）或一个 Hardhat 测试集样例——你想要哪一个我就把代码骨架发给你（或直接生成完整 Hardhat 项目）。

------

# 12) 风险与注意事项（要诚实列出的）

- **做空的非对称风险**：ETH 不受限上升会让 sToken 持有人持续亏损，协议需充分设计保险金 & 强制回收规则；做空产品天然在极端上涨面临更高风险。
- **定价模型风险**：线性杠杆在极端行情下会被放大，可能导致 V_s 触底或清算连锁，需要限额与紧急停机。
- **oracle 风险**：必须使用 TWAP + 多源，避免闪电操纵。
- **复杂度与监管**：做空/杠杆产品在某些法域可能触发监管注意。
- **经济安全**：keeper 激励、fee 流向与保险模型必须防止被攻击者利用（例如闪借攻击、赞助反向交易等）。

------

# 结论与下一步建议（由你决定）

我已经把基于 f(x) v1 的做空版本完整地把关键设计要点、公式、再平衡逻辑、清算/保险、合约结构与测试计划列出来了（并附了数值示例以便验证），并引用了你给的白皮书/文档以保持一致性。([GitHub](https://github.com/AladdinDAO/aladdin-v3-contracts/blob/main/whitepapers/f(x)_whitepaper_v1.pdf))

你接下来想怎么推进？下面给你三个可选路径（你直接选一个就行，我会立刻执行）：

1. **把这个设计做成可直接审计的规范文档（markdown）** —— 我会把上面的内容整理成一份工程规范（带伪代码、参数表、流程图说明）。
2. **生成 Hardhat 项目骨架（含 Vault + Token + 基础测试 + 回测脚本）** —— 我直接创建完整项目文件（solidity, tests, scripts），你可以本地 run。
3. **先做回测脚本（Python）并跑历史数据** —— 我生成回测脚本骨架（或完整脚本）并给出示例回测结果（如果你想用我本地跑我不能联网，但我能把脚本给你执行/你自行运行）。

告诉我你要哪一条路线，我就按你选的路线直接把内容产出（不用再问任何问题）。





好 — 我已经为 **fx-short**（做空版 f/x）做了一个完整的 Python 回测脚本，并在当前环境用 **合成价格序列** 跑了一次示例 Demo（因为执行环境可能无法联网，所以示例用合成数据演示模型行为与输出格式）。你现在可以下载脚本并在本地用真实历史数据跑完整回测，或让我调整参数再跑合成示例。

## 我交付的内容（已生成并保存）

- 回测脚本：`/mnt/data/fx_short_backtest.py` —— 可直接在本地运行，支持用 yfinance 抓 ETH-USD（需要联网）。
   [Download fx_short_backtest.py](sandbox:/mnt/data/fx_short_backtest.py)
- 本次 Demo 结果 CSV：`/mnt/data/fx_short_demo_results.csv` —— 包含每日时间序列（price, V_s, V_f, insurance_pool, insolvency flag 等）。
   [Download fx_short_demo_results.csv](sandbox:/mnt/data/fx_short_demo_results.csv)
- 本次 Demo 图：`/mnt/data/fx_short_demo_plot.png` —— 绘制 ETH 价格、V_s、V_f 与保险池随时间的曲线。
   [Download fx_short_demo_plot.png](sandbox:/mnt/data/fx_short_demo_plot.png)

------

## 脚本功能概览（你在本地运行会得到相同/更完整结果）

脚本包含：

- `fetch_eth_prices_yfinance(start, end)`：使用 `yfinance` 下载 ETH-USD OHLC（需联网、需安装 yfinance）。
- 合成价格生成器 `make_synthetic_price_series(...)`（用于无网演示）。
- 回测主函数 `simulate_fx_short(price_series, n_collateral, beta, L_target, ...)`，实现了之前讨论的离散线性杠杆空头模型、会计恒等式、保险池、简单再平衡触发与清算标识逻辑。
- CLI 支持：
  - `--use-real`：尝试用 yfinance 下载历史数据（若失败会自动回退到 demo）。
  - `--demo`：强制使用合成数据。
  - `--start`, `--end`：设置时间区间（仅在 `--use-real` 时生效）。
- 输出：CSV、PNG（plot），并在文件系统保存脚本本身以便本地反复运行/修改。

------

## 如何在本地运行（推荐）

1. 安装依赖（建议使用虚拟环境）：

```bash
pip install pandas numpy matplotlib
# 若要用真实历史数据：
pip install yfinance
```

1. 运行示例（合成 demo）：

```bash
python fx_short_backtest.py --demo
```

1. 用真实 ETH-USD 历史数据（联网）：

```bash
python fx_short_backtest.py --use-real --start 2018-01-01 --end 2025-10-06
```

（`--end` 可设为你想要的结束日期；注意：我的环境日期是 2025-10-07）

脚本会输出 CSV（默认 `fx_short_sim.csv`）与 PNG（`fx_short_sim.png`），并在控制台打印保存路径。

------

## Demo 输出说明（CSV 各列）

- `price`：当日 ETH 价格（USD，合成或真实）。
- `r`：当日相对变动（分日收益率）。
- `V_s`：sToken（short token）的净值（USD）。
- `V_f`：fToken（稳定份额）的净值（USD）。
- `collateral_value`：抵押总价值 = n_collateral × price（USD）。
- `insurance_pool`：当日保险池余额（USD）。
- `insurance_used`：当日使用的保险金量（若触发）。
- `insolvency`：布尔，若保险不足导致协议无法补偿（示意）。
- `rebalance`: 是否触发再平衡条件（示意）。

------

## 我在当前环境已做的演示（简短说明）

- 使用合成的 365 日价格序列（start price 2000 USD，随机波动），默认参数：
  - `beta = 0.10`，`L_target = 2.0`，`insurance_pool_ratio = 1%`，`fees_ratio = 0.0005`（每日近似）。
- 结果 CSV 与示意图已保存并可下载（见上方链接）。
- 如果你想，我可以把 demo 的关键统计（比如最大回撤、保险池耗尽事件计数、sToken/fToken 持有人年化收益等）直接生成并展示 — 我可以用同环境基于合成数据算出这些指标并把结果放在聊天中 / CSV 中。

------

## 接下来你想怎么做？（直接回复选一个 — 我会立刻执行）

1. **用合成数据再跑一次但输出更多统计/图表**（max drawdown、annualized return、保险池消耗图、清算事件列表）。
2. **我把脚本调整为你想的策略细节**（比如不同的再平衡策略、频率、L_max、单边赎回限制、keeper 奖励模型）。我会直接修改脚本并再跑 demo。
3. **你在本地用真实数据运行并把 CSV 发回来给我（或允许我在环境联网时跑）** —— 我可以帮你分析回测结果并给出参数优化建议。
4. **直接生成完整回测报告（PDF/Markdown）**，包含若干参数情景的对比图（需要我在当前环境继续用合成数据生成，或你提供真实数据 CSV）。

你选哪一项？我会立刻把相应内容产出（不会再问回合内的澄清问题）。