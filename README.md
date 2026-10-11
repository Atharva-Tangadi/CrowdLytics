# Aerial Crowd Intelligence

**Hierarchical Clustering-Based Spatial Grouping, Closeness Estimation, and Collective Movement Analysis**

An academic and production-grade full-stack system designed to analyze aerial photographs and drone video footage for crowd-level spatial organization and collective dynamics.

---

## Architecture Overview

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Lucide icons, Vitest.
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Pytest.
- **Computer Vision**: OpenCV, SciPy (Hierarchical Agglomerative Clustering), scikit-learn, NumPy.
- **Persistence**: SQLite (Local development default) / PostgreSQL (Production).
- **Deployment**: Docker & Docker Compose with multi-stage builds.

---

## Local Development Setup

### 1. Prerequisites
- Python 3.10+ (with `venv`)
- Node.js 20+ and npm

### 2. Backend Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e "./backend[dev]"

# Run tests
pytest backend/tests

# Start the API server
uvicorn app.main:app --app-dir backend --reload --port 8000
```
API docs available at: `http://localhost:8000/api/v1/docs`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run test
npm run build
npm run dev
```

### 4. Health Probes
- Liveness: `GET http://localhost:8000/health/live`
- Readiness: `GET http://localhost:8000/health/ready`

---

## Containerized Deployment

Run the complete multi-service stack with Docker Compose:
```bash
docker compose -f deployment/docker/compose.yaml up -d --build
```
