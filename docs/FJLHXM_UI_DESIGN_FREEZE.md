# FJLHXM-UI 设计定稿 · Glass Gold V5

| 字段 | 内容 |
|------|------|
| 定稿日期 | 2026-06-03 |
| 设计文件 | `FJLHXM-UI.pen` |
| 生成脚本 | `scripts/build_fjlhxm_ui_pen.py` |
| 定稿命令 | `python scripts/finalize_fjlhxm_ui_pen.py` |
| 视觉 | 深色径向底 · 毛玻璃组块 · 细金边 `#D4AF37` / 深蓝 `#2d5098` |

## 屏位地图（1280×832）

| # | 设计帧 | 坐标 (x, y) | Web 页面 | 说明 |
|---|--------|-------------|----------|------|
| 01 | Dashboard | (3200, 0) | `index.html` | 国内模拟监测大屏 |
| 02 | Backtest | (3200, 920) | `backtest.html` | 历史回测 · PG/桶详情 |
| 03 | Monitor | (4720, 0) | `monitor.html` | 自选池 · 模拟监测列表 |
| 04 | Strategies | (4720, 920) | `strategies.html` | 策略学堂 |
| 05 | Pricing | (6240, 920) | `pricing.html` | 三档订阅 · 标准/专业含流程说明 |
| 06 | Symbol Chart | (7760, 920) | `symbol.html` | 品种详情 · BTCUSDT 大标题 + 周期 Tab |
| 07 | Auth | (7760, 0) | `login.html` | 登录/注册 · 三链页脚 |
| 08 | Community | (9280, 0) | `community.html` | 默认仅 QQ 群 |
| 09 | Payment | (9280, 920) | `payment.html?pay=*` | 订阅付款 · 独立微信收款页 |

审阅说明帧：`(3200, -260)`。

## 订阅三档 · 与 Web 一致（定稿）

| 档位 | 订阅入口 | 付款后唯一落地页 |
|------|----------|------------------|
| 免费 | `login.html?mode=register&intent=free` | `backtest.html` |
| 标准 | `payment.html?pay=standard` | `monitor.html` |
| 专业 | `payment.html?pay=pro` | `backtest.html` |

权限只认 `localStorage.fj-plan`；URL `?plan=` 不参与鉴权。

## 导航（全屏统一）

`首页 · 回测 · 模拟监测 · 策略学堂 · 定价 · 交流群`（Web 顶栏「订阅」对应设计稿「定价」）

## 定稿后维护规则

1. **改 Web 布局/关键控件** → 先改 `build_fjlhxm_ui_pen.py`，再跑 `finalize_fjlhxm_ui_pen.py`。
2. **勿手改 `.pen` 后被脚本覆盖**；手工微调须同步回生成脚本。
3. **画布验收**需 Pencil MCP 连通后截图；否则记「文件级定稿，画布待确认」。
4. **交流群与付款页分离**：`community.html` 只保留 QQ 群二维码；微信收款码只允许在 `payment.html?pay=*` 独立付款页出现。
