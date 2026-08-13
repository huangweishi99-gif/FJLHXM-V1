# FJLHXM 主执行计划 v2（2026-06-09）

状态：`ACTIVE`（快照 2026-06-10：Wave 1–5 工程主线 ✅）  
依据：`FJLHXM-V1.md` §0.2、`峰极OS_最高宪法.md`、`TODO.md`  
维护：每完成一个 Wave 或变更优先级时更新本文 + `TODO.md` + `PROJECT_CONTEXT.md` + `CHANGELOG.md`

---

## 1. 北向目标（我们要做成什么）

峰极量化总工程在 **Web 产品化阶段** 的北向目标不是「把所有 CSV 再跑一遍」，而是建立三条可验收、可迭代的成熟链路：

| 轨道 | 目标 | 成功标准 |
|------|------|----------|
| **A · 正确性** | 雷达、回测、挂单、模拟盘对同一套 OS/定式口径 | 策略测试 + 沙盒图 + 成交后监督 invalid 可解释 |
| **B · 样本库** | 四市场历史成交 → 盈亏 + 开仓 K 线 + 三维 L0–L4 → `signal_tier` | 回测页可按品种/定式/桶查看强弱；**只读辅助**，不反改 OS/定式/挂单 |
| **C · 运行与产品化** | 本地一键、远端 API、watchdog、监督闭环 | 本地 `start_fengji_local.ps1` 可验收；远端 W17 待运维；M 线已跑首轮 audit |

**红线（全轨道适用）**：

- 不得为凑样本或 tier 修改峰极 OS、阵营转换、DS01–DS09 核心规则。
- `signal_tier` / 同桶统计只用于复盘、筛选、展示；模拟盘授权仍走雷达 + 挂单监控 + M 线复核。
- 模拟盘与真实实盘隔离；`audit_invalid` / 权益回滚须人工确认。

---

## 2. 成熟方案（数据→样本→判断，增量而非全量）

```
本地 K 线 CSV（A239 / F39 / C19 / US224）
        │
        ├─【缺 results/】──► 增量回测（C1）──► accepted_trades.csv
        │
        ├─【已有回测】────► context 批处理（C3）──► trade_context_snapshots + bucket_stats
        │                      ▲
        │                      │ L0–L4：OS 阵营/防守极、K 线形态、定式维、会话
        │
        ├─【OS/定式变更】──► 选择性重跑（C2）──► 仅受影响目录 + 重算 context
        │
        └─ PG 导入（C4）──► API / 回测页 trades · strength · 同桶样本
                                    │
                                    └── signal_tier（STRONG/MEDIUM/WEAK/INSUFFICIENT_DATA）

模拟盘 events.jsonl ──► M 线成交后监督（与 PG 样本库分离，不混用）
```

**是否需要「全部重新回测」？**

| 情况 | 动作 |
|------|------|
| 仅有新 K 线、无 `results/` | **增量回测**（C1），不动已有 ~137+ 目录 |
| 有回测、Web 缺 PG | **C3 + C4**，不必重跑回测 |
| S1 / OS 价格节奏 / 阵营规则变更 | **C2 选择性重跑** + context 重算 |
| 仅改 `context_market_calibration.json` | **只重算 context** |
| 模拟盘成交 | **M 线**，不进 PG 样本库 |

---

## 3. 任务难度分层（实施顺序依据）

| 难度 | 标签 | 典型耗时 | 依赖 | 任务 ID |
|------|------|----------|------|---------|
| ★☆☆☆ | **T1 轻量** | 分钟～2h | 脚本已有 | C0 缺口盘点、D5 PG smoke、D4 部分 HTTP smoke |
| ★★☆☆ | **T2 批处理** | 2h～1d | C0 清单 | C3 context、`--only-missing`、C4 PG 导入 |
| ★★★☆ | **T3 计算** | 1d～数天 | T2、回测引擎 | C1 增量回测、C2 DS01 选择性重跑 |
| ★★★★ | **T4 规则/人工** | 不定 | 用户/文档 | S2 沙盒指定品种、S3 DS02/06/08 裁定、M invalid 人工处置、C5 分市场校准 |
| ★★★★★ | **T5 阻塞/P2** | 外部或设计 | 运维/资产 | P1 远端 env+PG、P4 Pencil 画布、**O1 Lottie ✅**、C6 雷达 tier 只读展示 |

**原则**：同一 Wave 内先 T1 再 T2；**未通过 A 轨验收不扩大 C1 全市场回测**；P2 不抢占 B 轨。

---

## 4. 分 Wave 实施（按难易，一步步来）

### Wave 1 · 盘点与 smoke（T1）— ✅ 2026-06-09 完成

| ID | 任务 | 产出 | 状态 |
|----|------|------|------|
| C0 | 四市场 CSV × 回测目录 × PG 三方 diff | `results/coverage_gap_report.json` + `.md` | [x] |
| D5 | PG/API 四市场一致性复验 | **13/13** | [x] |
| D4a | 回测页 HTTP/API smoke | `scripts/smoke_w14_backtest_api.py` | [x] |
| M4 | invalid 成交人工确认清单 | 33 笔 → `results/fill_supervision_invalid_checklist_2026-06-09.md` | [x] |

