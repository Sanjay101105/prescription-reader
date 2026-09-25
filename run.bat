@echo off
title Prescription Reader Launcher
echo ===================================================
echo           Starting Prescription Reader...
echo ===================================================
echo.

cd /d "%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Check .env
if not exist ".env" (
    echo [WARNING] .env file not found. Copying from .env.example...
    copy .env.example .env
)

:: Open browser after a short delay in background
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

echo Server running at http://localhost:8000
echo Opening browser...
echo.
echo (Press CTRL+C in this window to stop the server)
echo ===================================================

:: Start server
python -m uvicorn main:app --host 127.0.0.1 --port 8000

pause
