"""Domestic futures actual main-contract lookup (tq_actual_main_contract manifest)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST_PATHS: tuple[str, ...] = (
    "runtime/logs/futures_main_contract_sources.json",
    "runtime/domestic_futures_main_contract_sources.json",
)


def project_root() -> Path:
    env = os.getenv("FENGJI_PROJECT_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def short_code_from_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper().replace("-", "").replace("_", "")
    if text.endswith("USDT"):
        text = text[:-4]
    return text


def manifest_paths(root: Path | None = None) -> list[Path]:
    base = root or project_root()
    paths: list[Path] = []
    env = os.getenv("FUTURES_MAIN_CONTRACT_MANIFEST", "").strip()
    if env:
        paths.append(Path(env).expanduser())
    for rel in DEFAULT_MANIFEST_PATHS:
        paths.append(base / rel)
    return paths


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    for path in manifest_paths(root):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("symbols"), dict):
                return payload
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def lookup_data_contract(short_code: str, manifest: dict[str, Any] | None = None) -> str:
    code = short_code_from_symbol(short_code)
    if not code or code.isdigit():
        return ""
    payload = manifest if manifest is not None else load_manifest()
    symbols = payload.get("symbols") if isinstance(payload, dict) else None
    if not isinstance(symbols, dict):
        return ""
    entry = symbols.get(code)
    if not isinstance(entry, dict):
        return ""
    for key in ("data_contract", "underlying_symbol", "display_contract"):
        value = str(entry.get(key) or "").strip()
        if value and not value.startswith("KQ.m@"):
            return value
    return ""


def parse_contract_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:19])
    except ValueError:
        return None


def detect_order_contract_switch(
    order: dict[str, Any],
    manifest: dict[str, Any] | None = None,
    *,
    observed_at: Any = None,
) -> dict[str, str] | None:
    """Return contract-switch details when an order belongs to the previous contract."""
    code = short_code_from_symbol(str(order.get("symbol", "")))
    payload = manifest if manifest is not None else load_manifest()
    symbols = payload.get("symbols") if isinstance(payload, dict) else None
    entry = symbols.get(code) if isinstance(symbols, dict) else None
    if not isinstance(entry, dict):
        return None

    current = str(entry.get("data_contract") or "").strip()
    previous = str(entry.get("previous_data_contract") or "").strip()
    switched_at_text = str(entry.get("contract_switched_at") or "").strip()
    order_contract = str(order.get("data_contract") or order.get("entry_data_contract") or "").strip()
    if not current:
        return None

    if order_contract and order_contract != current:
        return {
            "order_contract": order_contract,
            "current_contract": current,
            "previous_contract": previous,
            "contract_switched_at": switched_at_text,
            "detection": "explicit_order_contract",
        }

    created_at = parse_contract_timestamp(order.get("created_at"))
    switched_at = parse_contract_timestamp(switched_at_text)
    observed = parse_contract_timestamp(observed_at or order.get("time") or order.get("fill_time"))
    if (
        not order_contract
        and previous
        and previous != current
        and created_at is not None
        and switched_at is not None
        and observed is not None
        and created_at <= switched_at <= observed
    ):
        return {
            "order_contract": previous,
            "current_contract": current,
            "previous_contract": previous,
            "contract_switched_at": switched_at_text,
            "detection": "legacy_order_created_before_switch",
        }
    return None


def stamp_entry_data_contract(position: dict[str, Any], symbol: str, *, root: Path | None = None) -> dict[str, Any]:
    """Attach entry_data_contract for futures positions (audit only, no alerts)."""
    code = short_code_from_symbol(symbol)
    if not code or code.isdigit():
        return position
    contract = lookup_data_contract(code, load_manifest(root))
    if contract:
        position["entry_data_contract"] = contract
    return position
