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

Invoke-CheckedPython -Arguments @("-m", "ruff", "check", "python", "services", "tests", "scripts")
Invoke-CheckedPython -Arguments @("-m", "ruff", "format", "--check", "python", "services", "tests", "scripts")
Invoke-CheckedPython -Arguments @("-m", "mypy", "python", "services")
Invoke-CheckedPython -Arguments @("-m", "pytest", "--cov", "--cov-report=term-missing", "--cov-fail-under=75")
Invoke-CheckedPython -Arguments @("scripts/generate_openapi.py", "--check")
Invoke-Pnpm -Arguments @("check:web")
Invoke-Pnpm -Arguments @("format:check")
Invoke-CheckedPython -Arguments @("scripts/credential_scan.py", "--current-tree-only")
