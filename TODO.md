# TODO

## 2026-10-15 - v0.1.0 发布 + 数据同步流程

- [x] **发布适用性检查**：工作区 292 个未提交改动（P0-P2 + `fengji_core` 6 新模块 + A 股/海外数据）、本地 `main` 领先 `origin/main` 27 个提交、`gh` 不在 PATH（实际装在 `C:\Program Files\GitHub CLI\gh.exe`，已登录 `huangweishi99-gif`）；敏感文件名扫描 0 命中、待提交 diff 密钥模式扫描 0 命中；`verify_phase2_closeout.py` → `PHASE2_CLOSEOUT_OK`。
- [x] **提交并推送**：`c9ca822`（代码/测试/文档/脚本 67 files）+ `6bb32e2`（数据 223 files）；`git push origin main` → `bdce4bb..6bb32e2`（29 个提交）。
- [x] **发布 v0.1.0**：注解 tag `v0.1.0`（→ `6bb32e2`）已推送；`gh release create v0.1.0 --title "峰极OS v0.1.0 — 首个里程碑版本（方案 A 引擎稳定化）" --notes-file <tmp> --latest`；Release URL `https://github.com/huangweishi99-gif/FJLHXM-V1/releases/tag/v0.1.0`（`isDraft=false` / `isPrerelease=false`，中文标题渲染正常）。
- [x] **发布后数据同步**：提交 `e93b7e7`（7 个海外日线 2026-10-15 盘中更新）；`git push origin main` → `6bb32e2..e93b7e7`。
- [ ] **日常数据同步（可复用流程）**：数据泵实时写 `data/overseas_1d/*.csv` + `data/a_stock/*.csv`（**已被 git 跟踪**，`.gitignore` 的 `data/**/*.csv` 不影响已跟踪文件，故改动可见属预期）。四步：① `git status --short`（确认有 `M data/` 改动）② `git add data/overseas_1d/ data/a_stock/` ③ `git commit -m "data: daily update <YYYY-MM-DD>"` ④ `git push origin main`。
- [ ] **网络容错提示**：`github.com:443` 间歇性阻断（`api.github.com` 可达、本机外网正常）。`git push` 报 `Failed to connect to github.com port 443` / `Recv failure: Connection was reset` 时**重试**即可；远端校验优先 `gh api repos/huangweishi99-gif/FJLHXM-V1/commits/main --jq .sha`。
- [ ] **（可选）一键同步脚本**：可新增 `scripts/sync_data_to_github.ps1`（`git add data/` → commit → push 重试 3 次 → `gh api` 校验），待你确认后再做。
- [ ] **（可选）`gh` 加入 PATH**：把 `C:\Program Files\GitHub CLI` 加入用户 PATH，免去每次绝对路径调用。

## 2026-10-12 - free-stockdb 精华吸收（P0 摸底完成 · P1-P6 启动）

- [x] **P0 摸底**：只读 clone `hello245m/free-stockdb`（MIT License）→ `$env:TEMP\free-stockdb-audit`；逐文件读源码（`stock_sdk.py`/`zhibiao.py`/`native_mcp.py`/`stock_mcp_server.py`/`updater.cpp`/`DATA_SOURCE.md`/`调用方式/*`/`stockdb.conf`/`sync_url.txt`）；输出一页摘要 `docs/FREE_STOCKDB_AUDIT.md`（仓库元信息、目录树、技术栈、10 条核心设计模式、安全要点、12 项借鉴映射、P1-P6 对应表、验证计划、安全边界）。
- [x] **License 验证**：`Copyright (c) 2026 hello245m` MIT License；允许借鉴 / 复制 / 修改 / 合并 / 发布 / 再授权 / 销售；条件：保留版权声明。派生代码文件头注明「Design inspired by free-stockdb MIT © 2026 hello245m」。
- [x] **决策**：数据底座接入策略选 (b) **借鉴 Python 设计模式**而非引入二进制（`stockdb.pyd` + LevelDB + Rust 扩展均不依赖），与本项目 sqlite 共存。
- [x] **安全边界声明**：不复制 `stockdb.conf` 里注释的默认密码示例 `this-is-a-very-strong-password-32ch`；不引入其二进制 / LevelDB / Rust；不动峰极线 / 阵营 / DS01-DS09 / 峰极OS 任何字段。
- [x] **10 条核心设计模式吸收**：MCP 装饰器自研框架（17KB stdlib）/ `get_data()` 签名 / 复权因子预加载 + 二分 / BoardIndex 四向索引 / 39 指标 + 5 指数 / manifest + SHA-256 + size 校验 / 多源挂载（本地/HTTP/file://）/ 周月分钟 K 内存动态合成（含 A 股交易时段）/ K-V 协议风格 / HTTP 极简 API。
- [x] **P1 板块映射**（吸收 4.4 BoardIndex）：**2026-10-12 完成**。新增 `src/sector_mapping.py`（4 向索引 + 类别白名单 + 字段白名单 + 离线优先）；`data/sectors/a_stock_sectors.json` v1 种子（11 概念 + 3 SW 占位）；`scripts/build_sector_index.py`（东财拉取 + 合并 SW 占位 + 旧 symbols 保留 + version 递增）；`src/batch_backtest_a_stock_sector.py` 加 `--use-sector-index` / `--sector-json`（默认关，不破原路径）；`tests/test_sector_mapping.py` 28 例 + `tests/test_build_sector_index.py` 8 例；**40 passed in 0.51s**；lint 0 错误；**默认行为完全不变**（9 DEFAULT_SECTORS + 11 板块 master 归档 + DS01-DS09 零影响）。下一步 P2 复权+批量查询。
- [x] **P2 复权+批量查询 阶段 A**（吸收 4.5 AdjFactorIndex + get_data）：**2026-10-12 完成**。新增 `src/adj_factor.py`（AdjFactorIndex + to_qfq/hfq/none + AdjFactorMissingError，25 例测试）；`scripts/fetch_a_stock_adj_factors.py`（东财拉 f60 复权因子，main(argv=None) 可注入，17 例测试）；`src/market_data_resolve_a_stock.py`（仿 resolve_futures_csv 的 A 股 resolve，9 例测试）；`src/bulk_query.py`（BulkQuery.get_data + get_data_async asyncio.to_thread 包装，19 例测试）；**P2 阶段 A 共 70 passed**；lint 0 错误；**0 个既有 src/ 文件被改**（回测入口 / DS01-DS09 / OS / 阵营 / 模拟实盘 / 事件写入量 全部 0 影响）；sqlite schema 不变 / `data/a_stock/*.csv` 不变。**阶段 B 标记待你确认**——在 `backtest_a_stock_fengji.py` / `batch_backtest_a_stock_sector.py` 加 `--fq` / `--use-bulk-query` 开关（默认关）需另行批准。**已知风险**：东财 f60 是否真为 adj_factor 需你跑一次 `python scripts/fetch_a_stock_adj_factors.py --codes 000021` 验真实值；复权约定按东财不复权口径推断（与 free-stockdb 可能有细微差异）。
- [ ] **P2 复权 + 批量查询**（吸收 4.1/4.2/4.3）：新增 `src/adj_factor.py`（qfq/hfq/none/adj_factor）+ `src/bulk_query.py`（仿 `rd.get_data()` 签名但用本地 sqlite）；tests≥10 例；DS09 / 板块回测结果与不复权可对比。
- [ ] **P3 AI MCP 入口**（吸收 4.8 + 4.10）：新增 `src/services/mcp_fengji.py`（stdio MCP server，**直接抄** `NativeMCP` 17KB stdlib）+ 配套 `src/services/http_fengji.py`；工具集：get_kline / list_sectors / sector_stocks / get_indicator / get_index；暴露给 Codex/Cursor/Claude 默认 stdio；tests≥8 例；安全扫描 0。
- [ ] **P4 数据源多通道**（吸收 4.6/4.7/4.9）：`dataN/` 多源挂载（新浪 + 东财 + AKShare + 通达信）；`sync_url.txt` 入口；`manifest.txt` + SHA-256 + size 校验；增量同步（已存在+一致跳过）；Zstd 落盘（旧 CSV 保留）；tests≥10 例；数据覆盖率 ≥99%；磁盘占用 ≤旧 CSV 1/3。
- [ ] **P5 指标层**（吸收 4.3/4.5）：`src/indicators.py`（39 技术指标 + 5 指数加权）；周/月/分钟 K 内存动态合成（含 A 股交易时段 9:30-11:30 + 13:00-15:00）；纯 pandas + numpy（**不引入 Rust**）；与 OS 解耦；tests≥15 例。
- [ ] **P6 性能加速（可选）**：仅在 P4/回测仍慢时考虑 Rust / C 扩展；当前不做。
- [ ] **MIT 署名义务**：所有借鉴模块文件头添加「Design inspired by free-stockdb MIT © 2026 hello245m」（P1 阶段开始落地）。

---

## 2026-08-11 - Codex handoff + WIP commit + paper signal strength analysis

- [x] **Fresh handoff**: read CODEX_APP_HANDOFF.md, PROJECT_CONTEXT.md, AGENTS.md, TODO.md, CHANGELOG.md, all constitution/canonical/rule docs; git status, git log, verify_phase2_closeout PASS.
- [x] **Dual-server runtime check**: `check_dual_server_runtime_status.ps1` -> PASS; domestic data_manager heartbeat 285s, overseas all processes running; notification audit failures=0.
- [x] **Core test suite**: os_engine/ds01/ds03/ds05 + pending/futures_pending + radar_ds04-08 + fill_supervision + data_manager_futures_5m -> **86 passed**; Phase 2 closeout `PHASE2_CLOSEOUT_OK`.
- [x] **WIP classification**: separated modified files into code+tests (15 files), docs (9 files), scripts/deploy (7 files), and data-only (7 CSV files restored to HEAD).
- [x] **Data CSV restore**: `git checkout -- data/overseas_1d/*.csv` to revert daily-refresh cache files.
- [x] **Feishu paper trade signal strength analysis**: collected 622 fill events from JSONL, 552 Feishu claims; DS01 strongest (303 fills, 48.7%), DS05/DS07 tied second (81 each, 13%), DS08 (68, 10.9%), DS03 (53, 8.5%); domestic 81 open positions; overseas paper positions tracked.
- [x] **P1**: DS02 standalone tests created (15 tests: make_ds02_signal, update_stop, check_stop, audit_camp_direction).
- [x] **P1**: DS04 standalone tests created (16 tests: make_ds04_signal, k2_is_weakest, no_price_gap, update_stop, check_stop, audit_structure).
- [x] **P1**: DS05 K2 extreme sandbox verified (9 tests pass; CJ/FG/SA sandbox images archived in runtime/ds05_sandbox/).
- [x] **P1**: DS08 5-point denial-confirmation verified (12 tests pass including test_ds08_pending_fill.py).
- [x] **P1**: camp-conversion sandbox 4/4 crypto (RENDER/IO/DOGE/LTC) confirmed VALID in sandbox archive.
- [x] **Full test regression**: 630 passed, 17 skipped.（2026-08-14 重跑：**700 passed, 17 skipped**，`--basetemp` 定向临时目录规避沙箱删除保护误拦截；修复 `test_extract_crypto_open_position` 未隔离真实 pending_orders.csv（BNBUSDT long ACTIVE 触发方向矛盾过滤），显式 monkeypatch `PENDING_ORDER_PATHS=(None,)` 后全量 0 failed）
- [x] **.gitignore**: added `archives/` and `.vscode/`.
- [x] **Archival docs**: committed 8 root-level cleanup/handoff/baseline .md reports (`ARCHIVE_*`, `CLEANUP_*`, `CURRENT_BASELINE_*`, `HANDOFF_*`, `PG_BASELINE_*`, `WEB_MONITOR_*`).
- [x] **P2 A股板块回测归档**: 11 sectors (CPO/算力/BK0900/电动乘用车/半导体/飞行汽车/锂电池/互联网金融/证券Ⅱ/航空装备Ⅱ/虚拟机器人), 274 trades, 233 stocks, 1.46M cumulative PnL; 4/4 audit tests pass.
- [x] **P2 60m 长历史补齐**: A股239/239 60m complete; 加密16/16 1H_1825d complete; 美股224/224 1H complete; 期货36 1d vs 30 1h (6 missing: AO/LH/P/PG/SC/TA - low-data futures from SHFE/DCE/INE/CZCE, ~20KB each, limited history).
- [x] **P2 DS09 成交沙盒**: LC locks=0 (no signals to sandbox); ETH/BNB/TAO/生猪 already sandboxed; DS09 Live Watch running ACTIVE on overseas crypto radar.
- [x] **P3 untracked files clean-up**: batch-added 116 files (140 tests, 40+ strategy/deployment docs, 5 src modules, designs, reference rules, operational scripts); .gitignore extended with test-results/.
- [x] **P4 ops batch commit**: 307 files (236 scripts + 61 docs + 5 fengji_core modules + 5 misc) in `9cb8c98`; deleted 45 `_tmp_*`/`_` temp diagnostic scripts; untracked count now 0 (only 7 data-pump CSV cache files remain modified, left as-is). 630 tests pass.

