"""只读雷达快照：读取 runtime radar.csv，供 Web/API 展示（不改挂单、不写 paper_state）。"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

RADAR_PATHS = (
    Path(os.getenv("FENGJI_RADAR_CSV_PATH", "")).expanduser()
    if os.getenv("FENGJI_RADAR_CSV_PATH", "").strip()
    else None,
    ROOT / "runtime" / "fengji_radar" / "radar.csv",
    ROOT / "runtime" / "remote_domestic_radar" / "radar.csv",
    ROOT / "runtime" / "remote_overseas_radar" / "radar.csv",
)


def infer_radar_market(symbol: str) -> str:
    sym = str(symbol or "").strip().upper()
    if sym.isdigit() or (len(sym) == 6 and sym.isdigit()):
        return "A_STOCK"
    base = sym[:-4] if sym.endswith("USDT") else sym
    try:
        from fengji_core.symbol_names import FUTURES_CN_NAMES

        if base in FUTURES_CN_NAMES:
            return "FUTURES"
    except Exception:
        pass
    if sym.endswith("USDT"):
        return "CRYPTO"
    return "FUTURES"


def _radar_candidates() -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in RADAR_PATHS:
        if path is not None and path.is_file() and path not in seen:
            seen.add(path)
            out.append(path)
    runtime = ROOT / "runtime"
    if runtime.is_dir():
        discovered = [
            path
            for path in runtime.rglob("radar.csv")
            if path.is_file() and path not in seen and "backup" not in path.parts
        ]
        discovered.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for path in discovered[:6]:
            seen.add(path)
            out.append(path)
    return out


def _normalize_row(raw: dict[str, Any]) -> dict[str, Any]:
    symbol = str(raw.get("symbol") or "").strip().upper()
    strategy_id = str(raw.get("strategy_id") or "").strip().upper()
    side = str(raw.get("side") or "").strip().lower()
    status = str(raw.get("status") or "").strip().upper()
    try:
        score = float(raw.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    for key in ("current_price", "trigger_price", "distance_pct", "stop_price"):
        if key in raw and raw[key] not in {None, ""}:
            try:
                raw[key] = float(raw[key])
            except (TypeError, ValueError):
                pass
    return {
        "symbol": symbol,
        "strategy_id": strategy_id,
        "timeframe": str(raw.get("timeframe") or "").strip(),
        "side": side,
        "status": status,
        "setup": str(raw.get("setup") or ""),
        "current_price": raw.get("current_price"),
        "trigger_price": raw.get("trigger_price"),
        "distance_pct": raw.get("distance_pct"),
        "stop_price": raw.get("stop_price"),
        "os_camp": str(raw.get("os_camp") or "").strip().lower(),
        "latest_time": str(raw.get("latest_time") or ""),
        "score": score,
        "reason": str(raw.get("reason") or ""),
        "setup_key": str(raw.get("setup_key") or ""),
        "market": infer_radar_market(symbol),
    }


def load_latest_radar(*, limit: int = 80) -> dict[str, Any]:
    """读取最新 radar.csv；无文件时返回空列表。"""
    limit = max(1, min(int(limit), 500))
    for path in _radar_candidates():
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as fh:
                rows = [_normalize_row(row) for row in csv.DictReader(fh)]
        except Exception as exc:
            return {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "error",
                "source_path": str(path.name),
                "error": str(exc),
                "count": 0,
                "rows": [],
            }
        rows.sort(key=lambda r: (-float(r.get("score") or 0), r.get("symbol", ""), r.get("strategy_id", "")))
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "radar_csv",
            "source_path": str(path),
            "count": min(len(rows), limit),
            "rows": rows[:limit],
        }
    json_path = ROOT / "runtime" / "fengji_radar" / "radar.json"
    if json_path.is_file():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                rows = [_normalize_row(row) for row in payload if isinstance(row, dict)]
                rows.sort(key=lambda r: (-float(r.get("score") or 0), r.get("symbol", ""), r.get("strategy_id", "")))
                return {
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "radar_json",
                    "source_path": str(json_path),
                    "count": min(len(rows), limit),
                    "rows": rows[:limit],
                }
        except Exception as exc:
            return {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "error",
                "source_path": str(json_path.name),
                "error": str(exc),
                "count": 0,
                "rows": [],
            }
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "empty",
        "source_path": None,
        "count": 0,
        "rows": [],
    }
