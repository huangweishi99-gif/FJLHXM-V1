"""登录页：Tab 行与底部链接居中（FJLHXM-UI.pen）。"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"
AUTH_TABS_ID = "BJhEL"
FOOT_TEXT_ID = "AskPN"


def walk(node: object, parent: list | None = None, index: int | None = None) -> None:
    if isinstance(node, dict):
        if node.get("id") == AUTH_TABS_ID:
            node["layout"] = "horizontal"
            node["justifyContent"] = "center"
            node["alignItems"] = "center"
        for v in node.values():
            if isinstance(v, (dict, list)):
                walk(v)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            if isinstance(item, dict) and item.get("id") == FOOT_TEXT_ID:
                foot = copy.deepcopy(item)
                foot["width"] = "fill_container"
                foot["textAlign"] = "center"
                node[i] = {
                    "type": "frame",
                    "id": "authFootRow",
                    "name": "FootRow",
                    "width": "fill_container",
                    "layout": "horizontal",
                    "justifyContent": "center",
                    "alignItems": "center",
                    "children": [foot],
                }
            elif isinstance(item, (dict, list)):
                walk(item)


def main() -> int:
    data = json.loads(PEN.read_text(encoding="utf-8"))
    walk(data)
    PEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Centered auth tabs + footer in {PEN.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
