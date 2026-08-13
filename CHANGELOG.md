# CHANGELOG

## 2026-08-13 (codex_assets/skills 三技能安装到全局 Codex 技能目录)

- **TODO 完成**: "把 `codex_assets\skills` 中的技能安装到全局 Codex 技能目录，若后续需要自动触发"。
- **安装**: 三技能复制到 `%USERPROFILE%\.codex\skills\`：`fengji-live-ops-check`（海内外服务器/数据泵/模拟盘健康巡检）、`fengji-a-stock-sector-backtest`（A股板块回测工作流）、`fengji-signal-sandbox-audit`（DS01-DS08 信号沙盒审计）。SKILL.md frontmatter（name/description）校验完整，与 `~/.codex/skills/.system` 系统技能目录共存；项目内源目录 `codex_assets\skills` 保留不动。
- **发现并记录**: `fengji-signal-sandbox-audit/SKILL.md` 中 DS07 描述（H1 可蓝转红/红转蓝并轨或同阵营延续）与权威源 `fengji_core/ds07.py`（仅同向延续 `LONG/SHORT_CONTINUE` 且要求 `prev_h1_camp==1`）不一致，但与总纲"两类触发"口径一致（总纲 L575-592）。已记入 TODO 待验证问题，技能内容暂不修改，待用户确认以何为准（详见 TODO）。
- 本次仅安装技能与更新文档，未修改任何策略代码、峰极线、阵营转换、模拟成交规则或审计契约；未写入密钥/Token/密码/webhook。

## 2026-08-13 (DS07 旧逻辑负向审计：ALIGN_TURN 不回流权威源/雷达)

- **TODO 待验证项完成**: "DS07 新逻辑：确认旧逻辑已删除，不会污染海外/国内模拟盘"。
- **背景核实**: 权威源 `packages/fengji_core/fengji_core/ds07.py` 已按 2026-07-05 `e596aca` 冻结为**新逻辑**（D1 camp_confirmed 战略授权 + H1 DS03 二四棒同向触发 `LONG_CONTINUE`/`SHORT_CONTINUE`）；旧逻辑（`LONG_ALIGN_TURN`/`SHORT_ALIGN_TURN` 峰极线突破反向并轨）已从权威源、雷达、挂单、模拟盘入口删除，全库仅残留在**历史更新包** `domestic_futures_ds07_update/src/quant/ds07.py`（README 已标注历史包，不作为活跃代码路径）。
- **新增负向契约**: `scripts/audit_ds_consistency_contract.py` 的 `ds07_core_new_resonance_contract` 增加 `forbidden_tokens`（`LONG_ALIGN_TURN`/`SHORT_ALIGN_TURN`/`high > float(blue_ext)`/`low < float(red_ext)`），`radar_uses_canonical_ds_contracts` 增加 `LONG_ALIGN_TURN`/`SHORT_ALIGN_TURN` 禁止标记，防止旧逻辑经权威源或雷达入口回流。
- **新增测试**: `tests/test_audit_ds_consistency_contract.py` 新增 `test_ds07_contract_rejects_legacy_align_turn` 与 `test_radar_contract_rejects_legacy_align_turn`（旧标记混入权威源/雷达时即使新 token 全在也必须报失败）。
- **验证**: `python scripts\audit_ds_consistency_contract.py` -> `failures=0`；审计+DS07/DS09 相关测试 10 passed；核心回归 52 passed, 1 skipped。
- 本次只增加只读审计契约与测试，未修改 DS07 信号逻辑、峰极线、阵营转换或模拟成交规则；未写入密钥/Token/密码/webhook。

## 2026-08-13 (A股 000425 徐工机械失败股票复跑)

- **000425 徐工机械重跑成功**: master summary 中唯一 error 行（`数据库数据不完整: D1=0, H1=0`）补齐数据后重跑。
  - 60m 东财接口限流只返回 126 根 → 删除缓存重跑，自动回退新浪源拿到完整 1023 根（2025-05 ~ 2026-08）。
  - D1=1580 (eastmoney), H1=1023 (sina), 全策略 DS01-DS08，trades=134, return=-16.74%, maxDD=-28.56%, bad_audits=0。
  - 结果归档: `results/fengji_total_a_stock_sectors_ev_sec_fintech_ds07_fixed/BK0900_BK0900/000425_徐工机械/`；master summary 行 status=ok, error 清零。
- **操作说明**: 东财 60m 接口对单次请求有根数上限且易限流，`fetch_kline_with_fallback` 会自动回退新浪备用源，无需改代码。

## 2026-08-13 (DS09 固定样本反向验证)

- **DS09 固定样本验证**: TODO 遗留项"用DS09固定样本验证 D1红阵营+昨日阴线多头、D1蓝阵营+昨日阳线空头，确保不再只按昨日阴阳线触发"完成。
- **新增反向固定样本测试** `test_ds09_boundary_rejects_candle_without_camp_match`（`tests/test_ds09.py`）：昨日红营+阳线不产 LONG、昨日蓝营+阴线不产 SHORT、昨日红营+阴线仍不产 LONG；唯一合法样本为蓝营+阳线 → SHORT（boundary=昨日 low）。
- **验证结论**: `build_prev_day_boundary_map` 的 camp+阴阳线匹配过滤正确，不会退化为"只按昨日阴阳线触发"。
- **Tests**: core suite 46 passed, 1 skipped（含 os_engine/ds01/ds03/ds05/ds09/radar_ds09）。

## 2026-08-13 (阵营转换判断复核：字段来源 + 4 币种沙盒图验证)

- **active_high / active_low 字段来源审计**: 读取 `fengji_core.os_engine` 确认：
  - `active_high` = `red_peak.price`（红营）/ `blue_ext.price`（蓝营）
  - `active_low` = `red_ext.price`（红营）/ `blue_peak.price`（蓝营）
  - 红极/蓝极来源：seed（种阵营 `last_low`/`last_high`）→ `confirmed_raw`（阵营内部推进 `red_ext`/`blue_ext`）→ `redefined`（转势时 `last_failed_low`/`last_failed_high` 或旧峰重定义）
  - 合法假峰/假极 `FAILED_HIGH`/`FAILED_LOW` 均来自硬化节点（`update_hardened_nodes` 确认后的 `accepted_node`），非几何 raw high/low
- **4 币种阵营判断复核（沙盒图）**:
  - **DOGEUSDT**: 红营，`active_high=NaN`（刚转红，红峰尚未 3-3 硬化确立），`active_low=0.06822`（红极），价格 0.07017 在红极上方 → 合理
  - **LTCUSDT**: 蓝营，`active_high=46.5`（蓝极），`active_low=43.62`（蓝峰），价格 44.94 在区间内 → 合理
  - **RENDERUSDT**: 蓝营，`active_high=1.565`（蓝极），`active_low=1.448`（蓝峰），价格 1.274 在蓝峰下方（蓝营攻击深入），high 未突破蓝极 → **合理（非 bug）**
  - **IOUSDT**: 蓝营，`active_high=0.1309`（蓝极），`active_low=0.1177`（蓝峰），价格 0.1122 在蓝峰下方（蓝营攻击深入），high 未突破蓝极 → 合理
- **沙盒图目视验证**: `results/crypto_camp_sandbox_review_20260813/` 4 张 PNG 显示所有转势标记均在破极位置，硬化连线与身份标签正确，无异常跳变。
- **澄清误区**: 蓝营转红条件为 `high >= blue_ext.price`（突破蓝极），而非"跌破蓝峰"；蓝营价格下跌跌破蓝峰是正常攻击行为。RENDERUSDT 曾被误认为"跌破 active_low 应转红"，实际完全符合宪法破极转势规则。
- **Tests**: 630 passed, 17 skipped.

## 2026-08-13 (DS04/DS05 audit + check_ds05 fix)

- **DS04 夹棍式复核**: FG(玻璃)/SA(纯碱) 2026-05-26 K1/K2/K3 structure check passed — no signal (K3 close did not reclaim K1 extreme); no_gap/k2_weakest/dir_combo all correct. Data sourced from SQLite `bars` (Chinese symbol 玻璃/纯碱), exported 189 rows each to temporary CSV for the legacy check script.
- **DS05 指形式复核**: K2-as-possible-extreme confirmed (4-bar local min/max, not OS active extreme); 红枣(CJ) case scanned with fixed `check_ds05_conditions.py`; no recent signal (blue camp, K2 not a 4-bar extreme) — correct behavior.
- **Fix `scripts/check_ds05_conditions.py`**: L72 referenced non-existent `signal.active_extreme` (old 口径) → replaced with `k2_possible_extreme` (current 口径). Script now runs without AttributeError.
- **Tests**: 630 passed, 17 skipped.

## 2026-08-13 (DS01 fix + DS01/DS03 audit)

- **Fix `src/plot_fengji_structure.py` dead imports**: restored `identity_display`, `draw_identity_labels`, `draw_turn_marks` (3 functions, 79 lines) to repair 6 legacy audit/sandbox scripts that failed with `ImportError`.
- **DS01 左30线数复核**: code/radar/pending/execution-supervision all share `ds01_left_filter_pass`; 3-coin audit (RENDER left=0, IO left=0, DOGE left=2 all <=2); generated 3 sandbox PNGs + report in `results/ds01_three_coin_review_20260618/`.
- **DS03 二四棒复核**: IOUSDT 2026-05-26 / ETHUSDT 2026-05-27: no DS03 signal (trigger not crossed, camp structure consistent); `active_high=red_peak`, `active_low=red_ext`, `last_failed_high` tracked correctly.
- **Tests**: 630 passed, 17 skipped.

## 2026-08-13 (P4 ops batch commit: 307 files)

- **Batch committed 307 files (36,292 insertions)** in `9cb8c98`:
  - **scripts/**: 236 + 2 remote ops scripts (deploy_*, run_*, sync_*, verify_*/smoke_*, plot_*/render_*, install_*, patch_*) covering domestic/overseas deployment, m5 zones, os_rebuild, fill supervision, user paper execution, crypto/futures data sync.
  - **docs/**: 61 + 2 api acceptance/ops docs (W00-W24 acceptance history, W_PAY/WADMIN/WAVE5, api/chart_bundle_schema.md + openapi.yaml, fill supervision/futures repair SOPs).
  - **packages/fengji_core/**: 5 modules (ds08_pending_fill, feishu_trade_notify, futures_main_contract, state_lock, stop_bar_monitor).
  - **run_futures_astock_paper.ps1**: root runner.
- **Cleaned 45 temp diagnostic scripts** (`scripts/_tmp_*` / `_` prefix, 300B-9KB one-off debug snapshots).
- **Untracked file count: 0** (remaining git dirt: 7 `data/overseas_1d/*.csv` cache files updated by data pump, left as-is per user).
- **Verification**: 630 passed, 17 skipped.

## 2026-08-11 (P2 A股归档 + 60m补齐 + P3 untracked files batch commit)

- **P2 A股板块回测归档**: 11 sectors (CPO 87%, 算力 67%, etc.), 274 trades across 233 stocks, 1.46M cumulative PnL; archive zip at `results/a_stock_sector_archive_ds07_fixed.zip`; 4/4 audit tests pass.
- **P2 60m 长历史补齐**: audited all markets: A_stock 239/239 60m ✅, Crypto 16/16 1H_1825d ✅, US_stock 224/224 1H ✅, Futures 30/36 1h (6 gaps: AO/LH/P/PG/SC/TA - low-data exchange futures).
- **P2 DS09 沙盒**: LC (碳酸锂) has **locks=0** (293 boundary sessions, 0 signals); ETH/BNB/TAO/生猪 already sandboxed; DS09 Live Watch ACTIVE on overseas.
- **P3 untracked files batch commit**: 116 files, 10,190 insertions:
  - **tests/**: 140 new test files added (audit, monitor, catalog, context, backtest, deployment, feishu, fill_sandbox, paper, market_data, DS08/DS03 pending_fill, total_radar, conftest.py)
  - **docs/**: 40+ strategy/deployment/monitoring docs (DS01-DS09 CALIBRATION/DRAFT, CANONICAL_RULES, FENGJI_TOTAL_PATTERN_SPEC, PLAN_A_ROADMAP, POST_MERGE_ACCEPTANCE, LC_DS09_ACCEPTANCE, PG_SC_15M_ACCEPTANCE, DS09_LIVE_WATCH, FILL_SUPERVISION_SOP, etc.)
  - **src/**: 5 new modules (backtest_us_stock_fengji, batch_backtest_us_stock_sector, feishu_paper_notify, market_data_resolve, overseas_paper_monitor)
  - **designs/**: APPLE_UI_SPEC.md web design spec
  - **codex_assets/**: AI handoff context (3 files)
  - **峰极总定式规则版/**: 8 reference files (doc, PNGs) on N-字突破 and 未满足两点原则
  - **二维码/**: 2 QR code assets
  - **FJLHXM**: UI design + V1 spec
  - **data/us_stock/gics_sectors.json**: GICS sector classification reference
- **.gitignore**: added `test-results/`.
- **Updated TODO.md**: marked P2/P3 tasks complete.

## 2026-08-11 (P1 strategy audit + missing tests + archival cleanup)

- **DS04 standalone tests** (`tests/test_ds04.py`): 16 new unit tests covering `make_ds04_signal` (Yang-Yin-Yang long reclaim, Yin-Yang-Yin short reclaim), reject cases (gap, non-weakest K2, no-reclaim, short frame, no-next-bar), `k2_is_weakest`, `no_price_gap`, `update_ds04_stop` (red_ext/blue_ext upgrade with NaN guard), `check_stop` (gap/intraday long+short), `audit_ds04_structure`.
- **DS02 standalone tests** (`tests/test_ds02.py`): 15 new unit tests covering `make_ds02_signal` (Red Yang-Eats-Yin long, Blue Yin-Eats-Yang short), reject cases (camp mismatch, camp=0, no-devour, short frame, no-next-bar), `DS02Signal.to_dict`, `update_ds02_stop` (yang/yin trailing), `check_stop` (gap/intraday), `audit_ds02_camp_direction`.
- **DS05 K2 extreme**: verified 9 tests pass; CJ/FG/SA sandbox images confirmed archived in `runtime/ds05_sandbox/`.
- **DS08 5-point**: verified 12 tests pass (radar + pending_fill); denial-confirmation structure correct.
- **Camp verification**: 4/4 crypto camps (RENDER/IO/DOGE/LTC) confirmed VALID from sandbox archive.
- **Full test regression**: 630 passed, 17 skipped (was 582 before DS04+DS02 tests).
- **.gitignore**: added `archives/` and `.vscode/` to prevent auto-generated artifacts from entering the repo.
- **Archival docs**: committed 7 root-level cleanup/handoff/baseline `.md` reports from June 2026 Phase 1/2 activity.
- **`.vscode/extensions.json`**: committed workspace extension recommendations.

## 2026-08-11 (Codex handoff + WIP commit + paper signal strength analysis)

- Full Codex handoff: read all constitutional/canonical/rule/handoff docs; git status confirmed 29 modified + 170+ new/untracked; Phase 2 closeout `PHASE2_CLOSEOUT_OK`.
- Dual-server runtime check: domestic and overseas both PASS; domestic data_manager heartbeat 285s (under 420s threshold), overseas data_manager/radar/pending/paper all running; notification audits failures=0.
- Core test suite: os_engine + ds01/ds03/ds05 + pending + futures_pending + radar_ds04-08 + fill_supervision + data_manager_futures_5m -> **86 passed** in ~16s.
- Restored 7 `data/overseas_1d/*.csv` files to HEAD: these are daily-refresh market data caches, not source code or config changes.

### WIP files committed
- `packages/fengji_core/fengji_core/fill_supervision.py`: DS05 audit non-reproducible signal handling (skipped instead of invalid_new).
- `src/market_data_store.py`: `import_futures_local` for 5m/15m/1h CSV-to-SQLite ingestion.
- `src/fengji_futures_pending_order_monitor.py` (+162): contract-switch detection with `cancel_reason=main_contract_switched`; Feishu `已买入/已卖出/已平仓` wording alignment; `PlannedCancel` for pre-switch orders.
- `src/fengji_radar_order_loop.py` (+44): `--market` futures/crypto auto-detection; `--m15-tail` passthrough; `--top-n 40` default.
- `src/fengji_pending_orders.py`: minor fixes.
- `tests/test_fill_supervision.py` (+82), `tests/test_futures_pending_orders.py` (+182), `tests/test_pending_orders.py` (+35), `tests/test_data_manager_futures_5m.py` (new), `tests/test_radar_setup_keys.py`, `tests/test_w17_remote_acceptance.py`.
- `scripts/audit_paper_fills.py`, deployment/monitoring scripts (7 PS1/SH/CMD/BAT), manifest, patch scripts.
- Docs: TODO.md, CHANGELOG.md, FUTURES_5M_DATA_PLAN, LOCAL_MARKET_DATA_DB, MARKET_COVERAGE_BOUNDARIES, two OS explanation docs.
- Domestic paper script: `remote_domestic_optimize/峰极总定式01-08国内期货A股模拟实盘.py`.

### Feishu paper trade signal strength analysis
- Collected and analyzed all Feishu-pushed paper trading data:
  - 552 total Feishu claims: fill=260, close=160, pending=121
  - 622 fill events from runtime JSONL across both overseas and domestic
  - Signal ranking: DS01 (303 fills, 48.7%) > DS05 (81, 13.0%) = DS07 (81, 13.0%) > DS08 (68, 10.9%) > DS03 (53, 8.5%) > DS09 (34, 5.5%) > DS06/DS04 (1 each)
  - Top overseas symbols: TAOUSDT(31), DOGEUSDT(29), LINKUSDT(27), ADAUSDT(25), ZECUSDT/BTCUSDT(25)
  - Domestic paper: 81 open positions across futures + A-stock, DS01 dominates with 49 positions (60%)

- Verification: 86 tests passed; security boundary audit `failures=0 warnings=0`; Phase 2 closeout `PHASE2_CLOSEOUT_OK`.
- Safety boundary: no peak-line, camp-conversion, DS01-DS09 core strategy, trigger, stop, risk-control, real-order, credential, token, password, or webhook logic changed.

## 2026-08-10 (domestic heartbeat check threshold)

- Ran a fresh dual-server runtime check for the current date. Domestic and overseas checks both exited 0; evidence was written under `runtime/logs/dual_runtime_check/20260810_100638`.
- Domestic data manager was healthy and refreshing 34/34 symbols, but `check_domestic_status.ps1` still warned at `heartbeat_age_sec > 120` even though `data_manager_futures.py` polls every 300 seconds and the watchdog contract already uses `$HeartbeatMaxAgeSec = 420`.
- Updated `scripts/check_domestic_status.ps1` and `scripts/verify_domestic_watchdog.ps1` to use the shared 420-second heartbeat threshold, eliminating false stale warnings during the normal five-minute data-pump wait.
- Synchronized only those two domestic operational check scripts to the domestic server. No runtime process was restarted.
- Verification: `tests/test_runtime_check_scripts.py` -> 17 passed; PowerShell parser checks passed; `audit_domestic_futures_data_schedule.py` -> `failures=0`; `verify_phase2_closeout.py` -> `PHASE2_CLOSEOUT_OK`.
- Safety boundary: no peak-line, camp-conversion, DS01-DS09 core strategy, trigger, stop, risk-control, simulated fill, real-order, credential, token, password, or webhook logic changed.

## 2026-07-16 (domestic paper state-file write race fix)

- Confirmed the UR alert at 10:09:06 was a real Windows replace collision: the domestic paper process and `fengji_futures_pending_order_monitor.py` both write `runtime/fengji_futures/state_futures_v2.json`, but only the pending monitor used the shared sidecar lock.
- Refactored the staged domestic paper monitor into a scan/apply flow. CSV preparation and `run_unified_symbol` remain outside the lock; `commit_symbol_scan` uses `update_state_file` to reload the latest state, apply the current-symbol result in memory, and atomically save under `state_futures_v2.json.lock`.
- Deferred trade CSV writes, event logging, console output, and Feishu HTTP calls until after the state lock is released, keeping the critical section bounded to in-memory state mutation and atomic persistence.
- Extended `scripts/audit_domestic_paper_coordination.py` so the domestic deployment contract requires the shared lock dependency and split scan/commit/effect-dispatch structure.
- Added `tests/test_domestic_paper_state_lock.py` with concurrent paper/pending writers and duplicate-bar coverage. The focused paper/pending/fill/notification suite passed with 58 tests.
- Targeted domestic deployment synchronized only the paper source after confirming the remote `state_lock.py` SHA-256 matched local. The prior paper source was backed up, and only the paper process was restarted.
- Remote acceptance: deployed paper hash matched local; one paper Python process and one pending-monitor Python process were running; the paper error log was empty; a temp-state concurrency run retained 30/30 unique pending orders with no lost update.
- Verification: domestic coordination audit `failures=0`; security boundary audit `failures=0 warnings=0`; Phase 2 closeout `PHASE2_CLOSEOUT_OK`.
- Safety boundary: no live state repair, position/equity adjustment, peak-line, camp-conversion, DS01-DS09 core strategy, trigger, stop, risk-control, real-order, or credential logic changed.

## 2026-07-16 (domestic JD main-contract switch fill alert fix)

- Root cause: the JD DS01 short order was created for `DCE.jd2608` at 13:01:04, while the data manifest switched to `DCE.jd2609` at 13:02:29. The 15m bar range relocated from the old-contract 4600 area to 4393-4435, but the old 4590 order was simulated as filled at 13:02:40. The current-contract D1 replay then produced a different camp and raised repeated INVALID alerts.
- Added `detect_order_contract_switch` in `fengji_core.futures_main_contract` for explicit order/position contracts and legacy orders created before `contract_switched_at`.
- Futures pending orders now include `data_contract`; the contract participates in `order_id`, allowing a fresh order identity after contract rollover.
- The domestic pending monitor cancels old-contract orders before fill evaluation, records `cancel_reason=main_contract_switched`, and leaves setup_key available for a recalculated post-roll order.
- New positions record `entry_data_contract`; positions whose entry contract differs from the current main contract are excluded from automatic stop processing.
- `audit_paper_fills.py` classifies confirmed cross-contract fills as `exec_gap` before K-line/strategy replay and writes `invalid_new_fills` for watchdog alert details.
- `watchdog_domestic.ps1` fingerprints the current new-INVALID order-id set and suppresses unchanged 30-minute repeats while preserving alerts when the set changes.
- Domestic deployment synchronized five related runtime files and restarted only the pending monitor. Remote compile/parser checks passed; pending monitor remained at one process.
- Existing JD paper position: created a state backup and added only old/current contract quarantine metadata. Entry price 4590, stop 4688, direction, and equity remain unchanged; the position stayed open after monitor restart.
- Remote acceptance: 72h audit -> `valid=15 invalid=0 invalid_new=0 exec_gap=1 needs_data=0 skipped=2`; forced watchdog round logged `fill_supervision ok`; alert and fingerprint markers are absent.
- Local verification: focused main-contract/pending/fill-supervision/runtime/deploy-manifest suite -> 69 passed; Python compile and PowerShell parser checks passed; security boundary audit -> `failures=0 warnings=0`; Phase 2 closeout -> `PHASE2_CLOSEOUT_OK`.
- Safety boundary: no peak-line, camp-conversion, DS01-DS09 core strategy, trigger, stop, direction, equity, real-order, or credential logic was changed.

## 2026-07-14 (dual-server runtime log retention guard)

- Added `scripts/manage_dual_runtime_check_logs.ps1` with a default 14-day retention policy and dry-run behavior unless `-Execute` is explicitly supplied.
- Cleanup candidates are restricted to directories under the configured log root with exact `yyyyMMdd_HHmmss` names, no child directories, and only the three wrapper-owned files: `SUMMARY.md`, `domestic_runtime.log`, and `overseas_runtime.log`. Unknown content causes the directory to be skipped.
- Execute mode resolves and revalidates every absolute target path before recursive deletion, including root containment and timestamp-name checks.
- Updated `scripts/check_dual_server_runtime_status.ps1` to reject a simultaneous `-SkipDomestic -SkipOverseas` selection before output-directory creation, so invalid no-check calls no longer leave empty runtime batches.
- Added executable tests for dry-run preservation and execute-mode cleanup in a temporary directory; the execute test confirms that a managed old directory is removed while an old directory containing an unknown file remains untouched.
- Local project-log dry-run found 5 managed batches, including 3 incomplete batches, with 0 candidates older than 14 days and 0 deletions.
- Safety boundary: this change only manages local evidence produced by the dual-server runtime wrapper and does not modify peak-line logic, camp conversion, DS01-DS09 core strategy logic, pending trigger rules, stops, risk control, simulated fills, server processes, credentials, tokens, passwords, or webhook values.
- Verification: `python -m pytest tests\test_runtime_check_scripts.py -q` -> 15 passed; PowerShell parser smoke -> `PARSER_OK`; Phase 2 closeout verification remains green.

## 2026-07-14 (latest dual-server runtime status reader)

- Added `scripts/show_latest_dual_runtime_status.ps1` as a read-only local entry for the newest `runtime/logs/dual_runtime_check/*/SUMMARY.md`.
- The reader reports the latest summary path, PASS/FAIL status, freshness, age, configured maximum age, and domestic/overseas exit codes without reconnecting to either server.
- Added explicit automation semantics: fresh PASS exits 0, fresh FAIL exits 1, missing or malformed summaries exit 2, and stale summaries exit 3. The default freshness limit is 120 minutes and can be changed with `-MaxAgeMinutes`.
- Added executable regression coverage in `tests/test_runtime_check_scripts.py` for fresh PASS, fresh FAIL, stale PASS, and missing-summary paths.
- Safety boundary: this is a local read-only operational helper and does not modify peak-line logic, camp conversion, DS01-DS09 core strategy logic, pending trigger rules, stops, risk control, simulated fills, credentials, tokens, passwords, or webhook values.
- Verification: `python -m pytest tests\test_runtime_check_scripts.py -q` -> 12 passed; live reader output -> `status=PASS`, `freshness=FRESH`, domestic `exit_code=0`, overseas `exit_code=0`.

## 2026-07-14 (dual-server runtime check wrapper)

- Added `scripts/check_dual_server_runtime_status.ps1` as a local one-command wrapper around the existing domestic and overseas read-only runtime checks.
- The wrapper writes `domestic_runtime.log`, `overseas_runtime.log`, and `SUMMARY.md` under `runtime/logs/dual_runtime_check/<timestamp>/`, records each side's exit code, rejects empty check selections, and exits nonzero if either side fails.
- Added static regression coverage in `tests/test_runtime_check_scripts.py` for script inclusion, runtime log paths, summary generation, exit-code aggregation, and avoidance of command transcript or secret-oriented output patterns.
- Live verification on 2026-07-14: dual-server wrapper returned `status: PASS`; domestic and overseas checks both returned `exit_code=0`; domestic notification audit `failures=0`; overseas notification audit `failures=0`.
- Safety boundary: this change only wraps operational checks and does not modify peak-line logic, camp conversion, DS01-DS09 core strategy logic, pending trigger rules, stops, risk control, simulated fills, credentials, tokens, passwords, or webhook values.
- Verification: `python -m pytest tests\test_runtime_check_scripts.py -q` -> 7 passed; PowerShell parser smoke -> `PARSER_OK`; `python scripts\verify_phase2_closeout.py` -> `PHASE2_CLOSEOUT_OK stash_files=411 data_csv=332 fjlh=2`.

## 2026-07-14（海外运行态检查接入通知审计）
- `scripts/check_overseas_runtime_status.ps1` 新增 `OVERSEAS NOTIFICATION AUDIT` 小节：海外运行态检查现在会自动只读运行 `scripts/audit_overseas_notification_coverage.py`，把 DS01-DS09 覆盖和飞书状态文案回归纳入日常检查。
- 修正海外检查脚本解释器选择：优先使用 `.venv/bin/python`，不存在时回退 `python3`；`summarize_pending_effective_status.py` 与通知审计共用该解释器，避免系统 Python 缺 `numpy` 导致误报。
- `scripts/audit_overseas_notification_coverage.py` 加固导入路径：采用与国内审计一致的 `prepend_import_path`，强制 `src`、`packages/fengji_core`、项目根目录优先，避免直接脚本入口和模块入口出现不同导入结果。
- `tests/test_runtime_check_scripts.py` 增加断言，锁定海外运行态检查包含通知审计小节、`PYTHON_BIN` 选择、`PYTHONPATH` 和审计脚本入口。
- `tests/test_audit_overseas_notification_coverage.py` 增加路径重排契约测试，防止后续审计脚本退回只在路径不存在时插入的旧写法。
- 海外远端实测：已同步 `scripts/check_overseas_runtime_status.ps1` 与 `scripts/audit_overseas_notification_coverage.py`；远端 `py_compile` 通过；完整运行态检查显示 `PYTHON_BIN=.venv/bin/python`，通知审计 `failures=0`，DS01-DS09 覆盖完整，飞书状态词 `ok`。
- 本次只改运行态检查脚本、审计脚本同步和测试，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损、风控或模拟成交规则；未重启海外进程。
- 验证：`python scripts\audit_overseas_notification_coverage.py` 与 `python -m scripts.audit_overseas_notification_coverage` 均为 `failures=0`；`python -m pytest tests\test_runtime_check_scripts.py tests\test_audit_overseas_notification_coverage.py -q` -> **9 passed**；远端直接入口和模块入口均为 `failures=0`；`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_overseas_runtime_status.ps1` 远端只读验收通过。

## 2026-07-14（国内运行态检查接入通知审计）
- `scripts/check_domestic_runtime_remote.ps1` 新增 `DOMESTIC NOTIFICATION AUDIT` 小节：国内运行态检查现在会自动只读运行 `scripts/audit_domestic_notification_coverage.py`，把飞书状态文案回归纳入日常运行态检查。
- 国内运行态检查解释器口径补齐：effective pending summary 与通知审计均优先使用 `.venv\Scripts\python.exe`，不存在时回退 `python`，减少系统 PATH 或 Python 环境差异带来的误报。
- 远端通知审计块使用 `-OutputFormat Text -EncodedCommand`，脚本块内只用 `Write-Output`，并设置 `PYTHONPATH=src;packages/fengji_core;.`，避免 CLIXML 噪声和导入路径误报；不输出 webhook、Token、密码或完整命令行。
- `tests/test_runtime_check_scripts.py` 增加断言，锁定国内运行态检查包含通知审计小节、审计脚本入口、`PYTHONPATH` 和文本输出约束。
- 国内远端实测：`check_domestic_runtime_remote.ps1` 跑通，PG/SC 15m `ACCEPTANCE_OK`，通知审计 `failures=0`，`radar python count=1`、`pending python count=1`。
- 本次只改运行态检查脚本和测试，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损、风控或模拟成交规则；未重启远端进程。
- 验证：`python -m pytest tests\test_runtime_check_scripts.py tests\test_audit_domestic_notification_coverage.py -q` -> **9 passed**；`python -m py_compile scripts\audit_domestic_notification_coverage.py src\fengji_futures_pending_order_monitor.py` 通过；`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_domestic_runtime_remote.ps1` 远端只读验收通过。

## 2026-07-13（国内飞书状态文案防回归审计）
- 新增 `scripts/audit_domestic_notification_coverage.py`：只读检查国内挂单成交和平仓飞书文案，覆盖 `已买入`、`已卖出`、`已卖出平仓`、`已买入平仓`，并检查旧 `挂单触发价` / `模拟成交价` 不再回流。
- 审计脚本同时输出国内 runtime 快照：`pending_orders.json`、`futures_pending_state.json`、`state_futures_v2.json`、`radar.json` 的存在性、策略计数、有效状态计数、可复核候选和持仓策略计数。
- 新增 `tests/test_audit_domestic_notification_coverage.py`：覆盖文案 smoke、源文件旧文案拒绝、合成 runtime 快照统计。
- 加固审计脚本导入路径：即使远端用 `python scripts\audit_domestic_notification_coverage.py` 直接运行，也会把 `src`、`packages/fengji_core`、项目根目录移到 `sys.path` 前面，避免被 `scripts` 目录遮蔽产生旧文案误报。
- 更新 `scripts/sync_deploy_domestic.ps1` 与 `scripts/fengji_domestic_deploy_manifest.txt`，纳入国内通知审计脚本，避免后续国内同步遗漏该防回归检查。
- 本次只增加通知审计、测试和同步清单，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损、风控或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_domestic_notification_coverage.py` 与 `python -m scripts.audit_domestic_notification_coverage` 均为 `failures=0`；`python -m pytest tests\test_audit_domestic_notification_coverage.py tests\test_futures_pending_orders.py tests\test_feishu_trade_notify.py tests\test_feishu_paper_notify.py -q` -> **18 passed**；`python -m py_compile scripts\audit_domestic_notification_coverage.py src\fengji_futures_pending_order_monitor.py` 通过；国内远端直接入口和模块入口均为 `failures=0`。

