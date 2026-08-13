# W18 用户自选品种 Web 接入报告

日期：2026-06-05

范围：

- `web/backtest.html`
- `web/js/app.js`
- `web/css/apple.css`
- `scripts/build_fjlhxm_ui_pen.py`
- `FJLHXM-UI.pen`

## 1. 结论

W18 第三段已完成：历史回测页已接入自选品种回测入口。用户在虚拟货币市场输入 symbol 后，可提交自选回测请求，页面展示 `ingesting / backtesting / backtested / failed` 状态；成功后自动切换到该 symbol 并加载回测图。

本轮没有修改峰极OS、阵营转换、DS01-DS09、挂单器、模拟实盘、国内服务器或海外服务器运行逻辑。

## 2. Web 变更

`web/js/app.js` 新增：

- `submitCustomInstrumentRequest()`
- `fetchCustomInstrumentRequest()`

`web/backtest.html` 新增：

- `customInstrumentPanel`
- `customSubmitBtn`
- `customRequestStatus`
- `submitCustomInstrument()`
- `waitForCustomRequest()`

交互边界：

- 面板仅在 `CRYPTO` 市场显示。
- 免费档禁用提交。
- 标准/专业档可提交。
- 成功后自动执行 `loadAll()`。

`web/css/apple.css` 新增：

- `.custom-instrument-panel`
- `.custom-instrument-copy`
- `.custom-instrument-status`

## 3. 设计同步

`scripts/build_fjlhxm_ui_pen.py` 的 02 Backtest 屏已增加自选回测状态栏。

已重新生成：

```text
FJLHXM-UI.pen
```

文件级校验：

```text
python scripts\finalize_fjlhxm_ui_pen.py
OK · FJLHXM-UI.pen finalized
```

## 4. 验证结果

前端语法：

```text
node --check web\js\app.js
node --check web\js\config.js
node --check web\js\chart.js
BACKTEST_INLINE_SCRIPT_PARSE_OK=1
```

后端相邻测试：

```text
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
17 passed in 15.55s
```

HTTP smoke：

```text
WEB_CUSTOM_STATIC_OK
CUSTOM_WEB_CREATED 3eddba70-7b7a-450b-a24a-9464ddd1612f backtesting XRPUSDT 5ba07e3c-bee4-4fae-9176-575322832bcc
CUSTOM_WEB_POLL 0 backtested succeeded
W18_CUSTOM_WEB_SMOKE_OK request=3eddba70-7b7a-450b-a24a-9464ddd1612f symbol=XRPUSDT job=5ba07e3c-bee4-4fae-9176-575322832bcc
```

## 5. 已知限制

1. 当前 Web 表单入口在回测页内，不是独立“自选品种”页面。
2. 服务端配额计数未完成，仍只做免费档阻断。
3. 当前只支持 crypto D1 拉数；1H/15m、A 股、国内期货自选仍未开放。
4. `enable_paper` 到模拟观察 watchlist 未完成。
5. 浏览器截图级验收未完成；本轮是静态/HTTP/语法级验证。

## 6. 下一步

- W18 第四段：服务端配额计数，标准档 3 次/月、专业档 20 次/月。
- W18 第五段：补 `enable_paper` 到模拟观察 watchlist 的安全链路。
- 后续再决定是否扩展 1H/15m、A 股和国内期货。
