"""Audit + rebuild FUTURES trade context snapshots (Phase 2)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT / "scripts"))

from discover_backtest_results import discover  # noqa: E402
from fengji_core.context_stats import (  # noqa: E402
    _count_trades_in_os_range,
    build_from_result_dir,
    resolve_futures_os_frame,
    write_outputs,
)


def audit_item(item: dict) -> dict:
    result_dir = Path(item["result_dir"])
    accepted = result_dir / "accepted_trades.csv"
    trades = pd.read_csv(accepted) if accepted.exists() else pd.DataFrame()
    trade_count = len(trades)
    prev_snaps = 0
    snap_path = result_dir / "trade_context_snapshots.csv"
    if snap_path.exists():
        prev_snaps = max(0, len(pd.read_csv(snap_path)))

    in_range = 0
    os_len = 0
    timeframe = item.get("timeframe", "1d")
    data_dir = ROOT / item.get("data_dir", "data/futures")

    status = "ok"
    err = ""
    try:
        os_df, timeframe = resolve_futures_os_frame(
            data_dir,
            item["symbol"],
            gap=3,
            source_hint=result_dir,
            trades=trades,
            preferred_timeframe=item.get("timeframe", "1d"),
        )
        os_len = len(os_df)
        in_range = _count_trades_in_os_range(trades, os_len)
    except Exception as exc:
        status = "data_gap"
        err = str(exc)

    gap_trades = trade_count - in_range
    return {
        **item,
        "trade_count": trade_count,
        "prev_snapshots": prev_snaps,
        "os_bars": os_len,
        "resolved_timeframe": timeframe,
        "in_range_trades": in_range,
        "out_of_range_trades": gap_trades,
        "coverage_pct": round(100.0 * in_range / trade_count, 2) if trade_count else 0.0,
        "audit_status": status,
        "error": err,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and rebuild FUTURES context snapshots.")
    parser.add_argument("--root", default=str(ROOT / "results"))
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "futures_context_backfill_audit"))
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    items = [i for i in discover(Path(args.root)) if i.get("market") == "FUTURES" and int(i.get("trade_count", 0)) > 0]
    if args.limit > 0:
        items = items[: args.limit]

    audits = [audit_item(item) for item in items]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "futures_context_backfill_audit.json"
    audit_path.write_text(json.dumps(audits, ensure_ascii=False, indent=2), encoding="utf-8")

    rebuild_log: list[dict] = []
    if not args.audit_only:
        for item in items:
            result_dir = Path(item["result_dir"])
            data_dir = ROOT / item.get("data_dir", "data/futures")
            try:
                snapshots, stats = build_from_result_dir(
                    result_dir,
                    data_dir=data_dir,
                    market=item["market"],
                    symbol=item["symbol"],
                    timeframe=item.get("timeframe", "1d"),
                    source_hint=result_dir,
                )
                write_outputs(result_dir, snapshots, stats)
                rebuild_log.append(
                    {
                        "symbol": item["symbol"],
                        "result_dir": str(result_dir),
                        "status": "ok",
                        "snapshots": len(snapshots),
                        "buckets": len(stats),
                    }
                )
                print(f"OK {item['symbol']} snapshots={len(snapshots)} buckets={len(stats)}")
            except Exception as exc:
                rebuild_log.append(
                    {
                        "symbol": item["symbol"],
                        "result_dir": str(result_dir),
                        "status": "error",
                        "error": str(exc),
                    }
                )
                print(f"FAIL {item['symbol']}: {exc}")

    total_trades = sum(int(a.get("trade_count") or 0) for a in audits)
    total_in_range = sum(int(a.get("in_range_trades") or 0) for a in audits)
    total_prev = sum(int(a.get("prev_snapshots") or 0) for a in audits)
    total_new = sum(int(r.get("snapshots") or 0) for r in rebuild_log if r.get("status") == "ok")

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbols": len(audits),
        "total_trades": total_trades,
        "total_in_range_trades": total_in_range,
        "total_out_of_range_trades": total_trades - total_in_range,
        "prev_snapshots": total_prev,
        "rebuilt_snapshots": total_new,
        "data_gap_symbols": [a["symbol"] for a in audits if int(a.get("out_of_range_trades") or 0) > 0],
        "audit_path": str(audit_path),
    }
    summary_path = out_dir / "futures_context_backfill_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if rebuild_log:
        (out_dir / "futures_context_rebuild_log.json").write_text(
            json.dumps(rebuild_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    md = [
        "# FUTURES context 回填审计",
        "",
        f"- 生成时间：{summary['generated_at']}",
        f"- 品种数：**{summary['symbols']}**",
        f"- accepted 合计：**{summary['total_trades']}**",
        f"- OS 可覆盖 entry_idx：**{summary['total_in_range_trades']}**（{round(100*summary['total_in_range_trades']/max(total_trades,1),1)}%）",
        f"- 回填前 snapshots：**{summary['prev_snapshots']}** → 回填后：**{summary['rebuilt_snapshots']}**",
        "",
        "## 数据缺口",
        "",
        "15_5y 回测成交的 entry_idx 多为 15m 尺度；本地若无 `data/futures/15m/{代码}.csv`，只能保留 1d 可索引的尾部样本。",
        "需从国内数据泵同步 15m 后再跑本脚本。",
        "",
    ]
    for a in sorted(audits, key=lambda x: -int(x.get("out_of_range_trades") or 0))[:15]:
        md.append(
            f"- {a['symbol']}: trades={a['trade_count']} in_range={a['in_range_trades']} "
            f"tf={a.get('resolved_timeframe')} os_bars={a.get('os_bars')} prev_snaps={a.get('prev_snapshots')}"
        )
    (out_dir / "futures_context_backfill_audit.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False))
    print(f"Saved {audit_path}")
    print(f"Saved {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
