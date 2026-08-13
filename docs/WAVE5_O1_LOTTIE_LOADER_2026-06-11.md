# Wave5 O1 · W15 Lottie 加载器 — 2026-06-11（更新 2026-06-10）

## 范围

策略学堂定式动画：`Lottie 优先` + `SVG/CSS 回退`（`MODE: auto`）。

## 实现

- **配置**：`web/js/config.js` → `STRATEGY_ANIM.LOTTIE`（CDN、BASE_PATH、SOURCES）
- **加载器**：`web/js/strategy_animations.js` → `mountLottieStage` / `mountSvgStage` / `destroyStage`
- **示意资产**：`web/assets/lottie/DS01–DS09.json` + `TOTAL.json`（`scripts/build_strategy_lottie_illustrations.py` 生成；对齐 SVG/CSS 示意口径）
- **占位/bootstrap**：`scripts/build_strategy_lottie_placeholders.py`（仅开发用圆点占位）
- **样式**：`web/css/apple.css` → `.strategy-anim-lottie`

## 模式

| MODE | 行为 |
|------|------|
| `auto` | 有 Lottie JSON 且 lottie-web 可用 → Lottie；否则 SVG |
| `svg_only` | 始终 SVG |
| `lottie_only` | 仅 Lottie，缺失则提示 |

## 验证

```powershell
python scripts/build_strategy_lottie_illustrations.py
python scripts/run_o1_lottie_placeholder_acceptance.py
node --check web/js/strategy_animations.js
python -m pytest tests/test_w15_strategy_animations.py -q
python scripts/smoke_w15_strategies_browser.py --auto-server
```

浏览器 smoke：`lottie_count=9`，弹层暂停/深链 **ok**；报告 `runtime/web_validation/o1_lottie_placeholder_acceptance.json`。

## 仍待（可选）

- 设计方**精修分镜** Lottie（同名覆盖 JSON，非阻塞）
- Admin/对象存储托管（WEB-ANIM-005）

## 边界

- 示意 Lottie 仅供客户理解结构，不代表回测/实盘依据
- 不修改峰极OS / 定式规则
