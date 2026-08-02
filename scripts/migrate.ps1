$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  throw "Python environment is missing. Run .\scripts\setup.ps1 first."
}

& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
  throw "Database migration failed with exit code $LASTEXITCODE"
}
