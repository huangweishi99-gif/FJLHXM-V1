from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

from contextlib import contextmanager
from pathlib import Path

import pandas as pd

VALID_MARKETS = {"crypto", "futures"}


def now_text() -> str:
    return pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S")


def split_symbols(text: str) -> list[str]:
    return [item.strip().upper() for item in str(text or "").split(",") if item.strip()]


def resolve_market(args: argparse.Namespace, environ: dict[str, str] | None = None) -> str:
    explicit = str(getattr(args, "market", "") or "").strip().lower()
    if explicit in VALID_MARKETS:
        return explicit

    env = environ if environ is not None else os.environ
    from_env = str(env.get("FENGJI_MARKET", "") or "").strip().lower()
    if from_env in VALID_MARKETS:
        return from_env

    symbols = split_symbols(str(getattr(args, "symbols", "") or ""))
    if symbols:
        return "crypto" if all(symbol.endswith("USDT") for symbol in symbols) else "futures"

    monitor_state = str(getattr(args, "monitor_state", "") or "").lower()
    if "futures" in monitor_state:
        return "futures"

    data_hint = str(getattr(args, "data_dir", "") or "").lower()
    if "futures" in data_hint:
        return "futures"
    if "crypto" in data_hint:
        return "crypto"

    return "crypto"


@contextmanager
def refresh_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                yield False
                return
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                yield False
                return
        yield True
    finally:
        if acquired:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def run_command(cmd: list[str], env: dict[str, str]) -> None:
    print(f"[{now_text()}] RUN {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh FengJi radar and pending-order files in a loop.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--market", choices=["auto", "crypto", "futures"], default="auto")
    parser.add_argument("--radar-dir", default="runtime/fengji_radar")
    parser.add_argument("--pending-dir", default="runtime/fengji_pending_orders")
    parser.add_argument("--top-n", type=int, default=80)
    parser.add_argument("--daily-tail", type=int, default=520)
    parser.add_argument("--h1-tail", type=int, default=3200)
    parser.add_argument("--m15-tail", type=int, default=960)
    parser.add_argument("--max-distance-pct", type=float, default=0.08)
    parser.add_argument("--loop-seconds", type=int, default=300)
    parser.add_argument("--include-triggered", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--monitor-state",
        default="",
        help="挂单监控 state JSON，用于 DS03 去重；国内默认 futures_pending_state.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    py_paths = [str(root / "src")]
    core_pkg = root / "packages" / "fengji_core"
    if core_pkg.is_dir():
        py_paths.append(str(core_pkg))
    extra = env.get("PYTHONPATH", "").strip()
    if extra:
        py_paths.append(extra)
    env["PYTHONPATH"] = os.pathsep.join(py_paths)
    market = resolve_market(args, env)
    env["FENGJI_MARKET"] = market
    python = sys.executable
    radar_json = Path(args.radar_dir) / "radar.json"
    lock_path = Path(args.radar_dir) / ".radar_refresh.lock"

    while True:
        try:
            with refresh_lock(lock_path) as locked:
                if not locked:
                    print(f"[{now_text()}] skip refresh: another radar refresh is running", flush=True)
                    if args.once:
                        break
                    time.sleep(max(30, int(args.loop_seconds)))
                    continue
                run_command(
                    [
                        python,
                        str(root / "src" / "fengji_total_radar.py"),
                        "--data-dir",
                        args.data_dir,
                        "--out-dir",
                        args.radar_dir,
                        "--os-state-dir",
                        "runtime/fengji_os_state",
                        "--market",
                        market,
                        *(
                            [
                                "--symbols",
                                args.symbols,
                            ]
                            if args.symbols
                            else []
                        ),
                        "--top-n",
                        str(args.top_n),
                        "--daily-tail",
                        str(args.daily_tail),
                        "--h1-tail",
                        str(args.h1_tail),
                        "--m15-tail",
                        str(args.m15_tail),
                    ],
                    env,
                )
                if str(args.monitor_state).strip():
                    monitor_state = Path(args.monitor_state)
                elif market == "futures":
                    monitor_state = Path(args.pending_dir) / "futures_pending_state.json"
                else:
                    monitor_state = Path(args.pending_dir) / "state.json"
                pending_cmd = [
                    python,
                    str(root / "src" / "fengji_pending_orders.py"),
                    "--radar",
                    str(radar_json),
                    "--out-dir",
                    args.pending_dir,
                    "--max-distance-pct",
                    str(args.max_distance_pct),
                    "--monitor-state",
                    str(monitor_state),
                ]
                if args.include_triggered:
                    pending_cmd.append("--include-triggered")
                run_command(pending_cmd, env)
                print(f"[{now_text()}] refresh done", flush=True)
        except Exception as exc:
            print(f"[{now_text()}] refresh failed: {exc}", flush=True)

        if args.once:
            break
        time.sleep(max(30, int(args.loop_seconds)))


if __name__ == "__main__":
    main()
