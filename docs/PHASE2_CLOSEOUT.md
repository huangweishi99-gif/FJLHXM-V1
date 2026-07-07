# 方案 B · Phase 2 收口（D0–D7）

更新时间：2026-07-07

Phase 2 N 日清单 **全部完成**。本文作为交接收口页；细节见 `docs/PLAN_B_PHASE2_PROGRESS.md` 与各 PR/验收脚本。

## N 日清单结果

| 日序 | 主题 | 关键产出 | 状态 |
|------|------|----------|------|
| D0 | os_engine/radar | PR #12 @ `4d6a840` · 海内外部署 | ✅ |
| D1 | OS 账本增量 | 国内 LC · 海外 BTC `INCREMENTAL_OK` | ✅ |
| D2 | pending plan/apply | PR #13 · 海内外 hash match | ✅ |
| D3 | W18 watchlist | PR #15 · 国内 4 users dry-run | ✅ |
| D4 | 定式案例回归 | `verify_d4_pattern_cases.py` · 飞书中文名 | ✅ |
| D5 | 数据/挂单口径 | 天勤仅环境变量 · 雷达/撤销文档 · `verify_d5` | ✅ |
| D6 | 覆盖边界 | H1≥500 门槛 · 期货夜盘表 · `verify_d6` | ✅ |
| D7 | stash 卫生 | 边界审计 · 残留 manifest · `verify_phase2_closeout` | ✅ |

## 一键验收

```powershell
python scripts\verify_phase2_closeout.py
powershell -File scripts\verify_project_buckets.ps1
python scripts\verify_d4_pattern_cases.py
python scripts\verify_d5_data_pending_policy.py
python scripts\verify_d6_market_coverage_boundaries.py
```

## stash@{0} 策略

- **411 文件** 仍在 `stash@{0}: b04-wip-all`。
- **332** 个为 `data/` CSV — 禁止 pop。
- **FJLHXM-UI** 设计稿 — 独立 Web 轨道，保留 stash。
- 核心代码桶已在 D0–D6 按 manifest cherry-pick 或 PR merge；见 `docs/STASH_BOUNDARY_AUDIT.md`。

## 剩余风险 / 后续（非 Phase 2 阻塞）

| 项 | 说明 |
|----|------|
| A股 60m 长历史 | 100/239 为 partial（&lt;500 根）；正式筛选临时仅 DS01–DS06 |
| A股独立数据泵 | `MARKET_MODE=astock` 未上生产 |
| stash 残留 | 按需 `git checkout 'stash@{0}' -- <file>`，禁止整包 pop |
| 网络 push | 本地 `main` 若领先 origin，需用户侧恢复 GitHub 443 后 push |

## 相关文档

- `docs/MARKET_COVERAGE_BOUNDARIES.md` — D6
- `docs/RADAR_REFRESH_SCHEDULE.md` · `docs/PENDING_ORDER_CANCEL_RULES.md` — D5
- `docs/STASH_BOUNDARY_AUDIT.md` — D7
- `TODO.md` — 长期待办（超出 Phase 2 清单）
