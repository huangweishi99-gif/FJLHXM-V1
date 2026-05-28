# 峰极 OS 状态库（数据股）

## 原则

- **峰极 OS 规则在引擎代码中固定**，不在每次开仓时临时改规则。
- **运行态落在 `runtime/fengji_os_state/`**（按品种+周期 JSON），相当于「数据股」。
- **增量更新**：状态文件与 K 线尾部指纹一致时，只 `run_from_state` 处理**新走出来的 K**；历史不重算。
- **数据泵只追加行情 CSV**；雷达/回测读取 CSV 后合并状态库，避免每次全量硬化。

## 文件命名

| 市场 | 环境变量 | K 线文件 | 状态文件 |
|------|----------|----------|----------|
| 国内期货 | `FENGJI_MARKET=futures` | `data/1d/LC.csv`（兼容 `LCUSDT.csv`） | `runtime/fengji_os_state/LC_1d.json` |
| 海外加密 | 默认 `crypto` | `data/1d/BTCUSDT.csv` | `runtime/fengji_os_state/BTCUSDT_1d.json` |

## 何时全量重算

以下情况会丢弃旧状态、整段重算并写回：

- `gap` 变更
- 首根 K 日期变化（CSV 被替换或截断）
- 已处理最后一根的 OHLC 指纹变化（同日期 K 线被修订）

## 国内模拟盘配套

- 数据泵：`data_manager_futures.py`（停更超过 36h 可在盘外补抓一轮）
- 雷达循环：带 `--os-state-dir runtime/fengji_os_state`
- 挂单 `valid_until`：以**雷达刷新时刻**为锚 + 2 日，避免 K 线日期旧导致全部过期
- 挂单监控：读 `LC.csv` / `LCUSDT.csv` 双路径；`FENGJI_MARKET=futures`

## 代码入口

- `fengji_core.os_state_store`：`build_os_detail_frame_stateful`、`os_state_path`、`find_data_file`
- `fengji_total_radar.py`：已接入状态库
