# FUTURES 5m 数据桶规划

更新：2026-07-03  
状态：**PR-A 已部署国内 · PR-B 脚本就绪 · 待首轮回填**

## PR-A · 数据泵（✅ 2026-07-03）

| 项 | 状态 |
|----|------|
| `data_manager_futures.py` 增加 `5m` | ✅ duration=300 · 默认 6000 根 |
| `data/5m/` 目录 | ✅ 国内已创建 |
| 测试 | ✅ `tests/test_data_manager_futures_5m.py` 3 passed |
| 国内部署 | ✅ 仅重启 data_manager（paper/radar/pending 未动） |

**说明**：12:18 部署时处于非交易更新时段，5m CSV 将在下一交易窗口（约 13:00 日盘）开始写入。

环境变量：`FUTURES_5M_LENGTH`（默认 6000）

## PR-B · 本机同步 + SQLite（✅ 脚本 2026-07-03）

1. `scripts/sync_domestic_futures_5m_for_context.py` — SSH scp 国内 `data/5m/{CODE}.csv`
2. `scripts/run_sync_domestic_futures_5m_for_context.ps1` — sync + `market_data_store import-futures-local`
3. `assess_instruments_vs_coverage.py` — FUTURES 5m 周期对账

**前置**：国内 `data/5m/*.csv` 有数据后执行（午休 12:27 仍为 0，约 13:00 日盘写入）。

```powershell
powershell -File scripts\run_sync_domestic_futures_5m_for_context.ps1
python scripts/assess_instruments_vs_coverage.py
```

## 验收

```powershell
python -m pytest tests/test_sync_domestic_futures_5m_for_context.py tests/test_market_data_store_futures_local.py -q
python -m pytest tests/test_data_manager_futures_5m.py -q  # 需 tqsdk2 环境
python scripts/assess_instruments_vs_coverage.py  # sync+ingest 后 FUTURES 5m pass
```

## 非目标

- 不改 OS / 定式 / 挂单规则
- 不用 15m 冒充 5m
