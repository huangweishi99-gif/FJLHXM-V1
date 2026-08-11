from __future__ import annotations

from pathlib import Path

from scripts.discover_backtest_results import context_snapshots_ready, infer_from_path


def test_infer_a_stock_symbol_from_long_result_dir() -> None:
    root = Path("C:/Users/guangwan/Documents/New project")
    result_dir = root / "results" / "fengji_total_a_stock_002414_gaodehongwai"
    accepted = result_dir / "raw_fengji" / "accepted_trades.csv"
    item = infer_from_path(result_dir, accepted)
    assert item["market"] == "A_STOCK"
    assert item["symbol"] == "002414"
    assert item["data_dir"] == "data/a_stock"


def test_infer_futures_symbol_from_product_dir() -> None:
    root = Path("C:/Users/guangwan/Documents/New project")
    result_dir = root / "results" / "fengji_total_ds01_ds08_futures_15_5y" / "红枣"
    accepted = result_dir / "accepted_trades.csv"
    item = infer_from_path(result_dir, accepted)
    assert item["market"] == "FUTURES"
    assert item["symbol"] == "红枣"


def test_infer_crypto_realtime_uses_m15_timeframe() -> None:
    root = Path("C:/Users/guangwan/Documents/New project")
    result_dir = root / "results" / "crypto_realtime_monitor" / "20260520_125402" / "XRP-USDT"
    accepted = result_dir / "accepted_trades.csv"
    item = infer_from_path(result_dir, accepted)
    assert item["market"] == "CRYPTO"
    assert item["symbol"] == "XRPUSDT"
    assert item["timeframe"] == "15m"


def test_infer_us_stock_hyphen_ticker() -> None:
    root = Path("C:/Users/guangwan/Documents/New project")
    result_dir = root / "results" / "plan_a_us_stock_c1" / "BRK-B"
    accepted = result_dir / "raw_fengji" / "accepted_trades.csv"
    item = infer_from_path(result_dir, accepted)
    assert item["market"] == "US_STOCK"
    assert item["symbol"] == "BRK-B"


def test_context_snapshots_ready_requires_data_row(tmp_path: Path) -> None:
    assert context_snapshots_ready(tmp_path) is False
    empty = tmp_path / "trade_context_snapshots.csv"
    empty.write_text("", encoding="utf-8")
    assert context_snapshots_ready(tmp_path) is False
    header_only = tmp_path / "trade_context_snapshots.csv"
    header_only.write_text("trade_id,strategy_id\n", encoding="utf-8")
    assert context_snapshots_ready(tmp_path) is False
    header_only.write_text("trade_id,strategy_id\nabc,DS01\n", encoding="utf-8")
    assert context_snapshots_ready(tmp_path) is True
