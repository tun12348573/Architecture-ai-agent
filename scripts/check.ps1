# Runs all local checks. Usage: .\scripts\check.ps1
# Integration tests need EXTERIOR_AGENT_BLENDER (or blender on PATH); they skip otherwise.
# Native tools write progress to stderr; rely on exit codes, not PowerShell error records.
$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path "$py")) { throw "Missing .venv - see README setup" }
Push-Location "$repo"
try {
    $steps = @(
        @("ruff check", @("-m", "ruff", "check", ".")),
        @("ruff format", @("-m", "ruff", "format", "--check", ".")),
        @("unit tests", @("-m", "pytest", "tests/unit", "-q")),
        @("integration tests", @("-m", "pytest", "tests/integration", "-q")),
        @("dependency audit", @("-m", "pip_audit", "-r", "requirements.lock"))
    )
    foreach ($step in $steps) {
        Write-Host "==> $($step[0])"
        & "$py" @($step[1]) 2>&1 | ForEach-Object { "$_" } | Out-Host
        # pytest exit 5 = no tests collected (allowed for integration before tests exist)
        if ($LASTEXITCODE -ne 0 -and -not ($step[0] -eq "integration tests" -and $LASTEXITCODE -eq 5)) {
            throw "$($step[0]) failed (exit $LASTEXITCODE)"
        }
    }
    Write-Host "All checks passed"
} finally {
    Pop-Location
}
