# 方案 B · Phase 2 进度

更新：2026-07-03

## 已完成

| 项 | 结果 |
|----|------|
| 本地 Docker PG | TimescaleDB @5432 · Alembic 009 · **278 instruments** |
| W17 全量验收 | **7/7 + 5/5** · `runtime/web_validation/w17_remote_acceptance.json` |
| 国内 API deploy | `sync_deploy_fengji_api.ps1 -Verify` · health **ok** · manifest 124 文件同步 |
| 海外 pending monitor | 仓库对齐服务器版（`state_lock` + 飞书 dedup）· `test_pending_orders` 10 passed |
| 运行态 | SF ack · HYPE #28 平仓 · pending monitor 重启 |

## 待办

| 项 | 说明 |
|----|------|
| FUTURES **5m** | SQLite 缺整周期 · `assess_instruments_vs_coverage.py` → `results/plan_b_b02_instruments_coverage/` |
| 国内 PG P2 | 服务器 alembic 告警（DATABASE_URL 待确认）· 见 `docs/W17_PROD_LOCAL_PG_2026-06-11.md` |
| pending CPU | 单轮 ~24s 持锁 · 待拆临界区或国内 `fengji_futures_pending_order_monitor` 同步 state_lock |
| stash@{0} | 按桶 cherry-pick |

## 命令速查

```powershell
docker compose up -d
python scripts/w17_remote_acceptance.py --auto-server
powershell -File scripts/sync_deploy_fengji_api.ps1 -Verify
python scripts/assess_instruments_vs_coverage.py
```
