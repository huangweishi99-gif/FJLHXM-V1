import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from binance.client import Client

# === 1. 基础配置 ===
# 替换为你全新的 20 个监控币种列表
SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT', 
    'TRUMPUSDT', 'RENDERUSDT', 'IOUSDT', 'TAOUSDT', 
    'DASHUSDT', 'LTCUSDT', 'DOGEUSDT', 'ADAUSDT', 
    'APTUSDT', 'LINKUSDT', 'BNBUSDT', 'ZECUSDT'
]
# 映射本地文件夹名称与币安API的周期参数
INTERVALS = {
    '1d': Client.KLINE_INTERVAL_1DAY,
    '1h': Client.KLINE_INTERVAL_1HOUR,
    '15m': Client.KLINE_INTERVAL_15MINUTE
}
BASE_DIR = 'data'
client = Client()


def read_existing_klines(file_path: str) -> pd.DataFrame | None:
    path = Path(file_path)
    if not path.exists() or path.stat().st_size <= 5:
        return None
    try:
        frame = pd.read_csv(file_path, index_col="timestamp", parse_dates=True)
    except pd.errors.EmptyDataError:
        return None
    if frame.empty:
        return None
    return frame


def atomic_save_csv(frame: pd.DataFrame, file_path: str) -> None:
    if frame.empty:
        raise ValueError("refuse to save empty kline frame")
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp_path)
    os.replace(tmp_path, path)


def init_folders():
    """初始化数据存储文件夹结构"""
    for folder in INTERVALS.keys():
        os.makedirs(os.path.join(BASE_DIR, folder), exist_ok=True)

def sync_data():
    """核心同步函数：遍历所有币种和周期，自动判断【首次下载】或【增量更新】"""
    print(f"\n======== 🔄 开始数据同步流 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ========")
    
    for folder_name, api_interval in INTERVALS.items():
        for symbol in SYMBOLS:
            file_path = os.path.join(BASE_DIR, folder_name, f"{symbol}.csv")
            
            existing_df = read_existing_klines(file_path)
            if existing_df is not None:
                last_time = existing_df.index[-1]
                start_str = str(int(last_time.timestamp() * 1000))
                is_incremental = True
            else:
                start_str = "5 years ago UTC"
                is_incremental = False

            if is_incremental:
                print(f"⚡ [{symbol} - {folder_name}] 发现本地数据，正在追加最新增量数据...")
            else:
                print(f"📥 [{symbol} - {folder_name}] 本地无历史，正在拉取5年历史打底数据 (请耐心等待)...")

            try:
                # 从币安获取 K 线
                klines = client.get_historical_klines(symbol, api_interval, start_str)
                
                if not klines:
                    print(f"✨ [{symbol} - {folder_name}] 已经是最新，无需更新。")
                    continue

                # 规整字段
                columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore']
                new_df = pd.DataFrame(klines, columns=columns)
                new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
                new_df.set_index('timestamp', inplace=True)
                
                # 转换数值类型并只保留核心量化列
                numeric_cols = ['open', 'high', 'low', 'close', 'volume']
                new_df[numeric_cols] = new_df[numeric_cols].astype(float)
                new_df = new_df[numeric_cols]

                # 数据合并与去重。增量同步从最后一根K线的开盘时间开始拉取，
                # 所以这里必须保留新数据，覆盖更新未收盘的最后一根K线。
                if is_incremental:
                    combined_df = pd.concat([existing_df, new_df])
                    combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
                else:
                    combined_df = new_df

                atomic_save_csv(combined_df, file_path)
                print(f"✅ [{symbol} - {folder_name}] 同步成功。当前总行数: {len(combined_df)}")
                
                # 稍微小睡一下，防止频繁请求接口触发币安权重限制
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ [{symbol} - {folder_name}] 同步出错: {e}")

if __name__ == "__main__":
    init_folders()
    
    # 开启无限循环守护进程
    while True:
        try:
            sync_data()
            print("\n😴 本轮同步结束，程序将静默等待 10 分钟...")
            # 600秒 = 10分钟
            time.sleep(600) 
        except KeyboardInterrupt:
            print("\n👋 收到退出信号，数据同步程序已安全停止。")
            break
        except Exception as main_e:
            print(f"⚠️ 守护进程遇到未知错误: {main_e}，将在 60 秒后重试...")
            time.sleep(60)
