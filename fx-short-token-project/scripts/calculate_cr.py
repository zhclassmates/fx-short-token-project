import argparse
import os

import numpy as np
import pandas as pd

from _common import env, ensure_dir, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="动态杠杆下的 sToken CR 计算")
    parser.add_argument("--csv", default="")
    parser.add_argument("--target-leverage", type=float, default=3.0)
    parser.add_argument("--confidence", type=float, default=0.99)
    parser.add_argument("--output-dir", default=env("FXN_OUTPUT_DIR", "./analysis"))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    data_dir = env("FXN_DATA_DIR", "./data")
    file_path = args.csv or os.path.join(data_dir, "HYPE_protocol_prices.csv")

    df = pd.read_csv(file_path, parse_dates=["date"])
    df.set_index("date", inplace=True)
    df["return"] = df["price"].pct_change()
    df.dropna(inplace=True)

    P0 = df["price"].iloc[0]
    df["leverage_dynamic"] = args.target_leverage * P0 / df["price"]
    df["CR_daily"] = 100 * (1 + df["return"] * df["leverage_dynamic"])

    upside_CR = df["CR_daily"]
    VaR_CR = np.percentile(upside_CR, args.confidence * 100)

    ensure_dir(args.output_dir)
    out_path = args.out or os.path.join(args.output_dir, "dynamic_cr_results.json")

    result = {
        "confidence": args.confidence,
        "target_leverage": args.target_leverage,
        "VaR_CR": round(float(VaR_CR), 4),
        "start": df.index.min().strftime("%Y-%m-%d"),
        "end": df.index.max().strftime("%Y-%m-%d"),
        "count": int(len(df)),
        "CR_mean": round(float(df["CR_daily"].mean()), 4),
        "CR_min": round(float(df["CR_daily"].min()), 4),
        "CR_max": round(float(df["CR_daily"].max()), 4),
    }

    write_json(out_path, result)
    print(f"s token 做空 CR 阈值（{args.confidence*100:.2f}% VaR, 动态杠杆）：{VaR_CR:.2f}%")
    print(f"结果已保存: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
