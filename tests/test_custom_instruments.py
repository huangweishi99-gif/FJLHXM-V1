from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks, HTTPException

ROOT = Path(__file__).resolve().parents[1]
SERVICES = str(ROOT / "services")
if SERVICES not in sys.path:
    sys.path.insert(0, SERVICES)

from db.custom_instruments import (  # noqa: E402
    check_custom_request_quota,
    custom_month_bounds,
    normalize_custom_plan,
    normalize_custom_strategies,
    normalize_custom_symbol,
    refresh_custom_request_from_backtest,
)
from db.models import CustomInstrumentRequest  # noqa: E402
from services.api.main import (  # noqa: E402
    CustomInstrumentRequestCreate,
    PaperWatchlistStatusUpdate,
    create_custom_request,
    patch_paper_watchlist_status,
    run_custom_crypto_request_once,
    run_custom_market_request_once,
)
from services.api.main import get_paper_watchlist, get_paper_watchlist_runtime  # noqa: E402


def _auth_user(*, plan_id: str = "pro", user_id: str = "u-test") -> dict:
    return {
        "id": user_id,
        "account": "custom@test.com",
        "password_hash": "pbkdf2_sha256$120000$00$00",
        "plan_id": plan_id,
        "plan_expires_at": "2026-12-31T00:00:00+00:00",
        "created_at": "2026-06-01T00:00:00+00:00",
    }
from services.crypto_ingest import (  # noqa: E402
    crypto_timeframe_csv_path,
    missing_crypto_timeframes,
    normalize_timeframe,
    okx_inst_id,
)
from services.watchlist_runtime import (  # noqa: E402
    build_watchlist_runtime_snapshot,
    build_watchlist_signal_preview,
    clear_watchlist_signal_preview_cache,
)
from services.watchlist_runtime_file_cache import (  # noqa: E402
    load_watchlist_runtime_cache,
    runtime_cache_age_seconds,
    save_watchlist_runtime_cache,
)


def test_normalize_custom_symbol_crypto_adds_usdt() -> None:
    assert normalize_custom_symbol("crypto", "eth") == "ETHUSDT"
    assert normalize_custom_symbol("CRYPTO", "btc-usdt") == "BTCUSDT"


def test_normalize_custom_symbol_a_stock_pads_code() -> None:
    assert normalize_custom_symbol("A_STOCK", "21") == "000021"
    assert normalize_custom_symbol("A_STOCK", "000021") == "000021"


def test_normalize_custom_symbol_futures_and_us_stock() -> None:
    assert normalize_custom_symbol("FUTURES", "pvc") == "PVC"
    assert normalize_custom_symbol("US_STOCK", "brk.b") == "BRK_B"


def test_okx_inst_id_normalizes_crypto_symbol() -> None:
    assert okx_inst_id("eth") == "ETH-USDT"
    assert okx_inst_id("btc-usdt") == "BTC-USDT"


def test_crypto_timeframe_helpers_normalize_and_resolve_paths(tmp_path: Path) -> None:
    assert normalize_timeframe("1d") == "D1"
    assert normalize_timeframe("1h") == "H1"
    assert normalize_timeframe("15m") == "M15"
    assert crypto_timeframe_csv_path("eth", "1h").name == "ETHUSDT.csv"
    with patch("services.crypto_ingest.crypto_timeframe_csv_path", side_effect=lambda _s, tf: tmp_path / f"{tf}.csv"):
        (tmp_path / "D1.csv").write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
        assert missing_crypto_timeframes("ETH", timeframes=["D1", "H1", "M15"]) == ["H1", "M15"]


def test_normalize_custom_symbol_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        normalize_custom_symbol("CRYPTO", "eth;drop")


def test_normalize_custom_strategies_defaults_and_dedupes() -> None:
    assert normalize_custom_strategies([]) == ["TOTAL"]
    assert normalize_custom_strategies(["ds03", "DS03", "total"]) == ["DS03", "TOTAL"]


def test_custom_plan_and_month_bounds_helpers() -> None:
    assert normalize_custom_plan(None) == "free"
    assert normalize_custom_plan(" Pro ") == "pro"
    start, end = custom_month_bounds(datetime(2026, 6, 15, 12, 30, tzinfo=timezone.utc))
    assert start.isoformat() == "2026-06-01T00:00:00+00:00"
    assert end.isoformat() == "2026-07-01T00:00:00+00:00"


