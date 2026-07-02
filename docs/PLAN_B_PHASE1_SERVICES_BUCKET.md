# 方案 B · Phase 1 · services/API/Web 分桶

## 分 PR 状态

| PR | 状态 | 范围 |
|----|------|------|
| **#7–#9** | ✅ merged | services · chart · deploy |
| **#10** | 🔄 待 merge | `web/` · web tests · feature_gate_api 无 PG 修复 |

**PR #10 开 PR**：https://github.com/huangweishi99-gif/FJLHXM-V1/compare/main...pr/b2-web-phase1

## PR #10 验收

```powershell
python -m pytest tests/test_feature_gate_api.py tests/test_web_static.py tests/test_fengji_web_phase1_manifest.py tests/test_w17_subscription_browser_smoke.py tests/test_w15_strategy_animations.py -q
# 21 passed, 1 skipped
```

## Phase 1 完成标准（#10 merge 后）

- OpenAPI 38 paths · deploy manifest 全绿 · **web/** 入库
- W17 `web_index/login/strategies` 静态检查通过

## 引用

- `docs/POST_MERGE_ACCEPTANCE_PR9_20260702.md`
