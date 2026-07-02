from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from db.models import ContextBucketStat, TradeContextSnapshot
from db.session import get_engine
from fengji_core.context_stats import aggregate_bucket_stats, build_bucket_key, score_snapshot


def _parse_ts(value: Any):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(ts) else ts.to_pydatetime()


def _snapshot_row_to_model(row: pd.Series) -> TradeContextSnapshot:
    core_cols = {
        "trade_id",
        "setup_key",
        "strategy_id",
        "market",
        "symbol",
        "timeframe",
        "entry_time",
        "exit_time",
        "side",
        "entry_price",
        "initial_stop",
        "exit_reason",
        "net_pnl",
        "r_multiple",
        "holding_bars",
        "engine_version",
    }
    payload = row.to_dict()
    context = {k: (None if pd.isna(v) else v) for k, v in payload.items() if k not in core_cols}
    setup_raw = payload.get("setup_key")
    setup_key = None if pd.isna(setup_raw) or str(setup_raw).strip().lower() == "nan" else str(setup_raw).strip()
    return TradeContextSnapshot(
        trade_id=str(payload.get("trade_id", "")),
        setup_key=setup_key or None,
        strategy_id=str(payload.get("strategy_id", "")),
        market=str(payload.get("market", "")),
        symbol=str(payload.get("symbol", "")),
        timeframe=str(payload.get("timeframe", "1d")),
        entry_time=_parse_ts(payload.get("entry_time")),
        exit_time=_parse_ts(payload.get("exit_time")),
        side=int(payload["side"]) if pd.notna(payload.get("side")) else None,
        entry_price=float(payload["entry_price"]) if pd.notna(payload.get("entry_price")) else None,
        initial_stop=float(payload["initial_stop"]) if pd.notna(payload.get("initial_stop")) else None,
        exit_reason=str(payload.get("exit_reason", "") or "") or None,
        net_pnl=float(payload["net_pnl"]) if pd.notna(payload.get("net_pnl")) else None,
        r_multiple=float(payload["r_multiple"]) if pd.notna(payload.get("r_multiple")) else None,
        holding_bars=int(payload["holding_bars"]) if pd.notna(payload.get("holding_bars")) else None,
        engine_version=str(payload.get("engine_version", "") or "") or None,
        context_json=context,
    )


def import_snapshots_csv(result_dir: Path, *, replace: bool = True) -> int:
    """仅导入 trade_context_snapshots.csv（批量场景下 bucket 由 rebuild_global_bucket_stats 统一重算）。"""
    snap_path = result_dir / "trade_context_snapshots.csv"
    if not snap_path.exists():
        raise FileNotFoundError(f"missing trade_context_snapshots.csv in {result_dir}")

    try:
        snaps = pd.read_csv(snap_path)
    except EmptyDataError:
        return 0
    if snaps.empty:
        return 0

    engine = get_engine()
    snap_rows = 0
    with Session(engine) as session:
        if replace:
            trade_ids = snaps["trade_id"].astype(str).tolist()
            session.query(TradeContextSnapshot).filter(TradeContextSnapshot.trade_id.in_(trade_ids)).delete(
                synchronize_session=False
            )
        for _, row in snaps.iterrows():
            session.merge(_snapshot_row_to_model(row))
            snap_rows += 1
        session.commit()
    return snap_rows


