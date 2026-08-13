#!/usr/bin/env python3
"""Generate minimal Lottie placeholder JSON for DS01–DS09 + TOTAL (O1 bootstrap).

Prefer illustrative assets from:
  python scripts/build_strategy_lottie_illustrations.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "assets" / "lottie"

COLORS = {
    "DS01": [0.83, 0.69, 0.22, 1],
    "DS02": [0.55, 0.45, 0.95, 1],
    "DS03": [0.95, 0.45, 0.55, 1],
    "DS04": [0.45, 0.75, 0.55, 1],
    "DS05": [0.45, 0.65, 0.95, 1],
    "DS06": [0.95, 0.75, 0.35, 1],
    "DS07": [0.35, 0.85, 0.85, 1],
    "DS08": [0.85, 0.55, 0.35, 1],
    "DS09": [0.75, 0.35, 0.85, 1],
    "TOTAL": [0.83, 0.69, 0.22, 1],
}


def build(name: str, rgba: list[float]) -> dict:
    return {
        "v": "5.7.4",
        "fr": 30,
        "ip": 0,
        "op": 300,
        "w": 160,
        "h": 88,
        "nm": f"{name} placeholder",
        "ddd": 0,
        "assets": [],
        "layers": [
            {
                "ddd": 0,
                "ind": 1,
                "ty": 4,
                "nm": name,
                "sr": 1,
                "ks": {
                    "o": {"a": 0, "k": 100},
                    "r": {"a": 0, "k": 0},
                    "p": {"a": 0, "k": [80, 44, 0]},
                    "a": {"a": 0, "k": [0, 0, 0]},
                    "s": {
                        "a": 1,
                        "k": [
                            {"t": 0, "s": [100, 100, 100], "i": {"x": [0.667], "y": [1]}, "o": {"x": [0.333], "y": [0]}},
                            {"t": 150, "s": [118, 118, 100], "i": {"x": [0.667], "y": [1]}, "o": {"x": [0.333], "y": [0]}},
                            {"t": 300, "s": [100, 100, 100]},
                        ],
                    },
                },
                "ao": 0,
                "shapes": [
                    {
                        "ty": "el",
                        "p": {"a": 0, "k": [0, 0]},
                        "s": {"a": 0, "k": [36, 36]},
                        "nm": "Ellipse",
                        "mn": "ADBE Vector Shape - Ellipse",
                        "hd": False,
                    },
                    {
                        "ty": "fl",
                        "c": {"a": 0, "k": rgba},
                        "o": {"a": 0, "k": 100},
                        "r": 1,
                        "nm": "Fill",
                        "mn": "ADBE Vector Graphic - Fill",
                        "hd": False,
                    },
                ],
                "ip": 0,
                "op": 300,
                "st": 0,
                "bm": 0,
            }
        ],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for sid, color in COLORS.items():
        path = OUT / f"{sid}.json"
        path.write_text(json.dumps(build(sid, color), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {path}")
    manifest = OUT / "manifest.json"
    manifest.write_text(
        json.dumps({"version": 1, "strategies": list(COLORS.keys())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
