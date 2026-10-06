Set-Location $PSScriptRoot

function Fail($message) {
    Write-Host ""
    Write-Host "Problem: $message" -ForegroundColor Red
    Write-Host ""
    exit 1
}

function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { Fail "'docker $args' failed. See the message above." }
}

Write-Host "Cloakroom - starting CloakBrowser" -ForegroundColor White
Write-Host ""

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker is not installed.`nInstall Docker Desktop for Windows (it needs WSL 2), open it once, then run .\start.ps1 again:`n  https://www.docker.com/products/docker-desktop/"
}

$osType = (docker info --format "{{.OSType}}" 2>$null)
if ($LASTEXITCODE -ne 0) {
    Fail "Docker Desktop is not running.`nOpen Docker Desktop from the Start menu, wait until it says `"Engine running`", then run .\start.ps1 again."
}
if ($osType -ne "linux") {
    Fail "Docker is set to Windows containers, and Cloakroom needs Linux containers.`nRight-click the Docker icon in the taskbar, choose 'Switch to Linux containers...', then run .\start.ps1 again."
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Fail "Your Docker is missing 'docker compose'. Update Docker Desktop to the latest version."
}

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env -ErrorAction Stop
    Write-Host "Created .env with default settings (edit it later to add a license key or proxy)."
}

Write-Host "1/3 Downloading the latest CloakBrowser image (first time can take a few minutes)..."
Invoke-Docker compose pull hello --quiet
Invoke-Docker compose build --pull --quiet cloakroom

Write-Host "2/3 Starting the browser..."
Invoke-Docker compose up -d --force-recreate cloakroom

Write-Host "3/3 Waiting for the browser to be ready..."
$status = "missing"
for ($i = 0; $i -lt 150; $i++) {
    $status = (docker inspect -f "{{.State.Health.Status}}" cloakroom 2>$null)
    if ($status -eq "healthy") { break }
    Start-Sleep -Seconds 2
}

if ($status -ne "healthy") {
    docker compose logs --tail 40 cloakroom
    Fail "The browser did not become ready (status: $status). See the log above, or skills/cloakroom/SKILL.md > Troubleshooting."
}

$viewerUrl = "http://" + (docker compose port cloakroom 6080)
$cdpUrl = "http://" + (docker compose port cloakroom 9222)

Write-Host ""
Write-Host "You're ready!" -ForegroundColor Green
Write-Host ""
Write-Host "  See the browser:    $viewerUrl"
Write-Host "  Try an example:     docker compose run --rm hello"
Write-Host "  Stop everything:    .\stop.ps1"
Write-Host ""
Write-Host "  For scripts (Playwright, Puppeteer): $cdpUrl"
Write-Host "  Only this computer can connect. Your logins are kept between restarts."
Write-Host ""

Start-Process $viewerUrl