def test_custom_quota_helper_rejects_unknown_plan_before_db() -> None:
    assert check_custom_request_quota("u1", "enterprise") == {
        "allowed": False,
        "plan_id": "enterprise",
        "limit": 0,
        "used": 0,
        "remaining": 0,
    }


def test_custom_instrument_request_bounds_years() -> None:
    req = CustomInstrumentRequestCreate(market="CRYPTO", symbol="ETH", strategies=["DS03"], years=5)
    assert req.years == 5
    assert req.strategies == ["DS03"]


def test_custom_instrument_request_rejects_free_plan_before_db() -> None:
    req = CustomInstrumentRequestCreate(market="CRYPTO", symbol="ETH", plan_id="free")
    with pytest.raises(HTTPException) as exc:
        create_custom_request(req, BackgroundTasks(), auth_user=_auth_user(plan_id="free"))
    assert exc.value.status_code == 403
    assert "free plan" in exc.value.detail


def test_custom_instrument_request_requires_login() -> None:
    req = CustomInstrumentRequestCreate(market="CRYPTO", symbol="ETH", plan_id="pro", user_id="forged")
    with pytest.raises(HTTPException) as exc:
        create_custom_request(req, BackgroundTasks(), auth_user=None)
    assert exc.value.status_code == 401
    assert "login required" in exc.value.detail


def test_custom_instrument_request_accepts_futures_missing_csv() -> None:
    req = CustomInstrumentRequestCreate(market="FUTURES", symbol="NEWFUT", plan_id="pro", user_id="u-fut")
    row = {"id": "req-fut", "symbol": "NEWFUT", "status": "ingesting"}
    with (
        patch(
            "services.api.main.check_custom_request_quota",
            return_value={"allowed": True, "plan_id": "pro", "limit": 20, "used": 0, "remaining": 20},
        ),
        patch("services.api.main.resolve_csv", side_effect=FileNotFoundError("missing")),
        patch("services.api.main.create_custom_instrument_request", return_value=row) as create_request,
    ):
        tasks = BackgroundTasks()
        result = create_custom_request(req, tasks, auth_user=_auth_user(plan_id="pro", user_id="u-fut"))
    assert result == row
    assert create_request.call_args.kwargs["request_extra"] == {"missing_data": True}


def test_custom_instrument_request_ignores_forged_body_plan_id() -> None:
    req = CustomInstrumentRequestCreate(
        market="CRYPTO",
        symbol="ETH",
        plan_id="pro",
        user_id="forged-user",
        strategies=["DS01"],
        years=1,
    )
    with pytest.raises(HTTPException) as exc:
        create_custom_request(req, BackgroundTasks(), auth_user=_auth_user(plan_id="free", user_id="jwt-user"))
    assert exc.value.status_code == 403
    assert "free plan" in exc.value.detail


def test_custom_instrument_request_rejects_expired_subscription() -> None:
    req = CustomInstrumentRequestCreate(
        market="CRYPTO",
        symbol="ETH",
        strategies=["DS01"],
        years=1,
    )
    expired_user = {
        **_auth_user(plan_id="standard", user_id="expired-user"),
        "plan_expires_at": "2026-06-01T00:00:00+00:00",
    }
    with pytest.raises(HTTPException) as exc:
        create_custom_request(req, BackgroundTasks(), auth_user=expired_user)
    assert exc.value.status_code == 403
    assert "expired" in exc.value.detail


def test_custom_instrument_request_requires_user_id_for_paid_quota_before_db() -> None:
    req = CustomInstrumentRequestCreate(market="CRYPTO", symbol="ETH", plan_id="pro")
    with (
        patch(
            "services.api.main.check_custom_request_quota",
            return_value={"allowed": True, "plan_id": "pro", "limit": 20, "used": 0, "remaining": 20},
        ),
        patch("services.api.main.resolve_csv", side_effect=FileNotFoundError("missing")),
        patch("services.api.main.create_custom_instrument_request", return_value={"id": "req-login", "status": "ingesting"}),
    ):
        result = create_custom_request(req, BackgroundTasks(), auth_user=_auth_user(plan_id="pro", user_id="jwt-user"))
    assert result["id"] == "req-login"


