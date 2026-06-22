Set WshShell = CreateObject("WScript.Shell")

' Get the base path
BasePath = "C:\Users\DELL\Music\DocumentSearch"
RedisExe = "C:\Users\DELL\Downloads\Redis\redis-server.exe"
TikaJar = BasePath & "\tika\tika-server-2.9.2.jar"
OsHome = "C:\Users\DELL\Downloads\opensearch-2.18.0"

' Start Redis
WshShell.Run """" & RedisExe & """ --port 6379 --loglevel notice", 0, False

WScript.Sleep 2000

' Start Tika 9998
WshShell.Run "java -Xms256m -Xmx512m -jar """ & TikaJar & """ --port 9998 --host localhost", 0, False

WScript.Sleep 1000

' Start Tika 9999
WshShell.Run "java -Xms256m -Xmx512m -jar """ & TikaJar & """ --port 9999 --host localhost", 0, False

WScript.Sleep 1000

' Start OpenSearch with custom config
Dim osCmd
osCmd = "cmd /c """ & "set JAVA_HOME=" & OsHome & "\jdk && "
osCmd = osCmd & "set OPENSEARCH_JAVA_HOME=" & OsHome & "\jdk && "
osCmd = osCmd & "set OPENSEARCH_PATH_CONF=" & BasePath & "\config && "
osCmd = osCmd & "set OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m && "
osCmd = osCmd & "cd /d " & OsHome & "\bin && "
osCmd = osCmd & "opensearch.bat"""

WshShell.Run osCmd, 0, False

WScript.Echo "All services launched!"
