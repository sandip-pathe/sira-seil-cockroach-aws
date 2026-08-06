$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  throw "Python environment is missing. Run .\scripts\setup.ps1 first."
}
$env:PYTHONPATH = @(
  (Join-Path $repoRoot "python")
  (Join-Path $repoRoot "python\agents")
  (Join-Path $repoRoot "services\api")
  (Join-Path $repoRoot "services\worker")
) -join [IO.Path]::PathSeparator
& $python -m uvicorn sira_api.main:app --app-dir services/api --host 127.0.0.1 --port 8000 --reload
if ($LASTEXITCODE -ne 0) {
  throw "API process stopped with exit code $LASTEXITCODE"
}
