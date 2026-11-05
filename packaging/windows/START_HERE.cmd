@echo off
setlocal
title RoastSee NEXT to Artisan - read only
echo Keep this window open while using Artisan. Press Ctrl+C to stop.
echo This mode does not send start commands to the NEXT device.
"%~dp0RoastSeeNEXTBridge.exe" %*
set "BRIDGE_EXIT=%ERRORLEVEL%"
if not "%BRIDGE_EXIT%"=="0" pause
exit /b %BRIDGE_EXIT%
