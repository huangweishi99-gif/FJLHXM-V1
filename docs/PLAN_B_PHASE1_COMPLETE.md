# 方案 B · Phase 1 完成签收

日期：2026-07-02  
基线：`main` @ `2ead68e`（PR #7–#10 全部 merged）

## PR 签收表

| PR | 内容 | 状态 |
|----|------|------|
| #7 | services · migrations · alembic · docker-compose | ✅ |
| #8 | chart_bundle · chart_line · context · symbol_names | ✅ |
| #9 | sync_deploy · paper-state · W17 remote/smoke | ✅ |
| #10 | web/ · feature_gate_api · 静态页测试 | ✅ |

Phase 0（PR #1–#6）已于此前签收，见 `docs/PLAN_B_PHASE0_COMPLETE.md`。

## 合并后验收（PR #10 后）

```powershell
python -m pytest tests/test_fengji_api_phase1_manifest.py tests/test_fengji_api_phase2_manifest.py tests/test_fengji_api_phase3_manifest.py tests/test_fengji_web_phase1_manifest.py tests/test_feature_gate_api.py tests/test_web_static.py -q
# 18 passed

python scripts/export_openapi_snapshot.py
# openapi paths=38

python scripts/w17_remote_acceptance.py --preflight-only
# ok=true · deploy manifest + sync_deploy 存在
```

详见 `docs/POST_MERGE_ACCEPTANCE_PR10_20260702.md`。

## 工程能力（Phase 1 后）

| 能力 | 证据 |
|------|------|
| FastAPI + OpenAPI | `services/api/main.py` · **38 paths** |
| DB 迁移 | `migrations/versions/001–009` |
| Chart bundle | `src/chart_bundle.py` · `test_chart_line` |
| Web 静态页 | `web/` · `test_web_static` |
| W17 部署 | `sync_deploy_fengji_api.ps1` · 全量 manifest 文件齐 |
| fill audit | `run_overseas_fill_audit.ps1 -FailOnInvalid`（此前 invalid_new=0） |

## T0 并行（不阻塞 Phase 1 签收）

| 项 | 状态 |
|----|------|
| HYPE #28 | 🔄 `STOP_PENDING_MONITOR_BAR` · 待 07-02 D1 |
| FUTURES 5m 缺口 | 🔄 `assess_instruments_vs_coverage.py` |
| stash@{0} | 按桶 cherry-pick · 勿整包 pop |

## Phase 2 建议入口

1. **本地 PG + W17 全量 acceptance**（`w17_remote_acceptance.py --auto-server`，需 PG）
2. **国内 deploy 试跑**：`sync_deploy_fengji_api.ps1 -Verify`（SSH 已配置时）
3. **Pencil / Web 画布**：B0-3 已验收 · 后续改 Web 须同步 `FJLHXM-UI.pen`
4. **FUTURES 5m 数据 PR**（独立 data 桶，不混 core）

## 引用

- `docs/PLAN_B_PHASE1_SERVICES_BUCKET.md`
- `docs/PLAN_EXECUTION_20260701.md`
- `FJLHXM-V1.md`
