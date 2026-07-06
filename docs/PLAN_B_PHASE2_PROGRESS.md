# 方案 B · Phase 2 进度

更新：2026-07-06

## 已完成

| 项 | 结果 |
|----|------|
| 本地 Docker PG | TimescaleDB @5432 · Alembic 009 · **278 instruments** |
| W17 本地验收 | **7/7 + 5/5** |
| W17 国内远程 | SSH tunnel · **7/7 required** |
| 国内 API deploy | `-Verify` · health ok · PG @5432 · alembic 009 |
| 海外 pending monitor | 仓库 `state_lock` 版 · 测试 10 passed |
| 国内 futures pending | `state_lock` 已部署 |
| 运行态 | SF ack · HYPE #28 平仓 · SF watchdog 收口 |
| **FUTURES 5m** | 全量 sync **34** 品种 · B0-2 **pass** |
| **天勤 / data_manager** | `tqsdk` 优先 · 实际主力 · date≥2020 |
| **Phase 2 数据桶 manifest** | `fengji_phase2_data_manifest.txt` · verify **10 passed** · OpenAPI **38** |
| **运维/验收** | `verify_domestic_health.ps1` · `deploy_domestic_ops_stash_bucket.ps1` · ops manifest **1 passed** |
| **PG/SC 15m** | probe + data_manager 全链路 **PASS**（7/5 · 34/0 轮次） |
| **ensure_single** | 代码陈旧自动重启 · cmd+python dedupe 修复 |
| **海外 hash（核心雷达）** | `os_engine` / `fengji_total_radar` **match**（7/6） |
| **PR #11** | `feat/domestic-ops-pg-sc-sync` → `main` |
| **PR #12** | `feat/os-engine-radar-core` → `main` @ `4d6a840` · 海内外已部署 |

## 待办 / N 日清单（自 2026-07-06）

| 日序 | 说明 | 状态 |
|------|------|------|
| **D0** | PR #12 merge + 海内外 radar/pending 部署 | ✅ |
| **D1** | OS 账本增量：国内 LC delta=0 pl=192 · 海外 BTC `INCREMENTAL_OK` pl=1095 · 本地 BTC/LC ok | ✅ |
| **D2** | pending monitor 工作区改动 → 独立小 PR（勿混 data CSV） | 待做 |
| **D3** | W18 watchlist / 自定义品种 MVP（`docs/W18_*`） | 待做 |
| **D4** | DS01/DS03/DS05 争议案例沙盒回归 | 待做 |
| **D5** | 天勤账号环境变量复查 · 雷达频率/挂单撤销口径文档化 | 待做 |
| **D6** | A股 60m / 期货日夜盘覆盖边界标注 | 待做 |
| **D7** | stash@{0} 仅 cherry-pick · Phase2 收口 | 待做 |

stash@{0} 仍含大量 `data/` CSV 与 FJLHXM-UI · **勿整包 pop**。

完整条目见 `TODO.md`「方案 B · Phase 2 后续 · N 日清单」。

## 命令速查

```powershell
powershell -File scripts\deploy_domestic_ops_stash_bucket.ps1
powershell -File scripts\wait_pg_sc_15m_acceptance.ps1
powershell -File scripts\verify_project_buckets.ps1
powershell -File scripts\sync_deploy_domestic.ps1 -RestartRadarLoop -SkipPaperDeploy
powershell -File scripts\deploy_os_engine_radar_bucket.ps1 -OverseasOnly
python scripts/compare_overseas_core_hashes.py
docker compose up -d
python scripts/w17_remote_acceptance.py --auto-server
python scripts/w17_remote_acceptance.py --ssh-tunnel domestic-quant --local-port 8040 --wait-seconds 12
powershell -File scripts/sync_deploy_fengji_api.ps1 -Verify
python scripts/assess_instruments_vs_coverage.py
```
