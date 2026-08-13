# DS07 Calibration - 共振决战

状态：`CALIBRATED`

校准依据：2026-08-13 用户裁决——以权威源代码为准（仅延续）。权威源 `packages/fengji_core/fengji_core/ds07.py`（2026-07-05 `e596aca` 冻结）：D1 提供战略授权，H1 必须通过 DS03 二四棒同向触发 `LONG_CONTINUE`/`SHORT_CONTINUE`，要求 `prev_h1_camp` 与 `d1_camp` 同向；反向并轨（`LONG_ALIGN_TURN`/`SHORT_ALIGN_TURN`）已废止。本文件为当前唯一生效口径，旧文档中“两类触发（同向延续 + 反向并轨）”表述已作废。

## 当前最高 OS 迁移

- DS07 继承当前峰极 OS 最高宪法。
- D1 与 H1 必须分别独立运行完整峰极 OS。
- 旧文档只读取 DS07 自身买卖逻辑，不读取旧 OS。
- 当前峰极间隔统一使用 `gap=3`，不是旧文档里的 `gap=4`。
- H1 当前 K 只能读取上一根已收盘 D1 的阵营状态，禁止读取当天未收盘日线。

## 多头逻辑

1. D1 安全桥接阵营为红：`d1_camp == 1`。
2. H1 必须独立运行峰极 OS。
3. H1 启动前已同阵营：`prev_h1_camp == 1` 且当前 `h1_camp == 1`。
4. H1 需通过 DS03 二四棒同向判定（`resolve_ds03_attack` 返回 `side=1`），触发类型为 `LONG_CONTINUE`。
5. 入场价为 `max(open, ds03.entry_ref)`，防守价为 `prev_row.red_ext_price`（H1 红极）。
6. 防守价必须低于入场价（`defense_price < entry_price`），否则信号无效。
7. 同一个攻击结构只能消费一次（`attack_key` 去重）。
8. 后续只接受更高的 H1 红极上移止损。

## 空头逻辑

1. D1 安全桥接阵营为蓝：`d1_camp == -1`。
2. H1 必须独立运行峰极 OS。
3. H1 启动前已同阵营：`prev_h1_camp == -1` 且当前 `h1_camp == -1`。
4. H1 需通过 DS03 二四棒同向判定（`resolve_ds03_attack` 返回 `side=-1`），触发类型为 `SHORT_CONTINUE`。
5. 入场价为 `min(open, ds03.entry_ref)`，防守价为 `prev_row.blue_ext_price`（H1 蓝极）。
6. 防守价必须高于入场价（`defense_price > entry_price`），否则信号无效。
7. 同一个攻击结构只能消费一次（`attack_key` 去重）。
8. 后续只接受更低的 H1 蓝极下移止损。

## 审计硬条件

- D1 与 H1 必须分别是完整峰极 OS 结果，不能用裸 K 线替代。
- `d1_camp` 必须来自上一根已收盘 D1 的安全状态。
- 多头启动完成后必须 `d1_camp=1`、`prev_h1_camp=1` 且 `h1_camp=1`。
- 空头启动完成后必须 `d1_camp=-1`、`prev_h1_camp=-1` 且 `h1_camp=-1`。
- 只允许 `trigger_type ∈ {LONG_CONTINUE, SHORT_CONTINUE}`；`LONG_ALIGN_TURN`/`SHORT_ALIGN_TURN` 为 forbidden。
- 多头 `attack_price > entry_price` 为 bad；空头 `attack_price < entry_price` 为 bad。
- 多头 `defense_price >= entry_price` 为 bad；空头 `defense_price <= entry_price` 为 bad。
- 防守点必须是 H1 同向防守极：多头红极，空头蓝极。
- 同一攻击结构只允许触发一次，止损后不得重复消费同一结构。
- 止损只守 H1 防守极，并且只向有利方向移动。

## 本轮校准结果

- 本地 18 个 60m 文件中，16 个找到对应 D1 并跑通。
- 跑通品种全部 `bad_trades=0`。
- 棕榈、铁矿未跑通原因：本地缺少对应日线文件。
- 双周期沙盒图样本：`results/sandbox/ds07/生猪_trade_1_dual.png` 至 `results/sandbox/ds07/生猪_trade_3_dual.png`。
