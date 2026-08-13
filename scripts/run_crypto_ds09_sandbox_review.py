"""Crypto DS09 session diagnostic + sandbox overview (read-only)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
os.environ.setdefault("FENGJI_MARKET", "crypto")

from backtest_ds09 import DS09BacktestConfig, build_os_detail_frame, load_frame, load_m15_frame, run_ds09_backtest  # noqa: E402
from fengji_core.ds09 import assign_session_date, build_prev_day_boundary_map, make_ds09_signal  # noqa: E402
from fengji_core.os_state_store import os_state_path  # noqa: E402
from fengji_total_radar import build_os_detail_frame_stateful, find_data_file, load_ohlcv, normalize_symbol  # noqa: E402


def stage_label(day_state: dict[str, Any]) -> str:
    if day_state.get("lock_idx") is None:
        return "await_lock"
    if day_state.get("attack_idx") is None:
        return "await_attack_peak"
    if day_state.get("defense_idx") is None:
        return "await_defense_ext"
    if day_state.get("consumed"):
        return "consumed"
    return "await_second_attack"


def replay_all_sessions(m15_sess: pd.DataFrame, boundary_map: dict, symbol: str) -> dict[str, Any]:
    locks = 0
    signals = 0
    lock_sessions: list[str] = []
    signal_sessions: list[str] = []
    day_states: dict[pd.Timestamp, dict[str, Any]] = {}

    for i, row in m15_sess.iterrows():
        sd = pd.to_datetime(row["session_date"]).normalize()
        if sd not in boundary_map:
            continue
        if sd not in day_states:
            day_states[sd] = {
                **boundary_map[sd],
                "lock_idx": None,
                "consumed": False,
                "attack_idx": None,
                "attack_price": None,
                "defense_idx": None,
                "defense_price": None,
            }
        st = day_states[sd]
        if st.get("consumed"):
            continue
        if st.get("lock_idx") is None:
            boundary = float(st["boundary"])
            if st["mode"] == "LONG" and float(row["high"]) > boundary:
                st["lock_idx"] = int(i)
                locks += 1
                lock_sessions.append(str(sd.date()))
            elif st["mode"] == "SHORT" and float(row["low"]) < boundary:
                st["lock_idx"] = int(i)
                locks += 1
                lock_sessions.append(str(sd.date()))
        else:
            sig = make_ds09_signal(row, st, symbol=symbol)
            if sig is not None:
                signals += 1
                signal_sessions.append(str(sd.date()))

    latest_sd = pd.to_datetime(m15_sess.iloc[-1]["session_date"]).normalize()
    latest = day_states.get(latest_sd)
    latest_row = m15_sess[pd.to_datetime(m15_sess["session_date"]).dt.normalize() == latest_sd]
    pierce = None
    if latest and not latest_row.empty:
        boundary = float(latest["boundary"])
        if latest["mode"] == "LONG":
            pierce = float(latest_row["high"].max()) > boundary
        else:
            pierce = float(latest_row["low"].min()) < boundary
    return {
        "boundary_sessions": len(boundary_map),
        "locks": locks,
        "signals": signals,
        "lock_sessions": lock_sessions[-8:],
        "signal_sessions": signal_sessions[-8:],
        "latest_session": str(latest_sd.date()),
        "latest_boundary": latest,
        "latest_stage": stage_label(latest) if latest else "no_boundary",
        "latest_m15_camp": int(latest_row.iloc[-1].get("camp", 0)) if not latest_row.empty else None,
        "latest_m15_bars": len(latest_row),
        "latest_pierce": pierce,
    }


def maybe_plot_session(
    symbol: str,
    d1_os: pd.DataFrame,
    m15_sess: pd.DataFrame,
    session: pd.Timestamp,
    boundary_map: dict,
    out_path: Path,
) -> bool:
    try:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except ImportError:
        return False

    if session not in boundary_map:
        return False
    info = boundary_map[session]
    day = m15_sess[pd.to_datetime(m15_sess["session_date"]).dt.normalize() == session].copy()
    if day.empty:
        return False

    def draw_candles(ax, df: pd.DataFrame, width: float) -> None:
        xs = mdates.date2num(pd.to_datetime(df["date"]))
        for x, (_, row) in zip(xs, df.iterrows()):
            o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
            color = "#d62728" if c >= o else "#1f77b4"
            ax.vlines(x, l, h, color=color, linewidth=0.8)
            ax.add_patch(
                Rectangle((x - width / 2, min(o, c)), width, max(abs(c - o), 1e-12), facecolor=color, edgecolor=color, alpha=0.75)
            )

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    d1 = d1_os.copy()
    d1["d"] = pd.to_datetime(d1["date"]).dt.normalize()
    d1_win = d1[(d1["d"] >= session - pd.Timedelta(days=3)) & (d1["d"] <= session + pd.Timedelta(days=1))]

    pierce = (
        float(day["high"].max()) > float(info["boundary"])
        if info["mode"] == "LONG"
        else float(day["low"].min()) < float(info["boundary"])
    )

    fig, (ax_d1, ax_m15) = plt.subplots(2, 1, figsize=(14, 8), dpi=140, gridspec_kw={"height_ratios": [1, 2]})
    if not d1_win.empty:
        d1_plot = d1_win.copy()
        d1_plot["date"] = pd.to_datetime(d1_plot["d"])
        draw_candles(ax_d1, d1_plot[["date", "open", "high", "low", "close"]], 0.35)
    ax_d1.axhline(float(info["boundary"]), color="#7b1fa2", linestyle="-.", label=f"D1 boundary ({info['mode']})")
    ax_d1.set_title(f"{symbol} D1 | session={session.date()} | prev yin/yang + camp -> {info['mode']}")
    ax_d1.legend(loc="best", fontsize=8)
    ax_d1.grid(True, linestyle=":", alpha=0.3)

    draw_candles(ax_m15, day, 0.0025)
    ax_m15.axhline(float(info["boundary"]), color="#7b1fa2", linestyle="-.", label="strategic boundary")
    ax_m15.set_title(
        f"{symbol} M15 session | bars={len(day)} | pierce={'yes' if pierce else 'no'} | "
        f"mode={info['mode']} boundary={float(info['boundary']):.6g}"
    )
    ax_m15.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax_m15.legend(loc="best", fontsize=8)
    ax_m15.grid(True, linestyle=":", alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return True


def resolve_crypto_paths(data_dir: Path, clean: str) -> dict[str, Path]:
    """Resolve 1d/15m CSV for crypto (data/ + crypto_okx fallbacks)."""
    paths = {tf: find_data_file(data_dir, clean, tf) for tf in ["1d", "1h", "15m"]}
    okx = data_dir / "crypto_okx"
    if okx.is_dir():
        dash = clean.replace("USDT", "-USDT") if clean.endswith("USDT") else clean
        fallbacks = {
            "1d": [okx / f"{dash}_1D_1825d.csv", okx / f"{dash}_1D_180d.csv"],
            "15m": [okx / f"{dash}_15m_180d.csv", okx / f"{dash}_5m_180d.csv"],
            "1h": [okx / f"{dash}_1H_1825d.csv", okx / f"{dash}_1H_180d.csv"],
        }
        for tf, cands in fallbacks.items():
            if paths[tf].exists():
                continue
            for p in cands:
                if p.exists():
                    paths[tf] = p
                    break
    return paths


def analyze_symbol(symbol: str, args: argparse.Namespace) -> dict[str, Any]:
    clean = normalize_symbol(symbol)
    paths = resolve_crypto_paths(Path(args.data_dir), clean)
    if not paths["1d"].exists() or not paths["15m"].exists():
        return {"symbol": clean, "error": "missing_csv"}

    d1_raw = load_ohlcv(paths["1d"], 14, int(args.daily_tail))
    m15_raw = load_ohlcv(paths["15m"], 14, int(args.m15_tail))
    state_dir = str(args.os_state_dir or "").strip()
    d1_state = os_state_path(state_dir, clean, "1d") if state_dir else None
    m15_state = os_state_path(state_dir, clean, "15m") if state_dir else None
    d1_os, _ = build_os_detail_frame_stateful(d1_raw, 3, d1_state, record_hardened_by_bar=True)
    m15_os, _ = build_os_detail_frame_stateful(m15_raw, 3, m15_state, record_hardened_by_bar=False)

    boundary_map = build_prev_day_boundary_map(d1_os)
    m15_sess = assign_session_date(m15_os, d1_raw, futures=False)
    replay = replay_all_sessions(m15_sess, boundary_map, clean)

    # Full backtest (rebuilt OS, crypto calendar session)
    d1_bt, _ = build_os_detail_frame(d1_raw, 3)
    m15_bt, _ = build_os_detail_frame(m15_raw, 3)
    bt = run_ds09_backtest(d1_bt, m15_bt, DS09BacktestConfig(futures_mode=False, gap=3), symbol=clean)
    trades = bt["trades"]

    out: dict[str, Any] = {
        "symbol": clean,
        "d1_camp": int(d1_os["camp"].iloc[-1]),
        "d1_camp_confirmed": int(d1_os["camp_confirmed"].iloc[-1]) if "camp_confirmed" in d1_os.columns else None,
        "m15_rows": len(m15_raw),
        "backtest_trades": int(len(trades)),
        **replay,
    }

    if trades is not None and not trades.empty:
        last = trades.iloc[-1]
        out["last_bt_trade"] = {
            "session": str(pd.to_datetime(last.get("session_date")).date()) if pd.notna(last.get("session_date")) else "",
            "side": "long" if int(last.get("side", 0)) == 1 else "short",
            "entry_time": str(last.get("entry_time", "")),
        }

    session = pd.Timestamp(replay["latest_session"]).normalize()
    png = Path(args.out_dir) / f"{clean}_DS09_session_{session.date()}.png"
    if maybe_plot_session(clean, d1_os, m15_sess, session, boundary_map, png):
        out["session_png"] = str(png)

    # Plot most recent lock session if different and had pierce
    lock_dates = replay.get("lock_sessions") or []
    if lock_dates and lock_dates[-1] != replay["latest_session"]:
        lock_session = pd.Timestamp(lock_dates[-1]).normalize()
        png2 = Path(args.out_dir) / f"{clean}_DS09_session_{lock_session.date()}_lock.png"
        if maybe_plot_session(clean, d1_os, m15_sess, lock_session, boundary_map, png2):
            out["lock_session_png"] = str(png2)

    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--os-state-dir", default="runtime/fengji_os_state")
    parser.add_argument("--symbols", default="IOUSDT,BNBUSDT")
    parser.add_argument("--daily-tail", type=int, default=400)
    parser.add_argument("--m15-tail", type=int, default=960)
    parser.add_argument("--out-dir", default="results/crypto_ds09_sandbox_20260615")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    results = [analyze_symbol(s.strip(), args) for s in args.symbols.split(",") if s.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report) if args.report else out_dir / "crypto_ds09_sandbox_report.json"
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Crypto DS09 沙盒 / 会话诊断", ""]
    for r in results:
        sym = r.get("symbol", "?")
        if r.get("error"):
            lines.append(f"## {sym} — ERROR {r['error']}")
            continue
        lb = r.get("latest_boundary") or {}
        req_camp = "RED(1)" if lb.get("mode") == "LONG" else "BLUE(-1)" if lb.get("mode") == "SHORT" else "?"
        lines.extend(
            [
                f"## {sym}",
                "",
                f"- D1 camp={r.get('d1_camp')} confirmed={r.get('d1_camp_confirmed')}",
                f"- M15 bars={r.get('m15_rows')} · boundary_sessions={r.get('boundary_sessions')}",
                f"- 历史 lock={r.get('locks')} · signal={r.get('signals')} · backtest_trades={r.get('backtest_trades')}",
                f"- 最近 lock 日: {', '.join(r.get('lock_sessions') or []) or '无'}",
                f"- 最近 signal 日: {', '.join(r.get('signal_sessions') or []) or '无'}",
                f"- **当前 session** {r.get('latest_session')} mode={lb.get('mode')} boundary={lb.get('boundary')} "
                f"stage=**{r.get('latest_stage')}** pierce={r.get('latest_pierce')}",
                f"- 当前 M15 camp={r.get('latest_m15_camp')}（SHORT 需 -1 · LONG 需 1）→ 要求 {req_camp}",
                f"- 图: `{r.get('session_png', '无')}`",
                "",
            ]
        )
        if r.get("last_bt_trade"):
            lines.append(f"- 最近回测成交: {r['last_bt_trade']}")
            lines.append("")

    md_path = out_dir / "crypto_ds09_sandbox_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"Saved {report_path}")
    print(f"Saved {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
