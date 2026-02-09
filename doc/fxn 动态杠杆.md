

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# -------------------------------
# 参数
# -------------------------------
file_path = 'my_token_prices.csv'
target_leverage = 3.0      # 目标杠杆
confidence = 0.99           # VaR置信度
plot_dynamic = True

# -------------------------------
# 读取价格
# -------------------------------
df = pd.read_csv(file_path, parse_dates=['date'])
df.set_index('date', inplace=True)
df['return'] = df['price'].pct_change()
df.dropna(inplace=True)

# -------------------------------
# 动态杠杆计算
# -------------------------------
# 假设动态杠杆 = 目标杠杆 / (当前价格 / 初始价格)
P0 = df['price'].iloc[0]
df['leverage_dynamic'] = target_leverage * P0 / df['price']

# -------------------------------
# 每日 s token CR
# -------------------------------
df['CR_daily'] = 100 * (1 + df['return'] * df['leverage_dynamic'])

# -------------------------------
# 单日上涨 VaR（动态杠杆下）
# -------------------------------
upside_CR = df['CR_daily']
VaR_CR = np.percentile(upside_CR, confidence*100)

print(f"s token 做空 CR 阈值（{confidence*100}% VaR, 动态杠杆）：{VaR_CR:.2f}%")

# -------------------------------
# 可视化每日动态 CR
# -------------------------------
if plot_dynamic:
    plt.figure(figsize=(12,5))
    plt.plot(df.index, df['CR_daily'], label='每日动态 CR')
    plt.axhline(y=100, color='r', linestyle='--', label='CR=100% 爆仓线')
    plt.axhline(y=VaR_CR, color='g', linestyle='--', label=f'CR 阈值 ({confidence*100}% VaR)')
    plt.xlabel('日期')
    plt.ylabel('CR (%)')
    plt.title('s token 做空每日动态 CR（动态杠杆）')
    plt.legend()
    plt.grid(True)
    plt.show()
