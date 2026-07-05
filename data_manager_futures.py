from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Type

import pandas as pd


def _load_tq_sdk() -> tuple[Type[Any], Type[Any], str]:
    """Prefer official tqsdk 3.x; tqsdk2 may fail with 订阅合约信息失败 on some networks."""
    try:
        from tqsdk import TqApi, TqAuth
        import tqsdk as tq_mod

        return TqApi, TqAuth, f"tqsdk={getattr(tq_mod, '__version__', '?')}"
    except ImportError:
        from tqsdk2 import TqApi, TqAuth
        import tqsdk2 as tq_mod

        return TqApi, TqAuth, f"tqsdk2={getattr(tq_mod, '__version__', '?')}"


TqApi, TqAuth, TQ_SDK_FLAVOR = _load_tq_sdk()

try:
    from fengji_core.data import parse_tq_datetime_series, valid_futures_price_mask
except ImportError:
    parse_tq_datetime_series = None  # type: ignore[assignment,misc]
    valid_futures_price_mask = None  # type: ignore[assignment,misc]

# --- 天勤账号配置 ---
# 先兼容原有服务器运行方式；后续可以把账号密码放到系统环境变量。
TQ_PHONE = os.getenv("TQ_PHONE", "15323854134")
TQ_PASS = os.getenv("TQ_PASS", "Hwsgzjdqg1021")

# --- 目录配置 ---
DATA_DIR = Path(os.getenv("FUTURES_DATA_DIR", r"C:\Users\Administrator\quant_futures\data"))
LOG_DIR = Path(os.getenv("FUTURES_LOG_DIR", r"C:\Users\Administrator\quant_futures\runtime\logs"))
LOG_FILE = LOG_DIR / "data_manager_futures.log"
HEARTBEAT_FILE = LOG_DIR / "data_manager_heartbeat.txt"
STALE_CATCHUP_HOURS = int(os.getenv("FUTURES_STALE_CATCHUP_HOURS", "36"))
STALE_BAR_HOURS = int(os.getenv("FUTURES_STALE_BAR_HOURS", str(STALE_CATCHUP_HOURS)))
MAIN_CONTINUOUS_PREFIX = "KQ.m@"
MAIN_CONTRACT_MANIFEST = Path(
    os.getenv("FUTURES_MAIN_CONTRACT_MANIFEST", str(LOG_DIR / "futures_main_contract_sources.json"))
)
for d in ["1d", "1h", "15m", "5m"]:
    (DATA_DIR / d).mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