def test_custom_instrument_request_rejects_quota_exceeded_before_csv() -> None:
    req = CustomInstrumentRequestCreate(
        market="CRYPTO",
        symbol="ETH",
        plan_id="standard",
        user_id="u1",
        strategies=["DS01"],
    )
    with patch(
        "services.api.main.check_custom_request_quota",
        return_value={"allowed": False, "plan_id": "standard", "limit": 3, "used": 3, "remaining": 0},
    ):
        with pytest.raises(HTTPException) as exc:
            create_custom_request(req, BackgroundTasks(), auth_user=_auth_user(plan_id="standard", user_id="u1"))
    assert exc.value.status_code == 429
    assert "standard 3/3" in exc.value.detail


def test_custom_instrument_request_passes_quota_snapshot_to_ingest_request() -> None:
    req = CustomInstrumentRequestCreate(
        market="CRYPTO",
        symbol="XRP",
        plan_id="standard",
        user_id="quota-user",
        years=1,
        strategies=["DS01"],
    )
    row = {
        "id": "req-1",
        "symbol": "XRPUSDT",
        "status": "ingesting",
        "quota": {"plan_id": "standard", "limit": 3, "used_before": 1, "remaining_after": 1},
    }
    with (
        patch(
            "services.api.main.check_custom_request_quota",
            return_value={"allowed": True, "plan_id": "standard", "limit": 3, "used": 1, "remaining": 2},
        ),
        patch("services.api.main.resolve_csv", side_effect=FileNotFoundError("missing")),
        patch("services.api.main.create_custom_instrument_request", return_value=row) as create_request,
    ):
        result = create_custom_request(
            req,
            BackgroundTasks(),
            auth_user=_auth_user(plan_id="standard", user_id="quota-user"),
        )
    assert result == row
    create_request.assert_called_once()
    assert create_request.call_args.kwargs["quota"] == {
        "plan_id": "standard",
        "limit": 3,
        "used_before": 1,
        "remaining_after": 1,
    }
    assert create_request.call_args.kwargs["request_extra"] == {"missing_timeframes": ["D1", "H1", "M15"]}


def test_custom_instrument_request_ingests_when_intraday_timeframes_missing() -> None:
    req = CustomInstrumentRequestCreate(
        market="CRYPTO",
        symbol="ETH",
        plan_id="pro",
        user_id="u-timeframes",
        years=1,
    )
    row = {"id": "req-tf", "symbol": "ETHUSDT", "status": "ingesting"}
    with (
        patch(
            "services.api.main.check_custom_request_quota",
            return_value={"allowed": True, "plan_id": "pro", "limit": 20, "used": 1, "remaining": 19},
        ),
        patch("services.api.main.resolve_csv", return_value=Path("data/overseas_1d/ETHUSDT.csv")),
        patch("services.api.main.missing_crypto_timeframes", return_value=["H1", "M15"]),
        patch("services.api.main.create_custom_instrument_request", return_value=row) as create_request,
    ):
        result = create_custom_request(
            req,
            BackgroundTasks(),
            auth_user=_auth_user(plan_id="pro", user_id="u-timeframes"),
        )
    assert result["status"] == "ingesting"
    assert create_request.call_args.kwargs["request_extra"] == {"missing_timeframes": ["H1", "M15"]}


def test_refresh_custom_request_enables_paper_watchlist_after_backtest_success() -> None:
    row = CustomInstrumentRequest(
        id="req-paper-1",
        user_id="u1",
        plan_id="pro",
        market="CRYPTO",
        symbol="XRPUSDT",
        name="XRP",
        status="backtesting",
        strategies_json=["TOTAL"],
        years=1,
        enable_paper=True,
        backtest_job_id="job-1",
        request_json={},
    )
    watchlist = {
        "id": "watch-1",
        "request_id": "req-paper-1",
        "user_id": "u1",
        "market": "CRYPTO",
        "symbol": "XRPUSDT",
        "status": "pending_runtime",
    }
    with (
        patch("db.custom_instruments.get_backtest_job", return_value={"id": "job-1", "status": "succeeded"}),
        patch("db.custom_instruments.create_or_get_paper_watchlist_entry", return_value=watchlist) as create_watch,
    ):
        refresh_custom_request_from_backtest(row)
    assert row.status == "paper_enabled"
    assert row.error_message is None
    assert row.request_json["paper_watchlist"] == watchlist
    create_watch.assert_called_once()


