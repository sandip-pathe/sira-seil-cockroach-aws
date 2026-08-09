param(
  [Parameter(Position = 0, Mandatory = $true)]
  [ValidateSet("up", "doctor", "reset", "down")]
  [string]$Command,
  [switch]$Contract,
  [string]$Artifacts = ".artifacts/k0"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$runtimeCompose = Join-Path $repoRoot "infra/datahub/k0/compose.runtime.yaml"
$authCompose = Join-Path $repoRoot "infra/datahub/k0/compose.auth.yaml"
$quickstartRoot = Join-Path $env:USERPROFILE ".datahub/quickstart"
$quickstartCompose = Join-Path $quickstartRoot "docker-compose.yml"
$quickstartSecrets = Join-Path $quickstartRoot ".local-secrets.env"
$artifactRoot = Join-Path $repoRoot $Artifacts
$env:PYTHONUTF8 = "1"

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )
  $output = & $Executable @Arguments
  $exitCode = $LASTEXITCODE
  if ($output) {
    $output | ForEach-Object { Write-Host $_ }
  }
  if ($exitCode -ne 0) {
    throw "$Executable failed with exit code $exitCode"
  }
}

function Test-DataHubHealthy {
  try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080/health" -UseBasicParsing -TimeoutSec 5
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

function Set-RuntimeDigests {
  $adapterA = (docker image inspect sira-proof-adapter-a:k0 | ConvertFrom-Json)[0].Id
  $adapterB = (docker image inspect sira-proof-adapter-b:k0 | ConvertFrom-Json)[0].Id
  if (-not $adapterA -or -not $adapterB) { throw "K0 adapter images are missing" }
  $env:ADAPTER_A_DIGEST = $adapterA
  $env:ADAPTER_B_DIGEST = $adapterB
  return @{ adapterA = $adapterA; adapterB = $adapterB }
}

function Enable-DataHubAuthentication {
  $gmsContainer = "datahub-datahub-gms-quickstart-1"
  $configured = docker inspect --format "{{range .Config.Env}}{{println .}}{{end}}" $gmsContainer 2>$null
  if ($LASTEXITCODE -eq 0 -and $configured -contains "METADATA_SERVICE_AUTH_ENABLED=true") {
    return
  }
  if (-not (Test-Path -LiteralPath $quickstartCompose) -or -not (Test-Path -LiteralPath $quickstartSecrets)) {
    throw "DataHub quickstart configuration is missing"
  }
  $env:DATAHUB_VERSION = "v1.7.0"
  $env:UI_INGESTION_DEFAULT_CLI_VERSION = "1.7.0"
  Invoke-Checked -Executable "docker" -Arguments @(
    "compose", "--env-file", $quickstartSecrets,
    "-f", $quickstartCompose, "-f", $authCompose,
    "up", "-d", "--force-recreate", "datahub-gms-quickstart", "frontend-quickstart"
  )
  $deadline = (Get-Date).AddSeconds(90)
  while (-not (Test-DataHubHealthy)) {
    if ((Get-Date) -ge $deadline) { throw "DataHub did not become healthy with authentication enabled" }
    Start-Sleep -Seconds 2
  }
}

function Start-DataHub {
  if (-not (Test-DataHubHealthy)) {
    Invoke-Checked -Executable "uvx" -Arguments @("--python", "3.11", "--from", "acryl-datahub==1.7.0", "datahub", "docker", "quickstart", "--version", "v1.7.0", "--accept-version-default")
  }
  if (-not (Test-Path -LiteralPath "$env:USERPROFILE/.datahubenv")) {
    Invoke-Checked -Executable "uvx" -Arguments @("--python", "3.11", "--from", "acryl-datahub==1.7.0", "datahub", "init", "--username", "datahub", "--password", "datahub")
  }
  Enable-DataHubAuthentication
  if (-not (Test-DataHubHealthy)) { throw "DataHub GMS is not healthy" }
}

function Start-Runtime {
  $env:ADAPTER_A_DIGEST = "build-pending-a"
  $env:ADAPTER_B_DIGEST = "build-pending-b"
  Invoke-Checked -Executable "docker" -Arguments @("compose", "-f", $runtimeCompose, "build")
  $digests = Set-RuntimeDigests
  Invoke-Checked -Executable "docker" -Arguments @("compose", "-f", $runtimeCompose, "up", "-d", "--force-recreate")
  return $digests
}

function Reset-ProofState {
  Invoke-Checked -Executable "uvx" -Arguments @("--python", "3.11", "--from", "acryl-datahub==1.7.0", "datahub", "properties", "upsert", "-f", "infra/datahub/k0/structured-properties.yaml")
  Invoke-Checked -Executable "uv" -Arguments @("run", "--no-project", "--python", "3.11", "--with", "acryl-datahub==1.7.0", "python", "scripts/datahub_k0_seed.py")
  $digests = Set-RuntimeDigests
  Invoke-Checked -Executable "docker" -Arguments @("compose", "-f", $runtimeCompose, "up", "-d", "--force-recreate")
  return $digests
}

function Invoke-Contract {
  New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null
  Enable-DataHubAuthentication
  $digests = Reset-ProofState
  $dataHubArtifact = Join-Path $artifactRoot "datahub-mcp-contract.json"
  & uv run python scripts/datahub_k0_probe.py --quiet --output $dataHubArtifact
  if ($LASTEXITCODE -ne 0) { throw "DataHub MCP contract failed; inspect $dataHubArtifact" }
  $routerJson = & docker compose -f $runtimeCompose exec -T `
    -e ADAPTER_A_DIGEST=$($digests.adapterA) `
    -e ADAPTER_B_DIGEST=$($digests.adapterB) `
    router python /app/router_probe.py
  if ($LASTEXITCODE -ne 0) { throw "Router contract failed" }
  $routerArtifact = Join-Path $artifactRoot "router-contract.json"
  ($routerJson | ConvertFrom-Json) | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $routerArtifact -Encoding utf8
  $runtimeArtifact = Join-Path $artifactRoot "runtime-identities.json"
  @{
    status = "PASS"
    adapterA = $digests.adapterA
    adapterB = $digests.adapterB
    router = (docker image inspect sira-proof-router:k0 | ConvertFrom-Json)[0].Id
  } | ConvertTo-Json | Set-Content -LiteralPath $runtimeArtifact -Encoding utf8
  Write-Output "K0 CONTRACT PASS"
  Write-Output "DataHub: $dataHubArtifact"
  Write-Output "Router: $routerArtifact"
  Write-Output "Runtime: $runtimeArtifact"
}

switch ($Command) {
  "up" {
    Start-DataHub
    $null = Start-Runtime
    Write-Output "K0 services are up"
  }
  "doctor" {
    if (-not (Test-DataHubHealthy)) { throw "DataHub is not healthy. Run: ./scripts/proof.ps1 up" }
    if ($Contract) {
      Invoke-Contract
    } else {
      $running = docker compose -f $runtimeCompose ps --status running --quiet
      if (@($running).Count -ne 3) { throw "K0 runtime is incomplete. Run: ./scripts/proof.ps1 up" }
      Write-Output "K0 READ-ONLY HEALTH PASS"
    }
  }
  "reset" {
    Start-DataHub
    $null = Start-Runtime
    $null = Reset-ProofState
    Write-Output "K0 state restored"
  }
  "down" {
    $env:ADAPTER_A_DIGEST = "down"
    $env:ADAPTER_B_DIGEST = "down"
    Invoke-Checked -Executable "docker" -Arguments @("compose", "-f", $runtimeCompose, "down")
    Invoke-Checked -Executable "uvx" -Arguments @("--python", "3.11", "--from", "acryl-datahub==1.7.0", "datahub", "docker", "quickstart", "--stop")
    Write-Output "K0 services are down"
  }
}
