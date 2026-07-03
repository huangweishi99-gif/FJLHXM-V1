# FUTURES 5m 数据桶规划

更新：2026-07-03  
状态：**BLOCKED · 数据泵未产出 5m**

## 现状

| 来源 | 5m |
|------|-----|
| 国内 `data_manager_futures.py` | ❌ 仅 `1d/1h/15m` |
| 国内服务器 `data/5m/` | ❌ 目录不存在 |
| SQLite `market_data.sqlite` | ❌ 缺整周期 `5m`（69 品种） |
| B0-2 对账 | `assess_instruments_vs_coverage.py` → FUTURES **pass=false** |

## 目标（Plan A 口径）

- 69 个期货品种均有 **5m** K 线（与 15m/1h/1d 并列）
- 写入路径：`data/5m/{CODE}.csv`（实际主力合约，禁止 `KQ.m@` 主连污染）
- 下游：SQLite/PG ingest · context 回填（若需要）

## 建议分桶 PR（不混 core 策略）

### PR-A · 数据泵扩展（国内服务器）

1. `data_manager_futures.py` 增加 `5m` timeframe（天勤 `duration=300`）
2. `DATA_LENGTHS["5m"]` 初值建议 **3000–6000**（按 `frame_looks_sane` 降档）
3. 创建 `data/5m/` 目录 · manifest 审计 `data_contract_is_actual`
4. 测试：`tests/test_data_manager_futures_main_contracts.py`

### PR-B · 本机同步 + SQLite

1. 参照 `sync_domestic_futures_15m_for_context.py` 增加 **5m 同步脚本**
2. `market_data_store` ingest · 重跑 B0-2 对账

### PR-B 前置条件

**必须先完成 PR-A**（国内有 CSV 才可 sync）。

## 非目标

- 不为此改 OS / 定式 / 挂单规则
- 不拿 15m 冒充 5m 凑 coverage

## 验收

```powershell
python scripts/assess_instruments_vs_coverage.py
# FUTURES pass=true · missing_timeframes 不含 5m
```
