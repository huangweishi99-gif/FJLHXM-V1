from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Header, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from chart_bundle import ChartBundleRequest, build_chart_bundle
from chart_symbol_catalog import merge_symbol_summary
from fengji_core.constants import FENGJI_TOTAL_PATTERN_STRATEGIES, STRATEGY_DISPLAY_NAMES, STRATEGY_PRIORITY
from fengji_core.symbol_names import FUTURES_CN_NAMES, a_stock_name, normalize_a_stock_symbol

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db.backtest_jobs import (  # noqa: E402
    create_backtest_job,
    get_backtest_job,
    mark_backtest_job_failed,
    mark_backtest_job_running,
    mark_backtest_job_succeeded,
)
from db.custom_instruments import (  # noqa: E402
    SUPPORTED_CUSTOM_MARKETS,
    CUSTOM_PLAN_LIMITS,
    check_custom_request_quota,
    create_custom_instrument_request,
    get_custom_instrument_request,
    normalize_custom_plan,
    normalize_custom_strategies,
    normalize_custom_symbol,
    update_custom_instrument_request,
)
from db.paper_watchlist import (  # noqa: E402
    WATCHLIST_STATUS_CANCELLED,
    WATCHLIST_STATUS_PAUSED,
    list_paper_watchlist,
    update_paper_watchlist_status,
)
from db.context_queries import (
    attach_radar_signal_tiers,
    get_signal_strength,
    list_bucket_trades,
    list_bucket_stats,
    list_context_symbol_summary,
    list_trades_with_strength,
)
from db.queries import list_instruments as pg_list_instruments
from crypto_ingest import ingest_crypto_timeframes, missing_crypto_timeframes
from market_ingest import ingest_custom_market_d1
from monitor_domestic import load_latest_opens, overlay_position_on_bundle
from monitor_overseas import load_latest_opens as load_overseas_latest_opens
from monitor_ledger import load_recent_ledger_rejections
from monitor_paper_account import build_user_paper_account_summary
from radar_snapshot import load_latest_radar
from monitor_polling_gate import attach_monitor_policy, enforce_monitor_polling
from monitor_ws_telemetry import (
    build_heartbeat_message,
    get_stats as monitor_ws_get_stats,
    record_event as monitor_ws_record_event,
    snapshot_payload_fingerprint,
)
from monitor_ws_channels import (
    build_delta_message,
    channel_fingerprints,
    diff_changed_channels,
    filter_snapshot_payload,
    parse_monitor_channels,
)
from watchlist_runtime import build_watchlist_runtime_snapshots
from watchlist_runtime_file_cache import load_watchlist_runtime_cache, runtime_cache_age_seconds
from auth_service import auth_response_from_user, decode_token, normalize_plan as auth_normalize_plan
from db.auth_users import authenticate_user, create_user, get_user_by_id
from db.subscriptions import activate_user_subscription, redeem_code_for_plan, validate_subscription_intent
from subscription_payment_config import build_subscription_payment_config
from subscription_plan_catalog import plan_pricing
from feature_gate import (
    FeatureGateError,
    effective_plan,
    ensure_plan_active,
    ensure_strategy_allowed,
    ensure_years_allowed,
    is_plan_active,
)
from admin_overview import build_admin_overview

ROOT = Path(__file__).resolve().parents[2]
DATA_CRYPTO = ROOT / "data" / "overseas_1d"
DATA_A_STOCK = ROOT / "data" / "a_stock"
DATA_US_STOCK = ROOT / "data" / "us_stock"

app = FastAPI(
    title="FengJi Quant API",
    version="0.1.0",
    description="FJLHXM-V1 Web backend — chart-bundle & strategies (MVP)",
)


class BacktestCreateRequest(BaseModel):
    market: str = Field(..., description="A_STOCK | FUTURES | US_STOCK | CRYPTO")
    symbol: str = Field(..., min_length=1)
    strategy_id: str = Field("TOTAL")
    years: int = Field(3, ge=1, le=5)
    user_id: str | None = None


class CustomInstrumentRequestCreate(BaseModel):
    market: str = Field(..., description="FUTURES | A_STOCK | CRYPTO | US_STOCK")
    symbol: str = Field(..., min_length=1)
    name: str | None = None
    strategies: list[str] = Field(default_factory=lambda: ["TOTAL"])
    years: int = Field(3, ge=1, le=5)
    enable_paper: bool = False
    user_id: str | None = None
    plan_id: str | None = None


class PaperWatchlistStatusUpdate(BaseModel):
    user_id: str = Field(..., min_length=1)
    status: str = Field(..., description="paused | cancelled")


class AuthRegisterRequest(BaseModel):
    account: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class AuthLoginRequest(BaseModel):
    account: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class AuthRefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class SubscriptionActivateRequest(BaseModel):
    plan: str = Field(..., description="standard | pro")


class SubscriptionRedeemRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=64)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件：挂载 web/ 目录为前端入口
WEB_DIR = ROOT / "web"
if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


@app.get("/")
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/web/index.html")


def resolve_csv(symbol: str, market: str = "CRYPTO") -> Path:
    sym = symbol.strip().upper().replace("-", "")
    mkt = market.upper()
    if mkt == "CRYPTO":
        for folder in (DATA_CRYPTO, ROOT / "data" / "1d", ROOT / "data" / "overseas_1d"):
            path = folder / f"{sym}.csv"
            if path.exists():
                return path
    if mkt in {"A_STOCK", "ASTOCK"}:
        code = sym.zfill(6) if sym.isdigit() else sym
        for pattern in (f"{code}_1D_qfq.csv", f"{code}.csv"):
            path = DATA_A_STOCK / pattern
            if path.exists():
                return path
    if mkt in {"FUTURES", "CN_FUTURES"}:
        base = sym.replace("USDT", "")
        cn_name = FUTURES_CN_NAMES.get(base)
        candidates = [f"{base}.csv", f"{base}USDT.csv", f"{sym}.csv"]
        if cn_name:
            candidates.append(f"{cn_name}.csv")
        for folder in (
            ROOT / "data" / "futures" / "1d",
            ROOT / "data" / "futures_lc" / "1d",
            ROOT / "data" / "1d",
        ):
            for name in candidates:
                path = folder / name
                if path.exists():
                    return path
    if mkt in {"US_STOCK", "USSTOCK"}:
        base = sym.replace(".", "_")
        for pattern in (f"{base}_1D.csv", f"{base}.csv"):
            path = DATA_US_STOCK / pattern
            if path.exists():
                return path
    raise FileNotFoundError(f"no csv for {symbol} market={market}")


def _with_chart_data_flag(rows: list[dict]) -> list[dict]:
    """Mark PG summary rows that can also open a local chart-bundle CSV."""
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item.setdefault("has_pg_context", True)
        mkt = str(item.get("market", "")).upper()
        sym = str(item.get("symbol", "")).strip()
        if mkt in {"A_STOCK", "ASTOCK"} and sym.isdigit():
            display = normalize_a_stock_symbol(sym)
            item.setdefault("display_symbol", display)
            item.setdefault("symbol_name", a_stock_name(display) or "")
        else:
            from chart_symbol_catalog import _enrich_display_fields

            display, cn_name = _enrich_display_fields(mkt, sym)
            if mkt in {"FUTURES", "CN_FUTURES"}:
                item["display_symbol"] = display
                if cn_name:
                    item["symbol_name"] = cn_name
            else:
                item.setdefault("display_symbol", sym)
                item.setdefault("symbol_name", item.get("symbol_name") or "")
        try:
            csv_path = resolve_csv(str(item.get("symbol", "")), str(item.get("market", "")))
            item["has_chart_data"] = True
            item["chart_source_file"] = csv_path.name
        except FileNotFoundError:
            item["has_chart_data"] = False
            item["chart_source_file"] = None
        out.append(item)
    return out