def test_refresh_custom_request_does_not_enable_paper_before_backtest_success() -> None:
    row = CustomInstrumentRequest(
        id="req-paper-2",
        user_id="u1",
        plan_id="pro",
        market="CRYPTO",
        symbol="XRPUSDT",
        status="backtesting",
        strategies_json=["TOTAL"],
        years=1,
        enable_paper=True,
        backtest_job_id="job-2",
        request_json={},
    )
    with (
        patch("db.custom_instruments.get_backtest_job", return_value={"id": "job-2", "status": "running"}),
        patch("db.custom_instruments.create_or_get_paper_watchlist_entry") as create_watch,
    ):
        refresh_custom_request_from_backtest(row)
    assert row.status == "backtesting"
    create_watch.assert_not_called()


def test_get_paper_watchlist_delegates_to_db_helper() -> None:
    rows = [{"id": "watch-1", "user_id": "u1", "symbol": "XRPUSDT"}]
    with patch("services.api.main.list_paper_watchlist", return_value=rows) as list_watch:
        assert get_paper_watchlist(user_id="u1", status="pending_runtime", limit=10) == rows
    list_watch.assert_called_once_with(user_id="u1", status="pending_runtime", limit=10)


def test_patch_paper_watchlist_status_delegates_to_db_helper() -> None:
    row = {"id": "watch-1", "user_id": "u1", "status": "cancelled"}
    request = PaperWatchlistStatusUpdate(user_id="u1", status="cancelled")
    with patch("services.api.main.update_paper_watchlist_status", return_value=row) as update_watch:
        assert patch_paper_watchlist_status("watch-1", request) == row
    update_watch.assert_called_once_with(watchlist_id="watch-1", user_id="u1", status="cancelled")


def test_patch_paper_watchlist_status_rejects_invalid_status_before_db() -> None:
    request = PaperWatchlistStatusUpdate(user_id="u1", status="pending_runtime")
    with patch("services.api.main.update_paper_watchlist_status") as update_watch:
        with pytest.raises(HTTPException) as exc:
            patch_paper_watchlist_status("watch-1", request)
    assert exc.value.status_code == 400
    update_watch.assert_not_called()


def test_patch_paper_watchlist_status_returns_404_for_missing_row() -> None:
    request = PaperWatchlistStatusUpdate(user_id="u1", status="paused")
    with patch("services.api.main.update_paper_watchlist_status", return_value=None):
        with pytest.raises(HTTPException) as exc:
            patch_paper_watchlist_status("missing-watch", request)
    assert exc.value.status_code == 404


def test_watchlist_runtime_snapshot_ready_from_three_timeframes(tmp_path: Path) -> None:
    for tf, ts, close in (
        ("D1", "2026-06-05", "1.10"),
        ("H1", "2026-06-05 01:00:00", "1.20"),
        ("M15", "2026-06-05 01:15:00", "1.30"),
    ):
        (tmp_path / f"{tf}.csv").write_text(
            "timestamp,open,high,low,close,volume\n"
            f"{ts},1.00,1.50,0.90,{close},100\n",
            encoding="utf-8",
        )
    entry = {
        "id": "watch-1",
        "request_id": "req-1",
        "user_id": "u1",
        "market": "CRYPTO",
        "symbol": "XRPUSDT",
        "strategies": ["TOTAL"],
        "status": "pending_runtime",
    }
    with patch("services.watchlist_runtime.crypto_timeframe_csv_path", side_effect=lambda _s, tf: tmp_path / f"{tf}.csv"):
        snapshot = build_watchlist_runtime_snapshot(entry)
    assert snapshot["runtime_status"] == "ready"
    assert snapshot["current_price"] == 1.30
    assert snapshot["latest_time"] == "2026-06-05 01:15:00"
    assert snapshot["timeframes"]["D1"]["ok"] is True
    assert snapshot["signal_preview"] is None


