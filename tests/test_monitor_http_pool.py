"""海外挂单监控 HTTP 连接池复用语义单测（不触网）。"""
from __future__ import annotations

from fengji_pending_order_monitor import fetch_binance_prices, fetch_okx_prices, http_session, reset_http_session


def test_http_session_is_reused_until_reset() -> None:
    first = http_session()
    second = http_session()
    assert first is second
    reset_http_session()
    third = http_session()
    assert third is not first
    reset_http_session()


def test_reset_closes_previous_session() -> None:
    session = http_session()
    reset_http_session()
    # 对象已被 close：requests.Session.close 后可安全再 close，不再可发新请求依赖底层连接
    assert session is not http_session()
    reset_http_session()


def test_fetch_binance_prices_uses_session_pool(monkeypatch) -> None:
    calls: list[tuple] = []

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [{"symbol": "BTCUSDT", "price": "1.0"}, {"symbol": "SOLUSDT", "price": "2.0"}]

    class _Session:
        def get(self, url, timeout):
            calls.append((url, timeout))
            return _Resp()

    monkeypatch.setattr("fengji_pending_order_monitor.http_session", lambda: _Session())
    prices = fetch_binance_prices({"BTCUSDT"}, timeout=1.5, urls=["https://example.com/ticker"])
    assert prices == {"BTCUSDT": 1.0}
    assert calls and calls[0][1] == 1.5


def test_fetch_okx_uses_session_pool(monkeypatch) -> None:
    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"data": [{"last": "3.3"}]}

    class _Session:
        def get(self, url, params, timeout):
            return _Resp()

    monkeypatch.setattr("fengji_pending_order_monitor.http_session", lambda: _Session())
    prices = fetch_okx_prices({"HYPEUSDT"}, timeout=1.5)
    assert prices == {"HYPEUSDT": 3.3}
