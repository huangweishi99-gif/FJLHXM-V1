# stash@{0} 边界审计

更新时间：2026-07-07

## 身份

| 项 | 值 |
|---|---|
| Stash 引用 | `stash@{0}` |
| 消息 | `b04-wip-all` |
| 文件数 | **411**（2026-07-07 统计） |
| 策略 | **禁止整包 pop**；按桶 cherry-pick；数据/UI 残留保留 |

## 目录分布

| 类别 | 文件数 | 处置 |
|------|--------|------|
| `data/` CSV | 332 | **保留 stash**；不入库、不 pop |
| `FJLHXM-UI` / 设计稿 | 2+ | **保留 stash**；Web UI 独立轨道 |
| `packages/` 核心 | 7 | 多数已 cherry-pick 进 HEAD；stash 为旧快照 |
| `src/` | 14 | 多数已 merge（PR #12–#15 等） |
| `scripts/` | 15 | 运维桶已 pick；其余按需单文件 |
| `tests/` | 11 | 随对应 src 桶已入库 |
| `docs/` | 6 | 部分已独立维护；勿用 stash 覆盖 |
| 根文档 / 其他 | 24 | 以当前 `main` Markdown 为准 |

## 已 cherry-pick 桶（勿重复 pop）

| 桶 | 代表文件 | 状态 |
|----|---------|------|
| 运维 | `watchdog_domestic.ps1` · `ensure_single_data_manager.ps1` | ✅ `fengji_ops_domestic_manifest.txt` |
| os_engine/radar | `os_engine.py` · `fengji_total_radar.py` · `ds07.py` | ✅ PR #12 已部署 |
| ds03/paper | DS03 真峰双极 · paper 相关 | ✅ 已部署 |
| fill_supervision | `fill_supervision` 完整版在 HEAD | ✅ hash match |
| Phase2 数据 | `import_futures_local` · 5m sync | ✅ `fengji_phase2_data_manifest.txt` |
| ARCHIVE 文档 | `archives/2026-06-02_*` | ✅ `fengji_archive_docs_manifest.txt` |
| D4–D6 | verify_d4/d5/d6 · 覆盖/挂单文档 | ✅ 2026-07-07 直接入库 |

## 残留清单

见 `scripts/fengji_stash_residual_manifest.txt`（`data/` · `FJLHXM-UI.pen` · `designs/`）。

## 安全操作

```powershell
# 查看（只读）
git stash show 'stash@{0}' --stat

# 单文件取出（示例）
git checkout 'stash@{0}' -- path/to/file.py

# 禁止
git stash pop
git stash apply
```

## 验收

```powershell
python scripts\verify_phase2_closeout.py
```
