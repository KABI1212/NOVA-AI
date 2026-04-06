param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("chrome", "edge")]
    [string]$Browser
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$debugUrl = "http://localhost:3000"

switch ($Browser) {
    "chrome" {
        $browserName = "Chrome"
        $browserExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
        $profileDir = Join-Path $repoRoot ".vscode\chrome-debug-profile"
        $debugPort = 9222
    }
    "edge" {
        $browserName = "Edge"
        $browserExe = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        $profileDir = Join-Path $repoRoot ".vscode\edge-debug-profile"
        $debugPort = 9223
    }
}

function Test-DebugEndpoint {
    param([int]$Port)

    try {
        $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/json/version" -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Test-Path $browserExe)) {
    Write-Error "$browserName executable was not found at $browserExe"
    exit 1
}

if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir | Out-Null
}

if (Test-DebugEndpoint -Port $debugPort) {
    Write-Host "$browserName debug browser is already ready on port $debugPort" -ForegroundColor Green
    exit 0
}

$args = @(
    "--remote-debugging-port=$debugPort",
    "--user-data-dir=$profileDir",
    "--no-first-run",
    "--no-default-browser-check",
    "--do-not-de-elevate",
    "--new-window",
    $debugUrl
)

Start-Process -FilePath $browserExe -ArgumentList $args | Out-Null

$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
    if (Test-DebugEndpoint -Port $debugPort) {
        Write-Host "$browserName debug browser is ready on port $debugPort" -ForegroundColor Green
        exit 0
    }

    Start-Sleep -Milliseconds 500
}

Write-Error "$browserName opened, but the debug endpoint on port $debugPort did not become ready in time."
exit 1