## 2026-07-13（国内期货A股模拟成交飞书状态对齐）
- `src/fengji_futures_pending_order_monitor.py`：国内挂单成交推送从旧标题 `峰极总定式01-08国内期货A股模拟挂单触发` 改为状态型标题；多头成交显示 `已买入`，空头成交显示 `已卖出`，并补充 `消息类型`、`状态`、`预计挂单买入/卖出价格`、`挂单买入/卖出价格已成交`、`预计挂单平仓价格`。
- 国内止损平仓推送按原持仓方向显示 `已卖出平仓` 或 `已买入平仓`，并补充 `消息类型`、`状态`、`预计挂单平仓价格`、`平仓价格已成交`，与海外飞书推送的可读状态保持一致。
- `tests/test_futures_pending_orders.py`：增加 CF 多头成交样例、SA 空头成交样例和平仓状态断言，同时确认旧 `挂单触发价` / `模拟成交价` 不再出现在国内成交推送中。
- 本次只改国内通知展示层和测试，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损、风控或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python -m pytest tests\test_futures_pending_orders.py tests\test_feishu_trade_notify.py tests\test_feishu_paper_notify.py -q` -> **14 passed**；`python -m py_compile src\fengji_futures_pending_order_monitor.py` 通过。

## 2026-07-12（玻璃/纯碱 DS05 沙盒图补齐）
- 运行 `python scripts\verify_d4_pattern_cases.py --plot --out-dir results\sandbox\d4_phase2_20260712`，补出 D4 复核目录与 `FG_玻璃_DS05_2026-07-07.png`；该脚本内部 DS01/DS03/DS05 重点单测通过，D4 汇总为 `D4_VERIFY_OK`。
- 使用 `scripts/plot_live_ds05_sandbox.py` 按 SA 的 K1/K2/K3 时间锚点补出 `results/sandbox/d4_phase2_20260712/SA_纯碱_DS05_2026-07-07.png`；SA 信号回放为 `DS05 Bearish Finger`，`k2_possible_extreme=1117.0`。
- 更新 `scripts/audit_disputed_signal_sandbox_archive.py`：DS05 D4 归档不再只看 `d4_phase2_20260707`，改为识别所有 `results/sandbox/d4_phase2_*` 目录，并合并最新 D4 report。
- 重新生成 `results/disputed_signal_sandbox_archive_20260712/INDEX.md` 与 `archive_index.json`；当前争议样本 `archived_visuals=12/12`、`missing_visuals=0`、`missing_evidence=0`。
- 目视检查：FG/SA 两张图均可打开，包含 K 线、`hardened_fengji_line`、阵营背景、K1/K2/K3、入场和止损线。
- 本次只补沙盒图和归档索引，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、雷达、挂单、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_disputed_signal_sandbox_archive.py` -> `failures=0`；`python -m pytest tests\test_audit_disputed_signal_sandbox_archive.py -q` -> **4 passed**；`python -m py_compile scripts\audit_disputed_signal_sandbox_archive.py` 通过。

