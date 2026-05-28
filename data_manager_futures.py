from __future__ import annotations

import os
import time
import traceback
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path

import pandas as pd
from tqsdk2 import TqApi, TqAuth

# --- 天勤账号配置 ---
# 先兼容原有服务器运行方式；后续可以把账号密码放到系统环境变量。
TQ_PHONE = os.getenv("TQ_PHONE", "15323854134")
TQ_PASS = os.getenv("TQ_PASS", "Hwsgzjdqg1021")

# --- 目录配置 ---
DATA_DIR = Path(os.getenv("FUTURES_DATA_DIR", r"C:\Users\Administrator\quant_futures\data"))
LOG_DIR = Path(os.getenv("FUTURES_LOG_DIR", r"C:\Users\Administrator\quant_futures\runtime\logs"))
LOG_FILE = LOG_DIR / "data_manager_futures.log"
STALE_CATCHUP_HOURS = int(os.getenv("FUTURES_STALE_CATCHUP_HOURS", "36"))
for d in ["1d", "1h", "15m"]:
    (DATA_DIR / d).mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

DATA_LENGTHS = {
    "1d": int(os.getenv("FUTURES_1D_LENGTH", "800")),
    "1h": int(os.getenv("FUTURES_1H_LENGTH", "2600")),
    # DS09 需要更长 M15：默认 12000 根（约 125 个交易日）；天勤上限不足时可调低 FUTURES_15M_LENGTH
    # GFEX LC 在 tqsdk2 下 data_length>8000 时 15m 曾出现脏数据，默认 8000；需更长可设 FUTURES_15M_LENGTH
    "15m": int(os.getenv("FUTURES_15M_LENGTH", "8000")),
}
TIMEFRAMES = {
    "1d": 86400,
    "1h": 3600,
    "15m": 900,
}
MAX_FETCH_RETRIES = 3
MAX_CONNECT_RETRIES = 3
RETRY_SLEEP_SECONDS = 3
CONNECT_RETRY_SLEEP_SECONDS = 10
CSV_REPLACE_RETRIES = 5
POLL_INTERVAL_SECONDS = 300
IDLE_SLEEP_SECONDS = 60
MARKET_MODE = os.getenv("MARKET_MODE", "futures").strip().lower()

# 国内期货默认按“开盘前 30 分钟开始，收盘后停止”控制：
# 日盘 09:00/13:30 开盘，夜盘 21:00 开盘；夜盘最长品种到次日 02:30。
# A股没有夜盘，若未来单独跑 A股数据泵，可设置 MARKET_MODE=astock。
FUTURES_WINDOWS = (
    (dt_time(8, 30), dt_time(11, 35), {0, 1, 2, 3, 4}),
    (dt_time(13, 0), dt_time(15, 15), {0, 1, 2, 3, 4}),
    (dt_time(20, 30), dt_time(23, 59, 59), {0, 1, 2, 3, 4}),
    (dt_time(0, 0), dt_time(2, 35), {1, 2, 3, 4, 5}),
)
A_STOCK_WINDOWS = (
    (dt_time(9, 0), dt_time(11, 35), {0, 1, 2, 3, 4}),
    (dt_time(12, 30), dt_time(15, 5), {0, 1, 2, 3, 4}),
)