def infer_monitor_market(symbol: str) -> str:
    sym = symbol.strip().upper()
    if sym.isdigit() or (len(sym) == 6 and sym[:6].isdigit()):
        return "A_STOCK"
    if sym.endswith("USDT"):
        return "CRYPTO"
    return "FUTURES"


def latest_quote_from_csv(symbol: str, market: str) -> dict:
    csv_path = resolve_csv(symbol, market)
    latest: dict[str, str] | None = None
    rows = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows += 1
            close_raw = row.get("close")
            try:
                close = float(close_raw) if close_raw not in {None, ""} else None
            except (TypeError, ValueError):
                close = None
            if close is None:
                continue
            latest = row
    if latest is None:
        raise ValueError(f"no usable close price for {symbol} market={market}")
    latest_time = (
        latest.get("date")
        or latest.get("timestamp")
        or latest.get("datetime")
        or latest.get("time")
        or ""
    )
    return {
        "symbol": symbol.strip().upper(),
        "market": market.upper(),
        "current_price": float(latest["close"]),
        "latest_time": str(latest_time),
        "rows": rows,
        "source_file": csv_path.name,
    }


def _monitor_symbol_key(symbol: str, market: str) -> str:
    sym = str(symbol or "").strip().upper()
    mkt = str(market or infer_monitor_market(sym)).strip().upper()
    return f"{sym}|{mkt}"


