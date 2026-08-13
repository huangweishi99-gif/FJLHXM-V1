"""Remove obsolete pricing flow notes from FJLHXM-UI.pen standard/pro cards."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"

def patch_foot(node: object, *, in_pricing: bool = False) -> int:
    n = 0
    if isinstance(node, dict):
        name = str(node.get("name", ""))
        child_in = in_pricing or ("05 · Pricing" in name)
        if child_in and name in {"标准", "专业"} and node.get("type") == "frame":
            for ch in node.get("children", []):
                if ch.get("name") == "Foot":
                    kids = ch.get("children", [])
                    filtered = [
                        k
                        for k in kids
                        if not (k.get("type") == "text" and k.get("name") == "FlowNote")
                    ]
                    if len(filtered) != len(kids):
                        ch["height"] = "fit_content(40)"
                        ch["children"] = filtered
                        n += len(kids) - len(filtered)
        for v in node.values():
            if isinstance(v, (dict, list)):
                n += patch_foot(v, in_pricing=child_in)
    elif isinstance(node, list):
        for item in node:
            n += patch_foot(item, in_pricing=in_pricing)
    return n


def main() -> int:
    data = json.loads(PEN.read_text(encoding="utf-8"))
    n = patch_foot(data)
    PEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Removed {n} pricing flow note(s) in {PEN.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
