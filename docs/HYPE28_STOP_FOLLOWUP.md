# HYPE #28 止损跟进（DS05 D1 long）

更新：2026-07-03 10:30 · **已平仓签收**

## 签收 ✅

| 字段 | 值 |
|------|-----|
| order_id | `HYPEUSDT-DS05-D1-long-d69873cc01ec9234` |
| exit_time | **2026-07-03 00:00:13** |
| exit_reason | **gap_stop** |
| exit_price | **64.654** |
| entry | 65.815 @ 2026-06-30 11:35:53 |
| net_pnl | **-7.70** |

monitor 在 **07-02 D1** 入库后于 07-03 00:00 判停（07-01 low 61.777 < stop），与此前 `STOP_PENDING_MONITOR_BAR` 预期一致。

## 当前 HYPE 持仓

已换为 **DS01 多**（另一笔）：

- order_id: `HYPEUSDT-DS01-D1-long-78434a5ee89f2e08`
- entry: 2026-07-03 02:20:46 @ 66.559
- current_stop: 65.11

## 复核命令

```powershell
python scripts/watch_hype28_stop.py --json
# → CLOSED_OR_MISSING（#28 已不在 open）

powershell -File scripts/sync_overseas_paper_state.ps1
python scripts/promote_overseas_1d_new10.py
```

## 数据

- 海外 D1 末根：**2026-07-02**（HYPE close 66.89）
- 本地已 sync paper_state + promote 1d（2026-07-03）
