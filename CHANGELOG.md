# CHANGELOG

## 2026-07-07（D4 · 定式案例回归）

- 新增 `scripts/verify_d4_pattern_cases.py`：DS01/03/05 单测 + DS05 K2 合成 + 国内期货（红枣/玻璃/纯碱）扫描 + IO/ETH DS03 窗口探针。
- 报告输出：`results/sandbox/d4_phase2_YYYYMMDD/`（`SUMMARY.md` + `d4_report.json`）。
- 测试：`test_verify_d4_pattern_cases.py` · 合计 **21 passed** · `D4_VERIFY_OK`。

## 2026-07-07（D3 · W18 merge & 国内验收）

- **PR #15** merge `main@2e5a3e3`。
- 国内：`verify_w18_watchlist_api.py --with-pg` **OK** · `pending_runtime_users=4` · dry-run **4 items**。
- 修补：`verify_w18` unittest.mock + src path · runtime job PG 不可用清晰退出。

## 2026-07-07（D3 · W18 watchlist MVP）

- `paper_watchlist.list_distinct_watchlist_user_ids`：批量 runtime 缓存按用户枚举。
- `run_watchlist_runtime_job.py`：`--all-users` / `--dry-run` / 可复用 payload builder。
- 新增 `verify_w18_watchlist_api.py`（配额 + runtime 缓存年龄 + API shape 对齐）。
- 新增 `run_watchlist_runtime_job_all.ps1`（本地/计划任务入口）。
- 入库 `tests/test_custom_instruments.py` · manifest 补 3 脚本 · **43 passed**。

## 2026-07-06（D2 · pending monitor plan/apply · merge & deploy）

- **PR #13** merge `main@4a09090`。
- 海外：`fengji_pending_order_monitor.py` hash match · PID **3345868** · 日志正常轮询。
- 国内：`fengji_futures_pending_order_monitor.py` hash match · PID **1140**。
- 附带：`watchdog_overseas.sh`（`flock` + 拉起重试）已同步海外（注：scp 后需 `sed` 去 CRLF）。

## 2026-07-06（D2 · pending monitor plan/apply）

- `fengji_pending_order_monitor.py` / `fengji_futures_pending_order_monitor.py`：止损退出与成交路径拆为 **precompute/plan + apply**，缩短 `state_lock` 持锁窗口。
- 测试：`tests/test_pending_orders.py` + `test_futures_pending_orders.py` · **13 passed**。
- 附带：`scripts/watchdog_overseas.sh` 入库（`flock` + 拉起重试，防部署竞态误报）。

## 2026-07-06（海外 radar_loop 告警 · 看护加固）

- **根因**：PR #12 部署窗口 `pkill` 与 cron 看护竞态；10:53:02 已拉起，约 3s 内被 pkill，误报「拉起失败」。
- **现状**：radar 已在跑（约 10:53:38 起）· pending/data/paper 正常。
- **`watchdog_overseas.sh`**：`flock` 单实例 · `ensure_proc` 最多 3 次重试、分段等待探测 · 已 scp 海外。

## 2026-07-06（D1 · OS 状态账本增量复核）



- 国内 LC：两轮 radar `--once` · `delta1=0 delta2=0` · `processed_len=192`。
- 海外 BTC：两轮 radar `--once` · `INCREMENTAL_OK` · `processed_len=1095` · size 不变。
- 本地 `verify_os_state_incremental.py`：BTC/LC 第二轮 `size_delta=0` · `incremental_ok=true`。
- 修复 `verify_os_state_overseas.sh` CRLF（`set -eu`）。

## 2026-07-06（PR #12 merged · os_engine/radar + N 日清单）

- **PR #12** (`4d6a840`)：`os_engine` urgent_gap · `fengji_total_radar` · DS03/DS07 · **43 passed** · merge `main` · 海内外部署。
- `TODO.md` / `docs/PLAN_B_PHASE2_PROGRESS.md`：Phase 2 **D0–D7** N 日清单（D0–D1 完成）。

## 2026-07-05（PR merged · domestic ops）

- **`feat/domestic-ops-pg-sc-sync`** 已合并 **`main`**（GitHub · 2026-07-05）。

## 2026-07-05（post-sync 验证 · pending dedupe）

- **`stop_duplicate_pending_domestic.ps1`**：仅匹配 **python** 进程（避免误杀/误留 powershell）。
- **国内 post-sync**：radar **3108** · pending **3316** · data_manager **3220** · health **OK** · 海外 hash **0**。

## 2026-07-05（sync_deploy_domestic cherry-pick · 部署 manifest）

- **`sync_deploy_domestic.ps1`**：远程目录预建 · `Sync-RemoteFile` · 运维脚本/PG-SC 验收文档 · **paper 改走 `deploy_domestic_paper_feishu.ps1`**（移除直 scp 中文文件名）· fengji_core **按 .py 增量 sync**。
- 新增 **`fengji_domestic_deploy_manifest.txt`** + **`test_fengji_domestic_deploy_manifest.py`** · `verify_project_buckets` 纳入 deploy 桶。
- **`fengji_ops_domestic_manifest`**：补 `verify_domestic_health` · `compare_overseas_core_hashes` · runtime remote。
- **`ensure_single_data_manager.ps1`**：`@(Get-DmPythonProcs)` 修复单进程 `.Count` 为空 · 代码陈旧重启现可触发。
- **`sync_deploy_domestic.ps1`** 试跑 **PASS**（~2.3min · 38 core + 31 fengji_core · paper manifest · skip restart）· 末尾自动 `ensure_single`。

## 2026-07-05（运维巡检增强 · 海外 hash 批量比对）