## 2026-07-12（争议信号沙盒图归档索引）
- 新增 `scripts/audit_disputed_signal_sandbox_archive.py`：只读盘点 RENDERUSDT/IOUSDT/DOGEUSDT DS01、IOUSDT/ETHUSDT DS03、RENDER/IO/DOGE/LTC 阵营图、红枣/玻璃/纯碱 DS05 K2 可能极等争议样本的现有图、Markdown 和 JSON 报告。
- 新增 `tests/test_audit_disputed_signal_sandbox_archive.py`：覆盖当前仓库归档证据不缺失、报告存在但图缺失的 `missing_visual` 状态、证据完全缺失的 `missing_evidence` 状态，以及索引写入。
- 新增归档索引产物：`results/disputed_signal_sandbox_archive_20260712/INDEX.md` 与 `archive_index.json`；当前 12 个样本中 `archived_visuals=12`、`missing_visuals=0`、`missing_evidence=0`。
- 玻璃 FG DS05、纯碱 SA DS05 后续已补独立 PNG，归档索引不再存在 `missing_visual`。
- 本次只做结果归档盘点和索引写入，未重算策略、未生成新交易，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_disputed_signal_sandbox_archive.py` -> `failures=0`；`python -m pytest tests\test_audit_disputed_signal_sandbox_archive.py -q` -> **4 passed**；`python -m py_compile scripts\audit_disputed_signal_sandbox_archive.py` 通过。

## 2026-07-12（DS01/DS03/DS05/DS07 跨入口一致性审计）
- 新增 `scripts/audit_ds_consistency_contract.py`：只读检查 DS01 左30 <=2、DS03 failed high/low、DS05 K2 possible extreme、DS07 新共振口径在核心包、雷达、pending monitor、paper monitor、fill supervision 和成交后沙盒图编排入口中的契约 token。
- 新增 `tests/test_audit_ds_consistency_contract.py`：覆盖当前仓库契约全绿、缺失 token 检出、缺失文件检出和 forbidden token 检出。
- 当前审计结论：核心 DS01/DS03/DS05/DS07、`src/fengji_total_radar.py`、`src/fengji_pending_order_monitor.py`、`src/overseas_paper_monitor.py`、`fill_supervision.py`、`generate_fill_sandbox_review.py`、DS03/DS07 沙盒图入口均保留当前口径相关 token，`failures=0`。
- 本次只增加只读审计和测试，未生成或改写真实交易数据，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、雷达触发、挂单、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_ds_consistency_contract.py` -> `failures=0`；`python -m pytest tests\test_audit_ds_consistency_contract.py -q` -> **4 passed**；`python -m py_compile scripts\audit_ds_consistency_contract.py` 通过。

