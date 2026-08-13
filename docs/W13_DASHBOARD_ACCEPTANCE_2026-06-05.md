# W13 首页 Dashboard 验收报告

日期：2026-06-05

范围：

- `web/index.html`
- `web/js/monitor-chart.js`
- `web/css/apple.css`
- `services/monitor_domestic.py`
- `services/api/main.py`
- `scripts/sync_domestic_futures_1d_for_web.py`
- `data/futures/1d/` 当前首页 7 个持仓品种日线

## 1. 结论

W13 首页 Dashboard API/DOM/数据级验收通过。

本轮没有做 Playwright/Chrome 截图级验收，原因是当前环境未发现可直接调用的 Chrome/Playwright。验收依据为：代码静态检查、FastAPI 临时服务 API smoke、首页相关数据字段、图表 overlay、日线数据尾行与测试。

## 2. 当前首页 7 个最新持仓

接口：

```text
GET /api/v1/monitor/domestic/latest-opens
```

结果：

```text
source=paper_state
positions=7
pending_conflicts_filtered=2
```

当前 7 个持仓：

| 品种 | 定式 | 方向 | 开仓时间 | 开仓价 | 守护点 | 实际主力合约 |
|------|------|------|----------|--------|--------|--------------|
| 苯乙烯(EB) | DS05 | short | 2026-06-04 14:45:00 | 8681 | 8995 | DCE.eb2607 |
| 碳酸锂(LC) | DS07 | short | 2026-06-04 11:15:00 | 166880 | 182500 | GFEX.lc2609 |
| 烧碱(SH) | DS05 | short | 2026-06-04 10:30:00 | 1919 | 1961 | CZCE.SH607 |
| 白糖(SR) | DS05 | short | 2026-06-04 10:30:00 | 5427 | 5446 | CZCE.SR609 |
| PTA(TA) | DS05 | short | 2026-06-04 10:30:00 | 6220 | 6350 | CZCE.TA609 |
| 玻璃(FG) | DS01 | short | 2026-06-04 10:00:00 | 1036 | 1052 | CZCE.FG609 |
| 纸浆(SP) | DS01 | short | 2026-06-04 10:00:00 | 4842 | 4878 | SHFE.sp2609 |

说明：

- `pending_conflicts_filtered=2` 表示首页 API 已过滤 2 个与当前 pending/radar 方向冲突的旧持仓。
- 本轮只验收展示链路，不复核每笔开仓是否符合定式规则。

## 3. 主力合约数据

`runtime/domestic_futures_main_contract_sources.json` 存在，记录 34 个品种。

当前首页 7 个品种均返回实际主力月份合约：

- EB: `DCE.eb2607`
- LC: `GFEX.lc2609`
- SH: `CZCE.SH607`
- SR: `CZCE.SR609`
- TA: `CZCE.TA609`
- FG: `CZCE.FG609`
- SP: `SHFE.sp2609`

说明：

- `KQ.m@...` 仅作为发现主力合约入口。
- 首页展示使用 `main_contract_display` / `main_contract_actual`。

## 4. 日线数据补齐

验收前发现：

- 首页最新持仓开仓日为 2026-06-04。
- 本地 Web 日线部分品种尾行仍停在 2026-06-03，导致最新开仓点不能完整落在最新日线 K 上。

已执行：

```powershell
python scripts\sync_domestic_futures_1d_for_web.py --symbols EB,LC,SH,SR,TA,FG,SP
```

结果：

```text
SYNC_OK symbols=7
```

同步后尾行均为 2026-06-04：

- `data/futures/1d/苯乙烯.csv`
- `data/futures/1d/碳酸锂.csv`
- `data/futures/1d/烧碱.csv`
- `data/futures/1d/白糖.csv`
- `data/futures/1d/PTA.csv`
- `data/futures/1d/玻璃.csv`
- `data/futures/1d/纸浆.csv`

## 5. 图表 overlay 验收

接口：

```text
GET /api/v1/monitor/domestic/chart
```

7 个持仓均通过：

| 品种 | 定式 | EntryDate | LastBar | Bars | 峰极线段 | StopLine |
|------|------|-----------|---------|------|----------|----------|
| EB | DS05 | 2026-06-04 | 2026-06-04 | 205 | 24 | True |
| LC | DS07 | 2026-06-04 | 2026-06-04 | 171 | 22 | True |
| SH | DS05 | 2026-06-04 | 2026-06-04 | 214 | 25 | True |
| SR | DS05 | 2026-06-04 | 2026-06-04 | 171 | 28 | True |
| TA | DS05 | 2026-06-04 | 2026-06-04 | 171 | 23 | True |
| FG | DS01 | 2026-06-04 | 2026-06-04 | 171 | 15 | True |
| SP | DS01 | 2026-06-04 | 2026-06-04 | 170 | 23 | True |

## 6. 前端关键点检查

### 6.1 卡片

通过：

- 左侧卡片不显示英文 setup。
- 卡片显示品种、方向、实际主力合约、开仓价。
- 选中态有更亮蓝色底。
- 未选中态也与背景分离。

### 6.2 中间标题

通过：

- `chartStrategy` 显示 `最新开仓：定式xx`。

### 6.3 详情栏

通过：

- 详情栏为 8 栏均匀分布。
- 包含 `净盈亏`。
- 净盈亏基于最新 K 线 close、开仓价、方向、手数、乘数计算。

### 6.4 K 线日期

通过：

- `monitor-chart.js` 使用 `formatChartDate()` 统一格式化日期。
- API 返回 bar 字段 `t=YYYY-MM-DD`。
- 当前 7 个图表最后 K 线均为 `2026-06-04`，与开仓日对齐。

### 6.5 守护点

通过：

- 前端仅创建横向 `createPriceLine()`。
- `title` 为空，不在 K 线上重复标注“守护点”文字。

## 7. 测试

执行：

```powershell
python -m pytest tests\test_monitor_domestic.py tests\test_monitor_quotes.py tests\test_sync_domestic_futures_1d_for_web.py -q
```

结果：

```text
6 passed
```

## 8. 已知限制

1. 未做浏览器截图级验收，因为当前环境未发现可直接调用的 Chrome/Playwright。
2. 本轮不复核每笔持仓是否符合 DS01/DS05/DS07 策略开仓规则；这属于策略审计，不属于 W13 首页展示验收。
3. 首页图表 API 对 DS05/DS07 等不支持 chart bundle 的定式会回退 DS03 底图，仅用于展示 K 线/峰极线/持仓 overlay；不改变策略规则。
4. 本轮同步了 7 个首页持仓品种的本地 Web 日线 CSV，属于展示数据补齐，不涉及服务器策略逻辑。

## 9. 下一步

进入 W14 回测详情页产品化验收：

- 1/3/5 年切换。
- 四市场品种。
- K 线/OS/交易标记。
- 交易明细。
- 桶详情。
- 同桶样本。
- CSV 导出。
- PG/API/CLI 抽样一致性。
