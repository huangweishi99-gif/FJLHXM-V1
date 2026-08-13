# Shadow 观察期 · 6/30 复评

> 被动观察至 **2026-06-30**；**6/26 已做提前复评**，正式签字日仍为 **6/30**。  
> **6/26 复评包**：`results/shadow_observation_630_review_20260626/`  
> **6/25 预填包**：`results/shadow_observation_630_prep_20260625/`

## 当前裁定（6/26 用户确认 ✅）

| 项 | 结论 |
|----|------|
| `FENGJI_PAPER_MODE` | **维持 `shadow`** · 已签收 |
| 切流 | **不执行** |
| 签字 | `results/shadow_observation_630_review_20260626/USER_DECISION.md` |

6/30 当日可选复跑 `run_shadow_630_review.ps1` 做快照归档，**无需再裁定**除非触发条件变化。

**6/30 正式包**：`results/shadow_observation_630_review_20260630/` ✅

## 一键复评（6/30 当日）

```powershell
.\scripts\run_shadow_630_review.ps1
```

## 决策门

- [x] Shadow smoke `bad_audits` = 0
- [ ] standard/pro 真实用户 equity_gap 可解释
- [ ] PG 同桶 N≥30（非阻塞）
- [x] 双端 fill 72h exit=0
- [ ] 用户同意 per_user_execution
- [x] 回滚 `scoped_shared` 已文档化

## 切流 / 回滚（仅用户确认后）

```powershell
$env:FENGJI_PAPER_MODE = "per_user_execution"
$env:FENGJI_PAPER_MODE = "scoped_shared"   # 回滚
```

参考：`docs/V11_USER_PAPER_EXECUTION.md`

## 决策边界

- 同桶统计 / Web 回测 **不得** 反向修改峰极OS、定式或风控
- Shadow **不** 开启真实下单
- 切流仅 V1.1「我的模拟」视图，**不涉及** 服务器挂单/模拟盘主链路

## 运维基线

| 轮次 | 报告 |
|------|------|
| shadow630 | `results/ops_round_20260626_shadow630/` |
| r34 | `results/ops_round_20260626_r34/` |
