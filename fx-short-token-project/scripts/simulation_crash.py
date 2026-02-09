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

# 爆仓模拟参数
开仓价 = 108246.36  # 根据第一个数据点的价格设置
止损价 = 开仓价 * 0.99  # 1%止损

# -------------------------------
# 爆仓模拟函数
# -------------------------------
def 爆仓模拟(df, 窗口秒):
    # 滑动窗口最小低价
    df['滑动低'] = df['低'].rolling(window=窗口秒, min_periods=1).min()
    # 是否有任意一秒 窗口内最低价 ≤ 止损
    触发 = (df['滑动低'] <= 止损价).any()
    return '爆仓' if 触发 else '没爆'

# -------------------------------
# 读取并处理数据
# -------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="爆仓模拟（固定止损）")
    parser.add_argument("--input-dir", default=env("FXN_DATA_DIR", "./data"))
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--open-price", type=float, default=108246.36)
    parser.add_argument("--stoploss", type=float, default=0.99)
    parser.add_argument("--output-dir", default=env("FXN_OUTPUT_DIR", "./analysis"))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    global 开仓价, 止损价
    开仓价 = args.open_price
    止损价 = 开仓价 * args.stoploss

    print("开始处理爆仓模拟...")
    print(f"开仓价: {开仓价}")
    print(f"止损价: {止损价}")

    input_dir = args.input_dir
    csv_files = glob.glob(os.path.join(input_dir, '*.csv'))
    if not csv_files:
        print(f"错误: 在目录 {input_dir} 中未找到CSV文件")
        return 1

    print(f"找到 {len(csv_files)} 个CSV文件需要处理")

    爆仓天数 = 0
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
                模拟结果 = 爆仓模拟(日数据, args.window)

                if 模拟结果 == '爆仓':
                    爆仓天数 += 1
                    print(f"日期 {单日}: 爆仓")

                总天数 += 1

        except Exception as e:
            print(f"处理文件 {file_name} 时出错: {e}")
            continue

    if 总天数 > 0:
        概率 = 爆仓天数 / 总天数
        print(f"\n爆仓模拟结果:")
        print(f"总天数: {总天数}")
        print(f"爆仓天数: {爆仓天数}")
        print(f"爆仓概率: {概率:.2%}")
    else:
        print("\n未找到有效的数据进行爆仓模拟")
        return 1

    ensure_dir(args.output_dir)
    out_path = args.out or os.path.join(args.output_dir, "simulation_summary.json")
    write_json(out_path, {
        "window": args.window,
        "open_price": 开仓价,
        "stoploss_ratio": args.stoploss,
        "total_days": 总天数,
        "crash_days": 爆仓天数,
        "crash_prob": round(概率, 6),
    })
    print(f"结果已保存: {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
