$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  throw "Python environment is missing. Run .\scripts\setup.ps1 first."
}

function Invoke-CheckedPython {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
  & $python @Arguments
  if ($LASTEXITCODE -ne 0) { throw "Python check failed with exit code $LASTEXITCODE" }
}

function Invoke-Pnpm {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
  $pnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
  if ($pnpmCommand) { & $pnpmCommand.Source @Arguments } else { & corepack pnpm @Arguments }
  if ($LASTEXITCODE -ne 0) { throw "pnpm check failed with exit code $LASTEXITCODE" }
}

Invoke-CheckedPython @("-m", "ruff", "check", "python", "services", "tests", "scripts")
Invoke-CheckedPython @("-m", "ruff", "format", "--check", "python", "services", "tests", "scripts")
Invoke-CheckedPython @("-m", "mypy", "python", "services")
Invoke-CheckedPython @("-m", "pytest", "--cov", "--cov-report=term-missing", "--cov-fail-under=80")
Invoke-CheckedPython scripts/generate_openapi.py --check
Invoke-Pnpm check:web
Invoke-Pnpm format:check
Invoke-CheckedPython scripts/credential_scan.py
