# Wave 4 · Crypto DS09 沙盒 · 2026-06-16

## 范围

IOUSDT / BNBUSDT · DS09《九重天》· 只读诊断 + 成交级沙盒图 · **不改定式/OS**。

## BNBUSDT 结论

| 项 | 值 |
|----|-----|
| D1 camp | -1 / confirmed -1 |
| 2500 M15 窗口 | boundary_sessions=202 |
| lock / signal | 5 / 4 |
| backtest_trades | **4**（最近 2026-05-20 short） |
| 窗口末 session | 2026-05-25 · **no_boundary** |
| live radar | 待 radar 出现 DS09 行再出 live 沙盒 |

## 产出

- `results/crypto_ds09_sandbox_20260616/BNBUSDT_DS09_trade_20260611.png` — 成交级
- `results/crypto_ds09_sandbox_20260616/BNBUSDT_DS09_session_2026-05-20_lock.png` — 最近 lock 日
- `results/crypto_ds09_sandbox_20260616/crypto_ds09_sandbox_report.md`

## 复现

```powershell
python scripts/run_crypto_ds09_sandbox_review.py --symbols BNBUSDT --out-dir results/crypto_ds09_sandbox_20260616 --daily-tail 450 --m15-tail 2500
python src/plot_ds09_sandbox.py --crypto --d1-csv data/1d/BNBUSDT.csv --m15-csv data/crypto_okx/BNB-USDT_15m_180d.csv --symbol BNBUSDT --trade-no 1 --out results/crypto_ds09_sandbox_20260616/BNBUSDT_DS09_trade_20260611.png --d1-tail 450 --m15-tail 2500
```

## 待观察

- [ ] radar 出现 DS09 live 行 → 同上 `plot_ds09_sandbox.py` 出图
