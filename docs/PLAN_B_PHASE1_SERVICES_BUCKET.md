# 方案 B · Phase 1 · services/API 分桶

生成：2026-07-02 · Phase 0（PR #1–#6）完成后

## 目标

将本地 untracked 的 `services/` 纳入版本库，使 OpenAPI 导出与 auth/feature_gate 单测可在 CI/`main` 上复现，**不**在本 PR 混入定式/OS 逻辑变更。

## 分 PR 策略

| PR | 分支建议 | 范围 | 验收 |
|----|----------|------|------|
| **#7 MVP** | `pr/b2-services-api-phase1` | `services/` · `migrations/` · `alembic.ini` · `docker-compose.yml` · Phase1 manifest · auth 相关 tests | pytest phase1 · `export_openapi_snapshot.py` |

**开 PR**：https://github.com/huangweishi99-gif/FJLHXM-V1/compare/main...pr/b2-services-api-phase1
| **#8 chart** | `pr/b2-chart-bundle-deps` | `src/chart_bundle.py` · `chart_line.py` · `symbol_names.py` · context_* | manifest 全量 · chart smoke |
| **#9 ops** | `pr/b3-api-deploy-scripts` | `sync_deploy_fengji_api.ps1` · health · alembic upgrade · W17 remote（脱敏） | deploy manifest 全绿 |
| **#10 web** | `pr/b2-web-tests` | `web/` · feature_gate_api / w17 失败项 | 分桶修 6 fail |

**禁止**：`.env` · 真实 webhook/密钥 · `data/market_data.sqlite` · `runtime/*.json`

## Phase 1 manifest（PR #7）

见 `scripts/fengji_api_phase1_manifest.txt`（仅 services + DB 迁移 + 容器骨架）。

全量 W17 部署清单仍为 `scripts/fengji_api_deploy_manifest.txt`（119 项 · 随 #8/#9 逐步入库）。

## PR #7 提交前检查

```powershell
python -m pytest tests/test_auth_api.py tests/test_feature_gate.py tests/test_subscription_plan_catalog.py tests/test_fengji_api_phase1_manifest.py -q
python scripts/export_openapi_snapshot.py
python scripts/assess_instruments_vs_coverage.py   # FUTURES 5m 仍为已知 fail
```

## 已知缺口（不阻塞 #7）

| 项 | 说明 |
|----|------|
| FUTURES **5m** | `assess_instruments_vs_coverage.py` · Phase 1 数据 PR 单独排 |
| HYPE #28 | 待 07-02 D1 · `docs/HYPE28_STOP_FOLLOWUP.md` |
| chart_bundle | 依赖 `backtest_ds*` · 随 #8 |

## 引用

- `docs/PLAN_B_PHASE0_COMPLETE.md`
- `docs/PLAN_B_B04_COMMIT_BUCKETS.md`（B2 桶）
- `scripts/fengji_api_deploy_manifest.txt`
