import hmac 
import hashlib 
import time 
import requests 
import json 
import os
from urllib.parse import urlencode 
from datetime import datetime, timedelta 

# Binance USDC-M Futures API 配置（CRV/USDC 合约） 
BASE_URL = 'https://fapi.binance.com'  # USDC-M 永续合约端点 
API_KEY = os.getenv('BINANCE_API_KEY', '')  # 从环境变量读取 
API_SECRET = os.getenv('BINANCE_API_SECRET', '')  # 从环境变量读取 
SYMBOL = 'CRVUSDC'  # CRV/USDC 交易对 
MIN_VALUE_USD = 100  # 最小开仓价值阈值 

# 时间范围：过去24小时（可调整） 
END_TIME = int(time.time() * 1000)  # 当前时间 (ms) 
START_TIME = END_TIME - (24 * 60 * 60 * 1000)  # 24小时前 (ms) 
# 或指定您的开仓时间：START_TIME = 1728275566000  # 2025-10-07 12:32:46 

def create_signature(query_string): 
    """生成 Binance API 签名 (HMAC SHA256)"""
    return hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest() 

def fetch_user_trades(): 
    """查询 CRV/USDC 交易历史，检测爆仓"""
    if not API_KEY or not API_SECRET:
        print("错误: 缺少 BINANCE_API_KEY / BINANCE_API_SECRET 环境变量")
        return False, []
    endpoint = '/fapi/v1/userTrades'  # 官方端点：用户交易列表 
    params = { 
        'symbol': SYMBOL, 
        'startTime': START_TIME, 
        'endTime': END_TIME, 
        'limit': 1000  # 最多1000条 
    } 
    query_string = urlencode(params) 
    params['signature'] = create_signature(query_string) 
    headers = { 
        'X-MBX-APIKEY': API_KEY 
    } 
    
    url = f"{BASE_URL}{endpoint}?{urlencode(params)}" 
    try: 
        print(f"查询 URL: {url[:100]}...")  # 调试：部分URL 
        response = requests.get(url, headers=headers, timeout=10) 
        
        if response.status_code == 200: 
            trades = response.json() 
            print(f"成功查询到 {len(trades)} 条 CRV/USDC 交易记录（{datetime.fromtimestamp(START_TIME/1000).strftime('%Y-%m-%d %H:%M:%S')} ~ {datetime.fromtimestamp(END_TIME/1000).strftime('%Y-%m-%d %H:%M:%S')}）。") 
            
            liquidations = [] 
            total_pnl = 0 
            for trade in trades: 
                pnl = float(trade.get('realizedPnl', 0)) 
                total_pnl += pnl  # 累计盈亏 
                
                if pnl < 0:  # 负实现盈亏（爆仓核心标志） 
                    qty = float(trade['qty']) 
                    price = float(trade['price']) 
                    value = qty * price  # 交易价值 (USDC) 
                    
                    # 匹配爆仓：价值 >= 阈值 + 是平仓（isBuyer=False 为多头平仓） 
                    if value >= MIN_VALUE_USD: 
                        liquidation = { 
                            'trade_id': trade['id'], 
                            'timestamp': datetime.fromtimestamp(trade['time'] / 1000).strftime('%Y-%m-%d %H:%M:%S'), 
                            'qty': qty, 
                            'price': price, 
                            'value_usd': round(value, 2), 
                            'pnl': round(pnl, 4), 
                            'is_buyer': trade['isBuyer'],  # False: 卖出平多头（常见爆仓） 
                            'commission': float(trade.get('commission', 0)) 
                        } 
                        liquidations.append(liquidation) 
                        print(f"爆仓检测: ID={trade['id']}, 时间={liquidation['timestamp']}, 价值={value:.2f} USDC, 盈亏={pnl:.4f} USDC") 
            
            # 输出汇总 
            print(f"\n累计实现盈亏: {round(total_pnl, 4)} USDC") 
            if liquidations: 
                print("\n=== 验证结果：爆仓真实（检测到负P&L + >=100 USDC 仓位） ===") 
                print(json.dumps(liquidations, indent=2, ensure_ascii=False)) 
                return True, liquidations 
            else: 
                print("\n=== 验证结果：无爆仓记录，或仓位<100 USDC/非负P&L ===") 
                # 检查是否有持仓（可选扩展） 
                if trades: 
                    latest_trade = trades[-1] 
                    print(f"最新交易: {latest_trade.get('time', 'N/A')} - 盈亏 {float(latest_trade.get('realizedPnl', 0)):.4f} USDC") 
                return False, [] 
        else: 
            error_msg = response.text 
            print(f"API错误 {response.status_code}: {error_msg}") 
            # 常见错误：IP限制（2010）、无效密钥（-2015） 
            if 'IP' in error_msg or 2010 == response.status_code: 
                print("提示: 检查IP访问限制（推荐启用白名单）") 
            return False, [] 
    except requests.exceptions.RequestException as e: 
        print(f"网络/请求异常: {e}") 
        return False, [] 
    except Exception as e: 
        print(f"未知异常: {e}") 
        return False, [] 

# 主函数：运行验证 
if __name__ == "__main__": 
    print("=== CRV/USDC 爆仓验证程序启动 ===") 
    print(f"时间范围: {datetime.fromtimestamp(START_TIME/1000).strftime('%Y-%m-%d %H:%M:%S')} ~ {datetime.fromtimestamp(END_TIME/1000).strftime('%Y-%m-%d %H:%M:%S')}") 
    print(f"最小仓位: {MIN_VALUE_USD} USDC") 
    is_real, details = fetch_user_trades() 
    print(f"\n最终结果: {'爆仓真实 - 批准赔付' if is_real else '无爆仓/可能虚假 - 拒绝'}") 
    if details: 
        print(f"详情: {len(details)} 条爆仓记录")
