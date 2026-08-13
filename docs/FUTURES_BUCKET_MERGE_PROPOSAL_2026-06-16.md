# FUTURES 桶维度合并立项

状态：`PHASE1+2 IMPLEMENTED`（2026-06-16，用户批准 1+2）  
类型：**统计层 / Web 展示层** — **不涉及**峰极 OS、阵营转换、DS01–DS09 定式、挂单器、风控

## 1. 背景

FUTURES `signal_tier` 二次校准已写入 `data/context_market_calibration.json`（`tier_medium=0.533186`、`tier_strong=0.7`），但激活条件要求 **eligible_buckets ≥ 30**（每桶样本 N≥30 且可算 `signal_score`）。

| 指标 | 当前值（2026-06-16 PG 复审计） |
|------|-------------------------------|
| 快照数 | 1410 |
| 桶数 | 342 |
| eligible_buckets | **4** |
| N&lt;10 桶 | 306 |
| 状态 | `INSUFFICIENT_MARKET_DATA` |

离线评估与 PG 全量 import 结论一致：**不是缺 PG 导入，而是桶过度碎片化**。

## 2. 根因分析

### 2.1 现行分桶（V1）

来源：`packages/fengji_core/fengji_core/context_stats.py`

| 维度 | 切桶方式 | FUTURES 实际基数 |
|------|----------|------------------|
| `camp` | enum | 3 |
| `camp_confirmed` | enum | 3（与 camp **100% 相同**） |
| `dist_active_high_atr` | NEAR/MID/FAR | 4 |
| `bar_direction` | BULL/BEAR | 2 |
| `position_in_range_20` | LOW/MID/HIGH | 3 |
| `market_regime_vol` | LOW/NORM/HIGH | 3 |
| 定式 extra | DS03 peak_key 等 | 按定式 |

理论组合极大，1410 笔快照被切成 **342** 桶，均值约 **4.1 笔/桶**。

### 2.2 冗余维度

- `camp` 与 `camp_confirmed` 在 FUTURES 1410 快照中 **100% 一致** — 双写不增信息，但 key 字符串仍占两维。
- `market_regime_vol` 与 `position_in_range_20` 贡献最大碎片化（去掉后桶数 342→184 / 209）。

### 2.3 样本池未用尽（并行轨道，非本立项唯一手段）

| 来源 | 数量 |
|------|------|
| `accepted_trades.csv` 合计 | **9823** |
| `trade_context_snapshots.csv` 合计 | **1410** |

例：豆粕 1133 笔成交 → 仅 28 条 snapshot。说明 **context 构建过滤**（OS 审计失败、缺 L2 字段等）丢弃了大部分历史成交，而非定式无信号。  
**补 snapshot 属于 B 轨「样本回填」**，与桶合并正交，可并行立项。

## 3. 目标

1. 在 **不改 OS/定式** 前提下，将 FUTURES eligible_buckets 从 4 提升到 **≥30**，以便评审是否激活新分位阈值。
2. 合并方案必须 **可审计、可回滚、按 market 隔离**（不影响 A_STOCK / CRYPTO 现行 V1 桶）。
3. Web 回测页 `signal_tier` **仅用于复盘筛选**，不得反向修改策略规则（沿用 W22/W24 边界）。

## 4. 模拟结果（只读脚本）

脚本：`scripts/simulate_futures_bucket_merge.py`  
报告：`results/futures_bucket_merge_sim_20260616/futures_bucket_merge_simulation.json`

`min_bucket_samples=30` 时各方案：

| 方案 | 说明 | 桶数 | eligible |
|------|------|------|----------|
| V1_current | 现行 6 维 + extra | 342 | 4 |
| B_drop_market_regime_vol | 去掉波动 regime | 184 | 10 |
| C_drop_position_in_range_20 | 去掉区间位置 | 209 | 8 |
| D_coarse_atr_2bin | ATR：NEAR+MID / FAR | 255 | 8 |
| **F_core3** | camp_confirmed + ATR + bar_direction | 99 | **12** |
| **I_recommended_v1** | core3 + 粗 ATR + 保留 DS03 peak_key | 81 | **13** |
| H_strategy_only | 仅 strategy（对照，过粗） | 8 | 5 |

**结论**：单靠降维，在 N≥30 下 **最高约 13 个 eligible 桶**，仍达不到 30。  
若将 `min_bucket_samples` 降到 **25**（仍属校准参数，非定式改动），`I_recommended_v1` 可达 **20**；降到 **15** 时 `C_drop_position_in_range_20` 可达 **30** — 统计置信度下降，需单独风险签字。

## 5. 推荐方案（待用户批准）

### 方案 I — FUTURES 专用桶配置 `futures_v2`

**统计层 override**（仅 `market=FUTURES`）：

```
camp_confirmed (enum)
dist_active_high_atr (coarse2: NEAR_MID | FAR | UNKNOWN)
bar_direction (enum)
DS03 保留 peak_key；DS07/DS09 extra 暂不保留
```

