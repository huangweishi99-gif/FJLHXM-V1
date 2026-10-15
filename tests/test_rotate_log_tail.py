"""行为测试：scripts/rotate_log_tail.py（watchdog 日志增长防护的共享工具）。"""
from __future__ import annotations

from pathlib import Path

from scripts.rotate_log_tail import _bounded_tail, main, rotate_log_tail


def test_bounded_tail_drops_partial_first_line() -> None:
    raw = b"line0\nline1\nline2\nline3\n"
    out = _bounded_tail(raw, keep_bytes=9)
    assert out
    text = out.decode()
    # 不允许出现半行（每个非空字节行都必须完整出现在原始内容中）
    for line in text.split("\n"):
        if line:
            assert (line + "\n") in raw.decode()


def test_rotate_log_tail_truncates_oversized_to_tail(tmp_path: Path) -> None:
    original = b"0123456789\n" * 4000  # 44000 bytes
    path = tmp_path / "big.log"
    path.write_bytes(original)

    rotated = rotate_log_tail(path, max_bytes=20_000, keep_bytes=8_000)

    assert rotated is True
    out = path.read_bytes()
    # 内容必须是原文件的一个后缀（保留尾部，绝无内容重排/拼接）
    assert original.endswith(out)
    # 保留字节数上限 + 单行余量
    assert len(out) <= 8_000 + len(b"0123456789\n")
    # 首行必须完整
    assert out.startswith(b"0123456789\n")


def test_rotate_log_tail_single_long_line_no_newline(tmp_path: Path) -> None:
    original = b"x" * 50_000
    path = tmp_path / "one.log"
    path.write_bytes(original)

    rotated = rotate_log_tail(path, max_bytes=10_000, keep_bytes=5_000)

    assert rotated is True
    out = path.read_bytes()
    assert len(out) <= 5_000
    assert original.endswith(out)


def test_rotate_log_tail_keeps_same_inode(tmp_path: Path) -> None:
    """原地截断契约：不换 inode，活跃 writer 的句柄无感知（防退回 os.replace 方案）。"""
    original = b"0123456789\n" * 4000
    path = tmp_path / "big.log"
    path.write_bytes(original)
    ino_before = path.stat().st_ino

    rotated = rotate_log_tail(path, max_bytes=20_000, keep_bytes=8_000)

    assert rotated is True
    assert path.stat().st_ino == ino_before
    assert original.endswith(path.read_bytes())


def test_rotate_log_tail_leaves_undersized_file_untouched(tmp_path: Path) -> None:
    path = tmp_path / "small.log"
    path.write_bytes(b"0123456789\n" * 5)

    rotated = rotate_log_tail(path, max_bytes=10_000, keep_bytes=1_000)

    assert rotated is False
    assert path.read_bytes() == b"0123456789\n" * 5


def test_rotate_log_tail_missing_path_returns_false(tmp_path: Path) -> None:
    assert rotate_log_tail(tmp_path / "nope.log", max_bytes=10, keep_bytes=5) is False


def test_main_rotates_multiple_files_and_prints(tmp_path: Path, capsys) -> None:
    big = tmp_path / "multi.log"
    big.write_bytes(b"a\n" * 20_000)
    other = tmp_path / "other.log"
    other.write_bytes(b"b\n" * 20_000)
    tiny = tmp_path / "tiny.log"
    tiny.write_bytes(b"tiny")

    code = main(["--max-bytes", "5_000", "--keep-bytes", "2_000", str(big), str(other), str(tiny)])

    assert code == 0
    captured = capsys.readouterr().out
    assert "truncated" in captured and "truncated" in captured
    assert b"a\n" * 20_000 != big.read_bytes()  # 已截断
    assert tiny.read_bytes() == b"tiny"  # 未超限不动
