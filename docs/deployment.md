> **Current access model:** authentication has been removed. Open the dashboard directly.
> Sessions, media, jobs and exports share one local workspace; historical authentication
> descriptions below are superseded. Legacy data is retained without reassignment.

# Local Operations & Deployment Guide

## 1. Execution Environments

Aerial Crowd Intelligence is designed as a **local-first, fully self-hosted academic project**. It provides two local execution workflows:

1. **Direct Native Local Mode (Windows / macOS / Linux):**
   Zero Docker requirement. Uses native Python virtual environment, SQLite (`crowdlytics.db`), in-process FastAPI `BackgroundTasks`, and Vite development server.
2. **Containerized Local Lab Mode (Docker Compose):**
   Full multi-container stack with PostgreSQL, Redis, Celery worker, FastAPI, and Nginx.

---

## 2. Direct Native Local Setup (Recommended for Development)

### 2.1 Backend Setup
```bash
# From workspace root:
python -m venv .venv-win
.\.venv-win\Scripts\pip install -e "./backend[dev]"
.\.venv-win\Scripts\pip install email-validator celery redis

# Initialize database tables and migrations:
cd backend
..\.venv-win\Scripts\alembic -c alembic.ini upgrade head
cd ..

# Run tests:
.\.venv-win\Scripts\pytest backend/tests

# Launch backend (loopback only):
.\.venv-win\Scripts\uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### 2.2 Frontend Setup
```bash
# In a new terminal from workspace root:
cd frontend
npm install
npm test -- --run
npm run build
npm run dev
```

### 2.3 Single-Command Windows Startup
Run the automated startup script:
```powershell
.\scripts\run_local.ps1
```
Or double-click `scripts\run_local.bat`.

---

## 3. Containerized Lab Setup (Docker Compose)

On machines equipped with Docker Desktop:
```bash
# Build and launch all services:
docker compose -f deployment/docker/compose.yaml up -d --build

# Inspect logs:
docker compose -f deployment/docker/compose.yaml logs -f backend worker

# Stop services safely:
docker compose -f deployment/docker/compose.yaml down
```

### Port Mappings (Strict Loopback Binding)
- **Frontend Dashboard:** `http://localhost:5173`
- **Backend API:** `http://localhost:8000`
- **Interactive Swagger Docs:** `http://localhost:8000/api/v1/docs`
- **Health Liveness:** `http://localhost:8000/health/live`
- **Health Readiness:** `http://localhost:8000/health/ready`
- **PostgreSQL Database:** `127.0.0.1:5432` (internal Docker networking)
- **Redis Queue:** `127.0.0.1:6379` (internal Docker networking)

---

## 4. Local Media Storage Management

Media assets are segregated into private directories under `data/`:
```text
data/
├── uploads/       # Raw uploaded aerial photographs and drone videos
├── processed/     # Resized frames, normalized crops, background masks
├── results/       # Exported CSV/JSON summaries, generated visual overlays
└── temporary/     # Intermediate frame sequences, optical flow scratch files
```
All directories are excluded from Git version control via `.gitignore`.

---

## 5. Database Maintenance & Backup/Restore

### 5.1 SQLite (Direct Local Mode)
```powershell
# Backup database:
.\scripts\backup_restore.ps1 -Action backup -BackupFile backup_2026.db

# Restore database:
.\scripts\backup_restore.ps1 -Action restore -BackupFile backup_2026.db
```

### 5.2 PostgreSQL (Docker Mode)
```bash
# Backup containerized PostgreSQL:
docker exec -t crowdlytics_db pg_dump -U crowdlytics crowdlytics > backup.sql

# Restore containerized PostgreSQL:
docker exec -i crowdlytics_db psql -U crowdlytics crowdlytics < backup.sql
```

---

## 6. Troubleshooting Guide

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **Port 8000 or 5173 already in use** | Stray server process | Identify process via `netstat -ano \| findstr :8000` and terminate via `taskkill /PID <PID> /F`. |
| **`ImportError: email_validator`** | Missing Pydantic dependency | Run `pip install email-validator` in the active virtual environment. |
| **OpenCV VideoCapture fails to open video** | Missing codec support | Ensure file is encoded in standard H.264/MP4 format. |
| **`TypeError: bcrypt` wrap bug** | Passlib 1.7.4 compatibility | Use the native `bcrypt.hashpw` / `bcrypt.checkpw` implementation in `app.auth.security`. |
| **Permission denied on media download** | Missing token header | Ensure requests include `Authorization: Bearer <token>` or use the UI export buttons. |
