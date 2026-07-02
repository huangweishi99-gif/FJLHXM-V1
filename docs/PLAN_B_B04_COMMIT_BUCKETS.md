# 方案 B · B0-4 提交分桶计划

生成：2026-07-02 · 承接 `docs/W00_WORKTREE_BOUNDARY_AUDIT_2026-06-05.md`

目的：dirty 工作树按 **6 桶** 拆分 PR/提交，Phase 0 产品化不与 core 策略混提。

## 分桶定义

| 桶 ID | 名称 | 典型路径 | 默认 |
|-------|------|----------|------|
| **B1** | CORE_STRATEGY_OS | `packages/fengji_core/` · `src/fengji_*` · `src/overseas_paper_monitor.py` · `tests/test_os_engine.py` 等 | 单独 PR · 必跑 OS/定式 pytest |
| **B2** | WEB_PG_API | `web/` · `services/` · `migrations/` · `docs/api/` · `scripts/export_openapi_snapshot.py` | Phase 0 主 PR |
| **B3** | SERVER_OPS | `scripts/watchdog_*` · `scripts/sync_deploy_*` · `scripts/run_ops_*` · `data_manager*.py` | 脱敏后单独 PR |
| **B4** | DOCS_HANDOFF | `TODO.md` · `CHANGELOG.md` · `PROJECT_CONTEXT.md` · `docs/PLAN_*` · `AGENTS.md` | 可随 B2 或独立 docs PR |
| **B5** | DATA_RESULTS | `data/**/*.csv` · `results/` · `runtime/*.json` · `__pycache__` | **默认不提交** |
| **B6** | DESIGN_PEN | `FJLHXM-UI.pen` · `scripts/build_fjlhxm_ui_pen.py` | 改 Web 后同步 · B2 子 PR |

## 本轮已落地文件 → 建议桶

| 文件/目录 | 桶 | 说明 |
|-----------|-----|------|
| `fill_supervision.py` · DS03 attack_bar_time | **B1** | 已部署海外 · 需单独 core PR |
| `audit_paper_fills.py` · `audit_exit_code` | **B3** | 看护/审计脚本 |
| `run_overseas_fill_audit.ps1` | **B3** | 修复 `& $cmd[0]` 调用 |
| `assess_instruments_vs_coverage.py` | **B2** | B0-2 对账 · 随 API/docs |
| `docs/api/openapi.json` | **B2** | B0-1 |
| `build_overseas_audit_snapshot.ps1` | **B3** | 审计快照 |
| `watch_hype28_stop.py` · OPEN 跟进脚本 | **B3** | 运维工具 |

## 建议 PR 顺序（Phase 0）

1. **PR-core-fill-supervision**（B1）：DS03 复核修复 + 相关 tests
2. **PR-ops-audit-scripts**（B3）：audit exit · fill audit · snapshot · ops 加固
3. **PR-phase0-api-docs**（B2）：OpenAPI · B0-2 脚本 · instruments 文档
4. **PR-docs-handoff**（B4）：TODO/CHANGELOG/PLAN_B 系列
5. **PR-web-pencil**（B2+B6）：Web 改动 + `build_fjlhxm_ui_pen.py` 再生（B0-3 后）

## 禁止混入

- 密钥：`.env` · `runtime/*token*` · 完整 webhook
- 大 CSV：`data/a_stock/` · `data/crypto_okx/` · `data/market_data.sqlite`
- 运行态：`runtime/overseas_paper_state.json`（仅本地同步，不 commit）
- 策略混提：B2 PR 不得含 `os_engine.py` / DS01–09 逻辑变更

## 提交前检查

```powershell
# 桶内 pytest 基线（core）
python -m pytest tests\test_os_engine.py tests\test_fill_supervision.py tests\test_ds01.py -q

# Web/API smoke（B2）
python scripts\export_openapi_snapshot.py
python -m pytest tests\test_market_data_resolve.py -q

# 列出将提交文件（示例：B3）
git status --short scripts\audit_paper_fills.py scripts\run_overseas_fill_audit.ps1
```

## 验收

- [ ] 每个 PR < 30 个有意文件（不含自动生成 mass data）
- [ ] B1/B3 变更附 pytest 结果
- [ ] B2 附 OpenAPI path 数（当前 **38**）
- [ ] 无 B5 路径出现在 `git add`

引用：`docs/PLAN_B_PHASE0_KICKOFF.md` · `docs/W00_WORKTREE_BOUNDARY_AUDIT_2026-06-05.md`
