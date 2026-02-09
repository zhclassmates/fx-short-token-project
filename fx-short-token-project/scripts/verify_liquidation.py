import hmac 
import hashlib 
import time 
import requests 
import json 
from urllib.parse import urlencode 

# Binance Futures API 配置（USDT-M 或 USDC-M 合约） 
BASE_URL = 'https://fapi.binance.com'  # 对于 USDC-M，用 'https://dapi.binance.com' 如果是 COIN-M 
API_KEY = 'YOUR_BINANCE_API_KEY'  # 用户替换为自己的 Read-Only API 密钥 
API_SECRET = 'YOUR_BINANCE_SECRET'  # 用户替换 
SYMBOL = 'CRVUSDC'  # 替换为你的合约符号，如 CRVUSDC 
START_TIME = int(time.time() * 1000) - 86400000  # 过去24小时的 Unix 时间戳 (ms) 
END_TIME = int(time.time() * 1000)  # 当前时间 

def create_signature(query_string): 
    """生成 Binance API 签名"""
    return hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest() 

def fetch_user_trades(): 
    """查询用户交易历史，检测爆仓"""
    endpoint = '/fapi/v1/userTrades' 
    params = { 
        'symbol': SYMBOL, 
        'startTime': START_TIME, 
        'endTime': END_TIME, 
        'limit': 1000 
    } 
    query_string = urlencode(params) 
    signature = create_signature(query_string) 
    params['signature'] = signature 
    headers = {'X-MBX-APIKEY': API_KEY} 
    
    url = f"{BASE_URL}{endpoint}?{urlencode(params)}" 
    response = requests.get(url, headers=headers) 
    
    if response.status_code == 200: 
        trades = response.json() 
        print(f"查询到 {len(trades)} 条交易记录。") 
        
        # 检测爆仓：实现盈亏 < 0 且数量匹配开仓（假设爆仓为全平仓） 
        liquidations = [] 
        for trade in trades: 
            if float(trade.get('realizedPnl', 0)) < 0:  # 负实现盈亏 
                qty = float(trade['qty']) 
                price = float(trade['price']) 
                pnl = float(trade['realizedPnl']) 
                is_buyer = trade['isBuyer'] 
                trade_id = trade['id'] 
                timestamp = trade['time'] 
                
                # 简单匹配：假设开仓价值 >= 100 USDC（你的最小仓） 
                value = qty * price 
                if value >= 100: 
                    liquidations.append({ 
                        'trade_id': trade_id, 
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp / 1000)), 
                        'qty': qty, 
                        'price': price, 
                        'value_usd': value, 
                        'pnl': pnl, 
                        'is_buyer': is_buyer  # True: 买入平空仓, False: 卖出平多仓 
                    }) 
                    print(f"潜在爆仓检测: ID={trade_id}, 时间={timestamp}, 价值={value:.2f} USDC, 盈亏={pnl:.4f} USDC") 
        
        if liquidations: 
            print("\n=== 爆仓验证结果：真实（检测到负盈亏全平仓） ===") 
            print(json.dumps(liquidations, indent=2, ensure_ascii=False)) 
            return True 
        else: 
            print("\n=== 爆仓验证结果：未检测到，或非真实爆仓（无负盈亏记录） ===") 
            return False 
    else: 
        print(f"API错误: {response.status_code} - {response.text}") 
        return False 

# 运行验证 
if __name__ == "__main__": 
    print("开始验证你的交易记录真实性...") 
    is_real = fetch_user_trades() 
    print(f"最终结果: {'真实' if is_real else '可能虚假/未爆仓'}")