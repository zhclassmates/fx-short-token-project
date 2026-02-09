import argparse
from datetime import datetime
import os
from typing import Optional

import numpy as np
import pandas as pd
import requests

from _common import env, ensure_dir, write_json


def get_token_id(contract: str) -> Optional[str]:
    url = f"https://api.coingecko.com/api/v3/coins/ethereum/contract/{contract}"
    resp = requests.get(url, timeout=10).json()
    return resp.get("id")


def load_prices_from_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    elif "timestamp" in df.columns:
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("date")
    else:
        raise ValueError("CSV must contain date or timestamp column")
    if "price" not in df.columns:
        raise ValueError("CSV must contain price column")
    return df[["price"]].copy()


def get_historical_prices(token_id: str, vs_currency: str) -> pd.DataFrame:
    url = f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart?vs_currency={vs_currency}&days=max"
    print(f"Fetching data from: {url}")
    resp = requests.get(url, timeout=10).json()

    if "error" in resp or "prices" not in resp:
        raise RuntimeError(f"API error or missing prices: {resp.get('error')}")

    prices_data = resp["prices"]
    df = pd.DataFrame(prices_data, columns=["timestamp", "price"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df[["date", "price"]]
    df.set_index("date", inplace=True)
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="计算做多/做空 CR（VaR）")
    parser.add_argument("--contract", default="0x365AccFCa291e7D3914637ABf1F7635dB165Bb09")
    parser.add_argument("--vs", default="usd")
    parser.add_argument("--start", default="2023-10-01")
    parser.add_argument("--end", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--long", type=float, default=3.0)
    parser.add_argument("--short", type=float, default=3.0)
    parser.add_argument("--confidence", type=float, default=0.99)
    parser.add_argument("--csv", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--output-dir", default=env("FXN_OUTPUT_DIR", "./analysis"))
    args = parser.parse_args()

    ensure_dir(args.output_dir)
    out_path = args.out or os.path.join(args.output_dir, "cr_results.json")

    if args.csv:
        df = load_prices_from_csv(args.csv)
    else:
        token_id = get_token_id(args.contract)
        if not token_id:
            print("无法获取 CoinGecko token id，请使用 --csv")
            return 1
        print(f"CoinGecko token id: {token_id}")
        df = get_historical_prices(token_id, args.vs)

    df = df.loc[args.start:args.end].copy()
    if df.empty:
        print("价格数据为空，请检查日期范围或CSV内容")
        return 1

    df["return"] = df["price"].pct_change()
    df = df.dropna()

    downside_returns = -df["return"]
    VaR_down = np.percentile(downside_returns, args.confidence * 100)
    CR_long = 100 * (1 + VaR_down * args.long)

    upside_returns = df["return"]
    VaR_up = np.percentile(upside_returns, args.confidence * 100)
    CR_short = 100 * (1 + VaR_up * args.short)

    result = {
        "start": args.start,
        "end": args.end,
        "confidence": args.confidence,
        "leverage_long": args.long,
        "leverage_short": args.short,
        "CR_long": round(CR_long, 4),
        "CR_short": round(CR_short, 4),
    }

    write_json(out_path, result)
    print(f"做多 CR（{args.confidence*100:.2f}% VaR）: {CR_long:.2f}%")
    print(f"做空 CR（{args.confidence*100:.2f}% VaR）: {CR_short:.2f}%")
    print(f"结果已保存: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
