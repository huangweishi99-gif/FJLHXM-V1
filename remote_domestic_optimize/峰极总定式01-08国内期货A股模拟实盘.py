from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import pandas as pd
import requests

# 智能寻路：关联大本营旁边的 src 工具箱
ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

try:
    from batch_unified_crypto_whitelist import pct_return_trade
    from unified_whitelist_engine import UnifiedConfig, run_unified_symbol
except ModuleNotFoundError as exc:
    raise SystemExit(f"⚠️ 策略引擎零件不完整。请确保你的 src 文件夹已经完整放入 quant_futures 目录下！原始错误: {exc}")

# 34个主力监控品种
MONITOR_FUTURES = [
    "SA", "FG", "RB", "PG", "FU", "CJ", "OI", "SP", "LH", "JD",
    "SI", "PP", "SH", "EB", "NI", "SR", "EG", "AO", "JM", "EC",
    "RU", "BR", "SF", "M", "MA", "P", "V", "TA", "UR", "CF",
    "LC", "AU", "AG", "SC"
]

# 核心乘数表
FUTURES_MULTIPLIERS = {
    "SA": 20, "FG": 20, "RB": 10, "PG": 20, "FU": 10, "CJ": 5, "OI": 10, "SP": 10,
    "LH": 16, "JD": 5, "SI": 5, "PP": 5, "SH": 30, "EB": 5, "NI": 1, "SR": 10,
    "EG": 10, "AO": 20, "JM": 60, "EC": 50, "RU": 10, "BR": 5, "SF": 5, "M": 10,
    "MA": 10, "P": 10, "V": 5, "TA": 5, "UR": 20, "CF": 5, "LC": 1, "AU": 1000,
    "AG": 15, "SC": 1000
}

TOTAL_PATTERN_STRATEGIES = ["DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08"]
DEFAULT_FEISHU_WEBHOOK = os.getenv(
    "FENGJI_FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/8895c204-34e4-47aa-99a3-39859955fe91",
)
DEFAULT_SYMBOL_EQUITY = 100000.0
TRADE_COLUMNS = [
    "event_time", "symbol", "strategy_id", "side", "action", "lots",
    "entry_time", "entry_price", "exit_time", "exit_price", "net_pnl",
    "equity", "reason", "trade_key", "run_id",
]


def now_text() -> str:
    return pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S")


def normalize_symbol(symbol: str) -> str:
    text = symbol.strip().upper().replace("-", "").replace("_", "")
    if not text.endswith("USDT"):
        text += "USDT"
    return text


def display_name(symbol: str) -> str:
    return symbol.replace("USDT", "")


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️ [{now_text()}] 读取状态文件失败，将使用默认状态: {path} {exc}", flush=True)
        return default


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    last_error: Exception | None = None
    for attempt in range(10):
        tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.{attempt}.tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(str(tmp), str(path))
            return
        except PermissionError as exc:
            last_error = exc
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            time.sleep(0.2)
    raise PermissionError(f"保存状态文件失败，目标可能被其他程序短暂占用: {path}") from last_error


def runtime_path(args: argparse.Namespace, name: str) -> Path:
    return Path(args.runtime_dir) / name


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def log_event(args: argparse.Namespace, level: str, message: str, **payload: Any) -> None:
    record = {"time": now_text(), "level": level, "message": message, **payload}
    print(f"{level} [{record['time']}] {message} {payload if payload else ''}", flush=True)
    append_jsonl(runtime_path(args, "events_futures_astock.jsonl"), record)


