#!/usr/bin/env python3
"""Latest D1 camp snapshot for crypto symbols (OS rebuild sanity)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (SRC, ROOT / "packages" / "fengji_core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd
from backtest_ds07 import build_os_detail_frame

DEFAULT = ("DOGEUSDT", "LTCUSDT", "RENDERUSDT", "IOUSDT")


def pick_csv(data_dir: Path, symbol: str) -> Path | None:
    base = symbol.replace("USDT", "")
    cands = [
        data_dir / "overseas_1d" / f"{symbol}.csv",
        data_dir / "1d" / f"{symbol}.csv",
        data_dir / "crypto_okx" / f"{base}-USDT_1D_1825d.csv",
    ]
    found = [p for p in cands if p.is_file()]
    if not found:
        return None
    best = max(found, key=lambda p: pd.read_csv(p).shape[0])
    return best


def load_d1(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--symbols", default=",".join(DEFAULT))
    parser.add_argument("--out", default=str(ROOT / "results" / "crypto_camp_snapshot_20260618" / "report.json"))
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    rows = []
    for sym in symbols:
        csv_path = pick_csv(data_dir, sym)
        if not csv_path:
            rows.append({"symbol": sym, "verdict": "needs-data"})
            continue
        raw = load_d1(csv_path)
        os_df, _ = build_os_detail_frame(raw, gap=3)
        last = os_df.iloc[-1]
        prev = os_df.iloc[-2] if len(os_df) > 1 else last
        camp = int(last.get("camp", 0) or 0)
        rows.append(
            {
                "symbol": sym,
                "csv": str(csv_path),
                "last_date": str(last["date"])[:10],
                "camp": camp,
                "camp_label": {1: "red", -1: "blue", 0: "neutral"}.get(camp, str(camp)),
                "close": float(last["close"]),
                "active_high": last.get("active_high"),
                "active_low": last.get("active_low"),
                "prev_camp": int(prev.get("camp", 0) or 0),
                "verdict": "ok",
            }
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"symbols": rows}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = out.parent / "SUMMARY.md"
    lines = ["# Crypto D1 阵营快照", "", "| 品种 | 末K | camp | close |", "|---|---|---:|---:|"]
    for r in rows:
        if r.get("verdict") == "needs-data":
            lines.append(f"| {r['symbol']} | — | needs-data | — |")
        else:
            lines.append(f"| {r['symbol']} | {r['last_date']} | **{r['camp_label']}** ({r['camp']}) | {r['close']} |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
