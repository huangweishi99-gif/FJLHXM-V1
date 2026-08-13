# Wave5 O2 · 定式帮助深链 — 2026-06-11

## 范围

首页 / 回测 / 监测 / 品种详情 → `strategies.html?strategy=DSxx&open=1`（策略学堂弹层预览）。

## 实现

- **共享 API**：`web/js/app.js` → `strategyHelpLinkHtml()`（基于 `strategyAnimPageUrl` + `open=1`）
- **首页**：最新开仓 K 线区「定式帮助」
- **回测**：定式选择旁 + 成交详情「查看定式帮助 →」
- **监测**：表格「开仓定式」列可点击深链
- **品种详情**：footer `DSxx 定式帮助` 按钮（有持仓定式时显示）

## 验证

```powershell
node --check web/js/app.js
python -m pytest tests/test_strategy_help_links.py -q
```

## 边界

- 仅对当前订阅档 `isStrategyAllowed` 的定式显示链接；TOTAL/未解锁定式不链出
- 不修改峰极OS / 定式规则；链接只读展示
