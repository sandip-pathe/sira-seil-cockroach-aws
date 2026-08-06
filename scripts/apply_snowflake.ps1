param(
    [Parameter(Mandatory = $true)]
    [string]$Connection,
    [string]$RsaPublicKeyBody = ""
)

$repo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$snow = Get-Command snow -ErrorAction SilentlyContinue
if ($null -eq $snow) {
    throw 'Snowflake CLI (`snow`) is required and was not found on PATH.'
}

function Invoke-SnowSqlFile([string]$RelativePath) {
    $path = Join-Path $repo $RelativePath
    & $snow.Source sql --connection $Connection --filename $path
    if ($LASTEXITCODE -ne 0) {
        throw "Snowflake apply failed: $RelativePath"
    }
}

& $snow.Source sql --connection $Connection --query `
    "SELECT CURRENT_ACCOUNT() AS account, CURRENT_ROLE() AS role, CURRENT_REGION() AS region"
if ($LASTEXITCODE -ne 0) { throw 'Snowflake connection preflight failed.' }

Invoke-SnowSqlFile 'infra\snowflake\00_preflight.sql'
Invoke-SnowSqlFile 'infra\snowflake\01_bootstrap.sql'
Invoke-SnowSqlFile 'infra\snowflake\02_governed_tables.sql'
Invoke-SnowSqlFile 'infra\snowflake\03_evidence_pipeline.sql'

$sellerDocs = @(
    @{ Local = 'fixtures\snowflake\seller_evidence\product_a_meetai_integrations.txt'; Remote = 'product_a/' },
    @{ Local = 'fixtures\snowflake\seller_evidence\product_b_notesync_integrations.txt'; Remote = 'product_b/' }
)
foreach ($document in $sellerDocs) {
    $absolute = ([System.IO.Path]::GetFullPath((Join-Path $repo $document.Local))).Replace('\', '/')
    $put = "PUT file://$absolute @SIRA_HACKATHON.EVIDENCE.SELLER_DOCS_STAGE/$($document.Remote) AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
    & $snow.Source sql --connection $Connection --query $put
    if ($LASTEXITCODE -ne 0) { throw "Seller document upload failed: $($document.Local)" }
}

Invoke-SnowSqlFile 'infra\snowflake\08_ingest_seller_evidence.sql'
Invoke-SnowSqlFile 'infra\snowflake\04_cortex_search.sql'
Invoke-SnowSqlFile 'infra\snowflake\05_decision_ledger.sql'
Invoke-SnowSqlFile 'infra\snowflake\06_code_stage.sql'

$bundle = & (Join-Path $PSScriptRoot 'build_snowflake_bundle.ps1') -RepositoryRoot $repo
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $bundle)) {
    throw 'Snowpark evaluator bundle build failed.'
}
$bundleUrl = ([System.IO.Path]::GetFullPath($bundle)).Replace('\', '/')
& $snow.Source sql --connection $Connection --query `
    "PUT file://$bundleUrl @SIRA_HACKATHON.DECISION.CODE_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
if ($LASTEXITCODE -ne 0) { throw 'Snowpark evaluator upload failed.' }

Invoke-SnowSqlFile 'infra\snowflake\06_snowpark_evaluator.sql'
Invoke-SnowSqlFile 'infra\snowflake\07_seed_demo.sql'

if ($RsaPublicKeyBody) {
    if ($RsaPublicKeyBody -notmatch '^[A-Za-z0-9+/=]+$') {
        throw 'RsaPublicKeyBody must be the base64 body without PEM markers.'
    }
    $identityTemplate = Get-Content -Raw -LiteralPath (Join-Path $repo 'infra\snowflake\10_runtime_identity.sql')
    $identitySql = $identityTemplate.Replace('<RSA_PUBLIC_KEY_BODY>', $RsaPublicKeyBody)
    $identityTemp = Join-Path ([System.IO.Path]::GetTempPath()) ("sira-runtime-identity-" + [guid]::NewGuid().ToString('N') + '.sql')
    try {
        [System.IO.File]::WriteAllText($identityTemp, $identitySql)
        & $snow.Source sql --connection $Connection --filename $identityTemp
        if ($LASTEXITCODE -ne 0) { throw 'Runtime identity creation failed.' }
    }
    finally {
        Remove-Item -LiteralPath $identityTemp -Force -ErrorAction SilentlyContinue
    }
}

Invoke-SnowSqlFile 'infra\snowflake\worksheets\causal_proof.sql'
Write-Output 'Snowflake governed decision plane applied and causal proof completed.'