- **`check_domestic_status.ps1`**：python/cmd 进程分计 · **代码比进程新** 告警 · PG/SC 日志 tail 800。
- **`compare_overseas_core_hashes.py`**：单次 SSH 批量 `sha256sum`（原 17 次串行易挂起）· **mismatches=0**（~7s）。
- 国内运行态：**34/34 成功 fail=0** · PG/SC **`[OK]`** · data_manager PID **3980**。

## 2026-07-05（data_manager 陈旧进程 · ensure_single 修复）

- **根因**：国内 data_manager **PID 3828 自 7/3 14:14 未重启**，7/3 18:01 同步的 `fetch_frame` 降级修复未加载内存；日志仍显示 `连续抓取失败: None`。
- **`ensure_single_data_manager.ps1`**：`Get-DmProcs` 含 cmd 包装 · **`Test-DmBinaryStale`** 代码新于进程则重启 · dedupe 仅 **python>1**（避免 cmd+python 双进程误杀）。
- 国内重启后 **15:34** PG：`1h/15m 降级选用` · **`[OK] 成功抓取 [PG]`** · probe `--write` PG/SC mtime **15:30**。

## 2026-07-03（PG/SC 15m 验收 PASS · fetch_frame 错误信息修复）

- **`fetch_frame`**：全档校验失败时 `last_error` 不再为 `None` · 明确「严格/降级均未通过」原因。
- **`probe_domestic_futures_15m.py`**：新增 **`--write`** 运维补写（验证降级落盘，非 data_manager 常规路径）。
- 国内 probe `--write` PG/SC：**ACCEPTANCE_OK** · PG tail **2026-07-03 06:45** · SC mtime **18:02**。
- 测试：`test_data_manager_futures_main_contracts.py` → **12 passed**。

## 2026-07-03（PG/SC 验收文档 + sync_deploy 运维 cherry-pick）

- 新增 **`docs/PG_SC_15M_ACCEPTANCE.md`** · **`run_night_session_pg_sc_checks.ps1`**（夜盘轮询 + health）。
- **`check_domestic_status.ps1`** / **`verify_pg_sc_15m_csv.ps1`**：解析 next_window 与 PG/SC 抓取日志。
- **`sync_deploy_domestic.ps1`**：scp `-LiteralPath`（空格路径）· 追加 watchdog / ensure_single / PG-SC 探针。

## 2026-07-03（stash 运维桶 · watchdog/探针 sync）

- 新增 **`scripts/fengji_ops_domestic_manifest.txt`** · **`deploy_domestic_ops_stash_bucket.ps1`** · **`tests/test_fengji_ops_domestic_manifest.py`**。
- **`sync_watchdog_domestic.ps1`**：修复含空格路径 scp · 扩展 PG/SC 探针 + `install_watchdog_domestic_task.ps1`。
- **`check_domestic_runtime_remote.ps1`**：radar/pending 计数告警（expect 1）。
- 国内 sync：**7 文件** · radar=1 · pending=1 · PG/SC 验收 **PASS**（probe `--write` 18:02）。

## 2026-07-03（运维脚本 + 桶验收整合）

- **`ensure_single_data_manager.ps1`**：补 `Ensure-SingleDataManager` dedupe（修复启动后重复进程未定义函数）。
- **`refresh_domestic_once.ps1`**：雷达 `--once` 显式 `--market futures`（对齐 stash 运维桶）。
- 新增 **`verify_domestic_health.ps1`** · **`verify_project_buckets.ps1`**；`check_domestic_runtime_remote.ps1` 串联 PG/SC 验收。
- `fengji_phase2_data_manifest.txt` 扩展 ops/验收脚本路径 · manifest **6 passed** · 桶总验 **11 passed**。
- 海外 hash：`compare_overseas_core_hashes` **mismatches=0**。

## 2026-07-03（stash ARCHIVE 文档桶 + PG/SC 15m 巡检）

- 新增 **`docs/archives/INDEX.md`** · **`scripts/fengji_archive_docs_manifest.txt`** · **`scripts/verify_archive_docs_bucket.ps1`**。
- 2026-06-02 两批 results 归档 manifest/verify CSV 纳入清单（zip 仍不入库）。
- **`check_domestic_status.ps1`**：新增 **PG/SC 15m** 段（mtime + CSV tail）· 已 sync 国内。
- PG/SC 15m：16:57 复核仍为 **PENDING**（休市）· 新增 `scripts/verify_pg_sc_15m_csv.ps1` · 下一抓取窗口 **20:30**。

## 2026-07-03（stash Web manifest / Phase 2 数据桶）

- 新增 **`scripts/fengji_phase2_data_manifest.txt`** · **`tests/test_fengji_phase2_data_manifest.py`** · **`scripts/verify_phase2_web_manifest_bucket.ps1`**。
- 整合 Phase 2 本地数据链路：`import-futures-local`（5m/15m/1h）· `sync_domestic_futures_5m_for_context` · `run_sync_domestic_futures_5m_for_context.ps1`。
- **`docs/LOCAL_MARKET_DATA_DB.md`**：补 `import-futures-local` 与 5m sync 命令。
- 说明：stash@{0} 中 Web/API 主资产已在 PR #7–#10 合入；本桶以**本地 untracked Phase 2 脚本**为准，**未整包 pop**。
- 验证：manifest **6 passed** · 5m/import **4 passed** · OpenAPI **38 paths**。

## 2026-07-03（PG/SC 15m probe · 降级抓取验证）

