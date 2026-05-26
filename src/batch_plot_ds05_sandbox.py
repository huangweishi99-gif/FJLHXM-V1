from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

from backtest_ds05 import DS05BacktestConfig, run_ds05_backtest
from plot_ds05_sandbox import plot_trade
from quant.data import load_ohlcv_for_engine
from quant.futures_specs import get_futures_spec


def make_config(args: argparse.Namespace, csv_path: Path) -> DS05BacktestConfig:
    return DS05BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        extreme_atr_tol=args.extreme_atr_tol,
        gap=args.gap,
        futures_mode=args.futures_mode,
        spec=get_futures_spec(csv_path) if args.futures_mode else None,
    )


def make_contact_sheet(files: list[Path], out_path: Path, thumb_width: int = 900) -> None:
    thumbs: list[Image.Image] = []
    for file_path in files:
        image = Image.open(file_path).convert("RGB")
        ratio = thumb_width / image.width
        thumb = image.resize((thumb_width, int(image.height * ratio)))
        canvas = Image.new("RGB", (thumb.width, thumb.height + 34), "white")
        canvas.paste(thumb, (0, 34))
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 8), file_path.stem, fill=(0, 0, 0))
        thumbs.append(canvas)

    out = Image.new("RGB", (thumb_width, sum(thumb.height for thumb in thumbs)), "white")
    y = 0
    for thumb in thumbs:
        out.paste(thumb, (0, y))
        y += thumb.height
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate sandbox charts for the last N DS05 trades.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--last", type=int, default=7)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--before", type=int, default=30)
    parser.add_argument("--after", type=int, default=15)
    parser.add_argument("--line-mode", choices=["hardened", "identity", "tagged", "both", "all"], default="hardened")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--extreme-atr-tol", type=float, default=0.80)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--futures-mode", action="store_true")
    parser.add_argument("--no-contact", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    out_dir = Path(args.out_dir) if args.out_dir else Path("results") / "sandbox" / f"{csv_path.stem}_last{args.last}"
    config = make_config(args, csv_path)

    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    result = run_ds05_backtest(df, config)
    trades = result["trades"]
    if trades.empty:
        raise ValueError(f"No DS05 trades found for {csv_path}")

    selected = trades.tail(args.last)["trade_no"].astype(int).tolist()
    files: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    trades.tail(args.last).to_csv(out_dir / "selected_trades.csv", index=False)

    for trade_no in selected:
        out_path = out_dir / f"{csv_path.stem}_trade_{trade_no}.png"
        plot_trade(csv_path, trade_no, out_path, args.before, args.after, config, args.line_mode)
        files.append(out_path)
        print(f"Saved {out_path}")

    if not args.no_contact:
        contact_path = out_dir / f"{csv_path.stem}_last{args.last}_contact.png"
        make_contact_sheet(files, contact_path)
        print(f"Saved contact sheet {contact_path}")


if __name__ == "__main__":
    main()

