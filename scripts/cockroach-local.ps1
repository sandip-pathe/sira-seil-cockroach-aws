[CmdletBinding()]
param(
    [ValidateSet("start", "stop", "reset")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$workspacePath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspacePath

if ($Action -eq "stop") {
    docker compose stop cockroach
    exit $LASTEXITCODE
}

docker compose up -d --wait cockroach
docker compose exec -T cockroach cockroach sql --insecure --host=localhost:26257 `
    --execute="SET CLUSTER SETTING feature.vector_index.enabled = true;"
if ($Action -eq "reset") {
    docker compose exec -T cockroach cockroach sql --insecure --host=localhost:26257 `
        --execute="DROP DATABASE IF EXISTS sira CASCADE; CREATE DATABASE sira; CREATE USER IF NOT EXISTS sira_app; CREATE USER IF NOT EXISTS sira_worker_app;"
}
else {
    docker compose exec -T cockroach cockroach sql --insecure --host=localhost:26257 `
        --execute="CREATE DATABASE IF NOT EXISTS sira; CREATE USER IF NOT EXISTS sira_app; CREATE USER IF NOT EXISTS sira_worker_app;"
}

$env:DATABASE_ADMIN_URL = "cockroachdb+psycopg://root@127.0.0.1:26257/sira?sslmode=disable"
$env:DATABASE_URL = "cockroachdb+asyncpg://sira_app@127.0.0.1:26257/sira?ssl=disable"

& "$workspacePath\.venv\Scripts\alembic.exe" upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "Alembic migration failed"
}

docker compose exec -T cockroach cockroach sql --insecure --host=localhost:26257 --database=sira `
    --execute="GRANT CONNECT ON DATABASE sira TO sira_app, sira_worker_app; GRANT sira_runtime TO sira_app, sira_worker_app; GRANT sira_qualification_worker TO sira_worker_app;"
if ($LASTEXITCODE -ne 0) {
    throw "CockroachDB runtime role setup failed"
}

Write-Host "CockroachDB is ready at 127.0.0.1:26257 (DB: sira, runtime user: sira_app)."