- **`data_manager_futures.py`**：`frame_looks_acceptable` 短历史 floor 修正 · 15m `min_acceptable` **100** · 已 sync 国内并重启 data_manager。
- 新增 **`scripts/probe_domestic_futures_15m.py`**（绕过交易时段 gate 的一次性抓取探针）。
- 国内 probe（非交易时段）：**PG** `DCE.pg2608` 15m **4622** 行（严格校验未过、降级选用）· **SC** `INE.sc2608` 15m **4000** 行 · tail **2026-07-03 06:45**。
- 测试：`test_data_manager_futures_main_contracts.py` → **11 passed**。

## 2026-07-03（海外 crypto 数据泵 hash 全量对齐）

- 新增 `scripts/deploy_overseas_crypto_data_bucket.ps1` · sync `data_manager.py` · `crypto_ingest.py` · `sync_missing_crypto_15m.py`。
- `compare_overseas_core_hashes` → **mismatches=0**（海外核心文件与本地一致）。
- 修复 `test_sync_okx_crypto_timeframes`：OKX-only 品种改由 sync 脚本负责，不再要求写进 `data_manager.py`。
- 测试：OKX/crypto 相关 **8 passed** · watchdog 已重启 data_manager。

## 2026-07-03（fill_supervision 桶 · 海内外 hash 对齐）

- **说明**：stash 中该桶为**旧版删减**；以本地 HEAD 为准（完整 `fill_supervision` + `ds03_pending_fill`）。
- 新增 `scripts/deploy_fill_supervision_bucket.ps1` · 已 sync **海外 + 国内**。
- 海外 hash：`fill_supervision` · `ds03_pending_fill` **match**（剩余 drift：`data_manager` · `crypto_ingest`）。
- 合并 stash `test_feishu_notify.py` 扩展用例（pending/expected_close key）。
- 测试：`test_fill_supervision` + `test_ds03_pending_fill` + `test_feishu_notify` → **38 passed**。

## 2026-07-03（stash ds03/paper 桶 cherry-pick + 部署）

- **DS03**：真峰触发需同时存在 `active_high` + `active_low`（红/蓝防守极缺一不可）· 新增 `test_ds03` / `test_ds01` 用例。
- **`binance_fengji_paper_monitor.py`**：扩展 MONITOR_COINS · 飞书 `send_feishu_once` dedup（startup/异常/开平仓）。
- 新增 `scripts/deploy_ds03_paper_bucket.ps1` · 已 sync DS03 海内外 · 重启 radar loop。
- 测试：`test_ds01` + `test_ds03` + `test_pending_orders` → **24 passed**。

## 2026-07-03（stash os_engine/radar 桶 cherry-pick + 部署）

- **stash cherry-pick**：`os_engine.py` · `fengji_total_radar.py`（`resolve_market`/`resolve_symbols`）· `ds07.py` · 配套 `test_os_engine` / radar 测试。
- 新增 `scripts/deploy_os_engine_radar_bucket.ps1` · 已 sync **海外 + 国内** · 重启 radar loop。
- 测试：`test_os_engine` + radar + DS01/03/05 + pending + data_manager → **77 passed**。
- 国内 radar 去重：restart 后保留单进程。

## 2026-07-03（运维脚本 + PROJECT_CONTEXT + stash 运维桶）

- **stash cherry-pick（运维桶）**：恢复 `scripts/check_domestic_status.ps1`（heartbeat/去重/UTF-8）· `constants.py`（DS09→九重天 · TOTAL priority=5）。
- 新增 `scripts/deploy_domestic_futures_pending_lock.ps1` · 修复 `check_domestic_runtime_remote.ps1`（委托 status 脚本，避免 EncodedCommand 转义失败）。
- `PROJECT_CONTEXT.md`：更新 Phase 2 摘要（5m pass · 锁优化 · data_manager 口径）。
- B0-2：`assess_instruments_vs_coverage.py` **pass** · `test_feishu_notify` + `test_radar_setup_keys` **5 passed**。

## 2026-07-03（国内 futures pending 锁优化 + PG 15m 降档抓取）

- `fengji_futures_pending_order_monitor.py`：对齐海外 crypto 版 **plan/apply** 分离 · 锁内单次 `save_json` · 锁外 CSV/飞书。
- `data_manager_futures.py`：`frame_looks_sane` 修复短历史误判（<10 根）· 新增 `frame_looks_acceptable` 降级路径（PG 等 15m 严格校验失败时仍写入）。
- 已同步国内并重启 **futures pending monitor**（PID 3572）+ **data_manager**。
- 测试：`test_futures_pending_orders.py` 3 passed · `test_data_manager_futures_main_contracts.py` 8 passed。

## 2026-07-03（海外 pending monitor 持锁优化 · plan/apply 分离）

- `fengji_pending_order_monitor.py`：`process_once` 改为锁外 **plan**（止损刷新预览、DS03/DS08 解析、成交规划）→ 锁内 **apply** + 单次 `save_json` → 锁外 notify/append。
- 新增 `precompute_stop_exit_plans` / `apply_stop_exit_plans` / `plan_fill_actions` / `apply_fill_plans`；删除 `_run_fill_loop` 与 `process_open_position_stops_legacy`。
- 修复平仓 notify 误用已清空 `open_position` 的问题（平仓前快照 position）。
- 测试：`python -m pytest tests/test_pending_orders.py -q` → **10 passed**。
- **已部署海外**：`scp` sync · watchdog 重启 · hash **match** · 日志单轮 ~8s（原 ~24s）。

## 2026-07-03（FUTURES 5m 全量 sync + SF 告警收口）

- 国内 **34 品种 5m** 就绪 · 本机 `SYNC_OK symbols=34` · ingest 76 · B0-2 **pass**。
- SF watchdog：重启 data_manager 加载新 `normalize_frame` · 全品种 sanity dry-run **0**。
- `ensure_single_data_manager.ps1`：启动后自动去重 · 新增 `test_normalize_frame_drops_pre_2020_rows`。

