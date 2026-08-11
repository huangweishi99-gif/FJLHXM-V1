# 项目瘦身清理报告（2026-06-02）

## 1. 清理原则

- 只删除可再生成、低风险的缓存、临时文件和验证产物。
- 不删除 `data/`、`results/`、`runtime/fengji_os_state/` 等可能用于回测复核、模拟实盘、OS 状态固化的数据。
- 不改峰极OS、DS01-DS09、雷达、挂单器、模拟盘、服务器部署脚本的策略逻辑。
- 不输出或记录任何 API Key、Token、服务器密码、完整 webhook。

## 2. 已删除内容

本次安全清理已删除：

- Python 缓存目录：`__pycache__/`
- Python 字节码：`*.pyc`、`*.pyo`
- pytest 缓存：`.pytest_cache/`
- 运行期临时验证目录：
  - `runtime/cursor_cache_backup_20260528_180656`
  - `runtime/test_os_state`
  - `runtime/__smoke_os`
  - `runtime/__smoke_radar`
  - `runtime/docx_render_ds05`
  - `runtime/docx_render_ds05_word`
  - `runtime/tmp_data_manager_test`
- 临时 CSV：
  - `data/_tmp*.csv`
  - `data/_check*.csv`

## 3. 空间释放

- 前两轮缓存/临时产物清理：约 147 MB。
- 最后一轮测试后缓存清理：约 1.4 MB。
- 合计释放：约 148 MB。

清理后主要目录体积快照：

| 目录 | 文件数 | 体积 |
| --- | ---: | ---: |
| `results/` | 16249 | 约 774.09 MB |
| `data/` | 1064 | 约 390.46 MB |
| `.git/` | 97 | 约 342.96 MB |
| `runtime/` | 约 94 | 约 35.8 MB |

## 4. 验证

- 清理后已运行：`python -m pytest tests -q`
- 结果：`72 passed`

说明：运行 pytest 会重新生成 `.pytest_cache/` 和 `__pycache__/`，因此测试完成后已再次清理缓存。

## 5. 暂不删除的大目录

以下目录体积较大，但可能包含回测证据、数据源、沙盒图、OS 状态或产品化验收材料，未直接删除：

| 路径 | 体积 | 处理建议 |
| --- | ---: | --- |
| `results/fengji_total_us_stock_sectors` | 约 201.6 MB | 美股板块回测归档，建议压缩归档后再决定是否删除原目录。 |
| `results/fengji_total_a_stock_sectors_os20260529` | 约 94.67 MB | A股板块 OS 回测证据，删除前需确认是否已汇总。 |
| `results/sandbox` | 约 47.39 MB | 沙盒图审计证据，删除前需确认图形复核是否已完成。 |
| `results/ds09_real_5m_futures` | 约 40.72 MB | DS09 期货回测旧结果，建议先确认是否仍需对照。 |
| `data/us_stock` | 约 141.69 MB | 美股数据源，除非确认不再做美股验证，否则保留。 |
| `data/crypto_okx` | 约 119.44 MB | 虚拟货币数据源，模拟盘/回测复核可能需要，保留。 |
| `data/market_data.sqlite` | 约 101.12 MB | A股 SQLite 数据库，属于重要数据源，保留。 |
| `runtime/fengji_os_state` | 约 32.67 MB | 峰极OS增量状态账本，不能随意删除。 |

## 6. 待确认删除/归档清单

下一步如果继续瘦身，建议按以下顺序执行：

1. 先压缩归档 `results/` 下历史回测目录，再删除原目录。
2. 对 `results/sandbox/` 按日期或案例归档，只保留已验收图。
3. 对美股回测结果与 `data/us_stock/` 做一次产品决策：若 V1 明确不继续美股主策略，可迁移到外部归档盘。
4. 对 `data/` 内行情源建立“可重下 / 不可重下 / 当前实盘依赖”三级清单，再删除可重下且已归档的数据。

已完成下一步扫描：

- `ARCHIVE_CANDIDATES_2026-06-02.csv`：归档/删除候选 CSV 清单，共 128 条。
- `ARCHIVE_DECISION_REPORT_2026-06-02.md`：归档决策报告。
- 当前可归档后确认删除的候选目录共 54 个，合计约 674.94 MB；未完成压缩归档和人工确认前，不直接删除原目录。
- `ARCHIVE_MANIFEST_2026-06-02.md`：第一批 10 个历史回测目录已压缩归档，原始约 500.30 MB，压缩后约 93.10 MB，10/10 zip 可打开校验通过；用户确认后已删除原始目录，净释放约 407.20 MB。
- `ARCHIVE_MANIFEST_PHASE2_2026-06-02.md`：第二批 15 个历史回测目录已压缩归档，原始约 149.62 MB，压缩后约 25.15 MB，15/15 zip 可打开校验通过；用户确认后已删除原始目录，净释放约 124.47 MB。

## 7. 当前结论

本次已完成低风险瘦身、第一批和第二批已归档历史回测目录删除。项目核心代码、九大定式规则、模拟实盘状态、服务器部署脚本、行情源数据和峰极OS状态账本均未删除。
