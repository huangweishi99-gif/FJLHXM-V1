from __future__ import annotations

from services.api.main import latest_quote_from_csv


def test_monitor_quote_reads_crypto_latest_close() -> None:
    quote = latest_quote_from_csv("SOLUSDT", "CRYPTO")

    assert quote["symbol"] == "SOLUSDT"
    assert quote["market"] == "CRYPTO"
    assert quote["current_price"] > 0
    assert quote["rows"] > 100
    assert quote["latest_time"]


def test_monitor_quote_reads_futures_latest_close() -> None:
    quote = latest_quote_from_csv("PVC", "FUTURES")

    assert quote["symbol"] == "PVC"
    assert quote["market"] == "FUTURES"
    assert quote["current_price"] > 0
    assert quote["rows"] > 10
    assert quote["source_file"] in {"PVC.csv", "PVCUSDT.csv"}
