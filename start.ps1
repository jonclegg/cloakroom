# --force-onboard: show the first-run next steps even when the OpenRouter key is set.
$forceOnboard = $args -contains "--force-onboard"
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

Write-Host "Cloakroom - starting the browser" -ForegroundColor White
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
    Write-Host "Created .env with default settings (edit it later to add a proxy)."
}

# The API writes notes, run logs, photos and smoke reports here. Compose needs it
# spelled out: Windows has no HOME variable for docker-compose.yml to use.
if (-not $env:CLOAKROOM_DATA_DIR) { $env:CLOAKROOM_DATA_DIR = Join-Path $HOME ".cloakroom\data" }
New-Item -ItemType Directory -Force -Path $env:CLOAKROOM_DATA_DIR | Out-Null

if ($env:CLOAKROOM_DEV -eq "1") {
    Write-Host "1/3 Building Cloakroom from this folder (CLOAKROOM_DEV=1)..."
    # Every compose command in this run sees the build sections too.
    $env:COMPOSE_FILE = "docker-compose.yml;docker-compose.dev.yml"
    Invoke-Docker compose build --quiet cloakroom
} else {
    Write-Host "1/3 Downloading Cloakroom (first time can take a few minutes)..."
    Invoke-Docker compose pull --quiet cloakroom
}

Write-Host "2/3 Starting the browser..."
Invoke-Docker compose up -d --force-recreate cloakroom

# The first start also downloads the GeoIP database (~70 MB).
Write-Host "3/3 Waiting for the browser to be ready..."
$status = "missing"
for ($i = 0; $i -lt 300; $i++) {
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
$apiUrl = "http://" + (docker compose port cloakroom 8423)

Write-Host ""
Write-Host "You're ready!" -ForegroundColor Green
Write-Host ""
Write-Host "  See the browser:    $viewerUrl"
Write-Host "  Chat with it:       docker exec cloakroom cloakroom chat `"<message>`"   (API $apiUrl)"
Write-Host "  Stop everything:    .\stop.ps1"
Write-Host ""
if ($forceOnboard -or -not (Test-Path (Join-Path $env:CLOAKROOM_DATA_DIR "openrouter.key"))) {
    Write-Host "  Next: docker exec cloakroom cloakroom key     (open the link it prints and paste your OpenRouter key)"
    Write-Host "        docker exec cloakroom cloakroom smoke   (check it can reach Amazon, Walmart, Target and Best Buy;"
    Write-Host "                                                 the report is in $env:CLOAKROOM_DATA_DIR\smoke)"
    Write-Host ""
}
Write-Host "  For scripts (Playwright, Puppeteer): $cdpUrl"
Write-Host "  Only this computer can connect. Your logins are kept between restarts."
Write-Host ""
