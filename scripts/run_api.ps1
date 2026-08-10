[CmdletBinding()]
param(
  [string]$ListenHost = "127.0.0.1",
  [ValidateRange(1, 65535)]
  [int]$Port = 8000,
  [string]$DatabaseUrl = "",
  [switch]$Reload
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$sourcePaths = @(
  (Join-Path $root "python"),
  (Join-Path $root "python\agents"),
  (Join-Path $root "services\api"),
  (Join-Path $root "services\worker")
)
$existingPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
if ($existingPythonPath) {
  $sourcePaths += $existingPythonPath
}
$env:PYTHONPATH = $sourcePaths -join [IO.Path]::PathSeparator
if (-not $env:APP_ENV) {
  $env:APP_ENV = "development"
}
if ($DatabaseUrl) {
  $env:DATABASE_URL = $DatabaseUrl
}
elseif (-not $env:DATABASE_URL) {
  # Local development only; matches Compose's restricted, non-owner runtime role.
  $env:DATABASE_URL = "postgresql+asyncpg://sira_runtime:change-me@localhost:5432/sira" # pragma: allowlist secret
}

$arguments = @(
  "run",
  "uvicorn",
  "sira_api.main:app",
  "--host",
  $ListenHost,
  "--port",
  $Port
)
if ($Reload) {
  $arguments += "--reload"
}

Push-Location $root
try {
  & uv @arguments
  exit $LASTEXITCODE
}
finally {
  Pop-Location
}
