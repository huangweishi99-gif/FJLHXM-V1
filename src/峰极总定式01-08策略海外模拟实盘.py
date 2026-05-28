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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

REQUIRED_ENGINE_FILES = [
    "batch_unified_crypto_whitelist.py",
    "unified_whitelist_engine.py",
    "backtest_ds01.py",
    "backtest_ds02.py",
    "backtest_ds03.py",
    "backtest_ds04.py",
    "backtest_ds05.py",
    "backtest_ds06.py",
    "backtest_ds07.py",
    "backtest_ds08.py",
    "quant/os_engine.py",
    "quant/data.py",
]


def assert_engine_ready() -> None:
    missing = [name for name in REQUIRED_ENGINE_FILES if not (ROOT / "src" / name).exists()]
    if missing:
        details = "\n".join(f"  - src/{name}" for name in missing)
        raise SystemExit(
            "峰极总定式策略引擎不完整，模拟实盘无法启动。\n"
            "请把本机项目里的完整 src 文件夹同步到服务器，而不是只上传这个主脚本。\n"
            f"当前项目目录: {ROOT}\n"
            f"缺少文件:\n{details}"
        )


assert_engine_ready()

try:
    from batch_unified_crypto_whitelist import pct_return_trade
    from unified_whitelist_engine import UnifiedConfig, run_unified_symbol
except ModuleNotFoundError as exc:
    raise SystemExit(
        "峰极总定式策略引擎导入失败。\n"
        "常见原因：服务器只上传了主脚本，没有上传完整 src；或没有安装 pandas/requests/numpy/matplotlib。\n"
        f"当前项目目录: {ROOT}\n"
        f"原始错误: {exc}"
    ) from exc


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
]

DEFAULT_TRADE_COINS = list(MONITOR_COINS)

TOTAL_PATTERN_STRATEGIES = ["DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08"]
DAILY_PATTERN_STRATEGIES = {"DS01", "DS02", "DS03", "DS04", "DS05", "DS06"}
PENDING_MANAGED_STRATEGIES = {"DS01", "DS03", "DS05", "DS07", "DS08"}
DIRECT_OPEN_STRATEGIES = set(TOTAL_PATTERN_STRATEGIES) - PENDING_MANAGED_STRATEGIES
DEFAULT_FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")


@dataclass(frozen=True)
class MoneyConfig:
    initial_cash: float = 1000.0
    margin_per_trade: float = 200.0
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


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")


def append_csv(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([item])
    frame.to_csv(path, mode="a", header=not path.exists(), index=False, encoding="utf-8-sig")


def apply_config_file(args: argparse.Namespace) -> argparse.Namespace:
    config_path = Path(args.config)
    if not config_path.exists():
        return args
    config = load_json(config_path, {})
    if not isinstance(config, dict):
        raise SystemExit(f"配置文件格式错误，必须是 JSON 对象: {config_path}")

    parser_defaults = parse_args.defaults
    for key, value in config.items():
        attr = key.replace("-", "_")
        if not hasattr(args, attr):
            continue
        current = getattr(args, attr)
        default = parser_defaults.get(attr)
        if current == default or current in {"", None}:
            if isinstance(value, list):
                value = ",".join(str(item) for item in value)
            setattr(args, attr, value)
    return args


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


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 5:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def read_source_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")
    if path.stat().st_size <= 5:
        raise ValueError(f"数据文件为空或正在写入中，请稍后重试: {path}")
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"数据文件无法解析（可能同步中断）: {path}") from exc
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


