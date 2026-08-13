# W16 模拟监测页产品化验收报告

日期：2026-06-05

范围：

- `web/monitor.html`
- `web/symbol.html`
- `web/js/monitor-chart.js`
- `web/js/app.js`
- `web/js/config.js`
- `services/api/main.py`
- `services/monitor_domestic.py`
- `tests/test_monitor_domestic.py`
- `tests/test_monitor_quotes.py`

## 1. 结论

W16 模拟监测页 API/DOM/数据级验收通过。

本轮未修改峰极OS、阵营转换、DS01-DS09、挂单器或模拟实盘策略执行逻辑。验收只覆盖 Web 模拟监测展示链路：

- 监测列表。
- 自选品种。
- 档位限制。
- 国内 paper_state 最新持仓。
- 四市场最新价格。
- 国内持仓详情页 K 线 overlay。
- 旧冲突持仓过滤。

浏览器截图级验收仍待 Chrome/Playwright 可用后补。

## 2. 监测页能力

### 2.1 自选品种与档位

`web/monitor.html` 已复核：

- 读取 `localStorage.fj-plan` 对应订阅档。
- 免费档、标准档、专业档使用 `web/js/config.js` 中的统一权限配置。
- 自选数量与回测共享名额。
- 添加/移除品种写入 `FengJiApp.loadWatchlist()` / `saveWatchlist()`。
- 自选品种支持四市场目录：期货、A股、虚拟货币、美股。

### 2.2 行情与持仓

监测页同时读取：

- `/api/v1/monitor/domestic/latest-opens`
- `/api/v1/monitor/quotes`

列表字段包含：

- 品种。
- 开仓时间。
- 开仓价格。
- 目前价格。
- 信号强弱。
- 状态。
- 净盈亏。
- 详情入口。

状态说明：

- `持仓`：来自国内 `paper_state`。
- `观察`：自选品种且行情可读。
- `无数据`：行情读取失败。
- `空仓`：非自选且无持仓。

## 3. 本轮修复

### 3.1 持仓详情页非自选跳转问题

问题：

- 监测列表会自动合并国内 `paper_state` 当前持仓。
- 这些真实持仓不一定在用户自选列表内。
- 原 `symbol.html` 要求 `symbol` 必须存在于自选列表，否则直接跳回 `monitor.html`。
- 结果：监测页展示出来的真实持仓，点击“详情”可能打不开。

修复：

- `web/symbol.html` 允许打开非自选但来自持仓列表的品种详情。
- 非自选持仓详情页中，“移除自选”按钮改为“返回监测”。
- 匹配持仓时兼容 `EBUSDT` 与 `EB` 这类期货 symbol/code 差异。

### 3.2 详情页现价改为优先读取真实 quote

问题：

- `symbol.html` 原先现价主要来自 `MONITOR_DEMO_QUOTES`。
- 对国内实际主力合约和当前 Web 日线 CSV 来说，演示价可能与当前数据不一致。

修复：

- `symbol.html` 新增 `refreshQuote()`，优先调用 `/api/v1/monitor/quotes`。
- quote 不可用时才回退 `MONITOR_DEMO_QUOTES` 或开仓价。

## 4. API Smoke

临时启动 FastAPI 后，HTTP smoke 结果：

```text
API_HEALTH_OK
QUOTES_OK 200 [
  ('FUTURES', 'PVC', True, 'PVC.csv'),
  ('A_STOCK', '000021', True, '000021_1D_qfq.csv'),
  ('CRYPTO', 'ETHUSDT', True, 'ETHUSDT.csv'),
  ('US_STOCK', 'AAPL', True, 'AAPL_1D.csv')
]
LATEST_OPENS_OK 200 paper_state 7 EBUSDT
DOMESTIC_CHART_OK 200 苯乙烯 205 True True
```

详情页前三个当前持仓抽样：

