#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC 做空代币设计与模拟可视化
基于 f(x) 协议的做空代币研究

设计要点:
1. 使用 f(x) 协议的分割机制：抵押品分割为 FToken（稳定）和 XToken（杠杆）
2. 做空代币通过反向追踪 BTC 价格获得收益
3. 动态杠杆调整机制防止爆仓
4. 支持多种杠杆倍数（1x, 2x, 3x）
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec

# 设置中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# BTC 做空代币设计参数
BTC_SHORT_TOKEN_PARAMS = {
    "name": "BTC Short Token",
    "symbol": "sBTC",
    "underlying": "BTC",
    # 杠杆参数
    "leverage_options": [1.0, 2.0, 3.0],  # 支持的杠杆倍数
    "max_leverage": 5.0,  # 最大杠杆限制
    "rebalance_threshold": 4.5,  # 再平衡触发阈值
    # 抵押率参数
    "initial_collateral_ratio": 1.5,  # 初始抵押率 150%
    "min_collateral_ratio": 1.2,  # 最低抵押率 120%
    "liquidation_ratio": 1.05,  # 清算阈值 105%
    # 费用参数
    "minting_fee": 0.001,  # 0.1% 铸币费
    "redemption_fee": 0.001,  # 0.1% 赎回费
    "management_fee": 0.0001,  # 每日管理费 0.01%
    # 风险控制
    "volatility_threshold": 0.15,  # 日波动率阈值 15%
    "circuit_breaker": 0.20,  # 熔断机制 20%单日跌幅
    "cooldown_period": 24,  # 冷却期（小时）
}