def rebuild_global_bucket_stats(*, engine_version: str | None = None) -> dict[str, int]:
    """从 PG 全量 snapshots 重算 context_bucket_stats。"""
    engine = get_engine()
    with Session(engine) as session:
        rows = session.scalars(select(TradeContextSnapshot)).all()
        if not rows:
            session.query(ContextBucketStat).delete(synchronize_session=False)
            session.commit()
            return {"snapshots": 0, "buckets": 0}

        records: list[dict[str, Any]] = []
        for snap in rows:
            ctx = snap.context_json if isinstance(snap.context_json, dict) else json.loads(snap.context_json or "{}")
            records.append(
                {
                    "trade_id": snap.trade_id,
                    "strategy_id": snap.strategy_id,
                    "market": snap.market,
                    "symbol": snap.symbol,
                    "net_pnl": float(snap.net_pnl) if snap.net_pnl is not None else float("nan"),
                    "r_multiple": float(snap.r_multiple) if snap.r_multiple is not None else float("nan"),
                    **ctx,
                }
            )
        stats_df = aggregate_bucket_stats(pd.DataFrame(records))
        session.query(ContextBucketStat).delete(synchronize_session=False)
        stat_rows = 0
        for _, row in stats_df.iterrows():
            rec = ContextBucketStat(
                strategy_id=str(row["strategy_id"]),
                market=str(row["market"]),
                bucket_key=str(row["bucket_key"]),
                count=int(row["count"]),
                wins=int(row["wins"]),
                win_rate=float(row["win_rate"]) if pd.notna(row.get("win_rate")) else None,
                win_rate_smoothed=float(row["win_rate_smoothed"]) if pd.notna(row.get("win_rate_smoothed")) else None,
                avg_r=float(row["avg_r"]) if pd.notna(row.get("avg_r")) else None,
                avg_r_smoothed=float(row["avg_r_smoothed"]) if pd.notna(row.get("avg_r_smoothed")) else None,
                sample_confidence=float(row["sample_confidence"]) if pd.notna(row.get("sample_confidence")) else None,
                signal_score=float(row["signal_score"]) if pd.notna(row.get("signal_score")) else None,
                signal_tier=str(row.get("signal_tier", "") or "") or None,
                engine_version=engine_version or str(row.get("engine_version", "") or "") or None,
            )
            session.merge(rec)
            stat_rows += 1
        session.commit()
    return {"snapshots": len(records), "buckets": stat_rows}


def import_context_csvs(result_dir: Path, *, replace: bool = True) -> dict[str, int]:
    """将 trade_context_snapshots.csv / context_bucket_stats.csv 导入 PostgreSQL（单目录 dev 用）。"""
    snap_path = result_dir / "trade_context_snapshots.csv"
    stats_path = result_dir / "context_bucket_stats.csv"
    if not snap_path.exists() or not stats_path.exists():
        raise FileNotFoundError(f"missing context CSV in {result_dir}")

    snaps = pd.read_csv(snap_path)
    stats = pd.read_csv(stats_path)
    engine = get_engine()

    snap_rows = 0
    stat_rows = 0
    with Session(engine) as session:
        if replace and not snaps.empty:
            trade_ids = snaps["trade_id"].astype(str).tolist()
            session.query(TradeContextSnapshot).filter(TradeContextSnapshot.trade_id.in_(trade_ids)).delete(
                synchronize_session=False
            )
        for _, row in snaps.iterrows():
            session.merge(_snapshot_row_to_model(row))
            snap_rows += 1

        if replace and not stats.empty:
            pairs = stats[["strategy_id", "market"]].drop_duplicates()
            for _, pair in pairs.iterrows():
                session.query(ContextBucketStat).filter(
                    ContextBucketStat.strategy_id == str(pair["strategy_id"]),
                    ContextBucketStat.market == str(pair["market"]),
                ).delete(synchronize_session=False)
        for _, row in stats.iterrows():
            rec = ContextBucketStat(
                strategy_id=str(row["strategy_id"]),
                market=str(row["market"]),
                bucket_key=str(row["bucket_key"]),
                count=int(row["count"]),
                wins=int(row["wins"]),
                win_rate=float(row["win_rate"]) if pd.notna(row.get("win_rate")) else None,
                win_rate_smoothed=float(row["win_rate_smoothed"]) if pd.notna(row.get("win_rate_smoothed")) else None,
                avg_r=float(row["avg_r"]) if pd.notna(row.get("avg_r")) else None,
                avg_r_smoothed=float(row["avg_r_smoothed"]) if pd.notna(row.get("avg_r_smoothed")) else None,
                sample_confidence=float(row["sample_confidence"]) if pd.notna(row.get("sample_confidence")) else None,
                signal_score=float(row["signal_score"]) if pd.notna(row.get("signal_score")) else None,
                signal_tier=str(row.get("signal_tier", "") or "") or None,
                engine_version=str(row.get("engine_version", "") or "") or None,
            )
            session.merge(rec)
            stat_rows += 1
        session.commit()
    return {"snapshots": snap_rows, "buckets": stat_rows}


