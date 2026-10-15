"""只读审计：运行时资产膨胀盘点（大文件 + 长期未写 + 代码零引用 => 疑似可归档）。

背景
----
人工盘点时发现 ``runtime/`` 下存在三个数百 MB 级、合计约 2.1GB 的历史 ``.jsonl``
事件留存：已停止写入两个多月、代码中零引用，属无人认领的诊断残留。这类文件靠人
工排查才会暴露，故固化为可重复运行的审计。

注意：本脚本会检索代码里的文件名引用，**自检时排除自身**，且文档中不罗列具体
待清理文件名——否则会把「被本脚本文档提到」误判为「仍在使用」。

本脚本**只读、绝不删除/移动任何文件**。它只回答三个问题：
1. 哪些文件超过体积阈值（默认 200MB）？
2. 它们多久没被写入了？
3. 代码里还有没有任何地方引用它的文件名（引用 => 仍在使用，不可归档）？

用法::

    python scripts/audit_runtime_asset_bloat.py                  # 盘点并打印
    python scripts/audit_runtime_asset_bloat.py --json out.json  # 同时导出 JSON
    python scripts/audit_runtime_asset_bloat.py --fail-on-stale  # 存在疑似可归档文件时退出码 1

退出码：0=无问题（或仅报告）；1=``--fail-on-stale`` 且存在疑似可归档文件；2=参数/扫描异常。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SCAN_DIRS = ("runtime", "data", "results", "archives")
CODE_SUFFIXES = (".py", ".ps1", ".sh")
CODE_DIRS = ("src", "scripts", "packages", "services")
DEFAULT_MIN_MB = 200.0
DEFAULT_STALE_DAYS = 14


def iter_files(root: Path, dirs: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for name in dirs:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                out.append(path)
    return out


def collect_code_text(root: Path, exclude: set[Path] | None = None) -> str:
    """拼接代码文件内容，用于「文件名是否被引用」的粗筛（只读，跳过数据与产物目录）。

    ``exclude`` 用于排除本脚本自身，避免「文档里提到过某文件名」被当成仍在引用。
    """
    skip = {path.resolve() for path in (exclude or set())}
    chunks: list[str] = []
    for name in CODE_DIRS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CODE_SUFFIXES:
                continue
            try:
                if path.resolve() in skip:
                    continue
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return "\n".join(chunks)


def scan_assets(
    root: Path,
    *,
    min_mb: float = DEFAULT_MIN_MB,
    stale_days: int = DEFAULT_STALE_DAYS,
    dirs: tuple[str, ...] = SCAN_DIRS,
    now: float | None = None,
) -> list[dict[str, object]]:
    """返回超过阈值的资产清单（按体积降序），每项含 stale 判定所需字段。"""
    if now is None:
        now = time.time()
    threshold = max(0.0, float(min_mb)) * 1024 * 1024
    findings: list[dict[str, object]] = []
    candidates: list[tuple[Path, object]] = []
    for path in iter_files(root, dirs):
        stat = _safe_stat(path)
        if stat is not None and stat.st_size >= threshold:
            candidates.append((path, stat))
    if not candidates:
        return []
    code_text = collect_code_text(root, exclude={Path(__file__).resolve()})
    for path, stat in candidates:
        age_days = max(0.0, (now - stat.st_mtime) / 86400.0)
        referenced = path.name in code_text
        findings.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_mb": round(stat.st_size / (1024 * 1024), 1),
                "last_write": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                "age_days": round(age_days, 1),
                "referenced_in_code": referenced,
                "stale": (not referenced) and age_days >= float(stale_days),
            }
        )
    findings.sort(key=lambda item: float(item["size_mb"]), reverse=True)
    return findings


def _safe_stat(path: Path):
    try:
        return path.stat()
    except OSError:
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    parser.add_argument("--min-mb", type=float, default=DEFAULT_MIN_MB, help="体积阈值 MB（默认 200）")
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS, help="未写入天数阈值（默认 14）")
    parser.add_argument("--dirs", default=",".join(SCAN_DIRS), help="扫描目录（逗号分隔）")
    parser.add_argument("--json", dest="json_out", default="", help="额外导出 JSON 报告到该路径")
    parser.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="存在「超阈值 + 长期未写 + 代码零引用」的文件时退出码为 1",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"[audit_asset_bloat] root not found: {root}", flush=True)
        return 2
    dirs = tuple(part.strip() for part in str(args.dirs).split(",") if part.strip())
    findings = scan_assets(root, min_mb=args.min_mb, stale_days=args.stale_days, dirs=dirs)
    stale = [item for item in findings if bool(item["stale"])]

    if not findings:
        print(f"audit_runtime_asset_bloat: no file >= {args.min_mb}MB under {', '.join(dirs)}", flush=True)
        return 0

    print(f"audit_runtime_asset_bloat: {len(findings)} file(s) >= {args.min_mb}MB", flush=True)
    for item in findings:
        flag = "STALE" if item["stale"] else ("referenced" if item["referenced_in_code"] else "recent")
        print(
            f"  {item['size_mb']:>8.1f}MB  age={item['age_days']:>6.1f}d  {flag:<10} {item['path']}",
            flush=True,
        )

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "root": str(root),
                    "min_mb": args.min_mb,
                    "stale_days": args.stale_days,
                    "findings": findings,
                    "stale_count": len(stale),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[audit_asset_bloat] json report -> {out_path}", flush=True)

    if args.fail_on_stale and stale:
        print(f"audit_runtime_asset_bloat: {len(stale)} stale candidate(s) need manual archive/cleanup", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
