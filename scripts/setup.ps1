param(
  [switch]$SkipNode,
  [switch]$SkipPython
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Invoke-Pnpm {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
  $pnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
  if ($pnpmCommand) {
    & $pnpmCommand.Source @Arguments
  } else {
    & corepack pnpm @Arguments
  }
  if ($LASTEXITCODE -ne 0) { throw "pnpm failed with exit code $LASTEXITCODE" }
}

function Resolve-Uv {
  $uvCommand = Get-Command uv.exe -ErrorAction SilentlyContinue
  if ($uvCommand) {
    return $uvCommand.Source
  }
  $candidates = @(
    (Join-Path $env:APPDATA "Python\Python312\Scripts\uv.exe"),
    (Join-Path $env:APPDATA "Python\Python313\Scripts\uv.exe"),
    (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\Scripts\uv.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\Scripts\uv.exe")
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }
  return $null
}

function Invoke-Uv {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
  $uvExecutable = Resolve-Uv
  if (-not $uvExecutable) { throw "Install Python 3.12 and uv 0.12.1 first." }
  & $uvExecutable @Arguments
  if ($LASTEXITCODE -ne 0) { throw "uv failed with exit code $LASTEXITCODE" }
}

if (-not $SkipNode) {
  Invoke-Pnpm install --frozen-lockfile
}

if (-not $SkipPython) {
  $uvExecutable = Resolve-Uv
  if (-not $uvExecutable) {
    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCommand) {
      & $pyCommand.Source -m pip install --user uv==0.12.1
    } else {
      $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
      if (-not $pythonCommand) { throw "Install Python 3.12 or 3.13 before running setup." }
      & $pythonCommand.Source -m pip install --user uv==0.12.1
    }
    if ($LASTEXITCODE -ne 0) { throw "uv installation failed with exit code $LASTEXITCODE" }
  }
  Invoke-Uv sync --frozen --all-extras
}

if (-not (Test-Path -LiteralPath ".env")) {
  Copy-Item -LiteralPath ".env.example" -Destination ".env"
  Write-Host "Created .env from .env.example. Add provider credentials only when needed."
}

Write-Host "SIRA + SEIL dependencies are ready."
