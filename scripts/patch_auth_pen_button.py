"""登录页：将 AuthCard 内「登录」按钮包一层居中行（不重建整屏）。"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"
BTN_ID = "rsjYe"


def walk(node: object, parent: dict | list | None, key: int | str | None) -> bool:
    if isinstance(node, dict):
        if node.get("id") == BTN_ID and isinstance(parent, list) and isinstance(key, int):
            wrapper = {
                "type": "frame",
                "id": "authSubmitRow",
                "name": "SubmitRow",
                "width": "fill_container",
                "layout": "horizontal",
                "justifyContent": "center",
                "alignItems": "center",
                "children": [copy.deepcopy(node)],
            }
            parent[key] = wrapper
            return True
        for k, v in list(node.items()):
            if walk(v, node, k):
                return True
    elif isinstance(node, list):
        for i, item in enumerate(node):
            if walk(item, node, i):
                return True
    return False


def main() -> int:
    data = json.loads(PEN.read_text(encoding="utf-8"))
    if not walk(data, None, None):
        print(f"Button id {BTN_ID} not found; skip")
        return 1
    PEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Centered login button in {PEN.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
