from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from quant.ds03 import resolve_ds03_attack
from quant.os_engine import BLUE, RED, FengJiOSIdentityEngine


def load_ohlcv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(column).strip().lower() for column in df.columns]
    if "date" not in df.columns:
        for candidate in ["timestamp", "datetime", "time"]:
            if candidate in df.columns:
                df = df.rename(columns={candidate: "date"})
                break
    if "date" not in df.columns and len(df.columns) >= 5:
        df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)


def fmt(value: float) -> str:
    return f"{value:.8g}"


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def line(x1: float, y1: float, x2: float, y2: float, color: str, width: float = 1.0, dash: str = "") -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}"{dash_attr}/>'


def text(x: float, y: float, body: object, size: int = 12, color: str = "#202124", anchor: str = "middle") -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-family="Arial, Microsoft YaHei, sans-serif">{esc(body)}</text>'


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", opacity: float = 1.0) -> str:
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{fill}" stroke="{stroke}" opacity="{opacity:.3f}"/>'


def circle(x: float, y: float, r: float, fill: str, stroke: str = "none") -> str:
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{fill}" stroke="{stroke}"/>'


def polygon(points: list[tuple[float, float]], fill: str, stroke: str = "white") -> str:
    body = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polygon points="{body}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'


def make_svg(
    df: pd.DataFrame,
    os_df: pd.DataFrame,
    engine: FengJiOSIdentityEngine,
    *,
    symbol: str,
    target_idx: int,
    side: str,
    trigger_price: float,
    fill_price: float,
    stop_price: float,
    before: int,
    after: int,
) -> str:
    start = max(0, target_idx - before)
    end = min(len(df) - 1, target_idx + after)
    window = os_df.iloc[start : end + 1].copy()

    attack = resolve_ds03_attack(os_df, target_idx)
    ref_idx = int(attack.ref_idx) if attack is not None and attack.ref_idx is not None else None
    ref_price = float(attack.entry_ref) if attack is not None else trigger_price
    source = str(attack.trigger_source) if attack is not None else "trigger"

    values = list(window["high"].astype(float)) + list(window["low"].astype(float)) + [trigger_price, fill_price, stop_price, ref_price]
    ymin = min(values)
    ymax = max(values)
    pad = (ymax - ymin) * 0.09 if ymax > ymin else max(abs(ymax) * 0.01, 1.0)
    ymin -= pad
    ymax += pad

    width = 1500
    height = 860
    left = 78
    right = 42
    top = 74
    bottom = 92
    plot_w = width - left - right
    plot_h = height - top - bottom
    n = max(1, end - start)
    bar_step = plot_w / max(1, len(window) - 1)
    body_w = max(3.0, min(10.0, bar_step * 0.58))

    def x_at(idx: int) -> float:
        return left + (idx - start) * bar_step

    def y_at(price: float) -> float:
        return top + (ymax - price) / (ymax - ymin) * plot_h

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        rect(0, 0, width, height, "#ffffff"),
        text(width / 2, 30, f"{symbol.upper()} DS03 sandbox | {str(os_df.iloc[target_idx]['date'])[:10]} | {side.upper()} | source={source}", 18, "#111827"),
        text(width / 2, 53, f"trigger={fmt(trigger_price)}  fill/latest={fmt(fill_price)}  initial_stop={fmt(stop_price)}", 13, "#374151"),
        rect(left, top, plot_w, plot_h, "#fafafa", "#d1d5db"),
    ]

    for j, row in os_df.iloc[start : end + 1].iterrows():
        camp = int(row.get("camp", 0) or 0)
        fill = "#ffdddd" if camp == RED else "#dde8ff" if camp == BLUE else "#eeeeee"
        parts.append(rect(x_at(j) - bar_step / 2, top, bar_step, plot_h, fill, opacity=0.26))

    for k in range(6):
        price = ymin + (ymax - ymin) * k / 5
        y = y_at(price)
        parts.append(line(left, y, left + plot_w, y, "#e5e7eb", 1))
        parts.append(text(left - 10, y + 4, fmt(price), 11, "#6b7280", "end"))

    for j, row in os_df.iloc[start : end + 1].iterrows():
        x = x_at(j)
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        up = close >= open_
        color = "#d62728" if up else "#1f77b4"
        parts.append(line(x, y_at(high), x, y_at(low), color, 1.1))
        y1 = y_at(max(open_, close))
        y2 = y_at(min(open_, close))
        parts.append(rect(x - body_w / 2, y1, body_w, max(1.0, y2 - y1), color, color, 0.78))

    visible_nodes = sorted(
        [node for node in engine.hardened_nodes if start <= int(node.point_idx) <= end],
        key=lambda item: int(item.point_idx),
    )
    if len(visible_nodes) >= 2:
        point_body = " ".join(f"{x_at(int(node.point_idx)):.2f},{y_at(float(node.price)):.2f}" for node in visible_nodes)
        parts.append(f'<polyline points="{point_body}" fill="none" stroke="#6f35b5" stroke-width="2.2"/>')
    for node in visible_nodes:
        x = x_at(int(node.point_idx))
        y = y_at(float(node.price))
        label = "PEAK" if node.raw_type == "HIGH" else "EXT"
        parts.append(circle(x, y, 4.8, "#6f35b5", "white"))
        parts.append(text(x, y - 8 if node.raw_type == "HIGH" else y + 16, f"{label} {fmt(float(node.price))}", 10, "#4a148c"))

    for node in engine.identity_nodes:
        if not str(node.identity).startswith("FAILED"):
            continue
        idx = int(node.point_idx)
        if not (start <= idx <= end):
            continue
        x = x_at(idx)
        y = y_at(float(node.price))
        parts.append(line(x - 6, y - 6, x + 6, y + 6, "#ff6d00", 2.2))
        parts.append(line(x - 6, y + 6, x + 6, y - 6, "#ff6d00", 2.2))
        parts.append(text(x, y - 12, f"{node.identity} {fmt(float(node.price))}", 10, "#e65100"))

    trigger_y = y_at(trigger_price)
    stop_y = y_at(stop_price)
    parts.append(line(left, trigger_y, left + plot_w, trigger_y, "#7b1fa2", 1.6, "8 5"))
    parts.append(text(left + plot_w - 4, trigger_y - 6, f"trigger {fmt(trigger_price)}", 12, "#7b1fa2", "end"))
    parts.append(line(left, stop_y, left + plot_w, stop_y, "#8e24aa", 1.5, "2 5"))
    parts.append(text(left + plot_w - 4, stop_y + 16, f"initial stop {fmt(stop_price)}", 12, "#8e24aa", "end"))

    if ref_idx is not None and start <= ref_idx <= end:
        rx = x_at(ref_idx)
        ry = y_at(ref_price)
        parts.append(polygon([(rx, ry - 8), (rx + 8, ry), (rx, ry + 8), (rx - 8, ry)], "#6a00a8"))
        parts.append(text(rx, ry - 12, f"{source} {fmt(ref_price)}", 11, "#6a00a8"))

    entry_x = x_at(target_idx)
    entry_y = y_at(fill_price)
    entry_color = "#00897b" if side == "long" else "#c62828"
    if side == "long":
        pts = [(entry_x, entry_y - 14), (entry_x + 11, entry_y + 8), (entry_x - 11, entry_y + 8)]
        label_y = entry_y - 20
    else:
        pts = [(entry_x, entry_y + 14), (entry_x + 11, entry_y - 8), (entry_x - 11, entry_y - 8)]
        label_y = entry_y + 26
    parts.append(polygon(pts, entry_color))
    parts.append(text(entry_x, label_y, f"DS03 {side.upper()} fill {fmt(fill_price)}", 12, entry_color))

    date_ticks = []
    last_month = None
    for j, row in os_df.iloc[start : end + 1].iterrows():
        ts = pd.to_datetime(row["date"])
        if j in {start, target_idx, end} or ts.day in {1, 15} or ts.month != last_month:
            date_ticks.append((j, ts.strftime("%m-%d")))
            last_month = ts.month
    for j, label in date_ticks:
        x = x_at(j)
        parts.append(line(x, top + plot_h, x, top + plot_h + 5, "#9ca3af", 1))
        parts.append(text(x, top + plot_h + 22, label, 10, "#6b7280"))

    camp = int(os_df.iloc[target_idx].get("camp", 0) or 0)
    camp_label = "red" if camp == RED else "blue" if camp == BLUE else "neutral"
    parts.append(text(left, height - 24, f"FengJi OS camp at trigger bar: {camp_label}. Purple line is hardened peak-extreme line.", 12, "#374151", "start"))
    parts.append("</svg>")
    return "\n".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a dependency-light live DS03 SVG sandbox chart.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--date", required=True)
    parser.add_argument("--side", choices=["long", "short"], required=True)
    parser.add_argument("--fill-price", type=float, required=True)
    parser.add_argument("--trigger-price", type=float, required=True)
    parser.add_argument("--stop-price", type=float, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--before", type=int, default=110)
    parser.add_argument("--after", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.data_dir) / args.timeframe / f"{args.symbol.upper()}.csv"
    df = load_ohlcv(csv_path)
    engine = FengJiOSIdentityEngine().run(df)
    os_df = engine.to_frame(df)
    target = pd.to_datetime(args.date)
    matches = os_df.index[pd.to_datetime(os_df["date"]).dt.date == target.date()].tolist()
    if not matches:
        raise SystemExit(f"date not found: {args.date}")
    idx = int(matches[-1])
    svg = make_svg(
        df,
        os_df,
        engine,
        symbol=args.symbol,
        target_idx=idx,
        side=args.side,
        trigger_price=args.trigger_price,
        fill_price=args.fill_price,
        stop_price=args.stop_price,
        before=args.before,
        after=args.after,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
