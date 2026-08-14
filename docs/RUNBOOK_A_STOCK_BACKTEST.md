# A股板块回测手册（RUNBOOK_A_STOCK_BACKTEST）

状态：`ACTIVE`（2026-08-14 汇总成册）
范围：A股数据缓存、单只/HOT20/板块批回测入口、费用口径、输出归档、数据缺口。
约定：不修改既定市场规则（手续费/滑点/T+1/保证金），回测结果不作为策略改动依据，只用于验证与审计。

---

## 1. 数据源与缓存

| 项 | 说明 |
|---|---|
| 抓取来源 | 东方财富（日线/60m）+ 新浪（兜底），按需抓取 |
| 缓存目录 | `data/a_stock/`，命名 `{code}_1D_qfq.csv`、`{code}_60m_qfq.csv`（前复权） |
| 本地库 | `data/market_data.sqlite`（`src/market_data_store.py` 维护） |
| 数据现状 | 1d 可用；60m 约 128 根（2026-07-09 观察）；**无 15m** |
| 数据缺口 | DS07/DS08 依赖 1d 满足；60m 覆盖有限；DS09 类（M15）在 A股侧无法推进，见 `docs/MARKET_COVERAGE_BOUNDARIES.md` |

数据源选择（`--data-source`）：

- `auto`：优先本地库/缓存，缺失自动下载。
- `db`：只用 `data/market_data.sqlite`。
- `download`：强制重新下载。

---

## 2. 回测入口

### 2.1 单只股票

```powershell
python src\backtest_a_stock_fengji.py --symbol 600519 --name 贵州茅台 --start 20200101 --end 20250101
```

### 2.2 HOT20 批量（默认名单）

```powershell
python src\batch_backtest_a_stock_fengji.py --stocks HOT20 --start 20200101 --end 20500101
```

自定义名单：`--stocks code:name,code:name` 或 CSV 路径。

### 2.3 板块批量（默认板块列表）

```powershell
python src\batch_backtest_a_stock_sector.py --boards "CPO概念,算力概念" --top-n 28 --sort-by amount --start 20200101
```

常用参数：

| 参数 | 说明 | 默认 |
|---|---|---|
| `--boards` | 板块名称或 BK 代码，逗号分隔 | 内置 `DEFAULT_SECTORS` |
| `--board-source` | `all` / `concept` / `industry` | all |
| `--top-n` | 每个板块取成交额前 N 只 | 28 |
| `--sort-by` | 排序口径：amount / market_cap / free_market_cap / main_net_inflow / turnover | amount |
| `--include-bj` | 包含北交所（默认剔除） | 关闭 |
| `--dry-run` | 只生成板块股票池，不执行回测 | 关闭 |
| `--resume` | 同一输出目录跳过已成功股票，只重试失败 | 关闭 |
| `--download-pause-seconds` | 每只股票日线/60m 请求间隔 | 2.0 |
| `--sleep-seconds` | 股票间暂停（防东财断连） | 3.0 |

---

## 3. 费用与参数口径（既定规则，不得修改）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--initial-cash` | 20000 | 初始资金 |
| `--commission-rate` | 0.0003 | 佣金费率 |
| `--min-commission` | 5.0 | 最低佣金 |
| `--stamp-duty-rate` | 0.0005 | 印花税（卖出） |
| `--transfer-fee-rate` | 0.00001 | 过户费 |
| `--slippage-rate` | 0.0003 | 滑点 |
| `--lot-size` | 100 | 一手股数 |
| `--atr-window` | 14 | ATR 窗口 |
| `--gap` | 3 | 入场延迟/跳过参数 |

禁止为了让回测收益更好而修改上述市场规则；T+1 由数据引擎内建，不在命令行暴露。

---

## 4. 输出与归档

| 场景 | 默认输出目录 |
|---|---|
| HOT20 批量 | `results/fengji_total_a_stock_hot20/` |
| 板块批量 | `results/fengji_total_a_stock_sectors/` |

板块批次输出结构：每板块目录含股票回测 CSV/JSON + 板块汇总；根目录含 `summary`/`rank` 汇总文件。

辅助工具：

```powershell
# 从 rank 汇总恢复未完成板块/股票
python src\resume_a_stock_sector_from_rank.py

# 板块结果汇总
python src\summarize_a_stock_sectors.py

# 板块回测归档审计（盘点已归档股票、缺口）
python src\audit_a_stock_sector_archive.py

# 本地 C1 辅助（如存在，按脚本说明使用）
python src\run_a_stock_c1_local.py --help
```

---

## 5. 数据缺口与降级

- 60m 不足：仅 1d 数据可正常回测日线级别定式；60m 依赖策略（如 DS07 部分检查）会因覆盖不足跳过。
- 无 15m：A股不做 DS09 类 M15 回测。
- 覆盖不足时策略应跳过/降级，禁止用不足数据强行出信号。

---

## 6. 常见故障与排查

| 现象 | 排查 |
|---|---|
| 东财断连/下载失败 | 增大 `--sleep-seconds` / `--download-pause-seconds`；`--resume` 续跑 |
| 数据缺 60m | 确认 `data/a_stock/{code}_60m_qfq.csv` 存在；`--data-source download` 强制重抓 |
| 板块池为空 | 检查 `--boards` 名称与东方财富板块代码；`--dry-run` 先行验证 |
| 回测跳过 | 对照覆盖边界；确认 1d 根数与 DS07/DS08 最低要求 |
| 结果不一致 | 核对费用口径（§3）与 T+1 引擎；用沙盒图/单笔明细复核 |

---

## 7. 关联文档

- 覆盖边界：`docs/MARKET_COVERAGE_BOUNDARIES.md`
- 数据管线：`docs/RUNBOOK_DATA_PIPELINE.md`
- 服务器：`docs/RUNBOOK_SERVER.md`
- 挂单器：`docs/RUNBOOK_PENDING_ORDER.md`
- A股复盘：`docs/FENGJI_TOTAL_A_STOCK_HOT20_REVIEW.md`（如存在）
