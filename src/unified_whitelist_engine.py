from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from backtest_ds01 import DS01BacktestConfig, run_ds01_backtest
from backtest_ds02 import DS02BacktestConfig, run_ds02_backtest
from backtest_ds03 import DS03BacktestConfig, run_ds03_backtest
from backtest_ds04 import DS04BacktestConfig, run_ds04_backtest
from backtest_ds05 import DS05BacktestConfig, run_ds05_backtest
from backtest_ds06 import DS06BacktestConfig, run_ds06_backtest
from backtest_ds07 import DS07BacktestConfig, load_frame, run_ds07_backtest
from backtest_ds08 import DS08BacktestConfig, run_ds08_backtest
from backtest_ds09 import DS09BacktestConfig, load_m15_frame, run_ds09_backtest
try:
    from fengji_core.constants import DEFAULT_STRATEGIES_CSV, FENGJI_TOTAL_PATTERN_STRATEGIES, STRATEGY_PRIORITY
except ModuleNotFoundError:
    FENGJI_TOTAL_PATTERN_STRATEGIES = ["DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08", "DS09"]
    DEFAULT_STRATEGIES_CSV = ",".join(FENGJI_TOTAL_PATTERN_STRATEGIES)
    STRATEGY_PRIORITY = {strategy: (idx + 1) * 10 for idx, strategy in enumerate(FENGJI_TOTAL_PATTERN_STRATEGIES)}
from quant.data import load_ohlcv_for_engine
from quant.futures_specs import FuturesSpec, get_futures_spec


@dataclass(frozen=True)
class UnifiedConfig:
    initial_cash: float = 100_000.0
    lots: int = 1
    commission_rate: float = 0.0001
    slippage_ticks: float = 1.0
    atr_window: int = 14
    gap: int = 3
    max_same_direction_entries: int = 3
    futures_mode: bool = True
    spec: FuturesSpec | None = None


def _base_config_kwargs(config: UnifiedConfig) -> dict:
    return {
        "initial_cash": config.initial_cash,
        "lots": config.lots,
        "commission_rate": config.commission_rate,
        "slippage_ticks": config.slippage_ticks,
        "atr_window": config.atr_window,
        "gap": config.gap,
        "futures_mode": config.futures_mode,
        "spec": config.spec,
    }


def _direction_to_side(value) -> int:
    if value in {1, "1", "long", "LONG"}:
        return 1
    if value in {-1, "-1", "short", "SHORT"}:
        return -1
    raise ValueError(f"Unknown direction/side: {value}")


def _first_existing(row: pd.Series, names: list[str], default=None):
    for name in names:
        if name in row and not pd.isna(row[name]):
            return row[name]
    return default


