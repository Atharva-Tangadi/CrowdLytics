# Aerial Crowd Intelligence

**Hierarchical Clustering-Based Spatial Grouping, Closeness Estimation, and Collective Movement Analysis**

A local-first, fully self-hosted academic engineering system designed to analyze high-altitude aerial photographs and drone video footage for crowd-level spatial organization, hierarchical grouping, compactness, and collective movement dynamics.

---

## 1. System Overview & Core Capabilities

Aerial Crowd Intelligence is built from the ground up for **crowd-level and group-level insights**, completely omitting individual identity profiling or biometric identification.

### Analytical Capabilities by Mode

| Feature | Aerial Photograph (Image) | Drone Video | Technical Implementation |
| :--- | :---: | :---: | :--- |
| **Media Validation & Storage** | Yes (JPEG, PNG) | Yes (MP4, H.264) | Content inspection & private `data/uploads/` storage |
| **Spatial Localization** | Yes | Yes (sampled frames) | Multi-scale adaptive Otsu blob density contour segmentation |
| **Crowd Count Estimation** | Yes | Yes (time-series) | Group-level point summation; confidence-weighted |
| **Hierarchical Spatial Clustering** | Yes | Yes (per window) | SciPy Agglomerative Clustering (Ward, Complete, Average) |
| **Cophenetic Correlation ($r$)** | Yes | Yes | Tree fidelity verification ($r \ge 0.97$, minimal distortion) |
| **Spatial Closeness & Dispersion** | Yes | Yes | SciPy `cKDTree` 1-Nearest Neighbor search ($\mathcal{O}(N \log N)$) |
| **Convex Hull Area & Density** | Yes | Yes | SciPy `ConvexHull` polygon area; density per $1,000\text{ px}^2$ |
| **Camera Motion Compensation** | **Never** | Yes | Background Shi-Tomasi features + RANSAC affine registration |
| **Collective Movement Direction** | **Never** | Yes | Compensated velocity vectors & circular mean direction |
| **Temporal Formation Dynamics** | **Never** | Yes | Bipartite association (Merging, Splitting, Expanding, etc.) |
| **Zero-Motion Hallucination** | **Strict Invariant** | N/A | Still images unconditionally yield `null` for motion |
| **Authenticated Data Export** | Yes (JSON, CSV) | Yes (JSON, CSV) | Multi-tenant ownership verification & streaming downloads |

---

## 2. Technology Stack

- **Frontend:** React 18, TypeScript (strict mode), Vite, Tailwind CSS, Lucide icons, HTML5 Canvas overlay engine, Vitest.
- **Backend:** Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (declarative), Alembic migrations, native Bcrypt, HMAC-SHA256 JWT tokens.
- **Computer Vision & Scientific Algorithms:** OpenCV, SciPy (`scipy.cluster.hierarchy`, `scipy.spatial.cKDTree`, `scipy.spatial.ConvexHull`), scikit-learn, NumPy.
- **Data & Task Broker:** PostgreSQL, Redis, Celery worker (Containerized mode) / SQLite & FastAPI `BackgroundTasks` (Direct local host mode).
- **Storage:** Local private volume architecture (`data/uploads/`, `data/processed/`, `data/results/`, `data/temporary/`).
- **Orchestration:** Docker Compose with multi-stage builds.

---

## 3. Local Operational URLs

- **Frontend Web UI:** `http://localhost:5173`
- **Backend API:** `http://localhost:8000`
- **Interactive OpenAPI Documentation (Swagger):** `http://localhost:8000/api/v1/docs`
- **Liveness Health Check:** `http://localhost:8000/health/live`
- **Readiness Health Check:** `http://localhost:8000/health/ready`

*All services bind strictly to loopback (`127.0.0.1`) to ensure network isolation.*

---

## 4. Setup & Startup Instructions

The system provides dual execution paths:

### Method A: Direct Native Local Mode (Zero Docker Requirement)

#### 1. Backend Setup
```bash
# Create virtual environment and install backend dependencies:
python -m venv .venv-win
.\.venv-win\Scripts\pip install -e "./backend[dev]"
.\.venv-win\Scripts\pip install email-validator celery redis

# Initialize database schema & migrations:
cd backend
..\.venv-win\Scripts\alembic -c alembic.ini upgrade head
cd ..

# Launch FastAPI backend:
.\.venv-win\Scripts\uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

#### 2. Frontend Setup
```bash
# In a separate terminal from workspace root:
cd frontend
npm install
npm run dev
```

#### 3. Single-Command Startup Script (Windows)
```powershell
.\scripts\run_local.ps1
```
*(Or double-click `scripts\run_local.bat`)*

---

### Method B: Containerized Lab Setup (Docker Compose)

On machines equipped with Docker Desktop:
```bash
# Launch full stack (Postgres, Redis, Worker, Backend, Frontend):
docker compose -f deployment/docker/compose.yaml up -d --build

# View worker logs:
docker compose -f deployment/docker/compose.yaml logs -f worker

