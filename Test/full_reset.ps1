# Full System Reset Script for DocumentSearch v8
# This script stops ALL processes and performs a complete reset

$ErrorActionPreference = "Continue"
$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BaseDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Full System Reset - DocumentSearch v8" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop Streamlit dashboard (runs as python.exe, NOT streamlit.exe)
Write-Host "Step 1: Stopping Streamlit dashboard..." -ForegroundColor Yellow
Get-WmiObject Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and ($_.CommandLine -like "*streamlit*" -or $_.CommandLine -like "*dashboard*")
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "  Killed Streamlit process (PID: $($_.ProcessId))" -ForegroundColor Gray
}
Write-Host "  Done" -ForegroundColor Green

# Step 2: Stop any DocumentSearch Python worker/orchestrator processes
Write-Host "Step 2: Stopping worker processes..." -ForegroundColor Yellow
$currentPid = $PID
Get-WmiObject Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -like "*DocumentSearch*" -and $_.ProcessId -ne $currentPid
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "  Killed worker process (PID: $($_.ProcessId))" -ForegroundColor Gray
}
Start-Sleep -Seconds 3
Write-Host "  Done" -ForegroundColor Green

# Step 3: Clear Python cache
Write-Host "Step 3: Clearing Python cache..." -ForegroundColor Yellow
Get-ChildItem -Path "src" -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  Done" -ForegroundColor Green

# Step 4: Run the reset command
Write-Host "Step 4: Running system reset..." -ForegroundColor Yellow
& C:\Python314\python.exe src/main.py reset --force

# Step 5: Verify reset
Write-Host ""
Write-Host "Step 5: Final verification..." -ForegroundColor Yellow

$allClean = $true

# Check queue database
$queueDb = Join-Path $BaseDir "runtime\queue\queues.db"
if (Test-Path $queueDb) {
    Write-Host "  WARNING: Queue database still exists! Force deleting..." -ForegroundColor Red
    Remove-Item $queueDb -Force -ErrorAction SilentlyContinue
    Remove-Item "$queueDb-wal" -Force -ErrorAction SilentlyContinue
    Remove-Item "$queueDb-shm" -Force -ErrorAction SilentlyContinue
    Remove-Item "$queueDb-journal" -Force -ErrorAction SilentlyContinue
    if (Test-Path $queueDb) {
        Write-Host "  ERROR: Could not delete queue database!" -ForegroundColor Red
        $allClean = $false
    } else {
        Write-Host "  Force deleted successfully" -ForegroundColor Green
    }
} else {
    Write-Host "  Queue database: CLEAN" -ForegroundColor Green
}

# Check audit.db
$auditDb = Join-Path $BaseDir "runtime\audit\audit.db"
if (Test-Path $auditDb) {
    Write-Host "  WARNING: audit.db still exists! Force deleting..." -ForegroundColor Red
    Remove-Item $auditDb -Force -ErrorAction SilentlyContinue
    Remove-Item "$auditDb-wal" -Force -ErrorAction SilentlyContinue
    Remove-Item "$auditDb-shm" -Force -ErrorAction SilentlyContinue
    if (Test-Path $auditDb) {
        Write-Host "  ERROR: Could not delete audit.db (close dashboard first!)" -ForegroundColor Red
        $allClean = $false
    } else {
        Write-Host "  Force deleted successfully" -ForegroundColor Green
    }
} else {
    Write-Host "  Audit database: CLEAN" -ForegroundColor Green
}

# Check audit directory for remaining files
$auditDir = Join-Path $BaseDir "runtime\audit"
if (Test-Path $auditDir) {
    $remainingFiles = Get-ChildItem $auditDir -File -ErrorAction SilentlyContinue
    if ($remainingFiles) {
        Write-Host "  WARNING: $($remainingFiles.Count) audit files remain! Deleting..." -ForegroundColor Red
        $remainingFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

# Check Redis
Write-Host "  Checking Redis..." -ForegroundColor Gray
try {
    $redisCheck = & C:\Python314\python.exe -c "import redis; r=redis.from_url('redis://localhost:6379/0'); c=len(list(r.scan_iter('docsearch:*'))); print(c)" 2>$null
    if ($redisCheck -eq "0") {
        Write-Host "  Redis: CLEAN (0 keys)" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Redis has $redisCheck remaining keys!" -ForegroundColor Red
        $allClean = $false
    }
} catch {
    Write-Host "  Could not check Redis" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($allClean) {
    Write-Host "Reset Complete! Everything is clean." -ForegroundColor Green
} else {
    Write-Host "Reset partially complete. See warnings above." -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Start dashboard: C:\Python314\python.exe -m streamlit run src/ui/dashboard.py" -ForegroundColor Gray
Write-Host "  2. Start processing: C:\Python314\python.exe src/main.py start" -ForegroundColor Gray
