# Run local services for Document Search System (Redis, OpenSearch, Tika)

$AppRoot = "C:\Users\DELL\Music\DocumentSearch"
$RedisBin = "C:\Users\DELL\Downloads\Redis\redis-server.exe"
$OpenSearchHome = "C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0"
$TikaJar = "$AppRoot\tika\tika-server-2.9.2.jar"

$LogsDir = "$AppRoot\runtime\logs"
$TempDir = "$AppRoot\runtime\temp"

Write-Host "Stopping any previously running services..." -ForegroundColor Yellow
# Stop Redis
Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | Stop-Process -Force
# Stop Java (Tika/OpenSearch)
Get-Process -Name "java" -ErrorAction SilentlyContinue | Stop-Process -Force
# Stop system orchestrator & dashboard python processes (safely, excluding current PID)
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*main.py*" -or $_.CommandLine -like "*dashboard.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 1. Directories setup
Write-Host "Creating log and temp directories..." -ForegroundColor Yellow
$null = New-Item -ItemType Directory -Path $LogsDir -Force
$null = New-Item -ItemType Directory -Path "$LogsDir\opensearch" -Force
$null = New-Item -ItemType Directory -Path "$TempDir\tika1" -Force
$null = New-Item -ItemType Directory -Path "$TempDir\tika2" -Force
$null = New-Item -ItemType Directory -Path "$TempDir\opensearch" -Force
$null = New-Item -ItemType Directory -Path "$AppRoot\runtime\opensearch\data" -Force
$null = New-Item -ItemType Directory -Path "$AppRoot\runtime\opensearch\logs" -Force

# 2. Start Redis
Write-Host "Starting Redis datastore..." -ForegroundColor Yellow
if (Test-Path $RedisBin) {
    Start-Process -FilePath $RedisBin -NoNewWindow -RedirectStandardOutput "$LogsDir\redis.log" -RedirectStandardError "$LogsDir\redis_err.log"
    Write-Host "Redis launch command sent." -ForegroundColor Green
} else {
    Write-Host "Redis binary not found at $RedisBin" -ForegroundColor Red
}

# 3. Start OpenSearch
if (Test-Path "$OpenSearchHome\bin\opensearch.bat") {
    Write-Host "Copying OpenSearch configurations..." -ForegroundColor Yellow
    Copy-Item "$AppRoot\config\opensearch.yml" "$OpenSearchHome\config\opensearch.yml" -Force
    Copy-Item "$AppRoot\config\jvm.options" "$OpenSearchHome\config\jvm.options" -Force

    Write-Host "Starting OpenSearch node..." -ForegroundColor Yellow
    Start-Process -FilePath "$OpenSearchHome\bin\opensearch.bat" -WorkingDirectory "$OpenSearchHome\bin" -NoNewWindow -RedirectStandardOutput "$LogsDir\opensearch.log" -RedirectStandardError "$LogsDir\opensearch_err.log"
    Write-Host "OpenSearch launch command sent." -ForegroundColor Green
} else {
    Write-Host "OpenSearch not found at $OpenSearchHome" -ForegroundColor Red
}

# 4. Start Tika Instances
if (Test-Path $TikaJar) {
    Write-Host "Starting Tika servers (Port 9998 and 9999)..." -ForegroundColor Yellow
    Start-Process -FilePath "java" -ArgumentList "-Xms768m -Xmx768m -Djava.io.tmpdir=$TempDir\tika1 -jar $TikaJar -p 9998" -NoNewWindow -RedirectStandardOutput "$LogsDir\tika-9998.log" -RedirectStandardError "$LogsDir\tika-9998_err.log"
    Start-Process -FilePath "java" -ArgumentList "-Xms768m -Xmx768m -Djava.io.tmpdir=$TempDir\tika2 -jar $TikaJar -p 9999" -NoNewWindow -RedirectStandardOutput "$LogsDir\tika-9999.log" -RedirectStandardError "$LogsDir\tika-9999_err.log"
    Write-Host "Tika nodes launch command sent." -ForegroundColor Green
} else {
    Write-Host "Tika jar not found at $TikaJar" -ForegroundColor Red
}

Write-Host "Waiting 40 seconds for services to fully initialize..." -ForegroundColor Green
Start-Sleep -Seconds 40

Write-Host "Verifying service states..." -ForegroundColor Yellow
Start-Process -FilePath "C:\Users\DELL\AppData\Local\Programs\Python\Python311\python.exe" -ArgumentList "src/main.py check" -NoNewWindow -Wait
