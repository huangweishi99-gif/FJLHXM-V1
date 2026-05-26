$ErrorActionPreference = "Stop"

$PythonCandidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "python",
    "py"
)

$Python = $null
foreach ($Candidate in $PythonCandidates) {
    try {
        if ($Candidate -eq "python" -or $Candidate -eq "py") {
            $Command = Get-Command $Candidate -ErrorAction Stop
            $Python = $Command.Source
        }
        elseif (Test-Path -LiteralPath $Candidate) {
            $Python = $Candidate
        }

        if ($Python) {
            break
        }
    }
    catch {
        $Python = $null
    }
}

if (-not $Python) {
    throw "Python was not found. Install Python 3.12 or add python.exe to PATH."
}

& $Python .\src\backtest_ds05.py --csv .\data\sample_ohlcv.csv --out-dir .\results\ds05_sample