# --- 核心翻译官：将简称映射为天勤的机构级主连合约代码 ---
TQ_SYMBOL_MAP = {
    # 郑商所
    "SA": "KQ.m@CZCE.SA", "FG": "KQ.m@CZCE.FG", "CJ": "KQ.m@CZCE.CJ", "OI": "KQ.m@CZCE.OI",
    "SH": "KQ.m@CZCE.SH", "SR": "KQ.m@CZCE.SR", "SF": "KQ.m@CZCE.SF", "MA": "KQ.m@CZCE.MA",
    "TA": "KQ.m@CZCE.TA", "UR": "KQ.m@CZCE.UR", "CF": "KQ.m@CZCE.CF",
    # 上期所
    "RB": "KQ.m@SHFE.rb", "FU": "KQ.m@SHFE.fu", "SP": "KQ.m@SHFE.sp", "NI": "KQ.m@SHFE.ni",
    "AO": "KQ.m@SHFE.ao", "RU": "KQ.m@SHFE.ru", "BR": "KQ.m@SHFE.br", "AU": "KQ.m@SHFE.au", "AG": "KQ.m@SHFE.ag",
    # 大商所
    "PG": "KQ.m@DCE.pg", "LH": "KQ.m@DCE.lh", "JD": "KQ.m@DCE.jd", "PP": "KQ.m@DCE.pp",
    "EB": "KQ.m@DCE.eb", "EG": "KQ.m@DCE.eg", "JM": "KQ.m@DCE.jm", "M": "KQ.m@DCE.m",
    "P": "KQ.m@DCE.p", "V": "KQ.m@DCE.v",
    # 广期所
    "SI": "KQ.m@GFEX.si", "LC": "KQ.m@GFEX.lc",
    # 上期能源
    "EC": "KQ.m@INE.ec", "SC": "KQ.m@INE.sc",
}


def ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log_line(message: str) -> None:
    line = f"[{ts()}] {message}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def active_windows() -> tuple[tuple[dt_time, dt_time, set[int]], ...]:
    if MARKET_MODE in {"astock", "a_stock", "stock", "ashare", "a-share"}:
        return A_STOCK_WINDOWS
    return FUTURES_WINDOWS


