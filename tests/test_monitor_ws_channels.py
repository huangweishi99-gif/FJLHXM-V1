from __future__ import annotations

from services.monitor_ws_channels import (
    build_delta_message,
    channel_fingerprints,
    diff_changed_channels,
    filter_snapshot_payload,
    parse_monitor_channels,
)


def test_parse_monitor_channels_defaults_to_all() -> None:
    assert parse_monitor_channels("") == frozenset({"positions", "runtime", "quotes"})
    assert parse_monitor_channels("quotes,positions") == frozenset({"quotes", "positions"})


def test_filter_snapshot_payload_respects_channels() -> None:
    payload = {
        "positions": [{"symbol": "RB"}],
        "runtime": {"items": []},
        "quotes": [{"symbol": "RB", "current_price": 1}],
    }
    out = filter_snapshot_payload(payload, frozenset({"quotes"}))
    assert "quotes" in out
    assert "positions" not in out


def test_diff_changed_channels() -> None:
    prev = {"quotes": "aaa", "positions": "bbb"}
    curr = {"quotes": "ccc", "positions": "bbb"}
    assert diff_changed_channels(prev, curr) == ["quotes"]


def test_build_delta_message_shape() -> None:
    snap = {
        "seq": 3,
        "mode": "read_only_monitor",
        "user_id": "u1",
        "plan": "pro",
        "status": {"ok": True},
        "payload": {
            "positions": [{"symbol": "RB"}],
            "quotes": [{"symbol": "RB", "current_price": 2}],
        },
    }
    msg = build_delta_message(
        snapshot=snap,
        changed=["quotes"],
        channels=frozenset({"positions", "quotes"}),
    )
    assert msg["type"] == "monitor.delta.v1"
    assert msg["changed"] == ["quotes"]
    assert "positions" not in msg["payload"]
    assert msg["payload"]["quotes"][0]["current_price"] == 2
