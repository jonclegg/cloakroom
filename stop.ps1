Set-Location $PSScriptRoot

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop is not running, so Cloakroom is already stopped."
    exit 0
}

docker compose --profile examples down
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ""
Write-Host "Cloakroom stopped. Your browser profile is saved; .\start.ps1 brings it back."
