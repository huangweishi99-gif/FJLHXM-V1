# 方案 B · B0-4 分桶 PR 交接

生成：2026-07-02 · **5 分支已推送** · 合并顺序见下

## PR 清单（base: `origin/main`）

| 序 | 桶 | 分支 | 创建 PR |
|----|-----|------|---------|
| 1 | B1 core | `pr/b1-fill-supervision-ds03` | https://github.com/huangweishi99-gif/FJLHXM-V1/compare/main...pr/b1-fill-supervision-ds03 |
| 2 | B3 ops | `pr/b3-ops-audit-scripts` | https://github.com/huangweishi99-gif/FJLHXM-V1/compare/main...pr/b3-ops-audit-scripts |
| 3 | B2 API | `pr/b2-phase0-openapi` | https://github.com/huangweishi99-gif/FJLHXM-V1/compare/main...pr/b2-phase0-openapi |
| 4 | B4 docs | `pr/b4-docs-phase0-handoff` | https://github.com/huangweishi99-gif/FJLHXM-V1/compare/main...pr/b4-docs-phase0-handoff |
| 5 | B6 pencil | `pr/b6-pencil-b03-design` | https://github.com/huangweishi99-gif/FJLHXM-V1/compare/main...pr/b6-pencil-b03-design |

**必须先合 B1**，再合 B3（`audit_paper_fills` 依赖 `fill_supervision` 模块）。

## 各 PR 要点

### B1 · fill_supervision（已补依赖 · `860ab26`）
- `resolve_ds03_entry_bar_index` 优先 `attack_bar_time`
- **同 PR 附带 import 依赖**：`ds01` · `data` · `ds03_pending_fill` · `runtime_stop_updater`
- 测试：`pytest tests/test_fill_supervision.py -q` → **26 passed**
- 本地 `integrate/b1-b3-smoke`（B1+B3 merge）已通过 import + pytest

## 在 GitHub 创建 PR（无 gh CLI 时）

对每个 compare 链接 → **Create pull request**，建议标题：

| 分支 | PR 标题 |
|------|---------|
| B1 | `fix(core): fill_supervision DS03 attack_bar_time + deps` |
| B3 | `feat(ops): overseas fill audit and ops round scripts` |
| B2 | `feat(phase0): OpenAPI snapshot and coverage reconcile` |
| B4 | `docs: Phase 0 handoff and B0-4 PR buckets` |
| B6 | `design: FJLHXM pen build scripts and B0-3 assess` |

Test plan 粘贴各 PR 要点中的 pytest / audit 结果。

### B3 · ops / audit
- `audit_exit_code`：`--fail-on-invalid` + `invalid_new=0` → exit **0**
- `run_overseas_fill_audit.ps1` PowerShell 调用修复
- 全量 audit（2026-07-02）：快照 **75/75** · valid=**12** · **invalid_new=0** · needs_data=**1** · exit **0**

### B2 · Phase 0 API
- OpenAPI **38 paths** · `assess_instruments_vs_coverage.py`（FUTURES 缺 5m 为已知缺口）

### B4 · 文档
- `PLAN_B_PHASE0_*` · `PLAN_EXECUTION_20260701` · `PLAN_B_B04_COMMIT_BUCKETS`

### B6 · Pencil 脚本
- `build/finalize/assess_fjlhxm_ui_pen_b03.py`（B0-3 文件级 + MCP 画布已验收）

## 合并后本地

```powershell
git fetch origin
git switch main
git pull origin main
# 或按序 cherry-pick 各 PR merge commit
```

## 未纳入 PR（B5 · 默认不提交）

- `data/**/*.csv` · `results/` · `runtime/*.json`
- `stash@{0}: b04-wip-all` 含 main 上大量 WIP，**勿整包 pop 进 PR**

## T0 待跟进（合 PR 前可并行）

- **HYPE #28**：D1 末根 **07-01**（low **61.777**）· 已 sync 24/24 · 仍待 **07-02 D1**
- **Phase 0**：PR 全合并后 `main` 恢复 ops / fill audit 一键脚本

引用：`docs/PLAN_B_B04_COMMIT_BUCKETS.md`