## 2026-07-03（SF 15m watchdog 误报 · 日期口径对齐）

- **根因**：watchdog `sanitize` 丢弃 `<2020` 的 K 线；数据泵 `normalize_frame` 此前保留 `≥1990`，SF 15m 含 **138 行 2016 历史** 被标为 corrupt。
- 国内已 `sanitize --apply --symbols SF` 备份并裁剪；dry-run **files_changed=0**。
- `data_manager_futures.normalize_frame` 对齐 `fengji_core.valid_futures_price_mask` + **date≥2020**，后续写入不再触发同类告警。

## 2026-07-03（天勤 SDK 修复 · tqsdk 优先 + 心跳）

- **根因**：国内 `tqsdk2` 报 `订阅合约信息失败`；官方 `tqsdk 3.10.1` 连接正常（`_test_tq_connect.py` PASS）。
- `data_manager_futures.py`：优先 `tqsdk` 回退 `tqsdk2` · 写入 `data_manager_heartbeat.txt` 供 watchdog。
- 国内已强制重启；首品种 SA **5m=6000** · 实际合约 `CZCE.SA609`。

## 2026-07-03（data_manager 实际主力合约恢复 + tqsdk 测试 stub）

- `data_manager_futures.py` 恢复 **tq_actual_main_contract**：`resolve_data_contract` · manifest · 实际月份 K 线写入（拒绝 KQ.m@ 污染 CSV）。
- 已同步国内并**仅重启 data_manager**（paper/radar/pending 未动）。
- `tests/conftest.py`：本地无 tqsdk2 DLL 时 stub，便于 pytest。
- 测试：`test_data_manager_futures_main_contracts` + `test_data_manager_futures_5m` + `test_futures_main_contract` → **16 passed**。

## 2026-07-03（FUTURES 5m PR-B · sync + SQLite ingest）

- 新增 `scripts/sync_domestic_futures_5m_for_context.py` · `run_sync_domestic_futures_5m_for_context.ps1`（sync 后自动 `import-futures-local`）。
- `market_data_store.import_futures_local` + CLI `import-futures-local`：扫描 `data/futures/{5m,15m,1h}` 短代码 CSV 写入 SQLite。
- 测试：`test_sync_domestic_futures_5m_for_context.py` 2 passed · `test_market_data_store_futures_local.py` 2 passed。
- **前置**：国内 `data/5m/*.csv` 有数据后执行 sync；12:27 复核仍为 0（午休，约 13:00 开始写入）。

## 2026-07-03（FUTURES 5m 数据泵 PR-A）

- `data_manager_futures.py` 增加 **5m**（300s · 默认 6000 根）· `tests/test_data_manager_futures_5m.py` 3 passed。
- 已同步国内并仅重启 data_manager；`data/5m/` 目录已创建，CSV 待交易时段写入。

## 2026-07-03（国内 pending_monitor 重启失败修复）

- 根因：watchdog 传 `--os-state-dir`，新版 `fengji_futures_pending_order_monitor.py` 未声明该参数 → 进程秒退。
- 修复：补 CLI 兼容参数 · 已同步国内 · PID 856 正常运行。

## 2026-07-03（Phase 2 · 国内 W17 远程 + futures state_lock）

- 国内 PG 已在 **127.0.0.1:5432** · alembic **009 head**；`w17_remote_acceptance.py --ssh-tunnel domestic-quant` **7/7**。
- `fengji_futures_pending_order_monitor.py` 增加 `state_lock` · 已同步国内并重启。
- `docs/FUTURES_5M_DATA_PLAN.md`：5m 缺口规划（data_manager 尚未产出）。
- `verify_fengji_api_health.ps1`：alembic 检测误报修复。

## 2026-07-03（Phase 2 · 国内 deploy + pending monitor 对齐）

- `sync_deploy_fengji_api.ps1 -Verify`：124 文件同步国内 · `FENGJI_API_HEALTH_OK`。
- 仓库对齐海外生产 `fengji_pending_order_monitor.py`（`state_lock`）+ `fengji_feishu_notify.py`；修复 `test_pending_orders.py`。
- `docs/PLAN_B_PHASE2_PROGRESS.md` · B0-2 对账 FUTURES 缺 **5m**。

## 2026-07-03（Phase 2 · 本地 PG + W17 全量验收）

- 修复 `scripts/setup_local_pg.ps1` 编码/引号问题；Docker TimescaleDB @5432 启动 · Alembic **009 head**。
- `w17_remote_acceptance.py --auto-server`：**7/7 required + 5/5 optional** · 报告 `runtime/web_validation/w17_remote_acceptance.json`。
- CSV→PG 导入完成：**278 instruments**（crypto 39 + A股 239）· 首次 OPUSDT 权限瞬时失败，重跑成功。

## 2026-07-03（运行态 · SF ack · HYPE #28 平仓）

- 国内 SF DS05 invalid 登记 ack（`SFUSDT-DS05-D1-short-ba832cace3293f52`）· fill audit 72h 通过。
- 海外 pending monitor 重启（解 state.json.lock 争用）；HYPE #28 DS05 long **gap_stop** @ 64.654（07-03 00:00:13）。
- `docs/HYPE28_STOP_FOLLOWUP.md` 签收更新。

## 2026-07-02（Phase 1 完成 · PR #10 merged）

