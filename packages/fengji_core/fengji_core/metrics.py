from __future__ import annotations

import math

import pandas as pd


TRADING_DAYS = 252


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def annual_return(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    years = len(equity) / TRADING_DAYS
    if years <= 0:
        return 0.0

    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess_daily = returns - risk_free_rate / TRADING_DAYS
    volatility = excess_daily.std(ddof=0)
    if volatility == 0 or math.isnan(volatility):
        return 0.0

    return float(excess_daily.mean() / volatility * math.sqrt(TRADING_DAYS))


def summarize(equity: pd.Series, returns: pd.Series) -> dict[str, float]:
    return {
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0),
        "annual_return": annual_return(equity),
        "max_drawdown": max_drawdown(equity),
        "sharpe": sharpe_ratio(returns),
        "final_equity": float(equity.iloc[-1]),
    }

