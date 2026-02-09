# 研究流程（数据 → CR → 爆仓概率 → 报告）

该流程把项目里的脚本串成一条可复现的研究链路。适用于评估做空代币的 CR 阈值与爆仓风险。

## 0. 环境准备

```bash
pip install pandas numpy matplotlib seaborn requests
```

建议通过环境变量指定数据与输出目录：

```bash
export FXN_DATA_DIR="./data"
export FXN_OUTPUT_DIR="./analysis"
```

## 1. 价格数据获取

脚本：`scripts/price_day.py`

```bash
python scripts/price_day.py --contract 0x... --days 365 --data-dir "$FXN_DATA_DIR"
```

产物：`FXN_DATA_DIR/HYPE_protocol_prices.csv`（若获取失败，会尝试复用已有数据）

## 2. 做空 CR 阈值（VaR）

### 静态杠杆

脚本：`scripts/cr.py`

```bash
python scripts/cr.py --csv "$FXN_DATA_DIR/HYPE_protocol_prices.csv" --output-dir "$FXN_OUTPUT_DIR"
```

输出：`FXN_OUTPUT_DIR/cr_results.json`，并打印 `CR_short`

### 动态杠杆

脚本：`scripts/calculate_cr.py`

```bash
python scripts/calculate_cr.py --csv "$FXN_DATA_DIR/HYPE_protocol_prices.csv" --output-dir "$FXN_OUTPUT_DIR"
```

输出：`FXN_OUTPUT_DIR/dynamic_cr_results.json`

## 3. 爆仓模拟（秒级窗口）

脚本：

- `scripts/improved_simulation_crash.py`
- `scripts/crash_analysis_report.py`

运行示例：

```bash
python scripts/improved_simulation_crash.py --input-dir "$FXN_DATA_DIR" --output-dir "$FXN_OUTPUT_DIR"
python scripts/crash_analysis_report.py --input-dir "$FXN_DATA_DIR" --output-dir "$FXN_OUTPUT_DIR"
```

输出：

- `FXN_OUTPUT_DIR/爆仓概率对比图.png`
- `FXN_OUTPUT_DIR/爆仓模拟详细分析结果.xlsx`
- `FXN_OUTPUT_DIR/爆仓模拟分析报告.txt`

## 4. 爆仓真实性验证（可选）

脚本：`scripts/verify_crv_liquidation_binance.py`

需要配置环境变量：

```bash
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
```

运行：

```bash
python scripts/verify_crv_liquidation_binance.py
```
