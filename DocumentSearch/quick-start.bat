@echo off
REM Quick Start Script for Enterprise Document Search System
REM This script helps you start all services and verify they're running

echo ================================================================================
echo Enterprise Document Search System - Quick Start
echo ================================================================================
echo.

REM Get the script directory
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

echo [1/5] Starting OpenSearch...
echo.
start "OpenSearch" cmd /c "cd bin && start_opensearch.bat"
timeout /t 30 /nobreak >nul

echo.
echo [2/5] Starting Tika servers...
echo.
start "Tika" cmd /c "cd bin && start_tika.bat"
timeout /t 15 /nobreak >nul

echo.
echo [3/5] Waiting for services to initialize (45 seconds)...
timeout /t 45 /nobreak

echo.
echo [4/5] Checking service health...
echo.
python src\main.py check

if errorlevel 1 (
    echo.
    echo ================================================================================
    echo ERROR: Some services are not running properly!
    echo ================================================================================
    echo.
    echo Please check the error messages above and:
    echo   1. Ensure Java is installed and in PATH
    echo   2. Verify OpenSearch is configured correctly
    echo   3. Check that Tika jar file exists
    echo   4. See TROUBLESHOOTING.md for detailed help
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

echo.
echo [5/5] All services ready!
echo.
echo ================================================================================
echo Services are running. You can now:
echo ================================================================================
echo.
echo   1. Initialize the system (first time only):
echo      python src\main.py init
echo.
echo   2. Start document processing:
echo      python src\main.py start
echo.
echo   3. Open the dashboard (in a new terminal):
echo      streamlit run src\ui\dashboard.py
echo.
echo ================================================================================
echo.
pause
