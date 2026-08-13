# 本目录已废弃（DEPRECATED）

> 状态：**已废弃，仅保留历史存档。禁止安装、禁止作为新代码参考。**

## 废弃原因

本更新包内的 `src/quant/ds07.py` 包含 **DS07 反向并轨（ALIGN_TURN）完整逻辑**：

- `LONG_ALIGN_TURN` / `SHORT_ALIGN_TURN` 触发类型
- 允许 H1 从反向阵营破防守极后完成并轨
- `bad_trigger` 校验中同时接受 `ALIGN_TURN` 与 `CONTINUE` 四类触发

该口径与 2026-08-13 用户裁决冲突：

> **DS07 最终口径以权威源代码为准（仅延续）**——维持 `e596aca`（2026-07-05）冻结的 DS03 二四棒同向延续逻辑（`LONG_CONTINUE`/`SHORT_CONTINUE`，`prev_h1_camp==1` 启动前已同阵营）；反向并轨（ALIGN_TURN）已废止。

权威源：`packages/fengji_core/fengji_core/ds07.py`（e596aca 冻结），当前工程内唯一合法 DS07 实现。

## 禁止事项

- **禁止运行** `install_domestic_futures_ds07_update.ps1`（其强制校验 `LONG_ALIGN_TURN`/`SHORT_ALIGN_TURN` 标记，会把并轨逻辑安装回服务器）。
- 禁止将本目录任何文件复制到 `src/`、`packages/` 或服务器。
- 禁止以本目录代码作为 DS07 实现依据。

## 本目录文件清单

- `install_domestic_futures_ds07_update.ps1` — 安装脚本（含 ALIGN_TURN 强制标记校验）
- `src/quant/ds07.py` — 含 ALIGN_TURN 并轨的旧 DS07 实现
- `src/backtest_ds07.py` — 配套回测脚本
- `src/plot_ds07_sandbox.py` — 配套沙盒图脚本

## 处置记录

- 2026-08-13：经用户裁决（以权威源代码为准，仅延续）标注本目录废弃，仅保留历史存档；未删除任何文件。
- 删除/归档本目录需用户明确授权（遵守项目"禁止删除未知文件"规则）。
