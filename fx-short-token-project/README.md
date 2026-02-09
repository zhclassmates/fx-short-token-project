# f(x) 做空代币项目

这是一个基于 f(x) 协议的做空代币项目，包含智能合约、分析工具与数据处理脚本。

## 项目结构

```
fx-short-token-project/
├── contracts/           # 智能合约文件
│   ├── FToken.sol      # F 代币合约
│   ├── FxVaultV1.sol   # 主保险库合约
│   ├── XToken.sol      # X 代币合约
│   └── MockCollateralToken.sol  # 模拟抵押代币
│   ├── ShortToken.sol  # 做空代币
│   ├── ShortVaultV1.sol # 做空代币池
│   ├── MockOracle.sol  # 测试预言机
│   └── ChainlinkOracle.sol # Chainlink 预言机适配
├── scripts/            # 分析脚本与工具
│   ├── deploy.js       # 合约部署脚本
│   ├── vault.test.js   # 合约测试脚本
│   ├── calculate_cr.py # CR 计算工具
│   ├── cr.py          # 做空 CR 分析
│   ├── leversafe_calculator.py # 杠杆安全计算器
│   ├── simulation_crash.py # 爆仓模拟
│   ├── improved_simulation_crash.py # 改进版爆仓模拟
│   ├── crash_analysis_report.py # 爆仓分析报告
│   ├── universal_liquidation_verifier.py # 通用爆仓验证器
│   ├── verify_liquidation.py # 爆仓验证
│   ├── verify_crv_liquidation_binance.py # Binance CRV 爆仓验证
│   └── price_day.py    # 价格分析工具
├── data/               # 数据文件
│   ├── fx_protocol_prices.csv      # f(x) 协议价格数据
│   └── HYPE_protocol_prices.csv    # HYPE 协议价格数据
├── docs/               # 文档
│   ├── fxn.md
│   ├── README_verify_crv_liquidation.md
│   ├── short_token_design.md
│   ├── research_flow.md
│   └── f(x)_whitepaper_v1 (1).pdf
├── hardhat.config.js
├── package.json
└── README.md
```

## 功能特性

### 智能合约
- **FxVaultV1**: 主保险库合约，实现 f(x) 协议的动态杠杆机制
- **FToken**: 稳定部分代币（beta < 1）
- **XToken**: 杠杆部分代币（beta > 1）
- **MockCollateralToken**: 模拟抵押代币，用于测试
- **ShortVaultV1 / ShortToken**: 做空代币池与 sToken（研究用途）

### 分析工具
- **CR 计算**: 计算做空代币的抵押率阈值
- **爆仓模拟**: 模拟不同市场条件下的爆仓风险
- **杠杆安全分析**: 评估杠杆头寸的安全性
- **爆仓验证**: 验证交易所爆仓记录的真实性

### 数据管理
- 价格数据收集和处理
- 历史数据分析
- 风险评估报告生成

## 快速开始

### 智能合约部署

1. 安装依赖：
```bash
npm install
```

2. 编译合约：
```bash
npx hardhat compile
```

3. 部署合约：
```bash
npx hardhat run scripts/deploy.js --network localhost
```

### 分析工具使用

1. 安装 Python 依赖：
```bash
pip install pandas numpy matplotlib scipy requests
```

2. 可选环境变量（数据与输出目录）：
```bash
export FXN_DATA_DIR="./data"
export FXN_OUTPUT_DIR="./analysis"
```

3. 运行 CR 分析：
```bash
python scripts/cr.py --csv "$FXN_DATA_DIR/HYPE_protocol_prices.csv" --output-dir "$FXN_OUTPUT_DIR"
```

4. 运行爆仓模拟：
```bash
python scripts/improved_simulation_crash.py --input-dir "$FXN_DATA_DIR" --output-dir "$FXN_OUTPUT_DIR"
python scripts/crash_analysis_report.py --input-dir "$FXN_DATA_DIR" --output-dir "$FXN_OUTPUT_DIR"
```

## 技术栈

- **区块链**: Solidity, Hardhat, Ethers.js
- **数据分析**: Python, Pandas, NumPy, Matplotlib
- **API 集成**: Binance API, OKX API

## 文档

- `docs/fxn.md`
- `docs/README_verify_crv_liquidation.md`
- `docs/short_token_design.md`
- `docs/research_flow.md`
- `docs/f(x)_whitepaper_v1 (1).pdf`

## 许可证

本项目仅供学习和研究使用。
