[CmdletBinding()]
param([string]$DockerPath)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if (-not $DockerPath) {
    $command = Get-Command docker -ErrorAction SilentlyContinue
    if ($command) { $DockerPath = $command.Source }
    else {
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"),
            (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe")
        )
        $DockerPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
}
if (-not $DockerPath -or -not (Test-Path -LiteralPath $DockerPath)) {
    throw "Docker CLI not found. Pass -DockerPath with the installed docker.exe path."
}
$secretFile = Join-Path $repo "sandbox\.env"
if (-not (Test-Path -LiteralPath $secretFile)) {
    $values = "LAB_ADMIN_PASSWORD=" + [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N") +
        "`nLAB_CLIENT_SECRET=" + [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N") + "`n"
    [IO.File]::WriteAllText($secretFile, $values, [Text.UTF8Encoding]::new($false))
}
foreach ($line in [IO.File]::ReadAllLines($secretFile)) {
    if ($line -match "^(LAB_ADMIN_PASSWORD|LAB_CLIENT_SECRET)=(.+)$") {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process")
    }
}
& $DockerPath compose --project-name portfolio-identity-lab --env-file $secretFile -f (Join-Path $repo "sandbox\compose.yaml") up -d
if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed" }
$deadline = (Get-Date).AddSeconds(60)
do {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8080/realms/portfolio-lab/.well-known/openid-configuration" -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            Write-Host "Keycloak realm is ready at http://127.0.0.1:8080"
            Write-Host "Local secrets retained in ignored sandbox/.env; do not publish that file."
            return
        }
    } catch { }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)
throw "Keycloak realm was not ready within 60 seconds. Inspect the lab container logs."
