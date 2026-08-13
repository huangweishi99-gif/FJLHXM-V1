# W08 / Wave5 P4 · Pencil 9 屏验收 — 2026-06-11

## 范围

- `FJLHXM-UI.pen` + `scripts/build_fjlhxm_ui_pen.py` / `finalize_fjlhxm_ui_pen.py`
- Web 9 屏：`index` / `backtest` / `monitor` / `strategies` / `pricing` / `symbol` / `login` / `community` / `payment`
- 结构化验收：`scripts/w08_pencil_acceptance.py`

## 一键执行

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"

# 文件级 + pen 重建
python scripts/w08_pencil_acceptance.py --preflight-only

# 全量（pen 重建 + 静态分离 + JS + HTTP 10 路由）
python scripts/w08_pencil_acceptance.py --auto-server --port 8036

pytest tests/test_w08_pencil_acceptance.py -q
```

报告：`runtime/web_validation/w08_pencil_acceptance.json`

## 9 屏映射

| # | Pencil 帧 | Web | 必需 |
|---|-----------|-----|------|
| 01 | Dashboard | `/web/index.html` | ✅ |
| 02 | Backtest | `/web/backtest.html` | ✅ |
| 03 | Monitor | `/web/monitor.html` | ✅ |
| 04 | Strategies | `/web/strategies.html` | ✅ |
| 05 | Pricing | `/web/pricing.html` | ✅ |
| 06 | Symbol Chart | `/web/symbol.html` | ✅ |
| 07 | Auth | `/web/login.html` | ✅ |
| 08 | Community | `/web/community.html` | ✅ |
| 09 | Payment | `/web/payment.html?pay=standard\|pro` | ✅ |

## 实跑记录（2026-06-11 · 补全 Web 截图代理）

| 步骤 | 结果 |
|------|------|
| `w08_pencil_acceptance.py --auto-server --web-screenshots` | **通过** — 必需 17/17 |
| `pen_json_layout` | **9 帧** 1280×832 |
| `web_screenshot_proxy` | **9/9** → `runtime/web_validation/p4_web_screenshots/` |
| Pencil MCP | **pending** — 须在编辑器中打开 `.pen` |

**补验 MCP**：Cursor 中打开 `FJLHXM-UI.pen` → 对 01–09 帧 `get_screenshot` 与 `p4_*.png` 人工对照。

## 实跑记录（2026-06-11）

| 步骤 | 结果 |
|------|------|
| `finalize_fjlhxm_ui_pen.py` | **通过** — 9 屏 + 审阅说明 |
| 订阅/付款分离静态检查 | **通过** |
| Web JS `node --check` ×4 | **通过** |
| HTTP 10 路由（含 payment std/pro） | **通过** |
| Pencil MCP `get_screenshot` | **待确认** — MCP 报「需在 Pencil 编辑器中打开文件」 |
| `pytest tests/test_w08_pencil_acceptance.py -q` | **3 passed** |

**结论**：**文件级 / HTTP 级 17/17 必需项通过**；**画布截图级待 Pencil app 连接 MCP 后补验**。

## 画布级补验（运维/设计）

1. 在 Cursor 中打开 `FJLHXM-UI.pen`（Pencil 扩展需连接）
2. 对 01–09 各帧调用 MCP `get_screenshot` 对照 Web 截图
3. 通过后可将验收报告中 `pencil_canvas_mcp` 标为 ok

## 边界

- 不反向修改峰极OS / DS / 风控
- 不把密钥、收款码真实 URL 写入文档
- 未连接 Pencil MCP 时**不得**声称画布截图级验收已完成
