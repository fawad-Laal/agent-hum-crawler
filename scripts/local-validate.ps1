param(
    [switch]$SkipCompile,
    [switch]$SkipE2E
)

$ErrorActionPreference = "Stop"

Write-Host "==> Local validate: tests + compile checks"

Write-Host "==> Running pytest"
python -m pytest -q

if (-not $SkipCompile) {
    Write-Host "==> Running compileall on src/tests"
    python -m compileall -q src tests
}

if (-not $SkipE2E) {
    Write-Host "==> Running deterministic E2E gate with artifact capture"
    python .\scripts\e2e_gate.py
}

Write-Host "==> Local validate passed"
