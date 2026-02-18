param(
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"

Write-Host "==> Local validate: tests + compile checks"

Write-Host "==> Running pytest"
python -m pytest -q

if (-not $SkipCompile) {
    Write-Host "==> Running compileall on src/tests"
    python -m compileall -q src tests
}

Write-Host "==> Local validate passed"
