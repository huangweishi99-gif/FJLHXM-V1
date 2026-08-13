"""只追加 FJLHXM-UI.pen 第 8 屏「交流群」，并为各屏导航补「交流群」链接；不重建订阅/登录等屏。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"
SCRIPTS = ROOT / "scripts"


def _load_build():
    spec = importlib.util.spec_from_file_location("build_fjlhxm_ui_pen", SCRIPTS / "build_fjlhxm_ui_pen.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _nav_labels(links_node: dict) -> list[str]:
    return [
        c.get("content", "")
        for c in links_node.get("children", [])
        if c.get("type") == "text"
    ]


def patch_nav_links(node: object, build_mod) -> int:
    n = 0
    if isinstance(node, dict):
        if node.get("name") == "Links" and node.get("type") == "frame":
            labels = _nav_labels(node)
            if labels and "交流群" not in labels:
                node["width"] = "fit_content(440)"
                if node.get("gap", 28) > 24:
                    node["gap"] = 22
                node.setdefault("children", []).append(build_mod.link("交流群", False))
                n += 1
        for v in node.values():
            n += patch_nav_links(v, build_mod)
    elif isinstance(node, list):
        for item in node:
            n += patch_nav_links(item, build_mod)
    return n


def patch_review_note(node: object) -> int:
    n = 0
    if isinstance(node, dict):
        if node.get("type") == "text" and isinstance(node.get("content"), str):
            if "7 屏 · Glass Gold" in node["content"]:
                node["content"] = node["content"].replace(
                    "7 屏 · Glass Gold 风格；含登录注册 · 审阅通过后同步 web/css",
                    "8 屏 · Glass Gold 风格；含登录注册 · 交流群 · 审阅通过后同步 web/css",
                )
                n += 1
        for v in node.values():
            n += patch_review_note(v)
    elif isinstance(node, list):
        for item in node:
            n += patch_review_note(item)
    return n


def main() -> int:
    build = _load_build()
    data = json.loads(PEN.read_text(encoding="utf-8"))
    before = len(data.get("children", []))
    data["children"] = [
        c
        for c in data.get("children", [])
        if "08 · Community" not in str(c.get("name", ""))
    ]
    removed = before - len(data["children"])
    data["children"].append(build.screen_community())
    nav_patched = patch_nav_links(data, build)
    review_patched = patch_review_note(data)
    PEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Patched {PEN.name}: removed {removed} old community frame(s), "
        f"appended 08 · Community, nav_links+={nav_patched}, review_note={review_patched}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