## 2026-07-10（总定式统一账本回归）
- 新增 `scripts/audit_unified_ledger_regression.py`：使用合成 candidates 和临时目录回归统一账本契约，覆盖 `merge_candidates` 的 accepted/rejected/ledger events、同向持仓上限、反向持仓拦截、缺失入场时间拒绝，以及期货/crypto batch scoring 输出。
- 新增 `tests/test_audit_unified_ledger_regression.py`：覆盖统一账本合成审计、merge candidates 契约、期货评分契约和 crypto 评分契约。
- 现有重点测试补充回归：`PYTHONPATH=services;src;packages/fengji_core` 后运行 `test_audit_unified_ledger_regression.py`、`test_audit_paper_ledger_contract.py`、`test_monitor_ledger.py`、`test_backtest_trade_pnl_ratio.py`、`test_discover_backtest_results.py`、`test_radar_signal_tier.py` -> **16 passed, 5 skipped**；未补环境时服务测试会因 `radar_snapshot` / `db` 导入路径缺失而 collection error。
- 本次只增加合成数据审计和测试，未读写真实交易结果，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、回测规则、雷达、挂单、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_unified_ledger_regression.py` -> `failures=0`；`python -m pytest tests\test_audit_unified_ledger_regression.py -q` -> **4 passed**；补环境重点集 -> **16 passed, 5 skipped**；`python -m py_compile scripts\audit_unified_ledger_regression.py` 通过；`python scripts\verify_phase2_closeout.py` -> `PHASE2_CLOSEOUT_OK`。

## 2026-07-10（九大定式单定式回归测试）
- 运行现有 DS 单测与雷达定式测试集，覆盖 DS01、DS03、DS05、DS09 核心测试，DS09 期货 session，DS03/DS08 pending fill，DS04-DS09 radar 入口。
- 当前覆盖边界：仓库现有测试没有独立 `test_ds02.py`、`test_ds04.py`、`test_ds06.py`、`test_ds07.py` 核心单测文件；这些定式本轮通过 radar/pending 入口覆盖，后续逐一定式复核仍需补专门案例测试和沙盒图。
- 本次只运行测试并记录结果，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、雷达、挂单、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python -m pytest tests\test_ds01.py tests\test_ds03.py tests\test_ds05.py tests\test_ds09.py tests\test_ds09_futures_session.py tests\test_ds03_pending_fill.py tests\test_ds08_pending_fill.py tests\test_radar_ds04.py tests\test_radar_ds05.py tests\test_radar_ds06.py tests\test_radar_ds07.py tests\test_radar_ds08.py tests\test_radar_ds09.py -q` -> **56 passed, 1 skipped**。