## 2026-08-10 - Domestic heartbeat check threshold

- [x] **Fresh runtime check**: `check_dual_server_runtime_status.ps1` produced PASS evidence under `runtime/logs/dual_runtime_check/20260810_100638`; domestic and overseas checks both exited 0.
- [x] **False stale warning removed**: `check_domestic_status.ps1` now uses `$HeartbeatMaxAgeSec = 420`, matching the 300-second data-pump poll interval and existing watchdog contract.
- [x] **Watchdog verification aligned**: `verify_domestic_watchdog.ps1` now uses the same 420-second heartbeat threshold.
- [x] **Targeted sync**: synchronized only `scripts/check_domestic_status.ps1` and `scripts/verify_domestic_watchdog.ps1` to the domestic server; no process restart.
- [x] **Verification**: runtime script tests passed, PowerShell parser checks passed, domestic schedule audit reported `failures=0`, and Phase 2 closeout stayed `PHASE2_CLOSEOUT_OK`.

## 2026-07-16 - Domestic paper state-file write race fix

- [x] **Live root cause confirmed**: the 10:09:06 UR alert was a real `WinError 5` from the long-running domestic paper process replacing `runtime/fengji_futures/state_futures_v2.json` while the 5-second pending monitor was writing the same file. The paper process had been running since 2026-06-28 and did not use the shared sidecar lock.
- [x] **Shared read-modify-write boundary**: the domestic paper monitor now uses `fengji_core.state_lock.update_state_file`; each commit reloads the latest state under `state_futures_v2.json.lock`, applies only the in-memory result for the current symbol, and atomically saves before releasing the lock.
- [x] **Short critical section**: data loading, strategy-engine execution, trade CSV/event logging, console output, and Feishu HTTP calls remain outside the state lock. This prevents the pending monitor from being blocked by strategy scans or network I/O.
- [x] **Lost-update regression**: added `tests/test_domestic_paper_state_lock.py`; concurrent paper commits and pending-position inserts preserve all 20 unique orders. The coordination audit now requires the paper monitor, shared lock dependency, split scan/commit flow, and post-lock effect dispatch.
- [x] **Focused verification**: paper-lock, domestic coordination, futures pending, generic pending, fill supervision, and Feishu trade tests -> `58 passed`; coordination audit -> `failures=0`; security boundary audit -> `failures=0 warnings=0`; Phase 2 closeout -> `PHASE2_CLOSEOUT_OK`.
- [x] **Targeted deployment**: synchronized only the staged domestic paper script after confirming the already-deployed `state_lock.py` hash matched local; backed up the previous remote paper source and restarted only the domestic paper process.
- [x] **Remote acceptance**: deployed paper hash matches local; `paper_python_count=1`, `pending_python_count=1`, paper error log remains empty, and the deployed paper completed 30 concurrent temp-state commits with `positions=30`, `unique_orders=30`, `initialized=True`.
- [x] **Safety boundary**: no live paper state, position, entry, stop, direction, equity, peak-line, camp-conversion, DS01-DS09 strategy, trigger, risk-control, or real-order logic was manually changed; no credential or webhook value was written to the repository or output.

## 2026-07-16 - Domestic JD main-contract switch fill alert fix

- [x] **Root cause confirmed**: `JDUSDT-DS01-D1-short-b3b8ea0653c242ea` was created at 13:01:04 against `DCE.jd2608`; the manifest switched to `DCE.jd2609` at 13:02:29; the old 4590 trigger was simulated as filled at 13:02:40 after the 15m price range relocated to 4393-4435.
- [x] **Pending-order contract identity**: futures pending orders now carry `data_contract`, and contract identity participates in `order_id` generation so a post-roll order cannot inherit the old order identity.
- [x] **Pre-fill roll guard**: the domestic pending monitor cancels explicit or legacy pre-switch orders with `cancel_reason=main_contract_switched` before checking K-line crosses. Contract-switch cancellation does not blacklist the setup_key for a fresh post-roll radar order.
- [x] **Post-fill audit classification**: domestic fills spanning `created_at <= contract_switched_at <= fill_time` are reported as `exec_gap`, not DS strategy INVALID. Remote 72h audit now reports `valid=15`, `invalid=0`, `invalid_new=0`, `exec_gap=1`, `needs_data=0`, `skipped=2`.
- [x] **Watchdog dedup**: domestic fill-supervision alerts now fingerprint `invalid_new_fills`; an unchanged set is logged and suppressed instead of being pushed every 30 minutes.
- [x] **Existing JD position quarantine**: backed up the domestic paper state and added only `entry_data_contract=DCE.jd2608` plus contract-switch quarantine metadata to the open JD position. Entry 4590, stop 4688, direction, and equity were not changed. Cross-contract positions are excluded from automatic stop processing.
- [x] **Deployment**: synchronized only `futures_main_contract.py`, `fengji_pending_orders.py`, `fengji_futures_pending_order_monitor.py`, `audit_paper_fills.py`, and `watchdog_domestic.ps1`; restarted only the domestic pending monitor, which remains single-process.
- [x] **Live acceptance**: forced one watchdog supervision round -> `fill_supervision ok`; both `fill_supervision_invalid.alert` and `.fingerprint` are absent.
- [x] **Verification**: focused contract/pending/fill-supervision/deploy-manifest suite -> 69 passed; Python compile and PowerShell parser checks passed; `audit_security_boundaries.py` -> `failures=0 warnings=0`; `verify_phase2_closeout.py` -> `PHASE2_CLOSEOUT_OK`.
- [x] **Safety boundary**: no peak-line, camp-conversion, DS01-DS09 core strategy, trigger-price, stop-price, position direction, or equity logic was changed; no real order path or credential value was added.

## 2026-07-14 - Dual-server runtime log retention guard

- [x] **Dry-run retention entry**: added `scripts/manage_dual_runtime_check_logs.ps1` with a 14-day default retention window; it only reports candidates unless `-Execute` is explicitly supplied.
- [x] **Managed-directory boundary**: cleanup eligibility requires an exact `yyyyMMdd_HHmmss` directory name, containment under the configured log root, no child directories, and only `SUMMARY.md`, `domestic_runtime.log`, or `overseas_runtime.log` files. Directories with unknown content are skipped.
- [x] **Deletion safety**: execute mode resolves every candidate to an absolute path and rechecks root containment plus the timestamp name before recursive deletion. No live project logs were deleted during this work.
- [x] **Current local audit**: dry-run found `managed_count=5`, `incomplete_count=3`, `skipped_unmanaged_count=0`, `candidate_count=0`, `deleted_count=0`.
- [x] **Empty-batch prevention**: `check_dual_server_runtime_status.ps1` now rejects `-SkipDomestic -SkipOverseas` before creating the output directory, preventing invalid no-check calls from leaving new empty batches.
- [x] **Safety boundary**: this only manages wrapper-owned local runtime evidence. It does not modify peak lines, camp conversion, DS01-DS09 logic, pending triggers, stops, risk control, simulated fills, server processes, credentials, tokens, passwords, or webhook values.
- [x] **Verification**: `python -m pytest tests\test_runtime_check_scripts.py -q` -> 15 passed; PowerShell parser smoke -> `PARSER_OK`; `python scripts\verify_phase2_closeout.py` remains required as the final gate.

## 2026-07-14 - Latest dual-server runtime status reader

- [x] **Read-only latest status entry**: added `scripts/show_latest_dual_runtime_status.ps1` to locate the newest `runtime/logs/dual_runtime_check/*/SUMMARY.md` without reconnecting to either server.
- [x] **Freshness guard**: the reader reports `FRESH` or `STALE` from the summary file age; `-MaxAgeMinutes` defaults to 120 so an old PASS cannot be mistaken for current runtime health.
- [x] **Automation exit codes**: fresh PASS exits 0, fresh FAIL exits 1, missing or malformed summaries exit 2, and stale summaries exit 3; domestic and overseas exit codes are emitted as text fields.
- [x] **Safety boundary**: the reader is local and read-only. It does not modify runtime state, peak lines, camp conversion, DS01-DS09 logic, pending triggers, stops, risk control, simulated fills, credentials, tokens, passwords, or webhook values.
- [x] **Verification**: `python -m pytest tests\test_runtime_check_scripts.py -q` -> 12 passed; live latest-status read -> `status=PASS`, `freshness=FRESH`, domestic `exit_code=0`, overseas `exit_code=0`.

## 2026-07-14 - Dual-server runtime check wrapper

- [x] **One-command local entry**: added `scripts/check_dual_server_runtime_status.ps1` to run the existing domestic and overseas read-only runtime checks from one local command.
- [x] **Exit-code aggregation**: the wrapper records each side's exit code and exits nonzero if either side fails; an empty selection is rejected instead of silently passing.
- [x] **Runtime evidence**: check output is saved under `runtime/logs/dual_runtime_check/<timestamp>/` with `domestic_runtime.log`, `overseas_runtime.log`, and `SUMMARY.md`.
- [x] **Safety boundary**: this only wraps existing status checks. It does not modify peak lines, camp conversion, DS01-DS09 logic, pending trigger rules, stops, risk control, simulated fills, credentials, tokens, passwords, or webhook values.
- [x] **Verification**: `python -m pytest tests\test_runtime_check_scripts.py -q` -> 7 passed; PowerShell parser smoke -> `PARSER_OK`; live dual-server wrapper -> `status: PASS`, domestic `exit_code=0`, overseas `exit_code=0`; log scan found no `https://`, Feishu hook fragment, or common key/token markers.

## 2026-07-14 · 海外运行态检查接入通知审计

- [x] **运行态检查接入**：`scripts/check_overseas_runtime_status.ps1` 新增 `OVERSEAS NOTIFICATION AUDIT` 小节，海外运行态检查会自动只读运行 `scripts/audit_overseas_notification_coverage.py`，同步覆盖 DS01-DS09 入口和飞书状态词。
- [x] **解释器口径修正**：海外检查脚本优先使用 `.venv/bin/python`，不存在时才回退 `python3`；`summarize_pending_effective_status.py` 和 `audit_overseas_notification_coverage.py` 共用该解释器，避免系统 Python 缺 `numpy` 导致误报。
- [x] **导入路径加固**：`scripts/audit_overseas_notification_coverage.py` 采用与国内审计一致的 `prepend_import_path`，强制把 `src`、`packages/fengji_core`、项目根目录移到导入路径前面，保证直接入口和模块入口结果一致。
- [x] **远端同步与验收**：已同步 `scripts/check_overseas_runtime_status.ps1` 和 `scripts/audit_overseas_notification_coverage.py` 到海外服务器；远端 `py_compile` 通过；完整运行态检查显示 `PYTHON_BIN=.venv/bin/python`、通知审计 `failures=0`。
- [x] **当前海外快照**：海外通知审计显示 DS01-DS09 覆盖完整，`overseas_feishu_status_wording=ok`；effective pending 当前 `total=23`、`actionable=15`、`review_candidate_orders=0`。
- [x] **验证**：`python scripts\audit_overseas_notification_coverage.py` 与 `python -m scripts.audit_overseas_notification_coverage` 均为 `failures=0`；`python -m pytest tests\test_runtime_check_scripts.py tests\test_audit_overseas_notification_coverage.py -q` -> **9 passed**；远端直接入口和模块入口均为 `failures=0`；`check_overseas_runtime_status.ps1` 远端只读验收通过。
- [x] **安全边界**：本次只改运行态检查脚本、审计脚本同步和测试，不修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损、风控或模拟成交规则；未重启海外进程。

## 2026-07-14 · 国内运行态检查接入通知审计

