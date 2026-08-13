from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sanitize_domestic_futures_csv import clean_frame  # noqa: E402


TIMEFRAMES = ("1d", "1h", "15m")


@dataclass(frozen=True)
class DirtyFile:
    path: str
    symbol: str
    timeframe: str
    rows: int
    kept: int
    dropped: int


def now_stamp() -> str:
    return pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")


def normalize_symbol(value: str) -> str:
    text = str(value or "").strip().upper().replace("-", "").replace("_", "")
    return text[:-4] if text.endswith("USDT") else text


def split_symbols(text: str) -> set[str]:
    return {normalize_symbol(item) for item in str(text or "").replace(";", ",").split(",") if item.strip()}


def symbol_from_path(path: Path) -> str:
    return normalize_symbol(path.stem)


def discover_dirty_files(data_dir: Path, symbols: set[str] | None = None) -> list[DirtyFile]:
    dirty: list[DirtyFile] = []
    wanted = {normalize_symbol(item) for item in symbols or set()}
    for timeframe in TIMEFRAMES:
        tf_dir = data_dir / timeframe
        if not tf_dir.exists():
            continue
        for path in sorted(tf_dir.glob("*.csv")):
            symbol = symbol_from_path(path)
            if wanted and symbol not in wanted:
                continue
            try:
                frame = pd.read_csv(path)
            except Exception:
                continue
            cleaned = clean_frame(frame)
            dropped = len(frame) - len(cleaned)
            if dropped > 0:
                dirty.append(
                    DirtyFile(
                        path=str(path),
                        symbol=symbol,
                        timeframe=timeframe,
                        rows=int(len(frame)),
                        kept=int(len(cleaned)),
                        dropped=int(dropped),
                    )
                )
    return dirty


def unique_symbols(dirty_files: list[DirtyFile]) -> list[str]:
    return sorted({item.symbol for item in dirty_files})


def clean_dirty_files(dirty_files: list[DirtyFile], data_dir: Path, backup_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in dirty_files:
        path = Path(item.path)
        frame = pd.read_csv(path)
        cleaned = clean_frame(frame)
        target_backup = backup_dir / path.relative_to(data_dir)
        target_backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target_backup)
        tmp = path.with_suffix(path.suffix + ".tmp")
        cleaned.to_csv(tmp, index=False, encoding="utf-8")
        tmp.replace(path)
        record = asdict(item)
        record["backup"] = str(target_backup)
        records.append(record)
    return records


def refetch_symbols(symbols: list[str], data_dir: Path) -> list[dict[str, Any]]:
    os.environ["FUTURES_DATA_DIR"] = str(data_dir.resolve())
    import data_manager_futures as dm  # noqa: WPS433

    unknown = [symbol for symbol in symbols if symbol not in dm.TQ_SYMBOL_MAP]
    if unknown:
        raise ValueError(f"unknown futures symbols: {','.join(unknown)}")

    results: list[dict[str, Any]] = []
    api = None
    try:
        api = dm.connect_api()
        for symbol in symbols:
            ok = bool(dm.fetch_symbol(api, symbol, dm.TQ_SYMBOL_MAP[symbol]))
            results.append({"symbol": symbol, "ok": ok})
    finally:
        if api is not None:
            try:
                api.close()
            except Exception:
                pass
    return results


def write_audit(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair corrupt domestic futures CSVs by symbol.")
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--symbols", default="", help="Comma-separated symbols. Empty means auto-detect dirty symbols.")
    parser.add_argument("--backup-dir", default=None, type=Path)
    parser.add_argument("--audit-out", default=None, type=Path)
    parser.add_argument("--max-symbols", default=3, type=int)
    parser.add_argument("--apply", action="store_true", help="Backup, clean dirty files, refetch from Tianqin, and verify.")
    parser.add_argument("--no-refetch", action="store_true", help="Only clean dirty files; use only for emergency/manual recovery.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data_dir = args.data_dir
    requested = split_symbols(args.symbols)
    dirty = discover_dirty_files(data_dir, requested)
    symbols = unique_symbols(dirty)
    audit_path = args.audit_out or Path("runtime") / "logs" / f"futures_csv_repair_{now_stamp()}.json"
    payload: dict[str, Any] = {
        "apply": bool(args.apply),
        "data_dir": str(data_dir),
        "dirty_files": [asdict(item) for item in dirty],
        "symbols": symbols,
        "rows_dropped": int(sum(item.dropped for item in dirty)),
    }

    for item in dirty:
        prefix = "DIRTY"
        print(
            f"{prefix} {item.path} symbol={item.symbol} timeframe={item.timeframe} "
            f"rows={item.rows} kept={item.kept} dropped={item.dropped}"
        )

    if not dirty:
        print("repair_needed=0 files_changed=0 rows_dropped=0 apply=False")
        payload["status"] = "clean"
        write_audit(audit_path, payload)
        print(f"audit={audit_path}")
        return 0

    if len(symbols) > int(args.max_symbols):
        payload["status"] = "too_many_symbols"
        write_audit(audit_path, payload)
        print(f"ABORT symbols={','.join(symbols)} exceeds max_symbols={args.max_symbols}")
        print(f"audit={audit_path}")
        return 2

    if not args.apply:
        payload["status"] = "dry_run_dirty"
        write_audit(audit_path, payload)
        print(
            f"repair_needed=1 files_changed={len(dirty)} rows_dropped={payload['rows_dropped']} "
            f"symbols={','.join(symbols)} apply=False"
        )
        print(f"audit={audit_path}")
        return 1

    backup_dir = args.backup_dir or Path("runtime") / f"futures_csv_repair_backup_{now_stamp()}"
    payload["backup_dir"] = str(backup_dir)
    payload["cleaned_files"] = clean_dirty_files(dirty, data_dir, backup_dir)
    if not args.no_refetch:
        payload["refetch_results"] = refetch_symbols(symbols, data_dir)

    remaining = discover_dirty_files(data_dir, set(symbols))
    payload["remaining_dirty_files"] = [asdict(item) for item in remaining]
    payload["status"] = "repaired" if not remaining else "remaining_dirty"
    write_audit(audit_path, payload)

    print(
        f"repair_apply_done files_changed={len(dirty)} rows_dropped={payload['rows_dropped']} "
        f"symbols={','.join(symbols)} remaining={len(remaining)} audit={audit_path}"
    )
    return 0 if not remaining else 3


if __name__ == "__main__":
    raise SystemExit(main())