def test_watchlist_runtime_snapshot_can_attach_read_only_signal_preview(tmp_path: Path) -> None:
    for tf, ts, close in (
        ("D1", "2026-06-05", "1.10"),
        ("H1", "2026-06-05 01:00:00", "1.20"),
        ("M15", "2026-06-05 01:15:00", "1.30"),
    ):
        (tmp_path / f"{tf}.csv").write_text(
            "timestamp,open,high,low,close,volume\n"
            f"{ts},1.00,1.50,0.90,{close},100\n",
            encoding="utf-8",
        )
    entry = {
        "id": "watch-preview",
        "request_id": "req-preview",
        "user_id": "u1",
        "market": "CRYPTO",
        "symbol": "XRPUSDT",
        "strategies": ["TOTAL"],
        "status": "pending_runtime",
    }
    preview = {
        "mode": "read_only_signal_preview",
        "strategy_id": "TOTAL",
        "latest_signal": {"time": "2026-06-05", "side": "long", "price": 1.1},
    }
    with (
        patch("services.watchlist_runtime.crypto_timeframe_csv_path", side_effect=lambda _s, tf: tmp_path / f"{tf}.csv"),
        patch("services.watchlist_runtime.build_watchlist_signal_preview", return_value=preview) as build_preview,
    ):
        snapshot = build_watchlist_runtime_snapshot(entry, include_signal_preview=True)
    assert snapshot["runtime_status"] == "ready"
    assert snapshot["signal_preview"] == preview
    assert any(s["type"] == "signal_preview" for s in snapshot["signals"])
    build_preview.assert_called_once_with(tmp_path / "D1.csv")


def test_watchlist_signal_preview_uses_cache_for_unchanged_d1_csv(tmp_path: Path) -> None:
    clear_watchlist_signal_preview_cache()
    d1_path = tmp_path / "D1.csv"
    d1_path.write_text("timestamp,open,high,low,close,volume\n2026-06-05,1,2,0.5,1.5,100\n", encoding="utf-8")
    bundle = {
        "strategy_id": "TOTAL",
        "engine_version": "test-engine",
        "years": 1,
        "bars": [{"t": "2026-06-05"}],
        "markers": [{"t": "2026-06-05", "kind": "entry", "side": "long", "price": 1.5, "trade_no": 1}],
        "metrics": {"trades": 1, "win_rate": 1.0, "total_return": 0.1, "bad_audits": 0},
    }
    with patch("services.watchlist_runtime.build_chart_bundle", return_value=bundle) as build_bundle:
        first = build_watchlist_signal_preview(d1_path)
        second = build_watchlist_signal_preview(d1_path)
    assert first["cache"]["status"] == "miss"
    assert second["cache"]["status"] == "hit"
    assert second["latest_signal"]["side"] == "long"
    build_bundle.assert_called_once()
    clear_watchlist_signal_preview_cache()


def test_watchlist_runtime_file_cache_roundtrip(tmp_path: Path) -> None:
    payload = {
        "user_id": "u/cache",
        "runtime_binding": "file_cache_signal_preview",
        "status_filter": "pending_runtime",
        "items": [{"watchlist_id": "watch-1"}],
    }
    path = save_watchlist_runtime_cache("u/cache", payload, tmp_path)
    assert path.name == "u_cache.json"
    loaded = load_watchlist_runtime_cache("u/cache", tmp_path)
    assert loaded is not None
    assert loaded["items"][0]["watchlist_id"] == "watch-1"
    assert loaded["_cache_file"] == str(path)


def test_watchlist_runtime_cache_age_seconds() -> None:
    payload = {"generated_at": "2026-06-05T00:00:00+00:00"}
    now = datetime(2026, 6, 5, 0, 2, 30, tzinfo=timezone.utc)
    assert runtime_cache_age_seconds(payload, now=now) == 150


def test_watchlist_runtime_snapshot_reports_missing_timeframes(tmp_path: Path) -> None:
    (tmp_path / "D1.csv").write_text(
        "timestamp,open,high,low,close,volume\n2026-06-05,1,2,0.5,1.5,100\n",
        encoding="utf-8",
    )
    entry = {
        "id": "watch-2",
        "request_id": "req-2",
        "user_id": "u1",
        "market": "CRYPTO",
        "symbol": "XRPUSDT",
        "strategies": ["TOTAL"],
        "status": "pending_runtime",
    }
    with patch("services.watchlist_runtime.crypto_timeframe_csv_path", side_effect=lambda _s, tf: tmp_path / f"{tf}.csv"):
        snapshot = build_watchlist_runtime_snapshot(entry)
    assert snapshot["runtime_status"] == "data_missing"
    assert snapshot["signals"][0]["missing_timeframes"] == ["H1", "M15"]