def append_trade_csv(args: argparse.Namespace, record: dict) -> None:
    path = runtime_path(args, "trades_futures_astock.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRADE_COLUMNS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow({key: record.get(key, "") for key in TRADE_COLUMNS})


def send_msg(webhook: str, text: str) -> bool:
    if not webhook:
        return False
    try:
        resp = requests.post(webhook, json={"msg_type": "text", "content": {"text": text}}, timeout=8)
        return 200 <= resp.status_code < 300
    except Exception as exc:
        print(f"⚠️ [{now_text()}] 飞书推送失败: {exc}", flush=True)
        return False


def read_source_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [c.strip().lower() for c in frame.columns]
    if "date" not in frame.columns:
        if "timestamp" in frame.columns:
            frame = frame.rename(columns={"timestamp": "date"})
        elif "datetime" in frame.columns:
            frame = frame.rename(columns={"datetime": "date"})
        else:
            frame = frame.rename(columns={frame.columns[0]: "date"})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    required = ["date", "open", "high", "low", "close"]
    return frame.dropna(subset=required).sort_values("date").reset_index(drop=True)


def write_engine_csv(source: Path, target: Path, tail_rows: int) -> tuple[Path, pd.Timestamp]:
    frame = read_source_csv(source)
    if tail_rows > 0 and len(frame) > tail_rows:
        frame = frame.tail(tail_rows).copy()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    frame.to_csv(tmp, index=False, encoding="utf-8")
    os.replace(str(tmp), str(target))
    return target, pd.to_datetime(frame["date"].iloc[-1])


def current_bar_key(data_dir: Path, symbol: str) -> str:
    p1d = data_dir / "1d" / f"{symbol}.csv"
    p1h = data_dir / "1h" / f"{symbol}.csv"
    if not p1d.exists() or not p1h.exists():
        return ""
    try:
        f1d = read_source_csv(p1d)
        f1h = read_source_csv(p1h)
        if f1d.empty or f1h.empty:
            return ""
        return f"1d:{f1d['date'].iloc[-1]}|1h:{f1h['date'].iloc[-1]}"
    except Exception:
        return ""


def trade_key(row: pd.Series) -> str:
    return f"{row.get('symbol', '')}|{row.get('strategy_id', '')}|{row.get('entry_time', '')}|{row.get('entry_price', '')}|{row.get('side', '')}"


def init_symbol_state(state: dict, clean: str) -> dict:
    return state.setdefault(clean, {
        "last_bar_key": "",
        "initialized": False,
        "open_positions": [],
        "seen_entries": [],
        "closed_entries": [],
        "equity": DEFAULT_SYMBOL_EQUITY,
        "last_updated": "",
    })


def trim_state_lists(symbol_state: dict) -> None:
    symbol_state["seen_entries"] = list(symbol_state.get("seen_entries", []))[-2000:]
    symbol_state["closed_entries"] = list(symbol_state.get("closed_entries", []))[-2000:]


def active_positions(open_positions: list[dict]) -> list[dict]:
    return [pos for pos in open_positions if isinstance(pos, dict) and not pos.get("closed")]


def can_open_position(open_positions: list[dict], strategy_id: str, side: int, args: argparse.Namespace) -> tuple[bool, str]:
    positions = active_positions(open_positions)
    if len(positions) >= args.max_open_positions_per_symbol:
        return False, f"单品种总持仓已达上限 {args.max_open_positions_per_symbol}"

    for pos in positions:
        pos_side = safe_int(pos.get("side"), 0)
        if pos_side == 0:
            return False, "存在旧版未知方向持仓，等待先平仓"
        if pos_side != side:
            return False, "已有反向持仓，等待先平仓"

    if strategy_id == "DS01":
        ds01_count = sum(
            1 for pos in positions
            if str(pos.get("strategy_id", "")).upper() == "DS01" and safe_int(pos.get("side"), 0) == side
        )
        if ds01_count >= args.max_ds01_entries:
            return False, f"DS01 同向连续开仓已达 {args.max_ds01_entries} 次"
        return True, "DS01 允许同向连续开仓"

    same_strategy_count = sum(
        1 for pos in positions
        if str(pos.get("strategy_id", "")).upper() == strategy_id and safe_int(pos.get("side"), 0) == side
    )
    if same_strategy_count >= 1:
        return False, f"{strategy_id} 非连续定式已有同向持仓"
    return True, f"{strategy_id} 非连续定式允许首次开仓"


def write_status(args: argparse.Namespace, state: dict, run_id: str) -> None:
    summary = {
        "time": now_text(),
        "run_id": run_id,
        "version": state.get("version"),
        "symbols": {},
    }
    for symbol, item in state.get("symbols", {}).items():
        positions = active_positions(item.get("open_positions", []))
        summary["symbols"][symbol] = {
            "equity": item.get("equity", DEFAULT_SYMBOL_EQUITY),
            "last_bar_key": item.get("last_bar_key", ""),
            "last_updated": item.get("last_updated", ""),
            "open_count": len(positions),
            "open_positions": positions,
        }
    save_json(runtime_path(args, "status_futures_astock.json"), summary)


def process_symbol(symbol: str, args: argparse.Namespace, state: dict, run_id: str) -> None:
    clean = normalize_symbol(symbol)
    disp = display_name(clean)
    data_dir = Path(args.data_dir)

    bar_key = current_bar_key(data_dir, clean)
    if not bar_key:
        return

    symbol_state = init_symbol_state(state, clean)
    if symbol_state["last_bar_key"] == bar_key:
        return

    current_equity = safe_float(symbol_state.get("equity"), DEFAULT_SYMBOL_EQUITY)
    trade_lots = 2 if current_equity >= 200000.0 else 1

    cache_root = Path(args.runtime_dir) / "cache" / clean
    out_dir = Path(args.runtime_dir) / "runs" / run_id / clean

    try:
        daily_csv, _ = write_engine_csv(data_dir / "1d" / f"{clean}.csv", cache_root / f"{clean}_1D_runtime.csv", args.d1_tail_rows)
        h1_csv, h1_time = write_engine_csv(data_dir / "1h" / f"{clean}.csv", cache_root / f"{clean}_1H_runtime.csv", args.h1_tail_rows)
    except Exception as exc:
        log_event(args, "ERROR", "准备策略引擎输入数据失败", symbol=disp, error=str(exc))
        return

    engine_cfg = UnifiedConfig(
        initial_cash=DEFAULT_SYMBOL_EQUITY,
        lots=1,
        commission_rate=0.0,
        slippage_ticks=0.0,
        atr_window=14,
        gap=3,
        max_same_direction_entries=3,
        futures_mode=False,
        spec=None,
    )
    try:
        run_unified_symbol(clean.replace("USDT", ""), engine_cfg, daily_csv, h1_csv, None, TOTAL_PATTERN_STRATEGIES, out_dir)
    except Exception as exc:
        log_event(args, "ERROR", "策略引擎运行失败", symbol=disp, error=str(exc), traceback=traceback.format_exc())
        return

    symbol_state["last_bar_key"] = bar_key
    symbol_state["last_updated"] = now_text()

    accepted_path = out_dir / "accepted_trades.csv"
    accepted = pd.read_csv(accepted_path) if accepted_path.exists() else pd.DataFrame()

    if accepted.empty:
        symbol_state["initialized"] = True
        trim_state_lists(symbol_state)
        return

    if "strategy_priority" not in accepted.columns:
        accepted["strategy_priority"] = 999
    accepted["entry_time"] = pd.to_datetime(accepted["entry_time"], errors="coerce")
    accepted["exit_time"] = pd.to_datetime(accepted["exit_time"], errors="coerce")
    accepted = accepted.dropna(subset=["entry_time"]).sort_values(["entry_time", "strategy_priority"])
    accepted["trade_key"] = accepted.apply(trade_key, axis=1)

    if not symbol_state.get("initialized"):
        symbol_state["initialized"] = True
        symbol_state["seen_entries"] = [str(key) for key in accepted["trade_key"].tail(100).tolist()]
        trim_state_lists(symbol_state)
        print(f"[{disp}] 完成基线数据初始化", flush=True)
        return

    ref_time = h1_time
    lookback_start = ref_time - pd.Timedelta(hours=args.entry_lookback_hours)
    multiplier = FUTURES_MULTIPLIERS.get(disp, 10)

    # 1. 严格检查并执行模拟平仓
    still_open = []
    for pos in active_positions(symbol_state.get("open_positions", [])):
        key = str(pos.get("key", ""))
        matched = accepted[accepted["trade_key"] == key]
        if not matched.empty:
            row = matched.iloc[-1]
            exit_time = pd.to_datetime(row.get("exit_time"), errors="coerce")
            if not pd.isna(exit_time) and exit_time <= ref_time and key not in symbol_state.get("closed_entries", []):
                ep = safe_float(row.get("entry_price"))
                xp = safe_float(row.get("exit_price"))
                side = safe_int(row.get("side"), safe_int(pos.get("side"), 1))
                strategy_id = str(row.get("strategy_id", pos.get("strategy_id", ""))).upper()
                lots = safe_int(pos.get("lots"), 1)

                nominal_1_lot = ep * multiplier
                pnl_res = pct_return_trade(row, nominal_1_lot, 1.0, 0.0001, 0.0002, 0.05)
                real_net_pnl = safe_float(pnl_res.get("crypto_net_pnl")) * lots
                symbol_state["equity"] = safe_float(symbol_state.get("equity"), DEFAULT_SYMBOL_EQUITY) + real_net_pnl

                trade_record = {
                    "event_time": now_text(),
                    "symbol": disp,
                    "strategy_id": strategy_id,
                    "side": "LONG" if side == 1 else "SHORT",
                    "action": "CLOSE",
                    "lots": lots,
                    "entry_time": row.get("entry_time"),
                    "entry_price": ep,
                    "exit_time": exit_time,
                    "exit_price": xp,
                    "net_pnl": round(real_net_pnl, 2),
                    "equity": round(safe_float(symbol_state.get("equity"), DEFAULT_SYMBOL_EQUITY), 2),
                    "reason": row.get("exit_reason", ""),
                    "trade_key": key,
                    "run_id": run_id,
                }
                append_trade_csv(args, trade_record)
                log_event(args, "INFO", "模拟平仓", **trade_record)

                msg = (
                    f"✅【峰极总定式01-08国内期货A股模拟实盘 平仓】\n"
                    f"时间: {now_text()}\n"
                    f"品种: {disp}\n"
                    f"定式: {strategy_id}\n"
                    f"方向: {'多头' if side == 1 else '空头'}\n"
                    f"平仓价格: {xp:.4f}\n"
                    f"交易规模: 严格 {lots} 手 (单个账本资金: {symbol_state['equity']:.2f}元)\n"
                    f"平仓结果: {'盈利' if real_net_pnl >= 0 else '亏损'} {real_net_pnl:.2f} 元\n"
                    f"退出原因: {row.get('exit_reason', '')}"
                )
                send_msg(args.feishu_webhook, msg)
                symbol_state.setdefault("closed_entries", []).append(key)
                print(f"[{disp}] 模拟平仓信号播报成功", flush=True)
                continue
        still_open.append(pos)
    symbol_state["open_positions"] = still_open

    # 2. 严格检查次数限制，满足条件执行新开仓
    recent = accepted[(accepted["entry_time"] >= lookback_start) & (accepted["entry_time"] <= ref_time)].copy()
    if not recent.empty:
        seen = set(str(x) for x in symbol_state.get("seen_entries", []))
        for _, row in recent.sort_values(["entry_time", "strategy_priority"]).iterrows():
            key = str(row.get("trade_key", trade_key(row)))
            if key in seen:
                continue
            if any(str(pos.get("key", "")) == key for pos in active_positions(symbol_state.get("open_positions", []))):
                symbol_state["seen_entries"].append(key)
                continue

            strategy_id = str(row.get("strategy_id", "")).upper()
            side = safe_int(row.get("side"), 0)
            if strategy_id not in TOTAL_PATTERN_STRATEGIES or side not in (1, -1):
                symbol_state["seen_entries"].append(key)
                log_event(args, "WARN", "忽略异常开仓信号", symbol=disp, strategy_id=strategy_id, side=side, trade_key=key)
                continue

            allowed, reason = can_open_position(symbol_state.get("open_positions", []), strategy_id, side, args)
            if not allowed:
                symbol_state["seen_entries"].append(key)
                log_event(args, "INFO", "开仓信号被风控跳过", symbol=disp, strategy_id=strategy_id, side=side, reason=reason, trade_key=key)
                continue

            ep = safe_float(row.get("entry_price"))
            lots = trade_lots
            nominal_value = ep * multiplier * lots
            position = {
                "key": key,
                "strategy_id": strategy_id,
                "side": side,
                "entry_time": str(row.get("entry_time", "")),
                "entry_price": ep,
                "lots": lots,
                "created_at": now_text(),
                "entry_bar": str(h1_time),
                "risk_rule": reason,
            }
            symbol_state["seen_entries"].append(key)
            symbol_state.setdefault("open_positions", []).append(position)

            trade_record = {
                "event_time": now_text(),
                "symbol": disp,
                "strategy_id": strategy_id,
                "side": "LONG" if side == 1 else "SHORT",
                "action": "OPEN",
                "lots": lots,
                "entry_time": row.get("entry_time"),
                "entry_price": ep,
                "exit_time": "",
                "exit_price": "",
                "net_pnl": "",
                "equity": round(safe_float(symbol_state.get("equity"), DEFAULT_SYMBOL_EQUITY), 2),
                "reason": reason,
                "trade_key": key,
                "run_id": run_id,
            }
            append_trade_csv(args, trade_record)
            log_event(args, "INFO", "模拟开仓", **trade_record)

            msg = (
                f"🚨【峰极总定式01-08国内期货A股模拟实盘 开仓】\n"
                f"时间: {now_text()}\n"
                f"品种: {disp}\n"
                f"定式: {strategy_id}\n"
                f"方向: {'买入做多' if side == 1 else '卖出做空'}\n"
                f"入场价格: {ep:.4f}\n"
                f"交易规模: 严格 {lots} 手 (当前同品种持仓数: {len(active_positions(symbol_state['open_positions']))}/{args.max_open_positions_per_symbol})\n"
                f"单个品种独立本金: {safe_float(symbol_state.get('equity'), DEFAULT_SYMBOL_EQUITY):.2f} 元\n"
                f"名义合约总值: {nominal_value:.2f} 元\n"
                f"风控规则: {reason}\n"
                f"手续费设定: 万分之1\n"
                f"数据截至: {h1_time}"
            )
            send_msg(args.feishu_webhook, msg)
            print(f"[{disp}] 模拟开仓信号播报成功", flush=True)
            break

    trim_state_lists(symbol_state)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--runtime-dir", default="runtime/fengji_futures")
    parser.add_argument("--state-file", default="runtime/fengji_futures/state_futures_v2.json")
    parser.add_argument("--feishu-webhook", default=DEFAULT_FEISHU_WEBHOOK)
    parser.add_argument("--loop-seconds", type=int, default=60)
    parser.add_argument("--d1-tail-rows", type=int, default=800)
    parser.add_argument("--h1-tail-rows", type=int, default=2600)
    parser.add_argument("--entry-lookback-hours", type=int, default=3)
    parser.add_argument("--max-ds01-entries", type=int, default=3)
    parser.add_argument("--max-open-positions-per-symbol", type=int, default=3)
    args = parser.parse_args()

    state_path = Path(args.state_file)
    state = load_json(state_path, {"version": 3, "started_at": now_text(), "symbols": {}})
    state.setdefault("version", 3)
    state.setdefault("started_at", now_text())
    state.setdefault("symbols", {})

    startup = (
        f"🚀【峰极总定式01-08国内期货A股模拟实盘 已启动】\n"
        f"时间: {now_text()}\n"
        f"模式: 每个品种独立10万本金阶梯限仓策略\n"
        f"开仓约束: 基础1手 / 资金满20万开2手\n"
        f"限仓限制: DS01同向最多连续开仓 {args.max_ds01_entries} 次；DS02-DS08每个定式同向只开一次；单品种总持仓最多 {args.max_open_positions_per_symbol} 笔\n"
        f"反向限制: 有持仓时不允许开反方向仓\n"
        f"手续费设定: 万分之1 | 底层峰极OS与DS01-DS08策略核心未改"
    )
    print(startup, flush=True)
    send_msg(args.feishu_webhook, startup)
    log_event(args, "INFO", "模拟盘启动", max_ds01_entries=args.max_ds01_entries, max_open_positions_per_symbol=args.max_open_positions_per_symbol)

    while True:
        run_id = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%d_%H%M%S")
        for symbol in MONITOR_FUTURES:
            try:
                process_symbol(symbol, args, state["symbols"], run_id)
                save_json(state_path, state)
            except Exception as exc:
                log_event(args, "ERROR", "单品种处理异常", symbol=symbol, error=str(exc), traceback=traceback.format_exc())
                send_msg(args.feishu_webhook, f"⚠️【国内期货A股模拟盘异常】\n时间: {now_text()}\n品种: {symbol}\n错误: {exc}")
        write_status(args, state, run_id)
        time.sleep(args.loop_seconds)


if __name__ == "__main__":
    main()
