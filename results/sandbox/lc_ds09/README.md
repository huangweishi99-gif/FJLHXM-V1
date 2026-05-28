# LC DS09 沙盒（2026-05-28）

## 国内期货 LC

- **夜盘 session**：`assign_cn_futures_session_date`（`hour>=21` 归下一交易日；天勤 CSV 夜盘多为次日 `01:00–06:00`，已直接落在交易日历日）。
- **校验**：`scripts/verify_ds09_lc_session.py` — 690 根 D1、298 个授权 session；当前 `data/15m/LC.csv` 仅约 3000 根 M15（约 31 日），该窗口内 **无「刺穿昨日边界」**，故回测 0 笔成交。
- **示意图**：`LC_DS09_session_overview.png` — 2026-05-26 多头授权日，M15 最高价未高于 D1 边界（规则要求 `high > boundary`）。

## 参考成交沙盒（ETH 180d，同套 DS09 引擎）

- `ETH_DS09_trade1_reference.png` … `trade3` — 用于对照九重天标注样式；非 LC 成交。