- PR #10 merged（`2ead68e`）：`web/` · feature_gate_api · 静态页测试 · W17 subscription smoke 脚本。
- **方案 B Phase 1 签收**：PR #7–#10 全部完成 · `docs/PLAN_B_PHASE1_COMPLETE.md`。
- 验收：manifest 全绿 · pytest **18 passed** · OpenAPI **38 paths** · W17 preflight **ok=true**。

## 2026-07-02（Phase 1 · PR #8 merged）

- PR #8 merged：chart_bundle · chart_line · context · phase2 manifest。
- 验收：`docs/POST_MERGE_ACCEPTANCE_PR8_20260702.md`。

## 2026-07-02（Phase 1 · PR #10 merged）

- PR #10 merged（`2ead68e`）：`web/` 全量 · feature_gate_api 无 PG mock 修复 · 静态页测试。
- manifest：`scripts/fengji_web_phase1_manifest.txt` · 验收：`docs/POST_MERGE_ACCEPTANCE_PR10_20260702.md`。

## 2026-07-02（Phase 1 · PR #9 merged）

- 分支 `pr/b3-api-deploy-scripts`：`sync_deploy_fengji_api.ps1` · paper-state sync · W17 smoke/remote · phase3 manifest。
- 全量 `fengji_api_deploy_manifest.txt` 本地文件齐 · `test_fengji_api_phase3_manifest` 全绿。

## 2026-07-02（Phase 1 · PR #7 merged）

- PR #7 merged（`1a0bc86`）：services · migrations · auth tests · OpenAPI 38 paths。
- 验收：`docs/POST_MERGE_ACCEPTANCE_PR7_20260702.md`。

## 2026-07-02（Phase 1 · PR #8 chart）

- 分支 `pr/b2-chart-bundle-deps`：`chart_bundle` · `chart_line` · `symbol_names` · `context_*` · phase2 manifest。
- 期货 chart 黄金测试默认 skip（`FENGJI_CHART_FUTURES_GOLDEN=1` 时启用）。

## 2026-07-02（Phase 1 · services MVP）

### PR #7 准备 · services/API 分桶

- 分支 `pr/b2-services-api-phase1`：`services/` · `migrations/` · alembic · docker-compose · Phase1 manifest（67 文件）。
- 新增 `scripts/fengji_api_phase1_manifest.txt` · `tests/test_fengji_api_phase1_manifest.py` · `docs/PLAN_B_PHASE1_SERVICES_BUCKET.md`。
- 验证：pytest phase1 **24 passed** · OpenAPI **38 paths**。

## 2026-07-02（PR #6 merged）

### follow-up PR #6 合并 + Phase 0 签收

- PR #6 `pr/b1-followup-core-compat` merged（`c929b71`）：`STRATEGY_DISPLAY_NAMES` · `ds07` optional `df` · `test_core_post_merge_compat.py`。
- 合并后复验：pytest **38 passed** · OpenAPI **38 paths** · overseas fill audit **invalid_new=0**。
- Phase 0 完成文档：`docs/PLAN_B_PHASE0_COMPLETE.md`。
- HYPE #28：已 sync paper_state + promote 1d（07-01 close 更新为 63.533）· 仍 `STOP_PENDING_MONITOR_BAR` · 待 07-02 D1。

## 2026-07-02

### 方案 B Phase 0 · PR #1–#5 全部合并

- GitHub PR #1–#5 已 merge 到 `main`：fill_supervision（B1）、ops audit（#2）、OpenAPI Phase0（#3）、文档 handoff（#4）、Pencil B0-3 脚本（#5）。
- 合并后验收：`results/post_merge_acceptance_20260702/ACCEPTANCE.md`。
- 修复合并后 core 版本不一致：`constants.STRATEGY_DISPLAY_NAMES`；`ds07.make_ds07_signal` 增加可选 `df` 参数；新增 `tests/test_core_post_merge_compat.py`。
- follow-up 分支：`pr/b1-followup-core-compat`（待 merge）。
- 验证：pytest fill_supervision 相关 **33 passed**；`export_openapi_snapshot.py` **38 paths**；`run_overseas_fill_audit.ps1 -FailOnInvalid` **invalid_new=0** exit **0**。

## 2026-05-28

### 国内全链路重启与 LC DS09 签收（2026-05-28）

- 用户确认接受 LC `ds09_trades=0`（`locks=0`，引擎 `bad_trades=0`）；`docs/LC_DS09_ACCEPTANCE.md` 签收表已更新。
- `scripts/resolve_domestic_paper.ps1`：显式解析 `峰极总定式01-08国内期货A股模拟实盘.py`，修复 GBK/SSH 下 `*模拟实盘.py` 通配符匹配失败。
- `restart_domestic_futures_runtime.ps1`：数据泵 + 模拟盘 + 雷达 + 挂单；`restart_domestic_data_manager.ps1` 补 `PYTHONPATH`。
- `domestic_install_matplotlib.ps1`：国内沙盒图依赖安装。
- **cmd `PYTHONPATH`**：`set "PYTHONPATH=src;packages/fengji_core"`（分号在 cmd 中否则被当命令分隔符）。
- `fengji_radar_order_loop.py`：子进程 `fengji_total_radar.py` 继承 `packages/fengji_core`。

### LC 15m 加长回填与验收清单（2026-05-28 晚）

