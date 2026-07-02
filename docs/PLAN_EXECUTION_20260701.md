# 峰极OS · 项目执行计划（2026-07-01 起）

状态：`ACTIVE`  
视角：方案 A 收官 + 模拟盘运维闭环  
整体完成度约 **65–72%**（见上轮评估）；本计划聚焦 **A3–A5 缺口** 与 **日常运维**。

---

## 三轨并行

| 轨道 | 目标 | 周期 | 验收 |
|------|------|------|------|
| **T0 运维** | 双端哈希、OPEN 跟进、pytest、数据新鲜度 | 每日/每轮 ops | `ops_round_*` 全绿 · pytest ≥102 |
| **T1 签收** | new10 / 国内期货 fill 材料闭环 | 有 fill 即出 | `USER_SIGNOFF.md` |
| **T2 方案 A** | A3→A4→A5 里程碑 | 2–4 周 | 见 `docs/PLAN_A_ROADMAP.md` |

方案 B（FJLHXM-V1 产品化）可在 **A3+A5 完成** 后评估 Phase 0；A4 A股/回测 db 切换为余量项。

---

## 阶段划分

### 阶段 1 · 运维与签收（本周，进行中）

| ID | 任务 | 负责 | 状态 |
|----|------|------|------|
| S1 | 运维 **r70+**：哈希 · promote 1d · 15m sync · OPEN 跟进 · pytest | 自动 | 🔄 |
| S0 | **方案 B Phase 0** PR #1–#6 + 签收 | 自动 | ✅ `docs/PLAN_B_PHASE0_COMPLETE.md` |
| S2 | **OP #29** CLOSE 签收（+5.05） | 用户 | ✅ 2026-07-01 |
| S3 | **#30–#34** 五笔 DS01 OPEN 签收 | 用户 | ✅ **5/5 VALID** 2026-07-01 |
| S4 | **HYPE #28** 07-02 复核 07-01 D1 stop | 自动+用户 | 🔄 stop 64.259 |
| S5 | 国内 **DS02/04** 336h 扫描（0 样本则出诊断） | 自动 | 🔄 |

### 阶段 2 · A3 十币 180d 回测 — ✅ 2026-07-01 完成

| ID | 任务 | 状态 |
|----|------|------|
| A3-0 | 数据盘点 | ✅ 10/10 |
| A3-2 | 九定式白名单 180d | ✅ **bad_audits=0×10** |
| A3-3 | 验收报告 | ✅ `results/plan_a_crypto_180d/A3_ACCEPTANCE.md` |

### 阶段 3 · A4 本地行情库 — ✅ 2026-07-02 完成

| ID | 任务 | 状态 |
|----|------|------|
| A4-1 | init + import-crypto-okx | ✅ **10/10** 三周期 |
| A4-2 | import-futures-local | ✅ **69** 品种 · 310k bars |
| A4-3 | A股 import-a-stock | ✅ **239** 1D · **235** 1H · 430k bars |
| A4-4 | 回测 `--data-source db` 默认化 | ✅ `market_data_resolve` + smoke · `days` 内存守卫 |

### 阶段 4 · A5 监测 7×24 — ✅ 2026-07-02（30min + 守卫）

| ID | 任务 | 状态 |
|----|------|------|
| A5-1 | `crypto_combined_monitor` + 计划任务 | ✅ **30min** · 跑前 `validate_crypto_okx_180d_cache.py` |
| A5-2 | 日志 | ✅ `runtime/logs/crypto_combined_monitor.log` |

### 阶段 5 · 国内定式覆盖（非阻塞）

| ID | 任务 | 说明 |
|----|------|------|
| D1 | DS02/04 雷达/挂单链路审计 | 336h 0 样本 → 扩扫描窗口或沙盒合成 |
| D2 | LC DS09 locks>0 时再补成交沙盒图 | `docs/LC_DS09_ACCEPTANCE.md` |

### 阶段 6 · Shadow / 产品（被动）

| 项 | 说明 |
|----|------|
| Shadow | **维持 shadow**（6/30 已裁定）· 待 standard/pro 用户规模 |
| W-Pay | 个体户后再开 Native |

---

## 每周节奏（建议）

| 日 | 动作 |
|----|------|
| 每日 | `run_ops_round_check.ps1 -RoundTag rNN` |
| 有 fill | `audit_new10_crypto_fills.py` + `USER_SIGNOFF.md` |
| 周一 | A3 进度 / bad_audits 汇总复查 |
| 周五 | 更新 `PROJECT_CONTEXT.md` · `TODO.md` · `CHANGELOG.md` |

---

## 本轮执行（2026-07-01）

1. ✅ 发布本计划 · 同步路线图与 TODO  
2. ✅ 运维 **r61** · pytest **102**  
3. ✅ **A3 验收** · 十币 **bad_audits=0**  
4. ✅ 签收 **#29 CLOSE** + **#30–#34 OPEN**（用户 2026-07-01）  
5. ✅ **A4 crypto** SQLite 导入 · 十币三周期  
6. ✅ **A5** 监测 cron · **A4** 期货 local 导入  
7. ✅ **A4 余量**：回测 db + 内存守卫 · **A5** 30min 监测  
8. ✅ **运维 r63** · HYPE #28 复核 · 方案 B Phase 0 评估材料  
9. 🔄 **用户决策**：HYPE #28 触停签收 · 方案 B B0-a/b/c

---

## 风险

- A3 全量回测耗时长（网络拉 OKX + 十币×九定式）；建议先单币 smoke 再批跑。  
- 国内 DS02/04 可能长期 0 样本，不阻塞 A3，但影响期货定式验收广度。  
- 用户签收项（S2/S3）需人工确认，Agent 只维护材料与索引。
