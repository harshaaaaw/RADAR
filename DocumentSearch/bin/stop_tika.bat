@echo off
REM ============================================================================
REM Enterprise Document Search - Stop All Tika Instances
REM ============================================================================

REM Set NSSM path
set NSSM="C:\Users\hp212560601\Tools\nssm\nssm-2.24-101-g897c7ad\win64\nssm.exe"

echo ========================================
echo Stopping All Tika Instances
echo ========================================
echo.

REM Stop all Tika Windows services
echo Stopping Tika services (via NSSM)...

%NSSM% stop Tika-9998
%NSSM% stop Tika-9999
%NSSM% stop Tika-10000
%NSSM% stop Tika-10001
%NSSM% stop Tika-10002
%NSSM% stop Tika-10003
%NSSM% stop Tika-10004
%NSSM% stop Tika-10005

echo.
echo All Tika instances stopped.
echo.

REM Clean up temp files (optional)
choice /C YN /M "Clean up temp files?"
if errorlevel 2 goto :END
if errorlevel 1 goto :CLEANUP

:CLEANUP
echo Cleaning temp directories...
rmdir /s /q "D:\DocumentSearch\temp\tika1" 2>nul
rmdir /s /q "D:\DocumentSearch\temp\tika2" 2>nul
rmdir /s /q "D:\DocumentSearch\temp\tika3" 2>nul
rmdir /s /q "D:\DocumentSearch\temp\tika4" 2>nul
rmdir /s /q "D:\DocumentSearch\temp\tika5" 2>nul
rmdir /s /q "D:\DocumentSearch\temp\tika6" 2>nul
rmdir /s /q "D:\DocumentSearch\temp\tika7" 2>nul
rmdir /s /q "D:\DocumentSearch\temp\tika8" 2>nul
echo Temp files cleaned.

:END
echo.
pause
