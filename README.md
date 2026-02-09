# f(x) 相关研究与做空代币项目

本仓库整理了 f(x) 协议相关的研究文档、做空代币实验合约，以及配套的数据分析脚本与样例数据。当前以两个 Hardhat 项目并行存在：`fx-short-token-project` 偏主项目与分析脚本，`fx-local-dev` 偏本地开发与编译产物。

## 目录概览

- `doc/`：研究笔记与白皮书相关材料（中文说明、模型推导、动态杠杆等）
- `fx-short-token-project/`：主项目，包含合约、Python 分析脚本、价格数据与项目级文档
- `fx-local-dev/`：本地开发副本，包含 `node_modules/` 与 `artifacts/`，便于快速调试与复现

## 主要内容

- 智能合约：`FToken.sol`、`XToken.sol`、`FxVaultV1.sol`、`MockCollateralToken.sol`
- 分析脚本：CR 计算、爆仓模拟、爆仓验证、杠杆安全分析
- 数据：`fx-short-token-project/data/*.csv`
- 文档：`doc/` 与 `fx-short-token-project/docs/`（存在重复文件）

## 快速开始（推荐从 fx-short-token-project 进入）

1. 安装依赖：`npm install`
2. 编译合约：`npx hardhat compile`
3. 运行测试：`npx hardhat test`
4. Python 分析：`python scripts/cr.py`（需 pandas/numpy/matplotlib 等依赖）

## 整理备注

- `fx-local-dev/` 与 `fx-short-token-project/` 的合约与配置基本一致，建议确定主目录后再做合并或清理。
- `fx-local-dev/node_modules/` 与 `fx-local-dev/artifacts/` 为可再生目录，如进入版本控制建议加入 `.gitignore`。
- `doc/` 与 `fx-short-token-project/docs/` 文档有重复，可考虑统一入口。