- `data_manager_futures.fetch_frame`：15m 请求 >8000 时按 12000→…→3000 试探，保留**最长且 `frame_looks_sane` 通过**的一档；1d 仅向下试探且不超过 `FUTURES_1D_LENGTH`。
- 国内 LC 回填结果：`15m=10000`（`data_length=10000`）、`1d=800`、`1h=2600`；12000/11000 的 15m 与 >800 的 1d 对 LC 常校验失败。
- `fengji_core/data.py`：`load_tq_futures_kline_csv`、`parse_tq_datetime_series`；`backtest_ds09.load_m15_frame` 优先天勤 CSV。
- 脚本：`backfill_lc_domestic.ps1`（默认 `M15Length=12000`、`D1Length=800`）、`repair_lc_15m_only.py`、`build_lc_bars_from_1h.py`（仅联调）、`run_lc_ds09_domestic.ps1`（修复 `-BuildFrom1h` 注入远程脚本）。
- 文档：新增 `docs/LC_DS09_ACCEPTANCE.md`。
- 复验：`verify_ds09_lc_session` / `debug_lc_ds09` → `m15_rows≈9911`，`ds09_trades=0`，`locks=0`，`bad_trades=0`。
- Git：`8780b1e`（LC 流水线脚本）、`ec1be47`（加长回填 + 验收清单）。

### 国内 LC DS09 夜盘 session 与沙盒（2026-05-28）

- `assign_session_date(futures=True)` 走 `assign_cn_futures_session_date`（21:00 归次日；天勤 LC 夜盘多为次日 01:00–06:00）。
- `scripts/verify_ds09_lc_session.py` / `run_lc_ds09_domestic.ps1`：国内 690 D1、298 授权 session；当前 15m 仅约 3000 根，窗口内无刺穿边界故 0 笔成交。
- 沙盒：`results/sandbox/lc_ds09/LC_DS09_session_overview.png`（LC 授权日示意）+ `ETH_DS09_trade*_reference.png`（成交标注参考）。

### DS09 九重天接入雷达与挂单器（第 3 步）

- 复述口径与 `docs/DS09_CALIBRATION.md` 一致：D1 已完成 OS 阵营 + 昨日阴阳线授权边界；M15 第一次刺穿只锁定；第一进攻峰 → 第一防守极 → 二次攻击入场；一日一结构。
- `fengji_total_radar.py`：新增 `add_ds09` / `replay_ds09_session`（有 15m 数据时运行）；输出 `PENDING`（防守极已成立待二次攻击）或 `TRIGGERED`。
- `fengji_core/ds09.py`：新增 `assign_session_date`（crypto 日历日 / 期货夜盘）；修复 `make_ds09_signal` 分阶段校验（记录进攻峰时不再要求极已存在）。
- `fengji_pending_orders.py`：默认挂单策略集加入 `DS09`。
- 测试：`tests/test_radar_ds09.py`；全量 `pytest` 62 passed。
- 已同步国外 `fengji_total_radar.py`、`ds09.py`、`fengji_pending_orders.py` 并执行一轮 radar `--once`。

### OS 增量验证（双端 + 本地）

- 新增 `scripts/verify_os_state_incremental.py`、`verify_os_state_overseas.sh`、`verify_os_state_domestic.ps1`。
- 国外 BTC：`processed_len=1835` 两轮雷达后不变；状态文件 `delta2=0`。
- 国内 LC：`processed_len=690` 两轮雷达后不变；`delta1=delta2=0`。
- 本地 IOUSDT 连跑两轮：`size_delta=0`，`incremental_ok=true`。
- DS03 沙盒：`results/sandbox/io_ds03_20260528/IOUSDT_DS03_long_20260526.png`（规则图示；2026-05-26 实盘 IO 日线无 fake_peak，与 `tests/test_ds03` 合成用例区分）。

### 方案 A 验收与运行态巡检

- 运行 `scripts/plan_a_verify.ps1`：**PASSED**（pytest 59 passed、DS05 `bad_trades=0`、ETH 九定式 smoke `bad_audits=0`）。
- 修正 `tests/test_radar_setup_keys.py`：DS03 雷达 `setup_key` 对齐新规（`watch|trigger=` / `{symbol}|DS03|{peak_key}`）。
- 新增 `scripts/check_domestic_runtime_remote.ps1`：本机 SSH 巡检国内 `domestic-quant`（数据泵、雷达循环、LC K 线、OS 状态目录）。
- 国外 `check_overseas_runtime_status.ps1`：data_manager / 雷达 / 挂单 / 模拟盘 / `fengji_os_state` 正常；`radar.json` 15:15 更新。
- 国内巡检：雷达与挂单 15:19 更新；`LC.csv` / `LCUSDT.csv` 15:13 更新；`runtime/fengji_os_state` 已有 LC 等状态文件。

### 海外模拟盘 BNBUSDT 空 CSV 修复

- `data_manager.py`：K 线 **原子写入**（`.tmp` + `replace`），避免同步中被读空文件。
- `src/峰极总定式01-08策略海外模拟实盘.py`（同步为 `overseas_paper_monitor.py`）：`safe_read_csv`、空文件明确报错、`accepted_trades` 空表不再触发 pandas `No columns to parse`。
- `packages/fengji_core/fengji_core/data.py`：新增 `read_csv_strict`。

### 收敛 `src/quant` 与 `packages/fengji_core` 双实现风险

- 确认 `packages/fengji_core/fengji_core` 作为峰极OS与 DS01-DS09 的核心权威源。
- 将 `src/quant/os_engine.py`、`src/quant/ds01.py`、`src/quant/ds03.py`、`src/quant/ds05.py`、`src/quant/ds07.py` 改为兼容层 re-export，避免后续只改一边导致策略分叉。
- 保留 `src/quant` 路径作为现有 CLI、回测脚本、雷达、挂单器和模拟盘的兼容导入入口。
- 验证结果：`quant.*` 导入 smoke 通过；`python -m pytest tests -q` 通过，59 passed（2026-05-28 复验）。

## 2026-05-27

### 固化峰极OS增量连线状态账本

