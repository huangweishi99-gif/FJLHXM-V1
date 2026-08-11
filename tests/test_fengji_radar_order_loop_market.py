from __future__ import annotations

from argparse import Namespace
import sys

from fengji_radar_order_loop import parse_args, resolve_market


def make_args(**overrides) -> Namespace:
    values = {
        "market": "auto",
        "symbols": "",
        "monitor_state": "",
        "data_dir": "data",
    }
    values.update(overrides)
    return Namespace(**values)


def test_resolve_market_explicit_overrides_environment() -> None:
    args = make_args(market="futures", symbols="BTCUSDT,ETHUSDT")

    assert resolve_market(args, {"FENGJI_MARKET": "crypto"}) == "futures"


def test_resolve_market_infers_futures_from_short_symbols() -> None:
    args = make_args(symbols="SA,FG,LC")

    assert resolve_market(args, {}) == "futures"


def test_resolve_market_infers_futures_from_monitor_state() -> None:
    args = make_args(monitor_state="runtime/fengji_pending_orders/futures_pending_state.json")

    assert resolve_market(args, {}) == "futures"


def test_resolve_market_keeps_crypto_for_usdt_symbols() -> None:
    args = make_args(symbols="BTCUSDT,IOUSDT")

    assert resolve_market(args, {}) == "crypto"


def test_parse_args_accepts_watchdog_market_and_m15_tail(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["fengji_radar_order_loop.py", "--market", "crypto", "--m15-tail", "960"],
    )

    args = parse_args()

    assert args.market == "crypto"
    assert args.m15_tail == 960
