# Startup Script for AWS Production Environment
# 128 vCPU / 64GB RAM Optimization
# ---------------------------------------------------

Write-Host "Starting Document Search System (AWS Production Mode)..." -ForegroundColor Green

# 1. Set Python Path
$env:PYTHONPATH = "$PSScriptRoot\src"

# 2. Check for Tika (Assuming running as service, but simple check)
$tikaPorts = @(9998, 9999)
foreach ($port in $tikaPorts) {
    if (Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet) {
        Write-Host "  [OK] Tika running on port $port" -ForegroundColor Green
    }
    else {
        Write-Host "  [WARN] Tika NOT detected on port $port. Please start Tika." -ForegroundColor Yellow
    }
}

# 3. Check Redis
if (Test-NetConnection -ComputerName localhost -Port 6379 -InformationLevel Quiet) {
    Write-Host "  [OK] Redis running on port 6379" -ForegroundColor Green
}
else {
    Write-Host "  [WARN] Redis NOT detected. Please start Redis." -ForegroundColor Yellow
}

# 4. Start Dashboard and Orchestrator
Write-Host "Launching Dashboard and Orchestrator..."
Start-Process -FilePath "python" -ArgumentList "-m streamlit run src/ui/dashboard.py --server.port 8501 --server.headless true" -NoNewWindow

Write-Host "System started! Access dashboard at http://localhost:8501"