**C0 结论**：仅 CSV 待回测 **463**（A215/F24/C2/US222）；完整链路 **58**；缺 context/PG **0**（已有回测目录均已 context+PG）。

```powershell
# Wave 1 已执行
python scripts/audit_coverage_gaps.py
python scripts/smoke_pg_api_consistency.py --sample-plan "A_STOCK=4,CRYPTO=3,FUTURES=3,US_STOCK=3"
python scripts/smoke_w14_backtest_api.py --port 8000
python scripts/render_fill_supervision_checklist.py
```

---

### Wave 2 · 样本库增量同步（T2）— ✅ 2026-06-09 完成

| ID | 任务 | 产出 | 状态 |
|----|------|------|------|
| C3 | `batch_build_context_stats --only-missing` 四市场 | 各目录 `trade_context_snapshots.csv` | [x] ok=0 |
| C4 | `batch_import_context_stats_to_pg.py` | PG snapshots/buckets 与 Web 对齐 | [x] 137 目录 |
| C7a | 写 `docs/CONTEXT_SAMPLE_LIBRARY_SOP.md` | 增量流程 + 验收 checklist | [x] |
| D4b | 回测页 Playwright 四市场搜索/加载 | smoke 截图 + 报告 | [x] 四市场 OK |

**D4b 修复**：`backtest.html` 等待 `initStrategies` 后再 `loadAll`；smoke 每市场独立 browser context。

---

### Wave 3 · 增量回测与规则刷新（T3）— ✅ 2026-06-12 目录收口（C5 部分待样本）

| ID | 任务 | 产出 | 状态 |
|----|------|------|------|
| C1-C | crypto 缺目录增量回测 | `run_crypto_c1_local.py` / OKX 白名单 | [x] IO+TAO；crypto 19/19 |
| C1-F | 期货缺目录品种增量回测 | `run_futures_c1_local.py` | [x] 19 品种；FUTURES 34/34 |
| C1-U | 美股缺目录增量回测 | `run_us_stock_c1_local.py` | [x] 224/224 完整 |
| C1-A | A股缺目录增量回测 | `batch_backtest_a_stock_fengji.py` | [x] 238/239 完整 |
| C2 | S1/OS 变更后 DS01 **选择性**重跑 | 对比 trades 数 ± 清单 | [x] 2026-06-12 四市场全量 + 影响面报告 |
| C5 | 分市场 tier 校准激活 | crypto/futures 样本 N≥30 后改 calibration | [x] A/C **active** · FUTURES 保留旧阈值（新分位 4/342 待样本） |

**Wave 3 目录收口（2026-06-12）**：CRYPTO 19/19 · FUTURES 34/34 · US 224/224 · A 238/239（688820 no_ctx 边界）· 双端 72h fill audit pass · AG/BR/EC 误标已归档。

---

### Wave 4 · 策略正确性收尾（T4）

| ID | 任务 | 产出 | 状态 |
|----|------|------|------|
| S1 | DS01 回测/雷达 OS 防守极一致 | `ds01_os_defense_missing()` | [x] 2026-06-09 |
| S2 | DS01 沙盒图复核（用户指定） | D1 图 + 雷达行对照 | [x] 批量 10/10 + 四市场深度复核 **000021/RB/沪金/BNB** 结案 |
| S3 | DS02/06/08 裁定与补齐 | 文档 + 测试 | [x] 2026-06-11 → `results/wave4_s3_ds020608_ruling_2026-06-11.md` |
| M1 | 成交后 DS01 监督 + watchdog | `fill_supervision` + SOP | [x] 2026-06-09 |
| M2 | DS03/DS08 成交后复核 | 扩展 `audit_fill_record` | [x] 2026-06-10 |
| M3 | 服务器首轮 fill audit | 双端 `*_remote_latest.json` | [x] 2026-06-09 |
| M5 | invalid 持仓/权益（人工批准后） | repair / equity rollback | [x] 2026-06-11 B 区 apply；equity 回滚仍须人工批准 |

---

### Wave 5 · 生产化与运营（T5 / P2）

| ID | 任务 | 产出 | 状态 |
|----|------|------|------|
| P1 | 远端 API（运维） | `fengji_api.env` + PG + W17 acceptance | [x] 2026-06-10 7/7 |
| P2 | W16-WS 断线重连稳定 | reconnect smoke 时序 | [x] 2026-06-11 |
| P3 | 订阅 Playwright 全路径 | login→pricing→payment | [x] 2026-06-11 |
| P4 | Pencil 9 屏画布验收 | MCP export + 对照 Web | [x] 2026-06-12 9/9 + 17/17 + 可选 4/4 |
| C6 | 雷达行只读 `signal_tier` | 展示 only，不改挂单 | [x] 2026-06-11 API+Admin |
| O1 | W15 Lottie 策略学堂示意动画 | `web/assets/lottie/` DS01–09+TOTAL | [x] **2026-06-10** · `build_strategy_lottie_illustrations.py` · 验收 **PASS**；可选设计精修 drop-in |
| O2 | 定式帮助链到 strategies | 文案/深链 | [x] 2026-06-11 |

