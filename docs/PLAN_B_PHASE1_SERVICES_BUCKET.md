# 方案 B · Phase 1 · services/API 分桶

生成：2026-07-02

## 分 PR 状态

| PR | 分支 | 状态 |
|----|------|------|
| **#7** | `pr/b2-services-api-phase1` | ✅ merged |
| **#8** | `pr/b2-chart-bundle-deps` | ✅ merged |
| **#9** | `pr/b3-api-deploy-scripts` | 🔄 待 merge |
| **#10** | `pr/b2-web-tests` | 待办 |

**PR #9 开 PR**：https://github.com/huangweishi99-gif/FJLHXM-V1/compare/main...pr/b3-api-deploy-scripts

## Manifest 层级

| 文件 | PR |
|------|-----|
| `fengji_api_phase1_manifest.txt` | #7 |
| `fengji_api_phase2_manifest.txt` | #8 |
| `fengji_api_phase3_manifest.txt` | #9 |
| `fengji_api_deploy_manifest.txt` | 全量（#9 后应全绿） |

## PR #9 验收

```powershell
python -m pytest tests/test_fengji_api_phase3_manifest.py tests/test_w17_remote_acceptance.py -q
# 6+ passed · auto_server 需本地 PG（无 PG 时 skip 或 auth 失败属预期）
```

## 引用

- `docs/POST_MERGE_ACCEPTANCE_PR7_20260702.md`
- `docs/POST_MERGE_ACCEPTANCE_PR8_20260702.md`