# Shutdown services safely:
docker compose -f deployment/docker/compose.yaml down
```

---

## 5. Automated Verification & Testing

### Running Backend & CV Tests
```bash
.\.venv-win\Scripts\pytest backend/tests
```
**Test Coverage (26 passing tests):**
- `test_health.py`: Liveness and database readiness probe checks.
- `test_cv_algorithms.py`: Preprocessing, blob localization, Ward/Complete/Average HAC comparisons, KDTree NN closeness, degenerate geometry, Lucas-Kanade optical flow, and group formation transitions.
- `test_api_workflow.py`: Authentication, sessions, media upload, job lifecycle, results retrieval, CSV/JSON export, cancellation, and media deletion.
- `test_security_qa.py`: Multi-tenant isolation defense, token rejection, corrupted upload rejection, cascade file deletion, worker failure recovery, and end-to-end video pipeline.

### Running Frontend Tests & Production Build
```bash
cd frontend
npm test -- --run    # Vitest unit suite
npm run build        # TypeScript type-check and Vite production bundle
cd ..
```

### Running Empirical Benchmark Suite
```bash
.\.venv-win\Scripts\python scripts/benchmark.py
```
**Empirical Host CPU Benchmark Results ($N = 20$ to $1,000$):**
- $N=20$: HAC $1.88\text{ ms}$, Closeness $12.97\text{ ms}$, Total $14.86\text{ ms}$, Peak RAM $68\text{ KB}$, Cophenetic $r=0.973$.
- $N=100$: HAC $4.28\text{ ms}$, Closeness $29.34\text{ ms}$, Total $33.61\text{ ms}$, Peak RAM $283\text{ KB}$, Cophenetic $r=0.973$.
- $N=500$: HAC $19.47\text{ ms}$, Closeness $38.80\text{ ms}$, Total $58.27\text{ ms}$, Peak RAM $6.85\text{ MB}$, Cophenetic $r=0.971$.
- Camera Motion Compensation: Latency $16.95\text{ ms}$, Sub-pixel shift error $< 0.0003\text{ px}$.

---

## 6. Demonstration Workflow

1. **Sign Up & Log In:** Navigate to `http://localhost:5173`, register an account, and log in.
2. **Create Session:** Add an analysis session in the sidebar (e.g. `City Plaza Demo`).
3. **Analyze Image:** Click **Analyze Media**, upload an aerial image (JPEG/PNG), configure the distance threshold $\tau$ (default $50\text{ px}$) and linkage (`Ward`), and click **Run Analysis Pipeline**.
4. **View Overlays & Metrics:** Review cluster bounding boxes, centroids, convex hull areas, mean nearest-neighbor distances, and density tables.
5. **Analyze Video:** Upload a drone video (MP4), run analysis, and observe camera motion compensation, collective movement angle in degrees, and temporal formation state (e.g., `converging`, `expanding`, `merging`, `splitting`).
6. **Export & Delete:** Click **Export JSON** or **Export CSV** to download authenticated results. Delete individual media files or delete the session to cascade removal of disk files.

---

## 7. Security & Privacy Guardrails

- **Privacy by Design:** No facial recognition, biometric profiling, or person re-identification.
- **Tenant Isolation:** Enforced server-side on every route (`WHERE user_id = current_user.id`). Unauthorized access returns HTTP 404 to avoid disclosing resource existence.
- **Upload Hardening:** Uploads validated via OpenCV image decoding headers; paths resolved against `DATA_ROOT` to prevent directory traversal. Files stored with UUIDv4 filenames outside web roots.
- **Network Isolation:** Development services bind exclusively to loopback (`127.0.0.1`).

---

## 8. Final Project Handover Checklist

- [x] Both aerial photographs (Image Mode) and drone videos (Video Mode) fully supported.
- [x] Zero-motion hallucination invariant strictly enforced on still images.
- [x] Hierarchical Agglomerative Clustering (HAC) implemented using SciPy (Ward, Complete, Average).
- [x] Cophenetic correlation ($r \ge 0.97$) empirically verified on local CPU.
- [x] Spatial closeness (KDTree 1-NN) and convex hull density calculated and unit-labeled.
- [x] Video optical flow paired with affine RANSAC camera motion compensation.
- [x] Group formation dynamics classified (merging, splitting, expanding, contracting, converging, dispersing).
- [x] Local media storage segregated under `data/uploads/`, `data/processed/`, `data/results/`, `data/temporary/`.
- [x] Authentication & authorization with native Bcrypt and JWT access tokens.
- [x] Asynchronous background task execution with progress reporting and cancellation.
- [x] Database migrations verified at head with Alembic.
- [x] All 26 backend tests and frontend Vitest tests pass cleanly.
- [x] Single-command local startup scripts provided (`scripts/run_local.ps1`, `scripts/run_local.bat`).
- [x] Database backup and restore utilities provided (`scripts/backup_restore.ps1`).
- [x] No cloud dependencies, paid services, or public exposures created.
