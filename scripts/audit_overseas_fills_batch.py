"""Audit overseas pending-order fills: DS01/DS03 sandbox + rule checks."""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from backtest_ds07 import build_os_detail_frame
from quant.ds01 import ds01_left_filter_pass, entry_fill
from quant.ds03 import resolve_ds03_attack
from quant.os_engine import BLUE, RED

# 2026-05-28 11:16 国外挂单模拟成交（来自 runtime/fengji_pending_orders/fills.csv）
# 字段来自 fills.csv：fill_price, trigger_price, stop_price（勿与 current_price 混淆）
FILLS_20260528 = [
    {"symbol": "BTCUSDT", "strategy": "DS01", "side": "short", "entry_date": "2026-05-28", "entry_price": 74140.47, "trigger_price": 74243.99, "stop_price": 76174.15, "left_count": 0},
    {"symbol": "ETHUSDT", "strategy": "DS01", "side": "short", "entry_date": "2026-05-28", "entry_price": 2010.23, "trigger_price": 2016.0, "stop_price": 2097.4, "left_count": 0},
    {"symbol": "LINKUSDT", "strategy": "DS01", "side": "short", "entry_date": "2026-05-28", "entry_price": 9.078, "trigger_price": 9.099, "stop_price": 9.484, "left_count": 1},
    {"symbol": "SOLUSDT", "strategy": "DS01", "side": "short", "entry_date": "2026-05-28", "entry_price": 81.81, "trigger_price": 82.1, "stop_price": 84.84, "left_count": 1},
    {"symbol": "TAOUSDT", "strategy": "DS01", "side": "short", "entry_date": "2026-05-28", "entry_price": 263.0, "trigger_price": 265.2, "stop_price": 286.7, "left_count": 2},
    {"symbol": "IOUSDT", "strategy": "DS03", "side": "long", "entry_date": "2026-05-28", "entry_price": 0.1706, "trigger_price": 0.1602, "stop_price": 0.1676, "attack_idx": 708},
    {"symbol": "ADAUSDT", "strategy": "DS01", "side": "short", "entry_date": "2026-05-28", "entry_price": 0.236, "trigger_price": 0.236, "stop_price": 0.2435, "left_count": 0},
    {"symbol": "TRUMPUSDT", "strategy": "DS01", "side": "short", "entry_date": "2026-05-28", "entry_price": 1.909, "trigger_price": 1.918, "stop_price": 2.034, "left_count": 0},
]


def symbol_to_csv(data_dir: Path, symbol: str) -> Path:
    base = symbol.replace("USDT", "")
    candidates: list[Path] = []
    for folder in ("overseas_1d", "crypto_okx", "."):
        candidates.extend(
            [
                data_dir / folder / f"{symbol}.csv",
                data_dir / folder / f"{base}-USDT_1D_1825d.csv",
                data_dir / folder / f"{base}-USDT_1D_180d.csv",
            ]
        )
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"No D1 csv for {symbol} under {data_dir}")


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def audit_ds01(row: dict, csv_path: Path) -> dict:
    raw = load_csv(csv_path)
    os_df, engine = build_os_detail_frame(raw, gap=3)
    entry_day = pd.to_datetime(row["entry_date"]).normalize()
    matches = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == entry_day]
    if len(matches) == 0:
        return {"verdict": "needs-data", "reason": f"entry date {entry_day} not in csv"}
    i = int(matches[-1])
    if i < 1:
        return {"verdict": "invalid", "reason": "no previous bar for signal stick"}

    side = -1 if row["side"] == "short" else 1
    cur = os_df.iloc[i]
    prev = os_df.iloc[i - 1]
    camp_today = int(cur.get("camp", 0) or 0)
    camp_need = RED if side == 1 else BLUE
    trigger = float(prev["low"] if side == -1 else prev["high"])
    stop = float(prev["high"] if side == -1 else prev["low"])
    fill_ok = entry_fill(cur, side, trigger) is not None
    visible_nodes = engine.hardened_by_bar[i - 1] if engine.hardened_by_bar else []
    left_check = float(cur["low"] if side == -1 else cur["high"])
    left_ok, left_count = ds01_left_filter_pass(visible_nodes, i, left_check, False, 30)

    issues = []
    if camp_today != camp_need:
        issues.append(f"camp_today={camp_today} expected={camp_need}")
    if side == -1 and not (float(prev["close"]) < float(prev["open"])):
        issues.append("signal bar not bearish")
    if side == 1 and not (float(prev["close"]) > float(prev["open"])):
        issues.append("signal bar not bullish")
    if not fill_ok:
        issues.append("entry_fill=False on entry bar OHLC")
    if not left_ok:
        issues.append(f"left30 fail count={left_count}")
    if abs(trigger - float(row["trigger_price"])) > max(1e-6, abs(trigger) * 0.002):
        issues.append(f"trigger mismatch calc={trigger} fill={row['trigger_price']}")
    if abs(stop - float(row["stop_price"])) > max(1e-6, abs(stop) * 0.002):
        issues.append(f"stop mismatch calc={stop} fill={row['stop_price']}")
    if int(row.get("left_count", -1)) != left_count:
        issues.append(f"left_count mismatch fill={row.get('left_count')} calc={left_count}")

    verdict = "valid" if not issues else "invalid"
    return {
        "verdict": verdict,
        "issues": issues,
        "camp_today": camp_today,
        "trigger_calc": trigger,
        "stop_calc": stop,
        "fill_ok": fill_ok,
        "left_ok": left_ok,
        "left_count": left_count,
        "signal_date": str(prev["date"]),
    }


