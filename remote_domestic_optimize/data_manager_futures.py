from __future__ import annotations

import os
import time
import traceback
from pathlib import Path

import pandas as pd
import schedule
from tqsdk2 import TqApi, TqAuth

# --- 天勤账号配置 ---
# 先兼容原有服务器运行方式；后续可以把账号密码放到系统环境变量。
TQ_PHONE = os.getenv("TQ_PHONE", "15323854134")
TQ_PASS = os.getenv("TQ_PASS", "Hwsgzjdqg1021")

# --- 目录配置 ---
DATA_DIR = Path(r"C:\Users\Administrator\quant_futures\data")
for d in ["1d", "1h", "15m"]:
    (DATA_DIR / d).mkdir(parents=True, exist_ok=True)

DATA_LENGTHS = {
    "1d": 800,
    "1h": 2600,
    "15m": 3000,
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


def atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False, encoding="utf-8")
    os.replace(str(tmp), str(path))


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    if "datetime" not in data.columns:
        raise ValueError("天勤返回数据缺少 datetime 字段")
    data["date"] = pd.to_datetime(data["datetime"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    data = data.dropna(subset=["date"]).reset_index(drop=True)
    if data.empty:
        raise ValueError("天勤返回空数据")
    return data


def fetch_frame(api: TqApi, tq_code: str, timeframe: str) -> pd.DataFrame:
    last_error: Exception | None = None
    seconds = TIMEFRAMES[timeframe]
    length = DATA_LENGTHS[timeframe]
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            frame = api.get_kline_serial(tq_code, seconds, data_length=length)
            return normalize_frame(frame)
        except Exception as exc:
            last_error = exc
            print(f"⚠️ [{ts()}] {tq_code} {timeframe} 第 {attempt}/{MAX_FETCH_RETRIES} 次抓取失败: {exc}", flush=True)
            if attempt < MAX_FETCH_RETRIES:
                time.sleep(RETRY_SLEEP_SECONDS)
    raise RuntimeError(f"{tq_code} {timeframe} 连续抓取失败: {last_error}")


def fetch_symbol(api: TqApi, short_code: str, tq_code: str) -> bool:
    ok = True
    rows: dict[str, int] = {}
    for timeframe in ["1d", "1h", "15m"]:
        try:
            frame = fetch_frame(api, tq_code, timeframe)
            atomic_write_csv(frame, DATA_DIR / timeframe / f"{short_code}USDT.csv")
            rows[timeframe] = len(frame)
        except Exception as exc:
            ok = False
            print(f"❌ [{ts()}] 抓取 [{short_code}] {timeframe} 失败: {exc}", flush=True)
    if ok:
        print(
            f"✅ [{ts()}] 成功抓取 [{short_code}] "
            f"1d={rows.get('1d', 0)} 1h={rows.get('1h', 0)} 15m={rows.get('15m', 0)}",
            flush=True,
        )
    return ok


def connect_api() -> TqApi:
    last_error: Exception | None = None
    for attempt in range(1, MAX_CONNECT_RETRIES + 1):
        try:
            return TqApi(auth=TqAuth(TQ_PHONE, TQ_PASS))
        except Exception as exc:
            last_error = exc
            print(f"⚠️ [{ts()}] 天勤连接第 {attempt}/{MAX_CONNECT_RETRIES} 次失败: {exc}", flush=True)
            if attempt < MAX_CONNECT_RETRIES:
                time.sleep(CONNECT_RETRY_SLEEP_SECONDS)
    raise RuntimeError(f"天勤连接连续失败: {last_error}")


def fetch_all_data() -> None:
    print(f"[{ts()}] 🚨 启动天勤官方直连通道...", flush=True)
    api: TqApi | None = None
    success_count = 0
    fail_count = 0
    try:
        api = connect_api()
        for short_code, tq_code in TQ_SYMBOL_MAP.items():
            if fetch_symbol(api, short_code, tq_code):
                success_count += 1
            else:
                fail_count += 1
        print(
            f"[{ts()}] 🎉 本轮天勤数据更新完毕：成功 {success_count}，失败 {fail_count}。等待下一次轮询...\n",
            flush=True,
        )
    except Exception as exc:
        print(f"🚨 [{ts()}] 天勤连接严重异常: {exc}", flush=True)
        print(traceback.format_exc(), flush=True)
    finally:
        if api is not None:
            try:
                api.close()
            except Exception as exc:
                print(f"⚠️ [{ts()}] 关闭天勤连接失败: {exc}", flush=True)


# 程序启动时立即执行一次
fetch_all_data()

# 挂载定时器：每 5 分钟执行一次
schedule.every(5).minutes.do(fetch_all_data)

print("⏳ [天勤直连版] 数据泵已挂载！每 5 分钟自动刷新一次。请最小化此窗口...", flush=True)
while True:
    schedule.run_pending()
    time.sleep(1)
