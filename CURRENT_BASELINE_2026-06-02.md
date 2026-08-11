# CURRENT_BASELINE_2026-06-02

> 生成时间：2026-06-02 15:28（Asia/Shanghai）  
> 用途：给新的 Codex / Cursor 会话提供当前可验证基线。  
> 安全：本文档不记录 API Key、Token、服务器密码、天勤账号密码、完整 webhook 或私钥。

## 1. 项目定位

本项目是 **峰极OS总工程 / 峰极量化联合项目 V1**。

当前不是单一定式脚本项目，而是完整产品化工程：

- 峰极OS最高宪法
- 红蓝阵营与转势状态机
- DS01-DS09 九大定式
- 峰极总定式合一引擎
- 数据泵、回测、雷达、挂单器、模拟实盘
- 国内服务器 / 海外服务器模拟运行
- FJLHXM-V1 Web 订阅式模拟实盘产品化

核心产品目标见 `FJLHXM-V1.md`：把已成型的峰极OS、九大定式、回测与模拟实盘链路，产品化成可订阅的 Web 模拟实盘平台。V1 不接真实自动下单。

## 2. 必读文件

新会话接手前必须先读：

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `TODO.md`
4. `CHANGELOG.md`
5. `FJLHXM-V1.md`
6. `峰极OS_最高宪法.md`
7. `峰极OS_九大定式规则总纲.md`
8. `峰极OS_阵营转换判断.md`
9. `峰极OS_挂单器与模拟实盘说明.md`
10. `峰极OS_服务器与部署说明.md`
11. `峰极OS_数据与回测说明.md`
12. `docs/CANONICAL_RULES.md`
13. `docs/FENGJI_TOTAL_PATTERN_SPEC.md`
14. `.cursor/rules/project.mdc`

## 3. 权威源与边界

- 策略权威源：`packages/fengji_core/fengji_core`
- `src/quant`：兼容层，不是新的权威实现。
- 文档权威：根目录峰极OS规则文档 + `docs/CANONICAL_RULES.md` + `docs/FENGJI_TOTAL_PATTERN_SPEC.md`。
- 所有定式必须服从峰极OS最高宪法。
- 不允许用 raw high/low 冒充峰/极。
- 不允许把模拟盘改成真实下单。
- 不允许为了收益率改规则、手续费、滑点、保证金或市场时间。

## 4. 本地状态

### 4.1 测试

本地验证命令：

```powershell
python -m pytest tests -q
```

结果：

```text
72 passed in 18.71s
```

### 4.2 工作区

`git status --short` 当前约 469 项变更/未跟踪项。

结论：

- 工作区处于活跃开发态。
- 严禁回滚、清空、批量删除或 `git reset --hard`。
- 大量数据文件、结果文件、Web/API/脚本/文档都在变更中。
- 后续应先建立归档/提交边界，再做大规模改动。

## 5. 2026-06-02 已完成修复

### 5.1 模拟盘 state 锁争用

已完成：

- 海外 `src/overseas_paper_monitor.py`：锁外扫描，锁内只重载最新 state 并落盘。
- 国内 `remote_domestic_optimize/峰极总定式01-08国内期货A股模拟实盘.py`：同样调整为锁外扫描、锁内落盘。
- 海外、国内均已部署并重启对应模拟盘。

验证：

- 海外 `state.json.lock` timeout 最后停在 2026-06-02 14:09。
- 国内 `state_futures_v2.json.lock` timeout 最后停在 2026-06-02 14:22。
- 两端后续 pending monitor 持续输出 `checked=...`。

### 5.2 国内 watchdog 数据泵误报

问题：

- 数据泵正常抓取后会睡眠 300 秒。
- 旧 watchdog 心跳阈值只有 120 秒，导致正常等待期间误判 `data_manager down`。

已完成：

- `data_manager_futures.py`：长睡眠期间每 60 秒刷新心跳。
- `scripts/watchdog_domestic.ps1`：心跳阈值放宽到 420 秒。
- `scripts/ensure_single_data_manager.ps1`：避免用旧心跳掩盖“实际 Python 进程数为 0”的手动重启场景。

验证：

- 国内 watchdog 15:23-15:28 连续 `watchdog ok`。
- 数据泵心跳 15:28:22，age 约 9 秒。

### 5.3 天勤账号密码脱敏迁移

已完成：

- `data_manager_futures.py` 移除 `TQ_PHONE` / `TQ_PASS` 的代码默认明文。
- `remote_domestic_optimize/data_manager_futures.py` 同步移除默认明文。
- 改为读取 `TQ_PHONE` / `TQ_PASS` 环境变量。
- Windows 下增加用户/机器环境变量注册表兜底。
- 本机和国内服务器已配置环境变量。

验证：

- 本地 `py_compile` 通过。
- 本地 `pytest tests -q`：72 passed。
- 国内服务器远程 `py_compile` 通过。
- 国内数据泵已用新版启动，PID=3760。
- 国内远端 `data_manager_futures.py` 不含旧账号/密码字面量。
- 项目扫描未发现 `sk-...` 明文、旧天勤密码字面量、完整飞书 hook URL。

