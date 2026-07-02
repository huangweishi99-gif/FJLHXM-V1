from __future__ import annotations

import asyncio

from services.api import main
import monitor_ws_telemetry  # same module instance as services.api.main (sys.path)


class FakeWebSocket:
    def __init__(self, *, disconnect_after_messages: int | None = None) -> None:
        self.accepted = False
        self.messages: list[dict] = []
        self.closed_code: int | None = None
        self.disconnect_after_messages = disconnect_after_messages

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)
        if self.disconnect_after_messages is not None and len(self.messages) >= self.disconnect_after_messages:
            raise main.WebSocketDisconnect(code=1000)

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code


def _patch_monitor_sources(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "load_latest_opens",
        lambda: {
            "generated_at": "2026-06-05 19:30:00",
            "source": "paper_state",
            "positions": [
                {
                    "symbol": "PVC",
                    "market": "FUTURES",
                    "direction": "long",
                    "entry_price": 5000,
                }
            ],
        },
    )
    monkeypatch.setattr(
        main,
        "load_overseas_latest_opens",
        lambda: {
            "generated_at": "2026-06-05 19:30:00",
            "source": "paper_state",
            "market_scope": "CRYPTO",
            "positions": [],
        },
    )
    monkeypatch.setattr(
        main,
        "_build_paper_watchlist_runtime_response",
        lambda **_: {
            "user_id": "u1",
            "mode": "read_only_observation",
            "runtime_binding": "file_cache_signal_preview",
            "runtime_cache": {"status": "hit", "source": "file", "age_seconds": 12, "stale": False},
            "count": 1,
            "items": [
                {
                    "watchlist_id": "watch-1",
                    "symbol": "XRPUSDT",
                    "market": "CRYPTO",
                    "runtime_status": "ready",
                    "current_price": 0.52,
                    "latest_time": "2026-06-05 19:15:00",
                }
            ],
        },
    )

    def fake_quote(symbol: str, market: str) -> dict:
        return {
            "symbol": symbol.upper(),
            "market": market.upper(),
            "current_price": 5010 if symbol.upper() == "PVC" else 0.52,
            "latest_time": "2026-06-05",
            "rows": 10,
            "source_file": f"{symbol.upper()}.csv",
        }

    monkeypatch.setattr(main, "latest_quote_from_csv", fake_quote)


def test_build_monitor_snapshot_is_read_only_shape(monkeypatch) -> None:
    _patch_monitor_sources(monkeypatch)

    snapshot = main.build_monitor_snapshot(user_id="u1", plan="pro", seq=7)

    assert snapshot["type"] == "monitor.snapshot.v1"
    assert snapshot["seq"] == 7
    assert snapshot["mode"] == "read_only_monitor"
    assert snapshot["status"]["fallback_polling_allowed"] is True
    assert snapshot["payload"]["positions"][0]["symbol"] == "PVC"
    assert snapshot["payload"]["runtime"]["items"][0]["symbol"] == "XRPUSDT"
    assert {q["symbol"] for q in snapshot["payload"]["quotes"]} == {"PVC", "XRPUSDT"}


def test_monitor_websocket_sends_initial_snapshot(monkeypatch) -> None:
    _patch_monitor_sources(monkeypatch)
    main.MONITOR_WS_ACTIVE_CONNECTIONS.clear()
    fake_ws = FakeWebSocket(disconnect_after_messages=1)

    asyncio.run(main.monitor_websocket(fake_ws, user_id="u1", plan="pro", interval_seconds=2))

    assert fake_ws.accepted is True
    assert len(fake_ws.messages) == 1
    message = fake_ws.messages[0]
    assert message["type"] == "monitor.snapshot.v1"
    assert message["user_id"] == "u1"
    assert message["plan"] == "pro"
    assert message["payload"]["runtime"]["count"] == 1
    assert message["payload"]["quotes"][0]["ok"] is True
    assert main.MONITOR_WS_ACTIVE_CONNECTIONS == {}


def test_monitor_websocket_rejects_missing_user() -> None:
    main.MONITOR_WS_ACTIVE_CONNECTIONS.clear()
    fake_ws = FakeWebSocket()

    asyncio.run(main.monitor_websocket(fake_ws, user_id="", plan="pro", interval_seconds=5))

    assert fake_ws.accepted is True
    assert fake_ws.closed_code == 1008
    assert fake_ws.messages[0]["type"] == "monitor.auth_error.v1"
    assert fake_ws.messages[0]["policy"]["code"] == "missing_user"
    assert main.MONITOR_WS_ACTIVE_CONNECTIONS == {}


def test_monitor_websocket_rejects_non_pro_plan() -> None:
    main.MONITOR_WS_ACTIVE_CONNECTIONS.clear()
    fake_ws = FakeWebSocket()

    asyncio.run(main.monitor_websocket(fake_ws, user_id="u1", plan="standard", interval_seconds=5))

    assert fake_ws.accepted is True
    assert fake_ws.closed_code == 1008
    assert fake_ws.messages[0]["type"] == "monitor.auth_error.v1"
    assert fake_ws.messages[0]["policy"]["code"] == "plan_not_allowed"
    assert main.MONITOR_WS_ACTIVE_CONNECTIONS == {}


