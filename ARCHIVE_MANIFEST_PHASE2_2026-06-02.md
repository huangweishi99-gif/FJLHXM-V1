# 第二批结果归档 Manifest（2026-06-02）

## 1. 归档范围

归档目录：`archives/2026-06-02_results_phase2/`

本次已在用户确认后删除原始 `results/` 目录。压缩包保留在 `archives/2026-06-02_results_phase2/`。

## 2. 汇总

- 归档对象：15 个历史回测结果目录
- 原始体积：约 149.62 MB
- 压缩后体积：约 25.15 MB
- 已删除原目录：15 个
- 净释放：约 124.47 MB（原始约 149.62 MB，压缩包约 25.15 MB）
- 校验方式：每个 zip 生成 SHA256，并用 .NET ZipFile 打开验证
- 校验结果：15/15 `ZIP_READ_OK`

## 3. 归档明细

| 源目录 | 文件数 | 原始 MB | 压缩 MB | 校验 |
| --- | ---: | ---: | ---: | --- |
| `results/ds05_real_daily` | 212 | 16.50 | 2.05 | `ZIP_READ_OK` |
| `results/ds05_real_daily_gap3` | 212 | 16.44 | 2.04 | `ZIP_READ_OK` |
| `results/ds05_real_daily_futures` | 212 | 15.96 | 1.99 | `ZIP_READ_OK` |
| `results/ds06_real_daily_futures` | 302 | 15.74 | 1.99 | `ZIP_READ_OK` |
| `results/ds08_real_60m_futures` | 182 | 14.29 | 1.68 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_hot20_os20260529` | 304 | 9.93 | 1.96 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_sectors_cpo_ds07_fixed` | 420 | 8.40 | 1.83 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_sectors_suanli_ds07_fixed` | 426 | 7.57 | 1.68 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_sectors_semiconductor_ds07_fixed` | 427 | 6.77 | 1.55 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_sectors_securities_ds07_fixed` | 427 | 6.51 | 1.40 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_sectors_aviation_equipment_ds07_fixed` | 427 | 6.43 | 1.45 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_hot20_ds07_fixed` | 302 | 6.41 | 1.38 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_hot20` | 302 | 6.41 | 1.37 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_sectors_evtol_ds07_fixed` | 427 | 6.28 | 1.41 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_sectors_lithium_battery_ds07_fixed` | 412 | 5.98 | 1.37 | `ZIP_READ_OK` |

## 4. 原始目录删除条件

删除第二批原始目录前已满足以下条件：

1. 用户明确确认删除第二批原始 `results/` 目录。
2. `archives/2026-06-02_results_phase2/manifest.csv` 和 `verify.csv` 存在。
3. 15 个 zip 文件都存在。
4. 15 个 zip 均可打开读取目录。
5. 删除前再次列出将删除的原始路径，并确认路径全部在项目 `results/` 下。

## 5. 当前状态

状态：`DELETED_AFTER_ARCHIVE`

原始目录已从 `results/` 删除，归档包仍在 `archives/2026-06-02_results_phase2/`。如需恢复，可从对应 zip 解压回 `results/`。
