# 第一批结果归档 Manifest（2026-06-02）

## 1. 归档范围

归档目录：`archives/2026-06-02_results_phase1/`

本次已在用户确认后删除原始 `results/` 目录。压缩包保留在 `archives/2026-06-02_results_phase1/`。

## 2. 汇总

- 归档对象：10 个历史回测结果目录
- 原始体积：约 500.30 MB
- 压缩后体积：约 93.10 MB
- 已删除原目录：10 个
- 净释放：约 407.20 MB（原始约 500.30 MB，压缩包约 93.10 MB）
- 校验方式：每个 zip 生成 SHA256，并用 .NET ZipFile 打开验证
- 校验结果：10/10 `ZIP_READ_OK`

## 3. 归档明细

| 源目录 | 文件数 | 原始 MB | 压缩 MB | 校验 |
| --- | ---: | ---: | ---: | --- |
| `results/fengji_total_us_stock_sectors` | 2496 | 201.60 | 42.45 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_sectors_os20260529` | 3680 | 94.67 | 18.94 | `ZIP_READ_OK` |
| `results/ds09_real_5m_futures` | 77 | 40.72 | 3.84 | `ZIP_READ_OK` |
| `results/fengji_total_a_stock_sectors_ev_sec_fintech_ds07_fixed` | 1290 | 38.35 | 7.40 | `ZIP_READ_OK` |
| `results/ds01_real_daily_futures` | 272 | 28.09 | 5.15 | `ZIP_READ_OK` |
| `results/ds01_real_daily_trigger` | 272 | 26.65 | 4.99 | `ZIP_READ_OK` |
| `results/ds07_real_60m_futures` | 226 | 18.17 | 2.59 | `ZIP_READ_OK` |
| `results/ds04_real_daily_futures` | 272 | 17.49 | 2.55 | `ZIP_READ_OK` |
| `results/ds03_real_daily_futures` | 272 | 17.46 | 2.65 | `ZIP_READ_OK` |
| `results/ds02_real_daily_futures` | 242 | 17.10 | 2.54 | `ZIP_READ_OK` |

## 4. SHA256

| 压缩包 | SHA256 |
| --- | --- |
| `fengji_total_us_stock_sectors.zip` | `3E60ACD46BF24AB0C705E531C2DDAB39BD69B9513D84402B5B1A4DAB275FC9DF` |
| `fengji_total_a_stock_sectors_os20260529.zip` | `F39AF3BECD68F491D9545DC8FD305526C32CCE5FA7B8EC15F7FA9B507D77861E` |
| `ds09_real_5m_futures.zip` | `A4244464FFCDF5CA8DC149AFB12A295EE23DA3C1F102FEFD1B4A024F2EF4E663` |
| `fengji_total_a_stock_sectors_ev_sec_fintech_ds07_fixed.zip` | `03568AA312618F918EF2373BE1590D2D14F0F81FD041B3A5ED7697E45FE779DD` |
| `ds01_real_daily_futures.zip` | `556F23AE62A30B2F7DE68DE99F4DC5E8E582AA83F576428B8D38DBD2CD62C5A7` |
| `ds01_real_daily_trigger.zip` | `BD7541254C49B16C43430CF794678E27175F57495C05D6BA1930B1DC1CA16CF9` |
| `ds07_real_60m_futures.zip` | `72DF525896D620456A94529FA4DD1F266FECC502E1E61A85E756F50AB53CAABF` |
| `ds04_real_daily_futures.zip` | `74A55E0A688B650B501EA42EFFC26952A4C77EB264129A61EF7E85E4CB4BFD48` |
| `ds03_real_daily_futures.zip` | `B89839BD053D0021050E25ACFDBFD7A90B3221EF295E95B752F66B34BE76DF47` |
| `ds02_real_daily_futures.zip` | `42A4A0BDB93055B6FC1577E42896BC326F8BDB193155994AA0CEFDEEE69D15A8` |

## 5. 后续删除条件

删除原始目录前已满足以下条件：

1. 用户明确确认删除第一批原始 `results/` 目录。
2. `archives/2026-06-02_results_phase1/manifest.csv` 和 `verify.csv` 存在。
3. 10 个 zip 文件都存在。
4. 10 个 zip 均可打开读取目录。
5. 删除前再次列出将删除的原始路径。

## 6. 当前状态

状态：`DELETED_AFTER_ARCHIVE`

原始目录已从 `results/` 删除，归档包仍在 `archives/2026-06-02_results_phase1/`。如需恢复，可从对应 zip 解压回 `results/`。
