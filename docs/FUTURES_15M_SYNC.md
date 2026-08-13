# FUTURES 15m 数据同步（context 回填）

状态：`ACTIVE`（2026-06-16）

## 用途

从国内服务器拉取期货 **15m** K 线，写入 `data/futures/15m/`，供 `run_futures_context_backfill.py` 按 `entry_idx` 重建 context snapshots。

**不**修改峰极 OS / 定式 / 挂单规则。

## 计划任务（本机）

| 任务名 | 频率 | 脚本 |
|--------|------|------|
| `FengJiDomesticFutures15mSync` | 每天 **07:30、19:30** | `run_sync_domestic_futures_15m_for_context.ps1` |

安装：

```powershell
powershell -File scripts\install_domestic_futures_15m_sync_task.ps1
```

## 手动同步

```powershell
powershell -File scripts\run_sync_domestic_futures_15m_for_context.ps1
# 或
python scripts/sync_domestic_futures_15m_for_context.py --ssh-host domestic-quant
```

## 输出路径

每个品种写两份（中文名 + 短代码）：

- `data/futures/15m/豆粕.csv` + `data/futures/15m/M.csv`

远端源：`domestic-quant:.../data/15m/{CODE}.csv`（实际主力合约，拒绝 `KQ.m@` 主连）

## 回填 + 复审计

```powershell
python scripts/run_futures_context_backfill.py --out-dir results/futures_context_backfill_rerun
python scripts/run_futures_tier_pg_refresh.py --out-dir results/futures_tier_pg_refresh_rerun
```

## 2026-06-16 结果

| 指标 | 15m 同步前 | 15m 同步后 |
|------|------------|------------|
| snapshots | 1400 | **9329** |
| eligible_buckets | 16 | **59** |
| PG status | INSUFFICIENT | **READY_FOR_REVIEW** |

推荐新分位（**已激活 2026-06-16**）：`tier_medium=0.443491` · `tier_strong=0.70411`

仍缺覆盖：约 **494** 笔成交（9 品种 15m 历史短于 5y 回测窗口）

## 日志

`runtime/logs/domestic_futures_15m_sync.log`
