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

from fengji_core.context_snapshot import ENGINE_VERSION, build_snapshots
from fengji_core.ds07 import attach_os_detail
from fengji_core.os_engine import FengJiOSIdentityEngine
from fengji_core.os_state_store import find_data_file
from fengji_core.runtime_stop_updater import _normalize_ohlcv
from fengji_core.symbol_names import FUTURES_CN_NAMES

MIN_BUCKET_SAMPLES = 30
DEFAULT_PRIOR = 0.5
DEFAULT_PRIOR_STRENGTH = 10

# V1 分桶维度：枚举直接作键；连续字段按固定阈值切桶
BUCKET_SPECS: list[tuple[str, str]] = [
    ("camp", "enum"),
    ("camp_confirmed", "enum"),
    ("dist_active_high_atr", "atr_dist"),
    ("bar_direction", "enum"),
    ("position_in_range_20", "range_pos"),
    ("market_regime_vol", "enum"),
]

STRATEGY_EXTRA_BUCKETS: dict[str, list[str]] = {
    "DS03": ["peak_key"],
    "DS07": ["h1_merge_type"],
    "DS09": ["boundary_side"],
}

TIER_STRONG = 0.65
TIER_MEDIUM = 0.45
DEFAULT_SCORE_WEIGHTS = {"w_wr": 0.45, "w_r": 0.35, "w_conf": 0.20}


@dataclass(frozen=True)
class BucketProfile:
    name: str
    fields: tuple[tuple[str, str], ...]
    strategy_extras: dict[str, list[str]]
    atr_mode: str = "default"


DEFAULT_BUCKET_PROFILE = BucketProfile("v1", tuple(BUCKET_SPECS), STRATEGY_EXTRA_BUCKETS)

FUTURES_V2_BUCKET_PROFILE = BucketProfile(
    "futures_v2",
    (
        ("camp_confirmed", "enum"),
        ("dist_active_high_atr", "atr_dist"),
        ("bar_direction", "enum"),
    ),
    {"DS03": ["peak_key"]},
    atr_mode="coarse2",
)

BUCKET_PROFILES: dict[str, BucketProfile] = {
    "v1": DEFAULT_BUCKET_PROFILE,
    "futures_v2": FUTURES_V2_BUCKET_PROFILE,
}


def _default_market_calibration() -> dict[str, float | int | bool]:
    return {
        "activate": True,
        "tier_strong": TIER_STRONG,
        "tier_medium": TIER_MEDIUM,
        "min_bucket_samples": MIN_BUCKET_SAMPLES,
        **DEFAULT_SCORE_WEIGHTS,
    }


def _candidate_calibration_paths() -> list[Path]:
    paths: list[Path] = []
    env_path = os.getenv("FENGJI_CONTEXT_CALIBRATION")
    if env_path:
        paths.append(Path(env_path))
    cwd_path = Path.cwd() / "data" / "context_market_calibration.json"
    paths.append(cwd_path)
    for parent in Path(__file__).resolve().parents:
        paths.append(parent / "data" / "context_market_calibration.json")
    return paths


@lru_cache(maxsize=1)
def load_market_calibrations() -> dict[str, Any]:
    for path in _candidate_calibration_paths():
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid context market calibration json: {path}") from exc
    return {"default": _default_market_calibration(), "markets": {}}


def market_calibration(market: str | None) -> dict[str, float | int | bool | str]:
    raw = load_market_calibrations()
    default = _default_market_calibration()
    default.update(raw.get("default") or {})
    market_key = (market or "").upper()
    market_cfg = (raw.get("markets") or {}).get(market_key) or {}
    if market_cfg.get("activate") is False:
        return default
    cfg = {**default, **market_cfg}
    for key in ("w_wr", "w_r", "w_conf", "tier_strong", "tier_medium"):
        cfg[key] = float(cfg[key])
    cfg["min_bucket_samples"] = int(cfg["min_bucket_samples"])
    cfg["activate"] = bool(cfg.get("activate", True))
    if "bucket_profile" in market_cfg:
        cfg["bucket_profile"] = str(market_cfg["bucket_profile"])
    return cfg


