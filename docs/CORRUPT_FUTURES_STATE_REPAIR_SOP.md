# 国内期货坏行情后模拟状态处理 SOP

更新时间：2026-06-04

本文用于处理国内期货 CSV 脏行、异常成交、异常平仓后，模拟账本和挂单监控状态是否需要修复的问题。本文只适用于模拟实盘状态，不适用于真实下单账户。

## 1. 处理原则

- 先修数据，再审计状态，最后才考虑修模拟账本。
- 任何状态修复前必须先有只读审计报告。
- 任何写状态动作前必须先 dry-run 生成 repair plan。
- 任何 apply 前必须有人工确认清单。
- 权益回滚不允许自动执行，必须单独人工审批。
- 不允许借坏行情修复修改峰极OS最高宪法、阵营转换、DS01-DS09 策略规则。
- 不允许删除历史记录；只能归档到 `audit_invalid_*`，保留证据链。

## 2. 标准流程

### 2.1 CSV 数据检查

```powershell
python scripts\repair_corrupt_futures_csv.py --data-dir data --symbols PP,BR
```

如果 dry-run 显示有坏行，确认后再执行：

```powershell
python scripts\repair_corrupt_futures_csv.py --data-dir data --symbols PP,BR --apply
```

### 2.2 模拟状态只读审计

```powershell
python scripts\audit_corrupt_futures_state.py --symbol PP --around "2026-05-29 01:00:00" --hours 12 --paper-state-file runtime\fengji_futures\state_futures_v2.json --monitor-state-file runtime\fengji_pending_orders\futures_pending_state.json --events-file runtime\fengji_pending_orders\events.jsonl --out runtime\logs\corrupt_futures_state_audit_PP_20260529.json
```

### 2.3 生成 repair dry-run plan

```powershell
python scripts\repair_corrupt_futures_state_from_audit.py --audit runtime\logs\corrupt_futures_state_audit_PP_20260529.json --state runtime\fengji_futures\state_futures_v2.json --monitor-state runtime\fengji_pending_orders\futures_pending_state.json --out runtime\logs\corrupt_futures_state_repair_plan_PP_20260529.json
```

### 2.4 生成人工确认清单

```powershell
python scripts\render_corrupt_futures_state_repair_checklist.py --plan runtime\logs\corrupt_futures_state_repair_plan_PP_20260529.json --out runtime\logs\corrupt_futures_state_repair_checklist_PP_20260529.md --title "PP Corrupt Futures State Repair Checklist"
```

## 3. 清单决策含义

| Decision | 含义 | 是否允许 apply |
|---|---|---|
| `NO_ACTION` | 没有目标、仓位、锁、失效平仓或权益候选 | 不允许 |
| `AUDIT_ONLY_NO_APPLY` | 只有已归档证据，没有可写残留 | 不允许 |
| `EQUITY_REVIEW_REQUIRED` | 没有 state/monitor 残留，但存在假盈亏候选 | 不允许；先单独审批权益 |
| `APPLY_REQUIRES_CONFIRMATION` | 有 open position 或 monitor 锁需要归档/释放 | 人工确认并备份后才允许 |
| `APPLIED_REVIEW_REQUIRED` | 已经执行过 apply | 必须复查备份、归档和日志 |

## 4. 允许 apply 的最低条件

只有同时满足以下条件，才允许执行 `--apply`：

- 审计 JSON 来自同一个品种和同一个坏行情时间窗口。
- repair plan 先以 dry-run 生成。
- 清单 decision 为 `APPLY_REQUIRES_CONFIRMATION`。
- `invalidated_positions > 0` 或 `released_monitor_locks > 0`，且每个目标 ID 都能追溯到 suspicious fill/close。
- state 和 monitor state 文件路径确认是目标运行态文件。
- 备份目录确认可写。
- 用户明确同意执行 apply。

执行模板：

```powershell
python scripts\repair_corrupt_futures_state_from_audit.py --audit runtime\logs\corrupt_futures_state_audit_SYMBOL_DATE.json --state runtime\fengji_futures\state_futures_v2.json --monitor-state runtime\fengji_pending_orders\futures_pending_state.json --backup-dir runtime\corrupt_state_repair_backup_DATE --out runtime\logs\corrupt_futures_state_repair_plan_SYMBOL_DATE_apply.json --apply
```

## 5. 权益回滚规则

`repair_corrupt_futures_state_from_audit.py` 只输出 `equity_rollback_candidates`，不自动改 `equity`。

权益回滚必须另走人工审批，至少确认：

- 假盈亏来自坏行情价格，而不是正常止损或滑点。
- 对应 trade/order 已经归档为 `audit_invalid_close` 或等价审计记录。
- 当前权益是否已经被其它修复脚本恢复。
- 回滚前后的权益数值可复算。
- 回滚操作必须有备份和变更记录。

## 6. PP 2026-05-29 案例结论

远端 PP 坏行情 repair 清单输出：

```text
Decision: EQUITY_REVIEW_REQUIRED
targets=3
invalidated_positions=0
released_monitor_locks=0
already_invalid_closes=1
equity_rollback_candidates=1
```

结论：

- 当前 PP 坏交易无残留 open position。
- 当前 PP 坏交易无残留 monitor 锁。
- 不需要执行 `--apply`。
- 只剩权益回滚候选；是否需要改权益必须单独审批。

## 7. 禁止事项

- 禁止跳过 audit 直接 repair。
- 禁止 dry-run 未看清就 `--apply`。
- 禁止自动改权益。
- 禁止删除历史 fill/close 记录。
- 禁止把坏行情处理脚本用于修改定式规则。
- 禁止在 SOP、日志、报告里写 API Key、Token、服务器密码、交易密钥或完整 webhook。
