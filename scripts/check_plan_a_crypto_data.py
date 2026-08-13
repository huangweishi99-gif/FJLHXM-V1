#!/usr/bin/env python3
"""Plan A3-0: check crypto data coverage for ten-coin whitelist backtest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_SYMBOLS = [
    "BTC-USDT",
    "ETH-USDT",
    "SOL-USDT",
    "BNB-USDT",
    "XRP-USDT",
    "ADA-USDT",
    "DOGE-USDT",
    "AVAX-USDT",
    "LTC-USDT",
    "LINK-USDT",
]

ROOT = Path(__file__).resolve().parents[1]


def inst_to_usdt(inst: str) -> str:
    text = inst.strip().upper().replace("_", "-")
    if "-" in text:
        base = text.split("-")[0]
    elif text.endswith("USDT"):
        base = text[:-4]
    else:
        base = text
    return f"{base}USDT"


def find_csv(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists() and path.stat().st_size > 100:
            return path
    return None


def check_symbol(inst: str, days: int) -> dict:
    usdt = inst_to_usdt(inst)
    base = inst.replace("-", "_")
    rows: dict = {"inst_id": inst, "usdt": usdt, "frames": {}}
    ok = True

    d1 = find_csv(
        [
            ROOT / "data" / "crypto_okx" / f"{inst}_1D_{days}d.csv",
            ROOT / "data" / "crypto_okx" / f"{inst}_1D_1825d.csv",
            ROOT / "data" / "1d" / f"{usdt}.csv",
            ROOT / "data" / "overseas_1d" / f"{usdt}.csv",
        ]
    )
    h1 = find_csv(
        [
            ROOT / "data" / "crypto_okx" / f"{inst}_1H_{days}d.csv",
            ROOT / "data" / "crypto_okx" / f"{inst}_1H_1825d.csv",
            ROOT / "data" / "1h" / f"{usdt}.csv",
        ]
    )
    m15 = find_csv(
        [
            ROOT / "data" / "crypto_okx" / f"{inst}_15m_{days}d.csv",
            ROOT / "data" / "crypto_okx" / f"{inst}_15m_1825d.csv",
            ROOT / "data" / "15m" / f"{usdt}.csv",
        ]
    )

    for label, path in [("d1", d1), ("h1", h1), ("m15", m15)]:
        if path is None:
            rows["frames"][label] = {"ok": False, "path": None, "rows": 0}
            ok = False
        else:
            line_count = sum(1 for _ in path.open(encoding="utf-8", errors="replace")) - 1
            rows["frames"][label] = {
                "ok": line_count >= 30,
                "path": str(path.relative_to(ROOT)),
                "rows": max(0, line_count),
            }
            if line_count < 30:
                ok = False

    rows["ready"] = ok
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan A3-0 crypto data coverage check")
    parser.add_argument("--symbols", default="DEFAULT", help="DEFAULT or comma-separated inst ids")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.symbols.upper() == "DEFAULT":
        symbols = DEFAULT_SYMBOLS
    else:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    report = {
        "days": args.days,
        "symbols": symbols,
        "items": [check_symbol(s, args.days) for s in symbols],
    }
    report["ready_count"] = sum(1 for item in report["items"] if item["ready"])
    report["total"] = len(report["items"])
    report["all_ready"] = report["ready_count"] == report["total"]

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")

    return 0 if report["all_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
