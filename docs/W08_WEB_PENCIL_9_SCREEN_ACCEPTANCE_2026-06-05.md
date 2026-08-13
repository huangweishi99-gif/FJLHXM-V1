# W08 Web/Pencil 9 屏定稿验收报告

日期：2026-06-05

范围：

- `FJLHXM-UI.pen`
- `docs/FJLHXM_UI_DESIGN_FREEZE.md`
- `scripts/build_fjlhxm_ui_pen.py`
- `scripts/finalize_fjlhxm_ui_pen.py`
- `web/index.html`
- `web/backtest.html`
- `web/monitor.html`
- `web/strategies.html`
- `web/pricing.html`
- `web/symbol.html`
- `web/login.html`
- `web/community.html`
- `web/payment.html`

## 1. 结论

W08 文件级、生成脚本级、Web 页面级、HTTP 路由级和静态资源链接级验收通过。

Pencil MCP 画布级验收未完成，原因是当前 MCP 无法连接运行中的 Pencil app：

```text
transport not connected to app: cursor
```

因此当前状态为：

- 文件级定稿：通过。
- Web 9 页面存在性：通过。
- 设计生成脚本校验：通过。
- Web 静态语法检查：通过。
- HTTP 9 页访问：通过。
- 资源/站内链接检查：通过。
- Pencil 画布截图级验收：待确认。

## 2. 9 屏映射验收

| # | 设计帧 | Web 页面 | 当前状态 |
|---|--------|----------|----------|
| 01 | Dashboard | `index.html` | 通过 |
| 02 | Backtest | `backtest.html` | 通过 |
| 03 | Monitor | `monitor.html` | 通过 |
| 04 | Strategies | `strategies.html` | 通过 |
| 05 | Pricing | `pricing.html` | 通过 |
| 06 | Symbol Chart | `symbol.html` | 通过 |
| 07 | Auth | `login.html` | 通过 |
| 08 | Community | `community.html` | 通过 |
| 09 | Payment | `payment.html?pay=standard|pro` | 通过 |

## 3. Pencil 文件级验收

执行：

```powershell
python scripts\finalize_fjlhxm_ui_pen.py
```

结果：

```text
Updated FJLHXM-UI.pen · 9 glass-gold screens · Glass Gold V5 · 定稿
定稿屏位 (10 frames):
  · 01 · Dashboard · Glass Gold V5 · 定稿
  · 02 · Backtest · Glass Gold V5 · 定稿
  · 03 · Monitor · Glass Gold V5 · 定稿
  · 04 · Strategies · Glass Gold V5 · 定稿
  · 05 · Pricing · Glass Gold V5 · 定稿
  · 06 · Symbol Chart · Glass Gold V5 · 定稿
  · 07 · Auth · Glass Gold V5 · 定稿
  · 08 · Community · Glass Gold V5 · 定稿
  · 09 · Payment · Glass Gold V5 · 定稿
  · Glass Gold V5 · 定稿 · 审阅说明
OK · FJLHXM-UI.pen finalized
```

同步修复：

- `scripts/finalize_fjlhxm_ui_pen.py` 的 `EXPECTED` 第 9 屏从旧的 `08 · Community Pay` 修正为 `09 · Payment`，与 `docs/FJLHXM_UI_DESIGN_FREEZE.md` 和 `scripts/build_fjlhxm_ui_pen.py` 保持一致。

## 4. Web 页面存在性与标题

| 页面 | HTTP | 标题 |
|------|------|------|
| `index.html` | 200 | 峰极量化 |
| `backtest.html` | 200 | 峰极量化 |
| `monitor.html` | 200 | 峰极量化 |
| `strategies.html` | 200 | 峰极定式动画演示 |
| `pricing.html` | 200 | 峰极量化 · 订阅 |
| `symbol.html` | 200 | 峰极量化 · 品种详情 |
| `login.html` | 200 | 峰极量化 · 登录 |
| `community.html` | 200 | 峰极量化 · 加入交流群 |
| `payment.html?pay=standard` | 200 | 峰极量化 · 订阅付款 |
| `payment.html?pay=pro` | 200 | 峰极量化 · 订阅付款 |

## 5. 订阅与二维码分离

检查结果：

- 免费入口：`login.html?mode=register&intent=free` 存在于 `web/js/config.js`。
- 标准入口：`payment.html?pay=standard` 存在于 `web/js/config.js`。
- 专业入口：`payment.html?pay=pro` 存在于 `web/js/config.js`。
- 权限来源：`web/js/app.js` 读取 `localStorage.fj-plan`，并移除 URL 中的 `?plan=`，避免链接伪造档位。
- `community.html` 未发现 `community.html?pay`、微信收款码、订阅档位混用。
- `payment.html` 包含微信收款码和付款备注提示。
- `community.html` 只作为 QQ 群入口。

说明：`payment.html` 出现“订阅档位”属于付款页正常文案，不是登录页订阅档位选择。

## 6. 静态语法检查

执行：

```powershell
node --check web\js\app.js
node --check web\js\config.js
node --check web\js\chart.js
node --check web\js\monitor-chart.js
python -m py_compile scripts\build_fjlhxm_ui_pen.py scripts\finalize_fjlhxm_ui_pen.py
```

结果：通过。

## 7. 资源与站内链接检查

临时启动：

```powershell
python -m http.server 8041 --bind 127.0.0.1
python runtime\web_validation\check_web_links.py
```

结果：

```text
WEB_LINK_CHECK_OK=13/13
```

覆盖：

- `web/css/apple.css`
- `web/js/config.js`
- `web/js/app.js`
- `web/js/chart.js`
- `web/js/monitor-chart.js`
- `web/assets/qr/qq-group.jpg`
- `web/assets/qr/wechat-pay.png`
- 关键站内页面跳转
- 外部 lightweight-charts CDN

## 8. 已知限制

1. Pencil MCP 未连接运行中的 Pencil app，因此没有完成画布截图级验收。
2. 本轮没有做 Playwright 截图级视觉验收。
3. 本轮没有启动 FastAPI/PG 做回测和监测真实 API 深度验收；这属于 W13/W14/W16。
4. 本轮没有修改峰极OS、阵营转换、DS01-DS09、挂单器、服务器运行逻辑。

## 9. 下一步

进入 P0 Web 核心路径验收：

1. W13：首页 Dashboard 验收，重点检查 7 个最新开仓卡片、实际主力合约、净盈亏、K 线日期、守护点和旧冲突持仓过滤。
2. W14：回测页产品化验收，重点检查 1/3/5 年、K线/OS、交易明细、桶详情、同桶样本、CSV 导出和 PG/API/CLI 一致性。
3. W16：模拟监测页验收，重点检查四市场监测、paper_state、旧状态过滤和国内/海外运行态显示。
4. W17-demo：登录/订阅/付款/交流群演示流点击回归。

## 10. 禁止事项

- 不允许声称 Pencil 画布截图级验收已完成。
- 不允许把本轮 Web/Pencil 验收结果反向用于修改峰极OS或九大定式。
- 不允许把二维码、收款码、运行态日志、大 CSV、密钥配置混入后续提交。
