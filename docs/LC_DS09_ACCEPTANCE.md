# LC（碳酸锂）DS09 验收清单

状态：国内期货 D1+M15 九重天（DS09）  
依据：`docs/DS09_CALIBRATION.md`、国内天勤 `KQ.m@GFEX.lc`  
最后更新：2026-05-28

---

## 一、数据层

| # | 验收项 | 通过标准 | 命令 / 路径 |
|---|--------|----------|-------------|
| D1 | 15m 为天勤真数据 | `data/15m/LC.csv` 含 `datetime` 纳秒列；`date` 在 2020–2031；行数 **≥10000**（请求 12000 时通常取 **10000**，12000/11000 常校验失败） | `Get-Content data\15m\LC.csv -TotalCount 3` |
| D2 | 无脏数据 | 不存在大量 `1970-01-01`；`high > low`；`close` 在 LC 合理区间（通常 ≥1万） | 对比 SA 15m 格式 |
| D3 | 1d / 1h 同步 | 回填日志 `1d=800`（LC 勿强求 1200）、`1h≥2000`；1d 用于昨日边界 | `scripts/backfill_lc_domestic.ps1` |
| D4 | 禁止误用联调数据 | 验收与回测不用 `build_lc_bars_from_1h` 产物（仅流水线联调） | 勿加 `-BuildFrom1h` |
| D5 | 15m 长度上限 | `FUTURES_15M_LENGTH` 请求 12000 时，若脏数据则自动降为最大**校验通过**长度（见 `data_manager_futures.fetch_frame` 日志） | 日志含 `选用 data_length=` |

```powershell
.\scripts\backfill_lc_domestic.ps1 -M15Length 12000 -D1Length 1200
```

---

## 二、Session / 夜盘（期货）

| # | 验收项 | 通过标准 | 命令 |
|---|--------|----------|------|
| S1 | 期货市场标识 | `FENGJI_MARKET=futures` | 国内雷达 / 回测环境变量 |
| S2 | `assign_session_date` | `m15_mapped_rows` ≈ `m15_rows`（允许少量边界丢弃） | `verify_ds09_lc_session.py` |
| S3 | 边界日数量 | `boundary_sessions` > 0（加长 1d 后应明显增加） | 同上 JSON 输出 |
| S4 | 夜盘样本（说明） | 天勤 LC 15m 时间戳多在 **0–6 点** 段；`hour>=21` 样本可为 0，**不以之为失败** | `scripts/debug_lc_ds09.py` |

```powershell
$env:PYTHONPATH = "src;packages/fengji_core"
$env:FENGJI_MARKET = "futures"
python scripts/verify_ds09_lc_session.py --d1-csv data/1d/LC.csv --m15-csv data/15m/LC.csv
```

---

## 三、DS09 逻辑与回测

| # | 验收项 | 通过标准 | 说明 |
|---|--------|----------|------|
| L1 | 审计 | `ds09_bad_trades = 0` | 硬条件 |
| L2 | 成交笔数 | `ds09_trades ≥ 0`；>0 时须有可复核沙盒图 | LC 无突破昨日边界时 0 笔为**行情结果** |
| L3 | 锁定统计 | `debug_lc_ds09` 中 `locks` / `manual_sigs` 与回测一致 | `locks>0` 才有成交可能 |
| L4 | OS 宪法 | D1/M15 均 `gap=3`，`hardened_fengji_line` | 与 ETH 校准一致 |
| L5 | 一日一结构 | 同一 `session_date` 最多一笔 | 见 `ds09.py` |

```powershell
python scripts/debug_lc_ds09.py
```

---

## 四、雷达与挂单（国内）

| # | 验收项 | 通过标准 | 命令 |
|---|--------|----------|------|
| R1 | 雷达循环 | `futures_radar_order_loop` 进程存在，含 **LC** | `check_domestic_status.ps1` |
| R2 | 单次刷新 | `--once --symbols LC` 无 traceback | `fengji_radar_order_loop.py` |
| R3 | DS09 行 | 有结构时 `radar.json` 出现 `strategy_id=DS09`；无结构时为 0 | 非失败 |
| R4 | 代码同步 | `ds09.py`、`fengji_total_radar.py`、`data.py` 与仓库一致 | `sync_deploy_domestic.ps1` |

```powershell
.\scripts\sync_deploy_domestic.ps1 -RestartRadarLoop
.\scripts\run_lc_ds09_domestic.ps1
```

---

## 五、产物与归档

| # | 验收项 | 路径 |
|---|--------|------|
| A1 | Session 校验 JSON | `runtime/sandbox/lc_ds09/session_check.txt`（国内） |
| A2 | 总览沙盒图 | `results/sandbox/lc_ds09/LC_DS09_session_overview.png` |
| A3 | 单笔沙盒（有成交时） | `LC_DS09_trade_1.png` … `_3.png` |
| A4 | 国内 matplotlib | 国内需 `pip install matplotlib` 才能出图 |

---

## 六、已知限制（不记为缺陷）

1. **GFEX LC + tqsdk2**：`data_length=12000` 曾整表损坏；现以 `frame_looks_sane` 取最长可用窗口。  
2. **0 笔成交**：在约 8000 根 15m 内若无 `high>昨日高点`（多头）或 `low<昨日低点`（空头），回测为 0。  
3. **国内 Python 3.10**：`pip install -e fengji_core` 失败，依赖 `PYTHONPATH=src;packages/fengji_core`。  
4. **ETH 对照**：`plan_a_verify.ps1` 中 ETH DS09 应有成交，用于区分「代码错误」与「LC 无结构」。

---

## 七、签收记录（填写）

| 日期 | 15m 行数 | data_length | ds09_trades | bad_trades | 验收人 |
|------|----------|-------------|-------------|------------|--------|
| 2026-05-28 | 7946 | 8000 | 0 | 0 | 加长回填前 |
| 2026-05-28 | 10000 | 10000 | 0 | 0 | 加长回填后（locks 仍 0） |
| | | | | | |

---

## 八、快速一键（推荐顺序）

```powershell
# 本机
.\scripts\backfill_lc_domestic.ps1 -M15Length 12000 -D1Length 1200
.\scripts\run_lc_ds09_domestic.ps1

# 本机复验
$env:PYTHONPATH="src;packages/fengji_core"; $env:FENGJI_MARKET="futures"
python scripts/debug_lc_ds09.py
python scripts/plot_lc_ds09_session_overview.py `
  --d1-csv data/futures_lc/1d/LC.csv --m15-csv data/futures_lc/15m/LC.csv `
  --out results/sandbox/lc_ds09/LC_DS09_session_overview.png
```
