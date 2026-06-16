# Services Daemon for local testing
$ErrorActionPreference = "Continue"
$AppRoot = "c:\Users\DELL\Downloads\DocumentSearch\DocumentSearch"

Write-Host "Services Daemon Starting..." -ForegroundColor Cyan

# Ensure temp and log directories exist
$Ports = @(9998, 9999, 10000, 10001)
foreach ($port in $Ports) {
    $tikaDir = "$AppRoot\runtime\temp\tika$port"
    if (-not (Test-Path $tikaDir)) {
        New-Item -ItemType Directory -Path $tikaDir -Force | Out-Null
    }
}
$logDir = "$AppRoot\runtime\logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# 1. Start Redis
Write-Host "Starting Redis..." -ForegroundColor Yellow
$redisProcess = Start-Process -FilePath "C:\Users\DELL\Downloads\Redis\redis-server.exe" -PassThru -NoNewWindow

# 2. Start OpenSearch
Write-Host "Starting OpenSearch..." -ForegroundColor Yellow
$OSBin = "C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0\bin\opensearch.bat"
$env:OPENSEARCH_PATH_CONF = "C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0\config"
$osProcess = Start-Process -FilePath $OSBin -PassThru -NoNewWindow

# 3. Start Tika Cluster
Write-Host "Starting Tika servers..." -ForegroundColor Yellow
$TikaJar = "$AppRoot\tika\tika-server-2.9.2.jar"
$tikaProcesses = @()
foreach ($port in $Ports) {
    $tikaTmp = "$AppRoot\runtime\temp\tika$port"
    $JavaArgs = "-Xms512m -Xmx512m -Djava.io.tmpdir=$tikaTmp -jar $TikaJar --port $port"
    $tikaProc = Start-Process -FilePath "java.exe" -ArgumentList $JavaArgs -PassThru -NoNewWindow
    $tikaProcesses += $tikaProc
}

Write-Host "All processes launched! Siting in monitoring loop..." -ForegroundColor Green

# Infinite loop to keep processes alive and check health
while ($true) {
    $redisAlive = $false
    $osAlive = $false
    
    # Check port 6379 (Redis)
    $redisConn = New-Object System.Net.Sockets.TcpClient
    try {
        $redisConn.Connect("127.0.0.1", 6379)
        $redisAlive = $true
        $redisConn.Close()
    } catch {}

    # Check port 9200 (OpenSearch)
    $osConn = New-Object System.Net.Sockets.TcpClient
    try {
        $osConn.Connect("127.0.0.1", 9200)
        $osAlive = $true
        $osConn.Close()
    } catch {}

    # Check Tika ports
    $tikaStatus = @()
    foreach ($port in $Ports) {
        $tikaAlive = $false
        $tikaConn = New-Object System.Net.Sockets.TcpClient
        try {
            $tikaConn.Connect("127.0.0.1", $port)
            $tikaAlive = $true
            $tikaConn.Close()
        } catch {}
        $tikaStatus += "$port=$tikaAlive"
    }

    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Redis=$redisAlive | OpenSearch=$osAlive | Tika: $($tikaStatus -join ', ')" -ForegroundColor Gray
    
    Start-Sleep -Seconds 15
}
