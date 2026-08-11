from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_DB = "data/market_data.sqlite"


TIMEFRAME_ALIASES = {
    "1D": "1D",
    "D1": "1D",
    "DAY": "1D",
    "DAILY": "1D",
    "日线": "1D",
    "1H": "1H",
    "H1": "1H",
    "60M": "1H",
    "60MIN": "1H",
    "60分钟": "1H",
    "15M": "15m",
    "M15": "15m",
    "15MIN": "15m",
    "5M": "5m",
    "M5": "5m",
    "5MIN": "5m",
}


def normalize_timeframe(value: str) -> str:
    text = value.strip().upper().replace("_", "").replace("-", "")
    return TIMEFRAME_ALIASES.get(text, value.strip())


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS instruments (
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (market, symbol)
        );

        CREATE TABLE IF NOT EXISTS bars (
            market TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            dt TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL DEFAULT 0,
            source TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (market, symbol, timeframe, dt)
        );

        CREATE INDEX IF NOT EXISTS idx_bars_lookup
            ON bars (market, symbol, timeframe, dt);
        """
    )
    conn.commit()


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [str(column).strip().lower() for column in out.columns]
    aliases = {
        "date": ["date", "datetime", "timestamp", "time", "open_time", "日期", "时间"],
        "open": ["open", "o", "开盘", "开盘价"],
        "high": ["high", "h", "最高", "最高价"],
        "low": ["low", "l", "最低", "最低价"],
        "close": ["close", "c", "收盘", "收盘价"],
        "volume": ["volume", "vol", "v", "成交量"],
    }
    picked: dict[str, str] = {}
    for canonical, names in aliases.items():
        for name in names:
            if name in out.columns:
                picked[canonical] = name
                break

    if not all(column in picked for column in ["date", "open", "high", "low", "close"]):
        if len(out.columns) < 5:
            raise ValueError("CSV columns cannot be mapped to OHLCV")
        # Some futures minute files have garbled Chinese headers. Their first six
        # columns are datetime, open, high, low, close, volume.
        positional = list(out.columns)
        picked = {
            "date": positional[0],
            "open": positional[1],
            "high": positional[2],
            "low": positional[3],
            "close": positional[4],
        }
        if len(positional) > 5:
            picked["volume"] = positional[5]

    result = pd.DataFrame()
    if "time" in out.columns and picked["date"] in {"date", "日期"}:
        time_text = out["time"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
        time_text = time_text.str.slice(0, 2) + ":" + time_text.str.slice(2, 4)
        result["date"] = pd.to_datetime(out[picked["date"]].astype(str) + " " + time_text, errors="coerce")
    elif "时间" in out.columns and picked["date"] in {"date", "日期"}:
        time_text = out["时间"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
        time_text = time_text.str.slice(0, 2) + ":" + time_text.str.slice(2, 4)
        result["date"] = pd.to_datetime(out[picked["date"]].astype(str) + " " + time_text, errors="coerce")
    else:
        result["date"] = pd.to_datetime(out[picked["date"]], errors="coerce")
    for column in ["open", "high", "low", "close"]:
        result[column] = pd.to_numeric(out[picked[column]], errors="coerce")
    if "volume" in picked:
        result["volume"] = pd.to_numeric(out[picked["volume"]], errors="coerce").fillna(0.0)
    else:
        result["volume"] = 0.0
    result = result.dropna(subset=["date", "open", "high", "low", "close"])
    result = result.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    return result


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    try:
        frame = pd.read_csv(csv_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        frame = pd.read_csv(csv_path, encoding="gbk")
    return normalize_columns(frame)


def upsert_instrument(conn: sqlite3.Connection, market: str, symbol: str, name: str = "", source: str = "") -> None:
    conn.execute(
        """
        INSERT INTO instruments (market, symbol, name, source)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(market, symbol) DO UPDATE SET
            name = COALESCE(NULLIF(excluded.name, ''), instruments.name),
            source = COALESCE(NULLIF(excluded.source, ''), instruments.source),
            updated_at = CURRENT_TIMESTAMP
        """,
        (market, symbol, name, source),
    )


def import_frame(
    conn: sqlite3.Connection,
    frame: pd.DataFrame,
    market: str,
    symbol: str,
    timeframe: str,
    source: str,
    name: str = "",
) -> int:
    if frame.empty:
        return 0
    market = market.upper()
    symbol = symbol.upper()
    timeframe = normalize_timeframe(timeframe)
    upsert_instrument(conn, market, symbol, name, source)
    rows = [
        (
            market,
            symbol,
            timeframe,
            pd.to_datetime(row.date).isoformat(sep=" "),
            float(row.open),
            float(row.high),
            float(row.low),
            float(row.close),
            float(row.volume),
            source,
        )
        for row in frame.itertuples(index=False)
    ]
    conn.executemany(
        """
        INSERT INTO bars (market, symbol, timeframe, dt, open, high, low, close, volume, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(market, symbol,timeframe,dt) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            source = excluded.source,
            updated_at = CURRENT_TIMESTAMP
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def import_csv(conn: sqlite3.Connection, path: str | Path, market: str, symbol: str, timeframe: str, name: str = "") -> int:
    csv_path = Path(path)
    frame = load_ohlcv_csv(csv_path)
    return import_frame(conn, frame, market, symbol, timeframe, str(csv_path), name=name)


def parse_crypto_file(path: Path) -> tuple[str, str] | None:
    match = re.match(r"^([A-Z0-9]+-USDT)_(1D|1H|15m|5m)_", path.name, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper(), normalize_timeframe(match.group(2))


def parse_a_stock_file(path: Path) -> tuple[str, str] | None:
    match = re.match(r"^(\d{6})_(1D|60m|1H|15m|5m)", path.name, re.IGNORECASE)
    if not match:
        return None
    return match.group(1), normalize_timeframe(match.group(2))


def parse_futures_daily_file(path: Path) -> tuple[str, str] | None:
    if "_日线" not in path.name:
        return None
    return path.name.split("_日线", 1)[0], "1D"


def parse_futures_minute_file(path: Path) -> tuple[str, str] | None:
    match = re.match(r"^(.+)_(60m|15m|5m)", path.name, re.IGNORECASE)
    if not match:
        return None
    return match.group(1), normalize_timeframe(match.group(2))


FUTURES_INTRADAY_TIMEFRAMES = ("5m", "15m", "1h")


def futures_intraday_dir(root: Path, timeframe: str) -> Path | None:
    for candidate in (root / "data" / "futures" / timeframe, root / "data" / timeframe):
        if candidate.is_dir():
            return candidate
    return None


def import_futures_local(conn: sqlite3.Connection, root: str | Path, *, market: str = "FUTURES") -> list[dict]:
    """Import short-code futures intraday CSVs from data/futures/{5m,15m,1h} or data/{tf}."""
    root_path = Path(root)
    try:
        packages = Path(__file__).resolve().parents[1] / "packages" / "fengji_core"
        if str(packages) not in sys.path:
            sys.path.insert(0, str(packages))
        from fengji_core.symbol_names import FUTURES_CN_NAMES  # noqa: WPS433
    except Exception as exc:
        raise RuntimeError("import_futures_local requires fengji_core.symbol_names.FUTURES_CN_NAMES") from exc

    valid_codes = set(FUTURES_CN_NAMES)
    rows: list[dict] = []
    for timeframe in FUTURES_INTRADAY_TIMEFRAMES:
        directory = futures_intraday_dir(root_path, timeframe)
        if directory is None:
            continue
        for path in sorted(directory.glob("*.csv")):
            symbol = path.stem.upper()
            if symbol not in valid_codes:
                continue
            try:
                count = import_csv(
                    conn,
                    path,
                    market,
                    symbol,
                    timeframe,
                    name=FUTURES_CN_NAMES.get(symbol, symbol),
                )
                status = "ok"
                error = ""
            except Exception as exc:
                count = 0
                status = "error"
                error = str(exc)
            item = {
                "path": str(path),
                "market": market,
                "symbol": symbol,
                "timeframe": timeframe,
                "rows": count,
                "status": status,
                "error": error,
            }
            rows.append(item)
            print(f"{status}: {market} {symbol} {timeframe} rows={count} {path.name}")
    return rows


def import_directory(conn: sqlite3.Connection, directory: str | Path, market: str, parser_name: str) -> list[dict]:
    root = Path(directory)
    parsers = {
        "crypto_okx": parse_crypto_file,
        "a_stock": parse_a_stock_file,
        "futures_daily": parse_futures_daily_file,
        "futures_minute": parse_futures_minute_file,
    }
    parser = parsers[parser_name]
    rows: list[dict] = []
    for path in sorted(root.glob("*.csv")):
        parsed = parser(path)
        if parsed is None:
            continue
        symbol, timeframe = parsed
        try:
            count = import_csv(conn, path, market, symbol, timeframe, name=symbol)
            status = "ok"
            error = ""
        except Exception as exc:
            count = 0
            status = "error"
            error = str(exc)
        item = {"path": str(path), "market": market, "symbol": symbol, "timeframe": timeframe, "rows": count, "status": status, "error": error}
        rows.append(item)
        print(f"{status}: {market} {symbol} {timeframe} rows={count} {path.name}")
    return rows


def coverage(conn: sqlite3.Connection, market: str = "", symbol: str = "") -> pd.DataFrame:
    where: list[str] = []
    params: list[str] = []
    if market:
        where.append("market = ?")
        params.append(market.upper())
    if symbol:
        where.append("symbol = ?")
        params.append(symbol.upper())
    sql = """
        SELECT market, symbol, timeframe, COUNT(*) AS rows, MIN(dt) AS start_dt, MAX(dt) AS end_dt
        FROM bars
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY market, symbol, timeframe ORDER BY market, symbol, timeframe"
    return pd.read_sql_query(sql, conn, params=params)


def export_csv(conn: sqlite3.Connection, market: str, symbol: str, timeframe: str, out: str | Path, start: str = "", end: str = "") -> int:
    market = market.upper()
    symbol = symbol.upper()
    timeframe = normalize_timeframe(timeframe)
    where = ["market = ?", "symbol = ?", "timeframe = ?"]
    params: list[str] = [market, symbol, timeframe]
    if start:
        where.append("dt >= ?")
        params.append(start)
    if end:
        where.append("dt <= ?")
        params.append(end)
    sql = f"""
        SELECT dt AS date, open, high, low, close, volume
        FROM bars
        WHERE {' AND '.join(where)}
        ORDER BY dt
    """
    frame = pd.read_sql_query(sql, conn, params=params)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_path, index=False, encoding="utf-8")
    return len(frame)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local SQLite market data store for FengJi backtests.")
    parser.add_argument("--db", default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    p = sub.add_parser("import-csv")
    p.add_argument("--market", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", required=True)
    p.add_argument("--csv", required=True)
    p.add_argument("--name", default="")

    p = sub.add_parser("import-crypto-okx")
    p.add_argument("--dir", default="data/crypto_okx")

    p = sub.add_parser("import-a-stock")
    p.add_argument("--dir", default="data/a_stock")

    p = sub.add_parser("import-futures")
    p.add_argument("--daily-dir", required=True)
    p.add_argument("--minute-dir", required=True)

    p = sub.add_parser("import-futures-local")
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))

    p = sub.add_parser("coverage")
    p.add_argument("--market", default="")
    p.add_argument("--symbol", default="")
    p.add_argument("--out", default="")

    p = sub.add_parser("export")
    p.add_argument("--market", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--start", default="")
    p.add_argument("--end", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    conn = connect(args.db)
    init_db(conn)

    if args.cmd == "init":
        print(f"Initialized market data DB: {args.db}")
    elif args.cmd == "import-csv":
        count = import_csv(conn, args.csv, args.market, args.symbol, args.timeframe, name=args.name)
        print(f"Imported rows={count} into {args.db}")
    elif args.cmd == "import-crypto-okx":
        rows = import_directory(conn, args.dir, "CRYPTO", "crypto_okx")
        pd.DataFrame(rows).to_csv(Path(args.db).with_name("market_data_import_crypto_okx.csv"), index=False, encoding="utf-8-sig")
    elif args.cmd == "import-a-stock":
        rows = import_directory(conn, args.dir, "A_STOCK", "a_stock")
        pd.DataFrame(rows).to_csv(Path(args.db).with_name("market_data_import_a_stock.csv"), index=False, encoding="utf-8-sig")
    elif args.cmd == "import-futures":
        rows = []
        rows.extend(import_directory(conn, args.daily_dir, "FUTURES", "futures_daily"))
        rows.extend(import_directory(conn, args.minute_dir, "FUTURES", "futures_minute"))
        pd.DataFrame(rows).to_csv(Path(args.db).with_name("market_data_import_futures.csv"), index=False, encoding="utf-8-sig")
    elif args.cmd == "import-futures-local":
        rows = import_futures_local(conn, args.root)
        out_csv = Path(args.db).with_name("market_data_import_futures_local.csv")
        pd.DataFrame(rows).to_csv(out_csv, index=False, encoding="utf-8-sig")
        ok = sum(1 for row in rows if row["status"] == "ok")
        print(f"import-futures-local ok={ok} total={len(rows)} log={out_csv}")
    elif args.cmd == "coverage":
        frame = coverage(conn, args.market, args.symbol)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(args.out, index=False, encoding="utf-8-sig")
        print(frame.to_string(index=False))
    elif args.cmd == "export":
        count = export_csv(conn, args.market, args.symbol, args.timeframe, args.out, args.start, args.end)
        print(f"Exported rows={count} to {args.out}")


if __name__ == "__main__":
    main()