def audit_ds03(row: dict, csv_path: Path) -> dict:
    raw = load_csv(csv_path)
    engine_df, engine = build_os_detail_frame(raw, gap=3)
    entry_day = pd.to_datetime(row["entry_date"]).normalize()
    matches = engine_df.index[pd.to_datetime(engine_df["date"]).dt.normalize() == entry_day]
    if len(matches) == 0:
        return {"verdict": "needs-data", "reason": "entry date missing"}
    i = int(matches[-1])
    camp = int(engine_df.iloc[i].get("camp", 0) or 0)
    attack_idx = int(row.get("attack_idx", -1))
    issues = []
    if camp != RED:
        issues.append(f"camp={camp} expected RED for long DS03")
    attack = resolve_ds03_attack(engine_df, i)
    if attack is None:
        issues.append("resolve_ds03_attack returned None on entry bar")
    else:
        trig_calc = float(attack.entry_ref)
        if attack.side != 1:
            issues.append(f"attack.side={attack.side} expected 1")
        if abs(trig_calc - float(row["trigger_price"])) > max(1e-8, trig_calc * 0.01):
            issues.append(f"trigger mismatch calc={trig_calc} fill={row['trigger_price']}")
        if str(attack.trigger_source) != "failed_high" and "failed" not in str(attack.trigger_source):
            issues.append(f"unexpected trigger_source={attack.trigger_source}")
        # DS03 守势止损在雷达侧单独计算，此处仅核对触发价来源
        pass
    verdict = "valid" if not issues else "invalid"
    return {"verdict": verdict, "issues": issues, "camp": camp}


def plot_ds01(row: dict, csv_path: Path, out: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "plot_crypto_ds01_trade_sandbox.py"),
            "--csv",
            str(csv_path),
            "--symbol",
            row["symbol"],
            "--side",
            row["side"],
            "--entry-date",
            row["entry_date"],
            "--entry-price",
            str(row["entry_price"]),
            "--stop-price",
            str(row["stop_price"]),
            "--out",
            str(out),
        ],
        check=True,
        cwd=str(ROOT),
    )


def plot_ds03(row: dict, csv_path: Path, out: Path) -> None:
    import shutil

    staging = out.parent / "_data_staging" / "1d"
    staging.mkdir(parents=True, exist_ok=True)
    dest = staging / f"{row['symbol']}.csv"
    if not dest.exists():
        shutil.copy(csv_path, dest)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "plot_live_ds03_sandbox.py"),
            "--data-dir",
            str(staging.parent),
            "--symbol",
            row["symbol"],
            "--timeframe",
            "1d",
            "--date",
            row["entry_date"],
            "--side",
            row["side"],
            "--fill-price",
            str(row["entry_price"]),
            "--trigger-price",
            str(row["trigger_price"]),
            "--stop-price",
            str(row["stop_price"]),
            "--out",
            str(out),
        ],
        check=True,
        cwd=str(ROOT),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "sandbox" / "overseas_20260528"))
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = ["# 国外模拟挂单沙盒审计（2026-05-28 11:16 批次）", ""]
    for row in FILLS_20260528:
        sym = row["symbol"]
        strat = row["strategy"]
        lines.append(f"## {sym} {strat} {row['side']}")
        try:
            csv_path = symbol_to_csv(data_dir, sym)
        except FileNotFoundError as exc:
            lines.append(f"- **结论**: needs-data — {exc}")
            lines.append("")
            continue

        if strat == "DS01":
            audit = audit_ds01(row, csv_path)
            png = out_dir / f"{sym}_{strat}_{row['side']}.png"
            if not args.no_plot:
                plot_ds01(row, csv_path, png)
        else:
            audit = audit_ds03(row, csv_path)
            png = out_dir / f"{sym}_{strat}_{row['side']}.png"
            if not args.no_plot:
                plot_ds03(row, csv_path, png)

        lines.append(f"- **结论**: {audit['verdict']}")
        if audit.get("reason"):
            lines.append(f"  - {audit['reason']}")
        if audit.get("issues"):
            for issue in audit["issues"]:
                lines.append(f"  - {issue}")
        elif audit["verdict"] == "valid":
            lines.append("  - OS/价格/左30 与挂单记录一致")
        if audit.get("signal_date"):
            lines.append(f"  - 信号棍日期: {audit['signal_date']}")
        if audit.get("camp_today") is not None:
            lines.append(
                f"  - camp={audit['camp_today']} trigger_calc={audit.get('trigger_calc')} "
                f"stop_calc={audit.get('stop_calc')} left_count={audit.get('left_count')}"
            )
        if not args.no_plot:
            lines.append(f"- **沙盒图**: `{png.relative_to(ROOT).as_posix()}`")
        lines.append("")

    report = out_dir / "AUDIT_REPORT.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
