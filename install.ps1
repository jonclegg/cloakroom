# One-step install or update for Windows (Docker Desktop with WSL 2), in PowerShell:
#   irm https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.ps1 | iex   # // pragma: allowlist secret
#
# Works in Windows PowerShell 5.1 and PowerShell 7. The app lives in ~\.cloakroom\app and is
# replaced wholesale from a GitHub zip on every run; the previous copy is kept in
# ~\.cloakroom\app.previous and your .env settings carry over.
# Optional: $env:CLOAKROOM_ZIP_URL installs from another zip (a fork, branch or tag).

$ErrorActionPreference = "Stop"

function Fail($message) {
    Write-Host ""
    Write-Host "Problem: $message" -ForegroundColor Red
    Write-Host ""
    throw "Cloakroom install stopped."
}

function Install-Cloakroom {
    $zipUrl = $env:CLOAKROOM_ZIP_URL
    if (-not $zipUrl) { $zipUrl = "https://github.com/jonclegg/cloakroom/archive/refs/heads/main.zip" }  # // pragma: allowlist secret
    $stateDir = Join-Path $HOME ".cloakroom"
    $installDir = Join-Path $stateDir "app"

    # Windows PowerShell 5.1 may default to TLS 1.0, which GitHub refuses.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    # Let start.ps1 run in this session even where script execution is restricted.
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Fail "Docker is not installed.`nInstall Docker Desktop for Windows (it uses WSL 2), open it once, wait for 'Engine running', then run this again:`n  https://docs.docker.com/desktop/setup/install/windows-install/"
    }
    $osType = (docker info --format "{{.OSType}}" 2>$null)
    if ($LASTEXITCODE -ne 0) {
        Fail "Docker Desktop is not running.`nOpen Docker Desktop from the Start menu, wait until it says 'Engine running', then run this again."
    }
    if ($osType -ne "linux") {
        Fail "Docker is set to Windows containers, and Cloakroom needs Linux containers.`nRight-click the Docker icon in the taskbar, choose 'Switch to Linux containers...', then run this again."
    }
    docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        Fail "Your Docker is missing 'docker compose'. Update Docker Desktop, then run this again."
    }
    Write-Host "Container engine: Docker Desktop (Linux containers)."

    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
    # The app folder can't be moved aside while this session's current folder is inside it.
    if ((Get-Location).Path -like "$installDir*") { Set-Location $HOME }
    Get-ChildItem -Path $stateDir -Filter ".download-*" -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    $stage = Join-Path $stateDir (".download-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        Write-Host "Downloading Cloakroom..."
        $zip = Join-Path $stage "app.zip"
        Invoke-WebRequest -Uri $zipUrl -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath (Join-Path $stage "x")
        $new = Get-ChildItem -Path (Join-Path $stage "x") -Directory |
            Where-Object { (Test-Path (Join-Path $_.FullName "start.ps1")) -and (Test-Path (Join-Path $_.FullName "docker-compose.yml")) } |
            Select-Object -First 1
        if (-not $new) { Fail "The download from $zipUrl doesn't look like Cloakroom." }
        # Files from the internet are marked as such; unblock them so start.ps1 may run.
        Get-ChildItem -Path $new.FullName -Recurse -File | Unblock-File
        $oldEnv = Join-Path $installDir ".env"
        if (Test-Path $oldEnv) { Copy-Item $oldEnv (Join-Path $new.FullName ".env") }
        if (Test-Path $installDir) {
            $previous = Join-Path $stateDir "app.previous"
            if (Test-Path $previous) { Remove-Item -Recurse -Force $previous }
            Move-Item $installDir $previous
            Move-Item $new.FullName $installDir
            Write-Host "Updated Cloakroom. The previous copy is in $previous"
        } else {
            Move-Item $new.FullName $installDir
            Write-Host "Installed Cloakroom in $installDir"
        }
    } finally {
        if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
    }

    Write-Host "Starting Cloakroom..."
    # start.ps1 changes the current folder; give the user theirs back afterwards.
    Push-Location
    try { & (Join-Path $installDir "start.ps1") } finally { Pop-Location }
    Write-Host ("Start again later:  & `"" + (Join-Path $installDir "start.ps1") + "`"")
    Write-Host ("Stop:               & `"" + (Join-Path $installDir "stop.ps1") + "`"")
}

Install-Cloakroom
