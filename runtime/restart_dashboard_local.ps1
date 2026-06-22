$AppRoot = "c:\Users\DELL\Music\DocumentSearch"
$PythonBin = "C:\Users\DELL\AppData\Local\Programs\Python\Python311\python.exe"
$LogsDir = "$AppRoot\runtime\logs"

# Set environment
$env:PYTHONPATH = "src;."
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"

Write-Host "Stopping existing Streamlit processes..."
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*streamlit*" } | ForEach-Object {
    Write-Host "Stopping process ID: $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

Write-Host "Starting Streamlit dashboard at port 8501..."
Start-Process -FilePath $PythonBin -ArgumentList "-m streamlit run src/ui/dashboard.py --server.port 8501" -WorkingDirectory $AppRoot -NoNewWindow -RedirectStandardOutput "$LogsDir\streamlit.log" -RedirectStandardError "$LogsDir\streamlit_err.log"

Write-Host "Dashboard launched!"
