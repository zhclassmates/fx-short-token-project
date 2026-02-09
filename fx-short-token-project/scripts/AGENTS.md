# scripts/AGENTS.md - 脚本工具文档

**技术领域**: 部署脚本 + 数据分析工具  
**文件总数**: 17个（JavaScript + Python）  
**技术栈类型**: 混合技术栈

---

## 文件分类说明

### JavaScript脚本（Hardhat环境）
| 文件名 | 功能说明 |
|--------|----------|
| deploy.js | 完整的合约部署流程 |
| vault.test.js | ⚠️ 注意：位于scripts/目录而非test/目录 |

### Python脚本（数据分析工具）
| 文件名 | 功能说明 |
|--------|----------|
| cr.py | 基于VaR的风险价值计算，CR阈值分析 |
| improved_simulation_crash.py | 高频爆仓模拟（3秒/5秒时间窗口） |
| crash_analysis_report.py | 聚合报告生成（PNG图表 + Excel表格） |
| leversafe_calculator.py | 杠杆保险费计算工具 |
| universal_liquidation_verifier.py | 交易所API数据验证 |
| _common.py | 共享工具函数（env, ensure_dir, write_json） |

---

## Python编码规范

### 模块导入顺序
```python
import json              # 第一步：标准库
import pandas as pd      # 第二步：第三方库
from _common import env  # 第三步：本地模块
```

### 标准命令行接口模板
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--input-dir", default="./data")
parser.add_argument("--output-dir", default="./output")
args = parser.parse_args()
```

### 环境变量使用方法
```python
from _common import env
data_dir = env("FXN_DATA_DIR", "./data")
output_dir = env("FXN_OUTPUT_DIR", "./output")
```

---

## 数据处理标准模式

### CSV文件读取
```python
df = pd.read_csv(filepath)
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
```

### 滚动窗口爆仓检测
```python
# 检测3秒内是否触及止损线
df['rolling_min'] = df['price'].rolling(window=3, min_periods=1).min()
df['liquidation'] = df['rolling_min'] <= df['price'] * 0.99
```

### 可视化图表标准
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 中文字体支持
plt.savefig(output_path, dpi=300, bbox_inches='tight')
```

---

## 分析工作流程

```
第一步：数据准备
   data/*.csv → 加载价格数据

第二步：风险分析
   cr.py → 计算抵押率（CR）阈值

第三步：模拟测试
   improved_simulation_crash.py → 计算爆仓概率

第四步：报告生成
   crash_analysis_report.py → 输出PNG图表 + Excel报告
```

---

## 使用注意事项

1. **测试文件位置特殊**: vault.test.js不在标准位置，运行时需要指定完整路径
   ```bash
   npx hardhat test scripts/vault.test.js
   ```

2. **Python依赖包**: 所有Python脚本都需要安装 pandas/numpy/matplotlib

3. **输出目录**: 脚本会自动创建output/子目录存放结果

4. **API调用限制**: 使用交易所验证脚本时需注意API频率限制

---

*适用范围: scripts/ 目录 | 父文档: ../AGENTS.md*
