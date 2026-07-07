# 同品种多定式挂单撤销规则

更新时间：2026-07-07

## 适用范围

- 海外 crypto：`src/fengji_pending_order_monitor.py` → `cancel_conflicting_orders()`
- 国内期货：`src/fengji_futures_pending_order_monitor.py` 复用同一函数

触发时机：**某一挂单在本轮 `process_once` 内成交后**，对同品种其余未成交挂单做冲突撤销（`event_type=cancel`，`cancel_reason=conflict_after_fill`）。

## 判定维度

| 字段 | 说明 |
|---|---|
| `symbol` | 经 `normalize_symbol()` 后相同视为同品种 |
| `side` | `long` / `short` |
| `strategy_id` | 如 DS01、DS03、DS05 |

已成交单、已在 `cancelled_order_ids` 中的单、不同品种单 **不参与** 本轮冲突撤销。

## 规则表（成交单 = F）

设同品种待处理单为 O：

1. **反向单必撤**：`O.side != F.side` → 撤销 O。
2. **F 非 DS01**：同品种 **所有** 其余未成交单（含同向）→ 撤销 O。
3. **F 为 DS01**：
   - 同向且同为 DS01 → **保留** O；
   - 同向但 O 非 DS01 → 撤销 O；
   - 反向 → 见规则 1。

用代码表达（与实现一致）：

```text
should_cancel = (O.side != F.side)
if F.strategy != "DS01":
    should_cancel = True
elif O.strategy != "DS01":
    should_cancel = True
```

## 状态副作用

撤销时写入：

- `state.cancelled_order_ids`
- `state.cancelled_setup_keys`（若订单带 `setup_key`）

成交单写入 `filled_order_ids` / `filled_setup_keys` 后 **同一轮** 立即执行撤销，避免同周期内双开。

## 与 DS01 多笔入场的关系

`max_ds01_entries` 等限额在 **挂单生成/过滤** 阶段控制；本规则只在 **成交瞬间** 清理同品种冲突，不替代雷达侧的定式配额逻辑。

## 验证

```powershell
python -m pytest tests\test_pending_orders.py::test_pending_monitor_cancels_same_symbol_conflicts_in_same_cycle -q
python scripts\verify_d5_data_pending_policy.py
```

## 参考实现

`src/fengji_pending_order_monitor.py` 中 `cancel_conflicting_orders`（约 1049 行）。
