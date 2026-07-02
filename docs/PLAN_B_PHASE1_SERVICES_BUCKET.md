# 方案 B · Phase 1 · services/API 分桶

生成：2026-07-02 · Phase 0（PR #1–#6）完成后

## 目标

将 `services/` 与 chart/context 依赖纳入版本库，使 OpenAPI、auth 与 chart_bundle 可在 CI/`main` 上复现，**不**混入定式/OS 逻辑变更。

## 分 PR 策略

| PR | 分支 | 状态 | 范围 |
|----|------|------|------|
| **#7 MVP** | `pr/b2-services-api-phase1` | ✅ merged | `services/` · migrations · alembic · docker-compose |
| **#8 chart** | `pr/b2-chart-bundle-deps` | 🔄 | chart_bundle · chart_line · symbol_names · context_* |
| **#9 ops** | `pr/b3-api-deploy-scripts` | 待办 | sync_deploy · W17 remote（脱敏） |
| **#10 web** | `pr/b2-web-tests` | 待办 | web/ · feature_gate_api / w17 |

**PR #8 开 PR**：https://github.com/huangweishi99-gif/FJLHXM-V1/compare/main...pr/b2-chart-bundle-deps

## Manifest 层级

| 文件 | 说明 |
|------|------|
| `fengji_api_phase1_manifest.txt` | PR #7 · services + migrations |
| `fengji_api_phase2_manifest.txt` | PR #8 · chart + context 增量 |
| `fengji_api_deploy_manifest.txt` | 全量 W17（随 #9 逐步绿） |

## PR #8 提交前检查

```powershell
python -m pytest tests/test_chart_line.py tests/test_chart_bundle.py tests/test_fengji_api_phase2_manifest.py tests/test_fengji_api_phase1_manifest.py -q
python scripts/export_openapi_snapshot.py
```

## 已知缺口

| 项 | 说明 |
|----|------|
| FUTURES **5m** | `assess_instruments_vs_coverage.py` |
| HYPE #28 | 待 07-02 D1 · `docs/HYPE28_STOP_FOLLOWUP.md` |
| 期货 chart 黄金测试 | 需 `runtime/fengji_os_state/{NI,AG,SC}_1d.json` · 无则 skip |

## 引用

- `docs/PLAN_B_PHASE0_COMPLETE.md`
- `docs/POST_MERGE_ACCEPTANCE_PR7_20260702.md`