def test_watchlist_runtime_snapshot_astock_ready_from_d1_only(tmp_path: Path) -> None:
    d1_path = tmp_path / "000021_1D_qfq.csv"
    d1_path.write_text(
        "date,open,high,low,close,volume\n2026-06-05,10,11,9,10.5,1000\n",
        encoding="utf-8",
    )
    entry = {
        "id": "watch-a",
        "request_id": "req-a",
        "user_id": "u1",
        "market": "A_STOCK",
        "symbol": "000021",
        "strategies": ["TOTAL"],
        "status": "pending_runtime",
    }
    with (
        patch("services.watchlist_runtime.runtime_timeframe_csv_path", return_value=d1_path),
        patch("services.watchlist_runtime.build_watchlist_signal_preview") as build_preview,
    ):
        snapshot = build_watchlist_runtime_snapshot(entry, include_signal_preview=True)
    assert snapshot["runtime_status"] == "ready"
    assert snapshot["current_price"] == 10.5
    assert snapshot["latest_time"] == "2026-06-05"
    assert snapshot["timeframes"]["D1"]["ok"] is True
    assert snapshot["signal_preview"] is None
    assert any(s["message"] == "signal preview not attached for this market yet" for s in snapshot["signals"])
    build_preview.assert_not_called()


def test_watchlist_runtime_snapshot_futures_reports_missing_d1(tmp_path: Path) -> None:
    missing_path = tmp_path / "LC.csv"
    entry = {
        "id": "watch-f",
        "request_id": "req-f",
        "user_id": "u1",
        "market": "FUTURES",
        "symbol": "LC",
        "strategies": ["TOTAL"],
        "status": "pending_runtime",
    }
    with patch("services.watchlist_runtime.runtime_timeframe_csv_path", return_value=missing_path):
        snapshot = build_watchlist_runtime_snapshot(entry)
    assert snapshot["runtime_status"] == "data_missing"
    assert snapshot["current_price"] is None
    assert snapshot["timeframes"]["D1"] == {"ok": False, "path": str(missing_path), "error": "missing_csv"}
    assert snapshot["signals"][0]["missing_timeframes"] == ["D1"]


def test_watchlist_runtime_snapshot_us_stock_ready_from_d1_only(tmp_path: Path) -> None:
    d1_path = tmp_path / "AAPL_1D.csv"
    d1_path.write_text(
        "datetime,open,high,low,close,volume\n2026-06-05,200,205,198,204,1000\n",
        encoding="utf-8",
    )
    entry = {
        "id": "watch-us",
        "request_id": "req-us",
        "user_id": "u1",
        "market": "US_STOCK",
        "symbol": "AAPL",
        "strategies": ["TOTAL"],
        "status": "pending_runtime",
    }
    with patch("services.watchlist_runtime.runtime_timeframe_csv_path", return_value=d1_path):
        snapshot = build_watchlist_runtime_snapshot(entry)
    assert snapshot["runtime_status"] == "ready"
    assert snapshot["current_price"] == 204
    assert snapshot["latest_time"] == "2026-06-05"
    assert snapshot["timeframes"]["D1"]["rows"] == 1


def test_get_paper_watchlist_runtime_returns_read_only_snapshot() -> None:
    rows = [{"id": "watch-1", "user_id": "u1", "market": "CRYPTO", "symbol": "XRPUSDT", "status": "pending_runtime"}]
    snapshots = [{"watchlist_id": "watch-1", "runtime_status": "ready"}]
    with (
        patch("services.api.main.list_paper_watchlist", return_value=rows) as list_watch,
        patch("services.api.main.build_watchlist_runtime_snapshots", return_value=snapshots) as build_snapshots,
    ):
        result = get_paper_watchlist_runtime(
            user_id="u1",
            status="pending_runtime",
            limit=10,
            include_signal_preview=True,
        )
    assert result["mode"] == "read_only_observation"
    assert result["runtime_binding"] == "csv_snapshot_with_signal_preview"
    assert result["items"] == snapshots
    list_watch.assert_called_once_with(user_id="u1", status="pending_runtime", limit=10)
    build_snapshots.assert_called_once_with(rows, include_signal_preview=True)


