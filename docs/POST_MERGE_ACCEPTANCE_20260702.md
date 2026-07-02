# 方案 B · PR #1–#5 合并后验收

日期：2026-07-02  
基线：`main` @ `9c391ea`（含 PR #1–#5 merge commits）

## PR 合并状态

| PR | 分支 | 状态 |
|----|------|------|
| #1 | `pr/b1-fill-supervision-ds03` | ✅ merged |
| #2 | `pr/b3-ops-audit-scripts` | ✅ merged |
| #3 | `pr/b2-phase0-openapi` | ✅ merged |
| #4 | `pr/b4-docs-phase0-handoff` | ✅ merged |
| #5 | `pr/b6-pencil-b03-design` | ✅ merged |

## 合并后首轮发现（follow-up PR 修复）

| 症状 | 根因 | 修复 |
|------|------|------|
| `export_openapi_snapshot.py` → `ImportError: STRATEGY_DISPLAY_NAMES` | `constants.py` 缺展示名字典 | 补 `STRATEGY_DISPLAY_NAMES` |
| `audit_paper_fills` DS07 → `make_ds07_signal(..., df=)` TypeError | `ds07.py` 签名未含 `df` | 补可选参数 `df: pd.DataFrame \| None = None` |

分支：`pr/b1-followup-core-compat`

## 验收命令与结果

```powershell
python -m pytest tests/test_fill_supervision.py tests/test_core_post_merge_compat.py tests/test_validate_crypto_okx_180d_cache.py tests/test_report_new10_open_followup.py -q

python scripts/export_openapi_snapshot.py

powershell -File scripts/run_overseas_fill_audit.ps1 -FailOnInvalid

python scripts/watch_hype28_stop.py --json
```

## HYPE #28 跟进

- 状态：`STOP_PENDING_MONITOR_BAR`（exit 2）
- 07-01 D1 low **61.777** < stop **64.259**（`pending_eval_breach=true`）
- monitor 仍对齐 **06-30** 已完成 D1（`completed_only` 取倒数第二根）
- 待 **07-02 D1** 收盘入库后，monitor 切到 07-01 bar，预期触停

## 结论

- Phase 0 分桶 PR 已全部合入 `main`；follow-up 补丁补齐 core 兼容后 audit / OpenAPI 通过。
- `stash@{0}` 仍含大量 WIP，勿整包 pop。