## 2026-07-10（A股板块结果归档覆盖审计）
- 新增 `scripts/audit_a_stock_sector_archive.py`：只读审计 A股板块回测归档覆盖，检查 `a_stock_all_sectors_overview.csv`、`a_stock_all_sectors_master_summary.csv`、`fengji_total_a_stock_sectors_os20260529_run.log` 和旧 `a_stock_sector_archive_ds07_fixed.zip`。
- 新增 `tests/test_audit_a_stock_sector_archive.py`：覆盖当前归档契约、缺失 zip 摘要检出、overview 最小夹具和空缺明细目录快照。
- 当前归档事实：全量汇总 CSV 保留 11 个板块、274 条股票明细、`bad_audits=0`；旧 zip 可读但仅含 CPO/算力/半导体/虚拟机器人 4 个板块摘要；`master_summary` 引用的 274 个 `source_file` 与 274 个 `out_dir` 当前本地均不存在，因此不能视为完整 per-stock 明细归档。
- 本次只增加只读审计、测试和文档状态更新，未重跑 A股回测，未压缩/删除 results，未修改峰极线、阵营转换、DS01-DS09 核心逻辑；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_a_stock_sector_archive.py` -> `failures=0`；`python -m pytest tests\test_audit_a_stock_sector_archive.py -q` -> **4 passed**；`python -m py_compile scripts\audit_a_stock_sector_archive.py` 通过；`python scripts\verify_phase2_closeout.py` -> `PHASE2_CLOSEOUT_OK`。

## 2026-07-10（模拟挂单刷新与冲突撤销策略审计）
- 新增 `scripts/audit_pending_refresh_policy.py`：只读审计挂单刷新与成交后冲突撤销策略，覆盖 radar loop 每轮刷新总雷达并重写 `pending_orders.json`、海内外 watchdog 生产频率、`valid_until` 锚点、monitor 过滤已成交/已撤销 order/setup，以及既有冲突撤单契约测试覆盖。
- 新增 `tests/test_audit_pending_refresh_policy.py`：覆盖当前契约全绿、`valid_until` 以刷新时刻为锚、缺失 token 检出和空 runtime 快照。
- 当前策略结论：不需要额外每日开盘前统一批量刷新；国内 watchdog radar loop 600 秒、pending monitor 5 秒且启用 `--enforce-valid-until`；海外 watchdog radar loop 900 秒、pending monitor 5 秒；成交后同品种冲突撤销由 shared monitor state 事件驱动，DS01 同向加仓挂单例外保留。
- 本次只增加只读审计、测试和文档状态更新，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook；未重启服务器进程。
- 验证：`python scripts\audit_pending_refresh_policy.py` -> `failures=0`；`python -m pytest tests\test_audit_pending_refresh_policy.py tests\test_audit_pending_order_contract.py tests\test_fengji_radar_order_loop_market.py tests\test_summarize_pending_effective_status.py -q` -> **16 passed**；`python -m py_compile scripts\audit_pending_refresh_policy.py` 通过；`python scripts\verify_phase2_closeout.py` -> `PHASE2_CLOSEOUT_OK`。

## 2026-07-10（挂单触发后沙盒图复核流程审计）
- 新增 `scripts/audit_fill_sandbox_review_flow.py`：只读审计 effective pending summary 到成交后沙盒图复核的编排链路，覆盖 `--sandbox-review`、`--sandbox-review-execute`、事件尾读、`fill_sandbox_review.json/md` 输出、测试覆盖和 DS plotter 接入。
- 新增 `tests/test_audit_fill_sandbox_review_flow.py`：覆盖当前契约全绿、缺失 token 检出和空 runtime 快照。
- 当前复核流程口径：`scripts/summarize_pending_effective_status.py --sandbox-review` 默认只生成复核清单，不执行画图；只有显式传 `--sandbox-review-execute` 才调用已有 plotter；`events.jsonl` 默认尾读 20000 行，避免大日志全量扫描。
- 当前支持的已成交/持仓复核策略：DS01、DS03、DS04、DS05、DS07、DS08、DS09；未支持策略会显式输出 `unsupported`，不静默跳过。
- 本次只增加流程审计和测试，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook；未重启服务器进程。
- 验证：`python scripts\audit_fill_sandbox_review_flow.py` -> `failures=0`；`python -m pytest tests\test_audit_fill_sandbox_review_flow.py tests\test_summarize_pending_effective_status.py tests\test_generate_fill_sandbox_review.py -q` -> **15 passed**；`python -m py_compile scripts\audit_fill_sandbox_review_flow.py` 通过。

## 2026-07-10（海内外核心 DS 修正部署审计）
- 新增 `scripts/audit_server_core_logic_deploy.py`：只读审计 DS01/DS03/DS05/DS07 与 `src/fengji_total_radar.py` 的本地特征 token，并可通过 SSH 对国内/海外服务器执行 live hash/token 比对；远端只返回 hash 和缺失 token 列表，不打印源码或配置。
- 新增 `tests/test_audit_server_core_logic_deploy.py`：覆盖本地关键特征全绿、hash mismatch 检出、缺失 token 检出和远端命令构造。
- live 复核：国内服务器与海外服务器均为 `mismatches=0`；`ds01.py`、`ds03.py`、`ds05.py`、`ds07.py`、`fengji_total_radar.py` 的远端 hash 与本地一致，关键 token 均无缺失。
- 本次只增加部署审计和测试，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook；未重启服务器进程。
- 验证：`python scripts\audit_server_core_logic_deploy.py` -> `failures=0`；`python scripts\audit_server_core_logic_deploy.py --remote all` -> `failures=0` / 国内海外 `mismatches=0`；`python -m pytest tests\test_audit_server_core_logic_deploy.py -q` -> **4 passed**；`python -m py_compile scripts\audit_server_core_logic_deploy.py` 通过。

## 2026-07-10（src/quant 与 fengji_core 双实现边界审计）
- 新增 `scripts/audit_quant_import_shims.py`：只读审计本地 `src/quant` 是否仅为 `fengji_core` 兼容 re-export shim，检查 15 个 shim 模块无函数、类、赋值等策略逻辑，并确认 `packages/fengji_core/fengji_core` 对应源码存在。
- 审计同时检查国内同步边界：`scripts/sync_deploy_domestic.ps1` 仍从 `$Core` / `packages/fengji_core` 同步核心 OS/DS 文件到远端兼容路径，`scripts/fengji_domestic_deploy_manifest.txt` 不把本地 `src/quant` shim 当作策略源码。
- 新增 `tests/test_audit_quant_import_shims.py`：覆盖当前契约全绿、函数逻辑误入 shim 的检出、`__version__` re-export 解析，以及 UTF-8 BOM 读取兼容。
- 本次只增加结构审计和测试，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_quant_import_shims.py` -> `failures=0`；`python -m pytest tests\test_audit_quant_import_shims.py tests\test_fengji_domestic_deploy_manifest.py -q` -> **6 passed**；`python -m py_compile scripts\audit_quant_import_shims.py` 通过。

## 2026-07-10（国内期货天勤数据源与日夜盘时段审计）
- 新增 `scripts/audit_domestic_futures_data_schedule.py`：只读审计国内期货天勤数据泵契约，覆盖 `tqsdk`/`tqsdk2` 回退、`TQ_PHONE`/`TQ_PASS` 环境变量凭据、34 个 `KQ.m@` 主连发现码、`1d/1h/15m/5m` 周期、日盘/夜盘/A股窗口、空闲断连与长连接复用、watchdog 心跳/15m 新鲜度阈值，以及 `docs/MARKET_COVERAGE_BOUNDARIES.md` 全品种夜盘结束表。
- 新增 `tests/test_audit_domestic_futures_data_schedule.py`，并将审计脚本和 `docs/MARKET_COVERAGE_BOUNDARIES.md` 纳入国内同步清单；远端同步审计脚本、边界文档、同步脚本和部署清单，未重启任何国内进程。
- 国内远端复核：`py_compile` 通过，`scripts/audit_domestic_futures_data_schedule.py` 输出 `failures=0`，runtime 快照显示 `1d/1h/15m/5m` 各 68 个 CSV，data_manager 心跳 `idle` 且 age 约 37 秒；`verify_domestic_health.ps1` 显示 data_manager 单进程、PG/SC 15m `ACCEPTANCE_OK`。
- 本次未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_domestic_futures_data_schedule.py` -> `failures=0`；`python -m pytest tests\test_audit_domestic_futures_data_schedule.py tests\test_market_coverage_boundaries.py tests\test_data_manager_futures_main_contracts.py tests\test_data_manager_futures_5m.py tests\test_fengji_domestic_deploy_manifest.py -q` -> **23 passed**；`python -m py_compile scripts\audit_domestic_futures_data_schedule.py` 通过。

## 2026-07-10（海外虚拟货币数据源与新鲜度审计）
- 新增 `scripts/audit_crypto_data_pipeline.py`：只读审计海外 crypto 数据链路，覆盖 Binance 主数据泵 16 币种、OKX fallback HYPE/ATH、OKX ingest 新鲜度、watchdog 补偿、海外运行态检查契约，并输出 `data/1d`、`data/1h`、`data/15m` runtime 快照。
- 新增 `tests/test_audit_crypto_data_pipeline.py`：覆盖当前契约全绿、CSV 末行时间解析和缺文件快照。
- 更新 `峰极OS_数据与回测说明.md`：补充海外虚拟货币主源、fallback、watchdog 频率、新鲜度阈值和审计命令；未写入任何服务器地址、密钥、Token、密码或完整 webhook。
- 海外部署：仅同步 `scripts/audit_crypto_data_pipeline.py` 到海外服务器，未重启进程；远端 `py_compile` 通过，远端审计 `failures=0`，18 个币种三周期 `available_total=54/54`。
- 远端运行态复核：`check_okx_csv_freshness.py` 显示 HYPE/ATH 的 `15m`、`1h`、`1d` 均为 `ok`；`check_overseas_runtime_status.ps1` 显示 data_manager、radar loop、pending monitor、paper monitor 均在运行，`data/15m` 样本更新至 2026-07-10 11:27，radar/pending 更新至 11:24。
- 本次只增加数据链路审计和文档说明，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损或模拟成交规则。
- 验证：`python scripts\audit_crypto_data_pipeline.py` -> `failures=0`；`python -m pytest tests\test_audit_crypto_data_pipeline.py tests\test_sync_okx_crypto_timeframes.py tests\test_runtime_check_scripts.py -q` -> **12 passed**；`python -m py_compile scripts\audit_crypto_data_pipeline.py` 通过。

## 2026-07-10（国内模拟盘启动协同审计）
- 新增根目录 `run_futures_astock_paper.ps1`：国内 paper 根入口统一调用 `scripts/resolve_domestic_paper.ps1`，按 `scripts/domestic_paper_manifest.txt` 解析中文模拟盘文件名，并写入 `runtime/logs/futures_astock_paper_run.log` / `_err.log`。
- 修正 `scripts/start_factory_ascii.bat`：radar 与 pending monitor 改为调用 `scripts\run_futures_radar_loop.cmd`、`scripts\run_futures_pending_monitor.cmd`，避免启动工厂依赖远端根目录下缺失的 cmd 包装脚本。
- 修正 `scripts/run_futures_radar_loop.cmd`：补齐 `--market futures`、`--monitor-state runtime\fengji_pending_orders\futures_pending_state.json`、`--include-triggered`、`--loop-seconds 600`、`--m15-tail 960`、`--top-n 40`，与 `restart_domestic_futures_runtime.ps1` / `watchdog_domestic.ps1` 的生产口径对齐。
- 更新 `scripts/sync_deploy_domestic.ps1` 与 `scripts/fengji_domestic_deploy_manifest.txt`：纳入 data manager 根入口、paper 根入口、start factory、radar/pending cmd 包装脚本，避免后续同步遗漏启动工厂依赖。
- 新增 `scripts/audit_domestic_paper_coordination.py` 与 `tests/test_audit_domestic_paper_coordination.py`：只读审计国内模拟盘入口、启动工厂、数据泵、radar loop、pending monitor、watchdog、同步清单和 webhook 字面量边界。
- 国内部署：仅同步上述入口/审计文件与 `scripts/deploy_domestic_paper_feishu.ps1` 到国内服务器；未重启进程。远端 `py_compile` 通过，远端审计 `failures=0`，runtime 快照显示 manifest、paper 根文件、orders、pending state、paper state、trade CSV、data dir 均存在。
- 本次只改启动/部署/审计层，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_domestic_paper_coordination.py` -> `failures=0`；`python -m pytest tests\test_audit_domestic_paper_coordination.py tests\test_fengji_domestic_deploy_manifest.py -q` -> **4 passed**；`python -m py_compile scripts\audit_domestic_paper_coordination.py` 通过。