def find_data_file(data_dir: Path, symbol: str, timeframe: str) -> Path:
    clean = normalize_symbol(symbol)
    timeframe_aliases = {
        "1d": ["1d", "d1", "day", "daily"],
        "1h": ["1h", "h1", "60m", "60min"],
        "15m": ["15m", "m15", "15min"],
    }
    preferred_folder = {
        "1d": "1d",
        "1h": "1h",
        "15m": "15m",
    }[timeframe]
    preferred = data_dir / preferred_folder / f"{clean}.csv"
    if preferred.exists() and preferred.stat().st_size > 5:
        return preferred

    candidates: list[Path] = []
    for folder in [preferred_folder, *timeframe_aliases[timeframe]]:
        candidates.extend(
            [
                data_dir / folder / f"{clean}.csv",
                data_dir / folder / f"{clean}_{timeframe}.csv",
                data_dir / folder / f"{clean}-{timeframe}.csv",
            ]
        )
    for alias in timeframe_aliases[timeframe]:
        candidates.extend(
            [
                data_dir / f"{clean}_{alias}.csv",
                data_dir / f"{clean}-{alias}.csv",
                data_dir / f"{clean}{alias}.csv",
            ]
        )

    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 5:
            return candidate

    # Last-resort shallow search. Avoid recursive scanning every loop; server data should stay in data/1d, data/1h, data/15m.
    for candidate in data_dir.glob("*.csv"):
        if candidate.stat().st_size <= 5:
            continue
        name = candidate.name.lower().replace("-", "").replace("_", "")
        if clean.lower() in name and any(alias.lower().replace("-", "").replace("_", "") in name for alias in timeframe_aliases[timeframe]):
            return candidate

    return preferred


def symbol_paths(data_dir: Path, symbol: str) -> dict[str, Path]:
    clean = normalize_symbol(symbol)
    return {
        "1d": find_data_file(data_dir, clean, "1d"),
        "1h": find_data_file(data_dir, clean, "1h"),
        "15m": find_data_file(data_dir, clean, "15m"),
    }


def current_bar_key(data_dir: Path, symbol: str) -> str:
    paths = symbol_paths(data_dir, symbol)
    keys: list[str] = []
    for tf in ["1d", "1h"]:
        if not paths[tf].exists() or paths[tf].stat().st_size <= 5:
            return ""
        try:
            frame = read_source_csv(paths[tf])
        except (ValueError, pd.errors.EmptyDataError):
            return ""
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
    m15_csv = None
    m15_rows = 0
    m15_time = ""
    if paths["15m"].exists():
        m15_csv, m15_time, m15_rows = write_engine_csv(
            paths["15m"],
            cache_root / f"{clean}_15M_runtime.csv",
            getattr(args, "m15_tail", 0) or 0,
        )

    summary = run_unified_symbol(
        symbol=clean.replace("USDT", ""),
        config=build_unified_config(args),
        daily_csv=daily_csv,
        h1_csv=h1_csv,
        m15_csv=m15_csv,
        strategies=TOTAL_PATTERN_STRATEGIES,
        out_dir=out_dir,
    )
    accepted_path = out_dir / "accepted_trades.csv"
    accepted = safe_read_csv(accepted_path)
    meta = {
        "out_dir": str(out_dir),
        "d1_time": str(d1_time),
        "h1_time": str(h1_time),
        "d1_rows": d1_rows,
        "h1_rows": h1_rows,
        "m15_rows": m15_rows,
        "m15_time": str(m15_time),
        **summary,
    }
    return accepted, meta


def calc_pnl(row: pd.Series, money: MoneyConfig) -> dict[str, Any]:
    return pct_return_trade(
        row,
        trade_margin(row, money),
        money.leverage,
        money.fee_rate,
        money.slippage_rate,
        money.maintenance_margin_rate,
    )


def trade_units(row: pd.Series | dict[str, Any]) -> int:
    value = row.get("lots", 1)
    try:
        return max(1, int(float(value)))
    except Exception:
        return 1


def trade_margin(row: pd.Series | dict[str, Any], money: MoneyConfig) -> float:
    return money.margin_per_trade * trade_units(row)


def trade_key(row: pd.Series) -> str:
    return f"{row.get('symbol', '')}|{row.get('strategy_id', '')}|{row.get('entry_time', '')}|{row.get('entry_price', '')}|{row.get('side', '')}"