## 6. 国内服务器运行态

检查时间：2026-06-02 15:28。

模块状态：

```text
data_manager      python_count=1
radar_loop        python_count=1
pending_monitor   python_count=1
paper_monitor     python_count=1
```

数据状态：

- `data/15m` 最新文件停在 2026-06-02 15:12 左右。
- 15:15 后国内期货日盘已收盘，数据泵进入 idle，属正常。
- 心跳仍持续刷新，15:28:22 `pid=3760 idle`。

运行文件：

```text
runtime/fengji_radar/radar.json           2026-06-02 15:21:21
runtime/fengji_pending_orders/orders      2026-06-02 15:21:21
runtime/fengji_futures/state_futures_v2   2026-06-02 14:50:54
```

watchdog：

```text
15:23-15:28 连续 watchdog ok
```

pending monitor：

```text
15:27-15:28 持续 checked=19 bars=27 filled=0 closed=0 skipped=1
```

## 7. 海外服务器运行态

检查时间：2026-06-02 15:28。

模块状态：

```text
data_manager.py                  count=1
fengji_radar_order_loop.py       count=1
fengji_pending_order_monitor.py  count=2
overseas_paper_monitor.py        count=1
```

说明：

- `fengji_pending_order_monitor.py count=2` 是 bash 包装进程 + python 子进程，不按双开处理。
- 海外挂单监控仍可能有较高 CPU，原因是 5 秒轮询 + 动态止损/价格检查。当前不建议降频，避免影响模拟触发速度。

数据状态：

- `data/15m` 最新文件约 2026-06-02 15:22。
- `runtime/fengji_radar/radar.json` 约 2026-06-02 15:24。
- `runtime/fengji_pending_orders/pending_orders.json` 约 2026-06-02 15:24。
- `runtime/fengji_paper/state.json` 约 2026-06-02 15:12。

锁状态：

- `pending_order_monitor.log` 最后锁超时仍停在 2026-06-02 14:09。
- 15:27-15:28 持续 `checked=11 prices=13 filled=0 closed=0 skipped=8`。

## 8. FJLHXM-V1 产品化状态

`FJLHXM-V1.md` 定义了产品方向：Web 端为 V1 唯一客户端，移动端 V1.1+ 暂缓。

已具备：

- OS / DS01-DS09 核心规则与回测。
- 雷达、挂单器、模拟实盘链路。
- FastAPI 初步骨架。
- chart-bundle JSON / 测试。
- Web 静态页面初版。
- PostgreSQL / Alembic / context stats 相关代码骨架。
- 上下文快照与信号强弱统计离线引擎。

未完成：

- PostgreSQL 正式作为主数据层。
- `backtest_jobs` / `signals` / `paper_accounts` 等产品表完整闭环。
- CLI 回测结果与 PG/API 抽样 10 组一致性验收。
- Web 首页、回测详情、监测列表真正接后端数据。
- 用户自选品种拉数 -> 回测 -> 模拟观察管线。
- 订阅付费与 Feature Gate。
- 定式 10 秒讲解动画。

## 9. 当前主要风险

1. 工作区未提交项过多，必须先建立归档/提交边界。
2. `CHANGELOG.md` / `TODO.md` 已多次追加，后续需要整理而不是继续无限堆叠。
3. 服务器状态是时间敏感事实，每次判断“正常运行”都要实时 SSH。
4. 国内期货数据泵现在依赖服务器环境变量，迁移机器或计划任务账户时必须重新配置。
5. 海外挂单监控 CPU 偏高仍需观察，但目前锁争用已缓解。
6. 产品化阶段不能再把 CSV/JSON 运行态当长期主存储，必须推进 PG。

## 10. 下一步建议

按优先级执行：

1. **建立提交/归档边界**
   - 先把当前已验证的安全修复、watchdog 修复、state 锁修复、文档更新归成一组。
   - 大数据文件和结果文件不要混进同一组逻辑提交。

2. **PostgreSQL 基线验收**
   - `docker compose up -d`
   - `alembic upgrade head`
   - 导入小样本 crypto / A 股 / context stats
   - 抽样 10 组 CLI vs PG/API 数值一致。

3. **Web 产品化主线**
   - 让 `web/` 首页和回测页读取真实 API。
   - chart-bundle 继续作为前端 K 线标准输入。
   - 优先完成首页 -> 回测详情 -> 监测列表闭环。

4. **运行态继续观察**
   - 国内 watchdog 是否继续无误报。
   - 海外挂单监控 CPU 是否持续过高。
   - 国内/海外 pending monitor 是否重新出现 lock timeout。

## 11. 下一次会话建议提示词

```text
请先读取 CURRENT_BASELINE_2026-06-02.md、AGENTS.md、PROJECT_CONTEXT.md、TODO.md、CHANGELOG.md、FJLHXM-V1.md，以及峰极OS最高宪法和九大定式规则总纲。当前项目处于 FJLHXM-V1 产品化阶段，不要回滚大量未提交文件，不要输出任何密钥。请先确认本地测试、国内/海外运行态，然后继续 PostgreSQL 基线验收。
```
