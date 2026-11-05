@echo off
setlocal
title RoastSee NEXT to Artisan - auto start live
echo This mode enters the live screen and starts NEXT live measurement.
echo Keep this window open while using Artisan. Press Ctrl+C to stop.
"%~dp0RoastSeeNEXTBridge.exe" --auto-start-live %*
set "BRIDGE_EXIT=%ERRORLEVEL%"
if not "%BRIDGE_EXIT%"=="0" pause
exit /b %BRIDGE_EXIT%
