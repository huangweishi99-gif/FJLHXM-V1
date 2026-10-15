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

# === 同步容错配置 ===
MAX_SYMBOL_RETRIES = 3            # 单币种单周期失败后的最大尝试次数
SYMBOL_RETRY_BACKOFF_SECONDS = 5  # 重试退避基数（秒），第 n 次重试等待 n*基数
FAILED_ROUND_ALERT_THRESHOLD = 3  # 连续几轮存在失败时输出 CRITICAL 告警


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


def sync_one_symbol(api_client, symbol, folder_name, api_interval, *, retries=MAX_SYMBOL_RETRIES):
    """同步单个币种 + 周期，失败自动带退避重试。

    返回 {"status": "ok"|"skipped"|"failed", "message": str}：
    - ok:      已写入新 K 线
    - skipped: 本地已是最新，无需更新
    - failed:  重试耗尽
    """
    file_path = os.path.join(BASE_DIR, folder_name, f"{symbol}.csv")
    for attempt in range(1, retries + 1):
        try:
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

            # 从币安获取 K 线
            klines = api_client.get_historical_klines(symbol, api_interval, start_str)

            if not klines:
                print(f"✨ [{symbol} - {folder_name}] 已经是最新，无需更新。")
                return {"status": "skipped", "message": "already up-to-date"}

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
            return {"status": "ok", "message": f"rows={len(combined_df)}"}

        except Exception as exc:
            if attempt < retries:
                wait = SYMBOL_RETRY_BACKOFF_SECONDS * attempt
                print(f"⚠️ [{symbol} - {folder_name}] 第 {attempt}/{retries} 次失败: {exc}，{wait}s 后重试", flush=True)
                time.sleep(wait)
            else:
                print(f"❌ [{symbol} - {folder_name}] 同步失败（{retries} 次重试均失败）: {exc}", flush=True)
                return {"status": "failed", "message": str(exc)}
    return {"status": "failed", "message": "unreachable"}


def sync_data():
    """核心同步函数：遍历所有币种和周期，自动判断【首次下载】或【增量更新】。

    返回统计 dict {ok, skipped, failed, failed_items}，供守护进程做失败告警。
    """
    print(f"\n======== 🔄 开始数据同步流 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ========")

    stats = {"ok": 0, "skipped": 0, "failed": 0, "failed_items": []}
    for folder_name, api_interval in INTERVALS.items():
        for symbol in SYMBOLS:
            result = sync_one_symbol(client, symbol, folder_name, api_interval)
            status = result["status"]
            stats[status] = stats.get(status, 0) + 1
            if status == "failed":
                stats["failed_items"].append(f"{symbol}-{folder_name}")
    print(f"[SUMMARY] ok={stats['ok']} skipped={stats['skipped']} failed={stats['failed']}"
          f" failed_items={','.join(stats['failed_items']) or '-'}", flush=True)
    return stats


def evaluate_failure_alert(consecutive_failed_rounds: int, stats: dict) -> tuple[int, str | None]:
    """按轮次更新连续失败计数并生成告警文本。

    返回 (new_consecutive, alert_text)。stats["failed"] == 0 时重置计数且无告警。
    告警文本带 [ALERT] 前缀，供 watchdog 关键字抓取。
    """
    if stats["failed"] == 0:
        return (0, None)
    consecutive = consecutive_failed_rounds + 1
    failed_items = ",".join(stats.get("failed_items") or []) or "-"
    if consecutive >= FAILED_ROUND_ALERT_THRESHOLD:
        return (consecutive, f"[ALERT] 数据同步已连续 {consecutive} 轮存在失败: {failed_items}")
    return (consecutive, f"[ALERT] 本轮同步失败: {failed_items}")


if __name__ == "__main__":
    init_folders()

    # 开启无限循环守护进程
    consecutive_failed_rounds = 0
    while True:
        try:
            stats = sync_data()
            consecutive_failed_rounds, alert = evaluate_failure_alert(consecutive_failed_rounds, stats)
            if alert:
                print(f"{'🚨' if stats['failed'] >= FAILED_ROUND_ALERT_THRESHOLD else '⚠️'} {alert}", flush=True)
            print("\n😴 本轮同步结束，程序将静默等待 10 分钟...")
            # 600秒 = 10分钟
            time.sleep(600)
        except KeyboardInterrupt:
            print("\n👋 收到退出信号，数据同步程序已安全停止。")
            break
        except Exception as main_e:
            print(f"⚠️ 守护进程遇到未知错误: {main_e}，将在 60 秒后重试...", flush=True)
            time.sleep(60)
