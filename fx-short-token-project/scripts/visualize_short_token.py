#!/usr/bin/env python3
"""
BTC Short Token 模拟与可视化
基于 f(x) 协议的做空代币表现分析
"""

import numpy as np
import matplotlib.pyplot as plt
import json
import os
from datetime import datetime

# 设置中文字体
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def calculate_nav_changes(
    price_changes,
    initial_nav_f=1.0,
    initial_nav_s=1.0,
    beta_f=0.1,
    beta_s=0.9,
    leverage_target=2.0,
    min_nav_s=0.01,
):
    """
    计算 fBTC 和 sBTC 的 NAV 变化

    参数:
        price_changes: BTC 价格变动率数组 (例如 [-0.2, -0.1, 0, 0.1, 0.2] 表示 -20% 到 +20%)
        initial_nav_f: fBTC 初始净值
        initial_nav_s: sBTC 初始净值
        beta_f: fBTC 波动比例
        beta_s: sBTC 波动比例
        leverage_target: 目标杠杆
        min_nav_s: sBTC 最低净值保护

    返回:
        nav_f_values: fBTC 净值数组
        nav_s_values: sBTC 净值数组
        leverage_values: 杠杆倍数数组
    """
    nav_f_values = []
    nav_s_values = []
    leverage_values = []

    nav_f = initial_nav_f
    nav_s = initial_nav_s

    for r in price_changes:
        # sBTC NAV: V_s_t = V_s_{t-1} * max(MIN_NAV, 1 - L * r_t)
        change_factor = 1 - leverage_target * r
        if change_factor <= min_nav_s:
            change_factor = min_nav_s

        nav_s = nav_s * max(change_factor, min_nav_s)

        # fBTC NAV 由恒等式推导
        # 简化计算: fBTC 吸收 beta_f 比例的波动
        nav_f = nav_f * (1 + beta_f * r)

        # 计算实际杠杆
        if nav_s > 0:
            # 简化的杠杆计算
            leverage = leverage_target * (1 + r) if r > 0 else leverage_target
        else:
            leverage = 0

        nav_f_values.append(nav_f)
        nav_s_values.append(nav_s)
        leverage_values.append(leverage)

    return np.array(nav_f_values), np.array(nav_s_values), np.array(leverage_values)


def simulate_price_path(initial_price=50000, days=365, volatility=0.03, trend=0.0001):
    """
    模拟 BTC 价格路径

    参数:
        initial_price: 初始价格
        days: 模拟天数
        volatility: 日波动率
        trend: 日趋势 (正数表示上涨，负数表示下跌)

    返回:
        prices: 价格数组
        returns: 收益率数组
    """
    np.random.seed(42)
    returns = np.random.normal(trend, volatility, days)
    prices = initial_price * np.cumprod(1 + returns)
    return prices, returns


