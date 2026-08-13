"""只更新 FJLHXM-UI.pen 标准/专业订阅卡说明文字，不重建免费卡。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"

REPLACEMENTS = {
    "4、最多 20 个自选": "4、回测与监测共享名额，全库任选最多 20 个品种",
    "5、限 8 个订阅品种池": "5、满额后需先移除已有品种，再添加新品种",
    "4、最多 50 个自选": "4、回测与监测共享名额，全库任选最多 50 个品种",
    "5、全品种池，CSV 导出等": "5、回测支持导出 CSV、查看同类历史成交、按信号强弱筛选",
}


def walk(node: object) -> int:
    n = 0
    if isinstance(node, dict):
        if node.get("type") == "text" and node.get("content") in REPLACEMENTS:
            node["content"] = REPLACEMENTS[node["content"]]
            n += 1
        for v in node.values():
            n += walk(v)
    elif isinstance(node, list):
        for item in node:
            n += walk(item)
    return n


def main() -> int:
    data = json.loads(PEN.read_text(encoding="utf-8"))
    count = walk(data)
    PEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Patched {count} text node(s) in {PEN.name} (standard/pro only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
