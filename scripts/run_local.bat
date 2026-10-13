@echo off
REM Aerial Crowd Intelligence — Windows CMD Local Startup Script
echo ========================================================
echo   AERIAL CROWD INTELLIGENCE — LOCAL STARTUP (CMD)
echo ========================================================

cd /d "%~dp0\.."

REM Check for virtualenv
set PYTHON_EXE=.venv-win\Scripts\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=.venv\Scripts\python.exe
)

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment not found in .venv-win or .venv.
    echo Please run: python -m venv .venv-win ^&^& pip install -e ".\backend[dev]"
    pause
    exit /b 1
)

REM Ensure data folders exist
mkdir data\uploads 2>nul
mkdir data\processed 2>nul
mkdir data\results 2>nul
mkdir data\temporary 2>nul

REM Run migrations
echo [1/3] Running database migrations...
cd backend
..\%PYTHON_EXE% -m alembic -c alembic.ini upgrade head
cd ..

REM Start backend in separate window
echo [2/3] Launching FastAPI backend on http://127.0.0.1:8000...
start "CrowdLytics Backend" /min %PYTHON_EXE% -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

REM Start frontend
echo [3/3] Launching React Vite frontend on http://localhost:5173...
cd frontend
call npm run dev
cd ..
