# Chart bundle — Web K 线一次拉取格式（FJLHXM-V1）

版本：0.1.0 · 状态：已实现 DS03 MVP

## 用途

替代前端直接读 PNG 沙盒图；`GET /api/v1/backtests/chart-bundle` 返回 OHLCV + OS 阵营 + 硬化折线 + 买卖标记 + 摘要指标。

## 顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 品种代码 |
| `strategy_id` | string | DS01–DS09 / TOTAL |
| `years` | int | 回溯年数 1–5 |
| `engine_version` | string | fengji_core 版本标记 |
| `metrics` | object | trades, win_rate, total_return, max_drawdown, bad_audits |
| `bars` | array | K 线 + `camp` |
| `hardened_segments` | array | 峰极硬化线段 |
| `markers` | array | entry / exit 标记 |

## bars[]

```json
{ "t": "2026-05-08", "o": 90.1, "h": 91.2, "l": 88.0, "c": 90.7, "v": 12345, "camp": 1 }
```

`camp`: `1` 红 / `-1` 蓝 / `0` 中性

## hardened_segments[]

```json
{ "t0": "2026-04-01", "p0": 87.2, "t1": "2026-04-17", "p1": 90.7, "type": "HIGH" }
```

## markers[]

```json
{ "t": "2026-05-08", "kind": "entry", "side": "long", "price": 90.73, "trade_no": 57 }
```

## 实现

- 生成器：`src/chart_bundle.py`
- 当前支持策略：**DS03**（后续按同模式扩展 DS01、TOTAL）
