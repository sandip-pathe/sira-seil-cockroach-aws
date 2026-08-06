param(
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$repo = [System.IO.Path]::GetFullPath($RepositoryRoot)
$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("sira-snowflake-bundle-" + [guid]::NewGuid().ToString('N'))
$dist = Join-Path $repo 'infra\snowflake\dist'
$archive = Join-Path $dist 'sira_snowflake_evaluator.zip'

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
New-Item -ItemType Directory -Path $dist -Force | Out-Null

try {
    Copy-Item -Recurse -LiteralPath (Join-Path $repo 'python\decision_engine') -Destination $buildRoot
    Copy-Item -Recurse -LiteralPath (Join-Path $repo 'python\domain') -Destination $buildRoot
    New-Item -ItemType Directory -Path (Join-Path $buildRoot 'integrations') -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $repo 'python\integrations\__init__.py') -Destination (Join-Path $buildRoot 'integrations\__init__.py')
    Copy-Item -Recurse -LiteralPath (Join-Path $repo 'python\integrations\snowflake') -Destination (Join-Path $buildRoot 'integrations')
    Copy-Item -LiteralPath (Join-Path $repo 'python\integrations\snowflake\snowpark_handler.py') -Destination (Join-Path $buildRoot 'snowpark_handler.py')

    $vendor = Join-Path $repo '.venv\Lib\site-packages\rfc8785'
    if (-not (Test-Path -LiteralPath $vendor)) {
        throw 'rfc8785 is missing from .venv; install project dependencies before building.'
    }
    Copy-Item -Recurse -LiteralPath $vendor -Destination $buildRoot

    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive
    }
    Compress-Archive -Path (Join-Path $buildRoot '*') -DestinationPath $archive -CompressionLevel Optimal
    Write-Output $archive
}
finally {
    $resolvedBuild = [System.IO.Path]::GetFullPath($buildRoot)
    $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedBuild.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -Recurse -LiteralPath $resolvedBuild -Force -ErrorAction SilentlyContinue
    }
}
