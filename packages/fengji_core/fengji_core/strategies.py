from __future__ import annotations

import pandas as pd


def moving_average_cross_signal(
    close: pd.Series,
    short_window: int = 20,
    long_window: int = 60,
) -> pd.DataFrame:
    """Return long-only signal for a moving-average crossover strategy."""
    if short_window <= 0 or long_window <= 0:
        raise ValueError("Windows must be positive integers.")
    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window.")

    signal = pd.DataFrame(index=close.index)
    signal["close"] = close
    signal["short_ma"] = close.rolling(short_window).mean()
    signal["long_ma"] = close.rolling(long_window).mean()
    signal["position"] = (signal["short_ma"] > signal["long_ma"]).astype(int)
    signal["position"] = signal["position"].where(signal["long_ma"].notna(), 0)
    return signal

