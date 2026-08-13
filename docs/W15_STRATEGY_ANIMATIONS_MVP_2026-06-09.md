# W15 定式动画 MVP（第一段）— 2026-06-09

## 范围

对齐 `FJLHXM-V1.md` **P2-W15 / WEB-ANIM-001~004** 第一段：Web 端 **约 10 秒循环** SVG/CSS 示意动画，**不逐根还原真实 K 线**，不反向修改峰极OS/定式规则。

## 已实现

### 动画模块

- `web/js/strategy_animations.js` — `FengJiStrategyAnim.buildSvg()` / `mountStage()`
- `web/js/config.js` — `STRATEGY_ANIM.ENGINE_VERSION` / `DURATION_SEC`
- 覆盖 **DS01–DS09**；专业档额外展示 **TOTAL** 卡片
- 每段动画展示：阵营底色切换、峰极折线、触发虚线、启动棍、止损线；各定式有差异化装饰（如 DS03 假峰虚线、DS04 夹棍、DS09 D1+M15）

### 页面交互（WEB-ANIM-003）

- `web/strategies.html` — 卡片内自动循环播放
- 点击卡片 → 弹层放大预览
- 弹层支持 **暂停/播放**、Esc / 遮罩关闭
- 标注 `engine_version`（当前 `fengji_core@0.1.0`）

### 设计同步

- `scripts/build_fjlhxm_ui_pen.py` — 策略卡片预览文案改为「10s SVG」
- 运行 `python scripts/build_fjlhxm_ui_pen.py` 可重建 `FJLHXM-UI.pen`（画布级待 Pencil MCP）

## 验证

```powershell
python -m pytest tests/test_w15_strategy_animations.py -q
node --check web/js/strategy_animations.js
node --check web/js/app.js
```

本地：`scripts/start_fengji_local.ps1` → http://127.0.0.1:8000/web/strategies.html

### 浏览器 smoke

`scripts/smoke_w15_strategies_browser.py`

```powershell
pip install playwright
python -m playwright install chrome
python scripts/smoke_w15_strategies_browser.py --auto-server
python scripts/smoke_w15_strategies_browser.py --offline-skip-browser
```

截图：

- `runtime/web_validation/w15_strategies_browser_smoke.png`
- `runtime/web_validation/w15_strategies_modal_smoke.png`

## 仍待 W15

- Lottie 资产替换 / `strategy_animations` 表或对象存储（WEB-ANIM-005）
- TOTAL / DS 分镜精修与多语言

## 页面联动（第二段）

- `FengJiApp.strategyAnimPageUrl()` / `strategyAnimLinkHtml()` — 深链 `strategies.html?strategy=DSxx&open=1`
- **首页** `index.html`：图表工具栏定式标签链至对应动画
- **回测** `backtest.html`：定式下拉旁「动画示意」、成交详情「查看定式动画示意」
- **策略学堂** `strategies.html`：`applyDeepLink()` 滚动并自动弹层

## 边界

- 示意级动画仅供客户理解结构，不得作为回测或实盘依据
- 规则变更时需同步更新 `ENGINE_VERSION` 并重制动画

## O1 · Lottie 示意动画（已实现）

工程链路已就绪（`strategy_animations.js` · `MODE: auto` · Lottie 优先 / SVG 回退）。

**2026-06-10**：已由 `scripts/build_strategy_lottie_illustrations.py` 生成 **10 段示意 Lottie**（对齐下方分镜要点与 SVG/CSS 时序），策略学堂默认走 Lottie 播放；验收 `run_o1_lottie_placeholder_acceptance.py` **PASS**。

重建命令：

```powershell
python scripts/build_strategy_lottie_illustrations.py
python scripts/run_o1_lottie_placeholder_acceptance.py
```

### 可选 · 设计方精修 drop-in

若后续要更高保真分镜，设计方可**同名覆盖**下列文件：

| 文件 | 定式 | 示意要点（对齐 SVG 模块） |
|------|------|---------------------------|
| `DS01.json` | 挫棍式 | 挫棍 → 启动棍 |
| `DS02.json` | 阴阳相吃 | 红阳吃阴 / 蓝阴吃阳 |
| `DS03.json` | 二四棒 | 假峰虚线 + active 结构 |
| `DS04.json` | 夹棍 | K1/K2/K3 夹棍 |
| `DS05.json` | 指形 | K2 可能成极 |
| `DS06.json` | 外扩峰 | 转势授权 + 外扩峰 |
| `DS07.json` | 共振 | 同向延续 / 反向并轨 |
| `DS08.json` | 否认确定 | 五点 + 否认/确定 |
| `DS09.json` | 九重天 | D1 阵营 + M15 二次攻击 |
| `TOTAL.json` | 峰极总定式 | DS01–08 合一，不反仓 |

**技术约束**

- 目录：`web/assets/lottie/`（与 `manifest.json` 列表一致）
- 画布：**160×88**，**30fps**，**loop**，时长约 **10s**（与 `DURATION_SEC` 一致）
- 不得改 Web 定式/OS/风控规则；仅替换动画资产

**验收命令**

```powershell
python scripts/run_o1_lottie_placeholder_acceptance.py
# 或分步：
python -m pytest tests/test_w15_strategy_animations.py -q
python scripts/smoke_w15_strategies_browser.py --auto-server
# 期望 lottie_count=9（专业档卡片），engine_tag 含 Lottie
```

**占位验收报告**：`runtime/web_validation/o1_lottie_placeholder_acceptance.json`（2026-06-12 **PASS**）

占位重建（仅开发/bootstrap）：`python scripts/build_strategy_lottie_placeholders.py`
