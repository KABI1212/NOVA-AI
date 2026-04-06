param(
    [switch]$SkipMongo
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$mongoScript = Join-Path $PSScriptRoot "start-portable-mongo.ps1"
$pythonCandidates = @(
    (Join-Path $backendDir "venv314\Scripts\python.exe"),
    (Join-Path $backendDir "venv64\Scripts\python.exe"),
    (Join-Path $backendDir "venv\Scripts\python.exe")
)
$pythonExe = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

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
    if ($SkipMongo) {
        Write-Host "MongoDB is not reachable on 127.0.0.1:27017. Continuing because -SkipMongo was provided." -ForegroundColor Yellow
    }
    else {
        Write-Error "MongoDB is not reachable on 127.0.0.1:27017. Start it first or run this script without -SkipMongo."
        exit 1
    }
}

if (Test-TcpPort -Port 8000) {
    Write-Host "NOVA backend is already running at http://127.0.0.1:8000" -ForegroundColor Green
    exit 0
}

if (-not $pythonExe) {
    Write-Error "No backend Python environment was found. Expected one of: backend\\venv314, backend\\venv64, or backend\\venv."
    exit 1
}

Push-Location $backendDir
try {
    Write-Host "Starting NOVA backend at http://localhost:8000" -ForegroundColor Green
    Write-Host "Press Ctrl+C in this window to stop the backend." -ForegroundColor Yellow
    & $pythonExe "main.py"
}
finally {
    Pop-Location
}
