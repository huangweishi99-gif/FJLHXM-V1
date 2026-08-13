#!/usr/bin/env python3
"""Wave 4 S3: render DS02/DS06/DS08 engineering ruling backlog."""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "wave4_s3_ds020608_ruling_2026-06-11.md"


def run_pytest(expr: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *expr.split(), "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    return tail[-1] if tail else f"exit={proc.returncode}"


def main() -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t_ds06_ds08 = run_pytest("tests/test_radar_ds06.py tests/test_radar_ds08.py tests/test_pending_orders.py -k ds06 or ds08")
    t_fill = run_pytest("tests/test_fill_supervision.py")

    lines = [
        "# Wave 4 S3 · DS02/06/08 裁定（2026-06-11）",
        "",
        f"生成时间：{now}",
        "",
        "> 依据：`docs/DS02_CALIBRATION.md`、`docs/DS06_CALIBRATION.md`、`docs/DS08_CALIBRATION.md`、",
        "> `docs/CANONICAL_RULES.md`、`峰极OS_挂单器与模拟实盘说明.md`、当前代码与测试。",
        "",
        "## 验证基线",
        "",
        f"- DS06/DS08 雷达 + pending：`{t_ds06_ds08}`",
        f"- fill_supervision 全量：`{t_fill}`",
        "",
        "---",
        "",
        "## DS02 阴阳相吃",
        "",
        "| 项 | 现状 | 裁定 |",
        "|---|---|---|",
        "| 回测/校准 | `CALIBRATED`；30 期货 `bad_trades=0` | **维持**，N04 后须 spot-check 沙盒（未改 DS02 核心） |",
        "| 总雷达 | `fengji_total_radar.add_shape_watch` → `CONFIRM_ON_CLOSE` 占位 | **维持收线确认**；不得伪装成触价 pending |",
        "| 挂单器 | **不在** `DEFAULT_INCLUDE_STRATEGIES` | **维持**；模拟开仓走 paper monitor「主程序确认」分支 |",
        "| 成交监督 M5 | B 区 33 笔均为 DS01 | DS02 无新增 invalid backlog |",
        "",
        "**后续（非阻塞）**：若需 DS02 挂单价 pending，单独立项 + 沙盒 + `fill_supervision` 扩展；不得顺带改 OS/DS01。",
        "",
        "---",
        "",
        "## DS06 外扩峰",
        "",
        "| 项 | 现状 | 裁定 |",
        "|---|---|---|",
        "| 校准 | `CALIBRATED`；`hardened_fengji_line` + D/E/F 外扩 | **维持** |",
        "| 挂单器 | 在默认集合；与 DS03 **同价同守护点去重** | **维持去重**（`test_ds06_duplicate_of_ds03_same_trigger_is_suppressed`） |",
        "| 独立触发 | 同品种 DS06 触发价 ≠ DS03 时单独导出 | **允许**（`test_ds06_distinct_trigger_is_kept_with_ds03`） |",
        "| 观察 | 生产独立 DS06 案例仍少 | 继续 radar/pending 日志 spot-check；**不**为出案例放宽规则 |",
        "",
        "---",
        "",
        "## DS08 否认确定 / 夺权",
        "",
        "| 项 | 现状 | 裁定 |",
        "|---|---|---|",
        "| 五点骨架 | `hardened_by_bar` 可见物理点 P/V | **继续读物理 hardened 线** |",
        "| identity_line | 仅身份审计，非主折线 | **不得**改为 identity_line 触发（`CANONICAL_RULES` §2） |",
        "| 雷达/挂单 | H1；`add_ds08` + pending 默认集合 | **维持** |",
        "| 成交监督 M2 | `audit_ds08_fill` + setup_key 解析 | **维持**；720h 无 DS08 新 invalid |",
        "",
        "**关闭 backlog 项**：「DS08 是否改读 identity line」→ **否**，以 `docs/DS08_CALIBRATION.md` 为准。",
        "",
        "---",
        "",
        "## 工程入口索引",
        "",
        "| 定式 | 核心 | 雷达 | 挂单 | 监督 |",
        "|---|---|---|---|---|",
        "| DS02 | `backtest_ds02.py` / `ds02.py` | 占位 watch | 无 pending | — |",
        "| DS06 | `ds06.py` | `add_ds06` | 默认 + DS03 去重 | — |",
        "| DS08 | `ds08.py` | `add_ds08` | 默认 | `audit_ds08_fill` |",
        "",
        "## 剩余动作（可选）",
        "",
        "1. N04 后 DS02 沙盒 spot-check 1 笔（如橡胶样本）",
        "2. 积累 1 笔 **独立触发价** DS06 pending 截图归档",
        "3. S2 续：B 区其余 DS01 品种点名出图",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"ruling -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