def fetch_btc_historical_data(days: int = 365) -> pd.DataFrame:
    """
    从 CoinGecko API 获取 BTC 历史价格数据
    """
    print(f"正在获取 BTC 过去 {days} 天的历史数据...")

    url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days={days}"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # 解析价格数据
        prices = data["prices"]
        market_caps = data["market_caps"]
        total_volumes = data["total_volumes"]

        # 创建 DataFrame
        df = pd.DataFrame(prices, columns=["timestamp", "price"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["market_cap"] = [m[1] for m in market_caps]
        df["volume"] = [v[1] for v in total_volumes]

        # 计算日收益率
        df["returns"] = df["price"].pct_change()
        df["volatility"] = df["returns"].rolling(window=7).std() * np.sqrt(365)

        # 计算移动平均线
        df["ma_7"] = df["price"].rolling(window=7).mean()
        df["ma_30"] = df["price"].rolling(window=30).mean()

        print(f"成功获取 {len(df)} 条数据记录")
        return df

    except Exception as e:
        print(f"获取数据失败: {e}")
        return pd.DataFrame()


def calculate_short_token_performance(
    price_data: pd.DataFrame, leverage: float = 2.0, initial_investment: float = 10000.0
) -> pd.DataFrame:
    """
    计算做空代币的表现

    参数:
        price_data: BTC 价格数据
        leverage: 杠杆倍数
        initial_investment: 初始投资金额

    返回:
        包含做空代币表现的 DataFrame
    """
    df = price_data.copy()

    # 计算做空收益（反向追踪）
    df["short_returns"] = -df["returns"] * leverage

    # 计算累计收益
    df["cumulative_short"] = (1 + df["short_returns"]).cumprod()
    df["cumulative_btc"] = (1 + df["returns"]).cumprod()

    # 计算投资组合价值
    df["short_portfolio_value"] = initial_investment * df["cumulative_short"]
    df["btc_portfolio_value"] = initial_investment * df["cumulative_btc"]

    # 计算做空代币 NAV（净值）
    df["short_token_nav"] = 1.0 * df["cumulative_short"]

    # 计算抵押率（简化的 CR 计算）
    # CR = 抵押品价值 / (做空代币流通量 * 价格 * 杠杆)
    df["collateral_ratio"] = (
        BTC_SHORT_TOKEN_PARAMS["initial_collateral_ratio"]
        * (1 + df["returns"].cumsum())
        / (1 + df["short_returns"].cumsum())
    )

    return df


def simulate_liquidation_scenarios(
    price_data: pd.DataFrame,
    leverage: float = 2.0,
    scenarios: List[str] = ["normal", "bull_market", "bear_market", "high_volatility"],
) -> Dict[str, Any]:
    """
    模拟不同市场场景下的爆仓风险
    """
    results = {}

    for scenario in scenarios:
        df = price_data.copy()

        if scenario == "bull_market":
            # 牛市：价格持续上涨，做空代币亏损
            df["simulated_returns"] = df["returns"] * 1.5  # 放大涨幅
            df["simulated_price"] = (
                df["price"].iloc[0] * (1 + df["simulated_returns"]).cumprod()
            )
        elif scenario == "bear_market":
            # 熊市：价格持续下跌，做空代币盈利
            df["simulated_returns"] = df["returns"] * 1.2  # 放大跌幅
            df["simulated_price"] = (
                df["price"].iloc[0] * (1 + df["simulated_returns"]).cumprod()
            )
        elif scenario == "high_volatility":
            # 高波动：增加波动率
            df["simulated_returns"] = df["returns"] * 2.0
            df["simulated_price"] = (
                df["price"].iloc[0] * (1 + df["simulated_returns"]).cumprod()
            )
        else:
            # 正常市场
            df["simulated_returns"] = df["returns"]
            df["simulated_price"] = df["price"]

        # 计算做空代币表现
        df["short_returns"] = -df["simulated_returns"] * leverage
        df["cumulative_short"] = (1 + df["short_returns"]).cumprod()

        # 检测爆仓事件
        liquidation_threshold = 0.1  # 损失超过 90% 视为爆仓
        df["liquidation_risk"] = df["cumulative_short"] < liquidation_threshold

        # 统计爆仓事件
        liquidation_events = df[df["liquidation_risk"]].shape[0]
        max_drawdown = (
            df["cumulative_short"].max() - df["cumulative_short"].min()
        ) / df["cumulative_short"].max()

        results[scenario] = {
            "total_days": len(df),
            "liquidation_events": liquidation_events,
            "liquidation_rate": liquidation_events / len(df) if len(df) > 0 else 0,
            "max_drawdown": max_drawdown,
            "final_return": df["cumulative_short"].iloc[-1] - 1 if len(df) > 0 else 0,
            "avg_daily_return": df["short_returns"].mean(),
            "volatility": df["short_returns"].std() * np.sqrt(365),
        }

    return results


def create_visualization_report(
    price_data: pd.DataFrame,
    performance_data: pd.DataFrame,
    liquidation_results: Dict[str, Any],
    output_dir: str = "./btc_short_analysis",
):
    """
    创建可视化报告
    """
    os.makedirs(output_dir, exist_ok=True)

    # 确保 price_data 有 cumulative_btc 列
    if "cumulative_btc" not in price_data.columns:
        price_data["cumulative_btc"] = (1 + price_data["returns"]).cumprod()

    # 创建大图
    fig = plt.figure(figsize=(20, 24))
    gs = GridSpec(6, 2, figure=fig, hspace=0.3, wspace=0.3)

    # 1. BTC 价格走势
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(
        price_data["date"],
        price_data["price"],
        label="BTC Price",
        color="orange",
        linewidth=2,
    )
    ax1.plot(
        price_data["date"], price_data["ma_7"], label="MA 7", color="blue", alpha=0.7
    )
    ax1.plot(
        price_data["date"], price_data["ma_30"], label="MA 30", color="red", alpha=0.7
    )
    ax1.set_title("BTC 价格走势与移动平均线", fontsize=16, fontweight="bold")
    ax1.set_xlabel("日期")
    ax1.set_ylabel("价格 (USD)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # 2. BTC 日收益率分布
    ax2 = fig.add_subplot(gs[1, 0])
    price_data["returns"].hist(
        bins=50, ax=ax2, color="skyblue", edgecolor="black", alpha=0.7
    )
    ax2.axvline(
        price_data["returns"].mean(),
        color="red",
        linestyle="--",
        label=f"均值: {price_data['returns'].mean():.4f}",
    )
    ax2.axvline(
        price_data["returns"].quantile(0.05),
        color="orange",
        linestyle="--",
        label="5% 分位数",
    )
    ax2.axvline(
        price_data["returns"].quantile(0.95),
        color="green",
        linestyle="--",
        label="95% 分位数",
    )
    ax2.set_title("BTC 日收益率分布", fontsize=14, fontweight="bold")
    ax2.set_xlabel("日收益率")
    ax2.set_ylabel("频次")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 3. 波动率变化
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.plot(
        price_data["date"], price_data["volatility"], color="purple", linewidth=1.5
    )
    ax3.axhline(
        BTC_SHORT_TOKEN_PARAMS["volatility_threshold"],
        color="red",
        linestyle="--",
        label=f"阈值: {BTC_SHORT_TOKEN_PARAMS['volatility_threshold']}",
    )
    ax3.fill_between(
        price_data["date"],
        price_data["volatility"],
        BTC_SHORT_TOKEN_PARAMS["volatility_threshold"],
        where=(
            price_data["volatility"] > BTC_SHORT_TOKEN_PARAMS["volatility_threshold"]
        ),
        alpha=0.3,
        color="red",
    )
    ax3.set_title("BTC 年化波动率 (7日滚动)", fontsize=14, fontweight="bold")
    ax3.set_xlabel("日期")
    ax3.set_ylabel("波动率")
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # 4. 不同杠杆倍数下的做空代币表现
    ax4 = fig.add_subplot(gs[2, :])
    colors = ["blue", "green", "red"]
    leverages = [1.0, 2.0, 3.0]

    for i, lev in enumerate(leverages):
        perf = calculate_short_token_performance(price_data, leverage=lev)
        ax4.plot(
            perf["date"],
            perf["cumulative_short"],
            label=f"{lev}x 杠杆做空",
            color=colors[i],
            linewidth=2,
        )

    ax4.plot(
        price_data["date"],
        price_data["cumulative_btc"],
        label="BTC 现货",
        color="orange",
        linewidth=2,
        linestyle="--",
        alpha=0.7,
    )
    ax4.axhline(1.0, color="black", linestyle=":", alpha=0.5)
    ax4.set_title("不同杠杆倍数下做空代币累计收益对比", fontsize=16, fontweight="bold")
    ax4.set_xlabel("日期")
    ax4.set_ylabel("累计收益倍数")
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # 5. 投资组合价值对比
    ax5 = fig.add_subplot(gs[3, 0])
    perf_2x = calculate_short_token_performance(price_data, leverage=2.0)
    ax5.plot(
        perf_2x["date"],
        perf_2x["short_portfolio_value"],
        label="2x 做空代币",
        color="red",
        linewidth=2,
    )
    ax5.plot(
        perf_2x["date"],
        perf_2x["btc_portfolio_value"],
        label="BTC 现货",
        color="orange",
        linewidth=2,
    )
    ax5.set_title("投资组合价值对比 (初始投资 $10,000)", fontsize=14, fontweight="bold")
    ax5.set_xlabel("日期")
    ax5.set_ylabel("价值 (USD)")
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    ax5.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # 6. 抵押率模拟
    ax6 = fig.add_subplot(gs[3, 1])
    ax6.plot(perf_2x["date"], perf_2x["collateral_ratio"], color="green", linewidth=2)
    ax6.axhline(
        BTC_SHORT_TOKEN_PARAMS["min_collateral_ratio"],
        color="orange",
        linestyle="--",
        label=f"最低要求: {BTC_SHORT_TOKEN_PARAMS['min_collateral_ratio']}",
    )
    ax6.axhline(
        BTC_SHORT_TOKEN_PARAMS["liquidation_ratio"],
        color="red",
        linestyle="--",
        label=f"清算线: {BTC_SHORT_TOKEN_PARAMS['liquidation_ratio']}",
    )
    ax6.fill_between(
        perf_2x["date"],
        perf_2x["collateral_ratio"],
        BTC_SHORT_TOKEN_PARAMS["min_collateral_ratio"],
        where=(
            perf_2x["collateral_ratio"] < BTC_SHORT_TOKEN_PARAMS["min_collateral_ratio"]
        ),
        alpha=0.3,
        color="red",
    )
    ax6.set_title("抵押率 (CR) 模拟 - 2x 杠杆", fontsize=14, fontweight="bold")
    ax6.set_xlabel("日期")
    ax6.set_ylabel("抵押率")
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    ax6.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # 7. 不同市场场景下的表现对比
    ax7 = fig.add_subplot(gs[4, :2])
    scenarios = list(liquidation_results.keys())
    metrics = ["final_return", "max_drawdown", "liquidation_rate"]
    x = np.arange(len(scenarios))
    width = 0.25

    for i, metric in enumerate(metrics):
        values = [liquidation_results[s][metric] for s in scenarios]
        ax7.bar(x + i * width, values, width, label=metric)

    ax7.set_title("不同市场场景下的风险指标对比", fontsize=16, fontweight="bold")
    ax7.set_xlabel("市场场景")
    ax7.set_ylabel("数值")
    ax7.set_xticks(x + width)
    ax7.set_xticklabels(scenarios, rotation=45, ha="right")
    ax7.legend()
    ax7.grid(True, alpha=0.3, axis="y")

    # 8. 风险-收益散点图
    ax8 = fig.add_subplot(gs[5, 0])
    for scenario, data in liquidation_results.items():
        returns = data["avg_daily_return"] * 365  # 年化收益
        volatility = data["volatility"]
        ax8.scatter(volatility, returns, s=200, alpha=0.6, label=scenario)
        ax8.annotate(
            scenario,
            (volatility, returns),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
        )

    ax8.axhline(0, color="black", linestyle=":", alpha=0.5)
    ax8.axvline(0, color="black", linestyle=":", alpha=0.5)
    ax8.set_title("风险-收益分布 (年化)", fontsize=14, fontweight="bold")
    ax8.set_xlabel("波动率 (年化)")
    ax8.set_ylabel("收益率 (年化)")
    ax8.legend()
    ax8.grid(True, alpha=0.3)

    # 9. 参数配置表
    ax9 = fig.add_subplot(gs[5, 1])
    ax9.axis("off")

    param_text = "BTC 做空代币设计参数\n" + "=" * 50 + "\n\n"
    for key, value in BTC_SHORT_TOKEN_PARAMS.items():
        if isinstance(value, list):
            param_text += f"{key}: {value}\n"
        else:
            param_text += f"{key}: {value}\n"

    ax9.text(
        0.1,
        0.9,
        param_text,
        transform=ax9.transAxes,
        fontsize=10,
        verticalalignment="top",
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    plt.suptitle(
        "BTC 做空代币设计与风险分析报告", fontsize=20, fontweight="bold", y=0.995
    )

    # 保存图表
    output_path = os.path.join(output_dir, "btc_short_token_analysis.png")
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"可视化报告已保存: {output_path}")

    plt.close()

    return output_path


def generate_summary_report(
    price_data: pd.DataFrame,
    performance_data: pd.DataFrame,
    liquidation_results: Dict[str, Any],
    output_dir: str = "./btc_short_analysis",
) -> str:
    """
    生成文字总结报告
    """
    os.makedirs(output_dir, exist_ok=True)

    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("BTC 做空代币设计与风险分析报告")
    report_lines.append("=" * 80)
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(
        f"数据区间: {price_data['date'].min()} 至 {price_data['date'].max()}"
    )
    report_lines.append(f"数据天数: {len(price_data)}")
    report_lines.append("")

    # BTC 市场统计
    report_lines.append("-" * 80)
    report_lines.append("BTC 市场统计")
    report_lines.append("-" * 80)
    report_lines.append(f"平均价格: ${price_data['price'].mean():,.2f}")
    report_lines.append(f"价格标准差: ${price_data['price'].std():,.2f}")
    report_lines.append(f"最高价格: ${price_data['price'].max():,.2f}")
    report_lines.append(f"最低价格: ${price_data['price'].min():,.2f}")
    report_lines.append(
        f"平均日收益率: {price_data['returns'].mean():.4f} ({price_data['returns'].mean() * 100:.2f}%)"
    )
    report_lines.append(f"日收益率标准差: {price_data['returns'].std():.4f}")
    report_lines.append(f"年化波动率: {price_data['returns'].std() * np.sqrt(365):.4f}")
    report_lines.append("")

    # 做空代币设计参数
    report_lines.append("-" * 80)
    report_lines.append("做空代币设计参数")
    report_lines.append("-" * 80)
    for key, value in BTC_SHORT_TOKEN_PARAMS.items():
        report_lines.append(f"{key}: {value}")
    report_lines.append("")

    # 不同杠杆表现
    report_lines.append("-" * 80)
    report_lines.append("不同杠杆倍数表现对比 (基于历史数据回测)")
    report_lines.append("-" * 80)

    for leverage in [1.0, 2.0, 3.0]:
        perf = calculate_short_token_performance(price_data, leverage=leverage)
        final_return = perf["cumulative_short"].iloc[-1] - 1
        max_nav = perf["cumulative_short"].max()
        min_nav = perf["cumulative_short"].min()
        max_drawdown = (max_nav - min_nav) / max_nav

        report_lines.append(f"\n{leverage}x 杠杆:")
        report_lines.append(f"  累计收益率: {final_return * 100:+.2f}%")
        report_lines.append(f"  最大回撤: {max_drawdown * 100:.2f}%")
        report_lines.append(f"  NAV 最高: {max_nav:.4f}")
        report_lines.append(f"  NAV 最低: {min_nav:.4f}")

    report_lines.append("")

    # 爆仓风险分析
    report_lines.append("-" * 80)
    report_lines.append("爆仓风险模拟 (不同市场场景)")
    report_lines.append("-" * 80)

    for scenario, data in liquidation_results.items():
        report_lines.append(f"\n场景: {scenario}")
        report_lines.append(f"  爆仓事件数: {data['liquidation_events']}")
        report_lines.append(f"  爆仓率: {data['liquidation_rate'] * 100:.2f}%")
        report_lines.append(f"  最大回撤: {data['max_drawdown'] * 100:.2f}%")
        report_lines.append(f"  最终收益率: {data['final_return'] * 100:+.2f}%")
        report_lines.append(f"  平均日收益: {data['avg_daily_return'] * 100:.4f}%")
        report_lines.append(f"  年化波动率: {data['volatility']:.4f}")

    report_lines.append("")

    # 风险提示
    report_lines.append("-" * 80)
    report_lines.append("重要风险提示")
    report_lines.append("-" * 80)
    report_lines.append("1. 做空代币在牛市中会快速亏损，请谨慎使用")
    report_lines.append("2. 高杠杆倍数(3x以上)在市场波动大时极易爆仓")
    report_lines.append("3. 本模拟基于历史数据，未来表现可能不同")
    report_lines.append("4. 实际部署需考虑预言机延迟、Gas费、滑点等因素")
    report_lines.append("5. 建议设置止损和熔断机制控制风险")
    report_lines.append("")

    # 设计建议
    report_lines.append("-" * 80)
    report_lines.append("设计建议")
    report_lines.append("-" * 80)
    report_lines.append("1. 推荐使用 1x-2x 杠杆，平衡收益与风险")
    report_lines.append("2. 设置动态再平衡机制，当杠杆超过 4.5x 时自动调整")
    report_lines.append("3. 初始抵押率建议 150%，最低不低于 120%")
    report_lines.append("4. 引入熔断机制，单日波动超过 20% 时暂停交易")
    report_lines.append("5. 定期进行压力测试，模拟极端市场行情")
    report_lines.append("")

    report_lines.append("=" * 80)

    # 保存报告
    report_text = "\n".join(report_lines)
    report_path = os.path.join(output_dir, "btc_short_token_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"文字报告已保存: {report_path}")
    return report_text


def main():
    parser = argparse.ArgumentParser(description="BTC 做空代币设计与模拟可视化")
    parser.add_argument(
        "--days", type=int, default=365, help="获取历史数据天数 (默认: 365)"
    )
    parser.add_argument("--output-dir", default="./btc_short_analysis", help="输出目录")
    parser.add_argument(
        "--leverage", type=float, default=2.0, help="默认杠杆倍数 (默认: 2.0)"
    )
    args = parser.parse_args()

    print("=" * 80)
    print("BTC 做空代币设计与模拟程序")
    print("=" * 80)
    print()

    # 1. 获取 BTC 历史数据
    price_data = fetch_btc_historical_data(days=args.days)
    if price_data.empty:
        print("错误: 无法获取 BTC 数据，程序退出")
        return 1

    # 2. 计算做空代币表现
    print("\n正在计算做空代币表现...")
    performance_data = calculate_short_token_performance(
        price_data, leverage=args.leverage
    )

    # 3. 模拟不同场景下的爆仓风险
    print("正在模拟不同市场场景...")
    liquidation_results = simulate_liquidation_scenarios(
        price_data, leverage=args.leverage
    )

    # 4. 生成可视化报告
    print("\n正在生成可视化报告...")
    viz_path = create_visualization_report(
        price_data, performance_data, liquidation_results, args.output_dir
    )

    # 5. 生成文字报告
    report_text = generate_summary_report(
        price_data, performance_data, liquidation_results, args.output_dir
    )

    # 6. 输出总结
    print("\n" + "=" * 80)
    print("分析完成!")
    print("=" * 80)
    print(f"\n输出文件:")
    print(f"  可视化报告: {viz_path}")
    print(f"  文字报告: {os.path.join(args.output_dir, 'btc_short_token_report.txt')}")
    print(f"\n关键发现:")

    # 输出关键指标
    for leverage in [1.0, 2.0, 3.0]:
        perf = calculate_short_token_performance(price_data, leverage=leverage)
        final_return = perf["cumulative_short"].iloc[-1] - 1
        print(f"  {leverage}x 杠杆累计收益: {final_return * 100:+.2f}%")

    print()

    return 0


if __name__ == "__main__":
    exit(main())
