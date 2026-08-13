"""Compare OS state before/after rebuild and optionally re-audit paper fills."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CAMP_NAMES = {-1: "blue", 0: "neutral", 1: "red"}


def camp_label(value: Any) -> str:
    try:
        return CAMP_NAMES.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


def price_of(node: dict[str, Any] | None) -> float | None:
    if not node:
        return None
    try:
        return float(node.get("price"))
    except (TypeError, ValueError):
        return None


def snapshot_state(path: Path) -> dict[str, Any]:
    state = json.loads(path.read_text(encoding="utf-8"))
    return {
        "state_file": path.name,
        "camp": camp_label(state.get("camp")),
        "camp_confirmed": camp_label(state.get("camp_confirmed")),
        "pending_turn": bool(state.get("pending_turn", False)),
        "turn_count": len(state.get("turns", [])),
        "processed_len": int(state.get("processed_len", 0)),
        "first_date": str(state.get("first_date", "")),
        "last_date": str(state.get("last_date", "")),
        "red_ext_price": price_of(state.get("red_ext")),
        "blue_ext_price": price_of(state.get("blue_ext")),
        "red_peak_price": price_of(state.get("red_peak")),
        "blue_peak_price": price_of(state.get("blue_peak")),
        "hardened_count": len(state.get("hardened_nodes", [])),
        "identity_count": len(state.get("identity_nodes", [])),
    }


def list_state_files(state_dir: Path) -> dict[str, Path]:
    if not state_dir.exists():
        return {}
    return {path.name: path for path in sorted(state_dir.glob("*.json")) if path.is_file()}


def compare_state_dirs(before_dir: Path, after_dir: Path) -> list[dict[str, Any]]:
    before = list_state_files(before_dir)
    after = list_state_files(after_dir)
    names = sorted(set(before) | set(after))
    rows: list[dict[str, Any]] = []
    for name in names:
        b_path = before.get(name)
        a_path = after.get(name)
        if b_path is None:
            rows.append({"state_file": name, "status": "added", "note": "only in after"})
            continue
        if a_path is None:
            rows.append({"state_file": name, "status": "removed", "note": "only in before"})
            continue
        b = snapshot_state(b_path)
        a = snapshot_state(a_path)
        changed_fields: list[str] = []
        for key in (
            "camp",
            "camp_confirmed",
            "turn_count",
            "red_ext_price",
            "blue_ext_price",
            "red_peak_price",
            "blue_peak_price",
            "processed_len",
            "last_date",
        ):
            if b.get(key) != a.get(key):
                changed_fields.append(key)
        rows.append(
            {
                "state_file": name,
                "status": "changed" if changed_fields else "unchanged",
                "changed_fields": ",".join(changed_fields),
                "before_camp": b["camp"],
                "after_camp": a["camp"],
                "before_turn_count": b["turn_count"],
                "after_turn_count": a["turn_count"],
                "before_red_ext": b["red_ext_price"],
                "after_red_ext": a["red_ext_price"],
                "before_blue_ext": b["blue_ext_price"],
                "after_blue_ext": a["blue_ext_price"],
                "before_last_date": b["last_date"],
                "after_last_date": a["last_date"],
            }
        )
    return rows


def write_report(out_dir: Path, *, label: str, rows: list[dict[str, Any]], meta: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "label": label,
        "meta": meta,
        "summary": {
            "total": len(rows),
            "changed": sum(1 for row in rows if row.get("status") == "changed"),
            "unchanged": sum(1 for row in rows if row.get("status") == "unchanged"),
            "added": sum(1 for row in rows if row.get("status") == "added"),
            "removed": sum(1 for row in rows if row.get("status") == "removed"),
            "camp_changed": sum(
                1
                for row in rows
                if row.get("status") == "changed" and "camp" in str(row.get("changed_fields", ""))
            ),
        },
        "rows": rows,
    }
    json_path = out_dir / f"os_state_rebuild_diff_{label}_{stamp}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# OS state rebuild diff ({label})",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- before: `{meta.get('before_dir', '')}`",
        f"- after: `{meta.get('after_dir', '')}`",
        "",
        "## Summary",
        "",
        f"- total: {payload['summary']['total']}",
        f"- changed: {payload['summary']['changed']}",
        f"- camp_changed: {payload['summary']['camp_changed']}",
        f"- unchanged: {payload['summary']['unchanged']}",
        "",
        "## Changed symbols (camp or turns or defense ext)",
        "",
        "| state_file | before_camp | after_camp | turns | red_ext | blue_ext |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        if row.get("status") not in {"changed", "added", "removed"}:
            continue
        md_lines.append(
            "| {state_file} | {before_camp} | {after_camp} | {before_turn_count}→{after_turn_count} | "
            "{before_red_ext}→{after_red_ext} | {before_blue_ext}→{after_blue_ext} |".format(
                state_file=row.get("state_file", ""),
                before_camp=row.get("before_camp", row.get("status", "")),
                after_camp=row.get("after_camp", row.get("status", "")),
                before_turn_count=row.get("before_turn_count", ""),
                after_turn_count=row.get("after_turn_count", ""),
                before_red_ext=row.get("before_red_ext", ""),
                after_red_ext=row.get("after_red_ext", ""),
                before_blue_ext=row.get("before_blue_ext", ""),
                after_blue_ext=row.get("after_blue_ext", ""),
            )
        )
    md_path = out_dir / f"os_state_rebuild_diff_{label}_{stamp}.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    latest = out_dir / f"os_state_rebuild_diff_{label}_latest.md"
    latest.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"diff_json={json_path}")
    print(f"diff_md={md_path}")
    return json_path


def run_fill_audit(root: Path, profile: str, out_dir: Path) -> int:
    script = root / "scripts" / "audit_paper_fills.py"
    if not script.exists():
        print(f"skip fill audit: missing {script}")
        return 0
    cmd = [
        sys.executable,
        str(script),
        "--profile",
        profile,
        "--out-dir",
        str(out_dir),
        "--since-hours",
        "720",
    ]
    print("fill_audit_cmd=", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(root), check=False)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit OS state rebuild impact (before vs after).")
    parser.add_argument("--before-dir", required=True, help="Backup state dir before rebuild.")
    parser.add_argument("--after-dir", required=True, help="New rebuilt state dir.")
    parser.add_argument("--out-dir", default="", help="Report output dir (default: results/os_state_rebuild).")
    parser.add_argument("--label", default="local", help="Report label: local|domestic|overseas.")
    parser.add_argument(
        "--fill-audit-profile",
        default="",
        choices=["", "domestic", "overseas"],
        help="If set, run audit_paper_fills.py after diff (720h window).",
    )
    args = parser.parse_args()

    before_dir = Path(args.before_dir)
    after_dir = Path(args.after_dir)
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "results" / "os_state_rebuild"
    if not before_dir.exists():
        raise SystemExit(f"before-dir not found: {before_dir}")
    if not after_dir.exists():
        raise SystemExit(f"after-dir not found: {after_dir}")

    rows = compare_state_dirs(before_dir, after_dir)
    write_report(
        out_dir,
        label=args.label,
        rows=rows,
        meta={"before_dir": str(before_dir), "after_dir": str(after_dir)},
    )
    changed = sum(1 for row in rows if row.get("status") == "changed")
    camp_changed = sum(
        1 for row in rows if row.get("status") == "changed" and "camp" in str(row.get("changed_fields", ""))
    )
    print(f"summary changed={changed} camp_changed={camp_changed} total={len(rows)}")

    if args.fill_audit_profile:
        code = run_fill_audit(ROOT, args.fill_audit_profile, out_dir / "fill_supervision")
        if code != 0:
            print(f"fill_audit_exit={code}")
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
