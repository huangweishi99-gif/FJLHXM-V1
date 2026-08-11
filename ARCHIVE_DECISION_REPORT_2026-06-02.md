# 归档/删除候选决策报告（2026-06-02）

## 1. 本次目标

在不破坏峰极OS工程、九大定式规则、模拟实盘、数据源和回测复核能力的前提下，梳理大体积目录，明确哪些内容可以归档后再删除原目录。

本次未删除 `results/`、`data/`、`runtime/fengji_os_state/` 中的高价值目录，只生成候选清单和决策分层。

## 2. 输出文件

- `ARCHIVE_CANDIDATES_2026-06-02.csv`：`results/`、`data/`、`runtime/` 下一级目录扫描清单，共 128 条。
- `ARCHIVE_DECISION_REPORT_2026-06-02.md`：本报告。
- `CLEANUP_REPORT_2026-06-02.md`：低风险缓存/临时产物清理报告。

## 3. 分类汇总

| 分类 | 数量 | 体积 | 处理原则 |
| --- | ---: | ---: | --- |
| `ARCHIVE_THEN_DELETE_CONFIRM` | 54 | 约 674.94 MB | 历史回测/验证结果。先压缩归档，确认归档可读后，再由用户确认删除原目录。 |
| `KEEP_DATA_SOURCE` | 8 | 约 289.18 MB | 行情源/数据库源。默认保留，不直接删除。 |
| `REVIEW_RESULTS` | 49 | 约 50.69 MB | 小型结果证据。先保留，后续按案例清理。 |
| `KEEP_OR_SELECTIVE_ARCHIVE` | 1 | 约 47.39 MB | 沙盒图审计证据。只做选择性归档，不整体盲删。 |
| `KEEP_RUNTIME_STATE` | 1 | 约 32.67 MB | 峰极OS增量状态账本。保留。 |
| `ARCHIVE_OR_REVIEW_RUNTIME` | 15 | 约 2.83 MB | 运行期证据/验证产物。体积小，优先级低。 |

## 4. 第一批建议归档对象

第一批建议归档但不立即删除的目录：

| 目录 | 体积 | 理由 |
| --- | ---: | --- |
| `results/fengji_total_us_stock_sectors` | 约 201.6 MB | 美股板块回测。当前 V1 主线不以美股为主策略，适合归档。 |
| `results/fengji_total_a_stock_sectors_os20260529` | 约 94.67 MB | A股板块 OS 回测证据，体积大；归档前需确认汇总文件可追溯。 |
| `results/ds09_real_5m_futures` | 约 40.72 MB | DS09 期货旧回测结果，适合作为历史证据归档。 |
| `results/fengji_total_a_stock_sectors_ev_sec_fintech_ds07_fixed` | 约 38.35 MB | A股板块回测结果，建议归档后保留汇总。 |
| `results/ds01_real_daily_futures` | 约 28.09 MB | 单定式旧回测结果，适合归档。 |
| `results/ds01_real_daily_trigger` | 约 26.65 MB | 单定式旧回测结果，适合归档。 |
| `results/ds07_real_60m_futures` | 约 18.17 MB | 单定式旧回测结果，适合归档。 |
| `results/ds04_real_daily_futures` | 约 17.49 MB | 单定式旧回测结果，适合归档。 |
| `results/ds03_real_daily_futures` | 约 17.46 MB | 单定式旧回测结果，适合归档。 |
| `results/ds02_real_daily_futures` | 约 17.10 MB | 单定式旧回测结果，适合归档。 |

第一批前 10 项合计约 500.3 MB。建议压缩到 `archives/2026-06-02_results_phase1/` 后，确认压缩包存在且可读取，再删除原目录。

## 5. 暂不删除对象

以下内容不应在当前阶段删除：

| 路径 | 原因 |
| --- | --- |
| `data/us_stock` | 美股数据源，除非明确停止美股验证且已外部归档。 |
| `data/crypto_okx` | 虚拟货币数据源，可能用于回测复核和模拟盘核对。 |
| `data/market_data.sqlite` | A股 SQLite 数据库，属于重要数据源。 |
| `data/a_stock` | A股 CSV 数据源，当前产品和回测仍可能依赖。 |
| `runtime/fengji_os_state` | 峰极OS增量状态账本，删除会影响“固定已连峰极线、只增量更新”的工程目标。 |
| `results/sandbox` | 沙盒图是规则审计证据，必须按已验收案例选择性归档。 |

## 6. 建议执行顺序

1. 创建 `archives/2026-06-02_results_phase1/`。
2. 对第一批建议归档对象逐个压缩，保留目录名、时间和文件数。
3. 为每个压缩包生成 SHA256 校验。
4. 抽查压缩包可列目录、可解压单个 CSV/PNG。
5. 生成 `ARCHIVE_MANIFEST_2026-06-02.md`。
6. 等用户确认后，再删除原始目录。

## 7. 当前结论

项目可释放空间主要集中在历史 `results/` 回测结果。当前安全边界下，最多可先归档约 674.94 MB 的候选结果；未完成归档和人工确认前，不应直接删除原目录。

## 8. 第一批归档执行结果

已完成第一批压缩归档：

- 归档目录：`archives/2026-06-02_results_phase1/`
- 归档对象：10 个历史回测结果目录
- 原始体积：约 500.30 MB
- 压缩后体积：约 93.10 MB
- 压缩包校验：10/10 `ZIP_READ_OK`
- 详细记录：`ARCHIVE_MANIFEST_2026-06-02.md`
- 当前状态：用户确认后已删除 10 个原始 `results/` 目录

本次删除释放原始目录约 500.30 MB；扣除归档包约 93.10 MB，净释放约 407.20 MB。删除后复核：10 个原目录均不存在，10 个 zip 均仍可打开。

## 9. 第二批归档执行结果

已完成第二批压缩归档：

- 归档目录：`archives/2026-06-02_results_phase2/`
- 归档对象：15 个历史回测结果目录
- 原始体积：约 149.62 MB
- 压缩后体积：约 25.15 MB
- 压缩包校验：15/15 `ZIP_READ_OK`
- 详细记录：`ARCHIVE_MANIFEST_PHASE2_2026-06-02.md`
- 当前状态：用户确认后已删除 15 个原始 `results/` 目录

本次删除释放原始目录约 149.62 MB；扣除归档包约 25.15 MB，净释放约 124.47 MB。删除后复核：15 个原目录均不存在，15 个 zip 均仍可打开。
