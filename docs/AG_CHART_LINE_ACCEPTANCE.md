# 沪银(AG) 峰极连线 Web 验收 — 2026-06-12

## 范围

- 品种：沪银 `AG` / `data/futures/1d/沪银.csv`
- OS state：`runtime/fengji_os_state/AG_1d.json`（`used_os_state=True`）
- Web 口径：`chart_line.build_hardened_segments`（实线 + 橡皮筋 zigzag）
- 对照：沙盒 `draw_hardened_line`（紫线，全部 hardened_nodes）

## 验收命令

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
$env:PYTHONPATH = "src;packages/fengji_core;services"
python scripts\plot_ag_chart_line_acceptance.py
python scripts\audit_fengji_chart_lines.py --symbols AG
python -m pytest tests\test_chart_bundle.py::test_ag_provisional_trail_zigzag_through_rebound tests\test_chart_line_audit.py -q
```

## 关键结论（2026-06-12）

| 项 | 值 |
|---|---|
| 最后实线锚点 | 2026-05-28 LOW **17455**（`BLUE_PEAK`） |
| 橡皮筋 | 3 段：5/28→5/29 峰 18588 → 6/11 谷 15105 → 6/12 最新 K |
| `audit_hardened_segments` | 0 违规 |
| `audit_web_vs_sandbox` | 0 违规 |
| 最新 K | 2026-06-12 |

## 产物

- 对照图：`results/sandbox/ag_chart_line_acceptance_20260612/AG_D1_chart_line_acceptance.png`
- 审计 JSON：`results/sandbox/ag_chart_line_acceptance_20260612/ag_chart_line_audit.json`

## 说明

- **实线**只连已固化 hardened 锚点（FAILED-only 假点剔除，必要时区间桥接）。
- **橡皮筋**不是最后锚点到最新 K 的直线；须沿区间极值 zigzag 至最新 K（AG 5/28 谷后反弹不能抄近路）。
- Web 本地验收：`http://127.0.0.1:8001/web/index.html` + Ctrl+F5；页脚应显示「固化 21 段 · 橡皮筋 3 段」量级。

## 待办

- [ ] 国内 API 同步最新 `chart_line.py` 并远端复验
- [ ] Playwright 截图级 Web 验收（可选）
