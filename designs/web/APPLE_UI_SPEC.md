# 峰极量化 Web · Apple 设计语言规范

> 对应 FJLHXM-V1 §4 IA + W08/W13/W14。  
> **设计稿优先**：`FJLHXM-UI.pen`（Apple V4 · 简洁大方）审阅通过后，再同步 `web/` 实现。

## 设计原则（Apple HIG Dark · 全屏黑底）

- **统一深色**：6 屏均为 `#000000` 背景，卡片 `#161617`（对齐 V4 第 6 屏规范）
- **清晰**：大标题 + 次级说明，信息层级分明
- **留白**：内容区 max-width 1080px，卡片间距 16px
- **深度**：细分割线 `#38383a`，无重阴影

## 设计令牌

| 令牌 | 浅色 | 深色 |
|------|------|------|
| 背景 | `#f5f5f7` | `#000000` |
| 卡片 | `#ffffff` | `#1c1c1e` |
| 主文字 | `#1d1d1f` | `#f5f5f7` |
| 次级文字 | `#86868b` | `#98989d` |
| 强调蓝 | `#007aff` | `#0a84ff` |
| 涨/绿 | `#34c759` | `#30d158` |
| 跌/红 | `#ff3b30` | `#ff453a` |
| 红阵营 | `#e53935` | `#ff453a` |
| 蓝阵营 | `#007aff` | `#0a84ff` |

字体：`-apple-system, SF Pro Display, PingFang SC`

圆角：卡片 18px · 按钮 pill · 输入 8px

## 页面清单（6 屏 MVP）

| 页面 | 文件 | FJLHXM 需求 |
|------|------|-------------|
| 首页 Dashboard | `web/index.html` | **国内模拟监测** · 最新开仓 + 日线 K 线（同花顺式拖动/缩放） |
| 历史回测 | `web/backtest.html` | WEB-BT-* · K线 + 明细 + 指标 |
| 模拟监测 | `web/monitor.html` | WEB-MON-* · Phase 3 占位 |
| 策略学堂 | `web/strategies.html` | §4.7 动画占位 |
| 订阅定价 | `web/pricing.html` | §3 角色权限 |
| 共享样式 | `web/css/apple.css` | Design Token |

## 本地预览

```powershell
cd "C:\Users\guangwan\Documents\New project"
docker compose up -d
$env:PYTHONPATH="src;packages/fengji_core;services"
python -m uvicorn services.api.main:app --port 8001 --host 127.0.0.1
# 浏览器打开 http://127.0.0.1:8001/web/index.html
```

## pencil.dev 后续

在 `FJLHXM-UI.pen` 中建议新增 frame（Apple 浅色/深色各一套）：

1. Dashboard · 1440×900
2. Backtest Detail · 1440×900（左 K 线 + 右明细）
3. Monitor List · 1440×900
4. Strategy Academy（策略学堂）· 1440×900
5. Pricing · 1440×900

组件：Segmented Control、Glass Nav、Strategy Card、Metric Tile、Trade Row。
