# W18 Watchlist 暂停/取消观察

日期：2026-06-05

## 范围

本段完成用户自选品种 `paper_watchlist` 的暂停/取消观察能力，并让 Web 监测页的服务端观察候选行可以执行“取消观察”。

本段只处理 Web/API/PG 产品化链路：

- 不写 `paper_state`。
- 不创建模拟成交。
- 不触发挂单。
- 不修改峰极OS、阵营转换、DS01-DS09 或风控逻辑。
- 不同步国内/海外服务器运行态。

## 实现

### DB helper

文件：`services/db/paper_watchlist.py`

- 新增状态常量：
  - `pending_runtime`
  - `paused`
  - `cancelled`
- 新增 `update_paper_watchlist_status()`：
  - 按 `watchlist_id + user_id` 精确过滤，避免跨用户修改。
  - 更新 `status` 与 `updated_at`。
  - 在 `params_json` 中记录 `runtime_binding` 和 `last_status_change`。
  - 物理保留记录，不删除历史审计线索。

### API

文件：`services/api/main.py`

- 新增请求模型 `PaperWatchlistStatusUpdate`。
- 新增接口：

```text
PATCH /api/v1/paper-watchlist/{watchlist_id}
```

请求体：

```json
{
  "user_id": "demo-user",
  "status": "cancelled"
}
```

当前只允许：

- `paused`
- `cancelled`

不允许通过该接口恢复为 `pending_runtime`，避免前端误把暂停项重新纳入 runtime 观察池。恢复观察后续应做成明确的“重新观察/重新提交”流程。

### Web

文件：

- `web/js/app.js`
- `web/monitor.html`

改动：

- `web/js/app.js` 新增 `updatePaperWatchlistStatus()`，封装 PATCH 接口。
- `web/monitor.html` 的服务端 runtime 行保留 `watchlist_id`。
- 只有 `source="runtime"` 的观察候选行显示“取消观察”按钮。
- 点击“取消观察”后把状态改为 `cancelled`，再刷新监测页。
- 本地浏览器 watchlist 的“移除”逻辑保持不变。

### 设计同步

文件：

- `scripts/build_fjlhxm_ui_pen.py`
- `FJLHXM-UI.pen`

改动：

- 03 Monitor 样例表格增加“操作”列。
- 用户观察候选样例显示“取消观察”。
- 已重新生成并 finalize `FJLHXM-UI.pen`。

## 验证

已执行：

```powershell
python -m py_compile services\db\paper_watchlist.py services\api\main.py services\watchlist_runtime.py
python -m pytest tests\test_custom_instruments.py -q
node --check web\js\app.js
node -e "const fs=require('fs'); const html=fs.readFileSync('web/monitor.html','utf8'); const blocks=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]); new Function(blocks.join('\n')); console.log('MONITOR_INLINE_SCRIPT_PARSE_OK=1');"
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py -q
python scripts\build_fjlhxm_ui_pen.py
python scripts\finalize_fjlhxm_ui_pen.py
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
```

结果：

- `tests/test_custom_instruments.py`：24 passed
- monitor 相关回归：28 passed
- W18/W11 相关回归：33 passed
- `MONITOR_INLINE_SCRIPT_PARSE_OK=1`
- `FJLHXM-UI.pen finalized`

## 限制

- 当前仍是演示级 `user_id` / `plan_id`，正式用户权限要等 W17-prod Auth/订阅体系接入。
- 当前只支持取消/暂停登记，不支持从 Web 恢复为 `pending_runtime`。
- Runtime 仍为 CSV snapshot only，未接正式峰极OS实时信号引擎。
- Crypto 之外的用户自选品种仍待后续扩展。

## 下一步

1. W18 剩余生产化：把 watchlist runtime 从 CSV snapshot 过渡到正式信号引擎/监测 Job，但必须继续与真实/模拟成交隔离。
2. 扩展用户自选品种市场范围：A股、期货、更多 crypto 数据源。
3. 进入 W16-WS：把监测页轮询升级为 WebSocket/准实时观察。
