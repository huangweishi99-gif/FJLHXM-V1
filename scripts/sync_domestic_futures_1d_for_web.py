from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.symbol_names import FUTURES_CN_NAMES  # noqa: E402


ACTIVE_FUTURES_CODES = (
    "AG",
    "AO",
    "AU",
    "BR",
    "CF",
    "CJ",
    "EB",
    "EC",
    "EG",
    "FG",
    "FU",
    "JD",
    "JM",
    "LC",
    "LH",
    "M",
    "MA",
    "NI",
    "OI",
    "P",
    "PG",
    "PP",
    "RB",
    "RU",
    "SA",
    "SC",
    "SF",
    "SH",
    "SI",
    "SP",
    "SR",
    "TA",
    "UR",
    "V",
)
DEFAULT_SYMBOLS = tuple(sorted(code for code in ACTIVE_FUTURES_CODES if code in FUTURES_CN_NAMES))
MAIN_CONTINUOUS_PREFIX = "KQ.m@"
DEFAULT_MIN_ROWS = 20


def parse_symbols(value: str, all_known: bool) -> list[str]:
    if all_known:
        return sorted(FUTURES_CN_NAMES)
    symbols = [item.strip().upper().replace("USDT", "") for item in value.split(",") if item.strip()]
    if not symbols:
        raise ValueError("no symbols requested")
    return symbols


def run_scp(ssh_host: str, remote_root: str, symbol: str, staging_dir: Path, retries: int = 3) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    target = staging_dir / f"{symbol}.csv"
    remote = f"{ssh_host}:{remote_root.rstrip('/')}/data/1d/{symbol}.csv"
    if target.exists():
        target.unlink()
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(
                ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", remote, str(target)],
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
        raise RuntimeError(f"downloaded empty file for {symbol}")
    return target


def _source_symbols(df: pd.DataFrame) -> list[str]:
    if "symbol" not in df.columns:
        raise ValueError("raw futures CSV missing symbol column; cannot verify actual main contract source")
    values = df["symbol"].dropna().astype(str).str.strip()
    return sorted({value for value in values if value})


def validate_actual_main_source(df: pd.DataFrame, src: Path) -> list[str]:
    symbols = _source_symbols(df)
    if not symbols:
        raise ValueError(f"{src.name} has no source symbols")
    main_continuous = [symbol for symbol in symbols if symbol.startswith(MAIN_CONTINUOUS_PREFIX)]
    if main_continuous:
        raise ValueError(
            f"{src.name} is still main-continuous data ({','.join(main_continuous)}); "
            "domestic data pump must write actual main-month contract data first"
        )
    return symbols


def normalize_daily_csv(src: Path, dst: Path, min_rows: int = DEFAULT_MIN_ROWS) -> tuple[int, str, str]:
    df = pd.read_csv(src)
    validate_actual_main_source(df, src)
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{src.name} missing columns: {sorted(missing)}")

    # Tianqin CSV stores daily bar timestamps as UTC wall time, e.g.
    # 2026-06-01 16:00:00 represents 2026-06-02 00:00:00 Asia/Shanghai.
    dates = pd.to_datetime(df["date"], errors="coerce") + pd.Timedelta(hours=8)
    out = pd.DataFrame(
        {
            "date": dates.dt.strftime("%Y-%m-%d"),
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df.get("volume"), errors="coerce"),
            "hold": pd.to_numeric(df.get("close_oi", df.get("hold")), errors="coerce"),
            "settle": pd.to_numeric(df.get("settle", df.get("close")), errors="coerce"),
        }
    )

    mask = out["date"].notna()
    for column in ("open", "high", "low", "close"):
        mask &= out[column].notna() & (out[column] > 0)
    mask &= out["high"] >= out[["open", "close", "low"]].max(axis=1)
    mask &= out["low"] <= out[["open", "close", "high"]].min(axis=1)
    # Guard against rare corrupt Tianqin rows with denormalized tiny high/close values.
    mask &= out["high"] / out["low"] < 1.5

    out = out.loc[mask].copy()
    out = out.drop_duplicates(subset=["date"], keep="last")
    out = out.sort_values("date").reset_index(drop=True)
    if len(out) < min_rows:
        raise ValueError(f"{src.name} has too few sane daily rows: {len(out)} < {min_rows}")

    out["volume"] = out["volume"].fillna(0).round().astype("int64")
    out["hold"] = out["hold"].fillna(0).round().astype("int64")
    out["settle"] = out["settle"].fillna(out["close"])

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    out.to_csv(tmp, index=False, encoding="utf-8")
    tmp.replace(dst)
    return len(out), str(out["date"].iloc[0]), str(out["date"].iloc[-1])


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync domestic futures 1d CSVs into Web Chinese-name data files.")
    parser.add_argument("--ssh-host", default="domestic-quant")
    parser.add_argument("--remote-root", default="C:/Users/Administrator/quant_futures")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Comma separated futures codes, e.g. AO,NI,PG")
    parser.add_argument("--all-known", action="store_true", help="Sync all codes listed in FUTURES_CN_NAMES")
    parser.add_argument("--out-dir", default=str(ROOT / "data" / "futures" / "1d"))
    parser.add_argument("--staging-dir", default=str(ROOT / "runtime" / "domestic_futures_1d_sync"))
    parser.add_argument("--min-rows", type=int, default=DEFAULT_MIN_ROWS)
    parser.add_argument("--scp-retries", type=int, default=3)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    staging_dir = Path(args.staging_dir)
    symbols = parse_symbols(args.symbols, args.all_known)
    failed: list[tuple[str, str]] = []

    for symbol in symbols:
        cn_name = FUTURES_CN_NAMES.get(symbol)
        if not cn_name:
            failed.append((symbol, "missing FUTURES_CN_NAMES mapping"))
            continue
        try:
            raw = run_scp(args.ssh_host, args.remote_root, symbol, staging_dir, retries=args.scp_retries)
            dst = out_dir / f"{cn_name}.csv"
            rows, start, end = normalize_daily_csv(raw, dst, min_rows=args.min_rows)
            print(f"OK {symbol} -> {dst} rows={rows} start={start} end={end}")
        except Exception as exc:  # keep syncing remaining symbols
            failed.append((symbol, str(exc)))
            print(f"FAIL {symbol}: {exc}", file=sys.stderr)

    if failed:
        print("SYNC_FAILED")
        for symbol, reason in failed:
            print(f"{symbol}: {reason}")
        return 1

    print(f"SYNC_OK symbols={len(symbols)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
