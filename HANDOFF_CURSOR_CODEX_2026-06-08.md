# Cursor / 新 Codex 账号接手存档

日期：2026-06-08

项目路径：

```text
C:\Users\guangwan\Documents\New project
```

## 1. 项目身份

这是峰极OS总工程 + FJLHXM-V1 Web 产品化工程。

项目不是从零开发，也不是允许重写峰极OS。当前阶段是：

1. 保护峰极OS最高宪法、阵营转换、DS01-DS09 九大定式不被误改。
2. 保持国内/海外模拟实盘、雷达、挂单器、OS state 固化链路稳定。
3. 按 `FJLHXM-V1.md` 和 `TODO.md` 的优先级继续推进网页端产品化。

## 2. 新会话必须先读取

新 Cursor / 新 Codex 账号接手后，必须先按顺序读取：

1. `AGENTS.md`
2. `.cursor/rules/project.mdc`
3. `PROJECT_CONTEXT.md`
4. `TODO.md`
5. `CHANGELOG.md`
6. `FJLHXM-V1.md`
7. `README.md`
8. `峰极OS_最高宪法.md`
9. `峰极OS_九大定式规则总纲.md`
10. `峰极OS_阵营转换判断.md`
11. `峰极OS_挂单器与模拟实盘说明.md`
12. `峰极OS_服务器与部署说明.md`
13. `峰极OS_数据与回测说明.md`
14. `docs/CANONICAL_RULES.md`
15. `docs/FENGJI_TOTAL_PATTERN_SPEC.md`
16. `docs/PLAN_A_ROADMAP.md`

接手后先只读执行：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
git status --short
Get-ChildItem -Force
```

## 3. 2026-06-08 最新状态

### 已完成的关键修复

1. **国内 15m 数据停更已恢复**  
   国内 watchdog 报 `15m data stale for 4770 min` 后，已确认是 `data_manager_futures.py` 假活。已重启数据泵，34 个国内期货短代码更新成功，失败 0。`watchdog_domestic.ps1` 已增加 stale-data restart 保护。

2. **BNBUSDT DS01 误开多已阻断**  
   BNBUSDT 2026-06-07 DS01 多头误触发根因有两层：
   - 裸阵营问题：2026-05-31 `BLUE_TO_RED` 后 `camp/camp_confirmed=red`，但 `red_ext/active_low` 为空，旧代码仍允许 DS01/DS03 授权。
   - 时间隔离问题：第一次修正后，`add_ds01()` 仍用当前 D1 行的 `cur.active_low` 授权昨日信号；2026-06-08 才确认出来的 `red_ext=556.46` 反向授权了 2026-06-07 信号。

   当前已修：
   - `packages/fengji_core/fengji_core/ds03.py`：DS03 真峰启动必须同时存在进攻峰和防守极。
   - `src/fengji_total_radar.py`：DS01/DS03 裸阵营不再生成可挂单信号。
   - `src/fengji_total_radar.py:add_ds01()`：DS01 授权改为使用上一根已完成 D1 的 `prev.camp/prev.active_low/prev.active_high`，当前 D1 只负责触价检测。

3. **国内/海外服务器已同步**
   - 海外 OS state rebuild：`ok=48 error=0 total=48`
   - 国内 OS state rebuild：`ok=102 error=0 total=102`
   - 海外 BNBUSDT 全量雷达刷新后：`DS01 = BLOCKED_OS_INCOMPLETE / missing_red_ext`
   - 海外 `pending_orders.csv` 中已无 BNBUSDT。
   - 国内 `radar.csv` / `pending_orders.csv` 于 2026-06-08 11:09 刷新完成。

4. **国内状态检查 JSON 风险已解决**
   `runtime\fengji_futures\state_futures_v2.json` 经 Python 严格校验是合法 UTF-8 JSON。问题来自 `scripts/check_domestic_status.ps1` 用 PowerShell 默认编码读取 UTF-8 JSON。已改为 `Get-Content -Encoding UTF8` 并设置输出编码；同步国内后复跑通过：`STATE_JSON_OK symbols=34`。

### 本地验证

本轮最后相关验证：

```powershell
python -m pytest tests\test_fengji_total_radar_ds01.py tests\test_ds03.py tests\test_radar_setup_keys.py tests\test_radar_ds07.py -q
```

结果：

```text
18 passed
```

## 4. 当前工作树边界

当前工作树长期较脏，不能 `git add .`，不能批量回滚。

与本轮核心相关的文件包括：

- `src/fengji_total_radar.py`
- `packages/fengji_core/fengji_core/ds03.py`
- `src/quant/ds03.py`
- `scripts/rebuild_os_state_all.py`
- `scripts/check_domestic_status.ps1`
- `tests/test_fengji_total_radar_ds01.py`
- `tests/test_ds03.py`
- `tests/test_radar_setup_keys.py`
- `tests/test_radar_ds07.py`
- `docs/CANONICAL_RULES.md`
- `docs/DS03_CALIBRATION.md`
- `峰极OS_最高宪法.md`
- `峰极OS_九大定式规则总纲.md`
- `CHANGELOG.md`
- `TODO.md`

不要回滚这些文件中的既有相关修正；不要把无关 `data/`、运行日志、密钥、临时结果混入提交。

## 5. 下一步执行顺序

### 下一步 1：审计 BNBUSDT 旧误触发是否进入模拟盘 state — **已完成 2026-06-08**

只读审计结论：无 open position；1 笔已平仓误触发 `BNBUSDT-DS01-D1-long-ebfd3882424f3fc6`（setup=`signal=20260606000000|trigger=584.43`）已备份并标记 `audit_invalid`；`signal=20260607000000|trigger=610.54` 仅 radar 阻断行，未成交。权益未自动回滚，`equity_rollback_candidate` 待人工审批。详见 `CHANGELOG.md` 2026-06-08「海外 BNBUSDT DS01 旧误触发只读审计与 audit_invalid 标记」。

### 下一步 2：继续审计旧模拟持仓状态 — **已完成 2026-06-08（国内段）**

国内只读审计完成：PG 无 open、无 DS01 open；symbol 层 9 笔历史 audit_invalid 保留；新标记 EGUSDT DS04 long、MAUSDT DS04 long 方向冲突 2 笔。open 6→4，pending 方向冲突 0。详见 CHANGELOG「国内旧模拟持仓只读审计与 EG/MA 方向冲突标记」。海外 BNB 权益回滚候选仍待人工审批。

### 下一步 3：裁定 D1 定式止损是否必须收盘确认

当前国内挂单监控口径是按定式周期 K 线的实时 high/low 触价止损。需要用户最终裁定：

- DS01/DS03/DS05 这类 D1 定式，止损是否允许 D1 日内触价即平仓？
- 还是必须等 D1 完整收盘确认后才能平仓？

未裁定前，不要擅自改止损执行规则。

### 下一步 4：回到 Web 产品化主线

策略安全闭环后，继续 `TODO.md` 中的：

- `W16-WS 生产化加固第二段`
- 正式 Auth/JWT 替换演示身份
- 服务端连接指标/审计日志
- 频道拆分或 delta 消息
- 浏览器级 WebSocket smoke

## 6. 服务器安全边界

服务器连接、API Key、Webhook、Token、密码等只允许在本地私密配置、环境变量或服务器控制台中存在。任何文档、代码、日志、聊天输出都不得写明文密钥。

远程操作边界：

- 同步文件前先列清单。
- 只同步本任务相关文件。
- 重启前查进程，重启后复查进程和日志。
- 国内/海外服务器状态必须实时检查，不能用旧记录当实时结论。
- 模拟实盘和真实实盘必须隔离。
- 不得把模拟触发改成真实下单。

## 7. 可直接复制给 Cursor / 新 Codex 的提示词

```text
你现在接手项目：

