# 方案 B · Phase 0 切入评估

生成：2026-07-02 · 方案 A 主里程碑完成后

## 建议：**可启动 Phase 0 准备 · 不自动切产品流量**

方案 A 引擎侧（A3–A5）已收口；方案 B 指 `FJLHXM-V1.md` 产品化（Web/PG/OpenAPI/设计稿/订阅）。

| 前置 | 状态 | 说明 |
|------|------|------|
| A3 十币 180d | ✅ | bad_audits=0×10 |
| A4 SQLite | ✅ | crypto + futures + A股 239 |
| A4 回测 db | ✅ | `days` 窗口 + smoke |
| A5 监测 | ✅ | 30min + 缓存守卫 |
| 双端模拟盘 | ✅ | ops r63 · 海外 17/17 |
| Shadow | ✅ | **维持 shadow**（6/30 裁定） |

## Phase 0 工作包（建议顺序）

1. **设计冻结复核**：`docs/FJLHXM_UI_DESIGN_FREEZE.md` + `FJLHXM-UI.pen` 9 屏 · Pencil 画布待连 MCP 截图验收。
2. **OpenAPI 骨架**：回测/监测/品种列表只读端点 · 与现有 FastAPI 对齐，**不**改定式逻辑。
3. **PG 上下文**：延续 Wave 2–3 已有 bucket/context · crypto tier 17/30 inactive 单独排期（C5）。
4. **提交分桶**：Web/PG/docs 与 `packages/fengji_core` 策略改动 **分 PR**，避免 dirty 树一次提交。
5. **坏状态治理**：沿用 corrupt futures repair dry-run 流程 · 权益回滚仍须人工。

## 不建议现在做

- 把模拟盘 monitor 改为 **auto_trade**（仍 DISABLED）。
- 为 DS02/04 零样本 **改定式/OS**。
- 全量 Web E2E 在未分桶前跑 deploy 覆盖服务器密钥。

## 用户决策点

| 选项 | 含义 |
|------|------|
| **B0-a** | 启动 Phase 0 · 先做 OpenAPI + 设计验收（推荐） |
| **B0-b** | 延后 Phase 0 · 继续 T0 运维 + HYPE #28 / 国内定式 spot-check |
| **B0-c** | 并行：T0 每日 + Phase 0 每周 2 天 |

默认记录：**B0-b 直至用户确认**（Agent 不自动切 Shadow/standard 流量）。

## 引用

- `FJLHXM-V1.md` §0
- `docs/PLAN_A_ROADMAP.md` → 方案 B
- `docs/PLAN_EXECUTION_20260701.md`
