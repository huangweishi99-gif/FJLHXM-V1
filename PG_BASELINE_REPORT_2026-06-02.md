# PostgreSQL 基线验收报告（2026-06-02）

## 1. 验收目标

本次从项目瘦身回到 FJLHXM-V1 主线，验证 PostgreSQL / Alembic / API 是否已经可以支撑后续产品化。

验收范围：

- Docker PostgreSQL / TimescaleDB 容器
- Alembic migration
- `instruments` / `bars` / `trade_context_snapshots` / `context_bucket_stats`
- crypto CSV 小样本导入脚本幂等性
- FastAPI 读取 PG 的接口
- PG 与 API 的 10 笔分市场样本一致性

## 2. 配置与启动

执行：

```powershell
docker compose up -d
python -m alembic upgrade head
```

结果：

- 容器：`fengji_pg`
- 健康状态：`healthy`
- Alembic 当前版本：`002`
- 表存在：
  - `instruments`
  - `bars`
  - `trade_context_snapshots`
  - `context_bucket_stats`
  - `alembic_version`

说明：本地 docker-compose 使用开发库配置，不记录任何真实生产密钥。

## 3. 当前 PG 数据量

验收时数据量：

| 表 | 行数 |
| --- | ---: |
| `instruments` | 250 |
| `bars` | 445002 |
| `trade_context_snapshots` | 179814 |
| `context_bucket_stats` | 3983 |

按市场：

| market | instruments |
| --- | ---: |
| `A_STOCK` | 239 |
| `CRYPTO` | 11 |

按 market/timeframe 的 K 线：

| market | timeframe | bars |
| --- | --- | ---: |
| `A_STOCK` | `1D` | 279046 |
| `A_STOCK` | `1H` | 150965 |
| `CRYPTO` | `1D` | 14991 |

## 4. 小样本导入幂等验证

执行：

```powershell
python scripts\import_crypto_csv_to_pg.py --dir data\overseas_1d --symbol BTCUSDT
```

结果：

- 脚本读取 `BTCUSDT.csv`，输出 `1835 bars`
- 导入前 `bars=445002`
- 导入后 `bars=445002`
- `BARS_DELTA=0`

结论：已有数据冲突跳过，脚本对该样本具备幂等性。

## 5. API 验收

本地启动：

```powershell
$env:PYTHONPATH='src;packages/fengji_core;services'
python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8010
```

已验证接口：

- `GET /api/v1/health`
- `GET /api/v1/instruments?market=CRYPTO&limit=3`
- `GET /api/v1/context-stats/buckets?strategy_id=DS01&market=CRYPTO&limit=3`
- `GET /api/v1/backtests/trades?market=CRYPTO&symbol=BTCUSDT&limit=3`
- `GET /api/v1/signals/{trade_id}/strength`

结果：上述接口均能读取真实 PG 数据并返回有效 JSON。

## 6. PG vs API 10 笔一致性

抽样策略：

- `A_STOCK`：4 笔
- `CRYPTO`：3 笔
- `US_STOCK`：3 笔

对比字段：

- `trade_id`
- `strategy_id`
- `market`
- `symbol`
- `entry_time`
- `net_pnl`
- `r_multiple`
- `signal_tier`

结果：

```text
STRATIFIED_CONSISTENCY_OK=10/10
```

结论：PG 直接查询与 API `/signals/{trade_id}/strength` 在 10 笔分市场样本上保持一致。

## 7. 发现的问题

`/api/v1/signals/{trade_id}/strength` 的 `trade_id` 位于 URL path 中，若使用 PowerShell / 表单风格的 `UrlEncode`，空格会被编码成 `+`，FastAPI path 参数不会把 `+` 还原成空格，导致查不到交易。

正确方式：

- 使用路径编码：`[System.Uri]::EscapeDataString($tradeId)`
- 或在前端使用 `encodeURIComponent(tradeId)`

错误方式：

- 不要用会把空格编码成 `+` 的 query/form 编码方式处理 path 参数。

## 8. 当前结论

PostgreSQL 基线可用：

- 容器可启动
- migration 在 head
- 现有 PG 数据可查
- crypto CSV 小样本导入幂等
- API 可读取 PG
- 10 笔分市场样本一致性通过

下一步应进入 Web 产品化闭环：

1. 将首页 / 回测页从 demo JSON 切到真实 API。
2. 前端所有 `trade_id` path 调用统一用 `encodeURIComponent`。
3. 补充一个自动化 PG/API 一致性验收脚本，避免以后手工跑。
4. 再推进 W24 分市场 tier 阈值与权重校准。

## 9. Web 接真实 API 第一轮

本次已完成回测页信号强弱 path 编码修正与 smoke 验证。

代码修改：

- `web/js/app.js`
  - 新增 `signalStrengthUrl(tradeId)`。
  - 新增 `fetchSignalStrength(tradeId)`。
  - `trade_id` path 参数统一使用 `encodeURIComponent(tradeId)`。
- `web/backtest.html`
  - 点击交易明细行时，调用 `FengJiApp.fetchSignalStrength(trade.trade_id)`。
  - 状态栏显示单笔信号强弱：定式、品种、评级、bucket 样本数、分数。
  - URL 历史参数改为 `URLSearchParams` 生成，避免手写拼接。

验证：

```text
node --check web\js\app.js
ENCODE_TRADE_ID_OK
GET /web/backtest.html -> 200
GET /web/js/app.js -> 200, contains encodeURIComponent + signalStrengthUrl
GET /api/v1/backtests/trades?market=CRYPTO&symbol=BTCUSDT&limit=1 -> 200
GET /api/v1/signals/{encodeURIComponent(trade_id)}/strength -> 200
trade_id match -> true
python -m pytest tests -q -> 72 passed
```

当前状态：

- `backtest.html` 已读真实 API。
- 点击交易行会再次读取单笔 signal strength。
- `trade_id` 路径编码问题已在前端收敛到共享 helper。
- `index.html` 仍通过 `/api/v1/monitor/domestic/latest-opens` 读取 API；当未配置 `DOMESTIC_PAPER_STATE_PATH` 时后端会 fallback 到 demo 数据，这是后续要接真实国内 paper_state 的点。

## 10. PG/API 一致性自动化脚本

已新增：

- `scripts/smoke_pg_api_consistency.py`

脚本行为：

1. 预检 `DATABASE_URL` 指向的 PostgreSQL 端口，PG 未启动时快速失败并提示运行 `docker compose up -d`。
2. 分市场从 `trade_context_snapshots` 抽样，默认 `A_STOCK=4,CRYPTO=3,US_STOCK=3`。
3. 启动临时本地 `uvicorn`，请求真实 HTTP API `/api/v1/signals/{trade_id}/strength`。
4. 使用 path 编码 `urllib.parse.quote(..., safe="")`，确保空格编码为 `%20` 而不是 `+`。
5. 直接从 PG 读取 snapshot 与 bucket stats，计算预期字段，再与 API 返回比对。

当前验证：

```text
python scripts\smoke_pg_api_consistency.py
PG_API_CONSISTENCY_OK=10/10
A_STOCK=4
CRYPTO=3
US_STOCK=3
base_url=http://127.0.0.1:8022
python -m py_compile scripts\smoke_pg_api_consistency.py
python -m pytest tests -q -> 72 passed
```

结论：

- 手工 10 笔一致性验收已固化为可重复 smoke。
- 后续改动 PG schema、context scoring、API route 或前端 path 编码后，应运行该脚本。
