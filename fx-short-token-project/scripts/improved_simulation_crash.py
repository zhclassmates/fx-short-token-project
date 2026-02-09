import argparse
import pandas as pd
import os
import glob
from datetime import datetime, timedelta

from _common import env, ensure_dir, write_json

# -------------------------------
# 参数设置
# -------------------------------
input_dir = os.getenv('FXN_DATA_DIR', './data')

# -------------------------------
# 改进版爆仓模拟函数
# -------------------------------
def 爆仓模拟(df, 窗口秒, 止损比例=0.99):
    # 动态设置当天的开仓价（使用当天第一个数据点的开盘价）
    当天开仓价 = df['开'].iloc[0]  
    止损价 = 当天开仓价 * 止损比例  # 1%止损
    
    # 滑动窗口最小低价
    df['滑动低'] = df['低'].rolling(window=窗口秒, min_periods=1).min()
    
    # 是否有任意一秒 窗口内最低价 ≤ 止损
    触发 = (df['滑动低'] <= 止损价).any()
    
    return {
        '是否爆仓': 触发,
        '开仓价': 当天开仓价,
        '止损价': 止损价,
        '最低滑动价': df['滑动低'].min()
    }

# -------------------------------
# 读取并处理数据
# -------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="改进版爆仓模拟（按日开盘价）")
    parser.add_argument("--input-dir", default=env("FXN_DATA_DIR", "./data"))
    parser.add_argument("--stoploss", type=float, default=0.99)
    parser.add_argument("--min-rows", type=int, default=100)
    parser.add_argument("--output-dir", default=env("FXN_OUTPUT_DIR", "./analysis"))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    print("开始处理改进版爆仓模拟...")
    print("使用每天的实际开盘价作为开仓价，动态计算止损价")

    csv_files = glob.glob(os.path.join(args.input_dir, '*.csv'))
    if not csv_files:
        print(f"错误: 在目录 {args.input_dir} 中未找到CSV文件")
        return 1

    print(f"找到 {len(csv_files)} 个CSV文件需要处理")

    爆仓天数_3秒 = 0
    爆仓天数_5秒 = 0
    总天数 = 0

    for file_path in csv_files:
        file_name = os.path.basename(file_path)
        print(f"\n正在处理文件: {file_name}")
        try:
            df = pd.read_csv(file_path)
            print(f"成功读取数据，共 {len(df)} 行")

            df['时间'] = pd.to_datetime(df['时间'])
            df['日期'] = df['时间'].dt.date
            唯一日期 = df['日期'].unique()
            print(f"文件中包含 {len(唯一日期)} 天的数据")

            for 单日 in 唯一日期:
                日数据 = df[df['日期'] == 单日].copy()
                if len(日数据) < args.min_rows:
                    continue

                结果_3秒 = 爆仓模拟(日数据, 3, args.stoploss)
                结果_5秒 = 爆仓模拟(日数据, 5, args.stoploss)

                if 结果_3秒['是否爆仓']:
                    爆仓天数_3秒 += 1
                if 结果_5秒['是否爆仓']:
                    爆仓天数_5秒 += 1

                总天数 += 1
                if 总天数 % 10 == 0:
                    print(f"已处理 {总天数} 天数据")

        except Exception as e:
            print(f"处理文件 {file_name} 时出错: {e}")
            continue

    if 总天数 > 0:
        概率_3秒 = 爆仓天数_3秒 / 总天数
        概率_5秒 = 爆仓天数_5秒 / 总天数

        print(f"\n爆仓模拟结果:")
        print(f"总处理天数: {总天数}")
        print(f"3秒窗口爆仓天数: {爆仓天数_3秒}")
        print(f"3秒窗口爆仓概率: {概率_3秒:.2%}")
        print(f"5秒窗口爆仓天数: {爆仓天数_5秒}")
        print(f"5秒窗口爆仓概率: {概率_5秒:.2%}")
    else:
        print("\n未找到有效的数据进行爆仓模拟")
        return 1

    ensure_dir(args.output_dir)
    out_path = args.out or os.path.join(args.output_dir, "improved_simulation_summary.json")
    write_json(out_path, {
        "stoploss_ratio": args.stoploss,
        "min_rows": args.min_rows,
        "total_days": 总天数,
        "crash_days_3s": 爆仓天数_3秒,
        "crash_days_5s": 爆仓天数_5秒,
        "crash_prob_3s": round(概率_3秒, 6),
        "crash_prob_5s": round(概率_5秒, 6),
    })
    print(f"结果已保存: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
