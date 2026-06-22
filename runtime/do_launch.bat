@echo off
start "" /b "C:\Users\DELL\Downloads\Redis\redis-server.exe" --port 6379 --loglevel notice
timeout /t 3 /nobreak >nul
start "" /b java -Xms256m -Xmx512m -jar "C:\Users\DELL\Music\DocumentSearch\tika\tika-server-2.9.2.jar" --port 9998 --host localhost
timeout /t 2 /nobreak >nul
start "" /b java -Xms256m -Xmx512m -jar "C:\Users\DELL\Music\DocumentSearch\tika\tika-server-2.9.2.jar" --port 9999 --host localhost
timeout /t 2 /nobreak >nul
