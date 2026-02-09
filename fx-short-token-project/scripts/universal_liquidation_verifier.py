import time
import json
import requests
from datetime import datetime
import argparse
from abc import ABC, abstractmethod

class ExchangeVerifier(ABC):
    """交易所爆仓验证器基类"""
    
    @abstractmethod
    def verify_liquidation(self):
        """验证爆仓记录"""
        pass

class BinanceVerifier(ExchangeVerifier):
    """Binance交易所爆仓验证器"""
    def __init__(self, api_key, api_secret, symbol, days_back=1):
        self.base_url = 'https://fapi.binance.com'  # USDT-M
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol
        self.days_back = days_back
        
        # 计算时间范围
        current_time_ms = int(time.time() * 1000)
        self.start_time = current_time_ms - (days_back * 24 * 60 * 60 * 1000)
        self.end_time = current_time_ms
    
    def _create_signature(self, query_string):
        import hmac
        import hashlib
        from urllib.parse import urlencode
        return hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    
    def verify_liquidation(self):
        print(f"\n=== 开始Binance {self.symbol} 爆仓验证 ===")
        
        endpoint = '/fapi/v1/userTrades'
        params = {
            'symbol': self.symbol,
            'startTime': self.start_time,
            'endTime': self.end_time,
            'limit': 1000
        }
        
        # 生成签名
        from urllib.parse import urlencode
        query_string = urlencode(params)
        signature = self._create_signature(query_string)
        params['signature'] = signature
        headers = {'X-MBX-APIKEY': self.api_key}
        
        url = f"{self.base_url}{endpoint}?{urlencode(params)}"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            trades = response.json()
            
            print(f"查询到 {len(trades)} 条交易记录")
            
            # 检测爆仓：负实现盈亏且大额交易
            liquidations = []
            for trade in trades:
                if float(trade.get('realizedPnl', 0)) < 0:
                    qty = float(trade['qty'])
                    price = float(trade['price'])
                    pnl = float(trade['realizedPnl'])
                    value = qty * price
                    
                    # 筛选条件：大额亏损
                    if abs(pnl) > value * 0.1 or value > 100:  # 亏损超过10%或价值超过100USDT
                        liquidations.append({
                            'trade_id': trade['id'],
                            'timestamp': datetime.fromtimestamp(trade['time']/1000).strftime('%Y-%m-%d %H:%M:%S'),
                            'qty': qty,
                            'price': price,
                            'value': value,
                            'pnl': pnl,
                            'is_buyer': trade['isBuyer']
                        })
            
            if liquidations:
                print(f"\n检测到 {len(liquidations)} 条潜在爆仓记录：")
                for liq in liquidations:
                    print(f"时间: {liq['timestamp']}, 价值: {liq['value']:.2f}, 亏损: {liq['pnl']:.2f}")
                return True, liquidations
            else:
                print("未检测到爆仓记录")
                return False, []
                
        except requests.exceptions.RequestException as e:
            print(f"API请求错误: {e}")
            return False, []

class HyperliquidVerifier(ExchangeVerifier):
    """Hyperliquid交易所爆仓验证器"""
    def __init__(self, user_address, days_back=7):
        self.base_url = 'https://api.hyperliquid.xyz'
        self.user_address = user_address
        self.days_back = days_back
        
        # 计算时间范围
        current_time_ms = int(time.time() * 1000)
        self.start_time = current_time_ms - (days_back * 24 * 60 * 60 * 1000)
    
    def _post_request(self, endpoint, data):
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API请求错误: {e}")
            return None
    
    def verify_liquidation(self):
        print(f"\n=== 开始Hyperliquid 爆仓验证 ===")
        print(f"检查地址: {self.user_address}")
        
        # 获取用户交易历史
        fills_data = self._post_request('/info', {'user': self.user_address, 'type': 'userFills'})
        
        if not fills_data or 'fills' not in fills_data:
            print("无法获取交易历史数据")
            return False, []
        
        user_fills = fills_data['fills']
        recent_fills = [fill for fill in user_fills if fill['time'] >= self.start_time]
        
        print(f"查询到 {len(recent_fills)} 条近期交易记录")
        
        # 检测标记为liq的交易
        liquidations = []
        for fill in recent_fills:
            if fill.get('liq', False):  # liq为True表示爆仓
                coin = fill['coin']
                px = float(fill['px'])
                sz = float(fill['sz'])
                time_ms = fill['time']
                timestamp = datetime.fromtimestamp(time_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
                value = px * sz
                
                liquidations.append({
                    'coin': coin,
                    'timestamp': timestamp,
                    'price': px,
                    'quantity': sz,
                    'value': value,
                    'side': fill['side']
                })
        
        if liquidations:
            print(f"\n检测到 {len(liquidations)} 条爆仓记录：")
            for liq in liquidations:
                print(f"时间: {liq['timestamp']}, 资产: {liq['coin']}, 价值: {liq['value']:.2f}")
            return True, liquidations
        else:
            print("未检测到爆仓记录")
            return False, []

class UniversalLiquidationVerifier:
    """通用爆仓验证工具"""
    def __init__(self):
        self.verifiers = {}
    
    def register_verifier(self, exchange_name, verifier):
        """注册交易所验证器"""
        self.verifiers[exchange_name.lower()] = verifier
    
    def verify(self, exchange_name):
        """执行验证"""
        exchange_name = exchange_name.lower()
        if exchange_name not in self.verifiers:
            print(f"不支持的交易所: {exchange_name}")
            return False, []
        
        return self.verifiers[exchange_name].verify_liquidation()
    
    def verify_all(self):
        """验证所有注册的交易所"""
        results = {}
        for exchange_name, verifier in self.verifiers.items():
            is_real, data = verifier.verify_liquidation()
            results[exchange_name] = {'is_real': is_real, 'data': data}
        return results

# 配置示例和运行函数
def run_demo():
    """运行示例验证"""
    print("==== 通用爆仓验证工具 ====")
    print("注意：这是演示模式，需要配置真实API密钥才能使用")
    
    # 创建验证器实例
    verifier = UniversalLiquidationVerifier()
    
    # 配置交易所验证器（使用示例数据）
    # 注意：在实际使用时需要替换为真实的API密钥和地址
    binance_verifier = BinanceVerifier(
        api_key='YOUR_BINANCE_API_KEY',  # 替换为真实API密钥
        api_secret='YOUR_BINANCE_SECRET',  # 替换为真实API密钥
        symbol='CRVUSDC',
        days_back=1
    )
    
    hyperliquid_verifier = HyperliquidVerifier(
        user_address='YOUR_WALLET_ADDRESS',  # 替换为真实钱包地址
        days_back=7
    )
    
    # 注册验证器
    verifier.register_verifier('binance', binance_verifier)
    verifier.register_verifier('hyperliquid', hyperliquid_verifier)
    
    # 验证单个交易所
    # verifier.verify('binance')
    
    # 验证所有交易所
    results = verifier.verify_all()
    
    # 生成报告
    print("\n==== 验证报告 ====")
    for exchange, result in results.items():
        status = "检测到爆仓" if result['is_real'] else "未检测到爆仓"
        print(f"{exchange}: {status}")

if __name__ == "__main__":
    run_demo()