def bucket_profile_for_market(market: str | None) -> BucketProfile:
    cfg = market_calibration(market)
    name = str(cfg.get("bucket_profile") or "v1")
    return BUCKET_PROFILES.get(name, DEFAULT_BUCKET_PROFILE)


def bucketize_for_profile(field: str, kind: str, value: Any, profile: BucketProfile) -> str:
    if field == "dist_active_high_atr" and profile.atr_mode == "coarse2":
        base = bucket_atr_dist(value)
        if base in ("NEAR", "MID"):
            return "NEAR_MID"
        if base == "FAR":
            return "FAR"
        return "UNKNOWN"
    return bucketize_value(field, kind, value)


def bucket_atr_dist(value: Any) -> str:
    val = float(value) if value is not None and not (isinstance(value, float) and np.isnan(value)) else float("nan")
    if np.isnan(val):
        return "UNKNOWN"
    if val <= 0.5:
        return "NEAR"
    if val <= 1.5:
        return "MID"
    return "FAR"


def bucket_range_pos(value: Any) -> str:
    val = float(value) if value is not None and not (isinstance(value, float) and np.isnan(value)) else float("nan")
    if np.isnan(val):
        return "UNKNOWN"
    if val <= 0.33:
        return "LOW"
    if val <= 0.66:
        return "MID"
    return "HIGH"


def bucketize_value(field: str, kind: str, value: Any) -> str:
    if kind == "enum":
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "UNKNOWN"
        return str(value)
    if kind == "atr_dist":
        return bucket_atr_dist(value)
    if kind == "range_pos":
        return bucket_range_pos(value)
    return str(value) if value is not None else "UNKNOWN"


def build_bucket_key(
    row: dict[str, Any] | pd.Series,
    strategy_id: str,
    market: str | None = None,
) -> str:
    market_key = str(market or row.get("market") or "").upper()
    profile = bucket_profile_for_market(market_key or None)
    parts = [str(strategy_id)]
    for field, kind in profile.fields:
        parts.append(f"{field}={bucketize_for_profile(field, kind, row.get(field), profile)}")
    for extra in profile.strategy_extras.get(strategy_id, []):
        val = row.get(extra)
        if val is not None and not (isinstance(val, float) and np.isnan(val)) and str(val).strip():
            parts.append(f"{extra}={val}")
    return "|".join(parts)


def smoothed_rate(successes: float, total: float, prior: float = DEFAULT_PRIOR, strength: float = DEFAULT_PRIOR_STRENGTH) -> float:
    if total <= 0:
        return prior
    return (successes + prior * strength) / (total + strength)


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
    grouped["win_rate_smoothed"] = grouped.apply(
        lambda r: smoothed_rate(float(r["wins"]), float(r["count"])),
        axis=1,
    )
    grouped["avg_r_smoothed"] = grouped["avg_r"].fillna(0.0)
    grouped["sample_confidence"] = grouped.apply(
        lambda r: min(1.0, float(r["count"]) / float(market_calibration(str(r["market"]))["min_bucket_samples"])),
        axis=1,
    )
    grouped["max_dd_penalty"] = 0.0  # V1 占位：后续按桶内权益曲线补
    grouped["signal_score"] = grouped.apply(
        lambda r: (
            market_calibration(str(r["market"]))["w_wr"] * float(r["win_rate_smoothed"])
            + market_calibration(str(r["market"]))["w_r"]
            * float(np.clip(r["avg_r_smoothed"], -1.0, 2.0))
            / 2.0
            + market_calibration(str(r["market"]))["w_conf"] * float(r["sample_confidence"])
        ),
        axis=1,
    ).clip(0.0, 1.0)
    grouped["signal_tier"] = grouped.apply(
        lambda r: classify_tier(float(r["signal_score"]), int(r["count"]), market=str(r["market"])),
        axis=1,
    )
    return grouped


def classify_tier(score: float, count: int, *, market: str | None = None) -> str:
    cfg = market_calibration(market)
    if count < int(cfg["min_bucket_samples"]):
        return "INSUFFICIENT_DATA"
    if score >= float(cfg["tier_strong"]):
        return "STRONG"
    if score >= float(cfg["tier_medium"]):
        return "MEDIUM"
    return "WEAK"


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
