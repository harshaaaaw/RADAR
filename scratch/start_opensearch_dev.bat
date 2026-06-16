@echo off
set OPENSEARCH_HOME=C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0
set OPENSEARCH_JAVA_HOME=%OPENSEARCH_HOME%\jdk
set OPENSEARCH_PATH_CONF=%OPENSEARCH_HOME%\config
set OPENSEARCH_JAVA_OPTS=-Xms4g -Xmx4g
cd /d "%OPENSEARCH_HOME%\bin"
opensearch.bat
