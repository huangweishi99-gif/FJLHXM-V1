from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args()

    from data_manager_futures import TQ_SYMBOL_MAP, connect_api, fetch_symbol

    symbol = args.symbol.upper().replace("USDT", "")
    api = connect_api()
    try:
        ok = fetch_symbol(api, symbol, TQ_SYMBOL_MAP[symbol])
        print(f"{symbol}_FORCE_FETCH={ok}")
    finally:
        api.close()


if __name__ == "__main__":
    main()
