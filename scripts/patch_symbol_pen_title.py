"""只更新 FJLHXM-UI.pen 第 6 屏标题：大号品种代码 + 小号「 · 品种详情」，去掉「峰极量化」。"""
from __future__ import annotations

import json
import random
import string
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"

C_TEXT = "#f5f5f7"
C_TEXT2 = "#a8a8b3"


def _id() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=5))


def _title_row(symbol: str = "BTCUSDT") -> dict:
    return {
        "type": "frame",
        "id": _id(),
        "name": "TitleRow",
        "clip": True,
        "width": "fit_content(360)",
        "height": "fit_content(36)",
        "fill": "transparent",
        "layout": "horizontal",
        "gap": 0,
        "alignItems": "baseline",
        "children": [
            {
                "type": "text",
                "id": _id(),
                "name": "Symbol",
                "fill": C_TEXT,
                "content": symbol,
                "lineHeight": 1.35,
                "fontFamily": "Inter",
                "fontSize": 28,
                "fontWeight": "600",
            },
            {
                "type": "text",
                "id": _id(),
                "name": "Kind",
                "fill": C_TEXT2,
                "content": " · 品种详情",
                "lineHeight": 1.4,
                "fontFamily": "Inter",
                "fontSize": 13,
                "fontWeight": "normal",
            },
        ],
    }


def patch_symbol_head(node: object, *, in_screen_06: bool = False) -> tuple[int, bool]:
    patched = 0
    if isinstance(node, dict):
        name = str(node.get("name", ""))
        if in_screen_06 and name == "L" and node.get("type") == "frame":
            children = node.get("children") or []
            texts = [c for c in children if c.get("type") == "text"]
            symbol = "BTCUSDT"
            for t in texts:
                content = str(t.get("content", ""))
                if " · 品种详情" in content and content != " · 品种详情":
                    symbol = content.split(" · ", 1)[0].strip() or symbol
            if any(t.get("content") == "峰极量化" for t in texts) or any(
                " · 品种详情" in str(t.get("content", "")) for t in texts
            ):
                node["children"] = [_title_row(symbol)]
                node["layout"] = "vertical"
                node["gap"] = 0
                patched += 1
        child_in = in_screen_06 or ("06 · Symbol Chart" in name)
        for v in node.values():
            if isinstance(v, (dict, list)):
                n, _ = patch_symbol_head(v, in_screen_06=child_in)
                patched += n
    elif isinstance(node, list):
        for item in node:
            n, _ = patch_symbol_head(item, in_screen_06=in_screen_06)
            patched += n
    return patched, False


def main() -> int:
    data = json.loads(PEN.read_text(encoding="utf-8"))
    patched, _ = patch_symbol_head(data)
    PEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Patched {patched} symbol title block(s) in {PEN.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