def test_get_paper_watchlist_runtime_prefers_file_cache_when_enabled() -> None:
    cached = {
        "user_id": "u1",
        "runtime_binding": "file_cache_signal_preview",
        "status_filter": "pending_runtime",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "_cache_file": "runtime/watchlist_runtime_cache/u1.json",
        "items": [
            {"watchlist_id": "watch-1", "runtime_status": "ready"},
            {"watchlist_id": "watch-2", "runtime_status": "ready"},
        ],
    }
    with (
        patch("services.api.main.load_watchlist_runtime_cache", return_value=cached) as load_cache,
        patch("services.api.main.list_paper_watchlist") as list_watch,
    ):
        result = get_paper_watchlist_runtime(
            user_id="u1",
            status="pending_runtime",
            limit=1,
            include_signal_preview=True,
            prefer_runtime_cache=True,
        )
    assert result["runtime_binding"] == "file_cache_signal_preview"
    assert result["runtime_cache"]["status"] == "hit"
    assert result["runtime_cache"]["stale"] is False
    assert result["runtime_cache"]["age_seconds"] is not None
    assert result["count"] == 1
    assert result["items"][0]["watchlist_id"] == "watch-1"
    load_cache.assert_called_once_with("u1")
    list_watch.assert_not_called()


def test_custom_crypto_worker_ingests_then_runs_backtest() -> None:
    request_row = {
        "id": "req-1",
        "status": "ingesting",
        "market": "CRYPTO",
        "symbol": "XRPUSDT",
        "strategies": ["TOTAL"],
        "years": 1,
        "user_id": "u1",
    }
    ingest_meta = {
        "symbol": "XRPUSDT",
        "inst_id": "XRP-USDT",
        "rows": 100,
        "start": "2026-01-01",
        "end": "2026-06-01",
        "source": "okx_history_candles_1D",
        "path": "data/overseas_1d/XRPUSDT.csv",
    }
    job = {"id": "job-1", "status": "queued"}
    with (
        patch("services.api.main.get_custom_instrument_request", return_value=request_row),
        patch("services.api.main.ingest_crypto_timeframes", return_value=ingest_meta) as ingest,
        patch("services.api.main.create_backtest_job", return_value=job) as create_job,
        patch("services.api.main.update_custom_instrument_request") as update_request,
        patch("services.api.main.run_backtest_job_once") as run_job,
    ):
        run_custom_crypto_request_once("req-1")
    ingest.assert_called_once_with("XRPUSDT")
    create_job.assert_called_once()
    update_request.assert_called_once_with(
        "req-1",
        status="backtesting",
        backtest_job_id="job-1",
        request_patch={"ingest": ingest_meta},
    )
    run_job.assert_called_once_with("job-1")


def test_custom_market_worker_fails_when_ingest_fails() -> None:
    request_row = {
        "id": "req-astock",
        "market": "A_STOCK",
        "symbol": "999999",
        "status": "ingesting",
        "strategies": ["TOTAL"],
        "years": 1,
        "user_id": "u1",
    }
    with (
        patch("services.api.main.get_custom_instrument_request", return_value=request_row),
        patch("services.api.main.resolve_csv", side_effect=FileNotFoundError("missing")),
        patch(
            "services.api.main.ingest_custom_market_d1",
            side_effect=ValueError("A-share D1 too short"),
        ) as ingest,
        patch("services.api.main.update_custom_instrument_request") as update_request,
    ):
        run_custom_market_request_once("req-astock")
    ingest.assert_called_once()
    update_request.assert_called_once()
    assert update_request.call_args.kwargs["status"] == "failed"
    assert "too short" in update_request.call_args.kwargs["error_message"]


