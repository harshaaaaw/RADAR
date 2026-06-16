@echo off
REM ============================================================================
REM Enterprise Document Search System - Stop All Services
REM ============================================================================

REM Check for administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Administrator privileges required to stop services!
    echo Please run as administrator.
    pause
    exit /b 1
)

REM Set NSSM path
set NSSM="C:\Users\hp212560601\Tools\nssm\nssm-2.24-101-g897c7ad\win64\nssm.exe"

echo.
echo ================================================================================
echo   STOPPING ENTERPRISE DOCUMENT SEARCH SYSTEM
echo ================================================================================
echo.

echo [1/3] Stopping Master Orchestrator and all workers...
echo ----------------------------------------
REM Find and kill Python orchestrator process
for /f "tokens=2" %%a in ('tasklist ^| findstr /i "python.exe"') do (
    wmic process where "ProcessId=%%a and CommandLine like '%%orchestrator.py%%'" call terminate >nul 2>&1
)
echo ✓ Orchestrator stopped

echo.
echo [2/3] Stopping Tika instances...
echo ----------------------------------------
call bin\stop_tika.bat
echo ✓ Tika instances stopped

echo.
echo [3/3] Stopping OpenSearch...
echo ----------------------------------------
REM Stop OpenSearch2 Windows service
%NSSM% stop OpenSearch2
echo ✓ OpenSearch stopped

echo.
echo ================================================================================
echo   ALL SERVICES STOPPED
echo ================================================================================
echo.
echo System state saved in checkpoints.
echo Resume anytime by running: bin\start_all.bat
echo.
pause
