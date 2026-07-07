from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
for item in (ROOT / "src", ROOT / "packages" / "fengji_core"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from verify_d4_pattern_cases import probe_ds03_window, scan_ds05_futures  # noqa: E402
from fengji_core.ds03 import make_ds03_signal, resolve_ds03_attack  # noqa: E402
from fengji_core.os_engine import FengJiOSIdentityEngine  # noqa: E402


def _mini_os_df() -> pd.DataFrame:
    rows = []
    for i in range(10):
        rows.append(
            {
                "date": pd.Timestamp("2026-05-20") + pd.Timedelta(days=i),
                "open": 9.0,
                "high": 9.2,
                "low": 8.8,
                "close": 9.0,
                "camp": 1,
                "active_high": 10.0,
                "active_low": 8.0,
                "red_peak_idx": 1,
                "red_ext_idx": 3,
                "last_failed_high_idx": float("nan"),
                "last_failed_high_price": float("nan"),
                "blue_peak_idx": float("nan"),
                "blue_ext_idx": float("nan"),
                "last_failed_low_idx": float("nan"),
                "last_failed_low_price": float("nan"),
            }
        )
    df = pd.DataFrame(rows)
    df.loc[7, "high"] = 9.7
    df.loc[7, "last_failed_high_idx"] = 4
    df.loc[7, "last_failed_high_price"] = 9.5
    df.loc[7, "red_ext_idx"] = 6
    return df


def test_probe_ds03_window_finds_fake_peak() -> None:
    probe = probe_ds03_window(_mini_os_df(), "2026-05-27", window_days=3)
    assert probe["status"] == "hit"
    assert any(h.get("trigger_source") == "fake_peak" for h in probe["hits"])


def test_scan_ds05_futures_missing_csv(tmp_path: Path) -> None:
    out = scan_ds05_futures(tmp_path / "missing.csv")
    assert out["status"] == "missing_csv"
