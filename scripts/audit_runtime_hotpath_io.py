"""防回归审计：挂单监控热路径 IO 模式（尾读 CSV + HTTP 连接复用 + 数据泵告警）。

背景：挂单监控（海外 5s / 国内 5s）每轮都要读行情 CSV 与抓取价格/发飞书通知。
此前优化把全量 ``pd.read_csv`` 换成「尾部窗口读取 + 全量回退」、把裸
``requests.get/post`` 换成带连接池的 ``requests.Session``，并为海外数据泵加了
单品种重试、轮次汇总与连续失败告警。若未来有人改回旧写法，本脚本应 FAIL 提醒。

运行：python scripts/audit_runtime_hotpath_io.py
退出码：0=通过；1=存在违规（每行打印一条 [FAIL]）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "packages" / "fengji_core" / "fengji_core"


def load_text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def run_checks() -> list[str]:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        if not ok:
            failures.append(f"{label}: {detail or 'expectation not met'}")

    # 1. 尾读模块存在且带应急开关
    tail_text = ""
    tail_path = CORE_DIR / "tail_csv.py"
    if tail_path.exists():
        tail_text = tail_path.read_text(encoding="utf-8")
    check("tail_csv.module", tail_path.exists(), "missing fengji_core/tail_csv.py")
    check("tail_csv.reader", "def read_csv_tail" in tail_text)
    check("tail_csv.kill_switch", "FENGJI_TAIL_READ_BYTES" in tail_text, "env kill switch removed")

    # 2. stop_bar_monitor 优先尾读（保留全量回退）
    sbm = load_text("packages/fengji_core/fengji_core/stop_bar_monitor.py")
    check(
        "stop_bar_monitor.import",
        "read_csv_tail" in sbm,
        "tail_csv import missing in stop_bar_monitor",
    )
    check(
        "stop_bar_monitor.read_price_frame",
        "def read_price_frame" in sbm,
        "read_price_frame helper removed",
    )
    check(
        "stop_bar_monitor.latest_bar_tail_first",
        "frame = read_price_frame(path)" in sbm,
        "read_latest_bar no longer goes through read_price_frame",
    )

    # 3. 国内期货挂单监控复用共享读取，不再自带全量 pd.read_csv 路径
    fpm = load_text("src/fengji_futures_pending_order_monitor.py")
    check(
        "futures_monitor.reuse",
        "from fengji_core.stop_bar_monitor import read_price_frame" in fpm,
        "futures monitor not reusing shared read_price_frame",
    )
    # 其 read_latest_bar 函数体内不允许再出现 pd.read_csv
    import ast

    try:
        tree = ast.parse(fpm)
        seen_full_read = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "read_latest_bar":
                for sub in ast.walk(node):
                    if (
                        isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "read_csv"
                        and isinstance(sub.func.value, ast.Attribute)
                        and sub.func.value.attr == "pd"
                    ):
                        seen_full_read = True
        check("futures_monitor.no_full_csv", not seen_full_read, "read_latest_bar still calls pd.read_csv")
    except SyntaxError:
        check("futures_monitor.ast", False, "cannot parse futures monitor")

    # 4. 海外挂单监控用 Session 复用，禁裸 requests.get/post
    pom = load_text("src/fengji_pending_order_monitor.py")
    check("pending_monitor.session_fn", "def http_session" in pom)
    check("pending_monitor.reset_fn", "def reset_http_session" in pom)
    try:
        tree = ast.parse(pom)
        bare_calls = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"get", "post"}
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "requests"
            ):
                bare_calls.append(node.lineno)
        check("pending_monitor.no_bare_requests", not bare_calls, f"bare requests.get/post at lines {bare_calls}")
    except SyntaxError:
        check("pending_monitor.ast", False, "cannot parse pending monitor")

    # 5. 海外数据泵：重试 + 汇总 + 连续失败告警
    dm = load_text("data_manager.py")
    for key, label in [
        ("def sync_one_symbol", "data_pump.retry_fn"),
        ("MAX_SYMBOL_RETRIES", "data_pump.retry_const"),
        ("def evaluate_failure_alert", "data_pump.alert_fn"),
        ("[SUMMARY]", "data_pump.summary_line"),
        ("[ALERT]", "data_pump.alert_line"),
    ]:
        check(label, key in dm, f"{key!r} missing in data_manager.py")

    # 6. 国内天勤泵：heartbeat + 失败计数（只读复核）
    dmf = load_text("data_manager_futures.py")
    check("futures_pump.heartbeat", "write_heartbeat" in dmf)
    check("futures_pump.ok_fail", "success_count, fail_count" in dmf)

    # 7. 两端挂单监控：锁外 paper_state 每轮只整读一次（planning 复用 discovery 快照）
    for label, src, mod in [
        ("overseas_monitor.snapshot_single_read", pom, "src/fengji_pending_order_monitor.py"),
        ("futures_monitor.snapshot_single_read", fpm, "src/fengji_futures_pending_order_monitor.py"),
    ]:
        check(
            f"{label}.reuse",
            "planning_snapshot = discovery_snapshot" in src,
            f"{mod}: planning 仍各自整读 paper_state（应为 planning_snapshot = discovery_snapshot）",
        )
        check(
            f"{label}.no_second_lockfree_load",
            "planning_snapshot = load_json(" not in src,
            f"{mod}: planning 再次整读同一 paper_state 文件",
        )

    # 8. 日志截尾工具契约（watchdog 磁盘增长防护的共享实现）
    rot_text = ""
    rot_path = ROOT / "scripts" / "rotate_log_tail.py"
    if rot_path.exists():
        rot_text = rot_path.read_text(encoding="utf-8")
    check("rotate_log_tail.module", bool(rot_text), "missing scripts/rotate_log_tail.py")
    check("rotate_log_tail.fn", "def rotate_log_tail" in rot_text)
    check(
        "rotate_log_tail.inplace",
        "os.replace(" not in rot_text and "truncate" in rot_text,
        "rotate must truncate in place: os.replace detaches live writers on Linux "
        "and fails under cmd >> redirection on Windows",
    )
    check("rotate_log_tail.keep_bytes", "--keep-bytes" in rot_text)

    # 9. 两端 watchdog 均已接入日志截尾
    wd_sh = load_text("scripts/watchdog_overseas.sh")
    wd_ps = load_text("scripts/watchdog_domestic.ps1")
    check("watchdog_overseas.rotate", "rotate_log_tail.py" in wd_sh)
    check("watchdog_domestic.rotate", "rotate_log_tail.py" in wd_ps)

    # 10. OS 状态热路径：单份 1d 状态文件 14MB、解析后常驻约 40MB
    #     - 允许并保留「内容不变不回写」（省下每轮每持仓十余 MB 的写盘）
    #     - 禁止引入进程内大对象缓存：监控每轮按序扫描多个持仓状态文件，属于
    #       LRU 命中率极低的「循环扫描」模式，且内存随持仓数线性膨胀、不可控。
    oss_text = ""
    oss_path = CORE_DIR / "os_state_store.py"
    if oss_path.exists():
        oss_text = oss_path.read_text(encoding="utf-8")
    check("os_state_store.module", bool(oss_text), "missing fengji_core/os_state_store.py")
    check(
        "os_state_store.skip_rewrite",
        "previous_state" in oss_text and "_states_equal" in oss_text,
        "write_os_state no longer skips identical-content rewrite",
    )
    check(
        "os_state_store.no_big_object_cache",
        "_OS_STATE_CACHE" not in oss_text,
        "in-process os_state cache reintroduced (~40MB/entry, low hit rate on cyclic scan)",
    )

    return failures


def main() -> int:
    failures = run_checks()
    if failures:
        for item in failures:
            print(f"[FAIL] {item}", flush=True)
        print(f"audit_runtime_hotpath_io: {len(failures)} violation(s)", flush=True)
        return 1
    print("audit_runtime_hotpath_io: all hot-path IO expectations met", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
