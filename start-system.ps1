# Enterprise Document Search - Combined Startup & Run Script
# Configures environment, starts all services, runs the system and dashboard.

$AppRoot = "C:\Users\DELL\Music\DocumentSearch"
$RedisBin = "C:\Users\DELL\Downloads\Redis\redis-server.exe"
$OpenSearchHome = "C:\Users\DELL\Downloads\opensearch-2.18.0"
$TikaJar = "$AppRoot\tika\tika-server-2.9.2.jar"
$PythonBin = "C:\Python314\python.exe"

# 1. Environment Config
Write-Host "Setting Java environment..." -ForegroundColor Yellow
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
$env:PYTHONPATH = "src;."

Write-Host "Stopping any previously running services..." -ForegroundColor Yellow
# Stop Redis
Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | Stop-Process -Force
# Stop Java (Tika/OpenSearch)
Get-Process -Name "java" -ErrorAction SilentlyContinue | Stop-Process -Force
# Stop system orchestrator & dashboard python processes (safely, excluding current PID)
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*main.py*" -or $_.CommandLine -like "*dashboard.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 2. Directories setup
Write-Host "Creating log and temp directories..." -ForegroundColor Yellow
$LogsDir = "$AppRoot\runtime\logs"
$TempDir = "$AppRoot\runtime\temp"
$null = New-Item -ItemType Directory -Path $LogsDir -Force
$null = New-Item -ItemType Directory -Path "$LogsDir\opensearch" -Force
$null = New-Item -ItemType Directory -Path "$TempDir\tika1" -Force
$null = New-Item -ItemType Directory -Path "$TempDir\tika2" -Force
$null = New-Item -ItemType Directory -Path "$TempDir\opensearch" -Force
$null = New-Item -ItemType Directory -Path "$AppRoot\runtime\opensearch\data" -Force
$null = New-Item -ItemType Directory -Path "$AppRoot\runtime\opensearch\logs" -Force

# 3. Start Redis
Write-Host "Starting Redis datastore..." -ForegroundColor Yellow
if (Test-Path $RedisBin) {
    Start-Process -FilePath $RedisBin -NoNewWindow -RedirectStandardOutput "$LogsDir\redis.log" -RedirectStandardError "$LogsDir\redis_err.log"
    Write-Host "Redis launched." -ForegroundColor Green
} else {
    Write-Host "Redis binary not found at $RedisBin" -ForegroundColor Red
}

# 4. Start OpenSearch
if (Test-Path "$OpenSearchHome\bin\opensearch.bat") {
    Write-Host "Copying OpenSearch configurations..." -ForegroundColor Yellow
    Copy-Item "$AppRoot\config\opensearch.yml" "$OpenSearchHome\config\opensearch.yml" -Force
    Copy-Item "$AppRoot\config\jvm.options" "$OpenSearchHome\config\jvm.options" -Force

    Write-Host "Starting OpenSearch node (using bundled JDK)..." -ForegroundColor Yellow
    $env:JAVA_HOME = "$OpenSearchHome\jdk"
    Start-Process -FilePath "$OpenSearchHome\bin\opensearch.bat" -WorkingDirectory "$OpenSearchHome\bin" -NoNewWindow -RedirectStandardOutput "$LogsDir\opensearch.log" -RedirectStandardError "$LogsDir\opensearch_err.log"
    $env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
    Write-Host "OpenSearch launched." -ForegroundColor Green
} else {
    Write-Host "OpenSearch not found at $OpenSearchHome" -ForegroundColor Red
}

# 5. Start Tika Instances
if (Test-Path $TikaJar) {
    Write-Host "Starting Tika servers (Port 9998 & 9999)..." -ForegroundColor Yellow
    Start-Process -FilePath "java" -ArgumentList "-Xms768m -Xmx768m -Djava.io.tmpdir=$TempDir\tika1 -jar $TikaJar -p 9998" -NoNewWindow -RedirectStandardOutput "$LogsDir\tika-9998.log" -RedirectStandardError "$LogsDir\tika-9998_err.log"
    Start-Process -FilePath "java" -ArgumentList "-Xms768m -Xmx768m -Djava.io.tmpdir=$TempDir\tika2 -jar $TikaJar -p 9999" -NoNewWindow -RedirectStandardOutput "$LogsDir\tika-9999.log" -RedirectStandardError "$LogsDir\tika-9999_err.log"
    Write-Host "Tika nodes launched." -ForegroundColor Green
} else {
    Write-Host "Tika jar not found at $TikaJar" -ForegroundColor Red
}

Write-Host "`nWaiting 45 seconds for services to fully initialize..." -ForegroundColor Green
Start-Sleep -Seconds 45

Write-Host "`nVerifying service states..." -ForegroundColor Yellow
Start-Process -FilePath $PythonBin -ArgumentList "src/main.py check" -NoNewWindow -Wait

Write-Host "`nInitializing queue database..." -ForegroundColor Yellow
Start-Process -FilePath $PythonBin -ArgumentList "src/main.py init" -NoNewWindow -Wait

Write-Host "`nStarting Streamlit Dashboard (Port 8501)..." -ForegroundColor Yellow
Start-Process -FilePath $PythonBin -ArgumentList "-m streamlit run src/ui/dashboard.py --server.port 8501" -NoNewWindow -RedirectStandardOutput "$LogsDir\streamlit.log" -RedirectStandardError "$LogsDir\streamlit_err.log"

Write-Host "`nStarting Master Orchestrator in Foreground..." -ForegroundColor Green
& $PythonBin src/main.py start
