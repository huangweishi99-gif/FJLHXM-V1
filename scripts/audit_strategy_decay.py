"""只读审计：策略衰退检测（近期窗口 vs 历史基线）。

数据源是两端监控实时写出的 ``runtime/fengji_ops_stats/{MARKET}_ops_stats.json``
（``live_ops_stats`` 保留最近 N 笔平仓明细）。本脚本**只观测不干预**：不改任何
交易状态，是否停用策略由人决定。

用法：
    python scripts/audit_strategy_decay.py                     # 默认扫 FUTURES + CRYPTO
    python scripts/audit_strategy_decay.py --market FUTURES --window 30 --fail-on severe
    python scripts/audit_strategy_decay.py --json              # 结构化输出

退出码：``--fail-on severe``（默认）时，出现 severe 告警返回 1，便于接入看护告警。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fengji_core.live_ops_stats import stats_path_for
from fengji_core.strategy_decay import detect, format_report

DEFAULT_MARKETS = ["FUTURES", "CRYPTO"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect strategy alpha decay from live ops stats.")
    parser.add_argument("--runtime-dir", default="runtime", help="runtime 根目录（统计文件在其 fengji_ops_stats 子目录）")
    parser.add_argument("--market", nargs="+", default=DEFAULT_MARKETS, help="市场标签，可多个")
    parser.add_argument("--window", type=int, default=30, help="近期窗口笔数")
    parser.add_argument("--fail-on", choices=["none", "warn", "severe"], default="severe", help="何级别告警触发非零退出码")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reports: list[dict] = []
    worst = 0
    levels = {"none": 0, "warn": 1, "severe": 2}
    trigger = levels[args.fail_on]

    for market in args.market:
        path = stats_path_for(market, Path(args.runtime_dir))
        if not path.exists():
            print(f"[strategy-decay] skip {market}: no stats at {path}")
            continue
        try:
            stats = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[strategy-decay] skip {market}: unreadable stats ({exc})")
            continue
        report = detect(stats, window=int(args.window))
        reports.append(report)
        if not args.json:
            print(format_report(report))
        for alert in report.get("alerts") or []:
            worst = max(worst, levels.get(str(alert.get("level")), 0))

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2, default=str))
    return 1 if worst >= trigger and trigger > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
