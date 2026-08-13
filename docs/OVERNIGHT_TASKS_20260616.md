# 夜间任务包 · 2026-06-16

生成时间：2026-06-15 20:10（本地）

用户要求按序完成：FUTURES tier · DS09 BNB 沙盒 · 国内监测页 · V1.1 运维。

---

## 1. FUTURES tier（C5）

### 结论：**维持旧阈值，不可重校**

| 指标 | 值 |
|------|-----|
| PG snapshots | 1410 |
| buckets | 342 |
| eligible (N≥30) | **4/342** |
| 校准状态 | `INSUFFICIENT_MARKET_DATA` |
| 当前 tier 分布 | WEAK×4 · INSUFFICIENT_DATA×338 |
| C1 缺口 | **无**（34 品种均有回测目录） |
| context 缺口 | 仅 A股/CRYPTO 3 条 dry-run（非 FUTURES） |

**裁定**：与 CRYPTO 不同，FUTURES 瓶颈是 **L0–L4 桶碎片化**（306 桶 N<10），不是缺回测/PG。  
**生产配置不变**：`tier_medium=0.533186` · `tier_strong=0.7` · `activate=true`（见 `data/context_market_calibration.json`）。

### 产出

- `results/futures_tier_audit_20260616/futures_tier_audit.json`
- `results/futures_tier_audit_20260616/futures_tier_audit.md`
- `python scripts/calibrate_context_market_tiers.py` → FUTURES `eligible=4/342`

### 后续（非本轮）

- 若要 FUTURES 新分位激活：需 **eligible≥30**（更长历史回测或桶维度收敛），单独立项。

---

## 2. DS09 BNB 沙盒

### 结论：**回测有成交 · 当前窗口无 live boundary**

| 项 | BNBUSDT |
|----|---------|
| D1 camp | -1 / confirmed -1 |
| M15 窗口 | 2500 bars |
| boundary_sessions | 202 |
| lock / signal | 5 / 4 |
| backtest_trades | **4**（最近 2026-05-20 short） |
| 最近 lock 日 | 2026-05-20 |
| 当前 session（窗口末） | 2026-05-25 · **no_boundary** |

### 产出

- 成交级沙盒图：`results/crypto_ds09_sandbox_20260616/BNBUSDT_DS09_trade_20260611.png`
- 会话图：`BNBUSDT_DS09_session_2026-05-20_lock.png`
- 报告：`results/crypto_ds09_sandbox_20260616/crypto_ds09_sandbox_report.md`

### 代码修复

- `run_crypto_ds09_sandbox_review.py` 增加 `crypto_okx/` 15m/1d 回退路径（修复 `missing_csv`）。

### 待观察

- radar 出现 DS09 live 行时复跑：`plot_ds09_sandbox.py --crypto ...`

---

## 3. 国内监测页

### 结论：**API + 静态页正常**

| 检查 | 结果 |
|------|------|
| W17 远端验收 | **required 6/6** · optional 4/5 |
| `GET /api/v1/health` | 200 ok |
| `GET /api/v1/monitor/domestic/latest-opens` | 200 · source=paper_state · **7 持仓** |
| `GET /web/monitor.html` | 200 |
| Auth / Feature gate | 通过 |
| Admin overview（无 token） | 401（预期） |

报告：`runtime/web_validation/w17_remote_acceptance.json`

**注意**：本机连续打 monitor API 会 **429**（polling gate）；验收应单请求或走 SSH 远端 localhost。

---

## 4. V1.1 运维

### 结论：**paper state 全链路 OK**

```
sync_and_push_paper_state_for_web.ps1 -Verify
→ domestic 226047 bytes / 19 仓
→ overseas 349869 bytes / 5 仓
→ DOMESTIC_API_PAPER_STATE_FILES_OK
→ SYNC_AND_PUSH_PAPER_STATE_OK
```

**非阻塞告警**：海外 pending CSV sync `too small`（与上轮相同）。

**未做**：完整独立 per-user radar→paper 撮合（仍待立项）。

---

## 复现命令

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
$env:PYTHONPATH="src;packages/fengji_core;services;scripts"

# 1 FUTURES tier
python scripts/report_futures_tier_eligibility.py --check-csv-stale --out-dir results/futures_tier_audit_20260616
python scripts/calibrate_context_market_tiers.py

# 2 DS09 BNB
python scripts/run_crypto_ds09_sandbox_review.py --symbols BNBUSDT --out-dir results/crypto_ds09_sandbox_20260616 --daily-tail 450 --m15-tail 2500
python src/plot_ds09_sandbox.py --crypto --d1-csv data/1d/BNBUSDT.csv --m15-csv data/crypto_okx/BNB-USDT_15m_180d.csv --symbol BNBUSDT --trade-no 1 --out results/crypto_ds09_sandbox_20260616/BNBUSDT_DS09_trade_20260611.png --d1-tail 450 --m15-tail 2500

# 3 国内监测
python scripts/w17_remote_acceptance.py --ssh-tunnel domestic-quant --local-port 8040 --no-ws

# 4 V1.1 paper
powershell -File scripts/sync_and_push_paper_state_for_web.ps1 -Verify
```