## 2026-07-10（海外 DS 覆盖与通知审计）
- 新增 `scripts/audit_overseas_notification_coverage.py`：只读审计海外虚拟货币 DS01-DS09 入口覆盖、共享飞书状态词和当前 runtime 快照；脚本通过 AST 读取 `overseas_paper_monitor.py` 常量，避免导入运行态模块触发副作用。
- 新增 `tests/test_audit_overseas_notification_coverage.py`：覆盖 DS01-DS09 静态入口覆盖、飞书状态词 smoke、runtime 统计和直接运行导入路径。
- 海外部署：仅同步审计脚本到海外服务器；远端 `.venv/bin/python -m py_compile` 通过，远端审计 `failures=0`，当前 DS 覆盖 `missing=[]`，飞书状态词检查 `ok`。
- 当前海外 runtime 快照：radar 策略计数 `DS01=8, DS02=26, DS03=25, DS06=3, DS08=3`；pending 策略计数 `DS01=3, DS03=7, DS08=3`；有效挂单 `active=6, cancelled=7`；paper open 策略计数 `DS01=1, DS07=4, DS08=2`。
- 本次只增加只读审计与测试，未修改峰极线、阵营转换、DS01-DS09 核心逻辑、挂单触发、止损或模拟成交规则；未写入密钥、Token、密码或完整 webhook。
- 验证：`python scripts\audit_overseas_notification_coverage.py` -> `failures=0`；`python -m pytest tests\test_audit_overseas_notification_coverage.py tests\test_feishu_trade_notify.py tests\test_summarize_pending_effective_status.py -q` -> **13 passed**；`python -m py_compile scripts\audit_overseas_notification_coverage.py` 通过。

## 2026-07-10（海外飞书状态文案对齐）
- `packages/fengji_core/fengji_core/feishu_trade_notify.py`：海外挂单/成交/平仓共享通知文案增加明确状态标签；挂单显示 `已挂单`，多头成交显示 `已买入`，空头成交显示 `已卖出`，平仓按原持仓方向显示 `已卖出平仓` 或 `已买入平仓`。
- `tests/test_feishu_trade_notify.py`：补充断言锁定上述中文状态短语，避免后续海外飞书推送退回只显示价格标签。
- 海外部署：仅同步 `packages/fengji_core/fengji_core/feishu_trade_notify.py` 到海外服务器；远端 `.venv/bin/python -m py_compile` 通过；已定向重启海外 pending/paper monitor，复查新 PID 运行且 pending 日志继续刷新。
- 本次只改通知展示层，未修改峰极线、阵营转换、DS01-DS09、挂单触发、止损或模拟成交规则。
- 验证：`python -m pytest tests\test_feishu_trade_notify.py tests\test_feishu_paper_notify.py -q` -> **8 passed**；`python -m py_compile packages\fengji_core\fengji_core\feishu_trade_notify.py src\fengji_pending_order_monitor.py src\fengji_feishu_paper_notify.py src\overseas_paper_monitor.py` 通过。

## 2026-07-10（effective pending 接入成交后沙盒图复核）
- `scripts/summarize_pending_effective_status.py`：新增 `review_candidate_orders` 统计，并增加 `--sandbox-review` / `--sandbox-review-execute` 参数；运行 effective pending summary 时可直接生成成交后沙盒图复核清单。
- 安全默认值：`--sandbox-review` 只调用 `generate_fill_sandbox_review.py` 生成 `fill_sandbox_review.json/md`，不执行画图；只有显式传 `--sandbox-review-execute` 才运行已有 plotter。
- `tests/test_summarize_pending_effective_status.py`：补充 review candidate 统计和复核命令构造测试，锁定 orders/state/paper/event/data 参数透传。
- 海内外部署：仅同步 `scripts/summarize_pending_effective_status.py` 到国内/海外服务器，未重启进程；海外 dry-run 当前 `review_candidates=1 -> ready=1`，国内 LHUSDT dry-run `review_candidates=1 -> ready=1`。
- 本次只改审计编排入口，未修改峰极线、阵营转换、DS01-DS09、挂单触发、止损或模拟成交规则。
- 验证：`python -m pytest tests\test_summarize_pending_effective_status.py tests\test_generate_fill_sandbox_review.py tests\test_runtime_check_scripts.py -q` -> **15 passed**；`python -m py_compile scripts\summarize_pending_effective_status.py scripts\generate_fill_sandbox_review.py` 通过；`python scripts\verify_phase2_closeout.py` -> `PHASE2_CLOSEOUT_OK`。

