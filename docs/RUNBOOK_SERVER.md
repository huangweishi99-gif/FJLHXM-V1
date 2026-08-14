# 服务器运行手册（RUNBOOK）

状态：`ACTIVE`（2026-08-14 汇总成册）
依据：根目录 `峰极OS_服务器与部署说明.md`（权威基线）+ `scripts/` 运行脚本盘点。
约定：本文不写服务器 IP、登录用户、SSH 私钥、密码、API Key、Token、完整 webhook；连接信息一律见本地私密配置 / 服务器环境变量 / 云控制台。

---

## 1. 双服务器分工总览

| 维度 | 国内服务器 | 海外服务器 |
|---|---|---|
| SSH 别名（脚本默认，占位符） | 国内 SSH 别名（`domestic-quant`） | 海外 SSH 别名（`overseas-quant`） |
| 部署根目录（占位符） | 国内部署根目录（`quant_futures`） | 海外部署根目录（`quant_crypto`） |
| 系统 | Windows Server（`.ps1` / 计划任务） | Linux（`.sh` / cron） |
| 数据源 | 天勤（期货/A股） | Binance（crypto），补 HYPE/ATH 用 OKX |
| 数据周期 | 期货日盘/夜盘窗口、A股日盘（无夜盘） | crypto 7x24（1d/1h/15m） |
| 守护 | 计划任务 `FengJiDomesticWatchdog`（每 1 分钟） | cron 每分钟跑 `watchdog_overseas.sh` |
| 定位 | **只模拟实盘，不真实下单** | **只模拟实盘，不真实下单** |

说明：DS01/DS03/DS05/DS07/DS08/DS09 是策略编号（九大定式），不是独立进程。国内由单一模拟盘脚本 `峰极总定式01-08国内期货A股模拟实盘.py`（文件名含 `01-08`）统一实现；雷达循环与挂单监控是另两个独立进程。

---

## 2. 一键检查（推荐入口）

