$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'dev-env.ps1')
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskRuff = Join-Path $taskRoot '.venv\Scripts\ruff.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Önce README kurulum adımlarını çalıştırın.' }
Push-Location $taskRoot
try {
    & $taskRuff check .
    if ($LASTEXITCODE -ne 0) { throw 'Lint başarısız.' }
    & $taskPython -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Testler başarısız.' }
    & $taskPython -m pcbai doctor
    if ($LASTEXITCODE -ne 0) { throw 'Ortam denetimi başarısız.' }
}
finally { Pop-Location }
