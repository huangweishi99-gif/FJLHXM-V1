# 雷达 / 挂单刷新频率（工程口径）

更新时间：2026-07-07

说明：脚本 `--loop-seconds` **默认值**与 **生产 watchdog 实际参数** 可能不同；运维以 watchdog / restart 脚本为准。

## 海外 crypto（生产）

| 组件 | 生产周期 | 配置位置 |
|---|---|---|
| `fengji_radar_order_loop.py` | **900s（15min）** | `scripts/watchdog_overseas.sh` · `restart_overseas_runtime.sh` `--loop-seconds 900` |
| `fengji_pending_order_monitor.py` | **5s** | 同上 `--loop-seconds 5` |
| `data_manager.py`（crypto） | 按品种 K 线更新 | 海外 watchdog 每 10min 补 HYPE/ATH 15m |

代码默认：`fengji_radar_order_loop.py` 中 `--loop-seconds` 默认仍为 **300**；未走 watchdog 手工启动时需显式传参。

雷达单轮：`fengji_total_radar.py` → `pending_orders.csv/json`；持锁 `.radar_refresh.lock` 防并发。  
停更告警阈值：海外 watchdog `RADAR_STALE_SEC=2250`（约 2.5×900s）。

## 国内期货（生产）

| 组件 | 生产周期 | 配置位置 |
|---|---|---|
| `fengji_radar_order_loop.py` | **600s（10min）** | `scripts/watchdog_domestic.ps1` · `restart_domestic_futures_runtime.ps1` |
| `fengji_futures_pending_order_monitor.py` | **5s** | 同上；动态止损每轮刷新 |
| `data_manager_futures.py` | 日盘/夜盘时段内 **60s** 心跳 | 非交易时段暂停抓取 |

遗留入口 `scripts/run_futures_radar_loop.cmd` 仍为 **300s**；若仍被计划任务引用，应与 watchdog **600s** 对齐或停用，避免双实例参数不一致。

## 本机辅助任务

| 计划任务 | 周期 |
|---|---|
| `FengJiPaperStateSyncAndPush` | 2min |
| `FengJiNew10FillWatch` | 15min |
| `FengJiDs09LiveWatch` | 15min |
| `FengJiUserPaperExecutionJob` | 1min |

## 相关文档

- 同品种多定式成交后撤销：`docs/PENDING_ORDER_CANCEL_RULES.md`
- 天勤凭证：仅环境变量 `TQ_PHONE` / `TQ_PASS`（见 `data_manager_futures.require_tq_credentials`）

## 验证

```powershell
python scripts\verify_d5_data_pending_policy.py
# 海外雷达日志关键字：refresh done
# 国内：runtime\logs\futures_radar_order_loop.log
powershell -File scripts\check_domestic_tq_env.ps1
```
