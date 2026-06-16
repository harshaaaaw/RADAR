@echo off
REM ============================================================================
REM Enterprise Document Search - Start OpenSearch
REM Optimized with 12GB heap for 128 vCPU / 64GB RAM
REM ============================================================================

REM Check for administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Administrator privileges required to start services!
    echo Please run as administrator.
    pause
    exit /b 1
)

echo ========================================
echo Starting OpenSearch
echo Heap Size: 12GB
echo ========================================
echo.

REM Set NSSM path
set NSSM="C:\Users\hp212560601\Tools\nssm\nssm-2.24-101-g897c7ad\win64\nssm.exe"

REM Set OpenSearch installation directory (adjust as needed)
set OPENSEARCH_HOME=C:\opensearch-2.12.0

REM Check if OpenSearch exists
if not exist "%OPENSEARCH_HOME%\bin\opensearch.bat" (
    echo ERROR: OpenSearch not found at %OPENSEARCH_HOME%
    echo Please install OpenSearch and update the path
    pause
    exit /b 1
)

REM Create necessary directories
echo Creating directories...
mkdir "D:\DocumentSearch\opensearch\data" 2>nul
mkdir "D:\DocumentSearch\logs\opensearch" 2>nul
mkdir "D:\DocumentSearch\temp\opensearch" 2>nul

REM Copy custom configuration files
echo Copying configuration files...
copy /Y "C:\DocumentSearch\config\opensearch.yml" "%OPENSEARCH_HOME%\config\opensearch.yml" >nul
copy /Y "C:\DocumentSearch\config\jvm.options" "%OPENSEARCH_HOME%\config\jvm.options" >nul

echo.
echo Starting OpenSearch service (via NSSM)...
echo This may take 30-60 seconds...
echo.

REM Start OpenSearch2 Windows service (existing service)
%NSSM% start OpenSearch2

echo.
echo Waiting for OpenSearch to start...
timeout /t 30 /nobreak >nul

echo.
echo Checking OpenSearch status...

REM Check if OpenSearch is responding
curl -s http://localhost:9200 >nul 2>&1
if errorlevel 1 (
    echo WARNING: OpenSearch may still be starting...
    echo Wait 30 more seconds and check http://localhost:9200
) else (
    echo.
    echo ========================================
    echo OpenSearch is running!
    echo ========================================
    echo.
    curl -s http://localhost:9200 | findstr "cluster_name version"
)

echo.
echo OpenSearch UI: http://localhost:9200
echo Logs: D:\DocumentSearch\logs\opensearch\
echo.

pause
