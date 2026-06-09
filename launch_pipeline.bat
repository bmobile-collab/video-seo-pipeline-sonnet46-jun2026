@echo off
title Amazon Video SEO Pipeline - Layer 5

:: ── Set working directory to the script's location ──────────────────────────
cd /d "%~dp0"

:: ── Check Python ─────────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python not found in PATH.
    echo Please install Python 3.9+ and ensure it's on your PATH.
    pause
    exit /b 1
)

:: ── Install/check required packages ─────────────────────────────────────────
echo Checking required packages...
python -m pip install flask flask-cors python-dotenv --quiet --break-system-packages 2>nul
if errorlevel 1 (
    python -m pip install flask flask-cors python-dotenv --quiet
)

:: ── Check for .env ───────────────────────────────────────────────────────────
if not exist ".env" (
    echo.
    echo WARNING: No .env file found.
    echo Creating a template .env — add your ANTHROPIC_API_KEY before running.
    echo.
    (
        echo ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
        echo PIPELINE_DIR=C:\Users\Baruch\Desktop\Video-seo-4LYRS
        echo FFMPEG_DIR=C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin
        echo PROXY_PORT=5050
    ) > .env
    echo .env created. Edit it now, then run this launcher again.
    notepad .env
    pause
    exit /b 0
)

:: ── Set ffmpeg on PATH (read from .env if possible) ──────────────────────────
for /f "tokens=1,* delims==" %%a in (.env) do (
    if "%%a"=="FFMPEG_DIR" set FFMPEG_PATH=%%b
)
if defined FFMPEG_PATH (
    set "PATH=%FFMPEG_PATH%;%PATH%"
)

:: ── Launch proxy in its own window ───────────────────────────────────────────
echo.
echo Starting proxy server...
start "Video SEO Proxy" cmd /k "cd /d "%~dp0" && python proxy.py"

:: ── Wait for proxy to bind ───────────────────────────────────────────────────
echo Waiting for proxy to start...
timeout /t 3 /nobreak >nul

:: ── Open UI in default browser ───────────────────────────────────────────────
echo Opening pipeline UI...
start "" "http://127.0.0.1:5050"

echo.
echo ─────────────────────────────────────────────────────
echo   Layer 5 is running.
echo   UI:    http://127.0.0.1:5050
echo   Proxy: See the "Video SEO Proxy" console window.
echo   Close the proxy window to shut down.
echo ─────────────────────────────────────────────────────
echo.
