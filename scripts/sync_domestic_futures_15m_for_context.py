"""Sync domestic futures 15m CSVs for FUTURES context backfill (SSH scp from data pump)."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.symbol_names import FUTURES_CN_NAMES  # noqa: E402
from sync_domestic_futures_1d_for_web import (  # noqa: E402
    ACTIVE_FUTURES_CODES,
    DEFAULT_SYMBOLS,
    MAIN_CONTINUOUS_PREFIX,
    parse_symbols,
    validate_actual_main_source,
)


DEFAULT_MIN_ROWS = 120
PREFERRED_MIN_ROWS = 5000


def run_scp_15m(ssh_host: str, remote_root: str, symbol: str, staging_dir: Path, retries: int = 3) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    target = staging_dir / f"{symbol}_15m.csv"
    remote = f"{ssh_host}:{remote_root.rstrip('/')}/data/15m/{symbol}.csv"
    if target.exists():
        target.unlink()
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(
                ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", remote, str(target)],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            last_error = None
            break
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt >= retries:
                raise
            time.sleep(1.5 * attempt)
    if last_error is not None:
        raise last_error
    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError(f"downloaded empty 15m file for {symbol}")
    return target


def normalize_intraday_csv(src: Path, dst: Path, *, min_rows: int = DEFAULT_MIN_ROWS) -> tuple[int, str, str]:
    df = pd.read_csv(src)
    validate_actual_main_source(df, src)
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{src.name} missing columns: {sorted(missing)}")

    dates = pd.to_datetime(df["date"], errors="coerce")
    if dates.notna().mean() < 0.5:
        raise ValueError(f"{src.name} invalid date column")

    out = pd.DataFrame(
        {
            "date": dates.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df.get("volume"), errors="coerce"),
            "hold": pd.to_numeric(df.get("close_oi", df.get("hold")), errors="coerce"),
        }
    )
    if "symbol" in df.columns:
        out["symbol"] = df["symbol"].astype(str)

    mask = out["date"].notna()
    for column in ("open", "high", "low", "close"):
        mask &= out[column].notna() & (out[column] > 0)
    mask &= out["high"] >= out[["open", "close", "low"]].max(axis=1)
    mask &= out["low"] <= out[["open", "close", "high"]].min(axis=1)
    mask &= out["high"] / out["low"] < 1.25

    out = out.loc[mask].copy()
    out = out.drop_duplicates(subset=["date"], keep="last")
    out = out.sort_values("date").reset_index(drop=True)
    if len(out) < min_rows:
        raise ValueError(f"{src.name} has too few sane 15m rows: {len(out)} < {min_rows}")

    out["volume"] = out["volume"].fillna(0).round().astype("int64")
    out["hold"] = out["hold"].fillna(0).round().astype("int64")

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    out.to_csv(tmp, index=False, encoding="utf-8")
    tmp.replace(dst)
    return len(out), str(out["date"].iloc[0]), str(out["date"].iloc[-1])


def write_dual_outputs(raw: Path, out_dir: Path, code: str, cn_name: str, min_rows: int) -> tuple[int, str, str]:
    rows, start, end = normalize_intraday_csv(raw, out_dir / f"{cn_name}.csv", min_rows=min_rows)
    normalize_intraday_csv(raw, out_dir / f"{code}.csv", min_rows=min_rows)
    return rows, start, end


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync domestic futures 15m CSVs for context backfill.")
    parser.add_argument("--ssh-host", default="domestic-quant")
    parser.add_argument("--remote-root", default="C:/Users/Administrator/quant_futures")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--all-known", action="store_true")
    parser.add_argument("--out-dir", default=str(ROOT / "data" / "futures" / "15m"))
    parser.add_argument("--staging-dir", default=str(ROOT / "runtime" / "domestic_futures_15m_sync"))
    parser.add_argument("--min-rows", type=int, default=DEFAULT_MIN_ROWS)
    parser.add_argument("--scp-retries", type=int, default=3)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    staging_dir = Path(args.staging_dir)
    symbols = parse_symbols(args.symbols, args.all_known)
    failed: list[tuple[str, str]] = []
    synced = 0
    short_history: list[str] = []

    for symbol in symbols:
        cn_name = FUTURES_CN_NAMES.get(symbol)
        if not cn_name:
            failed.append((symbol, "missing FUTURES_CN_NAMES mapping"))
            continue
        try:
            raw = run_scp_15m(args.ssh_host, args.remote_root, symbol, staging_dir, retries=args.scp_retries)
            rows, start, end = write_dual_outputs(raw, out_dir, symbol, cn_name, args.min_rows)
            if rows < PREFERRED_MIN_ROWS:
                short_history.append(f"{symbol}({rows})")
            print(f"OK {symbol} -> {out_dir / cn_name} rows={rows} start={start} end={end}")
            synced += 1
        except Exception as exc:
            failed.append((symbol, str(exc)))
            print(f"FAIL {symbol}: {exc}", file=sys.stderr)

    if short_history:
        print(f"WARN short_history (<{PREFERRED_MIN_ROWS} bars): {', '.join(short_history)}")

    if failed:
        print("SYNC_PARTIAL" if synced else "SYNC_FAILED")
        for symbol, reason in failed:
            print(f"{symbol}: {reason}")
        return 1 if synced == 0 else 2

    print(f"SYNC_OK symbols={synced}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