C:\Users\guangwan\Documents\New project

这是峰极OS总工程 + FJLHXM-V1 Web 产品化工程。你不能自动继承旧 Codex 聊天，所以必须以项目文件为准，不要凭空补全旧聊天内容。

请先只读读取以下文件，并输出“项目接手报告”，不要先改代码：

1. AGENTS.md
2. .cursor/rules/project.mdc
3. PROJECT_CONTEXT.md
4. TODO.md
5. CHANGELOG.md
6. HANDOFF_CURSOR_CODEX_2026-06-08.md
7. FJLHXM-V1.md
8. README.md
9. 峰极OS_最高宪法.md
10. 峰极OS_九大定式规则总纲.md
11. 峰极OS_阵营转换判断.md
12. docs/CANONICAL_RULES.md
13. docs/FENGJI_TOTAL_PATTERN_SPEC.md
14. docs/PLAN_A_ROADMAP.md

接手后先执行：

git status --short

当前最新关键状态：

- BNBUSDT 2026-06-07 DS01 误开多已经在代码层修正：裸红阵营缺 red_ext/active_low 不得授权；DS01 只能用上一根已完成 D1 的 OS 状态授权，当前 D1 只负责触价检测。
- 国内/海外服务器已同步本轮 OS/DS01/DS03/雷达修正，并重建 OS state：海外 48/48 ok，国内 102/102 ok。
- 海外 BNBUSDT 当前 radar 为 BLOCKED_OS_INCOMPLETE / missing_red_ext，pending 中无 BNBUSDT。
- 国内 state_futures_v2.json 本体是合法 UTF-8 JSON；之前 ConvertFrom-Json 报错已通过修 scripts/check_domestic_status.ps1 的 UTF-8 读取解决。

现在请执行下一步，优先级最高：

只读审计海外 BNBUSDT 2026-06-07 DS01 旧误触发是否已经写入模拟盘状态或历史事件。检查：

- runtime/fengji_paper/state.json
- runtime/fengji_pending_orders/state.json
- runtime/fengji_pending_orders/events.jsonl（如果存在）
- pending_order_monitor.log

搜索关键字：

- BNBUSDT
- DS01
- signal=20260607000000
- trigger=584.43
- trigger=610.54

如果没有残留，只记录结果并更新 TODO/CHANGELOG。

如果已经写入 open position 或 fill，不要删除历史；先说明计划并备份，再标记 audit_invalid / audit_invalid_entries，原因写明：

DS01 was authorized by incomplete red camp or retroactive current-bar defense before 2026-06-08 fix.

禁止事项：

- 不允许真实下单。
- 不允许输出 API Key、Token、服务器密码、Webhook。
- 不允许删除未知文件。
- 不允许 git reset / 批量回滚。
- 不允许改峰极OS最高宪法、阵营转换或 DS01-DS09 核心逻辑，除非先给出证据和修改计划。
- 不允许把 data/、日志、密钥、无关大文件混入提交。
```

