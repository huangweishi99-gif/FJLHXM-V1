# 方案 B · Phase 2 进度

更新：2026-07-03

## 已完成

| 项 | 结果 |
|----|------|
| 本地 Docker PG | TimescaleDB @5432 · Alembic 009 · **278 instruments** |
| W17 本地验收 | **7/7 + 5/5** |
| W17 国内远程 | SSH tunnel · **7/7 required** |
| 国内 API deploy | `-Verify` · health ok · PG @5432 · alembic 009 |
| 海外 pending monitor | 仓库 `state_lock` 版 · 测试 10 passed |
| 国内 futures pending | `state_lock` 已部署 |
| 运行态 | SF ack · HYPE #28 平仓 |

## 待办

| 项 | 说明 |
|----|------|
| **FUTURES 5m** | PR-A ✅ 泵已部署 · PR-B sync/ingest 待办 |
| 海外 pending CPU | 单轮 ~24s 持锁 · 待优化临界区 |
| stash@{0} | 按桶 cherry-pick |

## 命令速查

```powershell
docker compose up -d
python scripts/w17_remote_acceptance.py --auto-server
python scripts/w17_remote_acceptance.py --ssh-tunnel domestic-quant --local-port 8040 --wait-seconds 12
powershell -File scripts/sync_deploy_fengji_api.ps1 -Verify
python scripts/assess_instruments_vs_coverage.py
```
