@echo off
REM OpenSearch Startup with App Config
set JAVA_HOME=C:\Users\DELL\Downloads\opensearch-2.18.0\jdk
set OPENSEARCH_JAVA_HOME=C:\Users\DELL\Downloads\opensearch-2.18.0\jdk
set OPENSEARCH_PATH_CONF=C:\Users\DELL\Music\DocumentSearch\config
set OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m
cd /d C:\Users\DELL\Downloads\opensearch-2.18.0\bin
call opensearch.bat
