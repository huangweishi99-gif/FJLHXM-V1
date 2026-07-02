"""Build chart-bundle JSON for Web K-line (bars + OS overlay + trade markers)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from fengji_core.chart_line import build_hardened_segments, iso_date as _chart_iso_date
from fengji_core.data import add_atr, filter_valid_futures_ohlcv
from fengji_core.ds07 import attach_os_detail
from fengji_core.os_state_store import build_os_detail_frame_stateful
from fengji_core.constants import FENGJI_TOTAL_PATTERN_STRATEGIES
from backtest_ds01 import DS01BacktestConfig, run_ds01_backtest
from backtest_ds03 import DS03BacktestConfig, run_ds03_backtest
from backtest_ds05 import build_os_frame
from quant.data import load_ohlcv_for_engine
from quant.futures_specs import get_futures_spec
from unified_whitelist_engine import UnifiedConfig, infer_symbol, run_unified_symbol

ENGINE_VERSION = "0.1.0"

_BACKTEST_RUNNERS: dict[str, Any] = {}


def _register_runners() -> None:
    if _BACKTEST_RUNNERS:
        return
    _BACKTEST_RUNNERS["DS01"] = (DS01BacktestConfig, run_ds01_backtest)
    _BACKTEST_RUNNERS["DS03"] = (DS03BacktestConfig, run_ds03_backtest)


@dataclass(frozen=True)
class ChartBundleRequest:
    csv_path: Path
    strategy_id: str = "DS03"
    years: int = 3
    atr_window: int = 14
    gap: int = 3
    initial_cash: float = 100_000.0
    commission_rate: float = 0.0004
    futures_mode: bool = False
    os_state_dir: Path | None = None
    os_symbol: str = ""
    os_timeframe: str = "1d"
    os_tail_rows: int = 1095


def _iso_date(value: Any) -> str:
    return _chart_iso_date(value)


def _hardened_segments(
    engine: Any,
    source_df: pd.DataFrame,
    display_df: pd.DataFrame | None = None,
    os_row_df: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    return build_hardened_segments(engine, source_df, display_df, os_row_df, _iso_date)


def _load_chart_ohlcv(req: ChartBundleRequest) -> pd.DataFrame:
    """Load OHLCV for chart/OS; domestic futures rows are sanity-filtered before OS state."""
    raw = load_ohlcv_for_engine(req.csv_path, req.atr_window)
    if not req.futures_mode:
        return raw
    base = raw.drop(columns=["tr", "atr"], errors="ignore")
    cleaned = filter_valid_futures_ohlcv(base)
    if cleaned.empty:
        return raw
    return add_atr(cleaned.reset_index(drop=True), req.atr_window)


def _tail_by_years(df: pd.DataFrame, years: int) -> pd.DataFrame:
    if years <= 0 or df.empty:
        return df
    end = pd.to_datetime(df["date"]).max()
    start = end - pd.DateOffset(years=years)
    out = df[pd.to_datetime(df["date"]) >= start].copy()
    return out.reset_index(drop=True) if not out.empty else df


def _bars_from_os_frame(os_df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in os_df.iterrows():
        item: dict[str, Any] = {
            "t": _iso_date(row["date"]),
            "o": float(row["open"]),
            "h": float(row["high"]),
            "l": float(row["low"]),
            "c": float(row["close"]),
        }
        if "volume" in row and not pd.isna(row["volume"]):
            item["v"] = float(row["volume"])
        if "camp" in row and not pd.isna(row["camp"]):
            item["camp"] = int(row["camp"])
        rows.append(item)
    return rows


def _chart_state_symbol(req: ChartBundleRequest) -> str:
    raw = (req.os_symbol or req.csv_path.stem).strip().upper().replace("-", "").replace("_", "")
    if req.futures_mode:
        return raw.removesuffix("USDT")
    return raw if raw.endswith("USDT") else f"{raw}USDT"


def _chart_os_state_path(req: ChartBundleRequest) -> Path | None:
    if req.os_state_dir is None:
        return None
    symbol = _chart_state_symbol(req).replace("/", "_").replace("\\", "_")
    timeframe = str(req.os_timeframe or "1d").strip().lower()
    return Path(req.os_state_dir) / f"{symbol}_{timeframe}.json"


def _build_stateful_os_overlay(
    raw: pd.DataFrame,
    req: ChartBundleRequest,
) -> tuple[pd.DataFrame, Any, dict[str, Any]]:
    state_path = _chart_os_state_path(req)
    if state_path is None:
        raise ValueError("os_state_dir not configured")
    os_source = raw.copy()
    if req.os_tail_rows > 0 and len(os_source) > req.os_tail_rows:
        os_source = os_source.tail(req.os_tail_rows).reset_index(drop=True)
    before_mtime = state_path.stat().st_mtime if state_path.exists() else None
    os_df, engine = build_os_detail_frame_stateful(
        os_source,
        req.gap,
        state_path,
        attach_os_detail,
        record_hardened_by_bar=(str(req.os_timeframe).lower() == "1d"),
    )
    after_mtime = state_path.stat().st_mtime if state_path.exists() else None
    meta = {
        "used_os_state": True,
        "state_file": str(state_path),
        "state_symbol": _chart_state_symbol(req),
        "timeframe": str(req.os_timeframe or "1d").lower(),
        "tail_rows": int(req.os_tail_rows or 0),
        "state_updated": before_mtime != after_mtime,
        "last_date": _iso_date(os_df.iloc[-1]["date"]) if not os_df.empty else "",
        "camp": int(getattr(engine, "camp", 0) or 0),
        "camp_confirmed": int(getattr(engine, "camp_confirmed", 0) or 0),
        "hardened_count": len(getattr(engine, "hardened_nodes", []) or []),
    }
    return os_df, engine, meta


def _row_entry_price(row: pd.Series) -> float | None:
    for key in ("entry_price", "avg_entry_price"):
        value = row.get(key)
        if value is None or pd.isna(value):
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def _row_exit_price(row: pd.Series) -> float | None:
    for key in ("exit_price", "price"):
        value = row.get(key)
        if value is None or pd.isna(value):
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def _trade_markers(trades: pd.DataFrame) -> list[dict[str, Any]]:
    if trades is None or trades.empty:
        return []
    entry_col = "entry_date" if "entry_date" in trades.columns else "entry_time"
    exit_col = "exit_date" if "exit_date" in trades.columns else "exit_time"
    pnl_col = "net_pnl" if "net_pnl" in trades.columns else "net"
    trade_no_col = "trade_no" if "trade_no" in trades.columns else "portfolio_trade_no"
    markers: list[dict[str, Any]] = []
    for _, row in trades.iterrows():
        side = str(row.get("direction", row.get("side", "long")))
        if side in {"1", "-1"}:
            side = "long" if int(side) == 1 else "short"
        trade_no = int(row.get(trade_no_col, 0) or 0)
        strategy_id = str(row.get("strategy_id", ""))
        entry_val = row.get(entry_col)
        if pd.isna(entry_val):
            continue
        entry_marker: dict[str, Any] = {
            "t": _iso_date(entry_val),
            "kind": "entry",
            "side": side,
            "price": float(_row_entry_price(row) or 0.0),
            "trade_no": trade_no,
        }
        if strategy_id:
            entry_marker["strategy_id"] = strategy_id
        markers.append(entry_marker)
        exit_val = row.get(exit_col)
        if pd.isna(exit_val):
            continue
        exit_marker: dict[str, Any] = {
            "t": _iso_date(exit_val),
            "kind": "exit",
            "side": side,
            "price": float(_row_exit_price(row) or 0.0),
            "trade_no": trade_no,
        }
        if strategy_id:
            exit_marker["strategy_id"] = strategy_id
        if pnl_col in row and not pd.isna(row[pnl_col]):
            exit_marker["net_pnl"] = float(row[pnl_col])
        markers.append(exit_marker)
    return markers


def _normalize_trade_side(raw: Any) -> str:
    side = str(raw or "long").strip().lower()
    if side in {"1", "long", "buy"}:
        return "long"
    if side in {"-1", "short", "sell"}:
        return "short"
    return side or "long"


def _serialize_trades_for_web(
    trades: pd.DataFrame,
    *,
    strategy_id: str,
    symbol: str,
) -> list[dict[str, Any]]:
    """Web 回测页明细降级：PG 无样本时与 markers 同源。"""
    if trades is None or trades.empty:
        return []
    entry_col = "entry_date" if "entry_date" in trades.columns else "entry_time"
    exit_col = "exit_date" if "exit_date" in trades.columns else "exit_time"
    pnl_col = "net_pnl" if "net_pnl" in trades.columns else "net"
    trade_no_col = "trade_no" if "trade_no" in trades.columns else "portfolio_trade_no"
    out: list[dict[str, Any]] = []
    sym = symbol.strip().upper()
    sid = strategy_id.strip().upper()
    for _, row in trades.iterrows():
        trade_no = int(row.get(trade_no_col, 0) or 0)
        row_sid = str(row.get("strategy_id") or sid).upper()
        entry_val = row.get(entry_col)
        if pd.isna(entry_val):
            continue
        exit_val = row.get(exit_col)
        entry_px = _row_entry_price(row)
        exit_px = _row_exit_price(row)
        pnl = row.get(pnl_col)
        out.append(
            {
                "trade_id": f"live-{sym}-{row_sid}-{trade_no or len(out) + 1}",
                "trade_no": trade_no or len(out) + 1,
                "strategy_id": row_sid,
                "market": "",
                "symbol": sym,
                "entry_time": _iso_date(entry_val),
                "exit_time": _iso_date(exit_val) if not pd.isna(exit_val) else None,
                "side": _normalize_trade_side(row.get("direction", row.get("side", "long"))),
                "entry_price": entry_px,
                "exit_price": exit_px,
                "net_pnl": float(pnl) if pnl is not None and not pd.isna(pnl) else None,
                "signal_tier": "INSUFFICIENT_DATA",
                "bucket_count": 0,
                "bucket_win_rate_smoothed": None,
                "trade_source": "live_backtest",
            }
        )
    return out


def _metrics_from_backtest(initial_cash: float, trades: pd.DataFrame, equity: pd.DataFrame) -> dict[str, Any]:
    final_equity = float(equity["equity"].iloc[-1]) if equity is not None and not equity.empty else initial_cash
    total_return = final_equity / initial_cash - 1.0
    mdd = float(equity["drawdown"].min()) if equity is not None and not equity.empty and "drawdown" in equity.columns else 0.0
    wins = int((trades["net_pnl"] > 0).sum()) if trades is not None and not trades.empty else 0
    n = int(len(trades)) if trades is not None else 0
    return {
        "trades": n,
        "wins": wins,
        "win_rate": (wins / n) if n else 0.0,
        "total_return": total_return,
        "max_drawdown": mdd,
        "final_equity": final_equity,
        "bad_audits": 0,
    }


def _metrics_from_accepted(initial_cash: float, trades: pd.DataFrame, bad_audits: int) -> dict[str, Any]:
    pnl_col = "net" if "net" in trades.columns else "net_pnl"
    n = int(len(trades)) if trades is not None else 0
    wins = int((trades[pnl_col] > 0).sum()) if n and pnl_col in trades.columns else 0
    total_pnl = float(trades[pnl_col].fillna(0).sum()) if n and pnl_col in trades.columns else 0.0
    final_equity = initial_cash + total_pnl
    return {
        "trades": n,
        "wins": wins,
        "win_rate": (wins / n) if n else 0.0,
        "total_return": final_equity / initial_cash - 1.0,
        "max_drawdown": 0.0,
        "final_equity": final_equity,
        "bad_audits": bad_audits,
    }


def _run_single_strategy(window: pd.DataFrame, strategy_id: str, req: ChartBundleRequest) -> dict[str, Any]:
    cfg_cls, runner = _BACKTEST_RUNNERS[strategy_id]
    cfg_kwargs: dict[str, Any] = {
        "initial_cash": req.initial_cash,
        "commission_rate": req.commission_rate,
        "atr_window": req.atr_window,
        "gap": req.gap,
        "futures_mode": req.futures_mode,
    }
    if strategy_id == "DS01":
        cfg_kwargs["spec"] = get_futures_spec(req.csv_path) if req.futures_mode else None
        cfg = cfg_cls(**cfg_kwargs)
    else:
        cfg_kwargs["spec"] = get_futures_spec(req.csv_path) if req.futures_mode else None
        cfg = cfg_cls(**cfg_kwargs)
    return runner(window, cfg)


def _run_total_strategy(window: pd.DataFrame, req: ChartBundleRequest) -> dict[str, Any]:
    import tempfile

    symbol = infer_symbol(req.csv_path, req.csv_path.stem.upper().replace("-", ""))
    spec = get_futures_spec(req.csv_path) if req.futures_mode else None
    config = UnifiedConfig(
        initial_cash=req.initial_cash,
        commission_rate=req.commission_rate,
        atr_window=req.atr_window,
        gap=req.gap,
        futures_mode=req.futures_mode,
        spec=spec,
    )
    with tempfile.TemporaryDirectory(prefix="fengji_total_") as tmp:
        summary = run_unified_symbol(
            symbol,
            config,
            req.csv_path,
            None,
            None,
            list(FENGJI_TOTAL_PATTERN_STRATEGIES),
            tmp,
        )
        accepted = pd.read_csv(Path(tmp) / "accepted_trades.csv")
        bad_path = Path(tmp) / "strategy_bad_trades.csv"
        bad_count = summary.get("bad_audits", 0)
        if bad_path.exists():
            bad_df = pd.read_csv(bad_path)
            bad_count = len(bad_df)

    os_df, engine = build_os_frame(window, req.gap)
    closed = accepted.copy()
    if not closed.empty and "exit_time" in closed.columns:
        closed = closed[closed["exit_time"].notna()].copy()
    metrics = _metrics_from_accepted(req.initial_cash, closed, int(bad_count))
    return {
        "df": os_df,
        "engine": engine,
        "trades": closed,
        "bad_audits": int(bad_count),
        "metrics": metrics,
    }


def _equity_curve_points(
    equity: pd.DataFrame | None,
    trades: pd.DataFrame | None,
    initial_cash: float,
    os_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Daily equity or stepped curve from closed trades for Web 收益曲线。"""
    if equity is not None and not equity.empty and "equity" in equity.columns:
        date_col = "date" if "date" in equity.columns else None
        if date_col:
            return [
                {"t": _iso_date(row[date_col]), "v": float(row["equity"])}
                for _, row in equity.iterrows()
                if not pd.isna(row[date_col])
            ]

    points: list[dict[str, Any]] = []
    if os_df is not None and not os_df.empty:
        points.append({"t": _iso_date(os_df.iloc[0]["date"]), "v": initial_cash})

    if trades is not None and not trades.empty:
        pnl_col = "net" if "net" in trades.columns else "net_pnl"
        exit_col = "exit_time" if "exit_time" in trades.columns else "exit_date"
        if exit_col in trades.columns:
            sub = trades.dropna(subset=[exit_col]).copy()
            if not sub.empty:
                sub = sub.sort_values(exit_col)
                eq = initial_cash
                for _, row in sub.iterrows():
                    eq += float(row.get(pnl_col, 0) or 0)
                    points.append({"t": _iso_date(row[exit_col]), "v": eq})

    if len(points) <= 1 and os_df is not None and not os_df.empty:
        points.append({"t": _iso_date(os_df.iloc[-1]["date"]), "v": initial_cash})
    return points


