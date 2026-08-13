#!/usr/bin/env python3
"""Audit domestic/crypto OS state *_1d.json file sizes and hardened_by_bar counts."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def audit_state_dir(state_dir: Path, *, warn_bytes: int) -> dict:
    files = sorted(state_dir.glob("*_1d.json"))
    rows: list[dict] = []
    for path in files:
        try:
            st = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            rows.append({"name": path.name, "bytes": path.stat().st_size, "error": str(exc)})
            continue
        hbb = st.get("hardened_by_bar") or {}
        rows.append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "processed_len": int(st.get("processed_len") or 0),
                "last_date": st.get("last_date"),
                "hbb_keys": len(hbb) if isinstance(hbb, dict) else 0,
                "warn": path.stat().st_size >= warn_bytes,
            }
        )
    total = sum(r.get("bytes", 0) for r in rows)
    warned = [r for r in rows if r.get("warn")]
    rows.sort(key=lambda r: r.get("bytes", 0), reverse=True)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "state_dir": str(state_dir),
        "count": len(files),
        "total_bytes": total,
        "warn_threshold_bytes": warn_bytes,
        "warn_count": len(warned),
        "top": rows[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", default="runtime/fengji_os_state")
    parser.add_argument("--warn-bytes", type=int, default=5_000_000)
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    state_dir = Path(args.state_dir)
    if not state_dir.is_absolute():
        state_dir = root / state_dir
    report = audit_state_dir(state_dir, warn_bytes=int(args.warn_bytes))
    out_dir = Path(args.out_dir) if args.out_dir else root / "results" / f"os_state_1d_sizes_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# OS state 1d 体积审计",
        "",
        f"- 目录：`{report['state_dir']}`",
        f"- 文件数：**{report['count']}** · 合计 **{report['total_bytes']:,}** bytes",
        f"- 超阈值（>{report['warn_threshold_bytes']:,}）：**{report['warn_count']}**",
        "",
        "## Top 10",
        "",
        "| 文件 | bytes | processed_len | last_date | hbb_keys |",
        "|------|------:|--------------:|-----------|--------:|",
    ]
    for row in report["top"][:10]:
        lines.append(
            f"| {row.get('name','?')} | {row.get('bytes',0):,} | {row.get('processed_len','?')} "
            f"| {row.get('last_date','?')} | {row.get('hbb_keys','?')} |"
        )
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"out": str(out_dir), "count": report["count"], "warn": report["warn_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
