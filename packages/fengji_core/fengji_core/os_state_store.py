"""峰极 OS 状态库（数据股）：规则固化在 JSON，增量只吃新走出来的 K 线。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from fengji_core.os_engine import FengJiOSIdentityEngine


def market_mode() -> str:
    return os.getenv("FENGJI_MARKET", "crypto").strip().lower()


def is_futures_market() -> bool:
    return market_mode() in {"futures", "future", "domestic", "cn_futures"}


def market_symbol(symbol: str) -> str:
    """数据文件名用简称：期货 LC；加密 LCUSDT。"""
    text = str(symbol).strip().upper().replace("-", "").replace("_", "")
    if is_futures_market():
        return text.removesuffix("USDT")
    return text if text.endswith("USDT") else f"{text}USDT"


def normalize_symbol(symbol: str) -> str:
    """挂单/账本符号：期货也保留 USDT 后缀以兼容现有 state。"""
    text = str(symbol).strip().upper().replace("-", "").replace("_", "")
    return text if text.endswith("USDT") else f"{text}USDT"


def date_key(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return str(value)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def row_fingerprint(row: pd.Series) -> str:
    parts = []
    for column in ["date", "open", "high", "low", "close", "volume"]:
        value = row.get(column, "")
        parts.append(date_key(value) if column == "date" else f"{float(value):.12g}")
    return "|".join(parts)


def os_state_path(state_dir: str | Path, symbol: str, timeframe: str) -> Path:
    code = market_symbol(symbol).replace("/", "_").replace("\\", "_")
    return Path(state_dir) / f"{code}_{timeframe}.json"


def read_os_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def state_matches_frame(
    state: dict[str, Any] | None,
    df: pd.DataFrame,
    gap: int,
    record_hardened_by_bar: bool,
) -> bool:
    if not state or df.empty:
        return False
    processed_len = int(state.get("processed_len", 0) or 0)
    if int(state.get("gap", gap)) != int(gap):
        return False
    if bool(state.get("record_hardened_by_bar", True)) != bool(record_hardened_by_bar):
        return False
    if processed_len <= 0 or processed_len > len(df):
        return False
    if state.get("first_date") != date_key(df.iloc[0]["date"]):
        return False
    last_row = df.iloc[processed_len - 1]
    if state.get("last_date") != date_key(last_row["date"]):
        return False
    if state.get("last_row_fingerprint") != row_fingerprint(last_row):
        return False
    return True


def write_os_state(
    path: Path,
    engine: FengJiOSIdentityEngine,
    df: pd.DataFrame,
    *,
    include_hardened_by_bar: bool,
) -> None:
    if df.empty:
        return
    state = engine.to_state(include_hardened_by_bar=include_hardened_by_bar)
    state.update(
        {
            "first_date": date_key(df.iloc[0]["date"]),
            "last_date": date_key(df.iloc[-1]["date"]),
            "last_row_fingerprint": row_fingerprint(df.iloc[-1]),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, default=str), encoding="utf-8")
    temp_path.replace(path)


def build_os_detail_frame_stateful(
    df: pd.DataFrame,
    gap: int,
    state_path: Path | None,
    attach_os_detail,
    *,
    record_hardened_by_bar: bool = True,
) -> tuple[pd.DataFrame, FengJiOSIdentityEngine]:
    """增量 OS：状态匹配则 run_from_state 只处理新 K；否则全量重算并落盘。"""
    state = read_os_state(state_path) if state_path is not None else None
    if not state_matches_frame(state, df, gap, record_hardened_by_bar):
        state = None
    engine = FengJiOSIdentityEngine(gap=gap, record_hardened_by_bar=record_hardened_by_bar).run_from_state(df, state)
    if state_path is not None:
        write_os_state(state_path, engine, df, include_hardened_by_bar=record_hardened_by_bar)
    return attach_os_detail(df, engine), engine


def find_data_file(data_dir: Path, symbol: str, timeframe: str) -> Path:
    names = [market_symbol(symbol)]
    crypto = normalize_symbol(symbol)
    if crypto not in names:
        names.append(crypto)
    aliases = {
        "1d": ["d1", "day", "daily"],
        "1h": ["h1", "60m", "60min"],
        "15m": ["m15", "15min"],
    }.get(timeframe, [])
    for folder in [timeframe, *aliases]:
        for name in names:
            for suffix in [f"{name}.csv", f"{name}_{timeframe}.csv", f"{name}-{timeframe}.csv"]:
                path = data_dir / folder / suffix
                if path.exists():
                    return path
    return data_dir / timeframe / f"{names[0]}.csv"
