# W14 回测详情页产品化验收报告

日期：2026-06-05

范围：

- `web/backtest.html`
- `web/css/apple.css`
- `services/api/main.py`
- `services/db/session.py`
- `services/db/context_queries.py`
- `src/chart_bundle.py`
- `scripts/batch_import_context_stats_to_pg.py`
- `scripts/smoke_pg_api_consistency.py`

## 1. 结论

W14 回测详情页 API/DOM/数据级验收通过。

本轮完成了两个产品化缺口：

- 回测页新增可见 CSV 导出入口。
- 回测页选中交易后可查看桶详情、同桶样本，并可导出同桶 CSV。

本轮没有做浏览器截图级验收，原因是当前环境未发现可直接调用的 Chrome/Playwright。验收依据为：前端脚本解析、静态检查、FastAPI HTTP smoke、PG/API 一致性 smoke、单元测试。

## 2. 前端能力

### 2.1 回测基础控件

已存在并复核：

- 市场：期货、A股、虚拟货币、美股。
- 品种搜索：读取 `/api/v1/backtests/symbol-summary`。
- 定式选择：读取 `/api/v1/strategies`，并受 `localStorage.fj-plan` 档位控制。
- 回测时间：1 年、3 年、5 年，受订阅档位控制。
- 加载回测：同时读取 `chart-bundle` 与 `trades`。

### 2.2 K 线与交易明细

已存在并复核：

- `chart-bundle` 返回 K 线、OS 峰极线、买卖标记、收益曲线、指标。
- 点击 K 线买卖点后，右侧交易明细显示定式、方向、信号强弱、买入/卖出时间、价格、手数、净盈亏。

### 2.3 本轮新增

- `导出 CSV`：导出当前回测页交易明细。
- `同桶强弱`：显示选中交易的 `bucket_count`、胜率、平均 R、分数、bucket key。
- `查看同桶样本`：调用 `/api/v1/context-stats/bucket-trades`。
- `导出同桶 CSV`：导出当前同桶样本。

## 3. API 验收

临时启动 FastAPI 后，HTTP smoke 结果：

```text
API_HEALTH_OK
CHART_OK FUTURES PVC 200 DS03 170 3
CHART_OK A_STOCK 000021 200 DS03 243 5
CHART_OK CRYPTO ETHUSDT 200 DS03 366 9
CHART_OK US_STOCK AAPL 200 DS03 252 9
SUMMARY_OK FUTURES 200 3 ['豆粕', '白糖', '菜油']
SUMMARY_OK A_STOCK 200 3 ['2475', '988', '600522']
SUMMARY_OK CRYPTO 200 3 ['AVAXUSDT', 'SOLUSDT', 'LTCUSDT']
SUMMARY_OK US_STOCK 200 3 ['AAPL', 'WEC', 'NWSA']
TRADES_OK 200 5 ETHUSDT|DS01|2026-05-18 00:00:00|101|ETH-DS01-23-3
STRENGTH_OK 200 INSUFFICIENT_DATA 6
BUCKET_TRADES_OK 200 3 ETHUSDT|DS01|2026-05-18 00:00:00|101|ETH-DS01-23-3
```

说明：

- 四市场 `chart-bundle` 均可返回。
- PG 样本概览、交易明细、单笔信号强弱、同桶样本均可返回。
- `STRENGTH_OK` 中 `INSUFFICIENT_DATA` 是统计样本不足标签，不是接口失败。

## 4. 本轮修复

### 4.1 美股 CSV 入口

问题：

- `data/us_stock/` 已有 `AAPL_1D.csv` 等文件，但 `services/api/main.py:resolve_csv()` 原先没有 `US_STOCK` 分支。
- 回测页选择美股时会找不到 CSV。

修复：

- `resolve_csv()` 增加 `US_STOCK/USSTOCK` 分支，读取 `data/us_stock/{symbol}_1D.csv` 或 `{symbol}.csv`。
- 新增测试覆盖 `AAPL -> AAPL_1D.csv`。

### 4.2 PG 连接快速失败

问题：

- 本地 PG 未启动时，`symbol-summary`、`trades`、`bucket-trades` 等接口可能长时间等待。

修复：

- `services/db/session.py` 增加 PostgreSQL `connect_timeout`，默认 3 秒，可用环境变量 `DATABASE_CONNECT_TIMEOUT` 覆盖。
- 复验未启动 PG 时约 3.14 秒返回 HTTP 503。

### 4.3 PG 样本导入

本轮启动本地 PG 并执行：

```powershell
docker compose up -d db
alembic upgrade head
python scripts\batch_import_context_stats_to_pg.py --limit 20
```

导入结果：

```text
dirs_ok=20
dirs_fail=0
imported_snapshots=1165
rebuilt buckets=5726 from snapshots=191841
```

## 5. PG/API 一致性

执行：

```powershell
python scripts\smoke_pg_api_consistency.py --port 8046 --sample-plan A_STOCK=2,CRYPTO=2,FUTURES=1,US_STOCK=1
```

结果：

```text
PG_API_CONSISTENCY_OK=6/6
A_STOCK=2
CRYPTO=2
FUTURES=1
US_STOCK=1
```

## 6. 测试

执行：

```powershell
python -m pytest tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
```

结果：

```text
5 passed
```

前端脚本检查：

```text
node --check web\js\app.js
node --check web\js\config.js
node --check web\js\chart.js
BACKTEST_INLINE_SCRIPT_PARSE_OK=1
```

## 7. 已知限制

1. 未做浏览器截图级验收；需要 Chrome/Playwright 可用后补。
2. 本轮只验证 DS03 chart-bundle 四市场样本；TOTAL 和 DS01 可继续抽样，但 DS02/DS04-DS09 的 chart-bundle 仍未全部产品化。
3. 本轮只做本地 PG 验证；生产 PG、正式 Worker、用户隔离和缓存仍属于 W11/W17-prod/WAdmin 范围。
4. `symbol-summary` 中 A 股 symbol 可能显示为去前导零形式，例如 `2475`；页面搜索已支持输入 `000021`，但展示格式后续可统一为 6 位。

## 8. 下一步

进入 W16 模拟监测页产品化验收：

- 四市场监测列表。
- 自选品种额度与档位。
- 国内实际主力合约。
- 海外 crypto 与国内 futures 状态。
- 旧状态过滤。
- 监测页 K 线/持仓/信号显示。
- API smoke 与前端脚本检查。
