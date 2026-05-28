from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

from fengji_core.os_state_store import is_futures_market
from contextlib import contextmanager
from pathlib import Path

import pandas as pd


def now_text() -> str:
    return pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S")


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
    parser.add_argument("--radar-dir", default="runtime/fengji_radar")
    parser.add_argument("--pending-dir", default="runtime/fengji_pending_orders")
    parser.add_argument("--top-n", type=int, default=80)
    parser.add_argument("--daily-tail", type=int, default=520)
    parser.add_argument("--h1-tail", type=int, default=3200)
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
    env["PYTHONPATH"] = f"{root / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"
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
                    ],
                    env,
                )
                if str(args.monitor_state).strip():
                    monitor_state = Path(args.monitor_state)
                elif is_futures_market():
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
