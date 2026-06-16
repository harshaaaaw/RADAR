# Local Service Starter for Document Search System
$AppRoot = "c:\Users\DELL\Downloads\DocumentSearch\DocumentSearch"

Write-Host "Creating temp directories for Tika..." -ForegroundColor Yellow
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

Write-Host "Starting Redis..." -ForegroundColor Yellow
Start-Process -FilePath "C:\Users\DELL\Downloads\Redis\redis-server.exe" -WindowStyle Minimized

Write-Host "Starting OpenSearch..." -ForegroundColor Yellow
$OSBin = "C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0\bin\opensearch.bat"
$env:OPENSEARCH_PATH_CONF = "C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0\config"
Start-Process -FilePath $OSBin -WindowStyle Minimized

Write-Host "Starting Tika cluster..." -ForegroundColor Yellow
$TikaJar = "$AppRoot\tika\tika-server-2.9.2.jar"
foreach ($port in $Ports) {
    $tikaTmp = "$AppRoot\runtime\temp\tika$port"
    $JavaArgs = "-Xms512m -Xmx512m -Djava.io.tmpdir=$tikaTmp -jar $TikaJar --port $port"
    Start-Process -FilePath "java.exe" -ArgumentList $JavaArgs -WindowStyle Minimized
}

Write-Host "Services started! Waiting for them to warm up (30 seconds)..." -ForegroundColor Green
Start-Sleep -Seconds 30
