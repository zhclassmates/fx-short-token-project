#!/usr/bin/env python3
"""
BTC Short Token 全参数回测与边界分析
下载真实BTC历史数据，扫描最优参数组合
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import os
from itertools import product
import warnings
warnings.filterwarnings('ignore')

# 尝试下载真实BTC数据
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    print("Warning: yfinance not installed. Using synthetic data.")

def download_btc_data(start='2020-01-01', end=None):
    """下载BTC历史数据"""
    if not HAS_YFINANCE:
        return generate_synthetic_btc_data()
    
    if end is None:
        end = datetime.now().strftime('%Y-%m-%d')
    
    print(f"Downloading BTC data from {start} to {end}...")
    btc = yf.download('BTC-USD', start=start, end=end, progress=False)
    
    if len(btc) == 0:
        print("Failed to download data, using synthetic data...")
        return generate_synthetic_btc_data()
    
    # 计算日收益率
    btc['returns'] = btc['Close'].pct_change()
    btc = btc.dropna()
    
    print(f"Downloaded {len(btc)} days of BTC data")
    print(f"Price range: ${btc['Close'].min():.2f} - ${btc['Close'].max():.2f}")
    print(f"Max daily drop: {btc['returns'].min()*100:.2f}%")
    print(f"Max daily rise: {btc['returns'].max()*100:.2f}%")
    
    return btc

def generate_synthetic_btc_data(days=1095, seed=42):
    """生成合成BTC数据（模拟2020-2023年 volatility）"""
    np.random.seed(seed)
    
    # 模拟BTC特征：高波动，偶尔的大跌大涨
    dates = pd.date_range(start='2020-01-01', periods=days, freq='D')
    
    # 生成收益率（包含一些极端值）
    returns = np.random.normal(0.001, 0.035, days)  # 基础波动
    
    # 添加一些极端行情
    crash_days = np.random.choice(days, size=5, replace=False)
    for day in crash_days:
        returns[day] = -np.random.uniform(0.15, 0.30)  # -15% 到 -30%
    
    pump_days = np.random.choice(days, size=5, replace=False)
    for day in pump_days:
        returns[day] = np.random.uniform(0.10, 0.25)  # +10% 到 +25%
    
    # 生成价格
    initial_price = 10000
    prices = initial_price * np.cumprod(1 + returns)
    
    btc = pd.DataFrame({
        'Close': prices,
        'returns': returns
    }, index=dates)
    
    print(f"Generated {len(btc)} days of synthetic BTC data")
    print(f"Max daily drop: {btc['returns'].min()*100:.2f}%")
    print(f"Max daily rise: {btc['returns'].max()*100:.2f}%")
    
    return btc

class ShortTokenBacktest:
    """
    BTC做空代币回测引擎
    """
    def __init__(self, 
                 beta_f=0.1,           # fBTC波动比例
                 leverage_target=2.0,   # 目标杠杆
                 min_nav_s=0.01,        # sBTC最低净值
                 max_leverage=5.0,      # 最大杠杆
                 insurance_ratio=0.02,  # 保险池比例 (2%)
                 rebalance_threshold=0.05,  # 再平衡阈值
                 collateral_ratio_trigger=1.05  # 抵押率触发线
                ):
        self.beta_f = beta_f
        self.beta_s = 1 - beta_f
        self.leverage_target = leverage_target
        self.min_nav_s = min_nav_s
        self.max_leverage = max_leverage
        self.insurance_ratio = insurance_ratio
        self.rebalance_threshold = rebalance_threshold
        self.collateral_ratio_trigger = collateral_ratio_trigger
        
        # 跟踪变量
        self.reset()
    
    def reset(self):
        """重置状态"""
        self.nav_f = 1.0
        self.nav_s = 1.0
        self.leverage = self.leverage_target
        self.insurance_pool = 0.0
        self.collateral = 1.0
        self.liquidation_count = 0
        self.rebalance_count = 0
        self.nav_f_history = []
        self.nav_s_history = []
        self.leverage_history = []
        self.insurance_history = []
        self.collateral_ratio_history = []
    
    def simulate_day(self, btc_return):
        """
        模拟一天的运行
        
        参数:
            btc_return: BTC日收益率 (例如 -0.1 表示跌10%)
        
        返回:
            is_liquidated: 是否触发清算
        """
        # 计算sBTC NAV变化
        # V_s_t = V_s_{t-1} * max(MIN_NAV, 1 - L * r_t)
        change_factor = 1 - self.leverage * btc_return
        
        # 检查是否触及下限
        if change_factor <= self.min_nav_s:
            change_factor = self.min_nav_s
            # 触发清算
            self.liquidation_count += 1
            return True
        
        new_nav_s = self.nav_s * change_factor
        
        # 计算fBTC NAV (由恒等式)
        # 简化为: fBTC 吸收 beta_f 比例的波动
        new_nav_f = self.nav_f * (1 + self.beta_f * btc_return)
        
        # 计算当前杠杆
        if new_nav_s > 0:
            # 杠杆 = 1 / (1 - beta_s_actual)
            beta_s_actual = self.beta_s * (1 + btc_return * self.leverage)
            if beta_s_actual >= 0.99:
                new_leverage = self.max_leverage
            else:
                new_leverage = 1 / (1 - beta_s_actual)
        else:
            new_leverage = self.max_leverage
        
        # 检查是否需要再平衡
        if new_leverage > self.max_leverage:
            self.rebalance_count += 1
            # 再平衡: 降低杠杆
            excess_leverage = new_leverage - self.leverage_target
            rebalance_cost = excess_leverage * 0.01  # 假设1%成本
            self.insurance_pool -= rebalance_cost
            new_leverage = self.leverage_target
        
        # 计算抵押率
        total_value = self.collateral
        f_value = self.beta_f * total_value * new_nav_f
        s_value = self.beta_s * total_value * new_nav_s
        total_liability = f_value + s_value
        
        if total_liability > 0:
            collateral_ratio = total_value / total_liability
        else:
            collateral_ratio = float('inf')
        
        # 检查抵押率
        if collateral_ratio < self.collateral_ratio_trigger:
            # 动用保险池
            shortfall = (self.collateral_ratio_trigger - collateral_ratio) * total_liability
            self.insurance_pool -= shortfall
            
            if self.insurance_pool < 0:
                # 保险池耗尽，触发清算
                self.liquidation_count += 1
                return True
        
        # 更新状态
        self.nav_f = new_nav_f
        self.nav_s = new_nav_s
        self.leverage = min(new_leverage, self.max_leverage)
        
        # 记录历史
        self.nav_f_history.append(self.nav_f)
        self.nav_s_history.append(self.nav_s)
        self.leverage_history.append(self.leverage)
        self.insurance_history.append(self.insurance_pool)
        self.collateral_ratio_history.append(collateral_ratio)
        
        return False
    
    def run_backtest(self, btc_returns):
        """运行完整回测"""
        self.reset()
        
        # 初始保险池资金
        self.insurance_pool = self.insurance_ratio
        
        for i, ret in enumerate(btc_returns):
            is_liquidated = self.simulate_day(ret)
            if is_liquidated:
                break
        
        # 计算统计指标
        results = {
            'final_nav_f': self.nav_f,
            'final_nav_s': self.nav_s,
            'final_leverage': self.leverage,
            'liquidation_count': self.liquidation_count,
            'rebalance_count': self.rebalance_count,
            'final_insurance': self.insurance_pool,
            'days_survived': len(self.nav_f_history),
            'nav_s_max': max(self.nav_s_history) if self.nav_s_history else 0,
            'nav_s_min': min(self.nav_s_history) if self.nav_s_history else 0,
            'nav_s_drawdown': (max(self.nav_s_history) - min(self.nav_s_history)) / max(self.nav_s_history) if self.nav_s_history and max(self.nav_s_history) > 0 else 0,
            'avg_leverage': np.mean(self.leverage_history) if self.leverage_history else 0,
            'max_leverage_reached': max(self.leverage_history) if self.leverage_history else 0,
        }
        
        return results, self.nav_f_history, self.nav_s_history

def parameter_scan(btc_data, output_dir='./output'):
    """
    参数扫描：寻找最优参数组合
    """
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 80)
    print("BTC Short Token Parameter Scan")
    print("=" * 80)
    
    btc_returns = btc_data['returns'].values
    
    # 定义参数范围
    param_grid = {
        'beta_f': [0.05, 0.08, 0.10, 0.12, 0.15],
        'leverage_target': [1.5, 2.0, 2.5, 3.0, 3.5],
        'min_nav_s': [0.005, 0.01, 0.02, 0.05],
        'max_leverage': [4.0, 5.0, 6.0, 7.0],
        'insurance_ratio': [0.01, 0.02, 0.03, 0.05],
    }
    
    # 生成所有参数组合（采样，避免过多组合）
    param_combinations = []
    for beta_f in param_grid['beta_f']:
        for leverage in param_grid['leverage_target']:
            for min_nav in [0.01, 0.02]:  # 限制范围
                for max_lev in [5.0, 6.0]:
                    for insurance in [0.02, 0.03]:
                        param_combinations.append({
                            'beta_f': beta_f,
                            'leverage_target': leverage,
                            'min_nav_s': min_nav,
                            'max_leverage': max_lev,
                            'insurance_ratio': insurance
                        })
    
    print(f"Testing {len(param_combinations)} parameter combinations...")
    
    results = []
    for i, params in enumerate(param_combinations):
        if i % 50 == 0:
            print(f"  Progress: {i}/{len(param_combinations)}")
        
        backtest = ShortTokenBacktest(**params)
        result, nav_f_hist, nav_s_hist = backtest.run_backtest(btc_returns)
        
        # 评分系统
        score = 0
        
        # 1. 生存天数（越高越好）
        score += result['days_survived'] * 10
        
        # 2. 未触发清算（重要）
        if result['liquidation_count'] == 0:
            score += 1000
        
        # 3. 再平衡次数适中（避免过于频繁）
        if 0 < result['rebalance_count'] <= 50:
            score += 100
        
        # 4. 最终保险池为正
        if result['final_insurance'] > 0:
            score += 200
        
        # 5. sBTC有合理的波动范围
        if 0.5 <= result['nav_s_max'] <= 5.0:
            score += 50
        
        results.append({
            'params': params,
            'result': result,
            'score': score
        })
    
    # 按评分排序
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results

def analyze_boundaries(btc_data, best_params, output_dir='./output'):
    """
    分析边界条件：找到系统的极限
    """
    print("\n" + "=" * 80)
    print("Boundary Condition Analysis")
    print("=" * 80)
    
    btc_returns = btc_data['returns'].values
    
    boundaries = {
        'max_daily_drop': {},
        'consecutive_drops': {},
        'sustained_bull': {},
        'insurance_requirement': {}
    }
    
    # 1. 最大单日跌幅承受测试
    print("\n1. Testing max daily drop tolerance...")
    max_drop_tests = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    
    for drop in max_drop_tests:
        # 创建极端场景：正常行情 + 一次大跌
        test_returns = btc_returns.copy()
        test_returns[100] = -drop  # 在第100天模拟大跌
        
        backtest = ShortTokenBacktest(**best_params)
        result, _, _ = backtest.run_backtest(test_returns)
        
        survives = result['liquidation_count'] == 0
        boundaries['max_daily_drop'][f"{-drop*100:.0f}%"] = {
            'survives': survives,
            'final_nav_s': result['final_nav_s'],
            'rebalance_count': result['rebalance_count']
        }
        
        print(f"  {-drop*100:.0f}% drop: {'✓ Survives' if survives else '✗ Liquidated'}")
    
    # 2. 连续下跌测试
    print("\n2. Testing consecutive drop scenarios...")
    consecutive_tests = [
        ([-0.05, -0.05, -0.05], "3x -5%"),
        ([-0.10, -0.10], "2x -10%"),
        ([-0.15, -0.10, -0.05], "-15%, -10%, -5%"),
        ([-0.20, -0.15], "-20%, -15%"),
    ]
    
    for drops, desc in consecutive_tests:
        test_returns = btc_returns.copy()
        for i, drop in enumerate(drops):
            test_returns[100 + i] = drop
        
        backtest = ShortTokenBacktest(**best_params)
        result, _, _ = backtest.run_backtest(test_returns)
        
        survives = result['liquidation_count'] == 0
        boundaries['consecutive_drops'][desc] = {
            'survives': survives,
            'final_nav_s': result['final_nav_s']
        }
        
        print(f"  {desc}: {'✓ Survives' if survives else '✗ Liquidated'}")
    
    # 3. 保险池需求测试
    print("\n3. Testing insurance pool requirements...")
    insurance_tests = [0.005, 0.01, 0.015, 0.02, 0.03, 0.05]
    
    for insurance in insurance_tests:
        params = best_params.copy()
        params['insurance_ratio'] = insurance
        
        backtest = ShortTokenBacktest(**params)
        result, _, _ = backtest.run_backtest(btc_returns)
        
        survives = result['liquidation_count'] == 0
        boundaries['insurance_requirement'][f"{insurance*100:.1f}%"] = {
            'survives': survives,
            'final_insurance': result['final_insurance']
        }
        
        status = '✓ Sufficient' if survives else '✗ Insufficient'
        print(f"  {insurance*100:.1f}% insurance: {status}")
    
    return boundaries

def generate_report(results, boundaries, btc_data, output_dir='./output'):
    """生成完整报告"""
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取最优参数
    best = results[0]
    best_params = best['params']
    best_result = best['result']
    
    report = []
    report.append("=" * 80)
    report.append("BTC SHORT TOKEN BACKTEST REPORT")
    report.append("=" * 80)
    report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Data Period: {btc_data.index[0]} to {btc_data.index[-1]}")
    report.append(f"Total Days: {len(btc_data)}")
    
    # 数据摘要
    report.append("\n" + "-" * 80)
    report.append("BTC DATA SUMMARY")
    report.append("-" * 80)
    report.append(f"Start Price: ${btc_data['Close'].iloc[0]:,.2f}")
    report.append(f"End Price: ${btc_data['Close'].iloc[-1]:,.2f}")
    report.append(f"Max Price: ${btc_data['Close'].max():,.2f}")
    report.append(f"Min Price: ${btc_data['Close'].min():,.2f}")
    report.append(f"Max Daily Drop: {btc_data['returns'].min()*100:.2f}%")
    report.append(f"Max Daily Rise: {btc_data['returns'].max()*100:.2f}%")
    report.append(f"Volatility (annualized): {btc_data['returns'].std() * np.sqrt(365) * 100:.2f}%")
    
    # 最优参数
    report.append("\n" + "-" * 80)
    report.append("OPTIMAL PARAMETERS (Top 10)")
    report.append("-" * 80)
    
    for i, r in enumerate(results[:10], 1):
        p = r['params']
        res = r['result']
        report.append(f"\n{i}. Score: {r['score']:.0f}")
        report.append(f"   beta_f: {p['beta_f']:.2f} | leverage: {p['leverage_target']:.1f}x | "
                     f"min_nav: {p['min_nav_s']:.3f} | max_lev: {p['max_leverage']:.1f}x | "
                     f"insurance: {p['insurance_ratio']*100:.1f}%")
        report.append(f   "   Result: NAV_s={res['final_nav_s']:.3f}, "
                     f"Liquidations={res['liquidation_count']}, "
                     f"Rebalances={res['rebalance_count']}, "
                     f"Survived={res['days_survived']}/{len(btc_data)} days")
    
    # 最优参数详情
    report.append("\n" + "-" * 80)
    report.append("BEST PARAMETER DETAILS")
    report.append("-" * 80)
    report.append(f"beta_f (fBTC波动比例): {best_params['beta_f']:.2f}")
    report.append(f"leverage_target (目标杠杆): {best_params['leverage_target']:.1f}x")
    report.append(f"min_nav_s (sBTC最低净值): {best_params['min_nav_s']:.3f}")
    report.append(f"max_leverage (最大杠杆): {best_params['max_leverage']:.1f}x")
    report.append(f"insurance_ratio (保险池比例): {best_params['insurance_ratio']*100:.1f}%")
    
    report.append(f"\nPerformance:")
    report.append(f"  Final fBTC NAV: {best_result['final_nav_f']:.4f}")
    report.append(f"  Final sBTC NAV: {best_result['final_nav_s']:.4f}")
    report.append(f"  Max sBTC NAV: {best_result['nav_s_max']:.4f}")
    report.append(f"  Min sBTC NAV: {best_result['nav_s_min']:.4f}")
    report.append(f"  Max Drawdown: {best_result['nav_s_drawdown']*100:.2f}%")
    report.append(f"  Liquidations: {best_result['liquidation_count']}")
    report.append(f"  Rebalances: {best_result['rebalance_count']}")
    report.append(f"  Days Survived: {best_result['days_survived']}/{len(btc_data)}")
    report.append(f"  Final Insurance: {best_result['final_insurance']:.4f}")
    
    # 边界条件
    report.append("\n" + "-" * 80)
    report.append("BOUNDARY CONDITIONS")
    report.append("-" * 80)
    
    report.append("\n1. Maximum Daily Drop Tolerance:")
    for drop, data in boundaries['max_daily_drop'].items():
        status = "✓ SAFE" if data['survives'] else "✗ FAIL"
        report.append(f"   {drop:>6}: {status} | Final NAV_s: {data['final_nav_s']:.3f}")
    
    report.append("\n2. Consecutive Drop Scenarios:")
    for desc, data in boundaries['consecutive_drops'].items():
        status = "✓ SAFE" if data['survives'] else "✗ FAIL"
        report.append(f"   {desc:>20}: {status} | Final NAV_s: {data['final_nav_s']:.3f}")
    
    report.append("\n3. Insurance Pool Requirements:")
    for ins, data in boundaries['insurance_requirement'].items():
        status = "✓ Sufficient" if data['survives'] else "✗ Insufficient"
        report.append(f"   {ins:>6}: {status} | Remaining: {data['final_insurance']:.4f}")
    
    # 建议
    report.append("\n" + "-" * 80)
    report.append("RECOMMENDATIONS")
    report.append("-" * 80)
    
    # 找出关键边界
    max_safe_drop = None
    for drop, data in boundaries['max_daily_drop'].items():
        if data['survives']:
            max_safe_drop = drop
    
    min_insurance = None
    for ins, data in boundaries['insurance_requirement'].items():
        if data['survives'] and min_insurance is None:
            min_insurance = ins
    
    report.append(f"\n1. Parameter Settings:")
    report.append(f"   - Use beta_f = {best_params['beta_f']:.2f} for optimal stability")
    report.append(f"   - Target leverage = {best_params['leverage_target']:.1f}x")
    report.append(f"   - Maximum leverage cap = {best_params['max_leverage']:.1f}x")
    report.append(f"   - sBTC minimum NAV = {best_params['min_nav_s']:.3f}")
    
    report.append(f"\n2. Risk Management:")
    if max_safe_drop:
        report.append(f"   - System can survive up to {max_safe_drop} single-day drop")
    report.append(f"   - Requires minimum {min_insurance} insurance pool")
    report.append(f"   - Expected rebalances: ~{best_result['rebalance_count']} per {len(btc_data)} days")
    
    report.append(f"\n3. Operational Limits:")
    report.append(f"   - Circuit breaker: Trigger at >{best_params['max_leverage']:.0f}x leverage")
    report.append(f"   - Rebalance trigger: When leverage exceeds {best_params['max_leverage']*0.8:.1f}x")
    
    report_text = "\n".join(report)
    
    # 保存报告
    report_file = os.path.join(output_dir, 'backtest_report.txt')
    with open(report_file, 'w') as f:
        f.write(report_text)
    
    print(report_text)
    print(f"\n\nReport saved to: {report_file}")
    
    return report_text

def plot_results(results, btc_data, output_dir='./output'):
    """生成可视化图表"""
    os.makedirs(output_dir, exist_ok=True)
    
    best = results[0]
    best_params = best['params']
    
    # 重新运行最优参数获取完整历史
    backtest = ShortTokenBacktest(**best_params)
    result, nav_f_hist, nav_s_hist = backtest.run_backtest(btc_data['returns'].values)
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    
    # 1. BTC 价格
    ax1 = axes[0, 0]
    ax1.plot(btc_data.index, btc_data['Close'], color='orange', linewidth=1)
    ax1.set_title('BTC Price History', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Price (USD)')
    ax1.grid(True, alpha=0.3)
    
    # 2. NAV 对比
    ax2 = axes[0, 1]
    days = range(len(nav_f_hist))
    ax2.plot(days, nav_f_hist, 'b-', label='fBTC', linewidth=1.5)
    ax2.plot(days, nav_s_hist, 'r-', label='sBTC', linewidth=1.5)
    ax2.axhline(y=1, color='gray', linestyle='--', alpha=0.5)
    ax2.set_title('Token NAV Evolution', fontsize=12, fontweight='bold')
    ax2.set_ylabel('NAV (USD)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. 杠杆变化
    ax3 = axes[0, 2]
    ax3.plot(days, backtest.leverage_history, 'g-', linewidth=1)
    ax3.axhline(y=best_params['max_leverage'], color='red', linestyle='--', 
                alpha=0.5, label=f"Max ({best_params['max_leverage']:.0f}x)")
    ax3.set_title('Dynamic Leverage', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Leverage (x)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. 保险池
    ax4 = axes[1, 0]
    ax4.plot(days, backtest.insurance_history, 'purple', linewidth=1)
    ax4.axhline(y=0, color='red', linestyle='--', alpha=0.5)
    ax4.set_title('Insurance Pool', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Insurance (USD)')
    ax4.grid(True, alpha=0.3)
    
    # 5. 抵押率
    ax5 = axes[1, 1]
    ax5.plot(days, backtest.collateral_ratio_history, 'brown', linewidth=1)
    ax5.axhline(y=best_params.get('collateral_ratio_trigger', 1.05), 
                color='red', linestyle='--', alpha=0.5, label='Trigger')
    ax5.set_title('Collateral Ratio', fontsize=12, fontweight='bold')
    ax5.set_ylabel('Ratio')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    
    # 6. 参数敏感性热力图
    ax6 = axes[1, 2]
    
    # 提取 beta_f vs leverage 的得分
    beta_vals = sorted(set([r['params']['beta_f'] for r in results]))
    lev_vals = sorted(set([r['params']['leverage_target'] for r in results]))
    
    score_matrix = np.zeros((len(beta_vals), len(lev_vals)))
    for r in results:
        i = beta_vals.index(r['params']['beta_f'])
        j = lev_vals.index(r['params']['leverage_target'])
        score_matrix[i, j] = max(score_matrix[i, j], r['score'])
    
    im = ax6.imshow(score_matrix, cmap='RdYlGn', aspect='auto')
    ax6.set_xticks(range(len(lev_vals)))
    ax6.set_yticks(range(len(beta_vals)))
    ax6.set_xticklabels([f"{v:.1f}x" for v in lev_vals])
    ax6.set_yticklabels([f"{v:.2f}" for v in beta_vals])
    ax6.set_xlabel('Target Leverage')
    ax6.set_ylabel('beta_f')
    ax6.set_title('Parameter Score Heatmap', fontsize=12, fontweight='bold')
    plt.colorbar(im, ax=ax6)
    
    plt.suptitle('BTC Short Token Backtest Results', fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    plot_file = os.path.join(output_dir, 'backtest_results.png')
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: {plot_file}")
    
    plt.show()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='BTC Short Token Backtest')
    parser.add_argument('--start', default='2020-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', default='./output/backtest', help='Output directory')
    parser.add_argument('--use-real', action='store_true', help='Use real BTC data from yfinance')
    
    args = parser.parse_args()
    
    # 下载/生成数据
    if args.use_real and HAS_YFINANCE:
        btc_data = download_btc_data(args.start, args.end)
    else:
        print("Using synthetic BTC data...")
        btc_data = generate_synthetic_btc_data(days=1095)
    
    # 运行参数扫描
    print("\nStarting parameter scan...")
    results = parameter_scan(btc_data, args.output)
    
    # 分析边界条件
    best_params = results[0]['params']
    boundaries = analyze_boundaries(btc_data, best_params, args.output)
    
    # 生成报告
    report = generate_report(results, boundaries, btc_data, args.output)
    
    # 生成图表
    plot_results(results, btc_data, args.output)
    
    # 保存详细结果
    results_file = os.path.join(args.output, 'backtest_results.json')
    with open(results_file, 'w') as f:
        json.dump({
            'top_10_results': [
                {
                    'rank': i+1,
                    'score': r['score'],
                    'params': r['params'],
                    'result': r['result']
                }
                for i, r in enumerate(results[:10])
            ],
            'boundaries': boundaries,
            'best_params': best_params
        }, f, indent=2)
    
    print(f"\n✅ Backtest complete! All results saved to: {args.output}/")
