# 挂单器手册（RUNBOOK_PENDING_ORDER）

状态：`ACTIVE`（2026-08-14 汇总成册）
范围：雷达 → 挂单生成 → 挂单监控触发 → 成交 → 冲突撤销 → 成交监督（五层防错链）→ 状态同步。
依据：`docs/PENDING_ORDER_CANCEL_RULES.md`、`docs/FILL_SUPERVISION_SOP_2026-06-09.md`、`docs/RADAR_REFRESH_SCHEDULE.md`、`docs/PAPER_STATE_SYNC.md` + `scripts/` 盘点。

---

## 1. 组件链路

```text
数据泵 → fengji_total_radar.py（生成 radar.csv/json）
       → fengji_radar_order_loop.py（循环刷新雷达 + 生成挂单）
       → fengji_pending_order_monitor.py（5s 轮询，触发成交）
       → cancel_conflicting_orders()（同品种冲突撤销）
       → fill_supervision（audit_paper_fills.py 复核成交）
       → paper_state sync（2min 同步 + 推送）
```

海外：`src/fengji_pending_order_monitor.py` / `src/fengji_pending_orders.py`
国内：`src/fengji_futures_pending_order_monitor.py`（复用同一撤销函数）

---

## 2. 运行周期（生产口径）

| 组件 | 海外 | 国内 |
|---|---|---|
| 雷达循环 `fengji_radar_order_loop.py` | **900s（15min）** | **600s（10min）** |
| 挂单监控 `fengji_pending_order_monitor.py` | **5s** | **5s**（动态止损每轮刷新） |
| 雷达单轮 | `fengji_total_radar.py` 持锁 `.radar_refresh.lock` 防并发 | 同左 |
| 停更告警 | `RADAR_STALE_SEC=2250`（海外 watchdog） | 国内 watchdog 每 30min 告警 |

配置位置：`scripts/watchdog_overseas.sh`、`scripts/restart_overseas_runtime.sh --loop-seconds 900`、`scripts/watchdog_domestic.ps1`、`scripts/restart_domestic_futures_runtime.ps1`。

注意：代码默认值仍为 300s；未走 watchdog 手工启动时需显式传参；遗留入口 `scripts/run_futures_radar_loop.cmd` 为 300s，若仍被计划任务引用应停用或对齐 600s。

---

## 3. 雷达与挂单文件

| 文件 | 生成方 | 用途 |
|---|---|---|
| `runtime/fengji_radar/radar.csv/json` | `fengji_total_radar.py` | 雷达信号（setup_key） |
| `runtime/fengji_pending_orders/pending_orders.csv/json` | `fengji_pending_orders.py` / loop | 挂单清单（order_id） |
| `runtime/fengji_pending_orders/state.json`（海外）/ `futures_pending_state.json`（国内） | monitor | 挂单状态 |
| `runtime/fengji_pending_orders/fills.csv` | monitor | 成交记录 |
| `runtime/fengji_pending_orders/events.jsonl` | monitor | 事件流（fill / cancel / audited） |
| `runtime/fengji_pending_orders/closed_trades.csv` | monitor | 已平仓交易 |

---

## 4. 同品种多定式冲突撤销规则（权威）

触发时机：**某一挂单在本轮 `process_once` 内成交后**，对同品种其余未成交挂单做冲突撤销（`event_type=cancel`，`cancel_reason=conflict_after_fill`）。

判定维度：`symbol`（经 `normalize_symbol()` 后相同）、`side`（long/short）、`strategy_id`（DS01/DS03/DS05…）。
已成交单、已在 `cancelled_order_ids` 中的单、不同品种单不参与本轮冲突撤销。

规则表（F = 本轮成交单，O = 同品种待处理单）：

| 情形 | 动作 |
|---|---|
| `O.side != F.side`（反向） | **必撤** O |
| F 非 DS01 | 同品种**所有**其余未成交单（含同向）撤销 |
| F 为 DS01 且 O 同向同为 DS01 | **保留** O |
| F 为 DS01 且 O 同向但非 DS01 | 撤销 O |

代码口径（与实现一致）：

```text
should_cancel = (O.side != F.side)
if F.strategy != "DS01":
    should_cancel = True
elif O.strategy != "DS01":
    should_cancel = True
```

状态副作用：撤销写入 `state.cancelled_order_ids`、`state.cancelled_setup_keys`（若带 `setup_key`）；成交单写入 `filled_order_ids`/`filled_setup_keys` 后**同一轮**立即撤销，避免同周期双开。
说明：`max_ds01_entries` 等限额在挂单生成/过滤阶段控制，本规则只做成交瞬间清理，不替代雷达侧定式配额。

验证：

```powershell
python -m pytest tests\test_pending_orders.py::test_pending_monitor_cancels_same_symbol_conflicts_in_same_cycle -q
python scripts\verify_d5_data_pending_policy.py
```

---

## 5. 成交监督 SOP（五层防错链）

核心模块：`packages/fengji_core/fengji_core/fill_supervision.py`
CLI：`scripts/audit_paper_fills.py`
事件源：`runtime/fengji_pending_orders/events.jsonl`
报告：`runtime/logs/fill_supervision/fill_supervision_{profile}_latest.json`
测试：`tests/test_fill_supervision.py`

