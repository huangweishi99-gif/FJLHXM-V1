"""定式开仓上下文聚合统计与信号强弱评分。"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from fengji_core.context_score import (  # noqa: F401  # 向后兼容：历史调用方仍从本模块导入
    ACTIONABLE_MIN_SAMPLES,
    BUCKET_PROFILES,
    BUCKET_SPECS,
    DEFAULT_Z,
    DEFAULT_BUCKET_PROFILE,
    DEFAULT_PRIOR,
    DEFAULT_PRIOR_STRENGTH,
    DEFAULT_SCORE_WEIGHTS,
    FUTURES_V2_BUCKET_PROFILE,
    MIN_BUCKET_SAMPLES,
    STRATEGY_EXTRA_BUCKETS,
    TIER_MEDIUM,
    TIER_STRONG,
    BucketProfile,
    benjamini_hochberg,
    bucket_atr_dist,
    bucket_p_value,
    bucket_profile_for_market,
    bucket_range_pos,
    bucketize_for_profile,
    bucketize_value,
    build_bucket_key,
    classify_tier,
    is_actionable,
    load_market_calibrations,
    market_calibration,
    score_bucket_row,
    smoothed_rate,
    wilson_lower_bound,
)
from fengji_core.context_snapshot import ENGINE_VERSION, build_snapshots
from fengji_core.ds07 import attach_os_detail
from fengji_core.os_engine import FengJiOSIdentityEngine
from fengji_core.os_state_store import find_data_file
from fengji_core.runtime_stop_updater import _normalize_ohlcv
from fengji_core.symbol_names import FUTURES_CN_NAMES

__all__ = [
    "MIN_BUCKET_SAMPLES",
    "DEFAULT_PRIOR",
    "DEFAULT_PRIOR_STRENGTH",
    "BUCKET_SPECS",
    "STRATEGY_EXTRA_BUCKETS",
    "TIER_STRONG",
    "TIER_MEDIUM",
    "DEFAULT_SCORE_WEIGHTS",
    "BucketProfile",
    "DEFAULT_BUCKET_PROFILE",
    "FUTURES_V2_BUCKET_PROFILE",
    "BUCKET_PROFILES",
    "load_market_calibrations",
    "market_calibration",
    "bucket_profile_for_market",
    "bucketize_for_profile",
    "bucket_atr_dist",
    "bucket_range_pos",
    "bucketize_value",
    "ACTIONABLE_MIN_SAMPLES",
    "DEFAULT_Z",
    "build_bucket_key",
    "smoothed_rate",
    "wilson_lower_bound",
    "benjamini_hochberg",
    "bucket_p_value",
    "is_actionable",
    "score_bucket_row",
    "aggregate_bucket_stats",
    "classify_tier",
    "score_snapshot",
]

def aggregate_bucket_stats(snapshots: pd.DataFrame) -> pd.DataFrame:
    """按 strategy × market × bucket_key 聚合 win_rate / avg_r / count。"""
    if snapshots.empty:
        return pd.DataFrame()

    work = snapshots.copy()
    work["bucket_key"] = work.apply(
        lambda r: build_bucket_key(r, str(r["strategy_id"]), str(r.get("market", ""))),
        axis=1,
    )
    work["is_win"] = work["net_pnl"].astype(float) > 0
    work["r_multiple"] = pd.to_numeric(work["r_multiple"], errors="coerce")

    grouped = (
        work.groupby(["strategy_id", "market", "bucket_key"], dropna=False)
        .agg(
            count=("trade_id", "size"),
            wins=("is_win", "sum"),
            avg_r=("r_multiple", "mean"),
            avg_net=("net_pnl", "mean"),
        )
        .reset_index()
    )
    grouped["win_rate"] = grouped["wins"] / grouped["count"]
    # 评分/分级走 context_score.score_bucket_row：离线与实时统计共用同一口径
    scored = [
        score_bucket_row(
            count=int(row["count"]),
            wins=float(row["wins"]),
            avg_r=0.0 if pd.isna(row["avg_r"]) else float(row["avg_r"]),
            market=str(row["market"]),
        )
        for _, row in grouped.iterrows()
    ]
    grouped["win_rate_smoothed"] = [item["win_rate_smoothed"] for item in scored]
    grouped["win_rate_ci_low"] = [item["win_rate_ci_low"] for item in scored]
    grouped["avg_r_smoothed"] = [item["avg_r_smoothed"] for item in scored]
    grouped["sample_confidence"] = [item["sample_confidence"] for item in scored]
    grouped["max_dd_penalty"] = 0.0  # V1 占位：后续按桶内权益曲线补
    grouped["signal_score"] = [item["signal_score"] for item in scored]
    grouped["signal_score_conservative"] = [item["signal_score_conservative"] for item in scored]
    grouped["signal_tier"] = [item["signal_tier"] for item in scored]
    # 是否足以支撑下单决策（样本 + 胜率下界双门槛），供离线挑桶与未来实时排序使用
    grouped["actionable"] = [is_actionable(item) for item in scored]
    return grouped


def score_snapshot(snapshot: dict[str, Any] | pd.Series, stats_df: pd.DataFrame) -> dict[str, Any]:
    """为新信号查表评分。"""
    strategy_id = str(snapshot.get("strategy_id", ""))
    bucket_key = build_bucket_key(snapshot, strategy_id, str(snapshot.get("market", "")))
    match = stats_df[
        (stats_df["strategy_id"] == strategy_id)
        & (stats_df["market"] == snapshot.get("market"))
        & (stats_df["bucket_key"] == bucket_key)
    ]
    if match.empty:
        return {
            "bucket_key": bucket_key,
            "signal_score": None,
            "signal_tier": "INSUFFICIENT_DATA",
            "bucket_count": 0,
            "bucket_win_rate_smoothed": None,
        }
    row = match.iloc[0]
    return {
        "bucket_key": bucket_key,
        "signal_score": float(row["signal_score"]),
        "signal_tier": str(row["signal_tier"]),
        "bucket_count": int(row["count"]),
        "bucket_win_rate_smoothed": float(row["win_rate_smoothed"]),
        "bucket_avg_r_smoothed": float(row["avg_r_smoothed"]),
    }


def _crypto_okx_symbol(symbol: str) -> str:
    base = symbol.strip().upper().replace("-", "")
    if base.endswith("USDT"):
        base = base[:-4]
    return f"{base}-USDT"


def _crypto_timeframe_token(timeframe: str) -> str:
    tf = timeframe.strip().lower()
    if tf in {"15m", "m15"}:
        return "15m"
    if tf in {"1h", "h1", "60m"}:
        return "1H"
    return "1D"


def infer_crypto_period_from_hint(source_hint: str | Path | None) -> str | None:
    """从回测结果路径推断 OKX 缓存周期，避免 context entry_idx 与 CSV 窗口错位。"""
    if source_hint is None:
        return None
    text = str(source_hint).replace("\\", "/").lower()
    if re.search(r"(^|[_/\-])1825d($|[_/\-])", text) or re.search(r"(^|[_/\-])5y($|[_/\-])", text):
        return "1825d"
    if re.search(r"(^|[_/\-])180d($|[_/\-])", text):
        return "180d"
    if "forward30" in text:
        # forward30 is the scoring/selection window in these result folders.
        # The underlying M15 backtest frame still uses the 180d cache, as shown
        # by entry_idx values above 16k in the existing ETH/SOL outputs.
        return "180d"
    if re.search(r"(^|[_/\-])30d($|[_/\-])", text):
        return "30d"
    if re.search(r"(^|[_/\-])365d($|[_/\-])", text):
        return "365d"
    return None


def _crypto_okx_dirs(data_dir: Path) -> list[Path]:
    dirs = [data_dir / "crypto_okx", data_dir]
    if data_dir.name.lower() != "data":
        dirs.append(data_dir.parent / "crypto_okx")
    out: list[Path] = []
    seen: set[Path] = set()
    for path in dirs:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            out.append(path)
    return out


def resolve_crypto_okx_csv(
    data_dir: Path,
    symbol: str,
    timeframe: str,
    *,
    source_hint: str | Path | None = None,
) -> Path | None:
    period = infer_crypto_period_from_hint(source_hint)
    if not period:
        return None
    name = f"{_crypto_okx_symbol(symbol)}_{_crypto_timeframe_token(timeframe)}_{period}.csv"
    for folder in _crypto_okx_dirs(data_dir):
        path = folder / name
        if path.exists():
            return path
    return None


def resolve_futures_csv(data_dir: Path, symbol: str, timeframe: str) -> Path | None:
    """Resolve domestic futures CSVs without crypto-style USDT normalization."""
    tf = timeframe.strip().lower()
    aliases = {
        "1d": ["1d", "d1", "day", "daily"],
        "d1": ["1d", "d1", "day", "daily"],
        "1h": ["1h", "h1", "60m", "60min"],
        "h1": ["1h", "h1", "60m", "60min"],
        "60m": ["1h", "h1", "60m", "60min"],
        "15m": ["15m", "m15", "15min"],
        "m15": ["15m", "m15", "15min"],
        "5m": ["5m", "m5", "5min"],
        "m5": ["5m", "m5", "5min"],
    }.get(tf, [tf])
    cn_to_code = {cn: code for code, cn in FUTURES_CN_NAMES.items()}
    seen_syms: set[str] = set()
    symbol_candidates: list[str] = []
    raw = symbol.strip()
    if raw:
        for cand in (raw.upper(), raw, cn_to_code.get(raw, "")):
            if cand and cand not in seen_syms:
                seen_syms.add(cand)
                symbol_candidates.append(cand)
    for sym in symbol_candidates:
        names = [
            f"{sym}.csv",
            f"{sym}_{tf}.csv",
            f"{sym}-{tf}.csv",
            f"{sym}_日线_5年.csv",
        ]
        for folder in [*aliases, ""]:
            root = data_dir / folder if folder else data_dir
            for name in names:
                path = root / name
                if path.exists():
                    return path
    return None


def _count_trades_in_os_range(trades: pd.DataFrame, os_len: int) -> int:
    if trades.empty or "entry_idx" not in trades.columns or os_len <= 0:
        return 0
    idx = pd.to_numeric(trades["entry_idx"], errors="coerce")
    return int(((idx >= 0) & (idx < os_len)).sum())


def resolve_futures_os_frame(
    data_dir: Path,
    symbol: str,
    *,
    gap: int,
    source_hint: str | Path | None,
    trades: pd.DataFrame,
    preferred_timeframe: str = "1d",
) -> tuple[pd.DataFrame, str]:
    """Pick futures OHLCV timeframe that maximizes in-range entry_idx coverage."""
    max_idx = 0
    if not trades.empty and "entry_idx" in trades.columns:
        max_idx = int(pd.to_numeric(trades["entry_idx"], errors="coerce").max())
    rel = str(source_hint or "").replace("\\", "/").lower()
    candidates: list[str] = []
    for tf in (preferred_timeframe, "15m", "1d", "1h"):
        if tf and tf not in candidates:
            candidates.append(tf)
    if max_idx > 400 or "15_5y" in rel or "15m" in rel:
        candidates = ["15m", "1d", "1h"] + [c for c in candidates if c not in {"15m", "1d", "1h"}]

    best_df: pd.DataFrame | None = None
    best_tf = preferred_timeframe or "1d"
    best_hits = -1
    last_error: Exception | None = None
    for tf in candidates:
        try:
            os_df = load_os_frame(data_dir, symbol, tf, gap=gap, market="FUTURES", source_hint=source_hint)
            hits = _count_trades_in_os_range(trades, len(os_df))
            if hits > best_hits:
                best_hits = hits
                best_df = os_df
                best_tf = tf
        except (FileNotFoundError, ValueError) as exc:
            last_error = exc
            continue
    if best_df is None:
        if last_error is not None:
            raise last_error
        raise FileNotFoundError(f"no futures OHLCV csv for {symbol} under {data_dir}")
    return best_df, best_tf


def resolve_data_csv(
    data_dir: Path,
    symbol: str,
    timeframe: str,
    market: str,
    *,
    source_hint: str | Path | None = None,
) -> Path:
    """按市场解析 OHLCV CSV 路径。"""
    market = market.upper()
    sym = symbol.strip().upper()
    if market == "A_STOCK":
        code = sym.zfill(6) if sym.isdigit() else sym
        for name in (f"{code}_1D_qfq.csv", f"{code}_1d_qfq.csv", f"{code}.csv"):
            path = data_dir / name
            if path.exists():
                return path
    if market == "US_STOCK":
        candidates = [sym]
        if source_hint:
            hint = Path(source_hint).name.split("_")[0].upper()
            if hint and hint not in candidates:
                candidates.insert(0, hint)
        for ticker in candidates:
            for name in (f"{ticker}_1D.csv", f"{ticker}_1d.csv", f"{ticker}.csv"):
                path = data_dir / name
                if path.exists():
                    return path
    if market == "CRYPTO":
        okx_path = resolve_crypto_okx_csv(data_dir, sym, timeframe, source_hint=source_hint)
        if okx_path is not None:
            return okx_path
        for folder in ("1d", "overseas_1d", timeframe):
            for name in (f"{sym}.csv", f"{sym.replace('USDT', '')}USDT.csv"):
                path = data_dir / folder / name
                if path.exists():
                    return path
    if market == "FUTURES":
        futures_path = resolve_futures_csv(data_dir, symbol, timeframe)
        if futures_path is not None:
            return futures_path
    path = find_data_file(data_dir, symbol, timeframe)
    if path.exists():
        return path
    raise FileNotFoundError(f"no OHLCV csv for {market} {symbol} under {data_dir}")


def load_os_frame(
    data_dir: Path,
    symbol: str,
    timeframe: str,
    gap: int = 3,
    market: str = "CRYPTO",
    *,
    source_hint: str | Path | None = None,
) -> pd.DataFrame:
    path = resolve_data_csv(data_dir, symbol, timeframe, market, source_hint=source_hint)
    raw = pd.read_csv(path)
    df = _normalize_ohlcv(raw)
    if df.empty:
        raise ValueError(f"empty OHLCV after normalize: {path}")
    engine = FengJiOSIdentityEngine(gap=gap, record_hardened_by_bar=False).run(df)
    return attach_os_detail(df, engine)


def build_from_result_dir(
    result_dir: Path,
    *,
    data_dir: Path,
    market: str,
    symbol: str,
    timeframe: str = "1d",
    gap: int = 3,
    engine_version: str = ENGINE_VERSION,
    source_hint: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """从回测结果目录读取 accepted_trades，生成 snapshots + bucket stats。"""
    accepted_path = result_dir / "accepted_trades.csv"
    bad_path = result_dir / "strategy_bad_trades.csv"
    if not accepted_path.exists():
        alt = result_dir / "stock_long_accepted_trades.csv"
        if alt.exists():
            accepted_path = alt
        else:
            raw = result_dir / "raw_fengji" / "accepted_trades.csv"
            if raw.exists():
                accepted_path = raw
                bad_path = result_dir / "raw_fengji" / "strategy_bad_trades.csv"
            else:
                raise FileNotFoundError(f"no accepted_trades in {result_dir}")

    trades = pd.read_csv(accepted_path)
    if trades.empty:
        return pd.DataFrame(), pd.DataFrame()

    if bad_path.exists():
        bad = pd.read_csv(bad_path)
        if not bad.empty and "trade_no" in trades.columns and "trade_no" in bad.columns:
            bad_nos = set(bad["trade_no"].astype(str))
            trades = trades[~trades["trade_no"].astype(str).isin(bad_nos)].copy()

    market_u = market.upper()
    if market_u == "FUTURES":
        os_df, timeframe = resolve_futures_os_frame(
            data_dir,
            symbol,
            gap=gap,
            source_hint=source_hint or result_dir,
            trades=trades,
            preferred_timeframe=timeframe,
        )
    else:
        os_df = load_os_frame(data_dir, symbol, timeframe, gap=gap, market=market, source_hint=source_hint)
    snapshots = build_snapshots(
        trades,
        os_df,
        market=market,
        symbol=symbol,
        timeframe=timeframe,
        engine_version=engine_version,
    )
    stats = aggregate_bucket_stats(snapshots)
    return snapshots, stats


def write_outputs(
    result_dir: Path,
    snapshots: pd.DataFrame,
    stats: pd.DataFrame,
) -> dict[str, Path]:
    result_dir.mkdir(parents=True, exist_ok=True)
    snap_path = result_dir / "trade_context_snapshots.csv"
    stats_path = result_dir / "context_bucket_stats.csv"
    meta_path = result_dir / "context_stats_meta.json"
    snapshots.to_csv(snap_path, index=False, encoding="utf-8-sig")
    stats.to_csv(stats_path, index=False, encoding="utf-8-sig")
    meta = {
        "snapshots": len(snapshots),
        "buckets": len(stats),
        "min_bucket_samples": MIN_BUCKET_SAMPLES,
        "engine_version": ENGINE_VERSION,
        "bucket_profile": bucket_profile_for_market(
            str(snapshots.iloc[0]["market"]) if not snapshots.empty and "market" in snapshots.columns else None
        ).name,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"snapshots": snap_path, "stats": stats_path, "meta": meta_path}


def build_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build trade context snapshots and bucket stats.")
    parser.add_argument("command", nargs="?", default="build", choices=["build"])
    parser.add_argument("--result-dir", required=True, help="Directory with accepted_trades.csv")
    parser.add_argument("--data-dir", default="data", help="OHLCV root directory")
    parser.add_argument("--market", default="CRYPTO", help="Market tag: CRYPTO | A_STOCK | FUTURES")
    parser.add_argument("--symbol", required=True, help="Symbol e.g. SOLUSDT or LC")
    parser.add_argument("--timeframe", default="1d", help="Primary timeframe for OS frame")
    parser.add_argument("--gap", type=int, default=3, help="OS gap parameter")
    args = parser.parse_args(argv)

    result_dir = Path(args.result_dir)
    snapshots, stats = build_from_result_dir(
        result_dir,
        data_dir=Path(args.data_dir),
        market=args.market.upper(),
        symbol=args.symbol.upper(),
        timeframe=args.timeframe,
        gap=args.gap,
    )
    paths = write_outputs(result_dir, snapshots, stats)
    print(json.dumps({k: str(v) for k, v in paths.items()}, ensure_ascii=False, indent=2))
    print(f"snapshots={len(snapshots)} buckets={len(stats)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build_cli())
