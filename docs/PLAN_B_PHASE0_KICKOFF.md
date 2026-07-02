# 方案 B · Phase 0 启动清单

生成：2026-07-02 · 在方案 A 收口后 · **只读/API 层 · 不改定式/OS**

> 评估摘要：`docs/PLAN_B_PHASE0_ASSESSMENT.md` · 默认 **B0-b** 直至用户确认 **B0-a**

## 现状：FastAPI 已有端点（`services/api/main.py`）

| 域 | 端点 | Phase 0 动作 |
|----|------|-------------|
| 健康 | `GET /api/v1/health` | 保持 · CI smoke |
| 鉴权 | `POST /auth/register|login|refresh` · `GET /auth/me` | 文档化 · 不写密钥 |
| 品种 | `GET /api/v1/instruments` | 对齐 `market_data.sqlite` coverage |
| 策略 | `GET /api/v1/strategies` | 只读 · DS01–09 显示名 |
| 回测 | `POST /backtests` · `GET /backtests/{id}` · chart/trades/summary | 默认 `--data-source db` 文档 |
| 上下文 | `GET /context-stats/buckets` · bucket-trades | 只读复盘 · 不反改策略 |
| 监测 | `GET /monitor/*` · `WS /api/v1/ws/monitor` | pro 档 · 只读 |
| 模拟 | paper-watchlist · paper-account | shadow 隔离 |

**Phase 0 不需要新建引擎**；工作是 OpenAPI 文档、分桶提交、设计验收。

## 第 1 周任务（B0-a 预填）

| ID | 任务 | 验收 |
|----|------|------|
| B0-1 | 导出 OpenAPI · `docs/api/openapi.json` | ✅ **38 paths** · `scripts/export_openapi_snapshot.py` |
| B0-2 | `market_data_coverage.csv` → instruments API 对账 | 🔄 **已跑** · CRYPTO/A股 ✅ · **FUTURES 缺 5m** · `scripts/assess_instruments_vs_coverage.py` |
| B0-3 | Pencil 9 屏 · MCP 截图验收（或标记待连） | ✅ **9/9 截图** · `plan_b_b03_pencil_acceptance/B03_ACCEPTANCE.md` |
| B0-4 | Web 提交分桶计划（core / web / data 分离） | ✅ `docs/PLAN_B_B04_COMMIT_BUCKETS.md` |

## 并行 T0（不阻塞 B0）

- **HYPE #28**：`watch_hype28_stop.py` · `hype28_close_audit_20260702/`
- **ops r64+**：pytest **107** · 180d 缓存守卫 · B0-2 对账

## 命令

```powershell
# Phase 0 smoke（本地 API 若已起）
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/instruments?market=CRYPTO

# B0-2 SQLite vs Plan A
python scripts\assess_instruments_vs_coverage.py

# B0-3 Pencil 9 屏（文件级）
python scripts\finalize_fjlhxm_ui_pen.py
python scripts\assess_fjlhxm_ui_pen_b03.py

# HYPE watch
python scripts\watch_hype28_stop.py --json
```

## 风险

- 工作树 dirty · 必须先分桶再 Phase 0 大提交
- Web 测试 6 fail（feature_gate / w17 remote）· 与 Phase 0 并行修，不混进 core PR
