# HYPE #28 止损跟进（DS05 D1 long）

更新：2026-07-02 16:54（paper_state sync + promote 1d）

## 数据同步

- `sync_overseas_paper_state.ps1`：✅ 2026-07-02
- `promote_overseas_1d_new10.py`：HYPE 等 10 品种已 promote
- 本地 D1 末根：**2026-07-01**（close 63.533，low 61.777 不变）

## 持仓

| 字段 | 值 |
|------|-----|
| order_id | `HYPEUSDT-DS05-D1-long-d69873cc01ec9234` |
| entry_time | 2026-06-30 11:35:53 |
| entry_price | 65.815 |
| current_stop | 64.259 |

## 当前状态

`watch_hype28_stop.py --json` → **`STOP_PENDING_MONITOR_BAR`**（exit 2）

- **monitor_bar**：2026-06-30 D1（`completed_only` 取已完成 bar，low 62.441 ≥ stop）
- **pending_eval_bar**：2026-07-01 D1（low **61.777** < stop **64.259** → `pending_eval_breach=true`）
- 本地 `data/1d/HYPEUSDT.csv` 末根：**2026-07-01**

## 预期触停时机

monitor 在 D1 上只判**已完成** K 线。07-01 bar 已 breach，但 monitor 仍停在 06-30，需等 **07-02 D1 收盘入库** 后 monitor 切到 07-01，预期变为 **`STOP_TRIGGERED_MONITOR`**（exit 3）。

## 复核命令

```powershell
python scripts/watch_hype28_stop.py --json
Get-Content data/1d/HYPEUSDT.csv -Tail 3
powershell -File scripts/sync_overseas_paper_state.ps1
python scripts/promote_overseas_1d_new10.py
```

## 签收

- [ ] 07-02 D1 入库后 monitor 触停
- [ ] paper_state 中 HYPE 持仓已平仓且 exit 价合理
