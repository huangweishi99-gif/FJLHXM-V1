from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate_sample_ohlcv(days: int = 900, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=days)

    drift = 0.00035
    volatility = 0.018
    returns = rng.normal(drift, volatility, size=days)
    close = 100 * np.cumprod(1 + returns)
    open_ = close * (1 + rng.normal(0, 0.003, size=days))
    high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.018, size=days))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.018, size=days))
    volume = rng.integers(800_000, 5_000_000, size=days)

    return pd.DataFrame(
        {
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate sample OHLCV data.")
    parser.add_argument("--out", default="data/sample_ohlcv.csv")
    parser.add_argument("--days", type=int, default=900)
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    generate_sample_ohlcv(days=args.days, seed=args.seed).to_csv(out_path, index=False)
    print(f"Saved {args.days} rows to {out_path}")


if __name__ == "__main__":
    main()

