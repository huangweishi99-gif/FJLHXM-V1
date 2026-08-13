# OI DS01 D1 止损周期只读审计

日期：2026-06-08

## 背景

2026-06-04 飞书推送：`菜油(OI) DS01 long` 平仓，通知写 `触发K线: 15m 2026-06-04 02:30:00`。DS01 为 D1 定式，15m 触价不应作为 DS01 止损依据。

## 2026-06-08 规则落地后裁定

| 定式 | 止损 K 线 | 是否允许 forming bar 触价 |
|------|-----------|---------------------------|
| DS01–DS06 | 上一根已完成 **1d** | 否 |
| DS07/DS08 | 上一根已完成 **1h** | 否 |
| DS09 | 最新 **15m** | 是（15m 定式） |

实现：`runtime_stop_updater.stop_bar_requires_completed_close()` + 国内/海外 pending monitor `read_stop_bar_for_position()`。

## 对 OI 案例的影响

1. **旧行为**：monitor 可能用 15m 实时价或最新 D1 行（含未收盘日 K）触价止损 → 06-04 02:30 的 15m 触价会误触发或通知口径错误。
2. **现行为**：
   - 止损判定只读 **已完成 D1** 的 high/low（`frame.iloc[-2]`，至少 2 根日 K 时）。
   - 06-04 02:30 的 **15m 触价不再触发 DS01 平仓**。
   - 飞书/事件应带 `exit_bar_timeframe=1d`（crypto 同步后同理）。

## 测试证据（本地）

- `tests/test_futures_pending_orders.py::test_ds01_position_not_closed_when_only_intraday_stop_crosses` — 仅 15m 触价，**不平仓**。
- `tests/test_futures_pending_orders.py::test_ds01_position_not_closed_by_forming_daily_bar` — forming D1 触价，**不平仓**；下一根 completed D1 才平。
- `tests/test_futures_pending_orders.py::test_ds01_position_closes_from_daily_stop_bar` — completed D1 触价，**平仓**且 `exit_bar_timeframe=1d`。

## 运行态

- 国内/海外 pending monitor 已同步 D1/H1 收盘确认逻辑并重启（2026-06-08）。
- **不重算** OI 历史平仓；该笔保留在 `closed_trades`，若需标记 `audit_invalid` 须单独审批（类似 BNB/PP 流程）。

## 结论

OI 2026-06-04 类问题在 **D1 收盘确认规则落地后已修复**；同类 DS01/DS03/DS05 不会再被 15m 或 forming D1 误止损。历史通知口径错误不自动改账。
