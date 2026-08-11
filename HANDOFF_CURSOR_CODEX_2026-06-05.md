# Cursor / 新 Codex 账号接手存档

日期：2026-06-05

项目路径：

```text
C:\Users\guangwan\Documents\New project
```

## 当前项目状态

本项目是峰极OS总工程 + FJLHXM-V1 Web 产品化工程。当前不是从零开发，也不是重写峰极OS；当前阶段是按 `FJLHXM-V1.md` 的重要性排序计划继续推进 Web 产品化。

当前最新计划版本：

- `FJLHXM-V1.md`：`1.4.15-draft`
- W18 用户自选品种管线已完成到“多市场只读 runtime”：
  - crypto：D1/H1/M15 拉数、回测、watchlist、runtime、只读信号预览、缓存、新鲜度展示已完成。
  - A股/国内期货/美股：watchlist runtime 已支持 D1 只读 `ready/data_missing` 快照。
- 当前最高优先级：
  - `W16-WS`：WebSocket/准实时监测推送。

## 必须先读取的文件

新 Cursor / 新 Codex 会话开始后，必须先按顺序读取：

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `TODO.md`
4. `CHANGELOG.md`
5. `FJLHXM-V1.md`
6. `README.md`
7. `.cursor/rules/project.mdc`
8. `峰极OS_最高宪法.md`
9. `峰极OS_九大定式规则总纲.md`
10. `峰极OS_阵营转换判断.md`
11. `docs/W18_WATCHLIST_RUNTIME_MULTI_MARKET_2026-06-05.md`

## 当前下一步任务

执行 `W16-WS`，目标是把当前监测页轮询能力升级为 WebSocket/准实时推送能力。

建议第一段只做最小闭环：

1. 梳理当前监测页数据源：
   - `web/monitor.html`
   - `web/js/app.js`
   - `services/api/main.py`
   - `services/monitor_domestic.py`
   - `services/watchlist_runtime.py`
2. 设计 WebSocket 消息 schema：
   - quote update
   - domestic paper position update
   - watchlist runtime update
   - cache freshness update
   - error/status update
3. 在 FastAPI 中增加只读 WebSocket endpoint。
4. 前端监测页增加 WS 连接、断线重连、轮询 fallback。
5. 保持安全边界：
   - 不写 `paper_state`
   - 不触发挂单
   - 不真实下单
   - 不修改峰极OS、阵营转换、DS01-DS09、风控参数
6. 增加测试：
   - API WebSocket smoke
   - 前端 JS 语法检查
   - monitor 相关 pytest 回归

## 上一段完成记录

上一段 W18 多市场 runtime 已完成，相关文件：

- `services/watchlist_runtime.py`
- `tests/test_custom_instruments.py`
- `docs/W18_WATCHLIST_RUNTIME_MULTI_MARKET_2026-06-05.md`
- `TODO.md`
- `CHANGELOG.md`
- `FJLHXM-V1.md`

验证结果：

```powershell
python -m py_compile services\watchlist_runtime.py services\api\main.py
python -m pytest tests\test_custom_instruments.py -q
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py -q
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
```

结果：

- `tests\test_custom_instruments.py`：32 passed
- monitor 回归：36 passed
- W18/W11 相关回归：45 passed
- 本地真实 CSV smoke：`000021/LC/LH/AAPL/XRPUSDT` 均为 `ready`

## 禁止事项

- 禁止凭空继承旧聊天内容，必须以项目文件为准。
- 禁止删除未知文件。
- 禁止 `git add .`。
- 禁止重写整个项目。
- 禁止修改峰极OS最高宪法、阵营转换、DS01-DS09、挂单器、模拟实盘逻辑，除非用户明确要求并先做审计。
- 禁止把 API Key、Token、服务器密码、交易所密钥、完整 webhook 写入代码、文档、日志或输出。
- 禁止把 WebSocket 推送做成真实下单或模拟成交写入。

## 给 Cursor / 新 Codex 的直接提示词

请复制下面这段到 Cursor 或新 Codex 账号：

```text
你正在接手我的峰极OS总工程 / FJLHXM-V1 Web 产品化项目。

项目路径是：
C:\Users\guangwan\Documents\New project

请先不要修改任何文件。先按顺序读取：
1. AGENTS.md
2. PROJECT_CONTEXT.md
3. TODO.md
4. CHANGELOG.md
5. FJLHXM-V1.md
6. README.md
7. .cursor/rules/project.mdc
8. 峰极OS_最高宪法.md
9. 峰极OS_九大定式规则总纲.md
10. 峰极OS_阵营转换判断.md
11. HANDOFF_CURSOR_CODEX_2026-06-05.md
12. docs/W18_WATCHLIST_RUNTIME_MULTI_MARKET_2026-06-05.md

读取后输出一份“项目接手报告”，必须包含：
- 当前项目状态
- 已完成到哪个 W 阶段
- 当前最高优先级
- 本次准备修改哪些文件
- 不会触碰哪些核心规则和服务器运行态
- 准备运行哪些测试

当前最新状态：
- FJLHXM-V1.md 已更新到 1.4.15-draft。
- W18 用户自选品种管线已完成到多市场只读 runtime。
- 下一步是 W16-WS：WebSocket/准实时监测推送。

请继续执行 W16-WS 的第一段最小闭环：
1. 梳理 monitor 页当前轮询数据源。
2. 设计 WebSocket 消息 schema。
3. 增加只读 WebSocket endpoint。
4. 前端 monitor 页接入 WS，并保留轮询 fallback。
5. 增加测试和 smoke。

安全边界：
- 不写 paper_state。
- 不触发挂单。
- 不真实下单。
- 不修改峰极OS最高宪法、阵营转换、DS01-DS09、风控参数。
- 不把 API Key、Token、服务器密码、完整 webhook 写进任何文件或输出。
- 当前工作树很脏，禁止 git add .，只能改本轮 W16-WS 相关文件。

完成后更新：
- TODO.md
- CHANGELOG.md
- FJLHXM-V1.md
- 如涉及 Web UI，检查是否需要同步 scripts/build_fjlhxm_ui_pen.py 和 FJLHXM-UI.pen。
```

## 建议第一条执行命令

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
git status --short
```

然后再读取上述文档，不要直接开改。
