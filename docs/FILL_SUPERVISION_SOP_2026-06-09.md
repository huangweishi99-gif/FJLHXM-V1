# 成交后开仓监督 SOP（2026-06-09）

状态：`ACTIVE`  
目标：模拟盘/挂单监控**成交后**自动复核是否符合定式开仓逻辑，形成**防错 + 可追溯**闭环，使峰极量化运行越来越稳定。

---

## 1. 设计原则

1. **不反向改策略**：监督只读复核，不得因 audit 结果自动修改 OS、定式或风控参数。
2. **模拟与实盘隔离**：本 SOP 仅覆盖模拟账本、挂单监控、`events.jsonl`；真实下单须人工确认，不在此自动处理。
3. **先标记、后处置**：发现 invalid 成交时，先写审计报告与 `fill_audited` 事件；权益回滚、`audit_invalid` 归档须走既有 repair SOP 并**人工确认**。
4. **阵营授权口径**：DS01 以**信号棍（入场上一根 D1）** 的 OS 阵营与 `active_*` 为准，与雷达 `add_ds01()` 一致，不用入场 K 当日新确认的防守极 retroactive 授权。

---

## 2. 五层防错链

| 层级 | 机制 | 作用 |
|------|------|------|
| L1 雷达预检 | `BLOCKED_OS_INCOMPLETE` / `BLOCKED_LEFT_LINES` / DS01 禁止 `TRIGGERED` 补挂单 | 成交前挡掉明显不合规 setup |
| L2 挂单监控 | `can_open_position`、同 setup 去重、DS01 禁止事后补成交 | 成交瞬间风控与重复防护 |
| L3 **成交后复核（本 SOP）** | `scripts/audit_paper_fills.py` + `fengji_core.fill_supervision` | 用 D1+OS 重算 DS01 是否 valid |
| L4 进程看护 | `watchdog_domestic.ps1` / `watchdog_overseas.sh` 定时跑 L3 | 无人值守时发现漏网 invalid |
| L5 账本 repair | `audit_corrupt_futures_state.py` + repair 清单 + 人工 `--apply` | 污染持仓/锁/权益的受控清理 |

---

## 3. DS01 / DS03 / DS08 复核项（当前已实现）

### DS01

对每笔 `event_type=fill` 且 `strategy_id=DS01` 的记录：

1. **信号棍阵营**：上一根 D1 `camp` 与方向一致（多=红营 1，空=蓝营 -1）。
2. **OS 防守极**：红营须有 `active_low`，蓝营须有 `active_high`（`ds01_os_defense_missing`）。
3. **信号棍阴阳**：多=阳棍，空=阴棍。
4. **入场触发**：入场 K 的 OHLC 是否满足 `entry_fill`（突破信号棍高/低）。
5. **左 30 线段**：首仓 `left_count ≤ 2`（续棍 `is_add` 跳过左 30 硬约束）。
6. **挂单价一致**：`trigger_price` / `stop_price` / `left_count` 与 OS 重算值在容差内一致（**首仓**）；**续棍** pending fill 以 order `trigger_price` / setup_key `trigger=` 为准，不与旧信号棍 calc 强行对齐。

### DS03（D1）

1. **入场日阵营**：入场 K `camp` 与方向一致（多=红营 1，空=蓝营 -1）。
2. **二四棒 attack**：`resolve_ds03_attack` 在入场 K 非空，且 `entry_ref` 与 `trigger_price` 容差一致。

### DS08（H1，按 fill `timeframe` 加载）

1. **setup bar**：以 fill 记录 `latest_time`（雷达挂单刷新时刻）映射 H1 bar，**不是** fill 时刻 bar。
2. **K 线窗口**：与雷达一致 tail=2400（`apply_radar_ohlcv_tail`），避免 setup_key 索引与全量 CSV 错位。
3. **结构核对**：setup bar 上 last-5 硬化点角色（多=VPVPV / 空=PVPVP）+ attack 价与 `setup_key` trigger 容差一致；`setup_key` 内 bar index 若与 tail 滚动不一致仅记 `setup_key_idx_stale`，不以索引 alone 判 invalid。
4. **挂单成交**：`pending_price_fill_ok` 核对 fill_price vs trigger；不要求 fill 时刻 `make_ds08_signal` 仍触发（PENDING→成交常见）。

### 国内期货主力合约切换

