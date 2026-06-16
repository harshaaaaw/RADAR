$logDir = 'D:\DocumentSearch\logs'
if (-not (Test-Path $logDir)) {
    Write-Output "Log directory not found: $logDir"
    exit 0
}
$logs = Get-ChildItem -Path $logDir -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 5
if (-not $logs) {
    Write-Output "No log files found in $logDir"
    exit 0
}
foreach ($f in $logs) {
    Write-Output "==== $($f.FullName) ==== (LastWrite: $($f.LastWriteTime))"
    try {
        Get-Content -Path $f.FullName -Tail 300 -ErrorAction Stop
    } catch {
        Write-Output "Failed to read $($f.FullName): $($_.Exception.Message)"
    }
    Write-Output ""
}
