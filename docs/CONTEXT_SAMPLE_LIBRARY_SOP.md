# 样本库增量维护 SOP（Wave 2 · C7a）

状态：`ACTIVE`  
关联：`docs/FJLHXM_EXECUTION_PLAN_2026-06-09.md` Wave 2–3

---

## 1. 目标

把四市场 **K 线 → 回测成交 → context 快照（L0–L4）→ PG → Web `signal_tier`** 做成可重复的增量流水线。

**禁止**：为提高 tier 修改峰极 OS / 九大定式 / 挂单授权。

---

## 2. 链路定义

| 阶段 | 产物 | 工具 |
|------|------|------|
| K 线 | `data/**/{symbol}.csv` | 数据泵 / 手动下载 |
| 回测 | `results/**/accepted_trades.csv` | `batch_unified_whitelist_engine.py` 等 |
| Context | `trade_context_snapshots.csv`、`context_bucket_stats.csv` | `batch_build_context_stats.py` |
| PG | `trade_context_snapshots`、`context_bucket_stats` 表 | `batch_import_context_stats_to_pg.py` |
| Web | 回测页 trades / strength / 同桶 | API + `backtest.html` |

**完整链路**（C0 口径）：CSV + 回测目录（trade_count>0）+ context CSV + PG 有该品种快照。

---

## 3. 何时做什么（决策表）

| 情况 | 动作 |
|------|------|
| 新下载 K 线，无 `results/` | Wave 3 **C1 增量回测** |
| 有回测，无 context CSV | **C3** `batch_build_context_stats --only-missing` |
| 有 context CSV，Web 缺 PG | **C4** `batch_import_context_stats_to_pg.py` |
| OS/定式规则变更 | **C2** 选择性重跑受影响目录 + C3 + C4 |
| 仅改 `context_market_calibration.json` | PG **rebuild buckets**（C4 内 `--skip-rebuild` 勿开） |
| 模拟盘成交 | **M 线** `audit_paper_fills.py`，不进 PG 样本库 |

**不要**在每次 CSV 扩容后全市场重跑回测。

---

## 4. 标准操作（本地）

### 4.1 缺口盘点（每次 Wave 开始前）

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
python scripts/audit_coverage_gaps.py
# 阅读 results/coverage_gap_report.md
```

### 4.2 Context 批处理（C3）

```powershell
python scripts/batch_build_context_stats.py --only-missing --dry-run
python scripts/batch_build_context_stats.py --only-missing
```

`ok=0` 表示已有回测目录均已生成 context — **正常**（Wave 2 2026-06-09 实测）。

### 4.3 PG 导入（C4）

```powershell
# 需 Docker PG + fengji_local.env
docker compose up -d
$env:PYTHONPATH = "src;packages/fengji_core;services"
python scripts/batch_import_context_stats_to_pg.py
# context 字段变更（如 exit_price）后建议全量刷新：
python scripts/batch_import_context_stats_to_pg.py --fresh
python scripts/verify_trade_exit_price_coverage.py --pg
```

### 4.4 验收 smoke

```powershell
python scripts/smoke_pg_api_consistency.py --sample-plan "A_STOCK=4,CRYPTO=3,FUTURES=3,US_STOCK=3"
python scripts/smoke_w14_backtest_api.py --port 8000
python scripts/smoke_w14_backtest_browser.py --base-url http://127.0.0.1:8000
```

---

## 5. 分市场增量回测（Wave 3 · C1）

按 C0「仅 CSV」数量优先级：

1. **CRYPTO** ✅ 2026-06-09（`run_crypto_c1_local.py` 非 OKX 品种 + promote `_io_unified`）
2. **FUTURES** ✅ 2026-06-09（19 品种 D1-only → `plan_a_futures_c1`；余 5 为 catalog 误分类）
3. **A_STOCK / US_STOCK**（215+222）→ **分批**，每批后跑 C3→C4

```powershell
# 美股批1（默认 10 只缺口）
python scripts/run_us_stock_c1_local.py --limit 10
python scripts/run_us_stock_c1_local.py --limit 20   # 续跑下一批
```

```powershell
# OKX 白名单
python src/batch_unified_crypto_whitelist.py --symbols SOLUSDT --days 180

# 非 OKX（overseas_1d 已有 K 线，如 IOUSDT/TAOUSDT）
python scripts/run_crypto_c1_local.py --symbols IOUSDT,TAOUSDT --promote-from "IOUSDT=results/_io_unified"

# 国内期货 D1-only 增量
python scripts/run_futures_c1_local.py --dry-run
python scripts/run_futures_c1_local.py
```

```powershell
python scripts/batch_build_context_stats.py --only-missing
python scripts/batch_import_context_stats_to_pg.py
python scripts/audit_coverage_gaps.py
```
---

## 6. signal_tier 使用边界

- **允许**：回测页筛选、同桶样本展示、复盘 CSV 导出。
- **禁止**：自动修改雷达授权、挂单监控、风控参数、模拟盘开仓逻辑。
- **样本不足**：`INSUFFICIENT_DATA`（桶 N&lt;30）不得强行标 STRONG。

分市场校准：`data/context_market_calibration.json`（A股 + CRYPTO 已 active；FUTURES 保留旧阈值，新分位待样本）。

---

## 7. Wave 2 验收记录（2026-06-09）

| 项 | 结果 |
|----|------|
| C3 `--only-missing` | ok=0（已有回测均已 context） |
| C4 PG 导入 | 137 目录重导 + bucket 重建 |
| D5 | 13/13（Wave 1 已验，Wave 2 可复跑） |
| D4a | 四市场 API OK |
| D4b | `smoke_w14_backtest_browser.py` 四市场 OK（~8s；独立 context） |
| 竞态修复 | `backtest.html` `await initStrategies()` 后再 `loadAll` |

---

## 8. 相关文档

- 主计划：`docs/FJLHXM_EXECUTION_PLAN_2026-06-09.md`
- 成交监督：`docs/FILL_SUPERVISION_SOP_2026-06-09.md`
- W14 验收：`docs/W14_BACKTEST_ACCEPTANCE_2026-06-05.md`
