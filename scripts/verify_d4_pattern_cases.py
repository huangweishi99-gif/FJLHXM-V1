from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "packages" / "fengji_core"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from fengji_core.data import load_ohlcv_for_engine  # noqa: E402
from fengji_core.ds03 import make_ds03_signal, resolve_ds03_attack  # noqa: E402
from fengji_core.ds05 import audit_ds05_camp_direction, make_ds05_signal  # noqa: E402
from fengji_core.os_engine import FengJiOSIdentityEngine  # noqa: E402

DS03_CRYPTO_CASES = (
    {"symbol": "IOUSDT", "date": "2026-05-26", "window_days": 3, "note": "IO 假峰/真峰复核"},
    {"symbol": "ETHUSDT", "date": "2026-05-27", "window_days": 3, "note": "ETH 蓝阵营 DS03 复核"},
)

DS05_FUTURES_CASES = (
    {"symbol": "CJ", "label": "红枣", "csv": ROOT / "data" / "futures" / "1d" / "红枣.csv"},
    {"symbol": "FG", "label": "玻璃", "csv": ROOT / "data" / "futures" / "1d" / "玻璃.csv"},
    {"symbol": "SA", "label": "纯碱", "csv": ROOT / "data" / "futures" / "1d" / "纯碱.csv"},
)


def crypto_d1_csv(symbol: str) -> Path | None:
    for path in (
        ROOT / "data" / "overseas_1d" / f"{symbol}.csv",
        ROOT / "data" / "1d" / f"{symbol}.csv",
    ):
        if path.is_file():
            return path
    return None


def build_os_frame(csv_path: Path) -> pd.DataFrame:
    raw = load_ohlcv_for_engine(csv_path, atr_window=14)
    return FengJiOSIdentityEngine(gap=3).run(raw).to_frame(raw)


def probe_ds03_window(os_df: pd.DataFrame, center_date: str, window_days: int = 3) -> dict[str, Any]:
    center = pd.Timestamp(center_date).normalize()
    hits: list[dict[str, Any]] = []
    for i in range(len(os_df)):
        bar_day = pd.to_datetime(os_df.iloc[i]["date"]).normalize()
        if abs((bar_day - center).days) > window_days:
            continue
        attack = resolve_ds03_attack(os_df, i)
        signal = make_ds03_signal(os_df, i)
        if attack is None and signal is None:
            continue
        row = os_df.iloc[i]
        hits.append(
            {
                "date": str(bar_day.date()),
                "idx": i,
                "camp": int(row.get("camp", 0) or 0),
                "trigger_source": None if attack is None else attack.trigger_source,
                "side": None if signal is None else signal.side,
                "pattern": None if signal is None else signal.pattern,
                "entry_ref": None if signal is None else signal.entry_ref,
            }
        )
    center_rows = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == center]
    center_idx = int(center_rows[-1]) if len(center_rows) else None
    center_attack = resolve_ds03_attack(os_df, center_idx) if center_idx is not None else None
    return {
        "center_date": center_date,
        "center_idx": center_idx,
        "center_attack": None if center_attack is None else center_attack.trigger_source,
        "window_days": window_days,
        "hits": hits,
        "status": "hit" if hits else "no_hit_in_window",
    }


def scan_ds05_futures(csv_path: Path, *, tail_bars: int = 240) -> dict[str, Any]:
    if not csv_path.is_file():
        return {"status": "missing_csv", "csv": str(csv_path)}
    os_df = build_os_frame(csv_path)
    start = max(0, len(os_df) - tail_bars)
    rows: list[dict[str, Any]] = []
    for i in range(start, len(os_df)):
        signal = make_ds05_signal(os_df, i)
        if signal is None:
            continue
        if signal.k2_possible_extreme is None:
            return {
                "status": "invalid",
                "csv": str(csv_path),
                "error": f"missing k2_possible_extreme at {os_df.iloc[i]['date']}",
            }
        rows.append(
            {
                "date": str(pd.to_datetime(os_df.iloc[i]["date"]).date()),
                "side": signal.side,
                "k2_possible_extreme": float(signal.k2_possible_extreme),
                "entry_price": float(signal.entry_price),
                "initial_stop": float(signal.initial_stop),
            }
        )
    if not rows:
        return {"status": "no_signal", "csv": str(csv_path), "hits": []}
    trades = pd.DataFrame(
        {
            "direction": ["long" if r["side"] == 1 else "short" for r in rows],
            "camp_k2": [1 if r["side"] == 1 else -1 for r in rows],
            "camp_k3": [1 if r["side"] == 1 else -1 for r in rows],
        }
    )
    bad = audit_ds05_camp_direction(trades)
    if not bad.empty:
        return {"status": "invalid", "csv": str(csv_path), "audit_bad": bad.to_dict(orient="records")}
    return {"status": "ok", "csv": str(csv_path), "hits": rows, "latest": rows[-1]}


