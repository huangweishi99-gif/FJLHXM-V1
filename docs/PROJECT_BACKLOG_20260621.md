# 峰极OS 待办 backlog · 2026-06-21

> 被动项不重复展开；可主动推进见下方 **P1**。

## 被动（等市场/用户）

| 项 | 说明 |
|---|---|
| ~~new10 r33 DS01×4~~ | ✅ **4/4 VALID** #19–#22 · 2026-06-26 |
| ATH DS08 OPEN | **VALID** #16 · EXEC_REVIEW 维持 |
| WLD DS08 | **EXEC_GAP** #18 · OPEN 观察止损 |
| Shadow 切流 | ✅ **维持 shadow**（用户 2026-06-26 裁定）· 待 standard/pro 用户再议 |
| W-Pay 商户号 | 个体户后再开 Native |

## P1 · 可主动推进

| 项 | 动作 |
|---|---|
| **A3 十币 180d** | ✅ **10/10 bad_audits=0** · `results/plan_a_crypto_180d/A3_ACCEPTANCE.md` |
| **A4 SQLite** | 🔄 下一重点 · `docs/LOCAL_MARKET_DATA_DB.md` |
| fill_supervision EXEC_GAP | ✅ 已接线 · 双端 sync |
| 国内 DS08 entry_fill | ✅ 已部署+重启 |
| DS02–DS09 沙盒扩展 | batch3 **DS07×3** 已出图 · DS02/04 **仍无** · `scan_domestic_futures_fills.py` |
| 国内 `_1d.json` 体积 | 远端 **34 warn=0** · `os_state_1d_sizes_domestic_20260623/` |
| W24 分市场 tier | A股/crypto/期货分别标定 w* |
| pending monitor CPU | 海外 ~39% · 锁已缓解 · 暂不降 5s 轮询 |

## P2 · 可选

| 项 | 说明 |
|---|---|
| W16-WS | 按频道独立 WS |
| W17-prod Auth/Admin | 排在 WS 之后 |
| DS06 独立触发案例 | 待与 DS03 不同触发价时复核 |

## 已完成（近 7 日摘要）

- WLD 首笔 fill 用户 **VALID** · crypto OS 24/24 fix
- 国内 fill_supervision 飞书告警 · 72h audit exit=0
- XRP / 6/20 二次开仓 沙盒验收
- watch 换 order_id 检测 · ATH/WLD 雷达状态文档
- new10 OPEN 5 · 哈希 5/5
