# Resolve domestic paper entry via UTF-8 manifest (ASCII-only script body for GBK servers)
function Get-DomesticPaperScript {
    param([string]$Root = "C:\Users\Administrator\quant_futures")

    $manifest = Join-Path $PSScriptRoot "domestic_paper_manifest.txt"
    if (Test-Path -LiteralPath $manifest) {
        $name = (Get-Content -LiteralPath $manifest -Encoding UTF8 | Select-Object -First 1).Trim()
        if ($name) {
            $path = Join-Path $Root $name
            if (Test-Path -LiteralPath $path) {
                return (Resolve-Path -LiteralPath $path).Path
            }
        }
    }

    foreach ($py in (Get-ChildItem -LiteralPath $Root -File -Filter "*.py" -ErrorAction SilentlyContinue)) {
        if ($py.Name -like "*01-08*") {
            return $py.FullName
        }
    }

    throw "Domestic paper script not found under $Root (see scripts/domestic_paper_manifest.txt)"
}
