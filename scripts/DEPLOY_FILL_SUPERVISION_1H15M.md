# 国内 fill_supervision 1h/15m 部署（单步，避免卡住）

本机 PowerShell 逐条执行（每条 <30s）：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"

# 1) 只同步一个文件
scp -o BatchMode=yes -o ConnectTimeout=15 `
  packages/fengji_core/fengji_core/fill_supervision.py `
  domestic-quant:C:/Users/Administrator/quant_futures/packages/fengji_core/fengji_core/fill_supervision.py

# 2) 远端复核（invalid_new 应为 0；exit 可能为 1 若仍有 needs_data）
ssh -o BatchMode=yes domestic-quant `
  "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/_tmp_domestic_fill_verify_20260625.ps1"
```

海外哈希（与上分开跑，勿捆一条）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sync_overseas_core_hash_files.ps1
python scripts\compare_overseas_core_hashes.py
```
