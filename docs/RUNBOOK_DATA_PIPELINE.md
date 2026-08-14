# 数据管线手册（RUNBOOK_DATA_PIPELINE）

状态：`ACTIVE`（2026-08-14 汇总成册）
范围：国内期货数据泵、海外 crypto 数据泵、A股缓存、本地行情数据库、同步任务、覆盖边界。
约定：不写数据源账号密码、API Key；凭证只经环境变量或本地私密配置提供。

---

## 1. 数据源总览

| 链路 | 主程序 | 数据源 | 周期 | 运行地 | 落盘 |
|---|---|---|---|---|---|
| 海外 crypto | `data_manager.py` | Binance（补 HYPE/ATH 用 OKX） | 1d / 1h / 15m | 海外服务器 | `data/{1d,1h,15m}/` |
| 国内期货 | `data_manager_futures.py` | 天勤（`TQ_PHONE`/`TQ_PASS` 环境变量） | 期货日盘/夜盘窗口、心跳 60s | 国内服务器 | `data/futures/{1d,15m,5m}/` |
| A股缓存 | `src/market_data_store.py` / 回测脚本 | 东方财富 / 新浪（按需抓取） | 1d / 60m（无 15m） | 本地/国内 | `data/a_stock/` |
| 本地行情库 | `src/market_data_store.py` | 汇总以上 | — | 本机 | `data/market_data.sqlite` |

---

## 2. 海外 crypto 数据泵（Binance）

- 主程序：`data_manager.py`。
- 周期：`1d`、`1h`、`15m`；每轮同步结束后默认 sleep 600s。
- 日志：`data_sync.log`。
- 数据目录：服务器项目目录下 `data/`。
- 守护：海外 cron 每分钟跑 `watchdog_overseas.sh`；雷达停更阈值 `RADAR_STALE_SEC=2250`。
- 注意：`restart_overseas_runtime.sh` 不负责启动 `data_manager.py`；数据泵守护方式待确认。

补数据（本地开发用，按 `scripts/` 实际脚本参数使用）：

```powershell
# 查看 scripts/ 下与 crypto/overseas 数据同步相关的入口，按其参数说明执行
python scripts\data_sync_overseas_once.py --help    # 若存在则按需使用
```

---

## 3. 国内期货数据泵（天勤）

- 主程序：`data_manager_futures.py`。
- 凭证：`TQ_PHONE` / `TQ_PASS` 必须由环境变量或服务器本地私密配置提供，禁止写入仓库。
- 窗口：期货市场默认开盘前 30 分钟开始、收盘后停止；日盘/夜盘窗口由代码控制；A股无夜盘。
- 心跳：交易时段内每 60s 一次；非交易时段暂停抓取。
- 日志：`runtime/logs/data_manager_futures_run.log` / `_err.log`。
- 落盘：`data/futures/{1d,15m,5m}/`。

启动 / 重启 / 查状态：

```powershell
scripts\run_data_manager_futures.cmd                  # CMD 入口
powershell -File scripts\run_data_manager_futures.ps1 # PowerShell 入口（写 run/err 日志）
powershell -File scripts\restart_domestic_data_manager.ps1    # 杀旧进程并重启
powershell -File scripts\ensure_single_data_manager.ps1       # 确保仅一个实例
powershell -File scripts\force_domestic_dm_catchup.ps1        # 强制数据泵补抓
powershell -File scripts\refresh_domestic_once.ps1            # 一次性手动刷新
powershell -File scripts\check_domestic_tq_env.ps1            # 检查天勤环境变量
```

---

## 4. A股数据缓存

- 落盘：`data/a_stock/`，命名 `{code}_1D_qfq.csv`、`{code}_60m_qfq.csv`（前复权）。
- 抓取来源：东方财富 / 新浪（本地回测脚本按需抓取）。
- 现状：60m 缓存约 128 根（2026-07-09 观察到），无 15m 数据。
- 数据缺口：DS07/DS08 依赖 1d 足够；60m 覆盖有限；A股无 15m → DS09 类需求需在数据侧补齐后才能推进（见 `docs/MARKET_COVERAGE_BOUNDARIES.md`）。

---

## 5. 本地行情数据库（LOCAL_MARKET_DATA_DB）

