# One-step install or update for Windows (Docker Desktop with WSL 2), in PowerShell:
#   irm https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.ps1 | iex   # // pragma: allowlist secret
#
# Works in Windows PowerShell 5.1 and PowerShell 7. The app lives in ~\.cloakroom\app and is
# replaced wholesale from a GitHub zip on every run; the previous copy is kept in
# ~\.cloakroom\app.previous and your .env settings carry over.
# Optional: $env:CLOAKROOM_ZIP_URL installs from another zip (a fork, branch or tag).
#
# For agents running this for a user: without Docker Desktop the installer changes
# nothing and stops after a line starting "CLOAKROOM_NEEDS: docker". Ask the user
# whether to install it, and if they agree, set $env:CLOAKROOM_INSTALL_DOCKER = "yes"
# and run it again. "CLOAKROOM_NEEDS: user" means a step only the user can do
# (finishing Docker Desktop's first-run setup, a restart); it says which.

$ErrorActionPreference = "Stop"

function Fail($message) {
    Write-Host ""
    Write-Host "Problem: $message" -ForegroundColor Red
    Write-Host ""
    throw "Cloakroom install stopped."
}

function Needs($kind, $message) {
    Write-Host ""
    Write-Host "CLOAKROOM_NEEDS: $kind"
    Write-Host $message
    Write-Host ""
    throw "Cloakroom install stopped: needs $kind."
}

function Wait-DockerEngine($seconds) {
    for ($i = 0; $i -lt $seconds; $i += 5) {
        docker info --format "{{.OSType}}" *> $null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Install-DockerDesktop {
    if ($env:CLOAKROOM_INSTALL_DOCKER -ne "yes") {
        Needs "docker" ("Cloakroom runs its browser in a Linux container, and Docker Desktop is not installed.`n" +
            "It would install Docker Desktop with winget (Windows asks for administrator approval):`n" +
            "  winget install -e --id Docker.DockerDesktop`n`n" +
            "To install it, run the installer again with:`n" +
            "  `$env:CLOAKROOM_INSTALL_DOCKER = `"yes`"; irm https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.ps1 | iex")  # // pragma: allowlist secret
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Needs "user" "winget is not available here. Install Docker Desktop from https://docs.docker.com/desktop/setup/install/windows-install/, open it once, then run the installer again."
    }
    Write-Host "Installing Docker Desktop with winget (approve the administrator prompt)..."
    winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Needs "user" "winget could not install Docker Desktop (exit $LASTEXITCODE). Install it from https://docs.docker.com/desktop/setup/install/windows-install/, open it once, then run the installer again."
    }
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Start-DockerDesktop {
    $app = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $app) {
        Write-Host "Starting Docker Desktop..."
        Start-Process $app
        if (Wait-DockerEngine 240) { return }
    }
    Needs "user" ("Docker Desktop is installed but its engine is not running.`n" +
        "Open Docker Desktop from the Start menu and finish its first-run setup (accept the terms;`n" +
        "if it asks to install or update WSL, allow it and restart Windows if asked).`n" +
        "When it says 'Engine running', run the Cloakroom installer again.")
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
        Install-DockerDesktop
    }
    $osType = (docker info --format "{{.OSType}}" 2>$null)
    if ($LASTEXITCODE -ne 0) {
        Start-DockerDesktop
        $osType = (docker info --format "{{.OSType}}" 2>$null)
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