本机 PowerShell 运行（同时检查国内 + 海外两台）：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\check_dual_server_runtime_status.ps1"
```

参数：

| 参数 | 说明 | 默认 |
|---|---|---|
| `-SkipDomestic` | 跳过国内检查 | 不跳过 |
| `-SkipOverseas` | 跳过海外检查 | 不跳过 |
| `-DomesticSshHost` | 国内 SSH 别名 | 国内 SSH 别名（脚本默认） |
| `-DomesticRemoteRoot` | 国内远端根目录 | 见脚本 |
| `-OverseasSshHost` | 海外 SSH 别名 | 海外 SSH 别名（脚本默认） |
| `-OverseasRemoteDir` | 海外远端目录 | 见脚本 |

输出：新建 `runtime\logs\dual_runtime_check\<yyyyMMdd_HHmmss>\`，内含 `domestic_runtime.log`、`overseas_runtime.log`、`SUMMARY.md`。退出码 0=PASS，1=FAIL。

日志管理（保留 14 天，默认 DRY_RUN，确认后加 `-Execute` 才删除）：

```powershell
powershell -File "scripts\manage_dual_runtime_check_logs.ps1" -Execute
```

---

## 3. 国内服务器

### 3.1 运行模块与进程

| 模块 | 进程关键字 | 说明 |
|---|---|---|
| 数据泵 | `data_manager_futures.py` | 天勤数据泵，含日夜盘窗口控制 |
| 模拟盘 | `峰极总定式01-08国内期货A股模拟实盘.py` | 国内期货/A股模拟实盘主入口（以服务器目录实际文件名为准） |
| 雷达循环 | `fengji_radar_order_loop.py` | 刷新雷达 + 生成挂单（生产 `--loop-seconds 600`） |
| 挂单监控 | `fengji_futures_pending_order_monitor.py` | 模拟挂单触发（生产 `--loop-seconds 5`） |
| Dash 看板 | `商业终端_Dash.py` | 商业终端看板（以服务器目录实际文件名为准） |

### 3.2 检查

本机远程委托检查（推荐）：

```powershell
powershell -File "scripts\check_domestic_runtime_remote.ps1" [-SshHost 国内SSH别名] [-RemoteRoot ...]
```

服务器本地检查：

```powershell
powershell -File "scripts\check_domestic_runtime_status.ps1"        # 进程 + 日志尾部
powershell -File "scripts\check_domestic_status.ps1"                # 数据泵心跳/15m新鲜度/活跃挂单
powershell -File "scripts\check_domestic_ds05_radar.ps1"            # 筛选 radar.csv 中 DS05 行
powershell -File "scripts\check_domestic_tq_env.ps1"                # 天勤账号环境变量是否已设置
```

### 3.3 重启

全链路重启（数据泵 + 模拟盘 + 雷达 + 挂单监控；先停旧进程）：

```powershell
powershell -File "scripts\restart_domestic_futures_runtime.ps1"
```

单模块重启：

```powershell
powershell -File "scripts\restart_domestic_radar_loop.ps1"      # 只重启雷达
powershell -File "scripts\restart_domestic_pending_monitor.ps1" # 只重启挂单监控
powershell -File "scripts\restart_domestic_data_manager.ps1"     # 杀并重启数据泵
powershell -File "scripts\restart_domestic_paper_only.ps1"       # 只重启模拟盘
```

启动工厂（停止旧进程后启动数据泵/模拟盘/雷达/挂单/Dash）：

```text
scripts\start_factory_ascii.bat        # 服务器本地运行（推荐入口）
scripts\run_futures_radar_loop.cmd     # 仅雷达（遗留入口，参数 300s 需与 watchdog 600s 对齐或停用）
scripts\run_futures_pending_monitor.cmd
```

注意：`run_futures_radar_loop.cmd` 的 300s 与生产 watchdog 600s 不一致，若仍被计划任务引用应停用，避免双实例参数不一致。

### 3.4 日志

```text
runtime/logs/data_manager_futures_run.log / _err.log
runtime/logs/paper_futures_run.log / _err.log
runtime/logs/futures_radar_order_loop.log / _err.log
runtime/logs/futures_pending_order_monitor.log / _err.log
```

状态文件（占位，以服务器目录为准）：

```text
runtime/fengji_futures/state_futures_v2.json
runtime/fengji_futures/trades_futures_astock.csv
runtime/fengji_pending_orders/pending_orders.json
runtime/fengji_pending_orders/futures_pending_state.json
runtime/fengji_pending_orders/events.jsonl
```

---

## 4. 海外服务器

### 4.1 运行模块与进程

| 模块 | 进程关键字 | 说明 |
|---|---|---|
| 数据泵 | `data_manager.py` | Binance 数据同步（1d/1h/15m），每轮同步后 sleep 600s |
| 主模拟盘 | `overseas_paper_monitor.py` | 海外 crypto 主模拟盘入口 |
| 雷达 | `fengji_total_radar.py` | 生成 `runtime/fengji_radar/radar.csv/json` |
| 雷达循环 | `fengji_radar_order_loop.py` | 生产 `--loop-seconds 900` |
| 挂单监控 | `fengji_pending_order_monitor.py` | 生产 `--loop-seconds 5` |
| 通知 | 飞书 webhook（环境变量，不落仓库） | 模拟成交通知 |

### 4.2 检查

```powershell
powershell -File "scripts\check_overseas_runtime_status.ps1" [-SshHost 海外SSH别名] [-RemoteDir ...]
```

输出：hostname/时间、进程清点、radar/pending JSON mtime、数据 CSV 新鲜度、有效挂单汇总、通知覆盖率。

### 4.3 重启 / 同步

```bash
# 海外服务器项目目录内执行：重启雷达循环 + 挂单监控 + 主模拟盘
bash scripts/restart_overseas_runtime.sh
```

```powershell
# 本机：打包 src 同步到海外（远端备份旧 src 后解压；同步后需重启进程）
powershell -File "scripts\sync_src_to_server.ps1"
```

注意：`restart_overseas_runtime.sh` 当前不负责启动 `data_manager.py`（数据泵守护方式：待确认）。`sync_src_to_server.ps1` 是代码同步工具，不是状态检查工具。

### 4.4 日志

```text
data_sync.log
paper_run.log
radar_order_loop.log
pending_order_monitor.log
runtime/fengji_paper/state.json
runtime/fengji_pending_orders/state.json
runtime/fengji_pending_orders/fills.csv
runtime/fengji_pending_orders/events.jsonl
runtime/fengji_pending_orders/closed_trades.csv
```

---

## 5. 本机辅助计划任务

| 任务名 | 频率 | 说明 |
|---|---|---|
| `FengJiDomesticWatchdog` | 1 min | 国内守护（进程保活 + 心跳） |
| `FengJiPaperStateSyncAndPush` | 2 min | paper state 同步 + 推送到国内 API（现行唯一） |
| `FengJiDomesticFutures1dSync` | 每日 12:05 / 21:05 | 期货 1d CSV 同步（Web 回测） |
| `FengJiDomesticFutures15mSync` | 每日 07:30 / 19:30 | 期货 15m CSV 同步 |
| `FengJiNew10FillWatch` | 15 min | 新10成交观察 |
| `FengJiDs09LiveWatch` | 15 min | DS09 实时成交观察 |
| `FengJiUserPaperExecutionJob` | 1 min | 用户模拟执行 |

海外 cron：每分钟跑 `watchdog_overseas.sh`（进程守护 + 雷达停更告警阈值 `RADAR_STALE_SEC=2250`）。

---

## 6. 故障排查顺序

1. SSH 是否连通（连接信息见本地私密配置 / 云控制台）。
2. 数据泵进程是否运行；数据文件最新修改时间是否接近市场更新窗口。
3. 雷达循环进程 + `runtime/fengji_radar/radar.csv/json` 更新时间。
4. 挂单文件 `runtime/fengji_pending_orders/pending_orders.csv/json` 更新时间。
5. 挂单监控进程 + `events.jsonl` / `fills.csv` / `closed_trades.csv`。
6. 主模拟盘状态文件与日志。
7. 错误日志是否有新异常。
8. 若刚同步代码，确认进程已重启。
9. 若策略行为异常，生成沙盒图复核峰极线、阵营、定式、买卖点、防守点和挂单点。

---

## 7. 安全红线

- 禁止把服务器密码、API Key、Token、交易所密钥、数据源密码、完整 webhook、SSH 私钥写入仓库/文档/日志。
- 禁止在文档中明文写服务器 IP、域名、登录用户名、控制台入口。
- 禁止把模拟盘脚本直接改成真实下单脚本。
- 未经用户明确确认，禁止真实下单/撤单/资金查询/API 权限修改。
- 禁止用旧日志判断当前服务器状态；必须实时 SSH 检查。
- 禁止同步代码前不备份远端关键目录；禁止在服务器批量删除未知文件。
- 禁止把期货/A股/crypto 的交易时间、风控、手续费、滑点、保证金规则混用。
- 禁止绕过最高宪法、阵营转换、九大定式规则直接部署策略。

---

## 8. 待完成事项（沿用权威文档 §7）

- [ ] 实时 SSH 检查国内/海外数据泵、模拟盘、雷达、挂单监控是否正常运行（每次回答均需实时检查）。
- [ ] 国内/海外服务器代码与本地最新 DS01/DS03/DS05/DS09 规则逐一核对（DS07 已于 2026-08-13 通过）。
- [ ] 把脚本中的 webhook、服务器连接默认值、数据源账号默认值移出仓库。
- [ ] 为海外服务器补齐独立数据泵启动/停止/守护说明。
- [ ] 为国内服务器补齐独立停止脚本。
- [ ] 明确国内期货日盘/夜盘数据泵自动运行表；A股无夜盘。
- [ ] 明确服务器守护方式（计划任务 / systemd / screen / nohup / 启动项 / 手动）。
- [ ] 统一健康检查输出；每次部署后记录版本、文件清单、重启时间和验证结果。

---

## 9. 关联文档

- 权威基线：根目录 `峰极OS_服务器与部署说明.md`
- 数据管线：`docs/RUNBOOK_DATA_PIPELINE.md`
- 挂单器：`docs/RUNBOOK_PENDING_ORDER.md`
- A股回测：`docs/RUNBOOK_A_STOCK_BACKTEST.md`
- 雷达刷新频率：`docs/RADAR_REFRESH_SCHEDULE.md`
- paper state 同步：`docs/PAPER_STATE_SYNC.md`