def test_custom_market_worker_ingests_then_runs_backtest() -> None:
    request_row = {
        "id": "req-us",
        "market": "US_STOCK",
        "symbol": "AAPL",
        "status": "ingesting",
        "strategies": ["TOTAL"],
        "years": 1,
        "user_id": "u1",
    }
    job = {"id": "job-aapl", "status": "queued"}
    ingest_meta = {"market": "US_STOCK", "symbol": "AAPL", "path": "data/us_stock/AAPL_1D.csv", "rows": 200}
    with (
        patch("services.api.main.get_custom_instrument_request", return_value=request_row),
        patch("services.api.main.resolve_csv", side_effect=[FileNotFoundError("missing"), Path("data/us_stock/AAPL_1D.csv")]),
        patch("services.api.main.ingest_custom_market_d1", return_value=ingest_meta) as ingest,
        patch("services.api.main.create_backtest_job", return_value=job) as create_job,
        patch("services.api.main.update_custom_instrument_request") as update_request,
        patch("services.api.main.run_backtest_job_once") as run_job,
        patch("services.api.main.get_custom_instrument_request", side_effect=[request_row, request_row]),
    ):
        run_custom_market_request_once("req-us")
    ingest.assert_called_once_with("US_STOCK", "AAPL", years=1)
    create_job.assert_called_once()
    run_job.assert_called_once_with("job-aapl")
    update_request.assert_called_once()
    assert update_request.call_args.kwargs["status"] == "backtesting"
    assert update_request.call_args.kwargs["request_patch"]["ingest"] == ingest_meta


def test_custom_market_worker_runs_backtest_when_csv_exists() -> None:
    request_row = {
        "id": "req-fut",
        "market": "FUTURES",
        "symbol": "PVC",
        "status": "ingesting",
        "strategies": ["TOTAL"],
        "years": 1,
        "user_id": "u1",
    }
    job = {"id": "job-pvc", "status": "queued"}
    with (
        patch("services.api.main.get_custom_instrument_request", return_value=request_row),
        patch("services.api.main.resolve_csv", return_value=Path("data/futures/1d/PVC.csv")),
        patch("services.api.main.create_backtest_job", return_value=job) as create_job,
        patch("services.api.main.update_custom_instrument_request") as update_request,
        patch("services.api.main.run_backtest_job_once") as run_job,
    ):
        run_custom_market_request_once("req-fut")
    create_job.assert_called_once()
    run_job.assert_called_once_with("job-pvc")
    update_request.assert_called_once()
    assert update_request.call_args.kwargs["status"] == "backtesting"


def test_list_distinct_watchlist_user_ids_delegates_to_session() -> None:
    from db.paper_watchlist import list_distinct_watchlist_user_ids

    class _FakeScalars:
        def all(self):
            return ["u-a", "u-b"]

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def scalars(self, _stmt):
            return _FakeScalars()

    with patch("db.paper_watchlist.get_engine", return_value=object()), patch(
        "db.paper_watchlist.Session", return_value=_FakeSession()
    ):
        assert list_distinct_watchlist_user_ids(status="pending_runtime", limit_users=10) == ["u-a", "u-b"]


def test_build_watchlist_runtime_cache_payload_uses_rows() -> None:
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import run_watchlist_runtime_job as job_mod

    rows = [{"id": "w1", "market": "CRYPTO", "symbol": "BTCUSDT", "status": "pending_runtime", "strategies": ["TOTAL"]}]
    with patch.object(job_mod, "build_watchlist_runtime_snapshots", return_value=[{"runtime_status": "ready"}]) as build_snaps:
        payload = job_mod.build_watchlist_runtime_cache_payload(
            user_id="u1",
            status="pending_runtime",
            limit=5,
            include_signal_preview=False,
            rows=rows,
        )
    build_snaps.assert_called_once_with(rows, include_signal_preview=False)
    assert payload["user_id"] == "u1"
    assert payload["count"] == 1
    assert payload["runtime_binding"] == "file_cache_snapshot_only"
    assert payload["items"][0]["runtime_status"] == "ready"


def test_run_watchlist_runtime_job_all_users_dry_run(monkeypatch, capsys) -> None:
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import run_watchlist_runtime_job as job_mod

    monkeypatch.setattr(job_mod, "list_distinct_watchlist_user_ids", lambda **_: ["u1", "u2"])
    monkeypatch.setattr(
        job_mod,
        "build_watchlist_runtime_cache_payload",
        lambda **_: {"count": 0, "items": []},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_watchlist_runtime_job.py", "--all-users", "--dry-run"],
    )
    assert job_mod.main() == 0
    out = capsys.readouterr().out
    assert "WATCHLIST_RUNTIME_JOB_OK" in out
    assert "users=2" in out
    assert "dry_run=True" in out