手动审计：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"

# 国内：最近 7 天成交
python scripts/audit_paper_fills.py --profile domestic --since-hours 168

# 海外 crypto
python scripts/audit_paper_fills.py --profile overseas --since-hours 168

# 看护模式：有新 invalid 则 exit 2（供 watchdog / 计划任务）
# 已人工确认的 invalid 登记在 runtime/fill_supervision_acknowledged.json（--ack-file 可覆盖）
python scripts/audit_paper_fills.py --profile domestic --since-hours 72 --fail-on-invalid

# 可选：把复核结论追加回 events.jsonl（event_type=fill_audited）
python scripts/audit_paper_fills.py --profile domestic --since-hours 168 --append-events
```

复核项（DS01/DS03/DS08 主检查）：`signal_date`、`camp`、`left_count_calc` 等；报告字段：`verdict`（valid/invalid/needs-data/skipped）、`issues[]`、`checks`。
主力合约切换：持仓写入 `entry_data_contract`；持仓合约与当前主力不一致时**冻结自动止损**，平仓/权益修复需人工确认。

watchdog 接入：

- 国内：`scripts/watchdog_domestic.ps1` 每 30min `audit_paper_fills.py --profile domestic --since-hours 72 --fail-on-invalid --quiet`；exit 2 → 飞书告警（冷却 30min）。
- 海外：`scripts/watchdog_overseas.sh` 同样 30min。
- stamp：`runtime/watchdog/fill_supervision.last`；指纹：`runtime/watchdog/fill_supervision_invalid.fingerprint`（集合未变化不重复告警）。

invalid 处置 SOP（**不得自动改权益**）：

1. 保存当次 `fill_supervision_*_latest.json`。
2. `scripts/audit_corrupt_futures_state.py` 或人工核对 `paper_state` 对应持仓。
3. `scripts/render_corrupt_futures_state_repair_checklist.py` 生成 repair 清单。
4. 人工确认后才允许 `repair_corrupt_futures_state_from_audit.py --apply`。
5. **禁止**脚本自动改 `equity`；权益回滚单独审批。
6. 处置完成将该笔 `order_id` 登记进 `runtime/fill_supervision_acknowledged.json`（可用 `scripts/build_fill_supervision_ack.py` 重建），同步两台服务器。

可追溯字段链：

```text
radar setup_key → pending order_id → events.jsonl(fill) → fill_supervision JSON → [fill_audited] → paper_state audit_invalid_* / repair JSON
```

---

## 6. 状态同步（paper state）

- 计划任务 `FengJiPaperStateSyncAndPush`（每 2min）：同步 paper state + 推送到国内 API（现行唯一入口）。
- 安装/更新：

```powershell
powershell -File scripts\install_domestic_paper_state_sync_task.ps1
powershell -File scripts\install_overseas_paper_state_sync_task.ps1
```

---

## 7. 检查与审计命令

```powershell
# 挂单监控进程与挂单文件
powershell -File scripts\check_domestic_runtime_remote.ps1
powershell -File scripts\check_overseas_runtime_status.ps1

# 雷达 DS05 行筛选（国内）
powershell -File scripts\check_domestic_ds05_radar.ps1

# 成交审计（海外/国内）
powershell -File scripts\run_overseas_fill_audit.ps1
powershell -File scripts\run_domestic_fill_audit.ps1
powershell -File scripts\run_domestic_fill_audit_720.ps1     # 最近 30 天

# 新10 / DS09 成交观察（本机计划任务 15min）
powershell -File scripts\run_new10_fill_watch.ps1
powershell -File scripts\run_ds09_live_watch.ps1
```

---

## 8. 常见故障与排查

| 现象 | 排查 |
|---|---|
| 挂单不生成 | 雷达循环进程是否运行；`radar.csv/json` mtime 是否新鲜；`.radar_refresh.lock` 是否残留 |
| 挂单不触发 | 挂单监控进程；5s 轮询日志；现价是否触及触发价；动态止损是否误改 |
| 同品种双开 | 检查 events.jsonl 是否同一轮 fill + cancel 时序；核对 §4 撤销规则 |
| 成交异常（invalid） | `audit_paper_fills.py --fail-on-invalid`；按 §5 SOP 处置，禁止自动改权益 |
| 状态不同步 | `FengJiPaperStateSyncAndPush` 是否运行；推送 API 日志 |
| 告警风暴 | 检查 `fill_supervision_invalid.fingerprint` 是否已更新；冷却 30min 是否生效 |

---

## 9. 关联文档

- 撤销规则：`docs/PENDING_ORDER_CANCEL_RULES.md`
- 成交监督 SOP：`docs/FILL_SUPERVISION_SOP_2026-06-09.md`
- 刷新频率：`docs/RADAR_REFRESH_SCHEDULE.md`
- 状态同步：`docs/PAPER_STATE_SYNC.md`
- 服务器：`docs/RUNBOOK_SERVER.md`
- 数据管线：`docs/RUNBOOK_DATA_PIPELINE.md`
