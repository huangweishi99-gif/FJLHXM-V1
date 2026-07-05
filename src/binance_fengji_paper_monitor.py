from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from fengji_feishu_notify import (
    default_feishu_claims_dir,
    paper_trade_notify_key,
    send_feishu_once,
    system_notify_key,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from batch_unified_crypto_whitelist import pct_return_trade
from unified_whitelist_engine import UnifiedConfig, run_unified_symbol


MONITOR_COINS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "TRUMPUSDT",
    "RENDERUSDT",
    "IOUSDT",
    "TAOUSDT",
    "DASHUSDT",
    "LTCUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "APTUSDT",
    "LINKUSDT",
    "BNBUSDT",
    "ZECUSDT",
    "XRPUSDT",
    "HYPEUSDT",
    "ATHUSDT",
    "PEPEUSDT",
    "ARBUSDT",
    "OPUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "INJUSDT",
    "WLDUSDT",
]

DEFAULT_TRADE_COINS = [
    "ZECUSDT",
    "DASHUSDT",
    "TRUMPUSDT",
    "ETHUSDT",
]

TOTAL_PATTERN_STRATEGIES = ["DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08"]


@dataclass(frozen=True)
class MoneyConfig:
    initial_cash: float = 1000.0
    margin_per_trade: float = 100.0
    leverage: float = 2.0
    fee_rate: float = 0.0005
    slippage_rate: float = 0.0003
    maintenance_margin_rate: float = 0.005


def now_text() -> str:
    return pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S")


def normalize_symbol(symbol: str) -> str:
    text = symbol.strip().upper().replace("-", "").replace("_", "")
    if not text.endswith("USDT"):
        text += "USDT"
    return text


def dashed(symbol: str) -> str:
    text = normalize_symbol(symbol)
    return f"{text[:-4]}-USDT"


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def send_msg(webhook: str, text: str) -> None:
    if not webhook:
        print(text)
        return
    headers = {"Content-Type": "application/json"}
    payload = {"msg_type": "text", "content": {"text": text}}
    try:
        requests.post(webhook, headers=headers, data=json.dumps(payload), timeout=8)
    except Exception as exc:
        print(f"飞书发送异常: {exc}")


def read_source_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [column.strip().lower() for column in frame.columns]
    if "date" not in frame.columns:
        if "timestamp" in frame.columns:
            frame = frame.rename(columns={"timestamp": "date"})
        elif frame.columns[0].startswith("unnamed"):
            frame = frame.rename(columns={frame.columns[0]: "date"})
        else:
            frame = frame.rename(columns={frame.columns[0]: "date"})
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} 缺少字段: {missing}")
    frame = frame[required].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    frame = frame.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    return frame


def write_engine_csv(source: Path, target: Path, tail_rows: int) -> tuple[Path, pd.Timestamp, int]:
    frame = read_source_csv(source)
    if tail_rows > 0 and len(frame) > tail_rows:
        frame = frame.tail(tail_rows).copy()
    if frame.empty:
        raise ValueError(f"{source} 没有可用K线")
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, encoding="utf-8")
    return target, pd.to_datetime(frame["date"].iloc[-1]), len(frame)


def symbol_paths(data_dir: Path, symbol: str) -> dict[str, Path]:
    clean = normalize_symbol(symbol)
    return {
        "1d": data_dir / "1d" / f"{clean}.csv",
        "1h": data_dir / "1h" / f"{clean}.csv",
        "15m": data_dir / "15m" / f"{clean}.csv",
    }


def current_bar_key(data_dir: Path, symbol: str) -> str:
    paths = symbol_paths(data_dir, symbol)
    keys: list[str] = []
    for tf in ["1d", "1h"]:
        if not paths[tf].exists():
            return ""
        frame = read_source_csv(paths[tf])
        if frame.empty:
            return ""
        keys.append(f"{tf}:{pd.to_datetime(frame['date'].iloc[-1])}")
    return "|".join(keys)


def build_unified_config(args: argparse.Namespace) -> UnifiedConfig:
    return UnifiedConfig(
        initial_cash=args.initial_cash,
        lots=1,
        commission_rate=0.0,
        slippage_ticks=0.0,
        atr_window=args.atr_window,
        gap=args.gap,
        max_same_direction_entries=args.max_same_direction_entries,
        futures_mode=False,
        spec=None,
    )


