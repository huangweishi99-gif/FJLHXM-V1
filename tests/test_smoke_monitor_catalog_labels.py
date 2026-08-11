"""HTTP smoke: catalog API labels must not duplicate adjacent Chinese names."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

import pytest


def _catalog_display_label(row: dict) -> str:
    display = str(row.get("display_symbol") or "").strip()
    sym = str(row.get("symbol") or "").strip()
    name = str(row.get("symbol_name") or "").strip()
    title = display or sym or name or "—"
    if name and name != sym and name not in title:
        title = f"{title} · {name}"
    return title


def _has_adjacent_dup(label: str) -> bool:
    parts = [p.strip() for p in label.split("·")]
    return any(parts[i] and parts[i] == parts[i + 1] for i in range(len(parts) - 1))


def _fetch_summary(base_url: str, market: str) -> list[dict]:
    q = urllib.parse.urlencode({"market": market, "limit": "50"})
    url = f"{base_url.rstrip('/')}/api/v1/backtests/symbol-summary?{q}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)


@pytest.mark.parametrize("market", ["FUTURES", "A_STOCK", "CRYPTO", "US_STOCK"])
def test_symbol_summary_labels_no_adjacent_duplicate(market: str) -> None:
    base = "http://127.0.0.1:8000"
    try:
        rows = _fetch_summary(base, market)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        pytest.skip(f"API unavailable at {base}: {exc}")
    assert rows, f"{market} catalog empty"
    bad = []
    for row in rows:
        label = _catalog_display_label(row)
        if _has_adjacent_dup(label):
            bad.append(label)
    assert not bad, f"{market} duplicate labels: {bad[:5]}"
