#!/usr/bin/env python3
"""Ops round r8: domestic + overseas + new10 crypto pipeline checks."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW10 = {
    "XRPUSDT",
    "HYPEUSDT",
    "ATHUSDT",
    "PEPEUSDT",
    "ARBUSDT",
    "OPUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "INJUSDT",
    "WLDUSDT",
}


def ssh(host: str, cmd: str, *, timeout: int = 90) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=25", host, cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    out: dict = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "checks": {}}

    # Overseas new10 pipeline (upload tiny checker to avoid shell quoting)
    checker = ROOT / "scripts" / "_tmp_new10_pipeline_check.py"
    checker.write_text(
        f"""import json
from pathlib import Path
root = Path('/home/ubuntu/quant_crypto')
syms = set({sorted(NEW10)!r})
po = json.loads((root/'runtime/fengji_pending_orders/pending_orders.json').read_text())
rows = [r for r in po if r.get('symbol') in syms]
active = [r for r in rows if r.get('status') in ('ACTIVE','READY_TRIGGERED')]
ps = json.loads((root/'runtime/fengji_paper/state.json').read_text())
paper_syms = [k for k in ps.get('symbols', {{}}) if k in syms]
open_positions = []
for k, v in ps.get('symbols', {{}}).items():
    if k not in syms:
        continue
    op = v.get('open_position')
    if op:
        open_positions.append({{
            'symbol': k,
            'strategy_id': op.get('strategy_id'),
            'side': op.get('direction'),
            'entry_time': op.get('entry_time'),
            'entry_price': op.get('entry_price'),
            'order_id': op.get('order_id'),
        }})
st = json.loads((root/'runtime/fengji_pending_orders/state.json').read_text())
fills_new10 = [f for f in st.get('fills', []) if f.get('symbol') in syms]
print(json.dumps({{
    'pending_total': len(rows),
    'pending_active': len(active),
    'pending_sample': [{{k: r.get(k) for k in ('symbol','strategy_id','status','side')}} for r in rows[:8]],
    'paper_symbol_keys': paper_syms,
    'open_positions_new10': open_positions,
    'monitor_fills_new10': len(fills_new10),
    'fill_sample': [{{k: f.get(k) for k in ('symbol','strategy_id','side','time','fill_price','order_id')}} for f in fills_new10[-5:]],
}}, ensure_ascii=False))
""",
        encoding="utf-8",
    )
    subprocess.run(
        ["scp", "-o", "BatchMode=yes", str(checker), "overseas-quant:/home/ubuntu/quant_crypto/runtime/_tmp_new10_pipeline_check.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    rc, stdout, stderr = ssh(
        "overseas-quant",
        "cd /home/ubuntu/quant_crypto && .venv/bin/python runtime/_tmp_new10_pipeline_check.py",
    )
    out["checks"]["overseas_new10"] = {"rc": rc, "stdout": stdout.strip(), "stderr": stderr.strip()}
    if rc == 0 and stdout.strip():
        try:
            out["checks"]["overseas_new10"]["parsed"] = json.loads(stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            pass

    # Overseas OKX + watchdog
    rc2, stdout2, stderr2 = ssh(
        "overseas-quant",
        "cd /home/ubuntu/quant_crypto && "
        "(test -f runtime/watchdog/okx_15m.last && cat runtime/watchdog/okx_15m.last || echo no_okx_last) && "
        "tail -2 runtime/logs/watchdog.log 2>/dev/null || true",
        timeout=30,
    )
    out["checks"]["overseas_okx_watchdog"] = {"rc": rc2, "stdout": stdout2.strip(), "stderr": stderr2.strip()}

    rc_okx, stdout_okx, stderr_okx = ssh(
        "overseas-quant",
        "cd /home/ubuntu/quant_crypto && .venv/bin/python scripts/check_okx_csv_freshness.py --root /home/ubuntu/quant_crypto",
        timeout=45,
    )
    out["checks"]["overseas_okx_freshness"] = {
        "rc": rc_okx,
        "stdout": stdout_okx.strip(),
        "stderr": stderr_okx.strip(),
    }

    rc_dedup, stdout_dedup, stderr_dedup = ssh(
        "overseas-quant",
        "cd /home/ubuntu/quant_crypto && .venv/bin/python scripts/check_ds09_feishu_dedup_state.py --root /home/ubuntu/quant_crypto",
        timeout=30,
    )
    out["checks"]["overseas_ds09_feishu_dedup"] = {
        "rc": rc_dedup,
        "stdout": stdout_dedup.strip(),
        "stderr": stderr_dedup.strip(),
    }
    if rc_dedup == 0 and stdout_dedup.strip():
        try:
            out["checks"]["overseas_ds09_feishu_dedup"]["parsed"] = json.loads(stdout_dedup.strip().splitlines()[-1])
        except json.JSONDecodeError:
            pass

    # Domestic status script
    rc3, stdout3, stderr3 = ssh(
        "domestic-quant",
        r'powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Administrator\quant_futures\scripts\check_domestic_status.ps1',
        timeout=120,
    )
    out["checks"]["domestic_status"] = {"rc": rc3, "stdout": stdout3.strip(), "stderr": stderr3.strip()}

    # Domestic pending monitor count
    if rc3 != 0:
        rc4, stdout4, stderr4 = ssh(
            "domestic-quant",
            r'powershell -NoProfile -Command "Set-Location C:\Users\Administrator\quant_futures; '
            r"$dm=(Get-CimInstance Win32_Process|?{$_.CommandLine -match 'data_manager_futures'}).Count; "
            r"$rad=(Get-Item runtime\fengji_radar\radar.json).LastWriteTime; "
            r"$pend=(Get-Item runtime\fengji_pending_orders\pending_orders.json).LastWriteTime; "
            r"Write-Output \"dm=$dm radar=$rad pending=$pend\"",
            timeout=60,
        )
        out["checks"]["domestic_fallback"] = {"rc": rc4, "stdout": stdout4.strip(), "stderr": stderr4.strip()}

    result_dir = ROOT / "results" / "ops_round_20260618_r8"
    result_dir.mkdir(parents=True, exist_ok=True)
    json_path = result_dir / "remote_checks.json"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"saved {json_path}")
    return 0 if out["checks"].get("domestic_status", {}).get("rc") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