def run_fengji_scan(symbol: str, args: argparse.Namespace, run_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    clean = normalize_symbol(symbol)
    paths = symbol_paths(Path(args.data_dir), clean)
    if not paths["1d"].exists() or not paths["1h"].exists():
        raise FileNotFoundError(f"{clean} 缺少 1d 或 1h 数据: {paths}")

    cache_root = Path(args.runtime_dir) / "cache" / clean
    out_dir = Path(args.runtime_dir) / "runs" / run_id / clean
    daily_csv, d1_time, d1_rows = write_engine_csv(paths["1d"], cache_root / f"{clean}_1D_runtime.csv", args.daily_tail)
    h1_csv, h1_time, h1_rows = write_engine_csv(paths["1h"], cache_root / f"{clean}_1H_runtime.csv", args.h1_tail)

    summary = run_unified_symbol(
        symbol=clean.replace("USDT", ""),
        config=build_unified_config(args),
        daily_csv=daily_csv,
        h1_csv=h1_csv,
        m15_csv=None,
        strategies=TOTAL_PATTERN_STRATEGIES,
        out_dir=out_dir,
    )
    accepted_path = out_dir / "accepted_trades.csv"
    accepted = pd.read_csv(accepted_path) if accepted_path.exists() else pd.DataFrame()
    meta = {
        "out_dir": str(out_dir),
        "d1_time": str(d1_time),
        "h1_time": str(h1_time),
        "d1_rows": d1_rows,
        "h1_rows": h1_rows,
        **summary,
    }
    return accepted, meta


def calc_pnl(row: pd.Series, money: MoneyConfig) -> dict[str, Any]:
    return pct_return_trade(
        row,
        money.margin_per_trade,
        money.leverage,
        money.fee_rate,
        money.slippage_rate,
        money.maintenance_margin_rate,
    )


def trade_key(row: pd.Series) -> str:
    return f"{row.get('symbol', '')}|{row.get('strategy_id', '')}|{row.get('entry_time', '')}|{row.get('entry_price', '')}|{row.get('side', '')}"


def format_entry(symbol: str, row: pd.Series, money: MoneyConfig, meta: dict[str, Any]) -> str:
    side = "买入做多" if int(row["side"]) == 1 else "卖出做空"
    return (
        f"🚨【峰极总定式 模拟开仓】\n"
        f"时间: {now_text()}\n"
        f"币种: {symbol}\n"
        f"定式: {row.get('strategy_id', '')}\n"
        f"方向: {side}\n"
        f"入场时间: {row.get('entry_time', '')}\n"
        f"入场价格: {float(row.get('entry_price', 0.0)):.8g}\n"
        f"初始止损: {float(row.get('initial_stop', 0.0)):.8g}\n"
        f"保证金: {money.margin_per_trade:.2f} USDT\n"
        f"杠杆: {money.leverage:.1f}x\n"
        f"名义仓位: {money.margin_per_trade * money.leverage:.2f} USDT\n"
        f"总定式: DS01-DS08\n"
        f"数据: D1={meta.get('d1_time')} H1={meta.get('h1_time')}"
    )


def format_exit(symbol: str, row: pd.Series, money: MoneyConfig, pnl: dict[str, Any]) -> str:
    net = float(pnl["crypto_net_pnl"])
    result = "盈利" if net >= 0 else "亏损"
    return (
        f"✅【峰极总定式 模拟平仓】\n"
        f"时间: {now_text()}\n"
        f"币种: {symbol}\n"
        f"定式: {row.get('strategy_id', '')}\n"
        f"方向: {'多头' if int(row['side']) == 1 else '空头'}\n"
        f"入场时间: {row.get('entry_time', '')}\n"
        f"平仓时间: {row.get('exit_time', '')}\n"
        f"入场价格: {float(row.get('entry_price', 0.0)):.8g}\n"
        f"平仓价格: {float(row.get('exit_price', 0.0)):.8g}\n"
        f"结果: {result} {net:.2f} USDT\n"
        f"退出原因: {row.get('exit_reason', '')}\n"
        f"手续费滑点: 已按严格版估算"
    )


def process_symbol(symbol: str, args: argparse.Namespace, state: dict, run_id: str) -> None:
    clean = normalize_symbol(symbol)
    dashed_symbol = dashed(clean)
    data_dir = Path(args.data_dir)
    bar_key = current_bar_key(data_dir, clean)
    if not bar_key:
        print(f"[{clean}] 等待数据文件生成")
        return

    symbol_state = state.setdefault(
        clean,
        {
            "last_bar_key": "",
            "initialized": False,
            "open_position": None,
            "seen_entries": [],
            "closed_entries": [],
            "last_scan": "",
        },
    )
    if symbol_state.get("last_bar_key") == bar_key and not args.force:
        return

    accepted, meta = run_fengji_scan(clean, args, run_id)
    symbol_state["last_bar_key"] = bar_key
    symbol_state["last_scan"] = now_text()
    if accepted.empty:
        print(f"[{clean}] 无接受交易 candidates={meta.get('candidates')} accepted=0")
        symbol_state["initialized"] = True
        return

    accepted["entry_time"] = pd.to_datetime(accepted["entry_time"], errors="coerce")
    accepted["exit_time"] = pd.to_datetime(accepted["exit_time"], errors="coerce")
    accepted = accepted.dropna(subset=["entry_time"]).sort_values(["entry_time", "strategy_priority"])
    ref_time = pd.to_datetime(meta["h1_time"], errors="coerce")
    lookback_start = ref_time - pd.Timedelta(hours=args.signal_lookback_hours)
    money = MoneyConfig(
        initial_cash=args.initial_cash,
        margin_per_trade=args.margin_per_trade,
        leverage=args.leverage,
        fee_rate=args.fee_rate,
        slippage_rate=args.slippage_rate,
        maintenance_margin_rate=args.maintenance_margin_rate,
    )

    if not symbol_state.get("initialized"):
        symbol_state["initialized"] = True
        symbol_state["seen_entries"] = [trade_key(row) for _, row in accepted.tail(args.bootstrap_seen_trades).iterrows()]
        print(f"[{clean}] 首次启动只建立基线，不补发历史信号 accepted={len(accepted)}")
        return

    open_position = symbol_state.get("open_position")
    if open_position:
        key = open_position["trade_key"]
        matched = accepted[accepted.apply(lambda row: trade_key(row) == key, axis=1)]
        if not matched.empty:
            row = matched.iloc[-1]
            exit_time = pd.to_datetime(row.get("exit_time"), errors="coerce")
            if not pd.isna(exit_time) and exit_time <= ref_time and key not in symbol_state.get("closed_entries", []):
                pnl = calc_pnl(row, money)
                symbol_state["closed_entries"].append(key)
                symbol_state["open_position"] = None
                send_feishu_once(
                    default_feishu_claims_dir(ROOT),
                    paper_trade_notify_key("close", key),
                    args.feishu_webhook,
                    format_exit(clean, row, money, pnl),
                    send_msg,
                )
                print(f"[{clean}] 模拟平仓 {row.get('strategy_id')} pnl={float(pnl['crypto_net_pnl']):.2f}")
        return

    if clean not in args.trade_coins:
        print(f"[{clean}] 仅监控，不在模拟交易名单")
        return

    recent = accepted[(accepted["entry_time"] >= lookback_start) & (accepted["entry_time"] <= ref_time)].copy()
    if recent.empty:
        print(f"[{clean}] 无最新开仓信号 accepted={len(accepted)}")
        return

    seen = set(symbol_state.get("seen_entries", []))
    for _, row in recent.sort_values(["entry_time", "strategy_priority"]).iterrows():
        key = trade_key(row)
        if key in seen:
            continue
        send_feishu_once(
            default_feishu_claims_dir(ROOT),
            paper_trade_notify_key("open", key),
            args.feishu_webhook,
            format_entry(clean, row, money, meta),
            send_msg,
        )
        symbol_state["seen_entries"].append(key)
        symbol_state["open_position"] = {
            "trade_key": key,
            "symbol": clean,
            "strategy_id": row.get("strategy_id", ""),
            "side": int(row["side"]),
            "entry_time": str(row.get("entry_time")),
            "entry_price": float(row.get("entry_price")),
            "margin": money.margin_per_trade,
            "leverage": money.leverage,
        }
        print(f"[{clean}] 模拟开仓 {row.get('strategy_id')} {row.get('direction')} {row.get('entry_price')}")
        break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Binance local-data FengJi DS01-DS08 paper monitor.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--runtime-dir", default="runtime/fengji_paper")
    parser.add_argument("--state-file", default="runtime/fengji_paper/state.json")
    parser.add_argument("--coins", default=",".join(MONITOR_COINS))
    parser.add_argument("--trade-coins", default=",".join(DEFAULT_TRADE_COINS))
    parser.add_argument("--feishu-webhook", default=os.getenv("FEISHU_WEBHOOK", ""))
    parser.add_argument("--loop-seconds", type=int, default=60)
    parser.add_argument("--signal-lookback-hours", type=int, default=3)
    parser.add_argument("--bootstrap-seen-trades", type=int, default=300)
    parser.add_argument("--daily-tail", type=int, default=420)
    parser.add_argument("--h1-tail", type=int, default=2600)
    parser.add_argument("--initial-cash", type=float, default=1000.0)
    parser.add_argument("--margin-per-trade", type=float, default=100.0)
    parser.add_argument("--leverage", type=float, default=2.0)
    parser.add_argument("--fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-rate", type=float, default=0.0003)
    parser.add_argument("--maintenance-margin-rate", type=float, default=0.005)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--max-same-direction-entries", type=int, default=3)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.coins = [normalize_symbol(item) for item in args.coins.split(",") if item.strip()]
    args.trade_coins = {normalize_symbol(item) for item in args.trade_coins.split(",") if item.strip()}
    state_path = Path(args.state_file)
    state = load_json(state_path, {"version": 1, "started_at": now_text(), "symbols": {}})
    state.setdefault("symbols", {})

    startup = (
        f"🚀【峰极总定式模拟盘已启动】\n"
        f"时间: {now_text()}\n"
        f"模式: 只模拟，不真实下单\n"
        f"总定式: DS01-DS08\n"
        f"监控币种: {', '.join(args.coins)}\n"
        f"模拟交易名单: {', '.join(sorted(args.trade_coins)) or '空'}\n"
        f"数据源: 本地 {Path(args.data_dir).resolve()}\n"
        f"说明: 首次启动只建立基线，不补发历史信号"
    )
    if args.feishu_webhook:
        send_feishu_once(
            default_feishu_claims_dir(ROOT),
            system_notify_key("binance_paper", "startup"),
            args.feishu_webhook,
            startup,
            send_msg,
        )
    print(startup)

    while True:
        run_id = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%d_%H%M%S")
        try:
            for coin in args.coins:
                try:
                    process_symbol(coin, args, state["symbols"], run_id)
                    save_json(state_path, state)
                except Exception as exc:
                    msg = f"⚠️【峰极模拟盘单币异常】\n时间: {now_text()}\n币种: {coin}\n错误: {exc}"
                    print(msg)
                    if args.feishu_webhook:
                        send_feishu_once(
                            default_feishu_claims_dir(ROOT),
                            system_notify_key("binance_paper", f"symbol_error|{coin}"),
                            args.feishu_webhook,
                            msg,
                            send_msg,
                        )
            if args.once:
                break
            time.sleep(args.loop_seconds)
        except KeyboardInterrupt:
            send_msg(args.feishu_webhook, f"🛑【峰极总定式模拟盘已停止】\n时间: {now_text()}")
            break
        except Exception as exc:
            msg = f"⚠️【峰极模拟盘主循环异常】\n时间: {now_text()}\n60秒后自动恢复\n错误: {exc}"
            print(msg)
            if args.feishu_webhook:
                send_feishu_once(
                    default_feishu_claims_dir(ROOT),
                    system_notify_key("binance_paper", "main_loop_error"),
                    args.feishu_webhook,
                    msg,
                    send_msg,
                )
            time.sleep(60)


if __name__ == "__main__":
    main()
