# 方案 B · Phase 2 进度

更新：2026-07-05

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
| **海外 hash** | `compare_overseas_core_hashes` 批量 SSH · **mismatches=0**（7/5） |

## 待办

| 项 | 说明 |
|----|------|
| **sync_deploy 桶** | `sync_deploy_domestic.ps1` cherry-pick · deploy manifest **1 passed** |
| stash@{0} 剩余 | 大量 data/ CSV · FJLHXM-UI · **勿整包 pop** |
| Phase 2 后续 | 按 `PLAN_B` 路线图继续 W18+ 或用户指定优先级 |

## 命令速查

```powershell
powershell -File scripts\deploy_domestic_ops_stash_bucket.ps1
powershell -File scripts\wait_pg_sc_15m_acceptance.ps1
powershell -File scripts\verify_project_buckets.ps1
docker compose up -d
python scripts/w17_remote_acceptance.py --auto-server
python scripts/w17_remote_acceptance.py --ssh-tunnel domestic-quant --local-port 8040 --wait-seconds 12
powershell -File scripts/sync_deploy_fengji_api.ps1 -Verify
python scripts/assess_instruments_vs_coverage.py
```
