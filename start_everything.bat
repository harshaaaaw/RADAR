@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "ROOT=%CD%"
set "PYTHON_BIN=%ROOT%\.venv\Scripts\python.exe"
set "TIKA_JAR=%ROOT%\tika\tika-server-2.9.2.jar"

if not exist "%PYTHON_BIN%" (
  set "PYTHON_BIN=python"
)

if not exist "%TIKA_JAR%" (
  echo Tika JAR not found: %TIKA_JAR%
  exit /b 1
)

if not exist "%ROOT%\runtime\logs" mkdir "%ROOT%\runtime\logs"
if not exist "%ROOT%\runtime\temp\tika1" mkdir "%ROOT%\runtime\temp\tika1"
if not exist "%ROOT%\runtime\temp\tika2" mkdir "%ROOT%\runtime\temp\tika2"
if not exist "%ROOT%\runtime\temp\tika3" mkdir "%ROOT%\runtime\temp\tika3"
if not exist "%ROOT%\runtime\temp\tika4" mkdir "%ROOT%\runtime\temp\tika4"

echo Starting backend services (if available in PATH)...
where redis-server >nul 2>&1
if not errorlevel 1 start "Redis" cmd /c "redis-server > \"%ROOT%\runtime\logs\redis.log\" 2>&1"

where opensearch >nul 2>&1
if not errorlevel 1 start "OpenSearch" cmd /c "opensearch > \"%ROOT%\runtime\logs\opensearch.log\" 2>&1"

echo Starting Tika instances...
for %%P in (9998 9999 10000 10001) do (
  netstat -ano | findstr /R ":%%P .*LISTEN" >nul
  if errorlevel 1 (
    if %%P==9998 start "Tika %%P" cmd /c "java -Xms768m -Xmx768m -Djava.io.tmpdir=\"%ROOT%\runtime\temp\tika1\" -jar \"%TIKA_JAR%\" --port %%P > \"%ROOT%\runtime\logs\tika-%%P.log\" 2>&1"
    if %%P==9999 start "Tika %%P" cmd /c "java -Xms768m -Xmx768m -Djava.io.tmpdir=\"%ROOT%\runtime\temp\tika2\" -jar \"%TIKA_JAR%\" --port %%P > \"%ROOT%\runtime\logs\tika-%%P.log\" 2>&1"
    if %%P==10000 start "Tika %%P" cmd /c "java -Xms1g -Xmx1g -Djava.io.tmpdir=\"%ROOT%\runtime\temp\tika3\" -jar \"%TIKA_JAR%\" --port %%P > \"%ROOT%\runtime\logs\tika-%%P.log\" 2>&1"
    if %%P==10001 start "Tika %%P" cmd /c "java -Xms1g -Xmx1g -Djava.io.tmpdir=\"%ROOT%\runtime\temp\tika4\" -jar \"%TIKA_JAR%\" --port %%P > \"%ROOT%\runtime\logs\tika-%%P.log\" 2>&1"
  )
)

echo Running health check...
"%PYTHON_BIN%" src\main.py check
if errorlevel 1 (
  echo Health check failed. Verify Redis/OpenSearch/Tika/Java installation.
  exit /b 1
)

echo Initializing system...
"%PYTHON_BIN%" src\main.py init
if errorlevel 1 exit /b 1

echo Starting orchestrator and dashboard...
start "DocumentSearch Orchestrator" cmd /k "cd /d \"%ROOT%\" && \"%PYTHON_BIN%\" src\main.py start"
start "DocumentSearch Dashboard" cmd /k "cd /d \"%ROOT%\" && \"%PYTHON_BIN%\" -m streamlit run src\ui\dashboard.py --server.port 8501"

echo.
echo Startup complete.
echo Dashboard: http://localhost:8501
echo OpenSearch: http://localhost:9200
endlocal
