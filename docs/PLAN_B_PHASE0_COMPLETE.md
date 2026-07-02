# 方案 B · Phase 0 完成签收

日期：2026-07-02  
基线：`main` @ `c929b71`（PR #1–#6 全部 merged）

## Phase 0 任务签收

| ID | 任务 | 状态 | 证据 |
|----|------|------|------|
| B0-1 | OpenAPI 导出 | ✅ | `docs/api/openapi.json` · **38 paths** · `export_openapi_snapshot.py` |
| B0-2 | instruments vs coverage 对账 | 🔄 | CRYPTO/A股 ✅ · **FUTURES 缺 5m** · `assess_instruments_vs_coverage.py` |
| B0-3 | Pencil 9 屏验收 | ✅ | 文件级 + MCP 9/9 · `assess_fjlhxm_ui_pen_b03.py` |
| B0-4 | 分桶 PR | ✅ | PR #1–#5 merged |
| B0-6 | Pencil 生成脚本 | ✅ | `build/finalize_fjlhxm_ui_pen.py` |
| follow-up | core 兼容补丁 | ✅ | **PR #6** merged · `test_core_post_merge_compat.py` |

## 合并后验收（PR #6 后）

```powershell
python -m pytest tests/test_fill_supervision.py tests/test_core_post_merge_compat.py tests/test_stop_bar_monitor.py -q
# 38 passed

python scripts/export_openapi_snapshot.py
# openapi paths=38

powershell -File scripts/run_overseas_fill_audit.ps1 -FailOnInvalid
# invalid_new=0 · exit 0
```

详见 `docs/POST_MERGE_ACCEPTANCE_20260702.md`。

## T0 并行项（Phase 0 不阻塞）

| 项 | 状态 | 说明 |
|----|------|------|
| HYPE #28 | 🔄 | `STOP_PENDING_MONITOR_BAR` · 07-01 breach · 待 07-02 D1 · `docs/HYPE28_STOP_FOLLOWUP.md` |
| DS02/04 336h | 🔄 | 0 样本 · 诊断非阻塞 |
| stash@{0} | 待处理 | WIP 按桶 cherry-pick · 勿整包 pop |

## Phase 1 建议入口（下一迭代）

1. **B1-API**：`services/` 纳入版本库分桶 PR（当前本地 untracked）· OpenAPI CI smoke
2. **B1-Web**：Web 6 fail 测试分桶修（feature_gate / w17 remote）· 不混 core PR
3. **B1-Data**：FUTURES **5m** coverage 缺口 · `assess_instruments_vs_coverage.py` 跟踪
4. **T0**：HYPE #28 07-02 D1 触停签收 · ops r70+

## 引用

- `docs/PLAN_B_PHASE0_KICKOFF.md`
- `docs/PLAN_B_PR_MERGE_HANDOFF.md`
- `docs/PLAN_EXECUTION_20260701.md`
- `FJLHXM-V1.md`