def run_pytest() -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_ds01.py",
        "tests/test_ds03.py",
        "tests/test_ds05.py",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-5:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-8:]),
    }


def run_ds05_k2_script() -> dict[str, Any]:
    script = ROOT / "scripts" / "check_ds05_k2_possible_extreme.py"
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0 and "OK_DS05_K2_POSSIBLE_EXTREME" in proc.stdout,
        "returncode": proc.returncode,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-6:]),
    }


def maybe_plot_ds03(symbol: str, hit: dict[str, Any], csv_path: Path, out_dir: Path) -> str | None:
    plot = ROOT / "scripts" / "plot_live_ds03_sandbox.py"
    if not plot.is_file() or hit.get("idx") is None:
        return None
    # plot_live_ds03_sandbox resolves data/{timeframe}/{symbol}.csv only
    if csv_path.parent.name != "1d":
        return None
    side = "long" if int(hit.get("side") or 0) == 1 else "short"
    png = out_dir / f"{symbol}_DS03_{hit['date']}_{side}.png"
    os_df = build_os_frame(csv_path)
    idx = int(hit["idx"])
    row = os_df.iloc[idx]
    trigger = float(hit.get("entry_ref") or (row["high"] if side == "long" else row["low"]))
    fill = float(row["close"])
    stop = float(row["low"] if side == "long" else row["high"])
    proc = subprocess.run(
        [
            sys.executable,
            str(plot),
            "--data-dir",
            "data",
            "--timeframe",
            "1d",
            "--symbol",
            symbol,
            "--date",
            hit["date"],
            "--side",
            side,
            "--fill-price",
            str(fill),
            "--trigger-price",
            str(trigger),
            "--stop-price",
            str(stop),
            "--out",
            str(png),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return str(png) if proc.returncode == 0 and png.is_file() else None


def resolve_ds05_trade_no(csv_path: Path, entry_date: str) -> int | None:
    from backtest_ds05 import DS05BacktestConfig, run_ds05_backtest
    from quant.data import load_ohlcv_for_engine
    from quant.futures_specs import get_futures_spec

    raw = load_ohlcv_for_engine(csv_path, atr_window=14)
    config = DS05BacktestConfig(
        futures_mode=True,
        spec=get_futures_spec(csv_path),
        gap=3,
    )
    result = run_ds05_backtest(raw, config)
    trades = result.get("trades")
    if not isinstance(trades, pd.DataFrame) or trades.empty:
        return None
    for _, row in trades.iterrows():
        if str(row.get("entry_date"))[:10] == entry_date:
            return int(row.get("trade_no"))
    return None


def maybe_plot_ds05(label: str, symbol: str, hit: dict[str, Any], csv_path: Path, out_dir: Path) -> str | None:
    plot = ROOT / "src" / "plot_ds05_sandbox.py"
    if not plot.is_file():
        return None
    trade_no = resolve_ds05_trade_no(csv_path, hit["date"])
    if trade_no is None:
        return None
    png = out_dir / f"{symbol}_{label}_DS05_{hit['date']}.png"
    proc = subprocess.run(
        [
            sys.executable,
            str(plot),
            "--csv",
            str(csv_path),
            "--trade-no",
            str(trade_no),
            "--futures-mode",
            "--out",
            str(png),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return str(png) if proc.returncode == 0 and png.is_file() else None


def build_report(*, plot: bool, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "read_only_regression",
        "sections": {},
    }

    pytest_result = run_pytest()
    ds05_k2 = run_ds05_k2_script()
    report["sections"]["ds01_ds03_ds05_unit"] = pytest_result
    report["sections"]["ds05_k2_synthetic"] = ds05_k2

    ds03_cases: list[dict[str, Any]] = []
    for case in DS03_CRYPTO_CASES:
        symbol = case["symbol"]
        csv_path = crypto_d1_csv(symbol)
        item: dict[str, Any] = dict(case)
        if csv_path is None:
            item["status"] = "missing_csv"
            ds03_cases.append(item)
            continue
        probe = probe_ds03_window(build_os_frame(csv_path), case["date"], case["window_days"])
        item.update({"csv": str(csv_path), "probe": probe, "status": probe["status"]})
        if plot and probe["hits"]:
            item["png"] = maybe_plot_ds03(symbol, probe["hits"][-1], csv_path, out_dir)
        ds03_cases.append(item)
    report["sections"]["ds03_crypto_cases"] = ds03_cases

    ds05_cases: list[dict[str, Any]] = []
    for case in DS05_FUTURES_CASES:
        item = dict(case)
        item.pop("csv")
        scan = scan_ds05_futures(case["csv"])
        item["scan"] = scan
        item["status"] = scan["status"]
        if plot and scan.get("latest"):
            item["png"] = maybe_plot_ds05(case["label"], case["symbol"], scan["latest"], case["csv"], out_dir)
        ds05_cases.append(item)
    report["sections"]["ds05_futures_cases"] = ds05_cases

    hard_fail = []
    if not pytest_result["ok"]:
        hard_fail.append("unit_tests")
    if not ds05_k2["ok"]:
        hard_fail.append("ds05_k2_synthetic")
    for row in ds05_cases:
        if row["status"] == "invalid":
            hard_fail.append(f"ds05_{row['symbol']}")
    report["hard_fail"] = hard_fail
    report["ok"] = not hard_fail
    return report


def write_summary_md(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# D4 定式案例回归",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        f"**总体：{'PASS' if report.get('ok') else 'FAIL'}**",
        "",
        "## 单元测试",
        "",
        f"- DS01/DS03/DS05 pytest: **{'OK' if report['sections']['ds01_ds03_ds05_unit']['ok'] else 'FAIL'}**",
        f"- DS05 K2 合成口径: **{'OK' if report['sections']['ds05_k2_synthetic']['ok'] else 'FAIL'}**",
        "",
        "## DS03 争议日（D1 ±窗口）",
        "",
        "| 品种 | 中心日 | 窗口内命中 | 中心日 attack | 说明 |",
        "|---|---|---|---|---|",
    ]
    for row in report["sections"]["ds03_crypto_cases"]:
        probe = row.get("probe") or {}
        hits = probe.get("hits") or []
        hit_txt = "; ".join(f"{h['date']}:{h.get('trigger_source')}" for h in hits) or "—"
        lines.append(
            f"| {row['symbol']} | {row['date']} | {len(hits)} | {probe.get('center_attack') or '—'} | {row.get('note','')} |"
        )
        if hits:
            lines.append(f"| | | `{hit_txt}` | | |")
    lines.extend(["", "## DS05 国内期货（K2 可能极）", "", "| 品种 | 状态 | 最近命中 | k2_possible_extreme |", "|---|---|---|---:|"])
    for row in report["sections"]["ds05_futures_cases"]:
        latest = (row.get("scan") or {}).get("latest") or {}
        lines.append(
            f"| {row['label']} ({row['symbol']}) | {row['status']} | {latest.get('date','—')} | {latest.get('k2_possible_extreme','—')} |"
        )
    if report.get("hard_fail"):
        lines.extend(["", "## 硬失败", ""])
        for item in report["hard_fail"]:
            lines.append(f"- {item}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase2 D4 pattern case regression (DS01/03/05).")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "results" / "sandbox" / f"d4_phase2_{datetime.now().strftime('%Y%m%d')}",
    )
    parser.add_argument("--plot", action="store_true", help="Emit DS03/DS05 sandbox PNGs when hits exist.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(plot=args.plot, out_dir=args.out_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "d4_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary_md(report, args.out_dir / "SUMMARY.md")
    print("D4_PATTERN_VERIFY", "ok" if report["ok"] else "fail", f"out={args.out_dir}")
    if not report["ok"]:
        print("D4_HARD_FAIL", ",".join(report["hard_fail"]), file=sys.stderr)
        return 1
    print("D4_VERIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
