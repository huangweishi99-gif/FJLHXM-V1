# DS03 Draft

DS03 二四棒已完成当前项目最高 OS 口径下的工程审计与沙盒图人工校准。

## 继承关系

DS03 必须继承当前项目最高 OS：

- `hardened_fengji_line`
- 当前红蓝阵营转换规则
- 当前峰极确认与硬化规则
- `gap = 3`
- 同价最新

旧文档只参考 DS03 自身买卖逻辑，不参考旧 OS、旧 `GAP=4` 或旧 Runtime。

## 当前买卖逻辑

DS03 是阵营内推进，不是反转/抄底/猜顶。进攻只认**峰**，防守只认**极**；破极=转势，不得作为 DS03 开仓。

多头（`camp==1`）：

- **真峰**：`high[i]` 第一次刺破 `active_high`（红峰）；成交价 `max(open[i], active_high)`。
- **假峰**（图 a 点 / OS `FAILED_HIGH`）：未破真峰、未破红极；`红峰-红极-假峰-红极` 成立后，**仅第一根启动棍**刺破假峰价。
- 守二：`min(low[i-1], low[i])`；守四：最近 4 根低点，只上移。
- 每个 `peak_key` 全局只允许一次 DS03（一峰一买）。

空头：镜像，触发 `active_low`（蓝峰）或合法假峰（`FAILED_LOW`），成交价 `min(open, 触发峰)`。

## 严格版说明

当前实现不使用旧文档的 `GAP=4`。  
触发必须使用上一根 K 已可见的阵营；真峰/假峰均须满足**启动棍**（前一根未破、当根第一次破）。  
假峰不得高于（多）或低于（空）当时真峰价。  
挂单 `setup_key` 绑定 `peak_key`；`consumed_ds03_setup_keys` 防止重复开仓。

日线回测无法知道同一根 K 线内先突破还是先止损，因此开仓当根不做同根止损；守四在收盘后更新，供下一根 K 线使用。

## 状态

```text
CALIBRATED
```

## 当前工程审计

国内期货 30 品种已跑通当前 OS 口径：

```text
result_dir  = results/ds03_real_daily_futures
rows        = 30
bad_trades  = 0
failed      = 0
```

表现较好的样本：

```text
橡胶 +195.99%
生猪 +163.61%
棉花 +101.91%
碳酸锂 +93.27%
PTA +58.43%
氧化铝 +42.38%
玻璃 +38.57%
LPG +35.20%
```

表现较差的样本：

```text
沪镍 -87.88%
鸡蛋 -45.70%
乙二醇 -31.45%
红枣 -26.20%
菜粕 -19.36%
菜油 -18.59%
焦煤 -17.16%
豆粕 -8.44%
```

该结果符合 DS03 推进型定式特征：趋势连续推进品种表现较好，高插针、高反杀品种表现较差。

## 当前沙盒复核包

已生成 DS03 沙盒图，并由用户确认正确：

```text
results/sandbox/ds03_calibration/lithium_carbonate_first8/ds03_lithium_carbonate_first8_contact.png
results/sandbox/ds03_calibration/rubber_last8/ds03_rubber_last8_contact.png
```

人工检查项：上一根已授权阵营、刺穿红峰/蓝峰、成交价、守二、守四、出场路径。

冻结记录见：

```text
docs/DS03_CALIBRATION.md
```
