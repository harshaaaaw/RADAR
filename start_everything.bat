@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "ROOT=%CD%"
set "PYTHON_BIN=C:\Users\DELL\AppData\Local\Programs\Python\Python311\python.exe"
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

echo Starting backend services (Redis & OpenSearch)...
set "REDIS_BIN=C:\Users\DELL\Downloads\Redis\redis-server.exe"
if exist "%REDIS_BIN%" (
  echo Starting Redis...
  start "Redis" cmd /c "\"%REDIS_BIN%\" > \"%ROOT%\runtime\logs\redis.log\" 2>&1"
) else (
  echo Redis not found at %REDIS_BIN%
)

set "OPENSEARCH_HOME=C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0"
if exist "%OPENSEARCH_HOME%\bin\opensearch.bat" (
  echo Copying configurations to OpenSearch...
  copy /Y "%ROOT%\config\opensearch.yml" "%OPENSEARCH_HOME%\config\opensearch.yml" >nul
  copy /Y "%ROOT%\config\jvm.options" "%OPENSEARCH_HOME%\config\jvm.options" >nul
  echo Starting OpenSearch...
  start "OpenSearch" cmd /c "cd /d \"%OPENSEARCH_HOME%\bin\" && call opensearch.bat > \"%ROOT%\runtime\logs\opensearch.log\" 2>&1"
) else (
  echo OpenSearch not found at %OPENSEARCH_HOME%
)

echo Starting Tika instances...
for %%P in (9998 9999) do (
  netstat -ano | findstr /R ":%%P .*LISTEN" >nul
  if errorlevel 1 (
    if %%P==9998 start "Tika %%P" cmd /c "java -Xms768m -Xmx768m -Djava.io.tmpdir=\"%ROOT%\runtime\temp\tika1\" -jar \"%TIKA_JAR%\" --port %%P > \"%ROOT%\runtime\logs\tika-%%P.log\" 2>&1"
    if %%P==9999 start "Tika %%P" cmd /c "java -Xms768m -Xmx768m -Djava.io.tmpdir=\"%ROOT%\runtime\temp\tika2\" -jar \"%TIKA_JAR%\" --port %%P > \"%ROOT%\runtime\logs\tika-%%P.log\" 2>&1"
  )
)

echo Waiting 35 seconds for services to initialize...
timeout /t 35 /nobreak >nul

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
