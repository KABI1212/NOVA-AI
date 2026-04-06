param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"

function Test-FrontendServer {
    try {
        $response = Invoke-WebRequest -UseBasicParsing "http://localhost:3000" -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

if (Test-FrontendServer) {
    Write-Host "Frontend dev server is already running at http://localhost:3000" -ForegroundColor Green
    exit 0
}

Push-Location $frontendDir
try {
    Write-Host "Starting Vite dev server at http://localhost:3000" -ForegroundColor Green
    Write-Host "Press Ctrl+C in this window to stop the frontend." -ForegroundColor Yellow
    & "npm.cmd" "run" "dev"
}
finally {
    Pop-Location
}
