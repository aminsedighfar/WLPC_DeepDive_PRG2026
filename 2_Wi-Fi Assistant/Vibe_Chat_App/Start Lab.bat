@echo off
rem Double-click to start the vibe chat on Windows.
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv ^(one time only^)...
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo Could not install uv. Check your internet connection.
        pause
        exit /b 1
    )
)

rem A .venv copied from another computer (for example inside a zip) cannot run here.
if exist ".venv\" (
    ".venv\Scripts\python.exe" -c "" >nul 2>nul
    if errorlevel 1 (
        echo Rebuilding the Python environment for this computer...
        rmdir /s /q .venv
    )
)

echo Preparing the lab. The first launch downloads Python and packages ^(about a minute^).
uv run --quiet launcher.py
echo Chat stopped.
pause
