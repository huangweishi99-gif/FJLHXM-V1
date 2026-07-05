# PG/SC 15m 降级抓取 · 国内 CSV 验收

状态：`ACTIVE` · 部署：`2026-07-03 16:19`

## 说明

- **2026-07-05 15:34**：新 data_manager 进程自动抓取 PG **PASS**（`降级选用` + `[OK] 成功抓取 [PG]`）。
- **2026-07-03 18:02**：`probe --write` 验证降级落盘 → **ACCEPTANCE_OK**。

## 背景

PG/SC 实际主力合约 15m 历史较短，严格 `frame_looks_sane` 常失败。`data_manager_futures.fetch_frame` 已增加 **`frame_looks_acceptable` 降级**（probe 已验证可抓取）。

## 验收标准

国内 `data/15m/PG.csv` / `SC.csv` 在部署后满足任一：

1. **tail_date** 晚于基线（PG `2026-07-02 14:45` · SC `2026-07-03 06:45`）
2. **mtime** 晚于 `2026-07-03 16:19`（降级逻辑部署时刻）

## 命令

```powershell
# 单次（国内服务器上）
powershell -File scripts\verify_pg_sc_15m_csv.ps1

# 本机远程
powershell -File scripts\verify_domestic_health.ps1

# 夜盘轮询（建议 20:35 后）
powershell -File scripts\run_night_session_pg_sc_checks.ps1

# 仅 probe（绕过交易时段 gate，不写 CSV）
python scripts/probe_domestic_futures_15m.py --symbols PG,SC --timeframe 15m

# 运维补写（验证降级落盘；非 data_manager 常规路径）
python scripts/probe_domestic_futures_15m.py --symbols PG,SC --timeframe 15m --write
```

## 数据泵交易窗口

`FUTURES_WINDOWS` 夜盘 **20:30–23:59**；休市时 data_manager  idle，**不会写 CSV**。

## 相关文件

- `data_manager_futures.py` · `frame_looks_acceptable`
- `scripts/probe_domestic_futures_15m.py`
- `scripts/check_domestic_status.ps1`（PG/SC 段 + next_window 日志）