**不改**：OS 硬化、定式信号、accepted_trades 生成逻辑。

**预期**（基于现有 1410 快照）：桶 **81**，eligible **13**（N≥30）。

### 组合路径（推荐并行，而非二选一）

| 轨道 | 动作 | 预期贡献 |
|------|------|----------|
| **A 降维** | 上线 `futures_v2` 桶配置 | eligible 4 → ~13 |
| **B 回填** | 对 34 品种重跑 `batch_build_context_stats --market FUTURES`，排查 snapshot 丢弃原因 | 快照 1410 → 目标显著增加 |
| **C 校准** | B 完成后重算分位；若仍 &lt;30，再议 `min_bucket_samples=25` | 需人工批准 |

**仅 A**：不足以激活新分位。  
**A + B**：最符合「增量样本库、不改策略」原则。  
**A + B + C**：最后手段，须写清样本置信度 trade-off。

## 6. 实现计划（批准后开始）

### Phase 0 — 立项 ✅（本轮）

- [x] 模拟脚本 + 本文件
- [x] PG/离线双重复审计基线

### Phase 1 — 代码（统计层）

1. `context_stats.py` 增加 `MARKET_BUCKET_PROFILES["FUTURES"]` 或读 `context_market_calibration.json` 的 `bucket_profile` 字段
2. `build_bucket_key(row, strategy_id, market=...)` 按 market 选 profile
3. `rebuild_global_bucket_stats` / import 路径不变，仅 key 变化
4. 测试：`tests/test_context_stats_futures_profile.py`（snapshot 数不变、key 数下降、eligible 上升）

### Phase 2 — 样本回填（B 轨）

1. `batch_build_context_stats --market FUTURES --force-rebuild`（新 flag：覆盖已有 CSV）
2. 输出 `results/futures_context_backfill_audit/`：每品种 trades vs snapshots vs bad_audits
3. PG import + `report_futures_tier_eligibility.py` 复审计

### Phase 3 — 评审激活

1. eligible ≥ 30 后，跑 `calibrate_context_market_tiers.py --markets FUTURES`
2. 人工对比新旧 tier 对 Top 桶排序影响
3. 更新 `context_market_calibration.json` 与 `CHANGELOG.md`

## 7. 红线

- ❌ 为凑样本修改 OS / 九大定式 / 挂单 / 风控
- ❌ 把 Web tier 筛选结果反向写入定式参数
- ❌ 未经批准降低 `min_bucket_samples` 并激活生产阈值
- ❌ 删除或静默丢弃旧模拟持仓相关 audit 数据
- ✅ FUTURES 桶配置与 A_STOCK / CRYPTO **隔离**
- ✅ 保留 V1 bucket_key 字段或 migration 说明，便于历史 CSV 对账

## 8. 验收标准

| 阶段 | 通过条件 |
|------|----------|
| Phase 1 | 单测通过；FUTURES eligible ≥ 13（现有快照）；A_STOCK/CRYPTO 桶数不变 |
| Phase 2 | 快照数较 1410 显著增加；bad_audit 比例文档化 |
| Phase 3 | eligible ≥ 30；分位 out-of-sample 抽检 5 桶无异常 |

## 9. 命令备忘

```powershell
# 模拟各合并方案
python scripts/simulate_futures_bucket_merge.py --out-dir results/futures_bucket_merge_sim_20260616

# 现行审计
python scripts/report_futures_tier_eligibility.py --out-dir results/futures_tier_audit

# 离线覆盖度
python scripts/assess_futures_context_coverage.py --out-dir results/futures_tier_offline_20260616
```

### Phase 1+2 实施结果（2026-06-16）

| 指标 | V1 基线 | futures_v2 后 |
|------|---------|---------------|
| 桶数 | 342 | **81** |
| eligible (N≥30) | 4 | **16** |
| 快照 | 1410 | 1400（1d 可索引上限） |
| 状态 | INSUFFICIENT | 仍 INSUFFICIENT（需 ≥30 eligible） |

- **Phase 1**：`context_stats.py` + `bucket_profile=futures_v2` 已上线；CRYPTO/A_STOCK 不变
- **Phase 2+15m**：国内 15m 同步后 snapshots **9329** · eligible **59** · `READY_FOR_REVIEW` · 见 `docs/FUTURES_15M_SYNC.md`

## 10. 待用户确认

1. **是否批准 Phase 1**（FUTURES 专用 `futures_v2` 桶配置，统计层 only）？
2. **是否并行启动 Phase 2**（9823 成交 → context 回填审计）？
3. 若 A+B 后仍 &lt;30 eligible，**是否接受** `min_bucket_samples=25` 作为 C 轨备选（须单独签字）？

— 批准前 **不修改** `context_stats.py` 生产分桶逻辑。