def is_market_update_time(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    weekday = now.weekday()
    current = now.time()
    for start, end, days in active_windows():
        if weekday in days and start <= current <= end:
            return True
    return False


def seconds_until_next_window(now: datetime | None = None) -> int:
    now = now or datetime.now()
    candidates: list[datetime] = []
    for day_offset in range(8):
        day = now.date() + timedelta(days=day_offset)
        weekday = day.weekday()
        for start, _, days in active_windows():
            candidate = datetime.combine(day, start)
            if weekday in days and candidate > now:
                candidates.append(candidate)
    if not candidates:
        return IDLE_SLEEP_SECONDS
    return max(1, int((min(candidates) - now).total_seconds()))


def atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    frame.to_csv(tmp, index=False, encoding="utf-8")
    for attempt in range(1, CSV_REPLACE_RETRIES + 1):
        try:
            os.replace(str(tmp), str(path))
            return
        except PermissionError:
            if attempt >= CSV_REPLACE_RETRIES:
                raise
            time.sleep(0.2 * attempt)


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    if "datetime" not in data.columns:
        raise ValueError("天勤返回数据缺少 datetime 字段")
    numeric = pd.to_numeric(data["datetime"], errors="coerce")
    if numeric.notna().any() and float(numeric.max(skipna=True)) > 1e14:
        data["date"] = pd.to_datetime(numeric, unit="ns", errors="coerce")
    else:
        data["date"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["date"] = data["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    data = data.dropna(subset=["date"]).reset_index(drop=True)
    if data.empty:
        raise ValueError("天勤返回空数据")
    return data


def frame_looks_sane(frame: pd.DataFrame) -> bool:
    if frame.empty or "date" not in frame.columns:
        return False
    dates = pd.to_datetime(frame["date"], errors="coerce")
    recent = dates >= pd.Timestamp("2020-01-01")
    if recent.sum() < max(10, int(len(frame) * 0.85)):
        return False
    for column in ("open", "high", "low", "close"):
        if column not in frame.columns:
            return False
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().sum() < max(10, int(len(frame) * 0.85)):
            return False
    highs = pd.to_numeric(frame["high"], errors="coerce")
    lows = pd.to_numeric(frame["low"], errors="coerce")
    return bool((highs > lows).sum() >= max(10, int(len(frame) * 0.85)))


def _length_candidates(timeframe: str, target: int) -> list[int]:
    if timeframe == "1d":
        extras = (1200, 1000, 800, 600, 400, 300)
    elif timeframe == "15m":
        extras = (12000, 11000, 10000, 9500, 9000, 8500, 8000, 6000, 4000, 3000)
    else:
        return [target]
    ordered = [target, *extras]
    min_len = 300 if timeframe == "1d" else 3000
    seen: set[int] = set()
    out: list[int] = []
    for value in ordered:
        if value < min_len or value in seen:
            continue
        if timeframe in ("1d", "1h") and value > target:
            continue
        seen.add(value)
        out.append(value)
    return sorted(out, reverse=True)


def fetch_frame(api: TqApi, tq_code: str, timeframe: str) -> pd.DataFrame:
    last_error: Exception | None = None
    seconds = TIMEFRAMES[timeframe]
    length = DATA_LENGTHS[timeframe]
    pick_longest = (timeframe == "15m" and length > 8000) or (timeframe == "1d" and length > 800)
    best: pd.DataFrame | None = None
    best_len = 0
    best_data_length = length

    for data_length in _length_candidates(timeframe, length):
        for attempt in range(1, MAX_FETCH_RETRIES + 1):
            try:
                frame = api.get_kline_serial(tq_code, seconds, data_length=data_length)
                normalized = normalize_frame(frame)
                if not frame_looks_sane(normalized):
                    log_line(f"[WARN] {tq_code} {timeframe} data_length={data_length} 校验未通过")
                    break
                row_count = len(normalized)
                if pick_longest:
                    if row_count > best_len:
                        best = normalized
                        best_len = row_count
                        best_data_length = data_length
                    continue
                if data_length != length:
                    log_line(f"[INFO] {tq_code} {timeframe} 使用 data_length={data_length}（原 {length}）")
                return normalized
            except Exception as exc:
                last_error = exc
                print(f"[WARN] [{ts()}] {tq_code} {timeframe} 第 {attempt}/{MAX_FETCH_RETRIES} 次抓取失败: {exc}", flush=True)
                if attempt < MAX_FETCH_RETRIES:
                    time.sleep(RETRY_SLEEP_SECONDS)
        stop_at = 8000 if timeframe == "15m" else 400
        if pick_longest and best is not None and data_length <= stop_at:
            break

    if best is not None:
        log_line(f"[INFO] {tq_code} {timeframe} 选用 data_length={best_data_length} rows={best_len}")
        return best
    raise RuntimeError(f"{tq_code} {timeframe} 连续抓取失败: {last_error}")


def fetch_symbol(api: TqApi, short_code: str, tq_code: str) -> bool:
    ok = True
    rows: dict[str, int] = {}
    for timeframe in ["1d", "1h", "15m"]:
        try:
            frame = fetch_frame(api, tq_code, timeframe)
            primary = DATA_DIR / timeframe / f"{short_code}.csv"
            atomic_write_csv(frame, primary)
            legacy = DATA_DIR / timeframe / f"{short_code}USDT.csv"
            if legacy != primary:
                atomic_write_csv(frame, legacy)
            rows[timeframe] = len(frame)
        except Exception as exc:
            ok = False
            log_line(f"[ERROR] 抓取 [{short_code}] {timeframe} 失败: {exc}")
    if ok:
        log_line(f"[OK] 成功抓取 [{short_code}] 1d={rows.get('1d', 0)} 1h={rows.get('1h', 0)} 15m={rows.get('15m', 0)}")
    return ok


def connect_api() -> TqApi:
    last_error: Exception | None = None
    for attempt in range(1, MAX_CONNECT_RETRIES + 1):
        try:
            return TqApi(auth=TqAuth(TQ_PHONE, TQ_PASS))
        except Exception as exc:
            last_error = exc
            print(f"[WARN] [{ts()}] 天勤连接第 {attempt}/{MAX_CONNECT_RETRIES} 次失败: {exc}", flush=True)
            if attempt < MAX_CONNECT_RETRIES:
                time.sleep(CONNECT_RETRY_SLEEP_SECONDS)
    raise RuntimeError(f"天勤连接连续失败: {last_error}")


def latest_1d_mtime(short_code: str) -> datetime | None:
    path = DATA_DIR / "1d" / f"{short_code}.csv"
    if not path.exists():
        path = DATA_DIR / "1d" / f"{short_code}USDT.csv"
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime)


def needs_stale_catchup() -> bool:
    now = datetime.now()
    stale: list[str] = []
    for short_code in TQ_SYMBOL_MAP:
        mtime = latest_1d_mtime(short_code)
        if mtime is None or (now - mtime).total_seconds() > STALE_CATCHUP_HOURS * 3600:
            stale.append(short_code)
    if stale:
        log_line(f"[CATCHUP] 日线停更超过 {STALE_CATCHUP_HOURS}h，需补抓: {','.join(stale[:8])}{'...' if len(stale)>8 else ''}")
        return True
    return False


def fetch_all_data(api: TqApi) -> tuple[int, int]:
    success_count = 0
    fail_count = 0
    try:
        log_line(f"开始抓取 {len(TQ_SYMBOL_MAP)} 个品种。")
        for short_code, tq_code in TQ_SYMBOL_MAP.items():
            if fetch_symbol(api, short_code, tq_code):
                success_count += 1
            else:
                fail_count += 1
            time.sleep(0.2)
    except Exception as exc:
        fail_count += max(0, len(TQ_SYMBOL_MAP) - success_count - fail_count)
        log_line(f"[ERROR] 天勤数据更新严重异常: {exc}")
        log_line(traceback.format_exc())
    finally:
        log_line(f"本轮天勤数据更新完毕：成功 {success_count}，失败 {fail_count}。")
    return success_count, fail_count


def main() -> None:
    api: TqApi | None = None
    log_line(f"[天勤直连版] 数据泵启动，市场模式={MARKET_MODE}，日志={LOG_FILE}")
    while True:
        if not is_market_update_time() and not needs_stale_catchup():
            if api is not None:
                try:
                    api.close()
                except Exception as exc:
                    print(f"[WARN] [{ts()}] 非交易更新时段关闭天勤连接失败: {exc}", flush=True)
                api = None
            wait_seconds = seconds_until_next_window()
            log_line(f"当前不在数据更新时段，暂停抓取；距离下一次自动更新约 {wait_seconds // 60} 分钟。")
            time.sleep(min(wait_seconds, IDLE_SLEEP_SECONDS))
            continue

        if api is None:
            print(f"[{ts()}] 启动天勤官方直连通道...", flush=True)
            try:
                api = connect_api()
                print(f"[{ts()}] 天勤连接成功。", flush=True)
            except Exception as exc:
                print(f"[ERROR] [{ts()}] 天勤连接失败，60 秒后重试: {exc}", flush=True)
                print(traceback.format_exc(), flush=True)
                time.sleep(60)
                continue

        success_count, _ = fetch_all_data(api)
        if success_count == 0:
            try:
                api.close()
            except Exception as exc:
                print(f"[WARN] [{ts()}] 关闭天勤连接失败: {exc}", flush=True)
            api = None
            print(f"[WARN] [{ts()}] 本轮没有任何品种成功，已释放连接，60 秒后重连。", flush=True)
            time.sleep(60)
            continue

        print(f"[{ts()}] 数据泵已挂载，{POLL_INTERVAL_SECONDS // 60} 分钟后继续复用当前连接刷新。", flush=True)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    finally:
        # 避免异常时留下半写入的临时文件。
        for tmp in DATA_DIR.glob("*/*.tmp.*"):
            try:
                tmp.unlink()
            except OSError:
                pass
