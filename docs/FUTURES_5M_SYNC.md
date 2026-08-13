# FUTURES 5m 数据同步（SQLite / B0-2）

状态：`ACTIVE`（2026-07-03）

## 用途

从国内服务器拉取期货 **5m** K 线，写入 `data/futures/5m/`，并 ingest 到本地 `data/market_data.sqlite`，供 Plan B B0-2 对账。

**不**修改峰极 OS / 定式 / 挂单规则。

## 手动同步 + ingest

```powershell
powershell -File scripts\run_sync_domestic_futures_5m_for_context.ps1
# 仅 sync、不 ingest：
powershell -File scripts\run_sync_domestic_futures_5m_for_context.ps1 -SkipIngest
```

或：

```powershell
python scripts/sync_domestic_futures_5m_for_context.py --ssh-host domestic-quant
python src/market_data_store.py --db data/market_data.sqlite import-futures-local
```

## 输出路径

每个品种写两份（中文名 + 短代码）：

- `data/futures/5m/豆粕.csv` + `data/futures/5m/M.csv`

远端源：`domestic-quant:.../data/5m/{CODE}.csv`（实际主力合约，拒绝 `KQ.m@` 主连）

## B0-2 对账

```powershell
python scripts/assess_instruments_vs_coverage.py
```

## 日志

`runtime/logs/domestic_futures_5m_sync.log`

## 前置

国内数据泵 PR-A 已部署；首轮回填需处于交易更新时段（非午休/非休市）。