- 文件：`data/market_data.sqlite`。
- 模块：`src/market_data_store.py`，提供子命令（import / export / query / status 等），用 `python -m market_data_store --help` 查看。
- 用途：本地快速查询历史行情、供回测与审计离线使用，避免每次从 CSV 全量解析。

常用：

```powershell
python -m market_data_store --status
python -m market_data_store --query --symbol BTCUSDT --timeframe 1d --start 2026-01-01
```

---

## 6. 同步任务（计划任务）

| 任务名 | 频率 | 同步内容 |
|---|---|---|
| `FengJiDomesticFutures1dSync` | 每日 12:05 / 21:05 | 期货 1d CSV 同步（Web 回测用） |
| `FengJiDomesticFutures15mSync` | 每日 07:30 / 19:30 | 期货 15m CSV 同步 |
| `FengJiPaperStateSyncAndPush` | 每 2 min | paper state 同步 + 推送国内 API（现行唯一） |

安装/更新任务脚本：

```powershell
powershell -File scripts\install_domestic_futures_1d_sync_task.ps1
powershell -File scripts\install_domestic_futures_15m_sync_task.ps1
powershell -File scripts\install_domestic_paper_state_sync_task.ps1
powershell -File scripts\install_overseas_paper_state_sync_task.ps1
```

---

## 7. 数据覆盖边界（权威口径）

详见 `docs/MARKET_COVERAGE_BOUNDARIES.md`，要点：

- DS07 / DS08 依赖：H1（1h）≥ 500 根；海外 crypto 已满足。
- DS09 依赖：M15（15m）≥ 800 根；海外 crypto 已满足。
- 国内期货：1d / 15m / 5m 覆盖随数据泵推进；A股仅 1d + 有限 60m，无 15m。
- 覆盖不足时策略应跳过/降级，不允许用不足数据强行出信号。

---

## 8. 新鲜度检查

```powershell
# 本地：检查数据文件最新修改时间
Get-ChildItem "data\futures\1d","data\overseas_1d","data\a_stock" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 10 Name,LastWriteTime

# 国内服务器（SSH 远程）
powershell -File "scripts\check_domestic_runtime_remote.ps1"

# 海外服务器
powershell -File "scripts\check_overseas_runtime_status.ps1"
```

判定口径：

- crypto 7x24：最新 CSV 修改时间距当前 < 1 小时视为新鲜。
- 期货：日盘收盘后 1d 同步（12:05/21:05 计划任务兜底）；15m 在交易时段内持续更新。
- A股：收盘后按回测需求抓取；无实时要求。

---

## 9. 常见故障与排查

| 现象 | 排查 |
|---|---|
| 期货数据不更新 | `check_domestic_tq_env.ps1` 检查凭证；看 `data_manager_futures_err.log`；确认日夜盘窗口 |
| crypto 数据不更新 | 检查 `data_sync.log`；确认 `data_manager.py` 进程；RADAR_STALE_SEC 告警 |
| 15m/1d 同步缺失 | 查计划任务 `FengJiDomesticFutures15mSync`/`1dSync` 是否注册、最近运行时间 |
| A股缓存不足 | 按回测入口触发抓取（见 `docs/RUNBOOK_A_STOCK_BACKTEST.md`） |
| 本地库过期 | `python -m market_data_store --status` 查看落后周期并触发 import |
| 数据覆盖不足 | 对照 `docs/MARKET_COVERAGE_BOUNDARIES.md` 检查 DS07/DS08/DS09 依赖是否满足 |

---

## 10. 关联文档

- 覆盖边界：`docs/MARKET_COVERAGE_BOUNDARIES.md`
- 本地库：`docs/LOCAL_MARKET_DATA_DB.md`
- 同步明细：`docs/FUTURES_1D_SYNC.md`（如存在）、`docs/FUTURES_5M_SYNC.md`、`docs/FUTURES_15M_SYNC.md`、`docs/FUTURES_5M_DATA_PLAN.md`
- 雷达刷新：`docs/RADAR_REFRESH_SCHEDULE.md`
- 服务器：`docs/RUNBOOK_SERVER.md`
- 挂单器：`docs/RUNBOOK_PENDING_ORDER.md`
- A股回测：`docs/RUNBOOK_A_STOCK_BACKTEST.md`