def build_chart_bundle(req: ChartBundleRequest) -> dict[str, Any]:
    _register_runners()
    strategy_id = req.strategy_id.upper()
    raw = _load_chart_ohlcv(req)
    window = _tail_by_years(raw, req.years)
    os_overlay_meta: dict[str, Any] = {"used_os_state": False}

    if strategy_id == "TOTAL":
        total = _run_total_strategy(window, req)
        os_df = total["df"]
        engine = total["engine"]
        trades = total["trades"]
        metrics = total["metrics"]
        equity_df = None
    elif strategy_id in _BACKTEST_RUNNERS:
        result = _run_single_strategy(window, strategy_id, req)
        os_df = result["df"]
        engine = result["engine"]
        trades = result.get("trades", pd.DataFrame())
        equity_df = result.get("equity", pd.DataFrame())
        bad = result.get("bad_trades", pd.DataFrame())
        metrics = _metrics_from_backtest(req.initial_cash, trades, equity_df)
        metrics["bad_audits"] = int(len(bad)) if bad is not None else 0
    else:
        raise ValueError(f"chart-bundle not implemented for strategy_id={strategy_id}")

    if req.os_state_dir is not None:
        try:
            state_os_df, state_engine, os_overlay_meta = _build_stateful_os_overlay(raw, req)
            display_os_df = _tail_by_years(state_os_df, req.years)
            os_df = display_os_df
            engine = state_engine
            segment_source_df = state_os_df
        except Exception as exc:  # noqa: BLE001 - chart must remain available with explicit audit metadata.
            os_overlay_meta = {
                "used_os_state": False,
                "state_file": str(_chart_os_state_path(req) or ""),
                "error": f"{type(exc).__name__}: {exc}",
            }
            segment_source_df = os_df
    else:
        segment_source_df = os_df

    symbol = req.csv_path.stem.upper().replace("-", "")
    return {
        "symbol": symbol,
        "strategy_id": strategy_id,
        "years": req.years,
        "engine_version": ENGINE_VERSION,
        "os_state": os_overlay_meta,
        "metrics": metrics,
        "bars": _bars_from_os_frame(os_df),
        "hardened_segments": _hardened_segments(engine, segment_source_df, os_df, os_df),
        "markers": _trade_markers(trades),
        "trades": _serialize_trades_for_web(trades, strategy_id=strategy_id, symbol=symbol),
        "equity_curve": _equity_curve_points(equity_df, trades, req.initial_cash, os_df),
    }
