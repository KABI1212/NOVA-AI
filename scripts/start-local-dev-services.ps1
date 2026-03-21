param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

function Test-CommandExists {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-CommandExists "docker")) {
    Write-Host "Docker Desktop is not installed or not on PATH." -ForegroundColor Yellow
    Write-Host "Install it from https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}

Push-Location $repoRoot
try {
    docker compose up mongo redis -d
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed."
    }

    Write-Host ""
    Write-Host "MongoDB and Redis are starting in Docker." -ForegroundColor Green
    Write-Host "Local backend can keep using DATABASE_URL=mongodb://localhost:27017/nova_ai" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next commands:" -ForegroundColor Cyan
    Write-Host "  cd `"$repoRoot\backend`""
    Write-Host "  .\venv\Scripts\Activate.ps1"
    Write-Host "  python main.py"
    Write-Host ""
    Write-Host "Useful checks:" -ForegroundColor Cyan
    Write-Host "  docker compose ps"
    Write-Host "  http://localhost:8000/health/db"
}
finally {
    Pop-Location
}