def test_monitor_websocket_limits_connections(monkeypatch) -> None:
    main.MONITOR_WS_ACTIVE_CONNECTIONS.clear()
    monkeypatch.setattr(main, "MONITOR_WS_MAX_CONNECTIONS_PER_USER", 1)
    main.MONITOR_WS_ACTIVE_CONNECTIONS["u1"] = 1
    fake_ws = FakeWebSocket()

    asyncio.run(main.monitor_websocket(fake_ws, user_id="u1", plan="pro", interval_seconds=5))

    assert fake_ws.accepted is True
    assert fake_ws.closed_code == 1013
    assert fake_ws.messages[0]["type"] == "monitor.error.v1"
    assert fake_ws.messages[0]["connection_limit"]["max_per_user"] == 1
    assert main.MONITOR_WS_ACTIVE_CONNECTIONS == {"u1": 1}
    main.MONITOR_WS_ACTIVE_CONNECTIONS.clear()


def test_monitor_ws_interval_clamps_by_plan() -> None:
    assert main.monitor_ws_interval_seconds("pro", 1) == 5
    assert main.monitor_ws_interval_seconds("standard", 1) == 60
    assert main.monitor_ws_interval_seconds("pro", 1000) == 900


def test_monitor_websocket_sends_heartbeat_when_payload_unchanged(monkeypatch) -> None:
    _patch_monitor_sources(monkeypatch)
    main.MONITOR_WS_ACTIVE_CONNECTIONS.clear()
    monitor_ws_telemetry.reset_stats_for_tests()
    fake_ws = FakeWebSocket(disconnect_after_messages=2)

    asyncio.run(main.monitor_websocket(fake_ws, user_id="u1", plan="pro", interval_seconds=2))

    assert len(fake_ws.messages) == 2
    assert fake_ws.messages[0]["type"] == "monitor.snapshot.v1"
    assert fake_ws.messages[0]["channels"] == ["positions", "quotes", "runtime"]
    assert fake_ws.messages[1]["type"] == "monitor.heartbeat.v1"
    assert fake_ws.messages[1]["since_last_change_seconds"] >= 0
    stats = monitor_ws_telemetry.get_stats(main.MONITOR_WS_ACTIVE_CONNECTIONS, max_per_user=3)
    assert stats["lifetime"]["snapshots_sent"] >= 1
    assert stats["lifetime"]["heartbeats_sent"] >= 1
    assert stats["lifetime"]["connects"] >= 1
    assert stats["lifetime"]["disconnects"] >= 1


def test_monitor_websocket_sends_delta_when_only_quotes_change(monkeypatch) -> None:
    _patch_monitor_sources(monkeypatch)
    main.MONITOR_WS_ACTIVE_CONNECTIONS.clear()
    monitor_ws_telemetry.reset_stats_for_tests()

    base = main.build_monitor_snapshot(user_id="u1", plan="pro", seq=1)
    quotes_v2 = [dict(row) for row in base["payload"]["quotes"]]
    quotes_v2[0] = {**quotes_v2[0], "current_price": 9999}
    snap2 = {
        **base,
        "seq": 2,
        "payload": {
            **base["payload"],
            "quotes": quotes_v2,
        },
    }
    calls = {"n": 0}

    def fake_build(**kwargs):
        calls["n"] += 1
        return base if calls["n"] == 1 else snap2

    monkeypatch.setattr(main, "build_monitor_snapshot", fake_build)
    fake_ws = FakeWebSocket(disconnect_after_messages=2)

    asyncio.run(main.monitor_websocket(fake_ws, user_id="u1", plan="pro", interval_seconds=0.01))

    assert fake_ws.messages[0]["type"] == "monitor.snapshot.v1"
    assert fake_ws.messages[1]["type"] == "monitor.delta.v1"
    assert fake_ws.messages[1]["changed"] == ["quotes"]
    assert fake_ws.messages[1]["payload"]["quotes"][0]["current_price"] == 9999


def test_monitor_ws_stats_endpoint() -> None:
    main.MONITOR_WS_ACTIVE_CONNECTIONS.clear()
    monitor_ws_telemetry.reset_stats_for_tests()
    main.MONITOR_WS_ACTIVE_CONNECTIONS["demo-user"] = 1

    stats = main.monitor_ws_stats()

    assert stats["active_total"] == 1
    assert stats["active_connections_by_user"]["demo-user"] == 1
    assert stats["max_connections_per_user"] == main.MONITOR_WS_MAX_CONNECTIONS_PER_USER
    assert "lifetime" in stats
    assert "recent_events" in stats


def test_snapshot_payload_fingerprint_stable(monkeypatch) -> None:
    _patch_monitor_sources(monkeypatch)
    snap1 = main.build_monitor_snapshot(user_id="u1", plan="pro", seq=1)
    snap2 = main.build_monitor_snapshot(user_id="u1", plan="pro", seq=99)
    assert main.snapshot_payload_fingerprint(snap1) == main.snapshot_payload_fingerprint(snap2)
