# W18 Watchlist Runtime Binding 只读观察快照

日期：2026-06-05

## 范围

本次实现 `paper_watchlist.pending_runtime` 的只读 runtime binding 快照。它读取 watchlist 与本地 D1/H1/M15 CSV，生成观察状态与数据新鲜度，不写现有 `paper_state`，不启动雷达/挂单/模拟盘，不接真实下单。

## 已完成

- 新增 `services/watchlist_runtime.py`：
  - `build_watchlist_runtime_snapshot()`
  - `build_watchlist_runtime_snapshots()`
  - 读取 D1/H1/M15 本地 CSV 最新 K 线。
  - 输出 `runtime_status=ready/data_missing/unsupported_market`。
  - 输出 `current_price`、`latest_time`、各周期 `latest_bar`、行数、CSV 路径。
- 新增 API：
  - `GET /api/v1/paper-watchlist/runtime?user_id=...&status=pending_runtime`
- 当前 snapshot 模式：
  - `mode=read_only_observation`
  - `runtime_binding=csv_snapshot_only`
- 对 CRYPTO 以 M15 最新 close 作为优先当前价，缺 M15 时回退 H1，再回退 D1。

## 安全边界

- 不修改峰极OS、阵营转换、DS01-DS09。
- 不写国内/海外模拟盘 `paper_state`。
- 不触发挂单。
- 不创建模拟成交。
- 不启动或重启任何服务器进程。
- 当前只做 CSV 快照，不声明策略实时信号已经接入。

## 验证

```powershell
python -m py_compile services\watchlist_runtime.py services\api\main.py tests\test_custom_instruments.py
python -m pytest tests\test_custom_instruments.py -q
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
```

结果：

- `tests\test_custom_instruments.py`：21 passed
- W18/W11 相关回归：30 passed

本地 runtime smoke：

```text
W18_WATCHLIST_RUNTIME_SMOKE_OK count=1 status=ready symbol=XRPUSDT latest=2026-06-05 01:15:00 price=1.156
```

## 当前限制

- 目前只是 CSV 数据 ready 快照，不是峰极总定式实时信号。
- 暂未把 watchlist 展示接入 Web 监测页。
- 暂未提供暂停/取消观察接口。
- 暂未把 `pending_runtime` 改为持久化 `runtime_bound`，避免误以为已经接入真实运行调度。

## 下一步

1. Web 监测页接入 `GET /api/v1/paper-watchlist/runtime`。
2. 页面上明确区分：
   - 用户观察候选
   - 实际模拟持仓
   - 国内/海外固定模拟盘运行态
3. 补暂停/取消观察接口。
4. 后续再接峰极总定式只读信号引擎。