```text
LATEST_OPENS_OK 200 paper_state 7
DETAIL_QUOTE_OK EBUSDT True 苯乙烯.csv
DETAIL_CHART_OK EBUSDT 200 205 True True
DETAIL_QUOTE_OK LCUSDT True 碳酸锂.csv
DETAIL_CHART_OK LCUSDT 200 171 True True
DETAIL_QUOTE_OK SHUSDT True 烧碱.csv
DETAIL_CHART_OK SHUSDT 200 214 True True
```

## 5. 测试

执行：

```powershell
python -m pytest tests\test_monitor_domestic.py tests\test_monitor_quotes.py tests\test_chart_bundle.py tests\test_context_queries.py -q
```

结果：

```text
8 passed
```

前端脚本解析：

```text
web/monitor.html:INLINE_OK=1
web/symbol.html:INLINE_OK=1
web/js/app.js:SCRIPT_OK
web/js/config.js:SCRIPT_OK
web/js/monitor-chart.js:SCRIPT_OK
```

## 6. 已知限制

1. 未做浏览器截图级验收。
2. 监测页仍是轮询刷新；准实时 WebSocket 属于后续 `W16-WS`。
3. 当前真实持仓只来自国内 `paper_state`；海外 crypto 运行态如需在同一监测页展示，需要增加统一监测状态聚合 API。
4. `symbol.html` 的 1H/15m 分段按钮目前仍使用同一个 `domestic/chart` 日线图表接口；多周期监测图属于后续增强。
5. 本轮不复核持仓是否符合具体定式开仓逻辑；策略审计需按峰极OS沙盒图另行执行。

## 7. 下一步

进入 W17-demo 登录/订阅/付款演示流验收：

- 登录。
- 注册。
- 免费 7 天试用。
- 定价页。
- 标准/专业付款页。
- QQ 交流群页。
- `localStorage.fj-plan` 唯一权限源。
- URL `?plan=` 不授予权限。
- 订阅 CTA 路由与落地页。

---

## 8. V1 功能齐全结案（2026-06-12）

**裁定**：监测页 V1 功能齐全，可作为订阅硬界线划分前的验收基线。

### V1 已交付

| 能力 | 状态 |
|------|------|
| 四市场全库品种搜索 + 市场筛选 + 下拉添加 | ✅ |
| 自选添加/移除（与回测共享名额） | ✅ |
| 国内 `paper_state` 持仓合并展示 | ✅ |
| `/api/v1/monitor/quotes` 现价 | ✅ |
| 状态：持仓 / 观察 / 观察候选 / 数据待补 | ✅ |
| 品种详情 `symbol.html` + K 线 overlay | ✅ |
| W18 runtime 观察 / 取消观察 / 信号预览 | ✅ |
| 专业档 WS + delta + 断线重连 + 轮询 fallback | ✅ |
| 合规：只观察、不向交易所发单 | ✅ |

### 留 W17-prod / V1.1（不阻塞 V1 结案）

- 服务端 subscription plan **硬 gate**（当前以 `localStorage.fj-plan` + 前端名额为主）
- 档位延迟 **服务端强制**（15min / 1min / WS）
- ~~WEB-MON-001 四市场分栏 Tab~~ → **2026-06-14 已交付**
- ~~WEB-MON-004 ledger 拒单明细、WEB-MON-007 通知、WEB-MON-008 结构合格徽章~~ → **2026-06-14 V1+ 已交付**
- ~~每用户 paper 账户只读摘要~~ → **2026-06-14 V1+ 已交付**（PG `paper_accounts` 独立撮合仍留 V1.1）
- 海外 crypto 与 domestic 统一监测聚合 API

### 2026-06-12 回归

```powershell
python -m pytest tests\test_monitor_symbol_search.py tests\test_monitor_domestic.py tests\test_monitor_quotes.py tests\test_w16_monitor_browser_smoke.py -q
```

结果：**8 passed, 1 skipped**（浏览器 live smoke 需 `RUN_W16_BROWSER_SMOKE=1`）。

本地 API：`/api/v1/monitor/domestic/latest-opens` 可读持仓；`/api/v1/backtests/symbol-summary` 四市场全量目录可挂接。