1. 新挂单写入 `data_contract`，且 `order_id` 包含合约身份；同一 setup 在换月后会生成新的订单身份。
2. pending monitor 每轮读取 `futures_main_contract_sources.json`；订单合约与当前数据合约不一致时，写入 `event_type=cancel`、`cancel_reason=main_contract_switched`，不得使用新合约 K 线成交旧合约挂单。
3. 旧版无 `data_contract` 的订单，若 `created_at <= contract_switched_at <= observed_at`，按 `previous_data_contract` 识别为旧合约订单并撤销。
4. 已发生的跨合约模拟成交归类为 `exec_gap`，不计入策略 `invalid_new`；报告保留旧合约、当前合约和切换时间。
5. 持仓记录写入 `entry_data_contract`。持仓合约与当前主力不一致时冻结自动止损处理，避免新合约价格直接平掉旧合约持仓；平仓或权益修复仍需人工确认。

其余定式（DS05 等）仍标记 `skipped`。

---

## 4. 工具与路径

| 组件 | 路径 |
|------|------|
| 核心模块 | `packages/fengji_core/fengji_core/fill_supervision.py` |
| CLI 审计 | `scripts/audit_paper_fills.py` |
| 成交事件源 | `runtime/fengji_pending_orders/events.jsonl` |
| JSON 报告 | `runtime/logs/fill_supervision/fill_supervision_{profile}_latest.json` |
| 单元测试 | `tests/test_fill_supervision.py` |

### 本地 / 服务器手动跑

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"

# 国内：最近 7 天成交
python scripts/audit_paper_fills.py --profile domestic --since-hours 168

# 海外 crypto
python scripts/audit_paper_fills.py --profile overseas --since-hours 168

# 看护模式：有【新 invalid】则 exit 2（供 watchdog / 计划任务）
# 已人工确认的 invalid 登记在 runtime/fill_supervision_acknowledged.json（--ack-file 可覆盖），不再重复告警
python scripts/audit_paper_fills.py --profile domestic --since-hours 72 --fail-on-invalid

# 可选：把复核结论追加回 events.jsonl（event_type=fill_audited）
python scripts/audit_paper_fills.py --profile domestic --since-hours 168 --append-events
```

---

## 5. 可追溯字段链

每笔成交建议能串起以下 ID：

```
radar setup_key
  → pending order_id
    → events.jsonl (event_type=fill)
      → fill_supervision JSON (order_id / setup_key / issues)
        → [可选] events.jsonl (event_type=fill_audited)
          → paper_state audit_invalid_* / repair JSON
```

报告 JSON 字段：`verdict`（valid/invalid/needs-data/skipped）、`issues[]`、`checks`（signal_date、camp、left_count_calc 等）。

---

## 6. invalid 处置 SOP（不得自动改权益）

1. 保存当次 `fill_supervision_*_latest.json`。
2. 用 `scripts/audit_corrupt_futures_state.py` 或人工核对 `paper_state` 对应持仓。
3. 生成 repair 清单：`scripts/render_corrupt_futures_state_repair_checklist.py`。
4. 人工确认后，才允许 `repair_corrupt_futures_state_from_audit.py --apply`。
5. **禁止**脚本自动改 `equity`；权益回滚单独审批（参见 CHANGELOG BNB 案）。
6. 处置完成后，将该笔 `order_id` 登记进 `runtime/fill_supervision_acknowledged.json`（可用 `scripts/build_fill_supervision_ack.py` 从 M4 清单重建），并同步两台服务器；watchdog 此后只对**新 invalid** 告警。

---

## 7. Watchdog 接入

- **国内**：`scripts/watchdog_domestic.ps1` 每 30 分钟调用一次 `audit_paper_fills.py --profile domestic --since-hours 72 --fail-on-invalid --quiet`；若 exit 2 则飞书告警（冷却 30min）。
- **海外**：`scripts/watchdog_overseas.sh` 同样每 30 分钟 `--profile overseas`。
- 国内 `fill_supervision_invalid` 使用新 INVALID order_id 集合指纹去重；集合未变化时只写 watchdog 日志，不重复发送飞书。新增或减少 INVALID 后更新指纹。

stamp 文件：`runtime/watchdog/fill_supervision.last`
指纹文件：`runtime/watchdog/fill_supervision_invalid.fingerprint`

---

## 8. 验证基线

```powershell
python -m pytest tests/test_fill_supervision.py tests/test_ds01.py -q
python scripts/audit_paper_fills.py --profile domestic --since-hours 0 --quiet
```

---

## 9. 后续扩展（backlog）

- DS05 等成交后复核接入 `fill_supervision.audit_fill_record`
- 成交当下在 monitor 内同步写 `fill_audited`（减少 watchdog 延迟）
- 与 `context_stats` / PG 回测页联动，仅展示 invalid 标记，不反改策略
