# HYPE / ATH 状态复核（2026-06-24）

来源：运维第 29 轮 `results/ops_round_20260624_r29/remote_checks.json` + 项目 TODO 记录。

## HYPEUSDT

| 字段 | 值 |
|------|-----|
| 当前 OPEN | **无** |
| 当前 ACTIVE 挂单 | **无**（r29 pending 样本未含 HYPE） |
| paper symbol 槽位 | 有（new10 监控池内） |
| 历史问题 | 2026-06-18 DS03 paper 成交 · **开仓执行 FAIL**（ticker ≠ entry_fill） |
| 审计包 | `results/hype_ds03_paper_fail_audit_20260624/` · **FAIL_ACK** ✅（用户 2026-06-23） |
| 当前规则 | DS03 攻击棍 + fill_supervision 已上线 |
| 下一步 | 保留观察；若再成交走沙盒 + fill 复核，**不反向改规则** |

## ATHUSDT

| 字段 | 值 |
|------|-----|
| 当前 OPEN | **无** |
| 当前 ACTIVE 挂单 | **无** |
| paper symbol 槽位 | 有 |
| 触发距离 | DS03 short · trigger **0.00397** · 现价 **~0.00470** · **~15.5% 圈外**（2026-06-24 雷达快照） |
| 距离快照 | `results/ath_status_20260624/ATH_DS03_DISTANCE.md` · `scripts/refresh_ath_ds03_distance.py` |
| 首笔 fill | **DS08** short @ 0.004384（6/24）· **VALID** ✅ · 索引 #16 |
| 价格源 | OKX only（`OKX_PRICE_ONLY`） |
| 下一步 | DS03 仍圈外观察 · DS08 首笔 **已 VALID** |

## 运维结论

- 两品种均在 new10 池内，链路正常，**无异常 OPEN**。
- HYPE 历史 FAIL 个案 **已 FAIL_ACK**；ATH 属「尚未触达」而非故障。
- 无需为出 fill 修改定式/OS/风控。

## 相关命令

```powershell
# 运维快照
.\scripts\run_ops_round_check.ps1 -RoundTag r29

# 海外 fill 轻量同步后审计
python scripts\sync_overseas_fill_events.py
python scripts\audit_new10_crypto_fills.py --symbols HYPEUSDT,ATHUSDT
```