DATA_LENGTHS = {
    "1d": int(os.getenv("FUTURES_1D_LENGTH", "800")),
    "1h": int(os.getenv("FUTURES_1H_LENGTH", "2600")),
    # DS09 需要更长 M15：默认 12000 根（约 125 个交易日）；天勤上限不足时可调低 FUTURES_15M_LENGTH
    # GFEX LC 在 tqsdk2 下 data_length>8000 时 15m 曾出现脏数据，默认 8000；需更长可设 FUTURES_15M_LENGTH
    "15m": int(os.getenv("FUTURES_15M_LENGTH", "8000")),
    # 5m：默认 6000 根（约 50 交易日）；天勤上限不足时按 frame_looks_sane 降档
    "5m": int(os.getenv("FUTURES_5M_LENGTH", "6000")),
}
TIMEFRAMES = {
    "1d": 86400,
    "1h": 3600,
    "15m": 900,
    "5m": 300,
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


def is_main_continuous_code(tq_code: str) -> bool:
    return str(tq_code or "").startswith(MAIN_CONTINUOUS_PREFIX)


def validate_main_continuous_map(mapping: dict[str, str]) -> None:
    for short_code, tq_code in mapping.items():
        if not is_main_continuous_code(tq_code):
            raise ValueError(f"{short_code} 必须使用 KQ.m@ 主连发现码，当前为 {tq_code}")


def _load_manifest() -> dict:
    if MAIN_CONTRACT_MANIFEST.is_file():
        payload = json.loads(MAIN_CONTRACT_MANIFEST.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("mode", "tq_actual_main_contract")
            payload.setdefault("symbols", {})
            return payload
    return {"mode": "tq_actual_main_contract", "updated_at": ts(), "symbols": {}}


def _save_manifest(manifest: dict) -> None:
    MAIN_CONTRACT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    manifest["mode"] = "tq_actual_main_contract"
    manifest["updated_at"] = ts()
    MAIN_CONTRACT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def initialize_main_contract_manifest() -> None:
    manifest = _load_manifest()
    symbols = manifest.setdefault("symbols", {})
    for short_code, tq_code in TQ_SYMBOL_MAP.items():
        symbols.setdefault(
            short_code,
            {
                "tq_code": tq_code,
                "display_contract": tq_code,
                "data_contract": tq_code,
                "data_contract_is_actual": False,
                "underlying_symbol": "",
                "main_continuous": True,
                "timeframes": {},
            },
        )
    _save_manifest(manifest)


def write_main_contract_identity(
    short_code: str,
    tq_code: str,
    underlying_symbol: str,
    data_contract: str,
) -> None:
    manifest = _load_manifest()
    symbols = manifest.setdefault("symbols", {})
    entry = symbols.setdefault(
        short_code,
        {
            "tq_code": tq_code,
            "display_contract": data_contract,
            "data_contract": data_contract,
            "data_contract_is_actual": False,
            "underlying_symbol": "",
            "main_continuous": True,
            "timeframes": {},
        },
    )
    previous = str(entry.get("data_contract") or "").strip()
    if (
        previous
        and previous != data_contract
        and not previous.startswith(MAIN_CONTINUOUS_PREFIX)
        and data_contract
    ):
        entry["previous_data_contract"] = previous
        entry["contract_switched_at"] = ts()
    entry["tq_code"] = tq_code
    entry["underlying_symbol"] = underlying_symbol
    entry["data_contract"] = data_contract
    entry["display_contract"] = data_contract
    entry["data_contract_is_actual"] = bool(data_contract and not data_contract.startswith(MAIN_CONTINUOUS_PREFIX))
    entry["main_continuous"] = True
    _save_manifest(manifest)


def record_manifest_timeframe(
    short_code: str,
    timeframe: str,
    data_contract: str,
    source_symbols: list[str],
    row_count: int,
) -> None:
    manifest = _load_manifest()
    entry = manifest.setdefault("symbols", {}).setdefault(short_code, {"timeframes": {}})
    timeframes = entry.setdefault("timeframes", {})
    timeframes[timeframe] = {
        "data_contract": data_contract,
        "source_symbols": source_symbols,
        "rows": row_count,
        "updated_at": ts(),
    }
    _save_manifest(manifest)


def resolve_data_contract(api: Any, short_code: str, tq_code: str) -> tuple[str, str]:
    if not is_main_continuous_code(tq_code):
        raise ValueError(f"resolve_data_contract 仅接受 KQ.m@ 发现码，拒绝非 KQ.m@: {tq_code}")
    quote = api.get_quote(tq_code)
    api.wait_update(deadline=time.time() + 5)
    underlying = str(getattr(quote, "underlying_symbol", "") or "").strip()
    if not underlying:
        raise RuntimeError(f"[{short_code}] 无法解析 underlying_symbol，拒绝继续写入主连数据")
    if underlying.startswith(MAIN_CONTINUOUS_PREFIX):
        raise RuntimeError(f"[{short_code}] underlying_symbol 仍是主连，拒绝继续写入主连数据")
    return underlying, underlying


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


def write_heartbeat(note: str) -> None:
    try:
        HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_FILE.write_text(f"{ts()} pid={os.getpid()} {note}\n", encoding="utf-8")
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
    if parse_tq_datetime_series is not None:
        data["date"] = parse_tq_datetime_series(data["datetime"])
    else:
        numeric = pd.to_numeric(data["datetime"], errors="coerce")
        if numeric.notna().any() and float(numeric.max(skipna=True)) > 1e14:
            data["date"] = pd.to_datetime(numeric, unit="ns", errors="coerce")
        else:
            data["date"] = pd.to_datetime(data["datetime"], errors="coerce")

    for column in ("open", "high", "low", "close", "volume"):
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    now_cutoff = pd.Timestamp.now() + pd.Timedelta(days=1)
    mask = data["date"].notna() & (data["date"] <= now_cutoff) & (data["date"] >= pd.Timestamp("2020-01-01"))
    for column in ("open", "high", "low", "close"):
        if column not in data.columns:
            raise ValueError(f"天勤返回数据缺少 {column} 字段")
        mask &= data[column].notna()
    if valid_futures_price_mask is not None:
        mask &= valid_futures_price_mask(data)
    else:
        mask &= (data["open"] > 0) & (data["high"] > 0) & (data["low"] > 0) & (data["close"] > 0)
        mask &= data["high"] >= data[["open", "close", "low"]].max(axis=1)
        mask &= data["low"] <= data[["open", "close", "high"]].min(axis=1)
        ratio = data["high"] / data["low"]
        mask &= ratio.notna() & (ratio < 1.25)

    out = data.loc[mask].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    if "symbol" in frame.columns:
        out["symbol"] = frame.loc[mask, "symbol"].astype(str).values
    out = out.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    if out.empty:
        raise ValueError("天勤返回空数据")
    return out


def _min_sane_rows(frame_len: int) -> int:
    if frame_len <= 0:
        return 0
    if frame_len < 10:
        return frame_len
    return max(10, int(frame_len * 0.85))


def frame_looks_sane(frame: pd.DataFrame) -> bool:
    if frame.empty or "date" not in frame.columns:
        return False
    need = _min_sane_rows(len(frame))
    dates = pd.to_datetime(frame["date"], errors="coerce")
    recent = dates >= pd.Timestamp("2020-01-01")
    if recent.sum() < need:
        return False
    for column in ("open", "high", "low", "close"):
        if column not in frame.columns:
            return False
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().sum() < need:
            return False
    highs = pd.to_numeric(frame["high"], errors="coerce")
    lows = pd.to_numeric(frame["low"], errors="coerce")
    return bool((highs > lows).sum() >= need)


def frame_looks_acceptable(frame: pd.DataFrame, *, min_rows: int = 100) -> bool:
    """Relaxed sanity for actual-month contracts with shorter clean history."""
    if frame.empty or "date" not in frame.columns:
        return False
    row_count = len(frame)
    if row_count < 50:
        return False
    floor = min(min_rows, row_count)
    need = max(floor, int(row_count * 0.5))
    highs = pd.to_numeric(frame["high"], errors="coerce")
    lows = pd.to_numeric(frame["low"], errors="coerce")
    return bool((highs > lows).sum() >= need)


def _length_candidates(timeframe: str, target: int) -> list[int]:
    if timeframe == "1d":
        extras = (1200, 1000, 800, 600, 400, 300)
    elif timeframe == "15m":
        extras = (12000, 11000, 10000, 9500, 9000, 8500, 8000, 6000, 4000, 3000)
    elif timeframe == "5m":
        extras = (6000, 5000, 4000, 3000, 2000)
    else:
        return [target]
    ordered = [target, *extras]
    min_len = 300 if timeframe == "1d" else (2000 if timeframe == "5m" else 3000)
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


def fetch_frame(api: Any, tq_code: str, timeframe: str) -> pd.DataFrame:
    last_error: Exception | None = None
    seconds = TIMEFRAMES[timeframe]
    length = DATA_LENGTHS[timeframe]
    pick_longest = (
        (timeframe == "15m" and length > 8000)
        or (timeframe == "5m" and length > 4000)
        or (timeframe == "1d" and length > 800)
    )
    best: pd.DataFrame | None = None
    best_len = 0
    best_data_length = length
    best_acceptable: pd.DataFrame | None = None
    best_acceptable_len = 0
    min_acceptable = 100 if timeframe == "15m" else (100 if timeframe == "5m" else 50)

    for data_length in _length_candidates(timeframe, length):
        for attempt in range(1, MAX_FETCH_RETRIES + 1):
            try:
                frame = api.get_kline_serial(tq_code, seconds, data_length=data_length)
                normalized = normalize_frame(frame)
                if not frame_looks_sane(normalized):
                    log_line(f"[WARN] {tq_code} {timeframe} data_length={data_length} 校验未通过")
                    if frame_looks_acceptable(normalized, min_rows=min_acceptable):
                        row_count = len(normalized)
                        if row_count > best_acceptable_len:
                            best_acceptable = normalized
                            best_acceptable_len = row_count
                    else:
                        last_error = RuntimeError(
                            f"{tq_code} {timeframe} data_length={data_length} "
                            f"rows={len(normalized)} 严格/降级校验均未通过"
                        )
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
        stop_at = 8000 if timeframe == "15m" else (3000 if timeframe == "5m" else 400)
        if pick_longest and best is not None and data_length <= stop_at:
            break

    if best is not None:
        log_line(f"[INFO] {tq_code} {timeframe} 选用 data_length={best_data_length} rows={best_len}")
        return best
    if best_acceptable is not None:
        log_line(f"[WARN] {tq_code} {timeframe} 降级选用 rows={best_acceptable_len}（严格校验未通过）")
        return best_acceptable
    detail = last_error if last_error is not None else "all candidates failed sanity/acceptable checks"
    raise RuntimeError(f"{tq_code} {timeframe} 连续抓取失败: {detail}")


def fetch_symbol(api: Any, short_code: str, tq_code: str) -> bool:
    try:
        data_contract, underlying = resolve_data_contract(api, short_code, tq_code)
    except Exception as exc:
        log_line(f"[ERROR] [{short_code}] 解析实际主力失败: {exc}")
        return False

    write_main_contract_identity(short_code, tq_code, underlying, data_contract)
    ok = True
    rows: dict[str, int] = {}
    for timeframe in ["1d", "1h", "15m", "5m"]:
        try:
            frame = fetch_frame(api, data_contract, timeframe)
            if "symbol" not in frame.columns:
                frame["symbol"] = data_contract
            else:
                frame["symbol"] = data_contract
            primary = DATA_DIR / timeframe / f"{short_code}.csv"
            atomic_write_csv(frame, primary)
            legacy = DATA_DIR / timeframe / f"{short_code}USDT.csv"
            if legacy != primary:
                atomic_write_csv(frame, legacy)
            rows[timeframe] = len(frame)
            source_symbols = sorted({str(value) for value in frame["symbol"].astype(str) if str(value).strip()})
            record_manifest_timeframe(short_code, timeframe, data_contract, source_symbols, len(frame))
        except Exception as exc:
            ok = False
            log_line(f"[ERROR] 抓取 [{short_code}] {timeframe} 失败: {exc}")
    if ok:
        log_line(
            f"[OK] 成功抓取 [{short_code}] contract={data_contract} "
            f"1d={rows.get('1d', 0)} 1h={rows.get('1h', 0)} 15m={rows.get('15m', 0)} 5m={rows.get('5m', 0)}"
        )
    return ok


def connect_api() -> Any:
    last_error: Exception | None = None
    for attempt in range(1, MAX_CONNECT_RETRIES + 1):
        try:
            write_heartbeat(f"connect attempt={attempt}/{MAX_CONNECT_RETRIES} sdk={TQ_SDK_FLAVOR}")
            return TqApi(auth=TqAuth(TQ_PHONE, TQ_PASS))
        except Exception as exc:
            last_error = exc
            write_heartbeat(f"connect_retry attempt={attempt}/{MAX_CONNECT_RETRIES}")
            print(f"[WARN] [{ts()}] 天勤连接第 {attempt}/{MAX_CONNECT_RETRIES} 次失败: {exc}", flush=True)
            if attempt < MAX_CONNECT_RETRIES:
                time.sleep(CONNECT_RETRY_SLEEP_SECONDS)
    write_heartbeat("connect_failed")
    raise RuntimeError(f"天勤连接连续失败: {last_error}")


def latest_1d_bar_time(short_code: str) -> datetime | None:
    path = DATA_DIR / "1d" / f"{short_code}.csv"
    if not path.exists():
        path = DATA_DIR / "1d" / f"{short_code}USDT.csv"
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path)
    except Exception:
        return None
    if frame.empty:
        return None
    if "date" not in frame.columns:
        return None
    parsed = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if parsed.empty:
        return None
    return parsed.iloc[-1].to_pydatetime().replace(tzinfo=None)


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
        bar_time = latest_1d_bar_time(short_code)
        if bar_time is None:
            stale.append(short_code)
            continue
        if (now - bar_time).total_seconds() > STALE_BAR_HOURS * 3600:
            stale.append(short_code)
    if stale:
        log_line(
            f"[CATCHUP] 日线停更超过 {STALE_BAR_HOURS}h，需补抓: "
            f"{','.join(stale[:8])}{'...' if len(stale) > 8 else ''}"
        )
        return True
    return False


def fetch_all_data(api: Any) -> tuple[int, int]:
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
    write_heartbeat(f"fetch_done ok={success_count} fail={fail_count}")
    return success_count, fail_count


def main() -> None:
    api: Any | None = None
    initialize_main_contract_manifest()
    write_heartbeat(f"boot sdk={TQ_SDK_FLAVOR}")
    log_line(
        f"[tq_actual_main_contract] 数据泵启动 sdk={TQ_SDK_FLAVOR}，市场模式={MARKET_MODE}，"
        f"manifest={MAIN_CONTRACT_MANIFEST}，日志={LOG_FILE}"
    )
    while True:
        if not is_market_update_time() and not needs_stale_catchup():
            if api is not None:
                try:
                    api.close()
                except Exception as exc:
                    print(f"[WARN] [{ts()}] 非交易更新时段关闭天勤连接失败: {exc}", flush=True)
                api = None
            wait_seconds = seconds_until_next_window()
            write_heartbeat("idle")
            log_line(f"当前不在数据更新时段，暂停抓取；距离下一次自动更新约 {wait_seconds // 60} 分钟。")
            time.sleep(min(wait_seconds, IDLE_SLEEP_SECONDS))
            continue

        if api is None:
            print(f"[{ts()}] 启动天勤官方直连通道 ({TQ_SDK_FLAVOR})...", flush=True)
            try:
                api = connect_api()
                write_heartbeat("connected")
                print(f"[{ts()}] 天勤连接成功 ({TQ_SDK_FLAVOR})。", flush=True)
            except Exception as exc:
                print(f"[ERROR] [{ts()}] 天勤连接失败，60 秒后重试: {exc}", flush=True)
                print(traceback.format_exc(), flush=True)
                write_heartbeat("connect_retry")
                time.sleep(60)
                continue

        write_heartbeat("fetch_start")
        success_count, fail_count = fetch_all_data(api)
        if success_count == 0:
            try:
                api.close()
            except Exception as exc:
                print(f"[WARN] [{ts()}] 关闭天勤连接失败: {exc}", flush=True)
            api = None
            write_heartbeat("fetch_all_failed")
            print(f"[WARN] [{ts()}] 本轮没有任何品种成功，已释放连接，60 秒后重连。", flush=True)
            time.sleep(60)
            continue

        write_heartbeat(f"poll ok={success_count} fail={fail_count}")
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
