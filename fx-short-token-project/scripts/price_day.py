import argparse
import os
from typing import Optional

import pandas as pd
import requests

from _common import env, ensure_dir


def get_token_id(contract: str) -> Optional[str]:
    url = f"https://api.coingecko.com/api/v3/coins/ethereum/contract/{contract}"
    print(f"请求代币ID的URL: {url}")
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        print(f"获取代币ID失败，状态码: {resp.status_code}")
        return None

    data = resp.json()
    print(f"获取代币ID响应键: {list(data.keys())}")
    if "error" in data:
        print(f"API返回错误: {data['error']}")
        return None
    return data.get("id")


def get_historical_prices(token_id: str, vs_currency: str, days: int):
    url = f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart?vs_currency={vs_currency}&days={days}"
    print(f"请求历史价格的URL: {url}")
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        print(f"获取历史价格失败，状态码: {resp.status_code}")
        return None

    data = resp.json()
    print(f"获取历史价格响应键: {list(data.keys())}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="获取历史价格数据（CoinGecko）并保存为CSV")
    parser.add_argument("--contract", default="0x365AccFCa291e7D3914637ABf1F7635dB165Bb09")
    parser.add_argument("--vs", default="usd")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--data-dir", default=env("FXN_DATA_DIR", "./data"))
    parser.add_argument("--out-file", default="")
    parser.add_argument("--fallback-csv", default="fx_protocol_prices.csv")
    args = parser.parse_args()

    out_dir = args.data_dir
    ensure_dir(out_dir)
    out_file = args.out_file or os.path.join(out_dir, "HYPE_protocol_prices.csv")

    token_id = get_token_id(args.contract)
    if token_id:
        print(f"成功获取CoinGecko token id: {token_id}")
        data = get_historical_prices(token_id, args.vs, args.days)
        if data and "prices" in data:
            prices = data["prices"]
            df = pd.DataFrame(prices, columns=["timestamp", "price"])
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df[["date", "price"]].copy()
            df.set_index("date", inplace=True)
            print(f"成功获取历史价格数据，共 {len(df)} 个数据点")
            df.to_csv(out_file)
            print(f"历史价格数据已保存为: {out_file}")
            return 0
        print("未能获取有效价格数据")
    else:
        print("未能获取代币ID，无法继续")

    # fallback
    if args.fallback_csv and os.path.isfile(args.fallback_csv):
        print(f"检测到已存在的 {args.fallback_csv}，将其复制为 {out_file}")
        existing_df = pd.read_csv(args.fallback_csv, index_col=0)
        existing_df.to_csv(out_file)
        print(f"已使用现有数据文件，包含 {len(existing_df)} 个数据点")
        return 0

    print("未生成任何价格数据文件")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