- 更新 `packages/fengji_core/fengji_core/os_engine.py` 与 `src/quant/os_engine.py`：新增 OS 状态导出、恢复、`run_from_state` 增量运行能力；已确认的 raw nodes、hardened nodes、identity nodes、turn events、红蓝阵营和防守/进攻点可持久化为状态账本。
- 更新 `src/fengji_total_radar.py`：雷达默认使用 `runtime/fengji_os_state` 保存每个品种/周期的峰极OS状态；D1保留完整 `hardened_by_bar` 供 DS01/DS06 审计，H1只保存当前硬化峰极线和OS日志，避免大周期循环被历史快照拖慢。
- 更新 `src/quant/ds07.py` 与 `packages/fengji_core/fengji_core/ds07.py`：允许 H1 在不保存完整 `hardened_by_bar` 时仍输出 `hardened_count`，DS08 使用当前 `hardened_nodes` 作为最新骨架。
- 更新 `tests/test_os_engine.py`：新增增量状态与全量运行一致性测试，保证固化后追加K线不会改变既有峰极线和阵营结果。
- 本地验证：`py_compile` 通过；使用内置 Python 轻量脚本验证增量OS与全量OS的 raw nodes、identity nodes、hardened nodes、阵营结果一致。
- 海外服务器同步状态：首次传输过未优化版本；优化后的最终版因海外 SSH banner 超时，尚未确认同步成功，需连接恢复后重传并重启海外雷达/挂单/模拟盘进程。

### 新增数据与回测说明文档

- 新增 `峰极OS_数据与回测说明.md`：整理国内期货、虚拟货币、A股、实盘、模拟实盘和回测数据类型，列出数据目录、结果目录、运行态目录、字段标准、数据库结构和九大定式回测状态。
- 明确当前项目未发现已冻结的 `5m -> 60m` 转换脚本，60m/H1 当前应视为独立数据源、数据库导出或外部已处理 CSV；如需新增转换，必须先冻结国内期货夜盘 session 规则。
- 记录回测统一规则：禁止未来函数污染、信号确认延迟、期货/虚拟货币/A股的资金和费用差异、沙盒图验证要求和已知数据问题。

### 更新 Cursor Project Rules

- 更新 `.cursor/rules/project.mdc`：升级为峰极OS总工程 Cursor 接手规则，要求每次先读取根目录交接文档、峰极OS最高宪法、九大定式总纲、阵营转换、挂单器与服务器部署说明。
- 明确 Cursor 不能自动继承 Codex 旧聊天内容，必须以项目 Markdown 文件作为进度来源；修改前先说明计划，修改后同步 `TODO.md` 和 `CHANGELOG.md`。
- 补充安全红线：不得写入或输出 API Key、Token、Secret、服务器密码、SSH 私钥、完整 webhook 等敏感信息。

### 新增服务器与部署说明文档

- 新增 `峰极OS_服务器与部署说明.md`：整理国内服务器、国外服务器、部署目标、运行模块、数据来源、模拟实盘边界、启动/停止/日志/排查流程和安全红线。
- 明确服务器连接信息、登录用户、密码、API Key、Token、完整 webhook、数据源账号密码均不得写入仓库文档；敏感信息只写“见本地私密配置文件/环境变量/服务器控制台”。
- 标记当前服务器实时运行状态必须通过 SSH 实时检查，不能引用旧日志；国外数据泵守护方式、独立停止脚本和敏感配置迁移仍待补齐。

### 新增挂单器与模拟实盘说明文档

- 新增 `峰极OS_挂单器与模拟实盘说明.md`：整理挂单器目标、架构、DS01-DS09 接入状态、模拟实盘流程、风控安全、相关文件和当前风险。
- 明确当前挂单链路仍是模拟触发，不是真实下单；DS09 九重天雷达/挂单器/模拟盘全链路仍待补齐。
- 文档中不记录任何 API Key、Token、服务器密码、完整 webhook；对敏感信息只保留脱敏处理要求。

### 修正 DS09 九重天 D1 OS 阵营口径，并新增阵营转换专项文档

- 新增 `峰极OS_阵营转换判断.md`：独立记录红/蓝/中性阵营定义、转势状态机、峰极线与阵营关系、DS01-DS09如何调用阵营、相关代码文件、日志验证和已知问题。
- 修正 `packages/fengji_core/fengji_core/ds09.py`：DS09 D1边界生成必须读取进入当日前已完成的D1 OS阵营；红阵营+昨日阴线才授权多头，蓝阵营+昨日阳线才授权空头；缺少D1 `camp` 列直接报错。
- 修正 `src/backtest_ds09.py`：DS09回测先对D1运行峰极OS，再生成当日边界，避免只看昨日阴阳线；交易记录增加 `d1_camp` 审计字段。
- 更新 `tests/test_ds09.py`：新增D1 OS阵营必需和安全D1阵营授权边界的回归测试。
- 更新 `docs/DS09_CALIBRATION.md`、`docs/DS09_DRAFT.md`、`docs/DS09_IN_TOTAL_PATTERN.md`、`docs/CANONICAL_RULES.md`、`docs/FENGJI_TOTAL_PATTERN_SPEC.md`、`峰极OS_最高宪法.md`、`峰极OS_九大定式规则总纲.md`：废止“D1不提供OS阵营方向”的旧表述。
- 更新 `AGENTS.md`、`PROJECT_CONTEXT.md`、`README.md`、`TODO.md`：把 `峰极OS_最高宪法.md`、`峰极OS_阵营转换判断.md`、`峰极OS_九大定式规则总纲.md` 加入接手重点，并记录DS09雷达/挂单器待补齐事项。

### 补全 DS06、DS07、DS09 九大定式总纲

