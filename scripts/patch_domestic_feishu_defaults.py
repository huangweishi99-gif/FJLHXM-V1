"""Remove hardcoded Feishu webhook defaults from domestic paper scripts on server."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\quant_futures")
REPLACEMENT = 'DEFAULT_FEISHU_WEBHOOK = os.getenv("FENGJI_FEISHU_WEBHOOK", "") or os.getenv("FEISHU_WEBHOOK", "")'
PATTERN = re.compile(
    r'DEFAULT_FEISHU_WEBHOOK\s*=\s*os\.getenv\(\s*["\']FENGJI_FEISHU_WEBHOOK["\']\s*,\s*["\'][^"\']*["\']\s*\)',
    re.MULTILINE,
)

patched = 0
for path in ROOT.glob("*.py"):
    if "模拟实盘" not in path.name:
        continue
    text = path.read_text(encoding="utf-8")
    if "open.feishu.cn" not in text and "DEFAULT_FEISHU_WEBHOOK" not in text:
        continue
    new_text, n = PATTERN.subn(REPLACEMENT, text)
    if n == 0 and "open.feishu.cn" in text:
        new_text = text.replace(
            '"https://open.feishu.cn/open-apis/bot/v2/hook/',
            '"',
        )
        n = 1 if new_text != text else 0
    if n:
        path.write_text(new_text, encoding="utf-8")
        patched += 1
        print(f"patched: {path.name}")

MAIN_PATCH = """
    if not args.feishu_webhook:
        try:
            from fengji_feishu_config import resolve_feishu_webhook
            args.feishu_webhook = resolve_feishu_webhook(ROOT)
        except Exception:
            pass
"""

for path in ROOT.glob("*.py"):
    if "模拟实盘" not in path.name:
        continue
    text = path.read_text(encoding="utf-8")
    if "resolve_feishu_webhook(ROOT)" in text:
        continue
    marker = "args = parser.parse_args()"
    if marker in text and MAIN_PATCH.strip() not in text:
        text = text.replace(marker, marker + MAIN_PATCH, 1)
        path.write_text(text, encoding="utf-8")
        print(f"main-hook: {path.name}")

print(f"done, files={patched}")
