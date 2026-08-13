"""更新 FJLHXM-UI.pen 第 6 屏标题行：品种详情底对齐、周期 Tab 加大、间距 4 字宽。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"

TAB_SIZE = 16
HEAD_GAP = 52  # 4 × 13px 字宽


def patch_node(node: object, *, in_screen_06: bool = False) -> int:
    n = 0
    if isinstance(node, dict):
        name = str(node.get("name", ""))
        child_in = in_screen_06 or ("06 · Symbol Chart" in name)

        if child_in and name == "Head" and node.get("type") == "frame":
            node["layout"] = "horizontal"
            node["alignItems"] = "end"
            node["gap"] = HEAD_GAP
            node.pop("justifyContent", None)
            n += 1

        if child_in and name == "TitleRow" and node.get("type") == "frame":
            node["alignItems"] = "end"
            n += 1

        if child_in and name == "Tabs" and node.get("type") == "frame":
            node["width"] = "fit_content(220)"
            node["height"] = 38
            node["gap"] = 20
            node["alignItems"] = "end"
            node.pop("justifyContent", None)
            for tab in node.get("children", []):
                if not isinstance(tab, dict):
                    continue
                tab["height"] = 38
                for ch in tab.get("children", []):
                    if isinstance(ch, dict) and ch.get("type") == "text":
                        ch["fontSize"] = TAB_SIZE
                        if ch.get("fontWeight") == "600":
                            ch["fontWeight"] = "600"
                    if isinstance(ch, dict) and ch.get("name") == "Line" and ch.get("width", 0) > 0:
                        ch["width"] = 26
            n += 1

        # 旧结构：TitleRow 包在 L 里时，去掉 L 包裹，Head 直接挂 TitleRow
        if child_in and name == "L" and node.get("type") == "frame":
            kids = node.get("children") or []
            if len(kids) == 1 and kids[0].get("name") == "TitleRow":
                # 标记由 Head 处理；此处仅同步 TitleRow 对齐
                pass

        for v in node.values():
            if isinstance(v, (dict, list)):
                n += patch_node(v, in_screen_06=child_in)
    elif isinstance(node, list):
        for item in node:
            n += patch_node(item, in_screen_06=in_screen_06)
    return n


def main() -> int:
    data = json.loads(PEN.read_text(encoding="utf-8"))
    patched = patch_node(data)
    PEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Patched {patched} layout node(s) in {PEN.name} (screen 06 head)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
