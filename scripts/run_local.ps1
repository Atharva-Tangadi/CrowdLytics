# Aerial Crowd Intelligence — Local Developer Startup Script (Windows PowerShell)
# Launches FastAPI backend on port 8000 and React Vite frontend on port 5173.

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  AERIAL CROWD INTELLIGENCE — LOCAL STARTUP" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = "$WorkspaceRoot\.venv-win\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "$WorkspaceRoot\.venv\Scripts\python.exe"
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python virtual environment not found in .venv-win or .venv." -ForegroundColor Red
    Write-Host "Please create a virtual environment first: python -m venv .venv-win" -ForegroundColor Yellow
    Exit 1
}

# 1. Initialize data storage directories
Write-Host "[1/4] Ensuring local data directories exist..." -ForegroundColor Green
$DataDirs = @("data\uploads", "data\processed", "data\results", "data\temporary")
foreach ($dir in $DataDirs) {
    $fullPath = Join-Path $WorkspaceRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}

# 2. Run Database Migrations
Write-Host "[2/4] Applying database migrations..." -ForegroundColor Green
Push-Location "$WorkspaceRoot\backend"
& $PythonExe -m alembic -c alembic.ini upgrade head
Pop-Location

# 3. Start Backend in Background Process
Write-Host "[3/4] Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Green
$BackendProcess = Start-Process -FilePath $PythonExe -ArgumentList "-m", "uvicorn", "app.main:app", "--app-dir", "$WorkspaceRoot\backend", "--host", "127.0.0.1", "--port", "8000", "--reload" -PassThru

# 4. Start Frontend
Write-Host "[4/4] Starting Vite frontend on http://localhost:5173..." -ForegroundColor Green
Push-Location "$WorkspaceRoot\frontend"
try {
    npm run dev
} finally {
    Write-Host "Stopping backend process (PID $($BackendProcess.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $BackendProcess.Id -ErrorAction SilentlyContinue
    Pop-Location
}
