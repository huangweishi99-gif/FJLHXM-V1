# 方案 A — 引擎稳定化路线图

状态：`ACTIVE`  
目标：在 **不做 Web/移动端** 的前提下，把峰极 OS + DS01–DS09 + 总定式引擎做稳、可测、数据齐全。

方案 B（FJLHXM-V1 产品化）暂缓，待方案 A 里程碑 **A3** 完成后再启动 Phase 0。

---

## 里程碑

| ID | 名称 | 状态 | 验收 |
|----|------|------|------|
| A0 | 安装验收 | 必做 | `plan_a_verify.ps1` 全绿 |
| A1 | fengji_core 包 | 进行中 | `pip install -e packages/fengji_core` + 现有 CLI 不改命令可跑 |
| A2 | 单元测试 | 进行中 | `pytest tests/` 全过 |
| A3 | DS09 数据 + 十币总定式回测 | 待做 | 核心币 `bad_audits=0` 汇总 |
| A4 | SQLite 行情库导入 | 待做 | `market_data.sqlite` 覆盖 crypto 1D/1H/15m |
| A5 | 监测脚本 7×24 稳定 | 待做 | `crypto_combined_monitor` 定时跑 + 日志 |

---

## A0 安装验收

```powershell
.\scripts\plan_a_verify.ps1
```

包含：依赖安装、`fengji_core` 可编辑安装、pytest、DS05 样本回测、ETH 九定式 smoke。

---

## A1 fengji_core 包

```text
packages/fengji_core/
  fengji_core/          # OS + 定式 + data + metrics + futures_specs
  fengji_core/constants.py   # 总定式策略列表
src/quant/              # 兼容层 → re-export fengji_core
```

**原则**：CLI 仍在 `src/`，内核逐步迁入 `fengji_core`；合一引擎暂留 `src/unified_whitelist_engine.py`（依赖 backtest_ds*.py）。

---

## A2 测试

```powershell
pip install -r requirements-dev.txt
pip install -e packages/fengji_core
pytest tests/ -q
```

覆盖：

- OS：T+3、硬化交替、gap≥3、identity 审计
- DS05：阵营方向审计
- DS09：总定式纳入 + smoke bad_audits

后续追加：DS01 未来函数、DS07 双周期、合一账本 merge。

---

## A3 数据与批量回测

```powershell
# 1) 拉 15m（DS09 必需）
python scripts\fetch_crypto_m15_for_ds09.py --symbols DEFAULT --days 180

# 2) 九定式白名单 180 天
python src\batch_unified_crypto_whitelist.py --symbols DEFAULT --days 180 --out-dir results\plan_a_crypto_180d

# 3) 国内期货（有数据时）
python src\batch_unified_whitelist_engine.py --whitelist 生猪,棉花 --daily-dir ... --minute-dir ... --out-dir results\plan_a_futures
```

产出：`whitelist_summary.csv` / `crypto_whitelist_summary.csv`，**bad_audits 列全为 0**。

---

## A4 本地行情库

见 `docs/LOCAL_MARKET_DATA_DB.md`。

```powershell
python src\market_data_store.py import --help
```

目标：回测优先读 DB，减少散落 CSV。

---

## A5 监测稳定

```powershell
python src\crypto_combined_monitor.py --symbols DEFAULT --days 180 --out-dir results\crypto_combined_monitor
```

Windows 计划任务或 `scripts/plan_a_monitor_loop.ps1`（可选）每 5–15 分钟跑一次。

---

## 当前进度（2026-05-25）

- [x] A1：`packages/fengji_core` 初版 + `src/quant` 兼容层
- [x] A2：tests/test_os_engine.py、test_ds05.py、test_ds09.py
- [x] A0 脚本：`scripts/plan_a_verify.ps1`
- [ ] A3：十币 180d 全量回测
- [ ] A4：DB 导入
- [ ] A5：监测 cron

---

## 方案 A 完成后 → 方案 B

满足 A3 + A2 后，再启动 `FJLHXM-V1.md` Phase 0（pencil.dev 设计 + OpenAPI + PostgreSQL）。
