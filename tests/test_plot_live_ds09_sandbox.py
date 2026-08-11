from __future__ import annotations

import pandas as pd

from scripts.plot_live_ds09_sandbox import normalize_indices, parse_ds09_metadata


def test_parse_ds09_metadata_accepts_idx_suffixes() -> None:
    metadata = parse_ds09_metadata(
        "TAUSDT|DS09|SHORT|2026-06-14 00:00:00|attack=953|6226",
        "lock_idx=953, attack_idx=953, defense_idx=956, boundary=6230",
    )

    assert metadata["session"] == "2026-06-14 00:00:00"
    assert metadata["lock_idx"] == 953
    assert metadata["attack_idx"] == 953
    assert metadata["defense_idx"] == 956


def test_normalize_indices_relocates_far_historical_indexes() -> None:
    rows = []
    for idx in range(1000):
        base = 100.0
        rows.append(
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=15 * idx),
                "open": base,
                "high": base + 1,
                "low": base - 1,
                "close": base,
            }
        )
    rows[790].update({"open": 118.0, "high": 121.0, "low": 117.0, "close": 120.0})
    rows[800].update({"open": 128.0, "high": 131.0, "low": 127.0, "close": 129.0})
    rows[810].update({"open": 108.0, "high": 111.0, "low": 107.0, "close": 109.0})
    df = pd.DataFrame(rows)

    metadata = {"lock_idx": 100, "attack_idx": 110, "defense_idx": 120}
    normalized = normalize_indices(
        df,
        metadata,
        entry_idx=820,
        trigger_price=130.0,
        stop_price=110.0,
        boundary=120.0,
        before=80,
    )

    assert normalized["lock_idx"] == 790
    assert normalized["attack_idx"] == 800
    assert normalized["defense_idx"] == 810
    assert normalized["relocations"]["attack_idx"]["from"] == 110
