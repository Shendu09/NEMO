@echo off
REM NEMO Floating Desktop Agent Launcher
REM Double-click this file to start the clownfish agent

cd /d "%~dp0"

echo.
echo ================================================
echo   NEMO Floating Agent - Clownfish Mode
echo ================================================
echo.
echo   Starting floating desktop agent...
echo   Make sure NEMO server is running on port 8765
echo.
echo   Window will appear at bottom-right of screen
echo   Click the fish to open the chat panel
echo   Type a command and press Enter
echo.
echo ================================================
echo.

python nemo_float.py

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start NEMO Float
    echo Make sure you have:
    echo   1. Python 3.8+ installed
    echo   2. pywebview installed: pip install pywebview
    echo   3. nemo_float.py in the same directory
    echo   4. nemo_float.html in the same directory
    echo.
    pause
)