- [x] **运行态检查接入**：`scripts/check_domestic_runtime_remote.ps1` 新增 `DOMESTIC NOTIFICATION AUDIT` 小节，国内运行态检查会自动只读运行 `scripts/audit_domestic_notification_coverage.py`，不再依赖人工单独触发。
- [x] **解释器口径修正**：国内远端 effective pending 与通知审计均优先使用 `.venv\Scripts\python.exe`，不存在时才回退 `python`，避免系统 PATH 或 Python 环境差异造成误报。
- [x] **输出与安全边界**：远端审计块使用 `-OutputFormat Text -EncodedCommand`，远端脚本块内只用 `Write-Output`，并显式设置 `PYTHONPATH=src;packages/fengji_core;.`；不打印 webhook、Token、密码或完整命令行。
- [x] **契约测试**：`tests/test_runtime_check_scripts.py` 增加国内通知审计小节断言，锁定 `audit_domestic_notification_coverage.py`、`PYTHONPATH` 和文本输出。
- [x] **国内远端实测**：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_domestic_runtime_remote.ps1` 已跑通；PG/SC 15m `ACCEPTANCE_OK`；通知审计 `failures=0`；`radar python count=1`、`pending python count=1`。
- [x] **验证**：`python -m pytest tests\test_runtime_check_scripts.py tests\test_audit_domestic_notification_coverage.py -q` -> **9 passed**；`python -m py_compile scripts\audit_domestic_notification_coverage.py src\fengji_futures_pending_order_monitor.py` 通过；`check_domestic_runtime_remote.ps1` 远端只读验收通过。
- [x] **安全边界**：本次只改运行态检查脚本和测试，不修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损、风控或模拟成交规则；未重启远端进程。

## 2026-07-13 · 国内期货A股模拟成交飞书状态对齐

- [x] **国内成交状态明确化**：`src/fengji_futures_pending_order_monitor.py` 的国内挂单成交推送改为与海外一致的状态型文案；多头成交显示 `已买入`，空头成交显示 `已卖出`，并使用 `预计挂单买入/卖出价格`、`挂单买入/卖出价格已成交`、`预计挂单平仓价格` 字段，替代旧 `挂单触发价` / `模拟成交价`。
- [x] **国内平仓状态明确化**：国内止损平仓推送按原持仓方向显示 `已卖出平仓` 或 `已买入平仓`，并补充 `消息类型`、`状态`、`预计挂单平仓价格`、`平仓价格已成交`。
- [x] **契约测试**：`tests/test_futures_pending_orders.py` 增加国内 CF 多头成交、SA 空头成交和平仓状态断言，防止国内推送退回旧标题。
- [x] **验证**：`python -m pytest tests\test_futures_pending_orders.py tests\test_feishu_trade_notify.py tests\test_feishu_paper_notify.py -q` -> **14 passed**；`python -m py_compile src\fengji_futures_pending_order_monitor.py` 通过。
- [x] **安全边界**：本次只改通知展示层和测试，不修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损、风控或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- [x] **国内部署**：已仅同步 `src/fengji_futures_pending_order_monitor.py` 到国内服务器，远端 `py_compile` 通过；已定向重启国内 pending monitor，复查 `pending_count=1`、新 PID `3204`。

## 2026-07-13 · 国内飞书状态文案防回归审计

- [x] **只读审计入口**：新增 `scripts/audit_domestic_notification_coverage.py`，对国内挂单成交和平仓推送做状态词 smoke，检查 `已买入`、`已卖出`、`已卖出平仓`、`已买入平仓`，并拒绝旧 `挂单触发价` / `模拟成交价` 文案回流。
- [x] **runtime 快照**：审计脚本读取国内默认 `pending_orders.json`、`futures_pending_state.json`、`state_futures_v2.json`、`radar.json`，只汇总策略计数、有效状态、可复核候选，不改写运行态。
- [x] **同步清单**：`scripts/sync_deploy_domestic.ps1` 与 `scripts/fengji_domestic_deploy_manifest.txt` 纳入该审计脚本，后续国内一键同步不会遗漏。
- [x] **导入路径加固**：审计脚本启动时强制把 `src`、`packages/fengji_core`、项目根目录移到导入路径前面，避免远端 `python scripts\audit_domestic_notification_coverage.py` 被 `scripts` 目录里的同名/旧模块遮蔽后误报。
- [x] **验证**：`python scripts\audit_domestic_notification_coverage.py` 与 `python -m scripts.audit_domestic_notification_coverage` 均为 `failures=0`；`python -m pytest tests\test_audit_domestic_notification_coverage.py tests\test_futures_pending_orders.py tests\test_feishu_trade_notify.py tests\test_feishu_paper_notify.py -q` -> **18 passed**；`python -m py_compile scripts\audit_domestic_notification_coverage.py src\fengji_futures_pending_order_monitor.py` 通过；国内远端直接入口和模块入口均为 `failures=0`。
- [x] **安全边界**：本次只增加通知审计、测试和同步清单，不修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损、风控或模拟成交规则。

## 2026-07-12 · 玻璃/纯碱 DS05 沙盒图补齐

- [x] **FG/SA 补图**：运行 `python scripts\verify_d4_pattern_cases.py --plot --out-dir results\sandbox\d4_phase2_20260712`，补出 `results/sandbox/d4_phase2_20260712/FG_玻璃_DS05_2026-07-07.png`；对 SA 使用 `plot_live_ds05_sandbox.py` 按 K1/K2/K3 时间锚点补出 `results/sandbox/d4_phase2_20260712/SA_纯碱_DS05_2026-07-07.png`。
- [x] **归档索引更新**：`scripts/audit_disputed_signal_sandbox_archive.py` 改为识别所有 `results/sandbox/d4_phase2_*` 目录，并重新生成 `results/disputed_signal_sandbox_archive_20260712/INDEX.md`；当前 `archived_visuals=12/12`、`missing_visuals=0`、`missing_evidence=0`。
- [x] **目视检查**：FG/SA 两张图均可打开，包含 K 线、`hardened_fengji_line`、阵营背景、K1/K2/K3、入场和止损线。
- [x] **验证**：`python scripts\audit_disputed_signal_sandbox_archive.py` -> `failures=0`；`python -m pytest tests\test_audit_disputed_signal_sandbox_archive.py -q` -> **4 passed**；`python -m py_compile scripts\audit_disputed_signal_sandbox_archive.py` 通过。
- [x] **安全边界**：本次只补沙盒图和归档索引，不修改峰极线、阵营转换、DS01-DS09 核心逻辑、雷达、挂单、止损或模拟成交规则。

## 2026-07-12 · 争议信号沙盒图归档索引

- [x] **归档索引审计**：新增 `scripts/audit_disputed_signal_sandbox_archive.py`，盘点 RENDERUSDT/IOUSDT/DOGEUSDT DS01、IOUSDT/ETHUSDT DS03、RENDER/IO/DOGE/LTC 阵营图、红枣/玻璃/纯碱 DS05 K2 可能极等争议样本的现有图与报告。
- [x] **统一索引产物**：生成 `results/disputed_signal_sandbox_archive_20260712/INDEX.md` 与 `archive_index.json`；当前 12 个样本中 `archived_visuals=12`、`missing_visuals=0`、`missing_evidence=0`。
- [x] **缺图边界已闭合**：玻璃 FG DS05、纯碱 SA DS05 已在 `results/sandbox/d4_phase2_20260712/` 补独立 PNG，归档索引不再有 `missing_visual`。
- [x] **验证**：`python scripts\audit_disputed_signal_sandbox_archive.py` -> `failures=0`；`python -m pytest tests\test_audit_disputed_signal_sandbox_archive.py -q` -> **4 passed**；`python -m py_compile scripts\audit_disputed_signal_sandbox_archive.py` 通过。
- [x] **安全边界**：本次只做结果归档盘点和索引写入，不重算策略、不生成新交易、不修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单、止损或模拟成交规则。

## 2026-07-12 · DS01/DS03/DS05/DS07 跨入口一致性审计

- [x] **只读契约审计**：新增 `scripts/audit_ds_consistency_contract.py`，静态复核 DS01 左30 <=2、DS03 failed high/low、DS05 K2 possible extreme、DS07 新共振口径是否同时保留在核心包、雷达、pending monitor、paper monitor、fill supervision 和成交后沙盒图编排入口。
- [x] **防旧逻辑回流**：审计覆盖 `packages/fengji_core/fengji_core/ds01.py` / `ds03.py` / `ds05.py` / `ds07.py`、`src/fengji_total_radar.py`、`src/fengji_pending_order_monitor.py`、`src/overseas_paper_monitor.py`、`packages/fengji_core/fengji_core/fill_supervision.py`、`scripts/generate_fill_sandbox_review.py`、DS03/DS07 沙盒图入口。
- [x] **验证**：`python scripts\audit_ds_consistency_contract.py` -> `failures=0`；`python -m pytest tests\test_audit_ds_consistency_contract.py -q` -> **4 passed**；`python -m py_compile scripts\audit_ds_consistency_contract.py` 通过。
- [x] **安全边界**：本次只增加只读审计和测试，不生成/改写交易数据，不修改峰极线、阵营转换、DS01-DS09 核心逻辑、雷达触发、挂单、止损或模拟成交规则。
- [x] **后续仍需图形复核**：RENDERUSDT、IOUSDT、DOGEUSDT、ETHUSDT、红枣、玻璃、纯碱等争议样本仍需按沙盒图逐笔归档；本次静态审计不替代人工看图。（2026-08-13：`audit_disputed_signal_sandbox_archive.py` 盘点 **12/12 全部 archived**，`failures=0`；DS01 左30×3、DS03×2、OS 阵营图×4、DS05 K2×3 均已存在 PNG/SVG 视觉归档；仅 ETHUSDT DS03 为 SVG 非 PNG。2026-08-13 晚已补充 PNG，12/12 全部视觉归档完成，source 因代码版本演进由 active_low 变为 trigger_ref，核心场景一致）

## 2026-07-10 · 总定式统一账本回归

- [x] **统一账本契约审计**：新增 `scripts/audit_unified_ledger_regression.py`，用合成 candidates 验证 `merge_candidates` 的 accepted/rejected/ledger events，覆盖同向持仓上限、反向持仓拦截、缺失入场时间拒绝和最终 close 事件。
- [x] **批量评分契约**：审计脚本用临时目录验证期货 `score_futures_results` 与 crypto `score_crypto_results` 输出 `*_scored_accepted_trades.csv`、`*_by_strategy.csv`，并保留 accepted/rejected/bad_audits 汇总字段。
- [x] **现有测试补充回归**：`PYTHONPATH=services;src;packages/fengji_core` 后运行账本/监控/回测接口相关测试 -> **16 passed, 5 skipped**；未补环境时 `test_monitor_ledger.py` / `test_backtest_trade_pnl_ratio.py` 会因 `radar_snapshot` / `db` 导入路径缺失而 collection error。
- [x] **验证**：`python scripts\audit_unified_ledger_regression.py` -> `failures=0`；`python -m pytest tests\test_audit_unified_ledger_regression.py -q` -> **4 passed**；补环境重点集 -> **16 passed, 5 skipped**；`python -m py_compile scripts\audit_unified_ledger_regression.py` 通过；`verify_phase2_closeout.py` 仍为 `PHASE2_CLOSEOUT_OK`。
- [x] **安全边界**：本次只增加合成数据审计和测试，不读写真实交易结果，不修改峰极线、阵营转换、DS01-DS09 核心逻辑、回测规则、雷达、挂单或模拟成交规则。

## 2026-07-10 · 九大定式单定式回归测试

- [x] **单定式回归**：运行现有 DS 单测与雷达定式测试集，覆盖 DS01、DS03、DS05、DS09 核心测试，DS03/DS08 pending fill，DS04-DS09 radar 入口。
- [x] **覆盖边界**：2026-07-10 曾记录"没有独立 `test_ds02.py`/`test_ds04.py`/`test_ds06.py`/`test_ds07.py` 核心单测"；2026-08-11 已补 DS02（15 例）/DS04（16 例），2026-08-14 已补 **DS06（21 例）/DS07（24 例）/DS08（22 例）**，九大定式独立核心单测全部就位（完整核心+雷达+挂单回归 201 passed, 1 skipped）。
- [x] **验证**：`python -m pytest tests\test_ds01.py tests\test_ds03.py tests\test_ds05.py tests\test_ds09.py tests\test_ds09_futures_session.py tests\test_ds03_pending_fill.py tests\test_ds08_pending_fill.py tests\test_radar_ds04.py tests\test_radar_ds05.py tests\test_radar_ds06.py tests\test_radar_ds07.py tests\test_radar_ds08.py tests\test_radar_ds09.py -q` -> **56 passed, 1 skipped**。
- [x] **安全边界**：本次只运行测试并记录结果，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、雷达、挂单、止损或模拟成交规则。

## 2026-07-10 · A股板块结果归档覆盖审计

- [x] **归档覆盖只读审计**：新增 `scripts/audit_a_stock_sector_archive.py`，盘点 `results/a_stock_all_sectors_overview.csv`、`results/a_stock_all_sectors_master_summary.csv`、`results/fengji_total_a_stock_sectors_os20260529_run.log` 与旧 `results/a_stock_sector_archive_ds07_fixed.zip`。
- [x] **当前归档事实**：全量汇总 CSV 仍保留 11 个板块、274 条股票明细、`bad_audits=0`；旧 zip 可读但只包含 CPO/算力/半导体/虚拟机器人 4 个板块摘要；`master_summary` 中 274 个 `source_file` 与 274 个 `out_dir` 当前本地均不存在，因此不是完整 per-stock 明细归档。（2026-08-14：12 个板块 `sector_summary.csv` 已从 master summary 反推重建，274 行完整保留；`source_file` 缺口从 274 降到 262，仍缺 269 个 per-stock 明细目录。2026-08-14 二次：板块批回测重跑后磁盘真实状态为 **11 板块 118 行**、per-stock 明细 `full_detail_archive_complete=True`；审计脚本已**动态化**（`derive_on_disk_baseline` 从磁盘推导基准，替代硬编码 274），`audit_a_stock_sector_archive.py` **failures=0**、测试 4 passed）
- [x] **安全边界**：本次只做审计和测试，不重跑 A股回测，不压缩/删除 results，不修改 DS01-DS09、峰极线或阵营逻辑。
- [x] **验证**：`python scripts\audit_a_stock_sector_archive.py` -> `failures=0`；`python -m pytest tests\test_audit_a_stock_sector_archive.py -q` -> **4 passed**。
- [ ] **后续可选**：如需要完整 per-stock 结果包，需要重新生成或找回 `results\fengji_total_a_stock_sectors_*` 明细目录后再做归档；当前仓库现存资产只能证明汇总层结果。（2026-08-14：已重建 12 个板块 `sector_summary.csv`；2026-08-14 二次重跑生成 **118 个 per-stock 明细目录**（11 板块全覆盖，含 raw_fengji/stock_summary 等 8 类文件）；其余 269 个早期 per-stock 明细目录仍需重跑或找回，属后续工作。注：`results/` 整体被 .gitignore 忽略，板块结果与 per-stock 明细不入库）

## 2026-07-10 · 模拟挂单刷新与冲突撤销策略审计

- [x] **刷新口径固化**：新增 `scripts/audit_pending_refresh_policy.py`，确认 `src/fengji_radar_order_loop.py` 每轮先刷新总雷达、再调用 `src/fengji_pending_orders.py` 重写 `runtime/fengji_pending_orders/pending_orders.json`；当前契约不需要额外每日开盘前批量刷新。
- [x] **海内外频率审计**：国内 watchdog radar loop 为 600 秒、pending monitor 为 5 秒且启用 `--enforce-valid-until`；海外 watchdog radar loop 为 900 秒、pending monitor 为 5 秒。
- [x] **有效期与撤销口径**：`default_valid_until` 以雷达刷新时刻 `created_at` 为锚，D1/H1/其他周期分别延后 2 天/6 小时/12 小时；两端 monitor 均过滤 `cancelled_order_ids` 与 `cancelled_setup_keys`。
- [x] **成交后同品种冲突撤销**：复用 `audit_pending_order_contract.py` 既有契约；非 DS01 成交后撤同品种其他挂单，DS01 成交后保留同向 DS01 加仓，撤反向 DS01 和其他定式，并记录 `conflict_after_fill`。
- [x] **验证**：`python scripts\audit_pending_refresh_policy.py` -> `failures=0`；`python -m pytest tests\test_audit_pending_refresh_policy.py tests\test_audit_pending_order_contract.py tests\test_fengji_radar_order_loop_market.py tests\test_summarize_pending_effective_status.py -q` -> **16 passed**；`python -m py_compile scripts\audit_pending_refresh_policy.py` 通过；`verify_phase2_closeout.py` 仍为 `PHASE2_CLOSEOUT_OK`。

## 2026-07-10 · 海外虚拟货币数据源与新鲜度审计

- [x] **数据源口径固化**：海外主数据泵 `data_manager.py` 通过 Binance 同步 16 个主监控币种的 `1d` / `1h` / `15m`；HYPE/ATH 由 `scripts/sync_missing_crypto_15m.py` 走 OKX fallback 补偿 `M15` / `H1` / `D1`。
- [x] **失败补偿与新鲜度**：`scripts/watchdog_overseas.sh` 默认每分钟看护；15m 数据停更阈值为 `WATCHDOG_DATA_STALE_LIMIT=1800` 秒；OKX fallback 默认 `WATCHDOG_OKX_15M_INTERVAL=600` 秒；`scripts/check_okx_csv_freshness.py` 负责 HYPE/ATH 新鲜度检查。
- [x] **只读审计**：新增 `scripts/audit_crypto_data_pipeline.py`，静态检查 Binance 主源、OKX fallback、OKX ingest、新鲜度脚本、watchdog 补偿和海外运行态检查契约，并输出 `data/1d`、`data/1h`、`data/15m` 当前快照。
- [x] **海外实测**：仅同步审计脚本到海外服务器，未重启进程；远端审计 `failures=0`，18 个币种三周期 `available_total=54/54`，`15m` 最大滞后约 802 秒，`1h` 最大滞后约 1702 秒，HYPE/ATH OKX 新鲜度检查全部 `ok`。

## 2026-07-10 · 国内模拟盘启动协同审计

- [x] **国内启动入口补齐**：新增根目录 `run_futures_astock_paper.ps1`，统一通过 `scripts/resolve_domestic_paper.ps1` 和 `scripts/domestic_paper_manifest.txt` 解析中文模拟盘文件名，避免启动工厂直接依赖不可移植文件名匹配。
- [x] **启动工厂参数对齐**：`scripts/start_factory_ascii.bat` 改为调用 `scripts\run_futures_radar_loop.cmd` 与 `scripts\run_futures_pending_monitor.cmd`；`scripts/run_futures_radar_loop.cmd` 补齐 `--market futures`、`--monitor-state`、`--include-triggered`、`--m15-tail 960` 等生产参数，与重启/看护脚本口径一致。
- [x] **国内同步清单补齐**：`scripts/sync_deploy_domestic.ps1` 与 `scripts/fengji_domestic_deploy_manifest.txt` 纳入 data manager 根入口、paper 根入口、start factory 和 radar/pending cmd 包装脚本。
- [x] **只读协同审计**：新增 `scripts/audit_domestic_paper_coordination.py`，静态检查国内模拟盘入口、启动工厂、数据泵、radar loop、pending monitor、watchdog 与同步清单的 runtime 路径和参数契约。
- [x] **远端验证**：仅同步入口/审计文件到国内服务器，未重启进程；远端 `py_compile` 通过，审计 `failures=0`，且 manifest、paper 根文件、orders、pending state、paper state、trade CSV、data dir 均存在。

## 2026-07-10 · 海外 DS 覆盖与通知审计

- [x] **海外 DS01-DS09 覆盖审计**：新增 `scripts/audit_overseas_notification_coverage.py`，只读检查海外 DS01-DS09 入口覆盖、飞书状态词和 runtime 快照；当前海外 `missing=[]`。
- [x] **海外通知格式审计**：审计脚本 smoke 检查共享飞书文案包含 `已挂单`、`已买入`、`已卖出`、`已卖出平仓`、`已买入平仓`，用于防止海外推送退回不明确状态。
- [x] **远端验证**：已仅同步审计脚本到海外服务器；远端 `.venv/bin/python -m py_compile` 通过，远端审计 `failures=0`，当前 radar 策略计数 `DS01=8, DS02=26, DS03=25, DS06=3, DS08=3`，pending 策略计数 `DS01=3, DS03=7, DS08=3`，paper open 策略计数 `DS01=1, DS07=4, DS08=2`。

## 2026-07-10 · 海外飞书状态文案对齐

- [x] **海外飞书状态明确化**：`feishu_trade_notify.py` 的共享通知文案已增加 `状态: 已挂单/已买入/已卖出`，成交后平仓按持仓方向显示 `已卖出平仓` 或 `已买入平仓`，用于对齐国内推送的状态可读性。
- [x] **验证**：`python -m pytest tests\test_feishu_trade_notify.py tests\test_feishu_paper_notify.py -q` -> **8 passed**；`python -m py_compile packages\fengji_core\fengji_core\feishu_trade_notify.py src\fengji_pending_order_monitor.py src\fengji_feishu_paper_notify.py src\overseas_paper_monitor.py` 通过。
- [x] **海外部署复核**：已将 `packages/fengji_core/fengji_core/feishu_trade_notify.py` 同步到海外服务器；远端 `.venv/bin/python -m py_compile` 通过；已定向重启海外 pending/paper monitor，复查新 PID 运行，pending 日志继续刷新。

## 2026-07-10 · effective pending 接入成交后沙盒图复核

- [x] **summary 一键复核入口**：`scripts/summarize_pending_effective_status.py` 新增 `review_candidate_orders` 统计与 `--sandbox-review` 参数；发现 `filled/filled_open` 时可直接调用 `generate_fill_sandbox_review.py` 生成复核清单。
- [x] **安全默认值**：`--sandbox-review` 默认只生成 `fill_sandbox_review.json/md`，不执行画图；只有显式传 `--sandbox-review-execute` 才运行 plotter，避免运行态检查误触发重任务。
- [x] **海内外只读部署**：已同步 `scripts/summarize_pending_effective_status.py` 到国内/海外服务器，未重启进程；海外 dry-run 当前 `review_candidates=1 -> ready=1`，国内 LHUSDT dry-run `review_candidates=1 -> ready=1`。
- [x] **验证**：`python -m pytest tests\test_summarize_pending_effective_status.py tests\test_generate_fill_sandbox_review.py tests\test_runtime_check_scripts.py -q` -> **15 passed**；`python -m py_compile scripts\summarize_pending_effective_status.py scripts\generate_fill_sandbox_review.py` 通过；`verify_phase2_closeout.py` 仍为 `PHASE2_CLOSEOUT_OK`。

## 2026-07-09 · 成交后沙盒图复核编排

- [x] **DS09 历史索引归一化**：`plot_live_ds09_sandbox.py` 已在旧事件索引距离当前全量 M15 入场索引过远时，按 `boundary` / `trigger_price` / `stop_price` 在入场前局部窗口内重定位 lock/attack/defense。
- [x] **DS09 归一化 smoke**：国内 `TAUSDT DS09` 旧事件索引 `953/956` 已重定位到 `3876/3872` 附近，归一化图已复制回 `runtime/fill_sandbox_review/smoke_TAUSDT_DS09_live_normalized.png`。
- [x] **DS05 / DS09 open fill 图**：新增 `scripts/plot_live_ds05_sandbox.py`、`scripts/plot_live_ds09_sandbox.py`；编排器对 `filled_open` 的 DS05/DS09 优先走 live/open 图，`filled` 仍保留 closed trade plotter。
- [x] **DS05 smoke**：国内历史 `LCUSDT DS05` 成交已生成 live 图，`make_ds05_signal` 回放为 `DS05 Bearish Finger`。
- [x] **DS09 smoke**：国内历史 `TAUSDT DS09` 成交已生成 live 图；元数据解析已支持 `lock_idx` / `attack_idx` / `defense_idx` / `boundary`。
- [ ] **DS09 后续细化**：继续观察下一笔实时 DS09 open fill 的 `--execute` 图；如出现跨夜/主力合约切换导致价格重定位歧义，再补更严格的时间锚点审计。
- [x] **DS04 open fill 图修正**：新增 `scripts/plot_live_ds04_sandbox.py`，DS04 `filled_open` 不再依赖已平仓 `trades.trade_no`，改为按 `setup_key` K1-K4 与 `make_ds04_signal` 回放生成 live/open 沙盒图。
- [x] **DS04 SH/RB 闭环**：国内 `SHUSDT DS04`、`RBUSDT DS04` 已生成沙盒图并复制回本地 `runtime/fill_sandbox_review/`；两图均包含完整峰极连线、阵营背景、K1-K4、回收边界、初始止损和开仓点。
- [x] **DS04 根因记录**：原 `no_backtest_trade` 不是 DS04 setup 不合法，而是旧编排用 closed trades 匹配 open fill；已用 `scripts/audit_ds04_fill_sandbox_match.py` 确认两笔均可回放出 `DS04 Long Yang-Yin-Yang Reclaim`。
- [x] **DS04 接入修正**：DS04 曾先接入 closed trade_no 反查，国内 SHUSDT/RBUSDT 因仍是 open fill 而显示 `no_backtest_trade`；现已改为 live/open plotter 并完成出图。
- [x] **DS04 当前样本处置**：国内 SHUSDT/RBUSDT 两笔 DS04 已从 `no_backtest_trade` 变为 `generated`，不再需要等待平仓 trade_no。
- [x] **DS05 / DS09 接入**：复用现有 `src/plot_ds05_sandbox.py` / `src/plot_ds09_sandbox.py`，编排器按方向、入场价、入场时间反查 backtest `trade_no`，匹配不到时显式输出 `no_backtest_trade`，不伪造定式图。
- [x] **海外同步恢复**：SSH 恢复后已同步尾读修正版并用海外 `.venv/bin/python` 完成 dry-run；海外当前 `filled/filled_open` 候选为 0。
- [x] **当前 unsupported 边界**：国内 dry-run 已无 DS04/DS05/DS09 `unsupported`；DS04 当前样本已可出图。
- [x] **复核编排脚本**：新增 `scripts/generate_fill_sandbox_review.py`，基于 effective pending summary 自动筛选 `filled` / `filled_open`，匹配成交事件，输出 `runtime/fill_sandbox_review/fill_sandbox_review.json` 与 `.md`。
- [x] **运行态性能保护**：`events.jsonl` 默认只尾读最近 `20000` 行，避免海外大日志全量扫描卡住运行态检查；需要离线全量回放时再显式传 `--event-tail-lines 0`。
- [x] **plotter 接入边界**：当前 DS01 / DS03 / DS07 / DS08 可生成沙盒图命令并可 `--execute`；DS05 / DS09 暂标 `unsupported`，等待后续统一图形入口，不用临时拼旧逻辑。
- [x] **国内闭环实测**：国内 `LCUSDT DS01 filled_open` 已生成成交后沙盒图并复制回本地 `runtime/fill_sandbox_review/2026-07-08_160000_LCUSDT_DS01_short_LCUSDT-DS01-D1-sho.png`。
- [x] **验证**：新增 `tests/test_generate_fill_sandbox_review.py`，覆盖可画图任务、非成交过滤、unsupported 显式标注和事件尾读；相关测试 **10 passed**。
- [ ] **后续优化**：下一笔 DS05/DS09 实时成交出现后执行 `--execute` 实图闭环验证。

## 2026-07-09 · 有效挂单视图与运行态去误导

- [x] **有效挂单视图**：新增 `scripts/summarize_pending_effective_status.py`，合并挂单表、执行 state、模拟盘 paper state，输出 `raw_status` / `effective_status` / `actionable`，避免已成交或已撤销候选被误看成仍可触发挂单。
- [x] **运行态检查接入**：`check_domestic_runtime_remote.ps1`、`check_overseas_runtime_status.ps1` 增加 effective pending summary；远端未部署脚本时给出明确提示。
- [x] **服务器只读同步**：已同步 `scripts/summarize_pending_effective_status.py` 到国内/海外服务器，未重启进程，未修改峰极线、阵营转换或 DS01-DS09 核心逻辑。
- [x] **LC 现场验证**：国内 `LCUSDT` 摘要显示 `DS01 READY_TRIGGERED -> filled_open`、`DS03 ACTIVE -> cancelled`、`actionable=0`，解释了"雷达仍显示但执行侧已成交/撤销"的误导来源。
- [x] **测试验证**：`tests/test_summarize_pending_effective_status.py` + runtime/check/pending/supervision/security 相关重点集 **59 passed**；`verify_phase2_closeout.py` 仍为 `PHASE2_CLOSEOUT_OK`。
- [x] **后续优化**：将成交后沙盒图自动生成/半自动检查流程接入 effective pending summary，减少人工拉图核对。（2026-07-10：`--sandbox-review` 默认只生成复核清单，`--sandbox-review-execute` 才画图）

更新时间：2026-07-08

## 方案 B · Phase 2 后续 · N 日清单（自 2026-07-06）

| 日序 | 主题 | 主要产出 | 状态 |
|------|------|----------|------|
| D0 | **PR #12 os_engine/radar** | merge `main@4d6a840` · 海内外 radar/pending 已部署 | ✅ |
| D1 | **OS 状态账本复核** | 国内 LC `delta1=0 delta2=0` pl=192 · 海外 BTC `INCREMENTAL_OK` pl=1095 · 本地 incremental BTC/LC **ok**（2026-07-06） | ✅ |
| D2 | **pending monitor 桶** | PR **#13** `4a09090` · 海内外已部署重启 · 海外 PID **3345868** · 国内 PID **1140** · hash match · 测 **13 passed** | ✅ |
| D3 | **W18 watchlist MVP** | PR **#15** `2e5a3e3` · 国内 verify **OK** · PG **4 users** · dry-run **4 items** · 测 **44 passed** | ✅ |
| D4 | **定式案例回归** | PR merge · `verify_d4_pattern_cases.py` · 飞书 **纯碱(SA)** · 国内已 sync | ✅ |
| D5 | **数据与挂单口径** | `require_tq_credentials` · `RADAR_REFRESH_SCHEDULE` · `PENDING_ORDER_CANCEL_RULES` · `verify_d5` | ✅ |
| D6 | **A股/期货覆盖边界** | `market_coverage` · `MARKET_COVERAGE_BOUNDARIES.md` · `verify_d6` | ✅ |
| D7 | **stash/文档卫生** | `STASH_BOUNDARY_AUDIT` · `verify_phase2_closeout` · Phase2 收口 | ✅ |

操作约束：实盘权限未开；勿提交密钥；海内外部署后仍用 `verify_domestic_health` / `compare_overseas_core_hashes`。

## 2026-07-08 · 海外 fill supervision 告警处置

- [x] **重复告警止血**：海外 `BTCUSDT-DS05-D1-short-da008ccaf48b8587` 已登记 `audit_invalid` ack；重跑 `audit_paper_fills.py --fail-on-invalid` exit **0**，latest summary 为 `invalid=1 invalid_acknowledged=1 invalid_new=0`。
- [x] **旧告警 marker 清理**：已删除海外 `runtime/watchdog/fill_supervision_invalid.alert`，避免旧 marker 干扰后续观察。
- [x] **DS05 专项复核**：确认该笔 BTCUSDT DS05 为 D1 K3 盘中触发；最终 2026-07-06 D1 高点后续突破 K2 高点，导致最终 D1 bar 无法重放当时 DS05。
- [x] **审计层修复部署**：`fill_supervision.audit_ds05_fill` 已区分 DS05 盘中触发的最终日线重绘场景，标为 `skipped` 而非 `invalid_new`；海外复验 latest summary 为 `invalid=0 invalid_new=0 skipped=8`。
- [x] **后续观察**：海外 2026-07-08 17:50 watchdog 复查 `fill_supervision ok`；latest summary 为 `invalid=0 invalid_new=0 skipped=8`，且 `runtime/watchdog/fill_supervision_invalid.alert` 不存在。若后续再次出现 `fill_supervision_invalid`，需确认是否为新的 order_id，而不是本次 BTCUSDT DS05。

## 2026-07-08 · 海内外运行态与 hash 复查

- [x] **海外运行态复查**：`check_overseas_runtime_status.ps1` 显示 data_manager、radar loop、pending monitor、paper monitor 均在运行；`radar.json` / `pending_orders.json` 更新至 2026-07-08 17:57，15m CSV 样本更新至 18:06。
- [x] **国内运行态复查**：`check_domestic_runtime_remote.ps1` 显示 data_manager 单进程、radar 单进程、pending 单进程；heartbeat age < 120s，PG/SC 15m 验收 `ACCEPTANCE_OK`。
- [x] **海外核心 hash 复查**：`compare_overseas_core_hashes.py` 为 `mismatches=0`。
- [x] **国内核心 hash 复查**：修正 `compare_domestic_ds08_hashes.py` 的 CRLF/LF 误报后，国内核心执行/监督文件比对为 `mismatches=0`；已同步 `fill_supervision.py` 审计层修复到国内并远端 `py_compile` 通过。

## 2026-07-08 · 安全边界审计

- [x] **仓库密钥边界复查**：新增 `scripts/audit_security_boundaries.py`，扫描仓库代码文件时只输出文件/行号/类别，不打印疑似密钥值；当前结果 `failures=0 warnings=0`。
- [x] **Webhook 脱敏修正**：移除 `scripts/patch_domestic_feishu_defaults.py` 中的完整 webhook 替换字面量，改为通用正则；`watchdog_overseas.sh` 本地与海外启动脚本均未发现完整 webhook URL。
- [x] **只模拟边界复查**：`audit_security_boundaries.py` 未发现 `create_order` / `insert_order` / `place_order` / `TradeAPI` 等真实下单 API 调用；当前运行进程仍为 data/radar/pending/paper 模拟链路。

## 2026-07-08 · 模拟账本契约复查

- [x] **开仓/平仓字段契约**：新增 `scripts/audit_paper_ledger_contract.py`，静态校验海外/国内模拟挂单监控的默认资金参数、开仓字段、平仓字段和交易 CSV 字段；当前 `failures=0`。
- [x] **手续费/滑点/保证金口径**：已在 `峰极OS_挂单器与模拟实盘说明.md` 补齐海外 `notional = margin * leverage`、海外 `costs = notional * (fee_rate + slippage_rate) * 2`、国内 `(entry + exit) * multiplier * lots * (fee + slippage)` 等公式。

## 2026-07-08 · 挂单触发与冲突撤单契约复查

- [x] **挂单触发契约**：新增 `scripts/audit_pending_order_contract.py`，验证海外现价触发、国内 K 线 high/low 触发、默认挂单策略集合和冲突撤单记录；当前 `failures=0`。
- [x] **同品种冲突撤单口径**：当前实现为非 DS01 成交后撤销同品种其他挂单；DS01 成交后保留同品种同向 DS01 加仓挂单，撤销反向 DS01 和其他定式挂单；撤销记录写入 `cancelled_order_ids` / `cancelled_setup_keys` / `events.jsonl`。
- [x] **国内/海外规则差异**：海外用现价或价格快照触发，国内用本地 K 线 high/low 触发；两者共享订单状态、`setup_key` 去重和冲突撤单契约，但市场交易时间由各自数据泵/任务调度控制。

## 2026-07-07 · Codex 接手复验

- [x] **60 秒接手检查**：`git status -sb` · `git log -3 --oneline` · `verify_phase2_closeout.py` → `PHASE2_CLOSEOUT_OK`。
- [x] **项目桶验收**：`powershell -File scripts\verify_project_buckets.ps1` → `All project buckets OK`。
- [x] **核心测试**：OS/DS01/DS03/DS05/挂单/雷达重点集 → **67 passed**。
- [x] **全量测试**：`python -m pytest tests -q` → **479 passed, 17 skipped**。
- [x] **radar loop market 兼容**：补齐 `--market` 参数与 `FENGJI_MARKET` 传递，防止重启命令解析失败。
- [x] **radar loop 部署**：仅同步 `src/fengji_radar_order_loop.py` 到国内/海外；国内 radar loop 重启后 health OK；海外 radar/pending 由 watchdog 自动拉起并刷新至 2026-07-07 19:04。
- [x] **海外 watchdog 锁继承修复**：`watchdog_overseas.sh` 后台拉起长期进程前关闭 lock fd；已同步海外并远端 `bash -n` 通过，后续 watchdog 不再因 pending monitor 持锁长期 skip。
- [x] **海外 BTC DS05 invalid 止血**：2026-07-08 已登记 ack，重复告警停止；根因复核仍见 2026-07-08 待办。

## 2026-07-07 · 节后实时巡检

- [x] **国内运行态**：`verify_domestic_health.ps1` 通过；data_manager/radar/pending 均单进程；PG/SC 15m 验收 `ACCEPTANCE_OK`。
- [x] **海外运行态**：data_manager、radar loop、pending monitor、paper monitor 均在运行；OS state 持续更新。
- [x] **海外 hash 误报修正**：`watchdog_overseas.sh` 仅 CRLF/LF 差异；`compare_overseas_core_hashes.py` 已对 `.sh` 本地 hash 做 LF 规范化，并补测试。
- [x] **巡检脚本输出收口**：海外脚本已正确显示远端 `FENGJI_MARKET=crypto` 与最新 CSV mtime；国内额外进程段不再混入 CLIXML。

## 2026-07-06 · 运行态处置

- [x] **海外 radar_loop 告警（10:53）**：部署 pkill 与 cron 竞态误报 · radar 已在跑 · `watchdog_overseas.sh` 已加固并部署。
- [x] **D2 pending plan/apply**：PR #13 merge · 海内外 pending hash match · 均已重启。
- [x] **Codex 一键接手**：`CODEX_APP_HANDOFF.md` · README/AGENTS 入口更新（2026-07-07）。

## 2026-07-03 · 运行态处置

- [x] **国内 SF DS05 invalid**：登记 ack 继续观察 · audit `new=0 ack=1`。
- [x] **海外 BTC lock timeout**：重启 pending monitor（旧进程 2d+ 100% CPU 占锁）。
- [x] **HYPE #28**：DS05 long 已 **gap_stop** 平仓（07-03 00:00:13 @ 64.654）· 见 `docs/HYPE28_STOP_FOLLOWUP.md`。
- [x] **Phase 2 W17 本地验收**：Docker PG + `w17_remote_acceptance.py --auto-server` · **7/7 + 5/5**（2026-07-03）。
- [x] **国内 API deploy 验证**：`sync_deploy_fengji_api.ps1 -Verify` · health ok · 124 文件同步。
- [x] **pending monitor 仓库对齐**：海外 `state_lock` 版入库 · 测试修复。
- [x] **国内 W17 远程验收**：SSH tunnel · **7/7 required**（2026-07-03）。
- [x] **国内 PG**：`127.0.0.1:5432` · alembic **009 head**。
- [x] **国内 futures pending `state_lock`**：已部署并重启 monitor。
- [x] **FUTURES 5m 数据泵 PR-A**：`data_manager_futures.py` + 国内部署 · 待交易时段首轮回填。
- [x] **FUTURES 5m PR-B 脚本**：sync + `import_futures_local` · 待国内 5m CSV 就绪后跑 sync + B0-2 对账。
- [x] **data_manager 实际主力合约**：`resolve_data_contract` + manifest · 已部署国内。
- [x] **天勤 SDK 修复**：`tqsdk` 优先 · 心跳 · 国内首轮回填进行中。
- [x] **SF 15m watchdog 误报**：date≥2020 口径对齐 · 国内 sanitize + normalize_frame 修复 · 全量 sanity dry-run **0**。
- [x] **FUTURES 5m 全量 sync**：国内 68 CSV → 本机 `data/futures/5m` · ingest 76 · B0-2 **pass**。
- [x] **海外 pending monitor 持锁优化**：plan/apply 分离 · `test_pending_orders.py` **10 passed**。
- [x] **海外 pending monitor 部署**：已 sync · hash match · 单轮 ~8s。
- [x] **国内 futures pending 锁优化**：plan/apply · 已部署 PID 3572 · pytest **11 passed**。
- [x] **PG 15m 抓取修复**：`frame_looks_sane` 短历史 + `frame_looks_acceptable` 降级 · data_manager 已重启。
- [x] **stash@{0} 运维桶**：已 cherry-pick `check_domestic_status.ps1` + `constants.py`。
- [x] **stash os_engine/radar 桶**：`os_engine` · `fengji_total_radar` · `ds07` · **77 passed** · 已部署海内外。
- [x] **stash ds03/paper 桶**：DS03 真峰需双极 · **24 passed** · 已部署。
- [x] **fill_supervision 桶**：本地 HEAD sync 海内外 · hash **match** · pytest **38 passed**。
- [x] **海外 crypto 数据泵 hash 对齐**：`data_manager` · `crypto_ingest` · `sync_missing_crypto_15m` · **mismatches=0**。
- [x] **PG/SC 15m 全链路验收**：probe `--write` + data_manager **15:34 `[OK] PG`**（`降级选用 rows=4630`）。
- [x] **ensure_single_data_manager 修复**：cmd 包装进程检测 · 代码陈旧自动重启 · dedupe 不误杀 cmd+python。
- [x] **海外 hash 批量比对**：`compare_overseas_core_hashes.py` 单次 SSH · **mismatches=0**（7/5）。
- [x] **check_domestic_status 增强**：python/cmd 分计 · 代码陈旧告警 · PG/SC 日志口径。
- [x] **stash Web manifest / Phase 2 数据桶**：`fengji_phase2_data_manifest.txt` · `import-futures-local` · 5m sync · manifest **6+4 passed** · OpenAPI **38 paths**。
- [x] **stash 文档/ARCHIVE 桶**：`fengji_archive_docs_manifest.txt` · `docs/archives/INDEX.md` · verify **1 passed**。
- [x] **stash 运维桶（watchdog/探针）**：`deploy_domestic_ops_stash_bucket.ps1` · `fengji_ops_domestic_manifest.txt` · sync 国内 **7 文件** · scp 路径含空格修复。
- [x] **PR merged**：`feat/domestic-ops-pg-sc-sync` → `main`（ops sync · PG/SC 15m · process guards · 试跑 34/0）。
- [x] **PR merged**：`feat/os-engine-radar-core` → `main`（#12 · `4d6a840`）· 国内 `-RestartRadarLoop` · 海外 os_engine/radar sync + watchdog · **43 passed**。
## 2026-07-02 · 方案 B Phase 1 完成 ✅

## 2026-07-02 · 方案 B Phase 0 完成

## 已完成 / 待复查（2026-05-28 LC DS09 与数据）

- [x] **LC 天勤 15m 加长回填**：`backfill_lc_domestic.ps1` 请求 12000 → 实际选用 **10000** 根（校验通过）；1d **800** 根；`data_manager_futures.fetch_frame` 最长 sane 档逻辑（`ec1be47`）。
- [x] **天勤 CSV 解析**：`load_tq_futures_kline_csv`、`load_m15_frame` 纳秒 `datetime`；避免误用天勤 7 列启发式（`8596374`）。
- [x] **LC DS09 校验脚本**：`verify_ds09_lc_session.py`、`debug_lc_ds09.py`；真数据 `m15≈9900`、`bad_trades=0`、`locks=0`。
- [x] **国内流水线**：`run_lc_ds09_domestic.ps1`（`-BuildFrom1h` 仅联调）；`sync_deploy_domestic.ps1` 同步 DS09/雷达；雷达循环已重启。
- [x] **验收清单**：`docs/LC_DS09_ACCEPTANCE.md`。
- [x] **沙盒总览图**：`results/sandbox/lc_ds09/LC_DS09_session_overview.png`（真·15m 数据）。
- [x] **Git 推送**：`8780b1e`、`ec1be47` 等已上 `origin/main`。
- [x] **LC DS09 0 笔**：用户确认接受（2026-05-28）；`locks=0` 为行情结果，ETH 作引擎对照，勿用 `build_lc_bars_from_1h` 冒充验收。
- [x] 国内服务器已安装 `matplotlib` 3.10.9（`domestic_install_matplotlib.ps1`，2026-05-28）。
- [ ] **待复查**：有 `locks>0` 历史时再补 `LC_DS09_trade_*.png`。
- [x] **天勤凭证仅环境变量**：`data_manager_futures.require_tq_credentials()`，无代码默认明文（2026-07-07）。

## 2026-05-28 增量 TODO

- [x] 确认 `packages/fengji_core` 与 `src/quant` 的权威关系：`packages/fengji_core/fengji_core` 为核心权威源，`src/quant` 为兼容层。
- [x] 将 `src/quant/os_engine.py`、`ds01.py`、`ds03.py`、`ds05.py`、`ds07.py` 收敛为 re-export，降低双实现分叉风险。
- [x] 运行核心测试集，确认 re-export 后 `quant.*` 兼容入口仍正常。
- [x] 用导入 smoke test 验证 CLI、回测、雷达和挂单链路所依赖的 `quant.*` 兼容导入仍能加载核心包。
- [x] **2026-05-28 验收**：`pytest tests/` 59+ passed；`scripts/plan_a_verify.ps1` 全绿（含 ETH DS01–DS09 smoke，`bad_audits=0`）。
- [x] **运行态巡检**：`check_overseas_runtime_status.ps1` + 新增 `check_domestic_runtime_remote.ps1`（雷达/挂单 15:15–15:19 更新，LC 数据 15:13）。
- [x] 修正 `tests/test_radar_setup_keys.py` 中 DS03 `setup_key` 断言（`watch` / `peak_key` 新规口径）。
- [x] 海外 OS 增量：`verify_os_state_overseas.sh` 两轮 radar `--once`，BTC `delta1=2` `delta2=0`，`processed_len=1835` 不变。
- [x] 国内 OS 增量：`verify_os_state_domestic.ps1` LC `delta1=0` `delta2=0`，`processed_len=690` 不变。
- [x] 本地 OS 增量：`verify_os_state_incremental.py` IOUSDT 第二轮 `size_delta=0`。
- [x] IOUSDT DS03 沙盒：`results/sandbox/io_ds03_20260528/IOUSDT_DS03_long_20260526.png`（测试口径参数；实盘 IO 该日无 fake_peak 触发，与合成用例一致见 `test_ds03`）。

## 2026-05-27 总工程 TODO

### 当前最高优先级任务

1. ~~连接恢复后立即重传峰极OS增量连线最终版到海外服务器~~ → **已完成**（PR #12 · 2026-07-06 海内外部署）。
2. ~~D1 OS 账本增量~~ → **已完成**（国内/海外/本地 `verify_os_state_*`）。
3. ~~**D5**：数据与挂单口径文档化~~ → **已完成**（2026-07-07）。
4. ~~**Phase 2 D0–D7**~~ → **已完成**（见 `docs/PLAN_B_PHASE2_COMPLETE.md`）。
5. 固化峰极OS总工程交接文档（Cursor/Codex 以 Markdown 为准）。
6. 实时检查国内/海外数据泵、模拟盘、雷达、挂单（节后巡检）。
7. 继续 A股板块回测、失败股票重试和结果归档。（2026-08-14：4 只 60m 缺口股票已补齐并重跑完整 DS01-DS08；12 个板块汇总重建；master summary `h1_rows=0` 清零）

### 九大定式逐个待完成任务

- [x] DS01《挫式棍》：复核左30线数小于等于 2 的代码、测试、雷达、挂单、模拟盘是否一致；重点复核 RENDERUSDT、IOUSDT、DOGEUSDT 案例（2026-08-13 三币审计通过）。
- [x] DS02《阴阳相吃式》：确认属于收线确认型策略（K2 收盘确认→次日开盘；雷达占位 CONFIRM_ON_CLOSE）；测试 22/22；已有碳酸锂/橡胶校准沙盒图。
- [x] DS03《二四棒式》：复核 active high/low 与合法假峰/假极触发；重点复核 IOUSDT 2026-05-26、ETHUSDT 2026-05-27。
- [x] DS04《夹棍式》：复核 K1/K2/K3 结构和触发条件；重点复核玻璃、纯碱 2026-05-26。
- [x] DS05《指形式》：确认 K2 是可能形成"极"的位置，不要求靠近旧 active extreme，不与峰混淆；重点复核红枣案例。
- [x] DS06《外扩峰式》：核心规则已补齐为转势授权 + D/E/F 外扩峰启动；后续只剩服务器/更多市场运行覆盖验证。
- [x] DS07《共振式》：核心规则已补齐为同向延续 + 反向并轨；已同步 `docs/DS07_CALIBRATION.md` 和 `docs/DS07_DRAFT.md`，后续继续排查服务器旧逻辑残留。（2026-08-13 注：该条目中"反向并轨"口径已被用户裁决推翻，最终口径以权威源代码为准——DS03 二四棒仅同向延续，见下方待验证问题更新）
- [x] DS08《否认确定式》：复核五点结构、否认、确定、触发和撤销规则（2026-08-13：否认=结构校验、确定=T+3、触发=首破攻击点、撤销=3禁令+key消费；测试 14/14 通过）。
- [x] DS09《股票式 / 九重天》：用户已确认股票式/A股专属版本等同九重天；2026-05-27 已修正为 D1 OS战略阵营 + 昨日D1战略边界 + M15二次攻击点火；缺少 M15 数据时只跳过 DS09，不影响 DS01-DS08。
- [x] DS09 国内 LC：夜盘 `assign_cn_futures_session_date`、雷达/挂单接入、天勤 15m 回填与验收清单（2026-05-28）；**成交沙盒图**待有 `locks>0` 历史后再补。

### 阵营转换判断待验证任务

- [x] 海外服务器连接恢复后，确认峰极OS状态账本 `runtime/fengji_os_state` 按品种/周期生成，并验证第二轮雷达只追加新K线，不重连历史峰极线。（2026-07-06 D1：BTC `INCREMENTAL_OK` · 国内 LC delta=0）
- [x] 用沙盒图验证红蓝阵营切换是否严格遵守峰极OS最高宪法。（2026-08-13：4 币种沙盒图目视通过，转势均在破极位置）
- [x] 复核 active high/active low、红极/蓝极、合法假峰/假极的字段来源。（2026-08-13：os_engine.py 源码审计通过，字段来源与最高宪法一致）
- [x] 确认 DOGEUSDT、LTCUSDT、RENDERUSDT、IOUSDT 的近期阵营判断是否和图形一致。（2026-08-13：快照+沙盒图全部 verdict=ok）
- [ ] 补充或更新 `tests/test_os_engine.py` 的争议案例。（本轮复核未发现新增争议案例；如后续发现再补充）
- [x] 用DS09固定样本验证 D1红阵营+昨日阴线多头、D1蓝阵营+昨日阳线空头，确保不再只按昨日阴阳线触发。（2026-08-13：新增 `test_ds09_boundary_rejects_candle_without_camp_match` 反向固定样本，红营+阳线、蓝营+阴线均不产边界，只有红+阴→LONG、蓝+阳→SHORT 合法；10 passed）

### 挂单器待完成任务

- [x] 明确每日/每轮雷达刷新频率：`docs/RADAR_REFRESH_SCHEDULE.md`（2026-07-07）。
- [x] 补齐 DS09 雷达/挂单器候选生成：D1安全阵营、昨日边界、M15锁定、第一进攻峰、防守极、二次攻击（`add_ds09` + 挂单默认含 DS09；2026-05-28）。【待复查】国内 LC 当前雷达 DS09 行数常为 0（无结构）。
- [x] 明确同品种一个定式触发后，其他定式挂单是否撤销及如何记录。（2026-07-08：`audit_pending_order_contract.py` failures=0；DS01 同向加仓保留，其他冲突写入 cancel 事件）
- [x] 确认国内期货/A股挂单器和海外虚拟货币挂单器规则一致，但市场交易时间不同。（2026-07-08：共享订单状态/冲突撤单/setup_key 契约；海外现价触发，国内 K 线 high/low 触发）
- [x] 补充挂单触发后的沙盒图自动生成或半自动检查流程。（2026-07-10：`summarize_pending_effective_status.py --sandbox-review` 默认生成 `fill_sandbox_review.json/md`；显式 `--sandbox-review-execute` 才执行画图；`audit_fill_sandbox_review_flow.py` 验证 DS01/DS03/DS04/DS05/DS07/DS08/DS09 plotter 接入）
- [x] 建立独立 `峰极OS_挂单器与模拟实盘说明.md`，交接挂单器、模拟实盘、日志、安全和待补齐边界。

### 实盘数据待整理任务

- [x] 梳理虚拟货币数据源、更新频率、失败补偿和数据新鲜度检查。（2026-07-10：`audit_crypto_data_pipeline.py` 本地/海外只读审计 `failures=0`，海外 18 个币种三周期文件齐全，HYPE/ATH OKX 新鲜度 `ok`）
- [x] 梳理国内期货天勤 LC 15m 加长与脏数据边界：`FUTURES_15M_LENGTH`、最长 sane 档、`docs/LC_DS09_ACCEPTANCE.md`（2026-05-28）。【待复查】是否需天勤历史区间 API 突破 10000 根上限。
- [x] 梳理国内期货天勤数据源、日盘/夜盘开收盘时间、开盘前自动更新、收盘后停止规则（全品种表）：`docs/MARKET_COVERAGE_BOUNDARIES.md` + `scripts/audit_domestic_futures_data_schedule.py`；2026-07-10 本地/国内远端审计 `failures=0`。
- [x] 梳理 A股数据源；A股无夜盘（见 `docs/MARKET_COVERAGE_BOUNDARIES.md`）。
- [x] 补齐或替换 A股 60 分钟历史数据源。【已完成】已固化 H1&lt;500 降级 DS01–DS06；2026-08-14 确认**新浪 `scale=60, datalen=1023`** 为补齐通道并**批量补齐 100 只** 60m 缓存至 1023 根（`scripts/backfill_a_stock_60m.py` + `scripts/verify_a_stock_60m_coverage.py`），写回 `market_data.sqlite`；240 只中 **236 只 ≥500 根**，仅 4 只次新/停牌股（301696/603459/688808/688820）受上市时间限制仍 306-354 根（数据源上限，待换更长历史源）。**2026-08-14 追加：板块批回测已重跑刷新**——`rebacktest_a_stock_h1_short.py` 重跑 118 行（11 板块）0 失败，master_summary 中 `h1<500` 从 118 降至 5 行（4 只次新股跨板块），其余 113 行 `h1_rows=1023/670` 且 DS07/DS08 已真实运行；`resume_a_stock_sector_from_rank.py` 新增 `--symbols` 精确重跑与缺失 `stock_pool.csv` 时从 summary 构建 pool 的 fallback。
- [x] 建立独立 `峰极OS_数据与回测说明.md`，交接数据类型、文件位置、字段、5m/60m状态、回测规则和九大定式回测状态。

### 国内服务器与国外服务器待验证任务

- [x] 国内全链路重启脚本：`resolve_domestic_paper.ps1` + manifest；`cmd` 内 `PYTHONPATH` 引号修复；`fengji_radar_order_loop` 子进程补 `packages/fengji_core`（2026-05-28）。
- [x] 国内服务器：实时检查数据泵、模拟盘、雷达循环、挂单监控、日志、数据新鲜度。（2026-07-08 复查：data_manager/radar/pending 均单进程，PG/SC 15m `ACCEPTANCE_OK`）
- [x] 海外服务器：实时检查数据泵、模拟盘、雷达循环、挂单监控、日志、数据新鲜度。（2026-07-08 复查：data/radar/pending/paper 运行，15m 数据更新至 18:06）
- [x] 确认服务器代码版本与本地核心文件一致。（2026-07-08：海外 core hash `mismatches=0`；国内执行/监督 core hash `mismatches=0`）
- [x] 确认服务器启动脚本使用脱敏配置，不把密钥写入仓库。（2026-07-08：本地审计 `failures=0 warnings=0`；海外/国内启动脚本未发现完整 webhook URL）
- [x] 建立独立 `峰极OS_服务器与部署说明.md`，交接国内/国外服务器、部署、启动停止、日志排查和安全红线。

### 模拟实盘运行待完成任务

- [x] 海外虚拟货币：确认 DS01-DS08/DS09 的当前覆盖状态和通知格式。（2026-07-10：`audit_overseas_notification_coverage.py` 本地与海外只读审计均为 `failures=0`，未缺 DS，通知状态词通过）
- [x] 国内期货/A股：确认模拟盘入口、启动工厂、数据泵和挂单器协同。（2026-07-10：`audit_domestic_paper_coordination.py` 本地与国内服务器只读审计均为 `failures=0`，并补齐启动工厂/radar 参数/同步清单）
- [x] 明确模拟开仓、平仓、止损、手续费滑点和账本字段。（2026-07-08：`audit_paper_ledger_contract.py` failures=0，说明文档已补字段与公式）
- [x] 确认当前全部链路仍是只模拟、不真实下单。（2026-07-08：仓库扫描未发现真实下单 API 调用；运行态仍为 data/radar/pending/paper 模拟链路）

### 回测待验证任务

- [x] 回归九大定式单定式测试。（2026-07-10：现有 DS 单测/雷达定式重点集 `56 passed, 1 skipped`；DS02/DS04/DS06/DS07 后续仍需补同等强度核心案例单测和沙盒图）
- [x] 回归总定式统一账本。（2026-07-10：新增 `audit_unified_ledger_regression.py`，合成账本审计 `failures=0`；账本/监控/回测接口重点集补 `PYTHONPATH=services;src;packages/fengji_core` 后 `16 passed, 5 skipped`）
- [x] 继续 A股板块回测，复跑失败股票。（2026-08-13：000425 徐工机械 60m 数据补齐并重跑成功，`a_stock_all_sectors_master_summary.csv` error 行清零；DS01-DS08 全策略，trades=134, return=-16.74%）
- [x] 对最近有争议的信号生成沙盒图并归档。（2026-08-13：`audit_disputed_signal_sandbox_archive.py` 盘点 12/12 案例已视觉归档，`archived_visuals=12, failures=0`，见 `results/disputed_signal_sandbox_archive_20260712/INDEX.md`；仅 ETHUSDT DS03 为 SVG 待后续可补 PNG）
- [x] 对 A股 DS07/DS08 标注数据覆盖不足边界（`market_coverage` · H1&lt;500 自动跳过）。

### Cursor 接手待完成任务

- [ ] Cursor 打开项目前先读取交接文件。
- [ ] Cursor 只按项目文档和当前代码判断，不继承不可见旧聊天。
- [ ] Cursor 修改代码前先输出计划，修改后更新 `CHANGELOG.md` 和 `TODO.md`。
- [ ] Cursor 不得写入服务器地址、密码、Token、完整 webhook。
- [x] 更新 `.cursor/rules/project.mdc`，让 Cursor 每次接手峰极OS总工程时自动遵守项目交接规则。

### 风险点

- 权威源重复：`packages/fengji_core`、`src/quant`、远程同步包可能出现旧逻辑分叉。
- 旧 DS07、旧 DS05、旧左30理解可能污染当前策略。
- 服务器运行状态随时间变化，不能用旧日志当当前状态。
- A股小时线数据不足会导致 DS07/DS08 回测结论偏弱。
- 敏感信息不能写入文档、日志或输出。
- 当前只允许模拟，不允许真实下单。

### 下一次启动 Codex / Cursor 的建议提示词

```text
请先读取 C:\Users\guangwan\Documents\New project 下的 PROJECT_CONTEXT.md、AGENTS.md、TODO.md、CHANGELOG.md、README.md、峰极OS_CANONICAL_RULES.md，以及 docs/CANONICAL_RULES.md、docs/FENGJI_TOTAL_PATTERN_SPEC.md、docs/PLAN_A_ROADMAP.md。这个项目是峰极OS总工程，包含 DS01-DS09 九大定式，不是单一定式项目。不要删除文件，不要回滚已有改动，不要写入任何服务器密码、API Key、Token 或完整 webhook。读取后先汇报当前状态、权威源风险、下一步建议，然后等待我指定任务。
```

## 当前最高优先级任务

以文首 **「方案 B · Phase 2 后续 · N 日清单」** 为准（D1–D7）。本段历史条目已收敛：

1. PR #12 / os_engine·radar 已 merge 并部署（D0 ✅）。
2. 待做：D1 OS 账本增量 · D2 pending 小 PR · D3 W18 · D4–D7 见清单。
3. 节后巡检：海内外数据泵 / 模拟盘 / 雷达 / 挂单。

## 待完成任务

- [x] 安装或修复本地测试环境，解决 `pytest` / Python 权限问题。
- [x] 运行 `scripts\plan_a_verify.ps1` 做 A0 安装验收（2026-05-28 全绿）。
- [x] 运行核心测试集（2026-05-28：`59 passed`）。
- [x] 复核海外服务器。（2026-08-13：`results/server_full_recheck_20260813.md`——`data_manager.py`/`fengji_total_radar.py`/`fengji_radar_order_loop.py`/`fengji_pending_order_monitor.py` 哈希与本地一致；`src/overseas_paper_monitor.py` 与本地模拟盘**不一致待确认**（远程 06-29 35706B vs 本地 07-02 34974B，本地更新或未部署，未拉取文件 diff）；`data_sync.log` 17:11、`paper_run.log` 17:15、`pending_order_monitor.log` 17:17 均活跃无报错；5 类进程运行中）**2026-08-13 复核更正**：上述"不一致"系对比错文件（误将本地旧版 `src/峰极总定式01-08策略海外模拟实盘.py`（07-02, 34974B）当对应文件）。实际远程 `src/overseas_paper_monitor.py` = 本地 `src/overseas_paper_monitor.py` = git HEAD（三方 SHA256 `7061e790…`，35706B）**完全一致**；远程无旧中文名文件、进程运行 `overseas_paper_monitor.py`。已修复 `scripts/sync_deploy_overseas.ps1` 部署源（原误用旧版文件，执行会回退远程），并同步更正 PROJECT_CONTEXT/服务器说明/挂单器说明/SKILL 文档入口名）
- [x] 复核国内服务器。（2026-08-13：`results/server_full_recheck_20260813.md`——`data_manager_futures.py`/`峰极总定式01-08国内期货A股模拟实盘.py`/`src\fengji_futures_pending_order_monitor.py`/`src\fengji_radar_order_loop.py`/`src\fengji_total_radar.py` 哈希与本地一致；`商业终端_Dash.py` 存在（9480B）且**已常驻运行**（2026-08-13：WMI 启动英文名副本 `fj_terminal_svc.py`，PID 跨 SSH 会话存活、0.0.0.0:8050 LISTENING、HTTP 200；schtasks/Register-ScheduledTask 在 SSH 下报 0x80071a2d 不可用，中文路径经 WMI 传参损坏故用副本；**服务器重启后需重新拉起**）；启动工厂 `run_*.cmd`×4 + `scripts\start_factory_ascii.bat` 存在；4+1 进程运行中（4 核心 + Dash），日志活跃；启动脚本含 webhook 参数（敏感，未展示））**2026-08-13 复核更正**：原记录"`src\fengji_pending_order_monitor.py` 为 07-06 10:42 旧版（本地 14:32 新版）但零引用非活跃"**不准确**——远程该文件 SHA256 `0fda2ea33232`（51650B, LF）= git HEAD 权威版内容（本地磁盘 `0677613581cf` 52981B 为同一内容 CRLF 版本，内容一致仅行尾差异）；且被 `src\fengji_futures_pending_order_monitor.py` import 11 个工具函数，为**活跃依赖，不可删除**。另：服务器端发现冗余目录（本地 git 无跟踪、无引用、不影响运行）：海外 `packages/fengji_core/fengji_core/fengji_core`（348K）；国内 `packages\fengji_core\fengji_core_temp`（含 DS01-DS07 副本）+ 三层嵌套 + 嵌套 egg-info）**2026-08-13 已用户授权清理**：国内删 3 项（三层嵌套 375KB + 嵌套 egg-info + `fengji_core_temp` 254KB）；海外删 3 项（三层嵌套 348K + 嵌套 egg-info + `~/` 6 个路径粘连空目录 `homeubuntuquant_cryptopackagesfengji_core*`）；保留顶层活跃包/顶层 egg-info/`runtime\temp`/`deploy_backup`。清理后国内 import RC=0、海外 .venv IMPORT_OK，两台服务器核心进程全部存活）
- [x] 继续 A股板块回测，复跑失败股票，归档结果。（2026-08-13：000425 复跑成功并归档，master summary error=0）
- [x] 补齐 A股 60 分钟历史数据，或明确 A股正式筛选临时只用 DS01-DS06 日线口径（H1&lt;500 降级，见 D6 文档）。
- [x] 明确国内期货日盘/夜盘数据泵自动运行时间表；A股无夜盘（`docs/MARKET_COVERAGE_BOUNDARIES.md` §2–3）。
- [x] 把 `codex_assets\skills` 中的技能安装到全局 Codex 技能目录，若后续需要自动触发。（2026-08-13：`fengji-live-ops-check`、`fengji-a-stock-sector-backtest`、`fengji-signal-sandbox-audit` 三技能已复制到 `%USERPROFILE%\.codex\skills\`，SKILL.md frontmatter 校验完整；源目录 `codex_assets\skills` 保留不动）

## 待验证问题

- [x] `左三线` 的最终定义仍待确认。不要自行编造；需要从用户确认或权威白皮书/代码冻结版中确认。（2026-08-13 用户审阅确认并冻结：启动棍向左最近 3 段峰极线段为考察范围，触发价水平线穿过峰极线段数 <= 2 通过、>= 3 失败；线段定义=相邻硬化峰极点连线，必须来自 OS 硬化节点；适用 DS01 首仓，续棍豁免；独立术语与左30无线并存。已写入最高宪法 §5.3、峰极OS_CANONICAL_RULES §5、PROJECT_CONTEXT、阵营转换判断）
- [x] DS07 口径三方不一致：`codex_assets/skills/fengji-signal-sandbox-audit/SKILL.md` 中 DS07 描述与总纲"两类触发（同向延续+反向并轨）"口径一致，但与权威源代码 `fengji_core/ds07.py`（仅 `LONG/SHORT_CONTINUE` 同向延续，且要求 `prev_h1_camp==1` 启动前已同阵营）不一致。（2026-08-13 用户裁决：**以权威源代码为准（仅延续）**。已反向修订总纲/最高宪法/CANONICAL_RULES/阵营转换判断/数据回测说明/挂单器说明/PROJECT_CONTEXT/校准/DRAFT/W15/技能（项目内+全局已安装）为 DS03 二四棒同向延续口径；`audit_ds_consistency_contract.py` forbidden ALIGN_TURN 与权威源一致，无需改动；服务器代码/部署不变）
- [x] 当前 `src/quant` 与 `packages/fengji_core` 是否完全一致，是否存在双实现不同步。（2026-07-10：`scripts/audit_quant_import_shims.py` 确认本地 `src/quant` 仅为 `fengji_core` re-export shim，无第二套策略实现；国内同步脚本仍以 `packages/fengji_core` 为源码）
- [x] 国内服务器当前代码是否已经包含 DS01 左30 <=2、DS03 failed peak/low、DS05 K2 可能极、DS07 新逻辑。（2026-07-10：`scripts/audit_server_core_logic_deploy.py --remote domestic` live 审计 `mismatches=0`，核心文件 hash 与本地一致且关键 token 无缺失）2026-08-13 16:45 重跑确认 `mismatches=0`（`results/server_core_logic_reaudit_20260813.md`），DS07 裁决后三端口径一致。
- [x] 海外服务器当前代码是否已经包含 DS01 左30 <=2、DS03 failed peak/low、DS05 K2 可能极、DS07 新逻辑。（2026-07-10：`scripts/audit_server_core_logic_deploy.py --remote overseas` live 审计 `mismatches=0`，核心文件 hash 与本地一致且关键 token 无缺失）2026-08-13 16:45 重跑确认 `mismatches=0`（`results/server_core_logic_reaudit_20260813.md`），DS07 裁决后三端口径一致。
- [x] **A 股三板块补跑（2026-05-29）**：新能源车 `BK0900`、证券 `BK0473`、互联网金融 `BK0637` → `results/fengji_total_a_stock_sectors_ev_sec_fintech_ds07_fixed`；汇总 `results/a_stock_all_sectors_overview.csv`。
- [x] A股板块结果是否已全部归档到 `results\a_stock_sector_archive_ds07_fixed.zip` 或对应目录。（2026-07-10：`audit_a_stock_sector_archive.py` 确认当前不是完整 per-stock 明细归档；旧 zip 仅 4 个板块摘要，全量汇总 CSV/运行日志仍在，274 个明细目录引用本地不存在；如需完整明细包需重新生成或找回目录）
- [x] 现有模拟挂单触发是否需要每日开盘前统一刷新，触发一笔后是否撤销同品种其他定式挂单。（2026-07-10：`audit_pending_refresh_policy.py` 固化结论：当前不需要额外每日开盘前批量刷新，海内外 radar loop 周期刷新挂单；成交后冲突撤销由 shared monitor state 事件驱动，DS01 同向加仓例外保留）

## 已完成但需要复查的内容

- [x] DS01 左30线数修正：确认代码、测试、雷达、模拟盘一致（2026-08-13 三币审计通过）。
- [x] DS03 假峰/假极触发：确认 IOUSDT 2026-05-26/27 案例及 ETHUSDT DS03 空头案例（2026-08-13 复核无信号，结构正确）。
- [x] DS05 K2 可能形成极：确认红枣、玻璃、纯碱等国内期货案例（2026-08-13 复核完成）。
- [x] DS07 新逻辑：确认旧逻辑已删除，不会污染海外/国内模拟盘。（2026-08-13：权威源 `fengji_core/ds07.py` 已冻结为 DS03 二四棒同向触发新逻辑；旧 `ALIGN_TURN` 峰极线突破并轨仅残留在历史更新包 `domestic_futures_ds07_update/`（非活跃路径），该目录已加 `README_DEPRECATED.md` 标注废弃、禁止安装。`audit_ds_consistency_contract.py` 新增 DS07 旧逻辑 `forbidden_tokens`（权威源+雷达双入口），防止旧逻辑回流；审计 failures=0，52 passed）2026-08-13 16:32 **国内服务器实时复核通过**（`results/domestic_ds07_recheck_20260813.md`）：远程 `src/quant/ds07.py` SHA256 与权威源一致、无 ALIGN_TURN；`fengji_core_temp/ds07.py`（含 ALIGN_TURN）与嵌套 `fengji_core/fengji_core/` 旧副本均零引用不可达。2026-08-13 16:37 **海外服务器实时复核通过**（`results/overseas_ds07_recheck_20260813.md`）：`src/quant/ds07.py` 与权威包双副本 SHA256 与权威源一致、无 ALIGN_TURN，**全仓 ALIGN_TURN 零命中**（无 `fengji_core_temp`）；嵌套 `fengji_core/fengji_core/`（2026-06-01）旧副本 NO_ALIGN 零引用。
- [x] 国内 `data_manager_futures.py` 天勤长连接复用：确认开盘前/收盘后自动运行逻辑；2026-07-10 审计覆盖 active window 内复用连接、非更新窗口关闭连接并写 `idle` 心跳，国内远端健康检查 data_manager 单进程、idle 心跳正常。
- [x] 海外服务器模拟盘：确认 16 个虚拟货币数据和挂单监控日志持续更新。（2026-07-10：海外 data_manager/radar/pending/paper 均运行；`data/15m` 样本更新至 11:27，radar/pending 更新至 11:24，effective pending summary 正常输出）

## 风险点

- 工作区存在大量未提交代码和数据变更，严禁回滚。
- 本地 Python 执行权限可能被 Codex 沙箱拦截。
- 服务器上运行状态会随时间变化，不能使用旧日志当作当前事实。
- A股 60 分钟历史不足会导致 DS07/DS08 历史结论不完整。
- 旧 Word 文档和旧代码可能包含旧 OS、旧 DS07、旧 DS05 理解，不能直接恢复。
- 文档和日志中不能写入完整 webhook、Token、密码、私钥。
- 虚拟货币当前只模拟，不真实下单。
- 只追加不轮转的事件流水（`runtime/fengji_pending_orders/events.jsonl`）会拖垮挂单监控：国内 2026-08-17 起因该文件涨到 11GB、追加打开报 `Errno 22`，整轮回滚、监控静默失效近两个月。两端 watchdog 已纳入轮转（512MB/64MB），需定期确认轮转生效。
- 常驻 monitor 改代码后**必须重启进程**才生效：watchdog 只在进程掉线时拉起，不会主动重启存活进程。

## 下一次启动 Cursor / Codex 时的建议提示词

```text
请先读取 PROJECT_CONTEXT.md、AGENTS.md、TODO.md、CHANGELOG.md、README.md、峰极OS_CANONICAL_RULES.md，以及 docs/CANONICAL_RULES.md 和 docs/FENGJI_TOTAL_PATTERN_SPEC.md。不要删除文件，不要回滚已有改动。所有定式必须在峰极OS最高宪法下执行。读取后先汇报当前状态、未提交改动风险、下一步建议，然后等待我指定任务。
```