def normalize_trades(symbol: str, strategy_id: str, trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if trades.empty:
        return pd.DataFrame(rows)

    for _, row in trades.iterrows():
        legs = row.get("legs") if "legs" in row else None
        if strategy_id == "DS01" and isinstance(legs, list) and legs:
            exit_price = _first_existing(row, ["exit_price"])
            exit_time = pd.to_datetime(_first_existing(row, ["exit_date", "exit_time"]), errors="coerce")
            exit_idx = _first_existing(row, ["exit_idx"])
            net_each = float(_first_existing(row, ["net", "net_pnl"], 0.0) or 0.0) / max(len(legs), 1)
            for leg_no, leg in enumerate(legs, start=1):
                side = _direction_to_side(leg.get("side"))
                entry_time = pd.to_datetime(leg.get("entry_date"), errors="coerce")
                source_trade_no = _first_existing(row, ["trade_no"], len(rows) + 1)
                rows.append(
                    {
                        "candidate_id": f"{symbol}-{strategy_id}-{int(source_trade_no)}-{leg_no}",
                        "symbol": symbol,
                        "strategy_id": strategy_id,
                        "strategy_priority": STRATEGY_PRIORITY[strategy_id],
                        "direction": "long" if side == 1 else "short",
                        "side": side,
                        "entry_time": entry_time,
                        "exit_time": exit_time,
                        "entry_idx": leg.get("entry_idx"),
                        "exit_idx": exit_idx,
                        "entry_price": leg.get("entry_price"),
                        "exit_price": exit_price,
                        "initial_stop": leg.get("stop"),
                        "current_stop": _first_existing(row, ["final_stop", "stop", "initial_stop"], leg.get("stop")),
                        "stop_rule_id": f"{strategy_id}_STOP",
                        "lots": int(leg.get("lots", 1)),
                        "pattern": "DS01 Add Cuogun" if leg.get("is_add") else "DS01 Initial Cuogun",
                        "source_trade_no": f"{source_trade_no}.{leg_no}",
                        "exit_reason": _first_existing(row, ["exit_reason", "reason"], ""),
                        "net": net_each,
                    }
                )
            continue

        side = _direction_to_side(_first_existing(row, ["side", "direction"]))
        entry_price = _first_existing(row, ["entry_price", "avg_entry_price"])
        exit_price = _first_existing(row, ["exit_price"])
        entry_time = pd.to_datetime(_first_existing(row, ["entry_date", "entry_time", "date"]), errors="coerce")
        exit_time = pd.to_datetime(_first_existing(row, ["exit_date", "exit_time"]), errors="coerce")
        exit_idx = _first_existing(row, ["exit_idx"])
        if pd.isna(exit_time) and exit_idx is not None and not pd.isna(exit_idx):
            exit_time = entry_time

        rows.append(
            {
                "candidate_id": f"{symbol}-{strategy_id}-{int(_first_existing(row, ['trade_no'], len(rows) + 1))}",
                "symbol": symbol,
                "strategy_id": strategy_id,
                "strategy_priority": STRATEGY_PRIORITY[strategy_id],
                "direction": "long" if side == 1 else "short",
                "side": side,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_idx": _first_existing(row, ["entry_idx"]),
                "exit_idx": exit_idx,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "initial_stop": _first_existing(row, ["initial_stop", "defense_price"]),
                "current_stop": _first_existing(row, ["stop", "initial_stop", "defense_price"]),
                "stop_rule_id": f"{strategy_id}_STOP",
                "lots": int(_first_existing(row, ["lots", "total_lots"], 1)),
                "pattern": _first_existing(row, ["pattern"], ""),
                "source_trade_no": _first_existing(row, ["trade_no"]),
                "exit_reason": _first_existing(row, ["exit_reason", "reason"], ""),
                "net": _first_existing(row, ["net", "net_pnl"], 0.0),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(["entry_time", "strategy_priority", "candidate_id"]).reset_index(drop=True)


def merge_candidates(candidates: pd.DataFrame, max_same_direction_entries: int = 3) -> dict[str, pd.DataFrame]:
    if candidates.empty:
        empty = pd.DataFrame()
        return {"accepted_trades": empty, "rejected_orders": empty, "ledger_events": empty}

    candidates = candidates.sort_values(["entry_time", "strategy_priority", "candidate_id"]).reset_index(drop=True)
    open_positions: list[dict] = []
    accepted: list[dict] = []
    rejected: list[dict] = []
    events: list[dict] = []

    def close_due_positions(now: pd.Timestamp) -> None:
        still_open: list[dict] = []
        for pos in open_positions:
            exit_time = pd.to_datetime(pos["exit_time"], errors="coerce")
            if not pd.isna(exit_time) and exit_time <= now:
                pos["status"] = "closed"
                events.append(
                    {
                        "event_time": exit_time,
                        "event_type": "close",
                        "symbol": pos["symbol"],
                        "strategy_id": pos["strategy_id"],
                        "candidate_id": pos["candidate_id"],
                        "direction": pos["direction"],
                        "reason": pos.get("exit_reason", ""),
                    }
                )
            else:
                still_open.append(pos)
        open_positions[:] = still_open

    for _, candidate in candidates.iterrows():
        now = pd.to_datetime(candidate["entry_time"], errors="coerce")
        if pd.isna(now):
            item = candidate.to_dict()
            item["reject_reason"] = "missing_entry_time"
            rejected.append(item)
            continue

        close_due_positions(now)
        same_symbol = [pos for pos in open_positions if pos["symbol"] == candidate["symbol"]]
        opposite = [pos for pos in same_symbol if int(pos["side"]) != int(candidate["side"])]
        same_direction = [pos for pos in same_symbol if int(pos["side"]) == int(candidate["side"])]

        if opposite:
            item = candidate.to_dict()
            item["reject_reason"] = "opposite_position_blocked"
            item["blocking_candidates"] = ",".join(pos["candidate_id"] for pos in opposite)
            rejected.append(item)
            events.append(
                {
                    "event_time": now,
                    "event_type": "reject",
                    "symbol": candidate["symbol"],
                    "strategy_id": candidate["strategy_id"],
                    "candidate_id": candidate["candidate_id"],
                    "direction": candidate["direction"],
                    "reason": "opposite_position_blocked",
                }
            )
            continue

        if len(same_direction) >= max_same_direction_entries:
            item = candidate.to_dict()
            item["reject_reason"] = "same_direction_entry_limit"
            item["blocking_candidates"] = ",".join(pos["candidate_id"] for pos in same_direction)
            rejected.append(item)
            events.append(
                {
                    "event_time": now,
                    "event_type": "reject",
                    "symbol": candidate["symbol"],
                    "strategy_id": candidate["strategy_id"],
                    "candidate_id": candidate["candidate_id"],
                    "direction": candidate["direction"],
                    "reason": "same_direction_entry_limit",
                }
            )
            continue

        item = candidate.to_dict()
        item["status"] = "open"
        item["portfolio_trade_no"] = len(accepted) + 1
        open_positions.append(item)
        accepted.append(item)
        events.append(
            {
                "event_time": now,
                "event_type": "open",
                "symbol": candidate["symbol"],
                "strategy_id": candidate["strategy_id"],
                "candidate_id": candidate["candidate_id"],
                "direction": candidate["direction"],
                "reason": "accepted",
            }
        )

    close_due_positions(pd.Timestamp.max)
    return {
        "accepted_trades": pd.DataFrame(accepted),
        "rejected_orders": pd.DataFrame(rejected),
        "ledger_events": pd.DataFrame(events).sort_values(["event_time", "event_type"]).reset_index(drop=True),
    }


def run_strategy_candidates(
    symbol: str,
    strategy_id: str,
    config: UnifiedConfig,
    daily_df: pd.DataFrame | None,
    h1_df: pd.DataFrame | None,
    m15_df: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    kwargs = _base_config_kwargs(config)

    runners: dict[str, Callable[[], dict]] = {
        "DS01": lambda: run_ds01_backtest(daily_df, DS01BacktestConfig(max_entries=config.max_same_direction_entries, **kwargs)),
        "DS02": lambda: run_ds02_backtest(daily_df, DS02BacktestConfig(**kwargs)),
        "DS03": lambda: run_ds03_backtest(daily_df, DS03BacktestConfig(**kwargs)),
        "DS04": lambda: run_ds04_backtest(daily_df, DS04BacktestConfig(**kwargs)),
        "DS05": lambda: run_ds05_backtest(daily_df, DS05BacktestConfig(**kwargs)),
        "DS06": lambda: run_ds06_backtest(daily_df, DS06BacktestConfig(**kwargs)),
        "DS07": lambda: run_ds07_backtest(daily_df, h1_df, DS07BacktestConfig(**kwargs), symbol=symbol),
        "DS08": lambda: run_ds08_backtest(h1_df, DS08BacktestConfig(**kwargs), symbol=symbol),
        "DS09": lambda: run_ds09_backtest(daily_df, m15_df, DS09BacktestConfig(**kwargs), symbol=symbol),
    }

    needs = {
        "DS01": daily_df is not None,
        "DS02": daily_df is not None,
        "DS03": daily_df is not None,
        "DS04": daily_df is not None,
        "DS05": daily_df is not None,
        "DS06": daily_df is not None,
        "DS07": daily_df is not None and h1_df is not None,
        "DS08": h1_df is not None,
        "DS09": daily_df is not None and m15_df is not None,
    }
    if not needs[strategy_id]:
        return pd.DataFrame(), pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "strategy_id": strategy_id,
                    "order_status": "data_missing",
                    "reason": "required timeframe csv not provided",
                }
            ]
        )

    result = runners[strategy_id]()
    candidates = normalize_trades(symbol, strategy_id, result.get("trades", pd.DataFrame()))
    bad = result.get("bad_trades", pd.DataFrame())
    if not bad.empty:
        bad = bad.copy()
        bad["symbol"] = symbol
        bad["strategy_id"] = strategy_id
    return candidates, bad


def infer_symbol(path: str | Path | None, fallback: str = "") -> str:
    if fallback:
        return fallback
    if path is None:
        return ""
    return Path(path).stem.split("_")[0]


def run_unified_symbol(
    symbol: str,
    config: UnifiedConfig,
    daily_csv: str | Path | None,
    h1_csv: str | Path | None,
    m15_csv: str | Path | None,
    strategies: list[str],
    out_dir: str | Path,
) -> dict:
    strategy_set = {strategy.upper() for strategy in strategies}
    needs_daily = bool(strategy_set.intersection({"DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS09"}))
    needs_h1 = bool(strategy_set.intersection({"DS07", "DS08"}))
    needs_m15 = "DS09" in strategy_set

    daily_df = load_ohlcv_for_engine(daily_csv, config.atr_window) if daily_csv and needs_daily else None
    h1_df = load_frame(h1_csv, config.atr_window) if h1_csv and needs_h1 else None
    m15_df = load_m15_frame(m15_csv, config.atr_window) if m15_csv and needs_m15 else None

    all_candidates: list[pd.DataFrame] = []
    bad_audits: list[pd.DataFrame] = []
    for strategy_id in strategies:
        if strategy_id not in STRATEGY_PRIORITY:
            raise ValueError(f"Unknown strategy_id: {strategy_id}")
        candidates, bad = run_strategy_candidates(symbol, strategy_id, config, daily_df, h1_df, m15_df)
        all_candidates.append(candidates)
        bad_audits.append(bad)

    candidates_df = pd.concat(all_candidates, ignore_index=True) if all_candidates else pd.DataFrame()
    bad_df = pd.concat(bad_audits, ignore_index=True) if bad_audits else pd.DataFrame()
    merged = merge_candidates(candidates_df, config.max_same_direction_entries)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    candidates_df.to_csv(out_path / "candidate_trades.csv", index=False, encoding="utf-8-sig")
    merged["accepted_trades"].to_csv(out_path / "accepted_trades.csv", index=False, encoding="utf-8-sig")
    merged["rejected_orders"].to_csv(out_path / "rejected_orders.csv", index=False, encoding="utf-8-sig")
    merged["ledger_events"].to_csv(out_path / "ledger_events.csv", index=False, encoding="utf-8-sig")
    bad_df.to_csv(out_path / "strategy_bad_trades.csv", index=False, encoding="utf-8-sig")

    return {
        "symbol": symbol,
        "spec": config.spec.code if config.spec else "",
        "candidates": len(candidates_df),
        "accepted": len(merged["accepted_trades"]),
        "rejected": len(merged["rejected_orders"]),
        "bad_audits": len(bad_df),
        "out_dir": str(out_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified FengJi Total Pattern DS01-DS09 whitelist ledger engine.")
    parser.add_argument("--symbol", default="")
    parser.add_argument("--daily-csv")
    parser.add_argument("--h1-csv")
    parser.add_argument("--m15-csv")
    parser.add_argument("--m5-csv", help="Deprecated alias for --m15-csv.")
    parser.add_argument("--strategies", default=DEFAULT_STRATEGIES_CSV)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--max-same-direction-entries", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    intraday_csv = args.m15_csv or args.m5_csv
    symbol = infer_symbol(args.daily_csv or args.h1_csv or intraday_csv, args.symbol)
    spec = get_futures_spec(args.daily_csv or args.h1_csv or intraday_csv or symbol)
    config = UnifiedConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        gap=args.gap,
        max_same_direction_entries=args.max_same_direction_entries,
        futures_mode=True,
        spec=spec,
    )
    strategies = [item.strip().upper() for item in args.strategies.split(",") if item.strip()]
    summary = run_unified_symbol(symbol, config, args.daily_csv, args.h1_csv, intraday_csv, strategies, args.out_dir)

    print(f"Symbol:         {symbol}")
    print(f"Spec:           {summary['spec'] or 'N/A'}")
    print(f"Candidates:     {summary['candidates']}")
    print(f"Accepted:       {summary['accepted']}")
    print(f"Rejected:       {summary['rejected']}")
    print(f"Bad audits:     {summary['bad_audits']}")
    print(f"Saved to:       {summary['out_dir']}")


if __name__ == "__main__":
    main()
