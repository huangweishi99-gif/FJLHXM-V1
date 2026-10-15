"""风险平价仓位的**影子测算**（只读、不改任何行为）。

问题：两端现在都是固定手数/固定名义（国内 ``--lots 1``、海外 ``--margin-per-trade``
固定）。于是「止损宽的品种单笔亏得离谱、止损窄的品种赚不到钱」——国内台账里
LH 一笔 -12267、LC 一笔 +52948，波动完全由品种价格尺度决定，而不是由策略优势
决定。风险平价让**每笔承担的初始风险一致**，从而可比、可控。

本脚本用历史平仓台账做反事实测算：若当初按 ``lots = 权益 × risk_per_trade /
(|入场-初始止损| × 每手名义)`` 开仓，历史总盈亏/最大单笔亏损/波动会变成什么样。
**只算不改**：不触碰任何交易状态，也不修改统计文件（不写回 live_ops_stats）。

需要 ``initial_stop``（缺该列的市场无法测算，脚本会明确报出并退出）。

用法：
    python scripts/shadow_risk_sizing.py --market CRYPTO
    python scripts/shadow_risk_sizing.py --closed-csv path/to/closed_trades.csv --risk-per-trade 0.01 --max-lots 10
"""
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path
from typing import Any

DEFAULT_CLOSED_CSV = "runtime/fengji_pending_orders/closed_trades.csv"


def _f(value: Any) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        return float(text)
    except ValueError:
        return None


def _load(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _scale_for(row: dict[str, str], equity: float, risk_per_trade: float, max_lots: float) -> float | None:
    """风险平价相对固定仓位的缩放倍数（1.0 = 与现状相同）。"""
    entry = _f(row.get("entry_price"))
    stop = _f(row.get("initial_stop"))
    net = _f(row.get("net_pnl"))
    notional = _f(row.get("notional"))
    if entry is None or stop is None or net is None:
        return None
    if notional is None:
        margin = _f(row.get("margin")) or 0.0
        leverage = _f(row.get("leverage")) or 1.0
        notional = margin * leverage
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0 or entry <= 0 or notional <= 0:
        return None
    # 当前这笔承担的风险额（按固定名义）
    current_risk = risk_per_unit / entry * notional
    if current_risk <= 0:
        return None
    target_risk = equity * risk_per_trade
    scale = target_risk / current_risk
    return float(min(max_lots, max(0.0, scale)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Shadow (read-only) analysis of risk-parity sizing vs fixed sizing.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--market", default="CRYPTO")
    parser.add_argument("--closed-csv", default="")
    parser.add_argument("--risk-per-trade", type=float, default=0.01, help="每笔风险占权益比例（默认 1%）")
    parser.add_argument("--max-lots", type=float, default=10.0, help="缩放倍数上限（默认 10）")
    parser.add_argument("--initial-equity", type=float, default=1000.0, help="起始权益（台账未给出时使用）")
    args = parser.parse_args()

    root = Path(args.root)
    csv_path = Path(args.closed_csv) if args.closed_csv else (root / DEFAULT_CLOSED_CSV)
    if not csv_path.is_absolute():
        csv_path = root / csv_path
    rows = _load(csv_path)
    print(f"closed_csv={csv_path} rows={len(rows)} risk_per_trade={args.risk_per_trade:.2%} max_scale={args.max_lots}")

    equity = args.initial_equity
    flat: list[float] = []
    sized: list[float] = []
    skipped = 0
    per_strategy: dict[str, dict[str, float]] = {}

    for row in rows:
        net = _f(row.get("net_pnl"))
        if net is None:
            skipped += 1
            continue
        after = _f(row.get("equity_after")) or _f(row.get("equity"))
        scale = _scale_for(row, equity, args.risk_per_trade, args.max_lots)
        if scale is None:
            skipped += 1
            continue
        # 权益用**上一笔结束后的权益**（与实盘下单时点一致）
        if after is not None and after > 0:
            equity = after
        flat.append(net)
        sized.append(net * scale)
        slot = per_strategy.setdefault(str(row.get("strategy_id") or "UNKNOWN").upper(), {"flat": 0.0, "sized": 0.0, "n": 0.0})
        slot["flat"] += net
        slot["sized"] += net * scale
        slot["n"] += 1

    if not flat:
        print(f"no usable rows (skipped={skipped}) — 该市场台账可能缺 initial_stop，无法做风险测算")
        return 1

    def _summary(name: str, values: list[float]) -> str:
        mean = statistics.fmean(values)
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        worst = min(values)
        best = max(values)
        wins = sum(1 for value in values if value > 0) / len(values)
        return (
            f"{name}: n={len(values)} 总盈亏={sum(values):.2f} 均值={mean:.2f} "
            f"波动={std:.2f} 最差单笔={worst:.2f} 最好单笔={best:.2f} 胜率={wins:.1%}"
        )

    print(_summary("固定仓位(现状)", flat))
    print(_summary("风险平价(影子)", sized))
    print("\n按策略对比（总盈亏）：")
    for name in sorted(per_strategy):
        slot = per_strategy[name]
        delta = slot["sized"] - slot["flat"]
        print(f"  {name}: n={int(slot['n'])} 固定={slot['flat']:.2f} 风险平价={slot['sized']:.2f} 差={delta:+.2f}")
    print(f"\nskipped={skipped}（缺 initial_stop/net_pnl 的行不参与测算）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
