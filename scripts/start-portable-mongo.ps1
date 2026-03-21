param(
    [string]$MongoExe = "$env:USERPROFILE\mongodb-portable\7.0.7\mongodb-win32-x86_64-windows-7.0.7\bin\mongod.exe",
    [string]$DbPath = "$env:USERPROFILE\mongodb-data\db",
    [string]$LogPath = "$env:USERPROFILE\mongodb-data\mongod.log",
    [int]$Port = 27017,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

function Test-TcpPort {
    param(
        [string]$Host = "127.0.0.1",
        [int]$Port
    )

    $client = $null
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $iar = $client.BeginConnect($Host, $Port, $null, $null)
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

if (Test-TcpPort -Port $Port) {
    Write-Host "MongoDB is already listening on 127.0.0.1:$Port" -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $MongoExe)) {
    Write-Error "mongod.exe was not found at '$MongoExe'. Download the MongoDB portable ZIP or update the -MongoExe path."
    exit 1
}

New-Item -ItemType Directory -Force (Split-Path -Parent $DbPath) | Out-Null
New-Item -ItemType Directory -Force $DbPath | Out-Null
New-Item -ItemType Directory -Force (Split-Path -Parent $LogPath) | Out-Null

$mongoArgs = @(
    "--dbpath", $DbPath,
    "--logpath", $LogPath,
    "--bind_ip", "127.0.0.1",
    "--port", $Port.ToString()
)

if ($Foreground) {
    & $MongoExe @mongoArgs
    exit $LASTEXITCODE
}

$process = Start-Process -FilePath $MongoExe -ArgumentList $mongoArgs -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3

if (-not (Test-TcpPort -Port $Port)) {
    Write-Error "MongoDB did not open port $Port. Check '$LogPath' for details."
    exit 1
}

Write-Host "MongoDB is running on mongodb://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "PID: $($process.Id)"
Write-Host "Log: $LogPath"
