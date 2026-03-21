param(
    [switch]$SkipMongo
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$mongoScript = Join-Path $PSScriptRoot "start-portable-mongo.ps1"

function Test-TcpPort {
    param(
        [string]$Hostname = "127.0.0.1",
        [int]$Port
    )

    $client = $null
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $iar = $client.BeginConnect($Hostname, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(1000, $false)) {
            return $false
        }

        $client.EndConnect($iar)
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $client) {
            $client.Dispose()
        }
    }
}

if (-not $SkipMongo) {
    & $mongoScript
}

if (-not (Test-TcpPort -Port 27017)) {
    Write-Error "MongoDB is not reachable on 127.0.0.1:27017. Start it first or run this script without -SkipMongo."
    exit 1
}

if (Test-TcpPort -Port 8000) {
    Write-Host "NOVA backend is already running at http://127.0.0.1:8000" -ForegroundColor Green
    exit 0
}

Push-Location $backendDir
try {
    Write-Host "Starting NOVA backend at http://localhost:8000" -ForegroundColor Green
    Write-Host "Press Ctrl+C in this window to stop the backend." -ForegroundColor Yellow
    cmd /c "call venv\Scripts\activate.bat && python main.py"
}
finally {
    Pop-Location
}
