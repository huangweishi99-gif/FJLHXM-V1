"""回填脚本 tests：口径与实时一致、幂等、缺 initial_stop 时 R 诚实留空。"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.backfill_ops_stats import main as backfill_main

HEADER = [
    "closed_at",
    "symbol",
    "strategy_id",
    "side",
    "entry_price",
    "exit_price",
    "initial_stop",
    "net_pnl",
    "exit_reason",
    "order_id",
]


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)


def _sample_rows() -> list[list[str]]:
    # DS01 空头：入场 100、止损 110（风险 10）、出场 90 → R=+1.0，净盈利
    # DS03 多头：入场 50、止损 45（风险 5）、出场 40 → R=-2.0，亏损
    # DS01 空头：入场 100、止损 110、出场 115 → R=-1.5，亏损（止损被打）
    return [
        ["2026-01-01 10:00:00", "AAAUSDT", "DS01", "short", "100", "90", "110", "10.0", "target", "o1"],
        ["2026-01-02 10:00:00", "BBBUSDT", "DS03", "long", "50", "40", "45", "-10.0", "target", "o2"],
        ["2026-01-03 10:00:00", "AAAUSDT", "DS01", "short", "100", "115", "110", "-15.0", "stop", "o3"],
    ]


def _stats(tmp_path: Path) -> dict:
    path = tmp_path / "runtime" / "fengji_ops_stats" / "TEST_ops_stats.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _bucket(buckets: dict, strategy: str) -> dict:
    for key, value in buckets.items():
        if key.upper().startswith(strategy.upper()):
            return value
    raise AssertionError(f"bucket for {strategy} not found: {list(buckets)}")


def test_backfill_fills_buckets_and_is_idempotent(tmp_path: Path, capsys) -> None:
    csv_path = tmp_path / "runtime" / "fengji_pending_orders" / "closed_trades.csv"
    _write_csv(csv_path, _sample_rows())

    assert backfill_main(["--root", str(tmp_path), "--market", "TEST", "--closed-csv", str(csv_path)]) == 0
    data = _stats(tmp_path)
    assert data["events_total"] == 3
    ds01 = _bucket(data["buckets"], "DS01")
    assert ds01["count"] == 2  # 以平仓为准
    assert ds01["wins"] == 1
    assert abs(float(ds01["avg_r"]) - (-0.25)) < 1e-6  # (+1.0 + -1.5) / 2
    assert ds01["stop_rate"] == 0.5

    # 第二次执行：无新行导入，统计不变（幂等）
    assert backfill_main(["--root", str(tmp_path), "--market", "TEST", "--closed-csv", str(csv_path)]) == 0
    again = _stats(tmp_path)
    assert again["events_total"] == 3
    assert _bucket(again["buckets"], "DS01")["count"] == 2


def test_backfill_without_initial_stop_leaves_r_empty(tmp_path: Path) -> None:
    rows = _sample_rows()
    for row in rows:
        row[6] = ""  # initial_stop 缺失（国内台账现状）
    csv_path = tmp_path / "runtime" / "fengji_pending_orders" / "closed_trades.csv"
    _write_csv(csv_path, rows)

    assert backfill_main(["--root", str(tmp_path), "--market", "TEST", "--closed-csv", str(csv_path)]) == 0
    data = _stats(tmp_path)
    ds01 = _bucket(data["buckets"], "DS01")
    assert ds01["count"] == 2
    assert ds01["wins"] == 1  # 胜负仍以 net_pnl 为准
    assert ds01["avg_r"] is None  # 不用假风险值
    assert ds01["avg_net"] is not None


def test_duplicate_ledger_rows_counted_once(tmp_path: Path, capsys) -> None:
    """台账里同一笔平仓被重复 append（历史故障）时，只能计一次。"""
    rows = _sample_rows()
    rows.append(list(rows[0]))  # 同一 order_id 再写一遍
    rows.append(list(rows[0]))
    csv_path = tmp_path / "runtime" / "fengji_pending_orders" / "closed_trades.csv"
    _write_csv(csv_path, rows)

    assert backfill_main(["--root", str(tmp_path), "--market", "TEST", "--closed-csv", str(csv_path)]) == 0
    data = _stats(tmp_path)
    assert data["events_total"] == 3  # 不是 5
    assert _bucket(data["buckets"], "DS01")["count"] == 2
    assert "duplicate_rows=2" in capsys.readouterr().out


def test_backfill_reset_replays_all(tmp_path: Path) -> None:
    csv_path = tmp_path / "runtime" / "fengji_pending_orders" / "closed_trades.csv"
    _write_csv(csv_path, _sample_rows())
    base = ["--root", str(tmp_path), "--market", "TEST", "--closed-csv", str(csv_path)]

    assert backfill_main(base) == 0
    assert backfill_main(base + ["--reset"]) == 0
    data = _stats(tmp_path)
    # reset 后全量重灌：仍是 3 条，不会翻倍
    assert data["events_total"] == 3
    assert _bucket(data["buckets"], "DS03")["count"] == 1