def create_visualization(output_dir="./output"):
    """创建完整的可视化图表"""

    os.makedirs(output_dir, exist_ok=True)

    # 创建大图
    fig = plt.figure(figsize=(16, 12))

    # 1. 不同价格变动下的 NAV 表现
    ax1 = plt.subplot(2, 3, 1)
    price_changes = np.linspace(-0.5, 0.5, 101)  # -50% 到 +50%
    nav_f, nav_s, leverage = calculate_nav_changes(price_changes)

    ax1.plot(price_changes * 100, nav_f, "b-", linewidth=2, label="fBTC NAV")
    ax1.plot(price_changes * 100, nav_s, "r-", linewidth=2, label="sBTC NAV")
    ax1.axhline(y=1, color="gray", linestyle="--", alpha=0.5)
    ax1.axvline(x=0, color="gray", linestyle="--", alpha=0.5)
    ax1.set_xlabel("BTC Price Change (%)", fontsize=11)
    ax1.set_ylabel("NAV (USD)", fontsize=11)
    ax1.set_title("NAV vs BTC Price Change", fontsize=12, fontweight="bold")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. 价格路径模拟 - 震荡行情
    ax2 = plt.subplot(2, 3, 2)
    prices_sideways, returns_sideways = simulate_price_path(trend=0, volatility=0.025)
    days = np.arange(len(prices_sideways))

    ax2.plot(
        days,
        prices_sideways / prices_sideways[0],
        "orange",
        linewidth=1.5,
        label="BTC Price",
    )
    ax2.set_xlabel("Days", fontsize=11)
    ax2.set_ylabel("Normalized Price", fontsize=11)
    ax2.set_title("Sideways Market Simulation", fontsize=12, fontweight="bold")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 3. 价格路径模拟 - 下跌行情
    ax3 = plt.subplot(2, 3, 3)
    prices_down, returns_down = simulate_price_path(trend=-0.001, volatility=0.03)
    nav_f_down, nav_s_down, _ = calculate_nav_changes(returns_down)

    ax3.plot(
        days,
        prices_down / prices_down[0],
        "orange",
        linewidth=1.5,
        label="BTC",
        alpha=0.7,
    )
    ax3.plot(days, nav_f_down, "b-", linewidth=1.5, label="fBTC", alpha=0.7)
    ax3.plot(days, nav_s_down, "r-", linewidth=2, label="sBTC")
    ax3.set_xlabel("Days", fontsize=11)
    ax3.set_ylabel("Normalized Value", fontsize=11)
    ax3.set_title("Bear Market: sBTC Profits", fontsize=12, fontweight="bold")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. 价格路径模拟 - 上涨行情
    ax4 = plt.subplot(2, 3, 4)
    prices_up, returns_up = simulate_price_path(trend=0.001, volatility=0.03)
    nav_f_up, nav_s_up, _ = calculate_nav_changes(returns_up)

    ax4.plot(
        days, prices_up / prices_up[0], "orange", linewidth=1.5, label="BTC", alpha=0.7
    )
    ax4.plot(days, nav_f_up, "b-", linewidth=1.5, label="fBTC", alpha=0.7)
    ax4.plot(days, nav_s_up, "r-", linewidth=2, label="sBTC")
    ax4.set_xlabel("Days", fontsize=11)
    ax4.set_ylabel("Normalized Value", fontsize=11)
    ax4.set_title("Bull Market: sBTC Losses", fontsize=12, fontweight="bold")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # 5. 杠杆变化
    ax5 = plt.subplot(2, 3, 5)
    _, _, leverage_down = calculate_nav_changes(returns_down)
    _, _, leverage_up = calculate_nav_changes(returns_up)

    ax5.plot(days, leverage_down, "g-", linewidth=1.5, label="Bear Market", alpha=0.7)
    ax5.plot(days, leverage_up, "m-", linewidth=1.5, label="Bull Market", alpha=0.7)
    ax5.axhline(y=5, color="red", linestyle="--", alpha=0.5, label="Max Leverage (5x)")
    ax5.set_xlabel("Days", fontsize=11)
    ax5.set_ylabel("Leverage (x)", fontsize=11)
    ax5.set_title("Dynamic Leverage Changes", fontsize=12, fontweight="bold")
    ax5.legend()
    ax5.grid(True, alpha=0.3)

    # 6. 风险收益分析
    ax6 = plt.subplot(2, 3, 6)
    scenarios = ["-30%", "-20%", "-10%", "0%", "+10%", "+20%", "+30%"]
    nav_s_scenarios = []

    for change in [-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3]:
        _, nav_s, _ = calculate_nav_changes([change])
        nav_s_scenarios.append((nav_s[0] - 1) * 100)

    colors = ["green" if x > 0 else "red" for x in nav_s_scenarios]
    bars = ax6.bar(scenarios, nav_s_scenarios, color=colors, alpha=0.7)
    ax6.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax6.set_xlabel("BTC Price Scenario", fontsize=11)
    ax6.set_ylabel("sBTC Return (%)", fontsize=11)
    ax6.set_title("sBTC Returns by Scenario", fontsize=12, fontweight="bold")
    ax6.grid(True, alpha=0.3, axis="y")

    # 在柱状图上添加数值标签
    for bar, value in zip(bars, nav_s_scenarios):
        height = bar.get_height()
        ax6.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{value:.1f}%",
            ha="center",
            va="bottom" if value > 0 else "top",
            fontsize=9,
        )

    plt.suptitle(
        "BTC Short Token (fBTC/sBTC) Analysis Dashboard",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )
    plt.tight_layout()

    # 保存图表
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"short_token_analysis_{timestamp}.png")
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"Chart saved to: {output_file}")

    # 保存数据摘要
    summary = {
        "timestamp": timestamp,
        "scenarios": {
            "btc_down_30%": {"sBTC_return": f"{nav_s_scenarios[0]:.2f}%"},
            "btc_down_20%": {"sBTC_return": f"{nav_s_scenarios[1]:.2f}%"},
            "btc_down_10%": {"sBTC_return": f"{nav_s_scenarios[2]:.2f}%"},
            "btc_flat": {"sBTC_return": f"{nav_s_scenarios[3]:.2f}%"},
            "btc_up_10%": {"sBTC_return": f"{nav_s_scenarios[4]:.2f}%"},
            "btc_up_20%": {"sBTC_return": f"{nav_s_scenarios[5]:.2f}%"},
            "btc_up_30%": {"sBTC_return": f"{nav_s_scenarios[6]:.2f}%"},
        },
    }

    summary_file = os.path.join(output_dir, f"short_token_summary_{timestamp}.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to: {summary_file}")

    plt.show()
    return output_file


if __name__ == "__main__":
    output_path = create_visualization()
    print(f"\n✅ Analysis complete! Chart saved to: {output_path}")