def _monitor_item_symbol_market(item: dict) -> tuple[str, str] | None:
    symbol = str(item.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    market = str(item.get("market") or infer_monitor_market(symbol)).strip().upper()
    return symbol, market


def _monitor_quotes_for_items(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for item in items:
        pair = _monitor_item_symbol_market(item)
        if pair is None:
            continue
        symbol, market = pair
        key = _monitor_symbol_key(symbol, market)
        if key in seen:
            continue
        seen.add(key)
        try:
            quote = latest_quote_from_csv(symbol, market)
            quote["ok"] = True
            rows.append(quote)
        except Exception as exc:  # noqa: BLE001 - monitor snapshot reports per-symbol diagnostics
            rows.append({"symbol": symbol, "market": market, "ok": False, "error": str(exc)})
    return rows


def _build_paper_watchlist_runtime_response(
    *,
    user: str,
    status: str | None = "pending_runtime",
    limit: int = 100,
    include_signal_preview: bool = False,
    prefer_runtime_cache: bool = False,
    runtime_cache_max_age_seconds: int = 600,
) -> dict:
    if prefer_runtime_cache:
        cached = load_watchlist_runtime_cache(user)
        if cached and cached.get("status_filter") == status:
            items = list(cached.get("items") or [])[:limit]
            age = runtime_cache_age_seconds(cached)
            stale = age is not None and age > runtime_cache_max_age_seconds
            return {
                "user_id": user,
                "mode": "read_only_observation",
                "runtime_binding": cached.get("runtime_binding") or "file_cache_signal_preview",
                "runtime_cache": {
                    "status": "hit_stale" if stale else "hit",
                    "source": "file",
                    "path": cached.get("_cache_file"),
                    "generated_at": cached.get("generated_at"),
                    "age_seconds": age,
                    "max_age_seconds": runtime_cache_max_age_seconds,
                    "stale": stale,
                },
                "count": len(items),
                "items": items,
            }
    try:
        rows = list_paper_watchlist(user_id=user, status=status, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    snapshots = build_watchlist_runtime_snapshots(rows, include_signal_preview=include_signal_preview)
    return {
        "user_id": user,
        "mode": "read_only_observation",
        "runtime_binding": "csv_snapshot_with_signal_preview" if include_signal_preview else "csv_snapshot_only",
        "runtime_cache": {"status": "miss" if prefer_runtime_cache else "bypass", "source": None},
        "count": len(snapshots),
        "items": snapshots,
    }


def _merge_monitor_position_payloads(
    domestic_payload: dict,
    overseas_payload: dict,
) -> list[dict]:
    positions: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for payload in (domestic_payload, overseas_payload):
        for pos in payload.get("positions") or []:
            if not isinstance(pos, dict):
                continue
            symbol = str(pos.get("symbol") or "").strip().upper()
            market = str(pos.get("market") or "").strip().upper()
            key = (symbol, market)
            if not symbol or key in seen:
                continue
            seen.add(key)
            positions.append(pos)
    positions.sort(
        key=lambda p: str(p.get("entry_time") or p.get("entry_time_raw") or ""),
        reverse=True,
    )
    return positions


def build_monitor_snapshot(
    *,
    user_id: str,
    plan: str = "free",
    seq: int = 1,
    status: str | None = "pending_runtime",
    limit: int = 100,
    include_signal_preview: bool = True,
    prefer_runtime_cache: bool = True,
    runtime_cache_max_age_seconds: int = 600,
) -> dict:
    """Build a read-only monitor snapshot for REST/WS consumers."""
    user = str(user_id or "").strip()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    domestic_payload = load_latest_opens()
    overseas_payload = load_overseas_latest_opens()
    positions = _merge_monitor_position_payloads(domestic_payload, overseas_payload)
    runtime_payload: dict = {"user_id": user, "mode": "read_only_observation", "count": 0, "items": []}
    runtime_error: str | None = None
    if user:
        try:
            runtime_payload = _build_paper_watchlist_runtime_response(
                user=user,
                status=status,
                limit=limit,
                include_signal_preview=include_signal_preview,
                prefer_runtime_cache=prefer_runtime_cache,
                runtime_cache_max_age_seconds=runtime_cache_max_age_seconds,
            )
        except HTTPException as exc:
            runtime_error = str(exc.detail)
    runtime_items = list(runtime_payload.get("items") or [])
    quotes = _monitor_quotes_for_items([*positions, *runtime_items])
    return {
        "type": "monitor.snapshot.v1",
        "version": 1,
        "seq": seq,
        "generated_at": generated_at,
        "mode": "read_only_monitor",
        "user_id": user,
        "plan": str(plan or "free").strip().lower() or "free",
        "sources": {
            "domestic_positions": domestic_payload.get("source") or "paper_state_readonly",
            "overseas_positions": overseas_payload.get("source") or "paper_state_readonly",
            "watchlist_runtime": runtime_payload.get("runtime_binding") or "not_requested",
            "quotes": "local_csv_latest_close",
        },
        "payload": {
            "positions": positions,
            "runtime": runtime_payload,
            "quotes": quotes,
        },
        "status": {
            "ok": runtime_error is None,
            "runtime_error": runtime_error,
            "fallback_polling_allowed": True,
        },
    }


MONITOR_WS_ALLOWED_PLANS = {"pro"}
MONITOR_WS_ACTIVE_CONNECTIONS: dict[str, int] = {}
MONITOR_WS_MAX_CONNECTIONS_PER_USER = max(1, int(os.getenv("MONITOR_WS_MAX_CONNECTIONS_PER_USER", "3")))


def normalize_monitor_plan(plan: str) -> str:
    key = str(plan or "").strip().lower()
    return key or "free"


def monitor_ws_policy(user_id: str, plan: str) -> dict:
    user = str(user_id or "").strip()
    normalized_plan = normalize_monitor_plan(plan)
    if not user:
        return {
            "allowed": False,
            "code": "missing_user",
            "message": "monitor websocket requires demo user identity",
            "plan": normalized_plan,
        }
    if normalized_plan not in MONITOR_WS_ALLOWED_PLANS:
        return {
            "allowed": False,
            "code": "plan_not_allowed",
            "message": "monitor websocket is available for pro plan only",
            "plan": normalized_plan,
        }
    return {"allowed": True, "code": "ok", "message": "ok", "plan": normalized_plan}


def _monitor_ws_connection_key(user_id: str) -> str:
    return str(user_id or "").strip() or "anonymous"


def _monitor_ws_increment_connection(user_id: str) -> tuple[bool, int]:
    key = _monitor_ws_connection_key(user_id)
    current = MONITOR_WS_ACTIVE_CONNECTIONS.get(key, 0)
    if current >= MONITOR_WS_MAX_CONNECTIONS_PER_USER:
        return False, current
    MONITOR_WS_ACTIVE_CONNECTIONS[key] = current + 1
    return True, current + 1


def _monitor_ws_decrement_connection(user_id: str) -> None:
    key = _monitor_ws_connection_key(user_id)
    current = MONITOR_WS_ACTIVE_CONNECTIONS.get(key, 0)
    if current <= 1:
        MONITOR_WS_ACTIVE_CONNECTIONS.pop(key, None)
    else:
        MONITOR_WS_ACTIVE_CONNECTIONS[key] = current - 1


def monitor_ws_interval_seconds(plan: str, requested: float | None = None) -> float:
    key = normalize_monitor_plan(plan)
    if requested is not None and requested > 0:
        minimum = 5.0 if key == "pro" else 60.0
        return max(minimum, min(float(requested), 900.0))
    if key == "pro":
        return 5.0
    if key == "standard":
        return 60.0
    return 900.0


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "fengji-api", "version": "0.1.0"}


def resolve_admin_api(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    secret = os.getenv("FENGJI_ADMIN_TOKEN", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="admin API not configured (set FENGJI_ADMIN_TOKEN)")
    bearer = _bearer_token(authorization)
    if not bearer or not hmac.compare_digest(bearer, secret):
        raise HTTPException(status_code=401, detail="invalid admin token")


@app.get("/api/v1/admin/overview")
def admin_overview(_: None = Depends(resolve_admin_api)) -> dict:
    """WAdmin MVP: 只读运行概览（WS 连接、订阅订单、回测任务计数）。"""
    stats = monitor_ws_get_stats(
        MONITOR_WS_ACTIVE_CONNECTIONS,
        max_per_user=MONITOR_WS_MAX_CONNECTIONS_PER_USER,
    )
    body = build_admin_overview(ws_stats=stats)
    body["service"] = health()
    return body


def _bearer_token(authorization: str | None) -> str | None:
    text = str(authorization or "").strip()
    if not text.lower().startswith("bearer "):
        return None
    token = text[7:].strip()
    return token or None


def _user_from_access_token(token: str | None) -> dict | None:
    raw = str(token or "").strip()
    if not raw:
        return None
    try:
        payload = decode_token(raw, expected_type="access")
    except Exception:  # noqa: BLE001
        return None
    return get_user_by_id(str(payload.get("sub", "")))


def resolve_auth_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token: str | None = Query(default=None),
) -> dict:
    token = _bearer_token(authorization) or str(access_token or "").strip() or None
    user = _user_from_access_token(token)
    if not token:
        raise HTTPException(status_code=401, detail="missing access token")
    if not user:
        raise HTTPException(status_code=401, detail="invalid access token")
    return user


def resolve_optional_auth_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict | None:
    return _user_from_access_token(_bearer_token(authorization))


@app.post("/api/v1/auth/register")
def auth_register(body: AuthRegisterRequest) -> dict:
    try:
        user = create_user(account=body.account, password=body.password, plan_id="free")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="auth storage unavailable") from exc
    return auth_response_from_user(user)


@app.post("/api/v1/auth/login")
def auth_login(body: AuthLoginRequest) -> dict:
    user = authenticate_user(account=body.account, password=body.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid account or password")
    return auth_response_from_user(user)


@app.post("/api/v1/auth/refresh")
def auth_refresh(body: AuthRefreshRequest) -> dict:
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="invalid refresh token") from exc
    user = get_user_by_id(str(payload.get("sub", "")))
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return auth_response_from_user(user)


@app.get("/api/v1/auth/me")
def auth_me(user: dict = Depends(resolve_auth_user)) -> dict:
    return {
        "id": user["id"],
        "account": user["account"],
        "plan": auth_normalize_plan(user.get("plan_id")),
        "plan_expires_at": user.get("plan_expires_at"),
        "created_at": user.get("created_at"),
    }


def _manual_subscription_confirm_enabled() -> bool:
    return os.getenv("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "").lower() in {"1", "true", "yes"}


@app.get("/api/v1/subscriptions/payment-config")
def subscription_payment_config() -> dict:
    """V1.1：只读支付通道配置（不含密钥）；供 payment.html 决定确认按钮与提示文案。"""
    return build_subscription_payment_config()


@app.post("/api/v1/subscriptions/manual-confirm")
def subscription_manual_confirm(
    body: SubscriptionActivateRequest,
    user: dict = Depends(resolve_auth_user),
) -> dict:
    """W17-prod MVP：用户扫码后自确认；须开启 FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM 并写入 subscription_orders 审计。"""
    if not _manual_subscription_confirm_enabled():
        raise HTTPException(
            status_code=503,
            detail="manual subscription confirm disabled; use redeem code or payment webhook",
        )
    try:
        validate_subscription_intent(current_plan=user.get("plan_id", "free"), requested_plan=body.plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        price = plan_pricing(body.plan) or {}
        updated, order = activate_user_subscription(
            user_id=str(user["id"]),
            plan_id=body.plan,
            channel="personal_wechat_qr",
            metadata={
                "account": user.get("account"),
                "amount_yuan": price.get("amount_yuan"),
                "amount_fen": price.get("amount_fen"),
                "confirm_mode": "user_manual",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"subscription storage unavailable: {exc}") from exc
    response = auth_response_from_user(updated)
    response["subscription_order"] = order
    return response


@app.post("/api/v1/subscriptions/redeem")
def subscription_redeem(body: SubscriptionRedeemRequest, user: dict = Depends(resolve_auth_user)) -> dict:
    """W17-prod MVP：兑换码开通订阅（FENGJI_SUBSCRIPTION_REDEEM_CODES=standard:CODE,pro:CODE）。"""
    plan = redeem_code_for_plan(body.code)
    if not plan:
        raise HTTPException(status_code=400, detail="invalid or expired redeem code")
    try:
        validate_subscription_intent(current_plan=user.get("plan_id", "free"), requested_plan=plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        updated, order = activate_user_subscription(
            user_id=str(user["id"]),
            plan_id=plan,
            channel="redeem_code",
            external_ref=body.code.strip().upper(),
            metadata={"account": user.get("account")},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"subscription storage unavailable: {exc}") from exc
    response = auth_response_from_user(updated)
    response["subscription_order"] = order
    return response


@app.post("/api/v1/webhooks/subscription")
async def subscription_payment_webhook(request: Request) -> dict:
    """W17-prod 占位：支付回调验签后开通订阅。密钥放 FENGJI_PAYMENT_WEBHOOK_SECRET。"""
    secret = os.getenv("FENGJI_PAYMENT_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="payment webhook not configured")
    body = await request.body()
    signature = str(request.headers.get("X-FengJi-Signature", "")).strip()
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid json payload") from exc
    user_id = str(payload.get("user_id", "")).strip()
    plan = auth_normalize_plan(str(payload.get("plan", "")))
    external_ref = str(payload.get("external_ref", "") or payload.get("transaction_id", "")).strip() or None
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    try:
        validate_subscription_intent(current_plan=user.get("plan_id", "free"), requested_plan=plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        updated, order = activate_user_subscription(
            user_id=user_id,
            plan_id=plan,
            channel="payment_webhook",
            external_ref=external_ref,
            metadata={"webhook": True},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"subscription storage unavailable: {exc}") from exc
    return {"ok": True, "user_id": updated["id"], "plan": auth_normalize_plan(updated.get("plan_id")), "order": order}


def resolve_monitor_identity(
    user_id: str,
    plan: str,
    access_token: str | None = None,
) -> tuple[str, str, dict | None]:
    token = str(access_token or "").strip()
    if token:
        user = _user_from_access_token(token)
        if user:
            return str(user["id"]), auth_normalize_plan(user.get("plan_id")), user
    return str(user_id or "").strip(), normalize_monitor_plan(plan), None


def _monitor_poll_user_key(request: Request, auth_user: dict | None, user_id: str | None) -> str:
    if auth_user:
        return str(auth_user["id"])
    demo = str(user_id or "").strip()
    if demo:
        return demo
    host = request.client.host if request.client else "unknown"
    return f"anon:{host}"


def resolve_monitor_poll_gate(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
) -> dict:
    token = _bearer_token(authorization) or str(access_token or "").strip() or None
    auth_user = _user_from_access_token(token)
    plan = effective_plan(auth_user=auth_user)
    policy = enforce_monitor_polling(
        user_key=_monitor_poll_user_key(request, auth_user, user_id),
        plan=plan,
    )
    if not policy["allowed"]:
        retry = int(max(float(policy["retry_after_seconds"]), 1))
        raise HTTPException(
            status_code=429,
            detail=(
                f"monitor polling too frequent for plan '{policy['plan']}'; "
                f"min interval {policy['min_interval_seconds']}s"
            ),
            headers={"Retry-After": str(retry)},
        )
    return {"auth_user": auth_user, "policy": policy}


CHART_BUNDLE_STRATEGIES = {"DS01", "DS03", "TOTAL"}
MONITOR_CHART_STRATEGIES = {"DS01", "DS03"}


def run_backtest_job_once(job_id: str) -> None:
    """W11 MVP worker: run chart-bundle in a FastAPI background task."""
    job = mark_backtest_job_running(job_id)
    if job is None or job.get("status") == "succeeded":
        return
    try:
        csv_path = resolve_csv(str(job["symbol"]), str(job["market"]))
        bundle = build_chart_bundle(
            ChartBundleRequest(
                csv_path=csv_path,
                strategy_id=str(job["strategy_id"]),
                years=int(job["years"]),
                futures_mode=str(job["market"]).upper() not in {"CRYPTO"},
            )
        )
        result = {
            "bundle": bundle,
            "summary": {
                "bars": len(bundle.get("bars") or []),
                "markers": len(bundle.get("markers") or []),
                "strategy_id": bundle.get("strategy_id"),
                "metrics": bundle.get("metrics") or {},
            },
        }
        mark_backtest_job_succeeded(job_id, result)
    except Exception as exc:  # noqa: BLE001 - worker records user-visible failure
        mark_backtest_job_failed(job_id, f"{type(exc).__name__}: {exc}")


def run_custom_crypto_request_once(request_id: str) -> None:
    """W18 MVP worker: ingest missing crypto D1/H1/M15 CSVs, then launch a backtest job."""
    row = get_custom_instrument_request(request_id)
    if not row or row.get("status") in {"backtested", "paper_enabled", "failed"}:
        return
    try:
        ingest_meta = ingest_crypto_timeframes(str(row["symbol"]))
        strategies = list(row.get("strategies") or ["TOTAL"])
        strategy_id = str(strategies[0] if strategies else "TOTAL").upper()
        if strategy_id not in CHART_BUNDLE_STRATEGIES:
            strategy_id = "TOTAL"
        job = create_backtest_job(
            market=str(row["market"]),
            symbol=str(row["symbol"]),
            strategy_id=strategy_id,
            years=int(row["years"]),
            user_id=row.get("user_id"),
        )
        update_custom_instrument_request(
            request_id,
            status="backtesting",
            backtest_job_id=job["id"],
            request_patch={"ingest": ingest_meta},
        )
        run_backtest_job_once(job["id"])
        get_custom_instrument_request(request_id)
    except Exception as exc:  # noqa: BLE001 - worker records user-visible failure
        update_custom_instrument_request(
            request_id,
            status="failed",
            error_message=f"{type(exc).__name__}: {exc}",
            finished=True,
        )


def run_custom_market_request_once(request_id: str) -> None:
    """WEB-CUSTOM-002 worker: ingest missing D1 CSV then run backtest when possible."""
    row = get_custom_instrument_request(request_id)
    if not row or row.get("status") in {"backtested", "paper_enabled", "failed"}:
        return
    market = str(row.get("market") or "").upper()
    if market == "CRYPTO":
        run_custom_crypto_request_once(request_id)
        return
    symbol = str(row["symbol"])
    years = int(row.get("years") or 1)
    ingest_meta: dict | None = None
    try:
        resolve_csv(symbol, market)
    except FileNotFoundError:
        try:
            ingest_meta = ingest_custom_market_d1(market, symbol, years=years)
            resolve_csv(symbol, market)
        except Exception as exc:
            update_custom_instrument_request(
                request_id,
                status="failed",
                error_message=f"{type(exc).__name__}: {exc}",
                finished=True,
                request_patch={"ingest_error": str(exc)},
            )
            return
    try:
        strategies = list(row.get("strategies") or ["TOTAL"])
        strategy_id = str(strategies[0] if strategies else "TOTAL").upper()
        if strategy_id not in CHART_BUNDLE_STRATEGIES:
            strategy_id = "TOTAL"
        job = create_backtest_job(
            market=str(row["market"]),
            symbol=str(row["symbol"]),
            strategy_id=strategy_id,
            years=years,
            user_id=row.get("user_id"),
        )
        request_patch: dict = {"csv_source": "local_existing" if ingest_meta is None else "custom_ingest"}
        if ingest_meta:
            request_patch["ingest"] = ingest_meta
        update_custom_instrument_request(
            request_id,
            status="backtesting",
            backtest_job_id=job["id"],
            request_patch=request_patch,
        )
        run_backtest_job_once(job["id"])
        get_custom_instrument_request(request_id)
    except Exception as exc:  # noqa: BLE001 - worker records user-visible failure
        update_custom_instrument_request(
            request_id,
            status="failed",
            error_message=f"{type(exc).__name__}: {exc}",
            finished=True,
        )


@app.get("/api/v1/instruments")
def list_instruments(
    market: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    try:
        return pg_list_instruments(market=market, query=q, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.get("/api/v1/strategies")
def list_strategies() -> list[dict]:
    rows = []
    for sid in ["TOTAL", *FENGJI_TOTAL_PATTERN_STRATEGIES]:
        rows.append(
            {
                "strategy_id": sid,
                "display_name": STRATEGY_DISPLAY_NAMES.get(sid, sid),
                "priority": STRATEGY_PRIORITY.get(sid, 999),
                "chart_bundle": sid in CHART_BUNDLE_STRATEGIES,
            }
        )
    return rows


@app.post("/api/v1/backtests", status_code=202)
def create_backtest(
    request: BacktestCreateRequest,
    background_tasks: BackgroundTasks,
    auth_user: dict | None = Depends(resolve_optional_auth_user),
) -> dict:
    """W11 MVP：提交异步回测任务，后台写回 job 状态与 chart-bundle 结果。"""
    strategy_id = request.strategy_id.upper()
    if strategy_id not in CHART_BUNDLE_STRATEGIES:
        strategy_id = "TOTAL"
    plan = effective_plan(auth_user=auth_user)
    try:
        ensure_plan_active(auth_user)
        ensure_years_allowed(plan, request.years)
        ensure_strategy_allowed(plan, strategy_id)
    except FeatureGateError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        resolve_csv(request.symbol, request.market)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        job = create_backtest_job(
            market=request.market,
            symbol=request.symbol,
            strategy_id=strategy_id,
            years=request.years,
            user_id=request.user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc

    if job["status"] == "queued":
        background_tasks.add_task(run_backtest_job_once, job["id"])
    return job


@app.post("/api/v1/custom-instruments/request", status_code=202)
def create_custom_request(
    request: CustomInstrumentRequestCreate,
    background_tasks: BackgroundTasks,
    auth_user: dict | None = Depends(resolve_optional_auth_user),
) -> dict:
    """WEB-BT-011：用户自选品种请求。Crypto 可后台拉数；其余市场有本地 CSV 时自动回测。"""
    market = request.market.strip().upper()
    if market not in SUPPORTED_CUSTOM_MARKETS:
        raise HTTPException(status_code=400, detail=f"unsupported custom instrument market: {market}")
    if not auth_user:
        raise HTTPException(status_code=401, detail="login required for custom instrument backtests")
    plan_id = effective_plan(auth_user=auth_user)
    user_id = str(auth_user["id"])
    if plan_id == "free":
        raise HTTPException(status_code=403, detail="free plan cannot submit custom instrument backtests")
    if plan_id not in CUSTOM_PLAN_LIMITS:
        raise HTTPException(status_code=403, detail="custom instrument requests require standard or pro plan")
    try:
        ensure_plan_active(auth_user)
        ensure_years_allowed(plan_id, request.years)
        for sid in normalize_custom_strategies(request.strategies):
            ensure_strategy_allowed(plan_id, sid)
    except FeatureGateError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        symbol = normalize_custom_symbol(market, request.symbol)
        strategies = normalize_custom_strategies(request.strategies)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        quota = check_custom_request_quota(user_id, plan_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    if not quota["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"custom instrument monthly quota exceeded: {plan_id} {quota['used']}/{quota['limit']}",
        )
    quota_snapshot = {
        "plan_id": plan_id,
        "limit": quota["limit"],
        "used_before": quota["used"],
        "remaining_after": max(int(quota["limit"]) - int(quota["used"]) - 1, 0),
    }

    strategy_id = strategies[0]
    if strategy_id not in CHART_BUNDLE_STRATEGIES:
        strategy_id = "TOTAL"

    try:
        resolve_csv(symbol, market)
        missing_timeframes = missing_crypto_timeframes(symbol) if market == "CRYPTO" else []
    except FileNotFoundError:
        missing_timeframes = ["D1", "H1", "M15"] if market == "CRYPTO" else ["D1"]
    if missing_timeframes:
        request_extra = (
            {"missing_timeframes": missing_timeframes}
            if market == "CRYPTO"
            else {"missing_data": True}
        )
        try:
            row = create_custom_instrument_request(
                market=market,
                symbol=symbol,
                strategies=strategies,
                years=request.years,
                user_id=user_id,
                plan_id=plan_id,
                name=request.name,
                enable_paper=request.enable_paper,
                status="ingesting",
                quota=quota_snapshot,
                request_extra=request_extra,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
        worker = run_custom_crypto_request_once if market == "CRYPTO" else run_custom_market_request_once
        background_tasks.add_task(worker, row["id"])
        return row

    try:
        job = create_backtest_job(
            market=market,
            symbol=symbol,
            strategy_id=strategy_id,
            years=request.years,
            user_id=user_id,
        )
        row = create_custom_instrument_request(
            market=market,
            symbol=symbol,
            strategies=strategies,
            years=request.years,
            user_id=user_id,
            plan_id=plan_id,
            name=request.name,
            enable_paper=request.enable_paper,
            status="backtesting",
            backtest_job_id=job["id"],
            quota=quota_snapshot,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc

    if job["status"] == "queued":
        background_tasks.add_task(run_backtest_job_once, job["id"])
    row["backtest_job"] = job
    return row


@app.get("/api/v1/custom-instruments/requests/{request_id}")
def get_custom_request(request_id: str) -> dict:
    try:
        row = get_custom_instrument_request(request_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    if row is None:
        raise HTTPException(status_code=404, detail=f"custom instrument request not found: {request_id}")
    return row


@app.get("/api/v1/paper-watchlist")
def get_paper_watchlist(
    user_id: str = Query(..., min_length=1),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> list[dict]:
    """W18 MVP: read custom-instrument paper watchlist registrations only."""
    try:
        return list_paper_watchlist(user_id=user_id.strip(), status=status, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.patch("/api/v1/paper-watchlist/{watchlist_id}")
def patch_paper_watchlist_status(watchlist_id: str, request: PaperWatchlistStatusUpdate) -> dict:
    """W18 MVP: pause/cancel a custom-instrument observation registration only."""
    status = request.status.strip().lower()
    if status not in {WATCHLIST_STATUS_PAUSED, WATCHLIST_STATUS_CANCELLED}:
        raise HTTPException(status_code=400, detail="paper watchlist status update supports paused or cancelled only")
    try:
        row = update_paper_watchlist_status(
            watchlist_id=watchlist_id,
            user_id=request.user_id.strip(),
            status=status,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    if row is None:
        raise HTTPException(status_code=404, detail=f"paper watchlist entry not found: {watchlist_id}")
    return row


@app.get("/api/v1/paper-watchlist/runtime")
def get_paper_watchlist_runtime(
    user_id: str = Query(..., min_length=1),
    status: str | None = Query("pending_runtime"),
    limit: int = Query(100, ge=1, le=500),
    include_signal_preview: bool = Query(False),
    prefer_runtime_cache: bool = Query(False),
    runtime_cache_max_age_seconds: int = Query(600, ge=1, le=86400),
) -> dict:
    """W18 MVP: read-only runtime binding snapshot for custom paper watchlist."""
    user = user_id.strip()
    max_cache_age = int(getattr(runtime_cache_max_age_seconds, "default", runtime_cache_max_age_seconds))
    return _build_paper_watchlist_runtime_response(
        user=user,
        status=status,
        limit=limit,
        include_signal_preview=include_signal_preview,
        prefer_runtime_cache=prefer_runtime_cache,
        runtime_cache_max_age_seconds=max_cache_age,
    )


@app.get("/api/v1/backtests/chart-bundle")
def chart_bundle(
    symbol: str = Query(..., description="e.g. SOLUSDT or 300502"),
    strategy_id: str = Query("DS03"),
    years: int = Query(3, ge=1, le=5),
    market: str = Query("CRYPTO"),
) -> dict:
    try:
        csv_path = resolve_csv(symbol, market)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return build_chart_bundle(
            ChartBundleRequest(
                csv_path=csv_path,
                strategy_id=strategy_id,
                years=years,
                futures_mode=market.upper() not in {"CRYPTO"},
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/backtests/trades")
def backtest_trades(
    symbol: str = Query(..., description="e.g. 000021 or NVDA"),
    market: str = Query(..., description="A_STOCK | FUTURES | US_STOCK | CRYPTO"),
    strategy_id: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
) -> list[dict]:
    """WEB-CTX-007：回测成交明细 + bucket 标签 + 同类历史胜率。"""
    try:
        return list_trades_with_strength(
            symbol=symbol,
            market=market,
            strategy_id=strategy_id,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.get("/api/v1/backtests/symbol-summary")
def backtest_symbol_summary(
    market: str = Query(..., description="A_STOCK | FUTURES | US_STOCK | CRYPTO"),
    limit: int = Query(200, ge=1, le=500),
    include_chart_catalog: bool = Query(True, description="Merge local CSV symbols without PG context"),
) -> list[dict]:
    """WEB-CTX-013：按市场列出品种；默认合并本地 K 线 CSV 全量目录。"""
    try:
        pg_limit = limit if not include_chart_catalog else max(limit, 500)
        pg_rows = list_context_symbol_summary(market=market, limit=min(pg_limit, 500))
        rows = merge_symbol_summary(pg_rows, market) if include_chart_catalog else pg_rows
        rows = _with_chart_data_flag(rows[:limit])
        return rows
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.get("/api/v1/backtests/{job_id}")
def get_backtest(job_id: str) -> dict:
    try:
        row = get_backtest_job(job_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    if row is None:
        raise HTTPException(status_code=404, detail=f"backtest job not found: {job_id}")
    return row


@app.get("/api/v1/signals/{trade_id}/strength")
def signal_strength(trade_id: str) -> dict:
    try:
        row = get_signal_strength(trade_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
    if row is None:
        raise HTTPException(status_code=404, detail=f"trade_id not found: {trade_id}")
    return row


@app.get("/api/v1/context-stats/buckets")
def context_buckets(
    strategy_id: str = Query(...),
    market: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict]:
    try:
        return list_bucket_stats(strategy_id=strategy_id, market=market, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.get("/api/v1/context-stats/bucket-trades")
def context_bucket_trades(
    strategy_id: str = Query(...),
    market: str = Query(..., description="A_STOCK | FUTURES | US_STOCK | CRYPTO"),
    bucket_key: str = Query(...),
    symbol: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    try:
        return list_bucket_trades(
            strategy_id=strategy_id,
            market=market,
            bucket_key=bucket_key,
            symbol=symbol,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.get("/api/v1/monitor/domestic/latest-opens")
def domestic_latest_opens(gate: dict = Depends(resolve_monitor_poll_gate)) -> dict:
    """WEB-HOME-001 改版：国内模拟实盘最新开仓列表（只读）。"""
    return attach_monitor_policy(load_latest_opens(), gate["policy"])


@app.get("/api/v1/monitor/overseas/latest-opens")
def overseas_latest_opens(gate: dict = Depends(resolve_monitor_poll_gate)) -> dict:
    """V1.1：海外 crypto 模拟实盘最新开仓列表（只读）。"""
    return attach_monitor_policy(load_overseas_latest_opens(), gate["policy"])


@app.get("/api/v1/monitor/ledger/recent")
def monitor_ledger_recent(
    limit: int = Query(30, ge=1, le=200),
    gate: dict = Depends(resolve_monitor_poll_gate),
) -> dict:
    """WEB-MON-004：只读 ledger 拒单/阻断明细（radar + pending_orders）。"""
    return attach_monitor_policy(load_recent_ledger_rejections(limit=limit), gate["policy"])


@app.get("/api/v1/monitor/paper-account")
def monitor_paper_account(
    local_watchlist_count: int | None = Query(None, ge=0, le=500),
    local_symbols: str | None = Query(None, description="Comma-separated local watchlist symbols"),
    paper_mode: str | None = Query(
        None,
        description="auto|scoped|execution — default auto uses FENGJI_PAPER_ACCOUNT_MODE (scoped)",
    ),
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token: str | None = Query(default=None),
    gate: dict = Depends(resolve_monitor_poll_gate),
) -> dict:
    """WEB-MON-V1+ / V1.1：每用户 paper 账户只读摘要（PG + scoped 或 execution）。"""
    token = _bearer_token(authorization) or str(access_token or "").strip() or None
    auth_user = gate.get("auth_user") or _user_from_access_token(token)
    plan = effective_plan(auth_user=auth_user)
    user_id = str(auth_user["id"]) if auth_user else ""
    pg_rows: list[dict] = []
    if user_id:
        try:
            pg_rows = list_paper_watchlist(user_id=user_id, limit=200)
        except Exception:
            pg_rows = []
    symbol_list = [s.strip().upper() for s in (local_symbols or "").split(",") if s.strip()]
    payload = build_user_paper_account_summary(
        user_id=user_id,
        plan_id=plan,
        local_watchlist_count=local_watchlist_count,
        local_watchlist_symbols=symbol_list or None,
        pg_watchlist=pg_rows,
        paper_mode=paper_mode,
    )
    return attach_monitor_policy(payload, gate["policy"])


@app.get("/api/v1/monitor/paper-account/positions")
def monitor_paper_account_positions(
    limit: int = Query(50, ge=1, le=200),
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token: str | None = Query(default=None),
    gate: dict = Depends(resolve_monitor_poll_gate),
) -> dict:
    """V1.1 Phase 3：每用户独立 CRYPTO 持仓（PG 优先，JSON 回退）。"""
    token = _bearer_token(authorization) or str(access_token or "").strip() or None
    auth_user = gate.get("auth_user") or _user_from_access_token(token)
    user_id = str(auth_user["id"]) if auth_user else ""
    if not user_id:
        raise HTTPException(status_code=401, detail="authentication required")
    plan = effective_plan(auth_user=auth_user)
    try:
        from paper_execution.watchlist import execution_allowed_for_plan
    except Exception:
        execution_allowed_for_plan = lambda _: False  # type: ignore[misc, assignment]
    if not execution_allowed_for_plan(plan):
        raise HTTPException(status_code=403, detail="execution view requires standard or pro plan")
    from monitor_paper_account import build_user_execution_positions_payload

    payload = build_user_execution_positions_payload(user_id=user_id, limit=limit)
    return attach_monitor_policy(payload, gate["policy"])


@app.get("/api/v1/monitor/paper-account/pending")
def monitor_paper_account_pending(
    limit: int = Query(50, ge=1, le=200),
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token: str | None = Query(default=None),
    gate: dict = Depends(resolve_monitor_poll_gate),
) -> dict:
    """V1.1 Phase 3：每用户独立 CRYPTO 挂单（PG 优先，JSON 回退）。"""
    token = _bearer_token(authorization) or str(access_token or "").strip() or None
    auth_user = gate.get("auth_user") or _user_from_access_token(token)
    user_id = str(auth_user["id"]) if auth_user else ""
    if not user_id:
        raise HTTPException(status_code=401, detail="authentication required")
    plan = effective_plan(auth_user=auth_user)
    try:
        from paper_execution.watchlist import execution_allowed_for_plan
    except Exception:
        execution_allowed_for_plan = lambda _: False  # type: ignore[misc, assignment]
    if not execution_allowed_for_plan(plan):
        raise HTTPException(status_code=403, detail="execution view requires standard or pro plan")
    from monitor_paper_account import build_user_execution_pending_payload

    payload = build_user_execution_pending_payload(user_id=user_id, limit=limit)
    return attach_monitor_policy(payload, gate["policy"])


@app.get("/api/v1/monitor/paper-account/shadow")
def monitor_paper_account_shadow(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token: str | None = Query(default=None),
    gate: dict = Depends(resolve_monitor_poll_gate),
) -> dict:
    """V1.1 Phase 4：Shadow 对比报告（scoped vs execution，须 standard/pro）。"""
    token = _bearer_token(authorization) or str(access_token or "").strip() or None
    auth_user = gate.get("auth_user") or _user_from_access_token(token)
    user_id = str(auth_user["id"]) if auth_user else ""
    if not user_id:
        raise HTTPException(status_code=401, detail="authentication required")
    plan = effective_plan(auth_user=auth_user)
    try:
        from paper_execution.watchlist import execution_allowed_for_plan
    except Exception:
        execution_allowed_for_plan = lambda _: False  # type: ignore[misc, assignment]
    if not execution_allowed_for_plan(plan):
        raise HTTPException(status_code=403, detail="shadow report requires standard or pro plan")
    try:
        from paper_execution.mode import paper_mode_summary, resolve_fengji_paper_mode
        from paper_execution.shadow import load_user_shadow_report
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"shadow module unavailable: {exc}") from exc

    report = load_user_shadow_report(user_id)
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id,
        "plan_id": plan,
        "paper_mode_global": resolve_fengji_paper_mode(),
        "paper_mode_config": paper_mode_summary(),
        "report": report,
        "available": report is not None,
    }
    return attach_monitor_policy(payload, gate["policy"])


@app.get("/api/v1/monitor/paper-account/ledger")
def monitor_paper_account_ledger(
    limit: int = Query(20, ge=1, le=200),
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token: str | None = Query(default=None),
    gate: dict = Depends(resolve_monitor_poll_gate),
) -> dict:
    """V1.1：只读 paper_account_ledger 最近明细（须登录）。"""
    token = _bearer_token(authorization) or str(access_token or "").strip() or None
    auth_user = gate.get("auth_user") or _user_from_access_token(token)
    user_id = str(auth_user["id"]) if auth_user else ""
    if not user_id:
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        from db.paper_accounts import list_recent_ledger

        items = list_recent_ledger(user_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"paper account ledger unavailable: {exc}") from exc
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id,
        "count": len(items),
        "items": items,
    }
    return attach_monitor_policy(payload, gate["policy"])


@app.get("/api/v1/monitor/radar/latest")
def monitor_radar_latest(
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="Filter by radar status, e.g. PENDING"),
    include_tier: bool = Query(True, description="Attach read-only PG signal_tier lookup"),
) -> dict:
    """C6：雷达行只读展示 + 历史同桶 signal_tier（不修改 radar/挂单）。"""
    payload = load_latest_radar(limit=limit)
    rows = list(payload.get("rows") or [])
    if status:
        want = status.strip().upper()
        rows = [r for r in rows if str(r.get("status") or "").upper() == want]
    tier_error = ""
    if include_tier and rows:
        try:
            rows = attach_radar_signal_tiers(rows)
        except Exception as exc:  # noqa: BLE001
            tier_error = str(exc)
    payload["rows"] = rows[:limit]
    payload["count"] = len(payload["rows"])
    payload["mode"] = "read_only_radar"
    payload["tier_disclaimer"] = "signal_tier 来自历史同桶统计，仅复盘展示，不修改 OS/定式/挂单"
    if tier_error:
        payload["tier_error"] = tier_error
    return payload


@app.get("/api/v1/monitor/quotes")
def monitor_quotes(
    symbols: str = Query(..., description="Comma-separated symbols, e.g. BTCUSDT,SOLUSDT,PVC"),
    markets: str | None = Query(None, description="Optional comma-separated markets aligned with symbols"),
    market: str | None = Query(None, description="Fallback market when markets is omitted"),
    gate: dict = Depends(resolve_monitor_poll_gate),
) -> dict:
    """模拟监测页自选品种行情摘要：从本地 CSV 读取最新 close。"""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    market_list = [m.strip().upper() for m in (markets or "").split(",") if m.strip()]
    rows = []
    for i, sym in enumerate(symbol_list):
        mkt = (
            market_list[i]
            if i < len(market_list)
            else (market or infer_monitor_market(sym)).strip().upper()
        )
        try:
            item = latest_quote_from_csv(sym, mkt)
            item["ok"] = True
            rows.append(item)
        except Exception as exc:
            rows.append(
                {
                    "symbol": sym,
                    "market": mkt,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return attach_monitor_policy(
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "quotes": rows,
        },
        gate["policy"],
    )


@app.get("/api/v1/monitor/ws/stats")
def monitor_ws_stats() -> dict:
    """Read-only monitor websocket connection metrics and recent audit events."""
    return monitor_ws_get_stats(
        MONITOR_WS_ACTIVE_CONNECTIONS,
        max_per_user=MONITOR_WS_MAX_CONNECTIONS_PER_USER,
    )


@app.websocket("/api/v1/ws/monitor")
async def monitor_websocket(
    websocket: WebSocket,
    user_id: str = "",
    plan: str = "free",
    access_token: str = "",
    status: str = "pending_runtime",
    limit: int = 100,
    include_signal_preview: bool = True,
    prefer_runtime_cache: bool = True,
    runtime_cache_max_age_seconds: int = 600,
    interval_seconds: float | None = None,
    channels: str = "",
) -> None:
    """W16-WS MVP: read-only monitor snapshots, with polling fallback on the client."""
    await websocket.accept()
    user_id, plan, auth_user = resolve_monitor_identity(user_id, plan, access_token)
    if auth_user and not is_plan_active(auth_user):
        policy = {
            "allowed": False,
            "code": "plan_expired",
            "message": "monitor websocket requires an active subscription",
            "plan": normalize_monitor_plan(plan),
        }
        monitor_ws_record_event(
            "auth_rejected",
            user_id=str(user_id or "").strip() or None,
            plan=policy["plan"],
            code=policy["code"],
        )
        await websocket.send_json(
            {
                "type": "monitor.auth_error.v1",
                "version": 1,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": "read_only_monitor",
                "status": {"ok": False, "fallback_polling_allowed": True},
                "policy": policy,
            }
        )
        await websocket.close(code=1008)
        return
    policy = monitor_ws_policy(user_id, plan)
    if not policy["allowed"]:
        monitor_ws_record_event(
            "auth_rejected",
            user_id=str(user_id or "").strip() or None,
            plan=policy["plan"],
            code=policy["code"],
        )
        await websocket.send_json(
            {
                "type": "monitor.auth_error.v1",
                "version": 1,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": "read_only_monitor",
                "status": {"ok": False, "fallback_polling_allowed": True},
                "policy": policy,
            }
        )
        await websocket.close(code=1008)
        return

    accepted, active_count = _monitor_ws_increment_connection(user_id)
    if not accepted:
        monitor_ws_record_event(
            "limit_exceeded",
            user_id=str(user_id or "").strip(),
            plan=policy["plan"],
            active=active_count,
        )
        await websocket.send_json(
            {
                "type": "monitor.error.v1",
                "version": 1,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": "read_only_monitor",
                "status": {"ok": False, "fallback_polling_allowed": True},
                "error": "monitor websocket connection limit exceeded",
                "connection_limit": {
                    "active": active_count,
                    "max_per_user": MONITOR_WS_MAX_CONNECTIONS_PER_USER,
                },
            }
        )
        await websocket.close(code=1013)
        return

    plan = policy["plan"]
    interval = monitor_ws_interval_seconds(plan, interval_seconds)
    subscribed = parse_monitor_channels(channels)
    seq = 1
    last_fingerprint: str | None = None
    last_channel_fps: dict[str, str] | None = None
    last_change_at = datetime.now()
    monitor_ws_record_event("connected", user_id=str(user_id or "").strip(), plan=plan, active=active_count)
    try:
        while True:
            try:
                snapshot = build_monitor_snapshot(
                    user_id=user_id,
                    plan=plan,
                    seq=seq,
                    status=status,
                    limit=max(1, min(int(limit), 500)),
                    include_signal_preview=include_signal_preview,
                    prefer_runtime_cache=prefer_runtime_cache,
                    runtime_cache_max_age_seconds=max(1, min(int(runtime_cache_max_age_seconds), 86400)),
                )
                filtered_payload = filter_snapshot_payload(snapshot.get("payload") or {}, subscribed)
                snapshot_out = {
                    **snapshot,
                    "channels": sorted(subscribed),
                    "payload": filtered_payload,
                }
                channel_fps = channel_fingerprints(filtered_payload, subscribed)
                fingerprint = snapshot_payload_fingerprint(snapshot_out)
                if last_channel_fps is None:
                    monitor_ws_record_event("snapshot_sent", user_id=str(user_id or "").strip(), plan=plan, seq=seq)
                    await websocket.send_json(snapshot_out)
                    last_fingerprint = fingerprint
                    last_channel_fps = channel_fps
                    last_change_at = datetime.now()
                elif fingerprint == last_fingerprint or not diff_changed_channels(last_channel_fps, channel_fps):
                    since = (datetime.now() - last_change_at).total_seconds()
                    heartbeat = build_heartbeat_message(
                        user_id=str(user_id or "").strip(),
                        plan=plan,
                        seq=seq,
                        since_last_change_seconds=since,
                    )
                    heartbeat["channels"] = sorted(subscribed)
                    monitor_ws_record_event("heartbeat_sent", user_id=str(user_id or "").strip(), plan=plan, seq=seq)
                    await websocket.send_json(heartbeat)
                else:
                    changed = diff_changed_channels(last_channel_fps, channel_fps)
                    delta = build_delta_message(snapshot=snapshot_out, changed=changed, channels=subscribed)
                    monitor_ws_record_event(
                        "delta_sent",
                        user_id=str(user_id or "").strip(),
                        plan=plan,
                        seq=seq,
                        changed=",".join(changed),
                    )
                    await websocket.send_json(delta)
                    last_fingerprint = fingerprint
                    last_channel_fps = channel_fps
                    last_change_at = datetime.now()
            except WebSocketDisconnect:
                raise
            except Exception as exc:  # noqa: BLE001 - websocket reports diagnostics and stays read-only
                monitor_ws_record_event(
                    "push_error",
                    user_id=str(user_id or "").strip(),
                    plan=plan,
                    seq=seq,
                    error=f"{type(exc).__name__}",
                )
                await websocket.send_json(
                    {
                        "type": "monitor.error.v1",
                        "version": 1,
                        "seq": seq,
                        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "mode": "read_only_monitor",
                        "status": {"ok": False, "fallback_polling_allowed": True},
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            seq += 1
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return
    finally:
        monitor_ws_record_event("disconnected", user_id=str(user_id or "").strip(), plan=plan)
        _monitor_ws_decrement_connection(user_id)


@app.get("/api/v1/monitor/domestic/chart")
def domestic_monitor_chart(
    symbol: str = Query(...),
    strategy_id: str = Query("TOTAL"),
    market: str = Query("FUTURES"),
    entry_time: str | None = Query(None),
    entry_price: float | None = Query(None),
    current_stop: float | None = Query(None),
    direction: str = Query("long"),
    years: int = Query(2, ge=1, le=5),
    gate: dict = Depends(resolve_monitor_poll_gate),
) -> dict:
    """国内监测页：日线 K 线 + 峰极连线 + 买入点/守护点 overlay。"""
    try:
        csv_path = resolve_csv(symbol, market)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # 监测详情页只需要 K 线、峰极线和持仓 overlay；未支持图表包的定式不要回退到
    # TOTAL，避免为了展示 DS04/DS05 等持仓而触发慢速总定式回算。
    sid = strategy_id if strategy_id in MONITOR_CHART_STRATEGIES else "DS03"
    try:
        bundle = build_chart_bundle(
            ChartBundleRequest(
                csv_path=csv_path,
                strategy_id=sid,
                years=years,
                futures_mode=market.upper() not in {"CRYPTO", "A_STOCK", "ASTOCK"},
                os_state_dir=ROOT / "runtime" / "fengji_os_state",
                os_symbol=symbol,
                os_timeframe="1d",
                os_tail_rows=1095,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    position = {
        "symbol": symbol,
        "strategy_id": strategy_id,
        "entry_time": entry_time or "",
        "entry_price": entry_price or 0,
        "current_stop": current_stop or 0,
        "direction": direction,
    }
    payload = overlay_position_on_bundle(bundle, position)
    payload["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = attach_monitor_policy(payload, gate["policy"])
    return JSONResponse(content=payload, headers={"Cache-Control": "no-store, max-age=0"})