def format_entry(symbol: str, row: pd.Series, money: MoneyConfig, meta: dict[str, Any]) -> str:
    side = "买入做多" if int(row["side"]) == 1 else "卖出做空"
    margin = trade_margin(row, money)
    return (
        f"🚨【峰极总定式 模拟开仓】\n"
        f"时间: {now_text()}\n"
        f"币种: {symbol}\n"
        f"定式: {row.get('strategy_id', '')}\n"
        f"方向: {side}\n"
        f"入场时间: {row.get('entry_time', '')}\n"
        f"入场价格: {float(row.get('entry_price', 0.0)):.8g}\n"
        f"初始止损: {float(row.get('initial_stop', 0.0)):.8g}\n"
        f"保证金: {margin:.2f} USDT\n"
        f"杠杆: {money.leverage:.1f}x\n"
        f"名义仓位: {margin * money.leverage:.2f} USDT\n"
        f"虚拟本金: 每个品种独立 {money.initial_cash:.2f} USDT\n"
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


def ensure_symbol_account(symbol_state: dict[str, Any], args: argparse.Namespace) -> None:
    initial_cash = float(args.initial_cash)
    realized_pnl = float(symbol_state.get("realized_pnl", 0.0))
    symbol_state["initial_cash"] = initial_cash
    symbol_state["realized_pnl"] = realized_pnl
    symbol_state["equity"] = initial_cash + realized_pnl
    symbol_state.setdefault("closed_trades", [])
    symbol_state.setdefault("events", [])


def short_events(items: list[dict[str, Any]], limit: int = 500) -> list[dict[str, Any]]:
    return items[-limit:] if len(items) > limit else items


def record_event(args: argparse.Namespace, state: dict[str, Any], event: dict[str, Any]) -> None:
    event = {"time": now_text(), **event}
    state.setdefault("events", [])
    state["events"].append(event)
    state["events"] = short_events(state["events"], 800)
    append_jsonl(Path(args.runtime_dir) / "events.jsonl", event)


def record_closed_trade(args: argparse.Namespace, state: dict[str, Any], symbol_state: dict[str, Any], row: pd.Series, pnl: dict[str, Any]) -> dict[str, Any]:
    net = float(pnl["crypto_net_pnl"])
    symbol_state["realized_pnl"] = float(symbol_state.get("realized_pnl", 0.0)) + net
    symbol_state["equity"] = float(symbol_state.get("initial_cash", args.initial_cash)) + float(symbol_state["realized_pnl"])
    record = {
        "closed_at": now_text(),
        "symbol": normalize_symbol(str(row.get("symbol", "")) or ""),
        "strategy_id": row.get("strategy_id", ""),
        "direction": "long" if int(row["side"]) == 1 else "short",
        "side": int(row["side"]),
        "entry_time": str(row.get("entry_time", "")),
        "exit_time": str(row.get("exit_time", "")),
        "entry_price": float(row.get("entry_price", 0.0)),
        "exit_price": float(row.get("exit_price", 0.0)),
        "initial_stop": float(row.get("initial_stop", 0.0)) if not pd.isna(row.get("initial_stop", 0.0)) else 0.0,
        "exit_reason": row.get("exit_reason", ""),
        "units": trade_units(row),
        "margin": trade_margin(row, MoneyConfig(
            initial_cash=args.initial_cash,
            margin_per_trade=args.margin_per_trade,
            leverage=args.leverage,
            fee_rate=args.fee_rate,
            slippage_rate=args.slippage_rate,
            maintenance_margin_rate=args.maintenance_margin_rate,
        )),
        "leverage": float(args.leverage),
        "notional": trade_margin(row, MoneyConfig(margin_per_trade=args.margin_per_trade, leverage=args.leverage)) * float(args.leverage),
        "net_pnl": net,
        "return_on_symbol_cash": net / float(symbol_state.get("initial_cash", args.initial_cash)),
        "equity_after": float(symbol_state["equity"]),
        "liquidated": bool(pnl.get("liquidated", False)),
        "liquidation_price": float(pnl.get("liquidation_price", 0.0)),
    }
    symbol_state.setdefault("closed_trades", []).append(record)
    symbol_state["closed_trades"] = short_events(symbol_state["closed_trades"], 200)
    state.setdefault("closed_trades", []).append(record)
    state["closed_trades"] = short_events(state["closed_trades"], 1000)
    append_csv(Path(args.runtime_dir) / "trades.csv", record)
    return record


def write_dashboard_snapshot(args: argparse.Namespace, state: dict[str, Any]) -> None:
    symbols: list[dict[str, Any]] = []
    total_initial = 0.0
    total_realized = 0.0
    open_count = 0
    closed_trades = state.get("closed_trades", [])
    strategy_pnl: dict[str, float] = {}
    symbol_pnl: dict[str, float] = {}

    for trade in closed_trades:
        strategy = str(trade.get("strategy_id", "") or "UNKNOWN")
        symbol = str(trade.get("symbol", "") or "UNKNOWN")
        net = float(trade.get("net_pnl", 0.0) or 0.0)
        strategy_pnl[strategy] = strategy_pnl.get(strategy, 0.0) + net
        symbol_pnl[symbol] = symbol_pnl.get(symbol, 0.0) + net

    for symbol in args.coins:
        clean = normalize_symbol(symbol)
        symbol_state = state.setdefault("symbols", {}).get(clean, {})
        initial = float(symbol_state.get("initial_cash", args.initial_cash))
        realized = float(symbol_state.get("realized_pnl", 0.0))
        open_position = symbol_state.get("open_position")
        total_initial += initial
        total_realized += realized
        if open_position:
            open_count += 1
        symbols.append(
            {
                "symbol": clean,
                "market": "CRYPTO",
                "initial_cash": initial,
                "realized_pnl": realized,
                "unrealized_pnl": 0.0,
                "equity": initial + realized,
                "return_pct": realized / initial if initial else 0.0,
                "open_position": open_position,
                "closed_trade_count": len(symbol_state.get("closed_trades", [])),
                "last_scan": symbol_state.get("last_scan", ""),
                "last_bar_key": symbol_state.get("last_bar_key", ""),
                "initialized": bool(symbol_state.get("initialized", False)),
                "accepted_count": symbol_state.get("last_accepted_count", 0),
            }
        )

    payload = {
        "version": 1,
        "generated_at": now_text(),
        "mode": "paper",
        "engine": "峰极总定式 DS01-DS08",
        "runtime_dir": str(Path(args.runtime_dir).resolve()),
        "data_dir": str(Path(args.data_dir).resolve()),
        "money": {
            "per_symbol_initial_cash": float(args.initial_cash),
            "margin_per_entry": float(args.margin_per_trade),
            "leverage": float(args.leverage),
            "fee_rate": float(args.fee_rate),
            "slippage_rate": float(args.slippage_rate),
            "max_ds01_entries": int(args.max_same_direction_entries),
            "note": "每个虚拟货币独立使用一份模拟本金，便于公平比较。",
        },
        "summary": {
            "symbols": len(symbols),
            "open_positions": open_count,
            "closed_trades": len(closed_trades),
            "total_initial_cash": total_initial,
            "total_realized_pnl": total_realized,
            "total_equity": total_initial + total_realized,
            "total_return_pct": total_realized / total_initial if total_initial else 0.0,
        },
        "markets": {
            "crypto": {"enabled": True, "symbols": len(symbols)},
            "us_stock": {"enabled": False, "symbols": 0},
        },
        "symbols": symbols,
        "closed_trades": closed_trades[-300:],
        "events": state.get("events", [])[-500:],
        "strategy_pnl": [{"strategy_id": key, "net_pnl": value} for key, value in sorted(strategy_pnl.items())],
        "symbol_pnl": [{"symbol": key, "net_pnl": value} for key, value in sorted(symbol_pnl.items())],
    }
    save_json(Path(args.runtime_dir) / "dashboard.json", payload)


def process_symbol(symbol: str, args: argparse.Namespace, root_state: dict, run_id: str) -> None:
    clean = normalize_symbol(symbol)
    dashed_symbol = dashed(clean)
    data_dir = Path(args.data_dir)
    bar_key = current_bar_key(data_dir, clean)
    if not bar_key:
        print(f"[{clean}] 等待数据文件生成")
        return

    symbols_state = root_state.setdefault("symbols", {})
    symbol_state = symbols_state.setdefault(
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
    ensure_symbol_account(symbol_state, args)
    if symbol_state.get("last_bar_key") == bar_key and not args.force:
        return

    accepted, meta = run_fengji_scan(clean, args, run_id)
    symbol_state["last_bar_key"] = bar_key
    symbol_state["last_scan"] = now_text()
    symbol_state["last_accepted_count"] = int(len(accepted))
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
                send_msg(args.feishu_webhook, format_exit(clean, row, money, pnl))
                closed = record_closed_trade(args, root_state, symbol_state, row, pnl)
                record_event(
                    args,
                    root_state,
                    {
                        "event_type": "close",
                        "market": "CRYPTO",
                        "symbol": clean,
                        "strategy_id": row.get("strategy_id", ""),
                        "net_pnl": closed["net_pnl"],
                        "equity_after": closed["equity_after"],
                    },
                )
                symbol_state["closed_entries"].append(key)
                symbol_state["open_position"] = None
                print(f"[{clean}] 模拟平仓 {row.get('strategy_id')} pnl={float(pnl['crypto_net_pnl']):.2f}")
        return

    if clean not in args.trade_coins:
        print(f"[{clean}] 仅监控，不在模拟交易名单")
        return

    d1_time = pd.to_datetime(meta.get("d1_time"), errors="coerce")
    same_daily_bar = (
        accepted["strategy_id"].isin(DAILY_PATTERN_STRATEGIES)
        & (accepted["entry_time"].dt.normalize() == d1_time.normalize())
    )
    recent = accepted[
        (((accepted["entry_time"] >= lookback_start) & (accepted["entry_time"] <= ref_time)) | same_daily_bar)
    ].copy()
    if recent.empty:
        print(f"[{clean}] 无最新开仓信号 accepted={len(accepted)}")
        return

    seen = set(symbol_state.get("seen_entries", []))
    for _, row in recent.sort_values(["entry_time", "strategy_priority"]).iterrows():
        key = trade_key(row)
        if key in seen:
            continue
        strategy_id = str(row.get("strategy_id", "")).upper()
        if strategy_id not in DIRECT_OPEN_STRATEGIES:
            symbol_state["seen_entries"].append(key)
            print(f"[{clean}] 跳过主程序直接开仓 {strategy_id}，交给挂单监控触发")
            continue

        exit_time = pd.to_datetime(row.get("exit_time"), errors="coerce")
        if not pd.isna(exit_time) and exit_time <= ref_time:
            symbol_state["seen_entries"].append(key)
            print(
                f"[{clean}] 跳过已失效信号 {row.get('strategy_id')} "
                f"entry={row.get('entry_time')} exit={row.get('exit_time')} ref={ref_time}"
            )
            continue

        entry_time = pd.to_datetime(row.get("entry_time"), errors="coerce")
        max_lag = pd.Timedelta(hours=args.max_entry_lag_hours)
        is_current_daily = (
            strategy_id in DAILY_PATTERN_STRATEGIES
            and not pd.isna(entry_time)
            and not pd.isna(d1_time)
            and entry_time.normalize() == d1_time.normalize()
        )
        if pd.isna(entry_time) or (entry_time < ref_time - max_lag and not is_current_daily):
            symbol_state["seen_entries"].append(key)
            print(
                f"[{clean}] 跳过过期信号 {row.get('strategy_id')} "
                f"entry={row.get('entry_time')} ref={ref_time} max_lag_hours={args.max_entry_lag_hours}"
            )
            continue

        send_msg(args.feishu_webhook, format_entry(clean, row, money, meta))
        symbol_state["seen_entries"].append(key)
        margin = trade_margin(row, money)
        symbol_state["open_position"] = {
            "trade_key": key,
            "symbol": clean,
            "strategy_id": row.get("strategy_id", ""),
            "side": int(row["side"]),
            "direction": row.get("direction", ""),
            "entry_time": str(row.get("entry_time")),
            "entry_price": float(row.get("entry_price")),
            "initial_stop": float(row.get("initial_stop", 0.0)) if not pd.isna(row.get("initial_stop", 0.0)) else 0.0,
            "units": trade_units(row),
            "margin": margin,
            "leverage": money.leverage,
            "notional": margin * money.leverage,
            "virtual_initial_cash": money.initial_cash,
        }
        record_event(
            args,
            root_state,
            {
                "event_type": "open",
                "market": "CRYPTO",
                "symbol": clean,
                "strategy_id": row.get("strategy_id", ""),
                "direction": row.get("direction", ""),
                "margin": margin,
                "virtual_initial_cash": money.initial_cash,
            },
        )
        print(f"[{clean}] 模拟开仓 {row.get('strategy_id')} {row.get('direction')} {row.get('entry_price')}")
        break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Binance local-data FengJi DS01-DS08 paper monitor.")
    parser.add_argument("--config", default="runtime/fengji_paper/config.json", help="JSON config file. CLI values override config values.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--runtime-dir", default="runtime/fengji_paper")
    parser.add_argument("--state-file", default="runtime/fengji_paper/state.json")
    parser.add_argument("--coins", default=",".join(MONITOR_COINS))
    parser.add_argument("--trade-coins", default=",".join(DEFAULT_TRADE_COINS))
    parser.add_argument("--feishu-webhook", default=DEFAULT_FEISHU_WEBHOOK)
    parser.add_argument("--loop-seconds", type=int, default=60)
    parser.add_argument("--signal-lookback-hours", type=int, default=3)
    parser.add_argument("--max-entry-lag-hours", type=float, default=1.25)
    parser.add_argument("--bootstrap-seen-trades", type=int, default=300)
    parser.add_argument("--daily-tail", type=int, default=420)
    parser.add_argument("--h1-tail", type=int, default=2600)
    parser.add_argument("--initial-cash", type=float, default=1000.0)
    parser.add_argument("--margin-per-trade", type=float, default=200.0)
    parser.add_argument("--leverage", type=float, default=2.0)
    parser.add_argument("--fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-rate", type=float, default=0.0003)
    parser.add_argument("--maintenance-margin-rate", type=float, default=0.005)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--max-same-direction-entries", type=int, default=3)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force", action="store_true")
    parse_args.defaults = {action.dest: action.default for action in parser._actions}
    args = parser.parse_args()
    return apply_config_file(args)


def main() -> None:
    args = parse_args()
    args.coins = [normalize_symbol(item) for item in args.coins.split(",") if item.strip()]
    args.trade_coins = {normalize_symbol(item) for item in args.trade_coins.split(",") if item.strip()}
    state_path = Path(args.state_file)
    state = load_json(state_path, {"version": 1, "started_at": now_text(), "symbols": {}})
    state.setdefault("symbols", {})
    state.setdefault("events", [])
    state.setdefault("closed_trades", [])
    state["money_mode"] = {
        "crypto_accounting": "per_symbol_independent",
        "per_symbol_initial_cash": float(args.initial_cash),
        "margin_per_entry": float(args.margin_per_trade),
        "leverage": float(args.leverage),
        "ds01_max_entries": int(args.max_same_direction_entries),
        "other_patterns_entries": 1,
    }

    startup = (
        f"🚀【峰极总定式模拟盘已启动】\n"
        f"时间: {now_text()}\n"
        f"模式: 只模拟，不真实下单\n"
        f"总定式: DS01-DS08\n"
        f"资金口径: 每个虚拟货币独立 {args.initial_cash:.2f} USDT 模拟本金\n"
        f"单次保证金: {args.margin_per_trade:.2f} USDT，杠杆 {args.leverage:.1f}x\n"
        f"监控币种: {', '.join(args.coins)}\n"
        f"模拟交易名单: {', '.join(sorted(args.trade_coins)) or '空'}\n"
        f"数据源: 本地 {Path(args.data_dir).resolve()}\n"
        f"开仓入口: DS01/DS03/DS05/DS07/DS08 由挂单监控触发；DS02/DS04/DS06 由主程序确认触发\n"
        f"说明: 首次启动只建立基线，不补发历史信号"
    )
    send_msg(args.feishu_webhook, startup)
    print(startup)

    while True:
        run_id = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%d_%H%M%S")
        try:
            for coin in args.coins:
                try:
                    process_symbol(coin, args, state, run_id)
                    save_json(state_path, state)
                except Exception as exc:
                    msg = f"⚠️【峰极模拟盘单币异常】\n时间: {now_text()}\n币种: {coin}\n错误: {exc}"
                    print(msg)
                    send_msg(args.feishu_webhook, msg)
            write_dashboard_snapshot(args, state)
            save_json(state_path, state)
            if args.once:
                break
            time.sleep(args.loop_seconds)
        except KeyboardInterrupt:
            send_msg(args.feishu_webhook, f"🛑【峰极总定式模拟盘已停止】\n时间: {now_text()}")
            break
        except Exception as exc:
            msg = f"⚠️【峰极模拟盘主循环异常】\n时间: {now_text()}\n60秒后自动恢复\n错误: {exc}"
            print(msg)
            send_msg(args.feishu_webhook, msg)
            time.sleep(60)


if __name__ == "__main__":
    main()
