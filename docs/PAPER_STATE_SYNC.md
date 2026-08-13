# Paper State 同步（V1.1 · Web 监测）

状态：`ACTIVE`（2026-06-16）

## 为什么需要

国内 API 服务器 **无法 SSH 海外**。Web 监测页要同时展示：

- 国内期货/A股模拟盘（domestic `paper_state`）
- 海外 crypto 模拟盘（overseas `paper_state`）

因此用 **本机** 作中转：拉取两端 state → 推到国内 API 的 `runtime/`。

## 唯一计划任务（本机）

| 任务名 | 频率 | 脚本 |
|--------|------|------|
| `FengJiPaperStateSyncAndPush` | **每 2 分钟** | `sync_and_push_paper_state_for_web.ps1` |

安装/重装：

```powershell
powershell -File scripts\install_paper_state_sync_and_push_task.ps1
```

**勿再启用**（已废弃，安装时会自动 Disable）：

- `FengJiDomesticPaperStateSync`
- `FengJiOverseasPaperStateSync`

## 链路（3 步 · 同进程）

```
domestic-quant SCP → runtime/domestic_paper_state.json
overseas-quant SCP → runtime/overseas_paper_state.json
本机 SCP push → domestic-quant runtime/domestic|overseas_paper_state.json
```

编排脚本 **同进程** 调用子脚本，避免每分钟弹出多个 PowerShell 窗口。

## 日志（不看弹窗）

- `runtime/logs/domestic_paper_state_sync.log`
- `runtime/logs/overseas_paper_state_sync.log`
- `runtime/logs/push_paper_state_to_domestic_api.log`

手动跑一次：

```powershell
powershell -WindowStyle Hidden -File scripts\sync_and_push_paper_state_for_web.ps1 -SkipVerify
```

## API 消费

- `GET /api/v1/monitor/domestic/latest-opens` ← 国内 paper
- `GET /api/v1/monitor/overseas/latest-opens` ← 海外 paper（V1.1）
- `monitor.html` 并行拉取后合并展示

## 验收

```powershell
# 默认 mint pro JWT，避免 opens 429（匿名 free 900s 限流）
python scripts/verify_v11_monitor_e2e.py --ssh-tunnel domestic-quant
powershell -File scripts\verify_remote_v11_monitor_e2e.ps1

# 显式 token 或匿名复现
python scripts/verify_v11_monitor_e2e.py --base-url http://127.0.0.1:8000 --pro-token $env:FENGJI_V11_E2E_PRO_TOKEN
python scripts/verify_v11_monitor_e2e.py --ssh-tunnel domestic-quant --no-mint-pro-token

powershell -File scripts\sync_and_push_paper_state_for_web.ps1 -Verify
```

## 与期货 1d 同步的区别

| 任务 | 用途 | 频率 |
|------|------|------|
| `FengJiPaperStateSyncAndPush` | 监测页 **持仓** | 2 分钟 |
| `FengJiDomesticFutures1dSync` | Web 回测 **K 线 CSV** | 每日 12:05 / 21:05 |

两者独立，不要合并。
