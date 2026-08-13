# DS09 Live Watch（crypto radar → 沙盒图）

状态：`ACTIVE`（2026-06-16）

## 用途

只读监控 crypto 雷达中的 **DS09** 行。发现**新指纹**（新 setup_key / 新触发结构）时，自动调用 `run_crypto_ds09_sandbox_review` 生成会话沙盒图。

**不**写 `paper_state`、**不**触发挂单、**不**真实下单。

## 计划任务（本机）

| 任务名 | 频率 | 脚本 |
|--------|------|------|
| `FengJiDs09LiveWatch` | **每 15 分钟** | `run_ds09_live_watch.ps1` → `watch_ds09_live_radar_sandbox.py --once` |

安装/重装：

```powershell
powershell -File scripts\install_ds09_live_watch_task.ps1
```

自定义间隔（分钟）：

```powershell
powershell -File scripts\install_ds09_live_watch_task.ps1 -IntervalMinutes 10
```

## 手动运行

```powershell
# 单次（写日志 + 更新 state）
powershell -File scripts\run_ds09_live_watch.ps1

# 仅检测、不出图
powershell -File scripts\run_ds09_live_watch.ps1 -DryRun

# 清空已见指纹后重扫（会重新出图）
powershell -File scripts\run_ds09_live_watch.ps1 -ResetState
```

## 路径

| 类型 | 路径 |
|------|------|
| 运行日志 | `runtime/logs/ds09_live_watch.log` |
| 状态（已见指纹） | `runtime/ds09_live_watch_state.json` |
| 沙盒图 / 运行快照 | `results/ds09_live_watch/` |

## 数据依赖

- D1/M15 CSV：`data/overseas_1d/`、`data/1d/`、`data/15m/`（缺文件时回退 `data/crypto_okx/`）
- OS state（可选）：`runtime/fengji_os_state/{SYMBOL}/1d|15m.json`

## 验收

```powershell
python -m pytest tests\test_watch_ds09_live_radar_sandbox.py -q
powershell -File scripts\run_ds09_live_watch.ps1 -DryRun
Get-ScheduledTask -TaskName FengJiDs09LiveWatch | Format-List TaskName, State
```
