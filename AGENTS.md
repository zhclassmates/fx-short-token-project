# AGENTS.md - f(x) 做空代币项目

**项目类型**: Hardhat + Solidity + Python DeFi 研究  
**核心技术栈**: Solidity 0.8.24, Hardhat, Python 3.x  
**生成时间**: 2026-02-09  
**代码分支**: master

---

## 项目概述

本项目是基于 f(x) 协议的做空代币研究项目，实现动态杠杆机制和爆仓模拟分析。

**⚠️ 重要提示：研究性质**  
本项目中的智能合约包含简化逻辑，仅供研究使用，不适合直接部署到生产环境。

---

## 项目目录结构

```
.
├── fx-short-token-project/     # 主项目目录（推荐入口）
│   ├── contracts/              # Solidity 智能合约（共10个）
│   ├── scripts/                # JavaScript部署脚本 + Python分析工具
│   ├── test/                   # Hardhat测试文件（部分测试在scripts目录）
│   ├── data/                   # CSV格式价格数据
│   └── docs/                   # 项目相关文档
├── fx-local-dev/               # 本地开发副本（通常可忽略）
└── doc/                        # 研究笔记和白皮书
```

---

## 快速查找指南

| 目标任务 | 文件位置 | 说明 |
|----------|----------|------|
| 主保险库逻辑 | contracts/FxVaultV1.sol | 动态杠杆核心实现 |
| 做空代币池 | contracts/ShortVaultV2.sol | 生产级实现，包含保险基金 |
| 合约部署脚本 | scripts/deploy.js | Hardhat部署脚本 |
| 抵押率分析 | scripts/cr.py | 基于VaR的风险价值计算 |
| 爆仓模拟 | scripts/improved_simulation_crash.py | 基于高频数据的爆仓模拟 |
| 通用工具函数 | scripts/_common.py | 环境变量、目录创建等 |

---

## 系统架构概览

```
保险库-代币架构:
┌─────────────────┐
│   FxVaultV1     │ ← 抵押品分割为 FToken + XToken
│  (动态杠杆)      │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌────────┐
│FToken │ │ XToken │
│(稳定币)│ │(杠杆币)│
└───────┘ └────────┘

┌─────────────────┐
│  ShortVaultV2   │ ← 做空代币池，生成 fToken + sToken
│ (带保险基金)     │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌─────────┐
│fToken │ │ sToken  │
│(稳定币)│ │(做空币) │
└───────┘ └─────────┘
```

---

## 常用开发命令

### Hardhat 命令（需在 fx-short-token-project/ 目录下执行）

```bash
# 安装项目依赖
npm install

# 编译智能合约
npx hardhat compile

# 运行测试（注意：测试文件位于scripts目录）
npx hardhat test scripts/vault.test.js

# 启动本地Hardhat节点
npx hardhat node
```

### Python 分析工具

```bash
# 安装Python依赖包
pip install pandas numpy matplotlib scipy requests

# 执行抵押率分析
python scripts/cr.py --csv data/HYPE_protocol_prices.csv --output-dir ./output

# 执行爆仓模拟
python scripts/improved_simulation_crash.py --input-dir data --output-dir ./output

# 生成分析报告
python scripts/crash_analysis_report.py --input-dir data --output-dir ./output
```

---

## 代码规范

### Solidity 编码规范
- **数值精度**: 使用 `1e18` 精度进行整数运算（禁止使用浮点数）
- **安全防护**: 涉及资金转移的函数必须添加 `nonReentrant` 修饰符
- **文件头**: 必须包含 SPDX 许可证声明
- **代码注释**: 业务逻辑使用中文注释，代码本身使用英文

### JavaScript 编码规范
- **设计模式**: 使用工厂模式 (`ethers.getContractFactory`)
- **异步处理**: 使用 `async/await` 配合 `.catch()` 进行错误处理
- **地址获取**: 使用 `await contract.getAddress()`（Ethers v6 风格）

### Python 编码规范
- **模块导入顺序**: 标准库 → 第三方库 → `_common.py`
- **命令行接口**: 所有脚本必须使用 `argparse` 处理命令行参数
- **类型注解**: 必须使用 `typing` 模块添加类型提示
- **文件输出**: 使用 `_common.write_json()` 进行JSON输出

---

## 核心概念说明

- **β (Beta)**: 资产占比参数，例如 `beta_f = 0.1` 表示10%稳定资产，`beta_x = 0.9` 表示90%杠杆资产
- **杠杆计算公式**: `L = 1 / (1 - beta_x)`
- **再平衡机制**: 当杠杆倍数 `L > MAX_LEVERAGE`（5倍）时自动触发
- **NAV**: 资产净值（Net Asset Value），用于动态跟踪盈亏
- **CR**: 抵押率（Collateral Ratio），用于计算爆仓阈值

---

## 重要使用限制

1. **ShortVaultV1**: 仅用于研究目的，使用虚拟权益计算方式
2. **价格预言机**: 当前使用Mock实现，生产环境需替换为Chainlink等真实预言机
3. **对冲机制缺失**: 做空池缺少实际对冲或资金池支持真实的盈亏结算
4. **测试文件位置**: `vault.test.js` 位于 `scripts/` 目录而非标准的 `test/` 目录

---

## 子项目文档

- [contracts/AGENTS.md](./fx-short-token-project/contracts/AGENTS.md) - 智能合约架构详细说明
- [scripts/AGENTS.md](./fx-short-token-project/scripts/AGENTS.md) - 脚本工具使用说明

---

*文档由 init-deep 生成 | 生成日期：2026-02-09*