def _normalize_a_stock_symbol(sym: str) -> str:
    """A 股 symbol 在 PG 中可能缺前导零：统一去零后比较。"""
    return sym.strip().lstrip("0") or "0"


def _context_float(ctx: dict[str, Any], key: str) -> float | None:
    value = ctx.get(key)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _futures_symbol_aliases(sym: str) -> list[str]:
    """国内期货 PG symbol 使用品种名/简称，不追加 crypto 的 USDT 后缀。"""
    clean = sym.strip().upper().replace("-", "").replace("_", "")
    base = clean.removesuffix("USDT")
    aliases = [clean, base]
    return list(dict.fromkeys(a for a in aliases if a))


def list_trades_with_strength(
    *,
    symbol: str,
    market: str,
    strategy_id: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """回测/Web 明细：按品种列出成交及 bucket 标签、同类历史胜率。"""
    sym = symbol.strip().upper()
    mkt = market.strip().upper()

    with Session(get_engine()) as session:
        if mkt == "A_STOCK":
            # A 股符号在 PG 中可能缺前导零：同时匹配两种格式
            normalized = _normalize_a_stock_symbol(sym)
            stmt = select(TradeContextSnapshot).where(
                TradeContextSnapshot.market == "A_STOCK",
                TradeContextSnapshot.symbol.in_([sym, sym.zfill(6), sym.lstrip("0") or "0", normalized]),
            )
        elif mkt in {"FUTURES", "CN_FUTURES"}:
            stmt = select(TradeContextSnapshot).where(
                TradeContextSnapshot.market == "FUTURES",
                TradeContextSnapshot.symbol.in_(_futures_symbol_aliases(sym)),
            )
        else:
            stmt = select(TradeContextSnapshot).where(
                TradeContextSnapshot.symbol == sym,
                TradeContextSnapshot.market == mkt,
            )

        if strategy_id:
            stmt = stmt.where(TradeContextSnapshot.strategy_id == strategy_id.upper())
        stmt = stmt.order_by(TradeContextSnapshot.entry_time.desc().nullslast()).limit(limit)
        snaps = session.scalars(stmt).all()
        if not snaps:
            return []

        strategy_ids = {s.strategy_id for s in snaps}
        stats_by_strategy: dict[str, pd.DataFrame] = {}
        for sid in strategy_ids:
            rows = session.scalars(
                select(ContextBucketStat).where(
                    ContextBucketStat.strategy_id == sid,
                    ContextBucketStat.market == mkt,
                )
            ).all()
            stats_by_strategy[sid] = pd.DataFrame(
                [
                    {
                        "strategy_id": r.strategy_id,
                        "market": r.market,
                        "bucket_key": r.bucket_key,
                        "count": r.count,
                        "wins": r.wins,
                        "win_rate_smoothed": r.win_rate_smoothed,
                        "avg_r_smoothed": r.avg_r_smoothed,
                        "signal_score": r.signal_score,
                        "signal_tier": r.signal_tier,
                    }
                    for r in rows
                ]
            )

        out: list[dict[str, Any]] = []
        for snap in snaps:
            ctx = snap.context_json if isinstance(snap.context_json, dict) else json.loads(snap.context_json or "{}")
            row = {
                "trade_id": snap.trade_id,
                "strategy_id": snap.strategy_id,
                "market": snap.market,
                "symbol": snap.symbol,
                **ctx,
            }
            stats_df = stats_by_strategy.get(snap.strategy_id, pd.DataFrame())
            scored = score_snapshot(row, stats_df) if not stats_df.empty else {
                "bucket_key": build_bucket_key(row, snap.strategy_id, snap.market),
                "signal_score": None,
                "signal_tier": "INSUFFICIENT_DATA",
                "bucket_count": 0,
                "bucket_win_rate_smoothed": None,
            }
            out.append(
                {
                    "trade_id": snap.trade_id,
                    "strategy_id": snap.strategy_id,
                    "market": snap.market,
                    "symbol": snap.symbol,
                    "setup_key": snap.setup_key,
                    "entry_time": snap.entry_time.isoformat() if snap.entry_time else None,
                    "exit_time": snap.exit_time.isoformat() if snap.exit_time else None,
                    "side": snap.side,
                    "entry_price": (
                        float(snap.entry_price)
                        if snap.entry_price is not None
                        else _context_float(ctx, "avg_entry_price") or _context_float(ctx, "entry_price")
                    ),
                    "exit_price": _context_float(ctx, "exit_price"),
                    "net_pnl": float(snap.net_pnl) if snap.net_pnl is not None else None,
                    "r_multiple": float(snap.r_multiple) if snap.r_multiple is not None else None,
                    "exit_reason": snap.exit_reason,
                    **scored,
                }
            )
        return out


def list_context_symbol_summary(
    *,
    market: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """按市场列出已有上下文的品种样本概览，供 Web 快捷选择。"""
    mkt = market.strip().upper()
    stmt = (
        select(
            TradeContextSnapshot.symbol,
            func.count(TradeContextSnapshot.id).label("trade_count"),
            func.count(func.distinct(TradeContextSnapshot.strategy_id)).label("strategy_count"),
            func.min(TradeContextSnapshot.entry_time).label("first_entry_time"),
            func.max(TradeContextSnapshot.entry_time).label("last_entry_time"),
        )
        .where(TradeContextSnapshot.market == mkt)
        .group_by(TradeContextSnapshot.symbol)
        .order_by(desc("trade_count"), TradeContextSnapshot.symbol)
        .limit(limit)
    )
    with Session(get_engine()) as session:
        rows = session.execute(stmt).all()
        return [
            {
                "market": mkt,
                "symbol": row.symbol,
                "trade_count": int(row.trade_count or 0),
                "strategy_count": int(row.strategy_count or 0),
                "first_entry_time": row.first_entry_time.isoformat() if row.first_entry_time else None,
                "last_entry_time": row.last_entry_time.isoformat() if row.last_entry_time else None,
            }
            for row in rows
        ]


def get_signal_strength(trade_id: str) -> dict[str, Any] | None:
    with Session(get_engine()) as session:
        snap = session.scalar(select(TradeContextSnapshot).where(TradeContextSnapshot.trade_id == trade_id))
        if snap is None:
            return None
        context = snap.context_json if isinstance(snap.context_json, dict) else json.loads(snap.context_json or "{}")
        row = {
            "trade_id": snap.trade_id,
            "strategy_id": snap.strategy_id,
            "market": snap.market,
            "symbol": snap.symbol,
            **context,
        }
        stmt = select(ContextBucketStat).where(
            ContextBucketStat.strategy_id == snap.strategy_id,
            ContextBucketStat.market == snap.market,
        )
        stats_df = pd.DataFrame(
            [
                {
                    "strategy_id": r.strategy_id,
                    "market": r.market,
                    "bucket_key": r.bucket_key,
                    "count": r.count,
                    "wins": r.wins,
                    "win_rate_smoothed": r.win_rate_smoothed,
                    "avg_r_smoothed": r.avg_r_smoothed,
                    "signal_score": r.signal_score,
                    "signal_tier": r.signal_tier,
                }
                for r in session.scalars(stmt).all()
            ]
        )
        scored = score_snapshot(row, stats_df) if not stats_df.empty else {
            "bucket_key": build_bucket_key(row, snap.strategy_id, snap.market),
            "signal_score": None,
            "signal_tier": "INSUFFICIENT_DATA",
            "bucket_count": 0,
            "bucket_win_rate_smoothed": None,
        }
        return {
            "trade_id": snap.trade_id,
            "strategy_id": snap.strategy_id,
            "market": snap.market,
            "symbol": snap.symbol,
            "setup_key": snap.setup_key,
            "entry_time": snap.entry_time.isoformat() if snap.entry_time else None,
            "net_pnl": float(snap.net_pnl) if snap.net_pnl is not None else None,
            "r_multiple": float(snap.r_multiple) if snap.r_multiple is not None else None,
            **scored,
        }


def list_bucket_trades(
    *,
    strategy_id: str,
    market: str,
    bucket_key: str,
    symbol: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """反查同一 strategy/market/bucket_key 下的历史交易样本。"""
    sid = strategy_id.strip().upper()
    mkt = market.strip().upper()
    stmt = select(TradeContextSnapshot).where(
        TradeContextSnapshot.strategy_id == sid,
        TradeContextSnapshot.market == mkt,
    )
    if symbol:
        sym = symbol.strip().upper()
        if mkt == "A_STOCK":
            normalized = _normalize_a_stock_symbol(sym)
            stmt = stmt.where(
                TradeContextSnapshot.symbol.in_([sym, sym.zfill(6), sym.lstrip("0") or "0", normalized])
            )
        elif mkt in {"FUTURES", "CN_FUTURES"}:
            stmt = stmt.where(TradeContextSnapshot.symbol.in_(_futures_symbol_aliases(sym)))
        else:
            stmt = stmt.where(TradeContextSnapshot.symbol == sym)
    stmt = stmt.order_by(TradeContextSnapshot.entry_time.desc().nullslast())

    with Session(get_engine()) as session:
        stats_rows = session.scalars(
            select(ContextBucketStat).where(
                ContextBucketStat.strategy_id == sid,
                ContextBucketStat.market == mkt,
            )
        ).all()
        stats_df = pd.DataFrame(
            [
                {
                    "strategy_id": r.strategy_id,
                    "market": r.market,
                    "bucket_key": r.bucket_key,
                    "count": r.count,
                    "wins": r.wins,
                    "win_rate_smoothed": r.win_rate_smoothed,
                    "avg_r_smoothed": r.avg_r_smoothed,
                    "signal_score": r.signal_score,
                    "signal_tier": r.signal_tier,
                }
                for r in stats_rows
            ]
        )
        out: list[dict[str, Any]] = []
        for snap in session.scalars(stmt).all():
            ctx = snap.context_json if isinstance(snap.context_json, dict) else json.loads(snap.context_json or "{}")
            row = {
                "trade_id": snap.trade_id,
                "strategy_id": snap.strategy_id,
                "market": snap.market,
                "symbol": snap.symbol,
                **ctx,
            }
            scored = score_snapshot(row, stats_df) if not stats_df.empty else {
                "bucket_key": build_bucket_key(row, snap.strategy_id, snap.market),
                "signal_score": None,
                "signal_tier": "INSUFFICIENT_DATA",
                "bucket_count": 0,
                "bucket_win_rate_smoothed": None,
            }
            if scored.get("bucket_key") != bucket_key:
                continue
            out.append(
                {
                    "trade_id": snap.trade_id,
                    "strategy_id": snap.strategy_id,
                    "market": snap.market,
                    "symbol": snap.symbol,
                    "entry_time": snap.entry_time.isoformat() if snap.entry_time else None,
                    "exit_time": snap.exit_time.isoformat() if snap.exit_time else None,
                    "side": snap.side,
                    "entry_price": (
                        float(snap.entry_price)
                        if snap.entry_price is not None
                        else _context_float(ctx, "avg_entry_price") or _context_float(ctx, "entry_price")
                    ),
                    "exit_price": _context_float(ctx, "exit_price"),
                    "net_pnl": float(snap.net_pnl) if snap.net_pnl is not None else None,
                    "r_multiple": float(snap.r_multiple) if snap.r_multiple is not None else None,
                    "exit_reason": snap.exit_reason,
                    **scored,
                }
            )
            if len(out) >= limit:
                break
        return out


def list_bucket_stats(
    strategy_id: str,
    market: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(ContextBucketStat).where(ContextBucketStat.strategy_id == strategy_id.upper())
    if market:
        stmt = stmt.where(ContextBucketStat.market == market.upper())
    stmt = stmt.order_by(ContextBucketStat.signal_score.desc().nullslast()).limit(limit)
    with Session(get_engine()) as session:
        rows = session.scalars(stmt).all()
        return [
            {
                "strategy_id": r.strategy_id,
                "market": r.market,
                "bucket_key": r.bucket_key,
                "count": r.count,
                "win_rate_smoothed": float(r.win_rate_smoothed) if r.win_rate_smoothed is not None else None,
                "avg_r_smoothed": float(r.avg_r_smoothed) if r.avg_r_smoothed is not None else None,
                "signal_score": float(r.signal_score) if r.signal_score is not None else None,
                "signal_tier": r.signal_tier,
            }
            for r in rows
        ]


def _camp_from_os_camp(os_camp: str) -> tuple[int | None, int | None]:
    text = str(os_camp or "").strip().lower()
    if text == "red":
        return 1, 1
    if text == "blue":
        return 0, 0
    return None, None


def radar_row_to_score_input(row: dict[str, Any]) -> dict[str, Any]:
    """将 radar 行映射为 score_snapshot 所需的最小 L1 字段（只读查表）。"""
    strategy_id = str(row.get("strategy_id") or "").strip().upper()
    symbol = str(row.get("symbol") or "").strip().upper()
    market = str(row.get("market") or "").strip().upper()
    if not market:
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        try:
            from fengji_core.symbol_names import FUTURES_CN_NAMES

            if base in FUTURES_CN_NAMES:
                market = "FUTURES"
            elif symbol.endswith("USDT"):
                market = "CRYPTO"
            else:
                market = "FUTURES"
        except Exception:
            if symbol.isdigit() or (len(symbol) == 6 and symbol.isdigit()):
                market = "A_STOCK"
            elif symbol.endswith("USDT"):
                market = "CRYPTO"
            else:
                market = "FUTURES"
    camp, camp_confirmed = _camp_from_os_camp(str(row.get("os_camp") or ""))
    out: dict[str, Any] = {
        "strategy_id": strategy_id,
        "market": market,
        "symbol": symbol,
    }
    if camp is not None:
        out["camp"] = camp
        out["camp_confirmed"] = camp_confirmed
    setup_key = str(row.get("setup_key") or "").strip()
    if setup_key and "|" in setup_key:
        parts = [p.strip() for p in setup_key.split("|") if p.strip()]
        if strategy_id == "DS03" and len(parts) >= 2:
            out["peak_key"] = parts[-1]
    return out


def _stats_df_for_pairs(session: Session, pairs: set[tuple[str, str]]) -> dict[tuple[str, str], pd.DataFrame]:
    cache: dict[tuple[str, str], pd.DataFrame] = {}
    for strategy_id, market in pairs:
        rows = session.scalars(
            select(ContextBucketStat).where(
                ContextBucketStat.strategy_id == strategy_id,
                ContextBucketStat.market == market,
            )
        ).all()
        cache[(strategy_id, market)] = pd.DataFrame(
            [
                {
                    "strategy_id": r.strategy_id,
                    "market": r.market,
                    "bucket_key": r.bucket_key,
                    "count": r.count,
                    "wins": r.wins,
                    "win_rate_smoothed": r.win_rate_smoothed,
                    "avg_r_smoothed": r.avg_r_smoothed,
                    "signal_score": r.signal_score,
                    "signal_tier": r.signal_tier,
                }
                for r in rows
            ]
        )
    return cache


def attach_radar_signal_tiers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """为 radar 行附加只读 signal_tier；不修改 radar 生成或挂单逻辑。"""
    if not rows:
        return []
    pairs: set[tuple[str, str]] = set()
    score_inputs: list[dict[str, Any]] = []
    for row in rows:
        snap = radar_row_to_score_input(row)
        sid = str(snap.get("strategy_id") or "").upper()
        mkt = str(snap.get("market") or "").upper()
        if sid and mkt:
            pairs.add((sid, mkt))
        score_inputs.append(snap)

    with Session(get_engine()) as session:
        stats_cache = _stats_df_for_pairs(session, pairs)

    out: list[dict[str, Any]] = []
    for row, snap in zip(rows, score_inputs):
        sid = str(snap.get("strategy_id") or "").upper()
        mkt = str(snap.get("market") or "").upper()
        stats_df = stats_cache.get((sid, mkt), pd.DataFrame())
        scored = (
            score_snapshot(snap, stats_df)
            if not stats_df.empty
            else {
                "bucket_key": build_bucket_key(snap, sid, snap.market),
                "signal_score": None,
                "signal_tier": "INSUFFICIENT_DATA",
                "bucket_count": 0,
                "bucket_win_rate_smoothed": None,
            }
        )
        enriched = dict(row)
        enriched["signal_tier"] = scored.get("signal_tier")
        enriched["signal_score"] = scored.get("signal_score")
        enriched["bucket_key"] = scored.get("bucket_key")
        enriched["bucket_count"] = scored.get("bucket_count")
        enriched["bucket_win_rate_smoothed"] = scored.get("bucket_win_rate_smoothed")
        enriched["tier_mode"] = "read_only_bucket_lookup"
        out.append(enriched)
    return out