---

## 5. 已完成基线（2026-06-05 ～ 2026-06-09）

| 领域 | 已完成 |
|------|--------|
| Web 核心 | W00/W08/W13/W14/W16/W17-demo、本地一键、用户验收 RB/监测/登录 |
| PG/API | W22–W24 smoke；context 引擎；137 目录 PG 导入 |
| 回测页 | D1/D2 品种目录 A239/F39/C19/US224；搜索 UI |
| OS/策略 | 价格节奏、RB 沙盒、S1 DS01 防守极、urgent_gap 集中 os_engine |
| 监督 | M1/M3 双端 fill audit（国内 32v/22i，海外 42v/11i） |
| Auth/WS | W17 本地 JWT、Feature Gate、WAdmin、W16-WS delta |

---

## 6. 当前进展快照（2026-06-10）

| 指标 | 数值 | 说明 |
|------|------|------|
| Web 可搜品种 | A239 / F39 / C19 / US224 | `chart_symbol_catalog.py` |
| 四市场完整链路 | C19 / F34 / US224 / A238 | C0 2026-06-12；A股 688820 no_ctx 已知边界 |
| PG context | 594 目录 / ~32 万 snapshots | C5 重校准 2026-06-12 |
| signal_tier 校准 | A/C **active** · FUTURES 旧阈值 active（新分位待样本） | C5 2026-06-14 CRYPTO 激活 |
| 模拟盘监督 | 双端 72h fill audit **pass** | M5 B 区 repair 已 apply |
| 远端 W17 | **7/7 + 可选 5/5** | PG 16 @5432 本地；15432 隧道已停 |
| O1 策略学堂动画 | **10/10 Lottie 示意 ✅** | `run_o1_lottie_placeholder_acceptance.py` PASS |

**当前阶段定位**：**Wave 1–5 工程主线 ✅** · **Wave 4 S2 四市场沙盒 ✅** · **C5 CRYPTO tier ✅**；剩余 **FUTURES 新分位（非阻塞）**、**O1 设计精修（可选）**、**真实支付 / 异步回测 Worker（V1.1+ 待立项）**。

```powershell
# O1 重建与验收
python scripts/build_strategy_lottie_illustrations.py
python scripts/run_o1_lottie_placeholder_acceptance.py

# 运维抽检
python scripts/audit_coverage_gaps.py
powershell -File scripts/run_w17_remote_acceptance.ps1 -FetchRemoteAdminToken
```

---

## 7. 验收口径

| 类型 | 最低标准 |
|------|----------|
| 策略改动 | `test_ds01` + `test_fengji_total_radar_ds01` + 受影响定式测试 |
| context/PG | C0 缺口报告 + `smoke_pg_api_consistency` 四市场 |
| Web | 相关 pytest + 硬刷新 spot check；D4b 截图存档 |
| 监督 | `test_fill_supervision`；invalid 必须有人工清单才可 repair |
| 样本 tier | 不得因 tier 修改 OS/定式；C6 若做雷达展示须单独评审 |

---

## 8. 模块索引（实现时勿重复造轮子）

| 能力 | 路径 |
|------|------|
| 品种目录 | `services/chart_symbol_catalog.py` |
| 回测发现 | `scripts/discover_backtest_results.py` |
| 批回测 | `src/batch_unified_whitelist_engine.py`、`src/batch_unified_crypto_whitelist.py` |
| context | `packages/fengji_core/fengji_core/context_snapshot.py`、`context_stats.py` |
| context 批处理 | `scripts/batch_build_context_stats.py` |
| PG 导入 | `scripts/batch_import_context_stats_to_pg.py` |
| 成交监督 | `fill_supervision.py`、`audit_paper_fills.py` |
| C0 缺口盘点 | `scripts/audit_coverage_gaps.py` |
| C1 本地 crypto | `scripts/run_crypto_c1_local.py` |
| C1 本地期货 | `scripts/run_futures_c1_local.py` |
| C1 本地美股 | `scripts/run_us_stock_c1_local.py` |
| D4a API smoke | `scripts/smoke_w14_backtest_api.py` |
| M4 invalid 清单 | `scripts/render_fill_supervision_checklist.py` |
| 本地一键 | `scripts/start_fengji_local.ps1` |
| O1 Lottie 生成 | `scripts/build_strategy_lottie_illustrations.py` |
| O1 验收 | `scripts/run_o1_lottie_placeholder_acceptance.py` |

---

## 9. 旧章节 ID 对照（避免文档分叉）

| 旧 ID | 新归属 |
|-------|--------|
| S* | Wave 4 |
| D1/D2 | 已完成基线 |
| D3 | 合并入 Wave 2 的 C3/C4 |
| D4/D5 | Wave 1 D4a / Wave 2 D4b + D5 |
| C0–C7 | Wave 1–3 / Wave 5 C6 |
| M* | Wave 4（M4/M5 新增） |
| P* / O* | Wave 5 |
