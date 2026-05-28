# AGENTS

## 2026-05-27 总工程接手规则

### 项目身份

本项目是峰极OS总工程，覆盖峰极OS最高宪法、阵营转换、DS01-DS09 九大定式、挂单器、实盘数据、国内/海外服务器部署、模拟实盘、回测验证和 Cursor/Codex 跨工具接手。

### 每次接手必须先读取

按顺序读取：

1. `PROJECT_CONTEXT.md`
2. `AGENTS.md`
3. `TODO.md`
4. `CHANGELOG.md`
5. `README.md`
6. `峰极OS_最高宪法.md`
7. `峰极OS_阵营转换判断.md`
8. `峰极OS_九大定式规则总纲.md`
9. `峰极OS_CANONICAL_RULES.md`
10. `docs/CANONICAL_RULES.md`
11. `docs/FENGJI_TOTAL_PATTERN_SPEC.md`
12. `docs/PLAN_A_ROADMAP.md`
13. 当前任务涉及的源代码、测试、结果文件和服务器脚本

接手后必须先只读检查：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
git status --short
Get-ChildItem -Force
```

### 必须遵守的总原则

1. 所有定式必须在峰极OS最高宪法之下执行策略。
2. 所有九大定式必须遵守 `峰极OS_CANONICAL_RULES.md`、`docs/CANONICAL_RULES.md`、`docs/FENGJI_TOTAL_PATTERN_SPEC.md` 中的规则总纲。
3. 峰极线、阵营转换、active high/low、合法假峰/假极必须来自峰极OS硬化结构，不允许用普通 high/low 替代。
4. 不允许凭空补全旧聊天内容；旧聊天不可见时，只能写“待确认”。
5. 不允许删除未知文件、清空目录、重写整个项目或批量回滚。
6. 不允许改错峰极线、阵营转换、九大定式核心逻辑；有疑问先用沙盒图和测试验证。
7. 不允许把 API Key、Token、服务器密码、私钥、完整 webhook 写入任何代码、文档、日志或输出。
8. 修改代码前必须先说明修改计划、影响范围、预期验证方式。
9. 修改代码后必须更新 `CHANGELOG.md` 和 `TODO.md`，并写清验证结果或未验证原因。

### 代码修改边界

- 优先复用现有模块，不在模拟盘脚本里复制一套策略旧逻辑。
- 修改 DS01-DS09、OS、雷达、挂单器后，必须检查相关测试和服务器同步范围。
- 不能为了让回测结果更好而修改市场规则、手续费、滑点、T+1、保证金、夜盘/日盘规则。
- 当前真实交易权限未开放，不能把模拟触发改成真实下单。

### 文档与安全边界

- 需要记录服务器时，只写“国内服务器：已配置，具体地址见本地私密配置文件”这类占位描述。
- 需要记录配置时，只写字段名称和用途，不写真实密钥。
- 如发现敏感信息，只写“存在敏感信息，需脱敏”，不得显示具体内容。
- 不确定的规则写“待确认”，不要编造。

## 项目身份

这是峰极量化项目 / FengJi OS / 峰极总定式工程。当前重点是方案 A：引擎稳定化，目标是稳定峰极 OS、DS01-DS09、峰极总定式、回测、模拟实盘、挂单模拟和沙盒图审计。

## AI 工作总原则

1. 所有定式必须在峰极 OS 最高宪法之下执行策略。
2. 先读取项目上下文，再修改任何文件。
3. 先证据、后判断、再改动。
4. 只改与用户当前目标直接相关的文件。
5. 不删除、不回滚、不覆盖用户或其他会话已有改动，除非用户明确要求。
6. 不凭空继承旧聊天。旧聊天不可见时，只能依据项目文件、日志、结果、用户本轮明确描述和可验证证据。
7. 不把 API Key、Token、密码、私钥、Webhook 完整 URL 写进代码、文档或日志。

## 每次接手项目必须先读取

按顺序读取：

1. `PROJECT_CONTEXT.md`
2. `AGENTS.md`
3. `TODO.md`
4. `CHANGELOG.md`
5. `README.md`
6. `峰极OS_最高宪法.md`
7. `峰极OS_阵营转换判断.md`
8. `峰极OS_九大定式规则总纲.md`
9. `峰极OS_CANONICAL_RULES.md`
10. `docs/CANONICAL_RULES.md`
11. `docs/FENGJI_TOTAL_PATTERN_SPEC.md`
12. `docs/PLAN_A_ROADMAP.md`
13. 需要修改的具体代码文件和对应测试文件

接手后先运行只读检查：

```powershell
git status --short
Get-ChildItem -Force
```

如果用户问“当前是否正常运行”，必须实时检查服务器进程、日志、数据新鲜度，不能用旧记忆直接回答。

## 代码修改规则

- 使用现有代码风格和现有模块边界。
- 策略逻辑优先改 `src/quant/*.py` 或对应统一入口，不要在模拟盘脚本里复制一套旧逻辑。
- 每次改 DS01/DS03/DS05/DS07/OS 后，必须检查雷达、挂单、模拟盘是否引用同一套逻辑。
- 修改定式时必须同步或新增测试。
- 不允许把几何 high/low 直接当峰/极，必须读取 OS Runtime 输出字段或硬化节点。
- 不允许恢复旧 DS07 逻辑。
- 不允许为了让回测收益更好而修改风控、手续费、滑点、保证金、T+1 等既定市场规则。
- 不允许把模拟实盘改成真实下单。

## 文档修改规则

- 修改文档前先读取旧内容。
- 更新文档要保留已有重要信息，不能无理由整段删掉历史命令和审查结论。
- 不确定的规则必须写“待确认”，不能编造。
- 文档中的运行命令要区分 PowerShell、CMD、Linux Bash。
- PowerShell 中运行带空格路径的 Python 必须使用 `& "完整路径\python.exe"`。
- 文档中不得出现完整 webhook URL、账号密码、API Token、私钥。

## 测试与验证规则

优先验证：

```powershell
python -m pytest tests\test_os_engine.py tests\test_ds01.py tests\test_ds03.py tests\test_ds05.py -q
python -m pytest tests\test_pending_orders.py tests\test_futures_pending_orders.py tests\test_radar_ds04.py tests\test_radar_ds05.py tests\test_radar_ds06.py tests\test_radar_ds07.py tests\test_radar_ds08.py -q
```

如果 `python` 或 `pytest` 不可用：

- 先检查 PATH 和 Python 安装。
- 可尝试完整路径：`C:\Users\guangwan\AppData\Local\Programs\Python\Python312\python.exe`。
- 若 Codex 沙箱提示 `Access is denied`，不要判断为代码失败，要让用户在本地 PowerShell 执行或申请明确权限。

策略验证优先级：

1. 单元测试。
2. 小样本回测。
3. 沙盒图人工检查。
4. 模拟盘日志与挂单触发检查。
5. 服务器运行状态检查。

## 禁止事项

- 禁止删除已有文件或清空目录。
- 禁止 `git reset --hard`、`git checkout -- .`、批量回滚、批量删除，除非用户明确要求并确认风险。
- 禁止把旧文档里的旧 OS、旧峰极线、旧阵营规则直接搬回代码。
- 禁止把 raw high/low 直接叫峰/极。
- 禁止跳过峰极 OS 审计直接判断定式信号。
- 禁止把模拟盘改成真实下单。
- 禁止在日志、文档、代码里写入密钥、Token、密码、完整 Webhook。
- 禁止凭空猜测旧聊天内容。

## 远程服务器规则

- 海外服务器和国内服务器状态是时间敏感事实，必须实时 SSH 检查。
- 同步文件前先列出将同步的文件清单。
- 只同步变更相关文件，不做无差别覆盖。
- 重启前先确认进程；重启后必须复查进程和日志。
- 国内期货/A股模拟盘不得因为修数据泵而改变买卖规则。
