# FUTURES 5m 数据桶规划

更新：2026-07-03  
状态：**PR-A 已部署国内 · 待首轮回填**

## PR-A · 数据泵（✅ 2026-07-03）

| 项 | 状态 |
|----|------|
| `data_manager_futures.py` 增加 `5m` | ✅ duration=300 · 默认 6000 根 |
| `data/5m/` 目录 | ✅ 国内已创建 |
| 测试 | ✅ `tests/test_data_manager_futures_5m.py` 3 passed |
| 国内部署 | ✅ 仅重启 data_manager（paper/radar/pending 未动） |

**说明**：12:18 部署时处于非交易更新时段，5m CSV 将在下一交易窗口（约 13:00 日盘）开始写入。

环境变量：`FUTURES_5M_LENGTH`（默认 6000）

## PR-B · 本机同步 + SQLite（待办）

1. 参照 `sync_domestic_futures_15m_for_context.py` 增加 **5m 同步脚本**
2. `market_data_store` ingest · 重跑 B0-2 对账

**前置**：国内 `data/5m/*.csv` 有数据后执行。

## 验收

```powershell
python -m pytest tests/test_data_manager_futures_5m.py -q
python scripts/assess_instruments_vs_coverage.py  # PR-B 后 FUTURES 5m pass
```

## 非目标

- 不改 OS / 定式 / 挂单规则
- 不用 15m 冒充 5m