## 2026-07-09（成交后沙盒图复核编排）
- `scripts/plot_live_ds09_sandbox.py` 增加历史索引归一化：当事件中的 `lock_idx` / `attack_idx` / `defense_idx` 距离当前全量 M15 入场索引过远时，在入场前局部窗口内按 `boundary` / `trigger_price` / `stop_price` 重定位标注，避免旧事件图被拉成长跨度全量图。
- 国内 DS09 smoke 复跑：`TAUSDT DS09` 的旧索引 `953/956` 已重定位到 `3876/3872` 附近，归一化图已复制回 `runtime/fill_sandbox_review/smoke_TAUSDT_DS09_live_normalized.png`。
- 海外已同步 DS09 归一化版本，`.venv/bin/python` 编译与尾读 dry-run 通过。
- 验证：`python -m pytest tests\test_plot_live_ds09_sandbox.py tests\test_generate_fill_sandbox_review.py -q` -> **10 passed**。
- 新增 `scripts/plot_live_ds05_sandbox.py` 与 `scripts/plot_live_ds09_sandbox.py`：DS05 / DS09 的 `filled_open` 不再依赖已平仓 `trades.trade_no`，改为 open/live 沙盒图入口；已平仓 `filled` 仍保留原 backtest trade plotter 路径。
- `generate_fill_sandbox_review.py` 更新：DS05 / DS09 当 `effective_status=filled_open` 时优先调用 live plotter；DS05 按 `setup_key` 的 K2/K3 回放 `make_ds05_signal`，DS09 按事件中的 session/lock/attack/defense/boundary 元数据绘制 D1+M15 上下文。
- 国内 smoke：历史 `LCUSDT DS05` 成交已生成 `runtime/fill_sandbox_review/smoke_LCUSDT_DS05_live.png`，回放信号为 `DS05 Bearish Finger`；历史 `TAUSDT DS09` 成交已生成 `runtime/fill_sandbox_review/smoke_TAUSDT_DS09_live.png`，随后已补归一化版本。
- 国内/海外已同步 DS05/DS09 live plotter 与编排器；两端编译通过，国内 dry-run 仍为 `total=12 counts={'ready': 12}`，海外当前 `filled/filled_open` 候选为 0。
- 验证：`python -m pytest tests\test_generate_fill_sandbox_review.py tests\test_audit_ds04_fill_sandbox_match.py -q` -> **9 passed**。
- 新增 `scripts/plot_live_ds04_sandbox.py`：针对 DS04 `filled_open` 持仓生成 open/live 沙盒图，直接按 `setup_key` 的 K1/K2/K3/K4 和现有 `make_ds04_signal` 回放，不依赖已平仓 `trades.trade_no`。
- 新增 `scripts/audit_ds04_fill_sandbox_match.py`：只读诊断 DS04 `no_backtest_trade`，输出 K1-K4 数据、`make_ds04_signal` 回放结果和附近 backtest trades；确认国内 SH/RB 两笔 DS04 可以回放出合法 signal，之前失败原因是旧编排误用"已平仓 trades"匹配 open fill。
- `generate_fill_sandbox_review.py` 的 DS04 分支改用 live/open plotter；国内 dry-run 从 `{'ready': 10, 'no_backtest_trade': 2}` 变为 `{'ready': 12}`。
- 实测：国内 `SHUSDT DS04 filled_open` 与 `RBUSDT DS04 filled_open` 已通过 `--execute` 生成成交后沙盒图，并复制回本地 `runtime/fill_sandbox_review/2026-07-08_160000_SHUSDT_DS04_long_SHUSDT-DS04-D1-lon.png`、`runtime/fill_sandbox_review/2026-07-08_160000_RBUSDT_DS04_long_RBUSDT-DS04-D1-lon.png`。
- 海外已同步 DS04 live plotter 与审计脚本，`.venv/bin/python` 编译和尾读 dry-run 通过；当前海外 `filled/filled_open` 候选仍为 0。
- 验证：`python -m pytest tests\test_audit_ds04_fill_sandbox_match.py tests\test_generate_fill_sandbox_review.py -q` -> **7 passed**。
- DS04 曾短暂按 closed trade_no 接入并输出 `no_backtest_trade`；本轮已改为 open/live plotter，国内 SH/RB 两笔已可生成图。
- 国内 dry-run 曾为 `total=12 counts={'ready': 10, 'no_backtest_trade': 2}`；本轮修正后为 `total=12 counts={'ready': 12}`。
- 海外 DS04 版本已同步并通过 `.venv/bin/python` 编译与尾读 dry-run；当前海外 `filled/filled_open` 候选仍为 0。
- 验证：`python -m pytest tests\test_generate_fill_sandbox_review.py tests\test_summarize_pending_effective_status.py tests\test_runtime_check_scripts.py -q` -> **12 passed**。
- 扩展 `scripts/generate_fill_sandbox_review.py`：DS05 / DS09 不再直接标为 `unsupported`，改为复用现有 `src/plot_ds05_sandbox.py` / `src/plot_ds09_sandbox.py`，通过 backtest trades 按方向、入场价和入场日期反查 `trade_no` 后生成沙盒图命令。
- 为 DS05 / DS09 接入增加 `match_trade_no` 保护：若当前成交无法匹配回现有 backtest trade，则输出 `no_backtest_trade`，不伪造图、不回填定式逻辑。
- 海外尾读修正版已在 SSH 恢复后重新同步并验证：系统 `python3` 可通过编译，项目 `.venv/bin/python` 可完成 `--event-tail-lines 5000` dry-run，未再全量扫描大日志。
- 国内 dry-run 验证曾为：`total=12 counts={'ready': 10, 'unsupported': 2}`，剩余 unsupported 为 DS04 样本；DS04 接入后已更新为 `no_backtest_trade`。
- 验证：`python -m pytest tests\test_generate_fill_sandbox_review.py tests\test_summarize_pending_effective_status.py tests\test_runtime_check_scripts.py -q` -> **11 passed**。
- 新增 `scripts/generate_fill_sandbox_review.py`：读取 effective pending summary，筛选 `filled` / `filled_open`，匹配 `events.jsonl` 的成交价和成交时间，生成成交后沙盒图复核报告；默认只生成 `json/md` 复核清单，只有显式 `--execute` 才调用画图脚本。
- 事件日志读取改为默认尾读 `--event-tail-lines 20000`，避免海外约 GB 级 `events.jsonl` 被全量扫描导致运行态工具卡死；`--event-tail-lines 0` 可用于需要全量回放的离线场景。
- 编排器当前接入 DS01、DS03、DS04、DS05、DS07、DS08、DS09 既有沙盒图脚本；尚未接入的定式会明确标为 `unsupported`，不静默跳过。
- 修正 `scripts/plot_live_ds07_sandbox.py` 的图形侧 `--side long|short` 标注，使 DS07 short 图不再被固定标成 long；该改动只影响沙盒图展示，不改 DS07 信号逻辑。
- 国内服务器已同步 `generate_fill_sandbox_review.py`、`summarize_pending_effective_status.py`、`plot_live_ds07_sandbox.py` 和 DS01 画图脚本；未重启进程，未修改峰极线、阵营转换或 DS01-DS09 核心逻辑。
- 海外服务器在尾读修正版同步阶段 SSH/SCP 曾短暂超时；SSH 恢复后已重新覆盖并完成 dry-run 验证。
- 实测：国内 `LCUSDT DS01 filled_open` 已通过 `--execute` 生成成交后沙盒图，图像已复制回 `runtime/fill_sandbox_review/2026-07-08_160000_LCUSDT_DS01_short_LCUSDT-DS01-D1-sho.png`。
- 验证：`python -m py_compile scripts\generate_fill_sandbox_review.py scripts\summarize_pending_effective_status.py scripts\plot_live_ds07_sandbox.py` 通过；`python -m pytest tests\test_generate_fill_sandbox_review.py tests\test_summarize_pending_effective_status.py tests\test_runtime_check_scripts.py -q` -> **10 passed**。

## 2026-07-09（有效挂单视图与运行态去误导）

- 新增 `scripts/summarize_pending_effective_status.py`：合并 `pending_orders`、执行 state、模拟盘 paper state，输出 `raw_status` 与 `effective_status`，区分 `active`、`ready_triggered`、`filled`、`filled_open`、`cancelled`。
- 更新 `scripts/check_domestic_runtime_remote.ps1` 与 `scripts/check_overseas_runtime_status.ps1`：运行态检查增加 effective pending summary；远端未部署脚本时输出明确提示，不误判为无挂单。
- 新增 `tests/test_summarize_pending_effective_status.py`，并扩展 `tests/test_runtime_check_scripts.py`，覆盖已成交持仓、冲突撤销、仍可行动挂单三类状态。
- 已将只读脚本 `scripts/summarize_pending_effective_status.py` 同步到国内/海外服务器，未重启任何进程，未修改峰极线、阵营转换或 DS01-DS09 核心逻辑。
- 现场复核：国内 `LCUSDT` 当前 `DS01 READY_TRIGGERED` 被有效标记为 `filled_open`，`DS03 ACTIVE` 被有效标记为 `cancelled`，`actionable=0`，避免已成交/已撤销候选被误看成仍可触发挂单。
- 验证：`python -m pytest tests\test_summarize_pending_effective_status.py tests\test_runtime_check_scripts.py tests\test_pending_orders.py tests\test_futures_pending_orders.py tests\test_fill_supervision.py tests\test_radar_setup_keys.py tests\test_audit_pending_order_contract.py tests\test_audit_paper_ledger_contract.py tests\test_audit_security_boundaries.py -q` → **59 passed**；`python scripts\verify_phase2_closeout.py` → `PHASE2_CLOSEOUT_OK`。

## 2026-07-08（挂单触发与冲突撤单契约复查）

- 新增 `scripts/audit_pending_order_contract.py`：行为级校验默认挂单策略集合、海外现价触发、国内 K 线 high/low 触发、同品种冲突撤单和 DS01 同向加仓保留规则。
- 新增 `tests/test_audit_pending_order_contract.py`：锁定冲突撤单契约和当前挂单触发契约。
- 更新 `峰极OS_挂单器与模拟实盘说明.md`：补齐同品种冲突撤单记录字段、DS01 同向加仓保留、海外/国内触发来源差异，并修正默认挂单集合包含 DS09 的旧描述。
- 复验：`python scripts/audit_pending_order_contract.py` 输出 `failures=0`；挂单监控相关测试通过。

## 2026-07-08（模拟账本契约复查）

- 新增 `scripts/audit_paper_ledger_contract.py`：静态校验海外/国内模拟挂单监控的默认资金参数、开仓字段、平仓字段和交易 CSV 字段。
- 新增 `tests/test_audit_paper_ledger_contract.py`：覆盖 argparse 默认值提取、账本字段提取和当前契约全绿。
- 更新 `峰极OS_挂单器与模拟实盘说明.md`：补齐海外/国内模拟开仓、平仓、止损、手续费、滑点、保证金/名义本金和账本字段口径。
- 复验：`python scripts/audit_paper_ledger_contract.py` 输出 `failures=0`；挂单监控相关测试通过。

## 2026-07-08（安全边界审计）

- 新增 `scripts/audit_security_boundaries.py`：扫描仓库代码文件中的完整 webhook URL、常见 API key 字面量和真实下单 API 调用；输出只包含文件、行号和类别，不打印疑似密钥值。
- 新增 `tests/test_audit_security_boundaries.py`：覆盖完整 webhook URL 检出、环境变量/正则误报规避、真实下单 API 检出。
- 脱敏修正：`scripts/patch_domestic_feishu_defaults.py` 不再保留完整 webhook 替换字面量，改为通用正则移除硬编码默认值。
- 复验：`python scripts/audit_security_boundaries.py` 输出 `failures=0 warnings=0`；海外/国内启动脚本抽样扫描未发现完整 webhook URL；仓库扫描未发现真实下单 API 调用。

## 2026-07-08（海内外运行态与国内 hash 复查）

- 海外运行态复查：`check_overseas_runtime_status.ps1` 显示 data_manager、radar loop、pending monitor、paper monitor 均在运行；`radar.json` / `pending_orders.json` 更新至 2026-07-08 17:57，15m CSV 样本更新至 18:06。
- 国内运行态复查：`check_domestic_runtime_remote.ps1` 显示 data_manager/radar/pending 均为单进程，heartbeat age < 120s，PG/SC 15m 验收 `ACCEPTANCE_OK`。
- 国内同步：仅同步 `packages/fengji_core/fengji_core/fill_supervision.py` 到国内，使 DS05 盘中触发重绘场景的审计层修复与海外一致；远端 `py_compile` 通过。
- 修正 `compare_domestic_ds08_hashes.py`：国内 hash 比对改为规范化 CRLF/LF 后的 SHA256 前 16 位，避免 Windows 远端换行差异造成误报；新增 `tests/test_compare_domestic_ds08_hashes.py`。
- 复验：`compare_domestic_ds08_hashes.py` 为 `mismatches=0`；`compare_overseas_core_hashes.py` 为 `mismatches=0`；相关 hash 脚本测试通过。

## 2026-07-08（海外 fill supervision 重复告警止血）

