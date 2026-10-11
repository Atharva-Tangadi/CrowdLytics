# Deployment & Operations Guide

## 1. Local Development Setup

### Backend
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "./backend[dev]"
alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --app-dir backend --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run build
npm run dev
```

---

## 2. Docker Compose Deployment (Recommended)

Run the full stack (PostgreSQL, Redis, Backend, Frontend):
```bash
docker compose -f deployment/docker/compose.yaml up -d --build
```

### Service Health Verification
- **Liveness Probe**: `http://localhost:8000/health/live`
- **Readiness Probe**: `http://localhost:8000/health/ready`
- **Swagger Documentation**: `http://localhost:8000/api/v1/docs`
- **Web UI**: `http://localhost`

---

## 3. Database Maintenance

### Generating Migrations
```bash
cd backend
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

### Database Backup & Restore
```bash
# Backup PostgreSQL container database
docker exec -t crowdlytics_db pg_dump -U crowdlytics crowdlytics > backup.sql

# Restore from backup
docker exec -i crowdlytics_db psql -U crowdlytics crowdlytics < backup.sql
```
