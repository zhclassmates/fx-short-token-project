def calculate_premium(principal, leverage):
    """
    计算保费额 (USDT)。
    公式: min(0.15, 0.05 + (leverage - 20) * 0.001 + (principal / 500) * 0.02) * principal
    """
    base_ratio = 0.05 + (leverage - 20) * 0.001 + (principal / 500) * 0.02
    premium_ratio = min(0.15, base_ratio)
    return premium_ratio * principal

def calculate_payout_ratio(principal, leverage):
    """
    计算赔付比例 (%，返回小数)。
    公式: min(0.5, max(0.1, 0.25 + (leverage - 50) * 0.005 - (principal / 500) * 0.1))
    """
    base_ratio = 0.25 + (leverage - 50) * 0.005 - (principal / 500) * 0.1
    return min(0.5, max(0.1, base_ratio))

def calculate_payout(principal, leverage):
    """
    计算赔付额 (USDT)。
    """
    ratio = calculate_payout_ratio(principal, leverage)
    return ratio * principal

# 示例使用（测试）
if __name__ == "__main__":
    # 小本低杠杆
    print(f"本金100, 杠杆20: 保费 = {calculate_premium(100, 20):.2f} USDT")
    print(f"赔付比例 = {calculate_payout_ratio(100, 20) * 100:.1f}%, 赔付额 = {calculate_payout(100, 20):.2f} USDT")
    
    # 大本高杠杆
    print(f"本金500, 杠杆100: 保费 = {calculate_premium(500, 100):.2f} USDT")
    print(f"赔付比例 = {calculate_payout_ratio(500, 100) * 100:.1f}%, 赔付额 = {calculate_payout(500, 100):.2f} USDT")
    
    # 额外测试用例
    print(f"本金100, 杠杆100: 保费 = {calculate_premium(100, 100):.2f} USDT")
    print(f"赔付比例 = {calculate_payout_ratio(100, 100) * 100:.1f}%, 赔付额 = {calculate_payout(100, 100):.2f} USDT")