- 海外 watchdog 连续告警来自同一笔已知 invalid 模拟成交：`BTCUSDT-DS05-D1-short-da008ccaf48b8587`，`DS05` short，问题为 `make_ds05_signal returned None at setup bar`。
- 已在海外 `runtime/fill_supervision_acknowledged.json` 登记该 order_id 为 `audit_invalid`，并写入 `runtime/n04_rebuild_disposition.json`；未修改 DS05 核心逻辑。
- 复验：重跑海外 `audit_paper_fills.py --profile overseas --since-hours 72 --fail-on-invalid --ack-file runtime/fill_supervision_acknowledged.json --quiet` exit **0**；latest summary 为 `invalid=1 invalid_acknowledged=1 invalid_new=0`。
- 已清理海外 `runtime/watchdog/fill_supervision_invalid.alert`；后续仍需专项复核 BTCUSDT DS05 pending 生成源与审计回放口径是否漂移。
- 根因复核：该笔 DS05 是 D1 K3 未收完时触发，后续 2026-07-06 最终日线高点 `64700` 高于 K2 高点 `63999`，导致最终 D1 bar 回放 `make_ds05_signal` 为 None。
- 审计层修复：`fill_supervision.audit_ds05_fill` 对"最终 D1 bar 无法重放，但 setup_key K3 日期匹配且 pending fill 成交价满足触发"的 DS05 盘中触发标记为 `skipped`，不再计入 `invalid_new`；不改变 DS05 信号、挂单、成交和止损逻辑。
- 部署与复验：仅同步 `packages/fengji_core/fengji_core/fill_supervision.py` 到海外；远端 `audit_paper_fills.py --fail-on-invalid` exit **0**，latest summary 为 `invalid=0 invalid_new=0 skipped=8`；`compare_overseas_core_hashes.py` 为 `mismatches=0`。
- 后续观察：海外 2026-07-08 17:50 watchdog 轮次显示 `fill_supervision ok`，latest summary 仍为 `invalid=0 invalid_new=0 skipped=8`，且 `runtime/watchdog/fill_supervision_invalid.alert` 不存在。

## 2026-07-07（Codex 接手复验与 radar loop market 兼容）

- `fengji_radar_order_loop.py`：补齐 `--market` 参数、market 自动推断和 `FENGJI_MARKET` 子进程传递，避免海外/国内重启时带 `--market` 的命令行解析失败。
- `fengji_radar_order_loop.py`：补齐 `--m15-tail` 透传，兼容海外 watchdog 当前生产启动命令。
- `watchdog_overseas.sh`：后台拉起 data/radar/pending/paper 前关闭 watchdog lock fd，避免子进程继承 `watchdog.lock` 导致后续 cron 长期 `skip`。
- 部署：仅同步 `src/fengji_radar_order_loop.py` 到国内/海外；另同步海外 `scripts/watchdog_overseas.sh` 并在远端转 LF。国内 radar loop 已重启；海外 watchdog 自动拉起 radar/pending，`radar.json` 与 `pending_orders.json` 已刷新至 2026-07-07 19:04。
- 测试修正：`test_fengji_radar_order_loop_market.py` 覆盖 loop 层 market 推断；`test_radar_setup_keys.py` 的 DS03 样本补齐 OS 防守极字段，避免用缺防守极样本绕过现行规则。
- 环境型验收测试：W08 Pencil frames、W17 本地 PG/auth storage 不具备时改为 skip，保留真实前置满足时的验收失败能力。
- 验证：`verify_project_buckets.ps1` 全绿；核心 OS/DS/挂单/雷达测试 **67 passed**；全量 `python -m pytest tests -q` → **479 passed, 17 skipped**；国内 `verify_domestic_health.ps1` OK；海外 runtime 检查 OK；海外核心 hash `mismatches=0`。
- 运行态风险：海外 fill supervision 近 72h 报 `invalid_new=1`，对象为 `BTCUSDT` / `DS05` / short，原因 `make_ds05_signal returned None at setup bar`；未改交易/定式逻辑，列入后续专项复核。

## 2026-07-07（节后运行态巡检 + 海外 hash 误报修正）

- 实时巡检：国内 `verify_domestic_health.ps1` 通过；data_manager/radar/pending 均为单进程，PG/SC 15m 验收 `ACCEPTANCE_OK`。
- 实时巡检：海外 data_manager/radar_loop/pending/paper 均在运行，OS state 持续更新。
- 修正 `compare_overseas_core_hashes.py`：`.sh` 文件本地 hash 按 LF 规范化，避免 Windows CRLF 与服务器 LF 导致 `watchdog_overseas.sh` 假 mismatch。
- 新增 `tests/test_compare_overseas_core_hashes.py` 覆盖 shell 换行规范化与非 shell 原始字节 hash。
- 完善巡检脚本输出：`check_overseas_runtime_status.ps1` 避免本地 PowerShell 误展开远端 `${FENGJI_MARKET:-crypto}`，并改用递归 CSV mtime 抽样；`check_domestic_runtime_remote.ps1` 的额外进程段改为文本输出，避免 CLIXML 信息流污染。
- 新增 `tests/test_runtime_check_scripts.py` 锁定海外远端变量展开与国内文本输出约束。

## 2026-07-07（Codex App 一键接手文档）

- 新增根目录 **`CODEX_APP_HANDOFF.md`**：开场白 · 60 秒检查 · Phase2 签收 · 目录/服务器/stash · 接手报告模板。
- 更新 `README.md` · `AGENTS.md` · `PROJECT_CONTEXT.md` · `.cursor/rules/project.mdc` 指向该入口。

## 2026-07-07（Phase 2 签收文档）

- 新增 `docs/PLAN_B_PHASE2_COMPLETE.md` · 更新 `PROJECT_CONTEXT.md` Phase 2 完成态。

## 2026-07-07（D7 · Phase 2 收口）

- 新增 `docs/PHASE2_CLOSEOUT.md` · `docs/STASH_BOUNDARY_AUDIT.md`（stash@{0} 411 文件分类）。
- 新增 `scripts/fengji_phase2_closeout_manifest.txt` · `fengji_stash_residual_manifest.txt`。
- 新增 `scripts/verify_phase2_closeout.py` · `tests/test_phase2_closeout_manifest.py`。
- `verify_project_buckets.ps1` 纳入 Phase2 closeout manifest 检查。

## 2026-07-07（D6 · 市场覆盖边界）

- 新增 `fengji_core.market_coverage`：A股 H1≥500 / M15≥800 定式门槛 · 期货 34 品种夜盘结束表。
- 新增 `docs/MARKET_COVERAGE_BOUNDARIES.md` · `scripts/verify_d6_market_coverage_boundaries.py`。
- `backtest_a_stock_fengji`：H1 行数不足时自动跳过 DS07/DS08（不再仅判空文件）。

## 2026-07-07（D5 · 数据与挂单口径）

- **安全**：`data_manager_futures.require_tq_credentials()` — 移除 `TQ_PHONE`/`TQ_PASS` 代码默认明文。
- **文档**：更新 `docs/RADAR_REFRESH_SCHEDULE.md`（海外 900s · 国内 600s 生产口径）；新增 `docs/PENDING_ORDER_CANCEL_RULES.md`。
- **验收**：`scripts/verify_d5_data_pending_policy.py` · `tests/test_data_manager_futures_tq_env.py`。

## 2026-07-07（D4 merge · 定式回归 + 飞书中文名）

- **PR merge**（`feat/d4-pattern-regression`）：`verify_d4_pattern_cases.py` · `domestic_display` 飞书中文名。
- 国内已 sync：`symbol_names` · `fengji_futures_pending_order_monitor` · `verify_d4_pattern_cases.py`。

## 2026-07-07（国内飞书品种中文名）

- `fengji_futures_pending_order_monitor`：飞书通知改用 `domestic_display`（如 **纯碱(SA)**）。
- `symbol_names.domestic_display`：期货/A股统一中文(代码) 展示。

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
- 明确服务器连接信息、登录用户、密码、API Key、Token、完整 webhook、数据源账号密码均不得写入仓库文档；敏感信息只写"见本地私密配置文件/环境变量/服务器控制台"。
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
- 更新 `docs/DS09_CALIBRATION.md`、`docs/DS09_DRAFT.md`、`docs/DS09_IN_TOTAL_PATTERN.md`、`docs/CANONICAL_RULES.md`、`docs/FENGJI_TOTAL_PATTERN_SPEC.md`、`峰极OS_最高宪法.md`、`峰极OS_九大定式规则总纲.md`：废止"D1不提供OS阵营方向"的旧表述。
- 更新 `AGENTS.md`、`PROJECT_CONTEXT.md`、`README.md`、`TODO.md`：把 `峰极OS_最高宪法.md`、`峰极OS_阵营转换判断.md`、`峰极OS_九大定式规则总纲.md` 加入接手重点，并记录DS09雷达/挂单器待补齐事项。

### 补全 DS06、DS07、DS09 九大定式总纲

- 更新 `峰极OS_九大定式规则总纲.md`：DS06 外扩峰式从"部分完整"调整为"完整"，明确其核心为转势授权后等待 D/E/F 或 d/e/f 外扩启动，不是破旧极立即入场。
- 更新 `峰极OS_九大定式规则总纲.md`：DS07 共振式从"部分完整"调整为"完整"，当前正式口径为 D1 战略授权 + H1 同向延续或反向并轨；禁止恢复旧的"启动前 H1 必须已同阵营"窄逻辑。
- 更新 `docs/DS07_CALIBRATION.md` 和 `docs/DS07_DRAFT.md`：同步 DS07 当前并轨口径，避免旧文档误导后续 AI 或人工开发。
- 更新 `峰极OS_九大定式规则总纲.md`、`docs/DS09_CALIBRATION.md`、`docs/DS09_IN_TOTAL_PATTERN.md`：根据用户确认，DS09 股票式/A股专属版本等同九重天 D1+M15，不另立一套A股买卖规则。
- 更新 `TODO.md`：将 DS06、DS07、DS09 的规则补全事项标记完成，保留服务器同步、数据覆盖、运行验证等后续任务。

### 自动沉淀峰极OS总工程上下文

本次根据项目扫描结果、当前项目文件、已有代码、已有文档和当前会话上下文，更新根目录总交接文件。目标是让 Cursor 或新的 Codex 会话在无法读取旧聊天记录时，仍能理解这是完整峰极OS总工程，覆盖峰极OS最高宪法、阵营转换、DS01-DS09 九大定式、挂单器、实盘数据、国内/海外服务器、模拟实盘、回测验证和跨工具接手。

### 本次创建/更新的文件

- 更新 `PROJECT_CONTEXT.md`：新增"2026-05-27 总交接版"，补充项目名称、总目标、当前状态、已完成/未完成、目录结构、重要文件、峰极OS最高宪法、阵营转换、九大定式、挂单器、实盘数据、服务器部署、模拟实盘、回测验证、已知问题和接手说明。
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