- 更新 `峰极OS_九大定式规则总纲.md`：DS06 外扩峰式从“部分完整”调整为“完整”，明确其核心为转势授权后等待 D/E/F 或 d/e/f 外扩启动，不是破旧极立即入场。
- 更新 `峰极OS_九大定式规则总纲.md`：DS07 共振式从“部分完整”调整为“完整”，当前正式口径为 D1 战略授权 + H1 同向延续或反向并轨；禁止恢复旧的“启动前 H1 必须已同阵营”窄逻辑。
- 更新 `docs/DS07_CALIBRATION.md` 和 `docs/DS07_DRAFT.md`：同步 DS07 当前并轨口径，避免旧文档误导后续 AI 或人工开发。
- 更新 `峰极OS_九大定式规则总纲.md`、`docs/DS09_CALIBRATION.md`、`docs/DS09_IN_TOTAL_PATTERN.md`：根据用户确认，DS09 股票式/A股专属版本等同九重天 D1+M15，不另立一套A股买卖规则。
- 更新 `TODO.md`：将 DS06、DS07、DS09 的规则补全事项标记完成，保留服务器同步、数据覆盖、运行验证等后续任务。

### 自动沉淀峰极OS总工程上下文

本次根据项目扫描结果、当前项目文件、已有代码、已有文档和当前会话上下文，更新根目录总交接文件。目标是让 Cursor 或新的 Codex 会话在无法读取旧聊天记录时，仍能理解这是完整峰极OS总工程，覆盖峰极OS最高宪法、阵营转换、DS01-DS09 九大定式、挂单器、实盘数据、国内/海外服务器、模拟实盘、回测验证和跨工具接手。

### 本次创建/更新的文件

- 更新 `PROJECT_CONTEXT.md`：新增“2026-05-27 总交接版”，补充项目名称、总目标、当前状态、已完成/未完成、目录结构、重要文件、峰极OS最高宪法、阵营转换、九大定式、挂单器、实盘数据、服务器部署、模拟实盘、回测验证、已知问题和接手说明。
- 更新 `AGENTS.md`：新增总工程接手规则，明确必须先读的文件、必须遵守峰极OS最高宪法和九大定式总纲、禁止凭空补全旧聊天、禁止删除未知文件、禁止写入敏感信息、修改前必须说明计划、修改后必须更新文档。
- 更新 `TODO.md`：新增总工程 TODO，按九大定式、阵营转换、挂单器、实盘数据、服务器、模拟实盘、回测、Cursor 接手拆分待办。
- 更新 `CHANGELOG.md`：追加本次上下文沉淀记录。
- 更新 `README.md`：新增总工程接手版摘要，补充项目简介、目录说明、Codex/Cursor 接手方式、运行验证和安全注意事项。

### 当前项目进度摘要

- 峰极OS总工程已形成核心结构：OS 引擎、九大定式、雷达、挂单器、数据泵、模拟盘、回测和交接文档。
- DS01、DS03、DS05、DS07 是最近重点修正对象，需要持续确认本地、国内服务器、海外服务器一致。
- DS02、DS04、DS06、DS08、DS09 已纳入工程，但仍需要同等强度的测试、案例和沙盒图复核。
- A股板块回测已有多个结果目录，但 A股 60 分钟历史数据覆盖不足，限制 DS07/DS08 的历史级结论。
- 国内/海外服务器部署链路已存在，但当前运行状态必须实时 SSH 检查，不能引用旧日志作为当前事实。

### 仍需人工确认的内容

- `packages/fengji_core` 与 `src/quant` 的权威源和同步机制。
- 国内/海外服务器是否已经部署全部最新 DS01、DS03、DS05、DS07 修正。
- DS02、DS04、DS06、DS08、DS09 的最终开仓/确认/撤销规则是否完全冻结。
- 国内期货日盘/夜盘数据泵自动运行表。
- A股 60 分钟数据源的替代或补齐方案。
- 文档中历史遗留敏感信息需要继续脱敏清理。

### 本次沉淀项目上下文

本次目标是把 Codex 旧聊天和当前项目进度沉淀为项目根目录 Markdown 文件，供 Cursor 或新的 Codex 会话继续接手。

### 本次新增或更新的文件

- 新增 `PROJECT_CONTEXT.md`
- 新增 `AGENTS.md`
- 新增 `TODO.md`
- 新增 `CHANGELOG.md`
- 更新 `README.md`
- 新增 `峰极OS_CANONICAL_RULES.md`

### 当前项目进度摘要

- 项目处于方案 A：引擎稳定化阶段。
- 峰极 OS、DS01-DS09、峰极总定式已经成型，但仍需测试和服务器同步复核。
- DS01、DS03、DS05、DS07 最近有重要规则修正，必须确认代码、雷达、挂单、模拟盘一致。
- A股热门20和多个板块已有批量结果，但 60 分钟历史覆盖不足，DS07/DS08 历史级结论需谨慎。
- 国内/海外模拟盘、数据泵和挂单监控需要实时 SSH 复查，旧日志不能当作当前状态。
- 当前虚拟货币阶段只允许模拟和观察，不允许真实下单。

### 下一步建议

1. 新会话先读取 `PROJECT_CONTEXT.md`、`AGENTS.md`、`TODO.md`、`峰极OS_CANONICAL_RULES.md`。
2. 运行 `git status --short`，识别现有未提交改动。
3. 跑核心测试或让用户在本地 PowerShell 跑测试。
4. SSH 检查海外、国内服务器进程、日志、数据新鲜度。
5. 继续 A股板块回测归档，复跑失败股票。
6. 明确并实现国内期货/A股数据泵开盘前自动更新、收盘后停止更新规则。
