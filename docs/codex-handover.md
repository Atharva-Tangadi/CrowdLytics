# Aerial Crowd Intelligence — Technical Handover & Codex Architecture Specification

> **System Name:** Aerial Crowd Intelligence: Hierarchical Clustering-Based Spatial Grouping, Closeness Estimation, and Collective Movement Analysis  
> **Workspace Root:** `d:\CrowdLytics`  
> **Execution Constraint:** Mandatory Local-First, Fully Self-Hosted, Loopback-Bound (`127.0.0.1`). No cloud dependencies, paid APIs, or external inference.  
> **Primary Audience:** Codex / Engineering Team

---

## 1. Executive Summary & Objective

Aerial Crowd Intelligence is a specialized, privacy-first computer-vision and web platform that analyzes aerial still photographs and drone video feeds. The system answers macro-level crowd questions:
- How many people are estimated to be present?
- How are individuals spatially grouped into clusters?
- What is the internal closeness/dispersion of each group?
- In what direction are groups collectively moving?
- Are groups merging, splitting, expanding, contracting, converging, dispersing, or remaining stationary?
- How do these dynamics evolve progressively over time?

### Privacy Invariant
The platform strictly computes group-level and spatial topology centroids. It performs **no facial recognition, no biometric identification, and no person re-identification**.

### Zero-Motion Hallucination Invariant
Still images lack temporal progression. The system strictly returns `null` for velocity, directional headings, and formation transitions on image-only inputs.

---

## 2. Completed Milestones (Phases 0 through 7 + Progressive Video)

### Phase 0: Architecture & Local Planning
- Fully documented local execution layout and dependency hierarchy in `docs/` and project plans.
- Established strict loopback isolation (`127.0.0.1`).

### Phase 1: Local Environment & Storage Standard
- Partitioned private media storage under `data/`:
  - `data/uploads/` — raw ingested images and videos.
  - `data/processed/` — scaled and preprocessed frames.
  - `data/results/` — exported artifacts (JSON/CSV).
  - `data/temporary/` — scratch computation buffer.
- Initialized SQLite persistence (`backend/crowdlytics.db`) with Alembic migration versioning.

### Phase 2: Computer Vision Core Pipeline (`backend/app/cv/`)
1. **Preprocessing (`processor.py`):**
   - Resolution-aware resizing (bounding dimension $\le 1920\text{ px}$) preserving native aspect ratios.
   - Region of Interest (ROI) masking and adaptive contrast equalization.
2. **Crowd Localization (`detector.py`):**
   - High-altitude aerial head/person detection using Otsu adaptive thresholding and contour moment centroid extraction.
   - Deterministic test fixtures for synthetic pipeline validation.
3. **Hierarchical Agglomerative Clustering (`hac.py`):**
   - Unsupervised spatial grouping via SciPy (`scipy.cluster.hierarchy`).
   - Supports **Ward**, **Complete**, and **Average** linkage criteria.
   - Automatic dendrogram cophenetic correlation calculation ($r \ge 0.97$).
4. **Closeness & Spatial Density (`estimator.py`):**
   - Pairwise spatial distances and 1-Nearest Neighbor (1-NN) metrics using SciPy `cKDTree` ($O(N \log N)$ complexity).
   - Cluster convex hull surface area calculation using `scipy.spatial.ConvexHull`.
   - Density quantification per 1,000 square pixels ($\text{density} / \text{kpx}^2$).
5. **Video Motion Analysis & Global Camera Compensation (`analyzer.py`):**
   - Lucas-Kanade pyramidal sparse optical flow (`cv2.calcOpticalFlowPyrLK`).
   - Background Shi-Tomasi feature tracking + RANSAC affine transformation matrix estimation to isolate and eliminate drone/camera drift.
   - Circular mean heading angle $[0^\circ, 360^\circ)$ and circular variance (directional dispersion $[0, 1]$).
6. **Formation Transition Tracking (`tracker.py`):**
   - Temporal graph matching between consecutive time windows classifying macro and micro changes: `converging`, `dispersing`, `expanding`, `contracting`, `merging`, `splitting`, `stationary`.

### Phase 3: Backend API & Async Worker (`backend/app/`)
- FastAPI application with modular routers under `/api/v1` (`auth`, `sessions`, `media`, `jobs`).
- Native `bcrypt` password hashing with salt rounds 12 and JWT bearer tokens (`HS256`).
- Multi-tenant data isolation (`WHERE user_id = current_user.id`).
- Physical disk cascade deletion: Deleting a session or media asset immediately purges files from `data/uploads/`.
- Dual background execution support:
  - Default: FastAPI `BackgroundTasks` for turnkey single-machine operation.
  - Scalable: Local Docker Celery worker via Redis broker (`celery_worker.py`).

### Phase 4: Frontend Dashboard & Canvas Engine (`frontend/src/`)
- React 18, TypeScript, Vite, Tailwind CSS, and Lucide icons.
- Interactive HTML5 canvas compositing engine overlaying cluster bounding boxes, centroids, convex hulls, and motion vectors.
- Analytical parameter controls (sliders for confidence threshold, distance cut-off $\tau$, and linkage criteria).
- Blob streaming for secure downloads of media files and CSV/JSON reports.

### Phase 5 & 6: Integration, Security QA & Benchmarks
- Automated defense tests verifying cross-tenant access returns 401/404.
- Corrupted file, empty upload, and disguised `.exe` rejection validation.
- Empirical CPU scaling benchmarks for $N=20$ to $N=1,000$ points:
  - $N=20$: $14.86\text{ ms}$, Peak RAM $68\text{ KB}$, Cophenetic $r=0.973$.
  - $N=100$: $33.61\text{ ms}$, Peak RAM $283\text{ KB}$, Cophenetic $r=0.973$.
  - $N=500$: $58.27\text{ ms}$, Peak RAM $6.85\text{ MB}$, Cophenetic $r=0.971$.
  - $N=1,000$: $119.48\text{ ms}$, Peak RAM $27.37\text{ MB}$, Cophenetic $r=0.970$.
  - Camera motion subtraction: Latency $16.95\text{ ms}$, drift error $< 0.0003\text{ px}$.

### Phase 7: Progressive Video Playback Extension
- **Chunked Processing:** Added `AnalysisChunk` table and worker partitioning to process video in 2-second timestamped segments, streaming partial results before the entire video finishes.
- **Stable Group Identifiers (`StableGroupTracker`):** Binds clusters across time steps using centroid spatial proximity ($dist \le 85\text{ px}$) so group IDs ($G_1, G_2, \dots$) remain persistent instead of flickering with every frame.
- **Synchronized Video Overlay Player:** Canvas composited over `<video>` synchronized on `onTimeUpdate` and `onSeeked`, displaying:
  - Convex hull polygons with semi-transparent cluster coloring.
  - Movement direction arrows with arrowhead vectors.
  - 8-way compass labels (`UP`, `DOWN`, `LEFT`, `RIGHT`, `UP-RIGHT`, etc.).
  - Clean vs. Detailed mode toggles (showing density, closeness px, formation state).
  - Non-blocking buffering indicators when the player seeks ahead of processed chunks.

---

## 3. Technology Stack & Directory Tree

```
D:\CrowdLytics
├── backend
│   ├── alembic/                    # Database migration version scripts
│   ├── app
│   │   ├── api                     # FastAPI routers (auth, health, jobs, media, sessions)
│   │   ├── auth                    # Security, bcrypt hashing, JWT dependencies
│   │   ├── core                    # App configuration and settings
│   │   ├── cv                      # Pure CV pipeline (clustering, motion, formation, etc.)
│   │   ├── db                      # SQLAlchemy engine, session maker, base
│   │   ├── models                  # SQLAlchemy entity models
│   │   ├── schemas                 # Pydantic validation schemas
│   │   ├── storage                 # Local filesystem storage service
│   │   └── workers                 # Analysis worker and Celery wrapper
│   ├── tests                       # Pytest test suite (30 automated tests)
│   ├── crowdlytics.db              # SQLite development database
│   └── pyproject.toml              # Backend dependencies and configuration
├── frontend
│   ├── src
│   │   ├── features
│   │   │   ├── analysis            # ResultCanvas, MetricsOverview, NewAnalysisModal
│   │   │   └── auth                # AuthModal, AuthContext
│   │   ├── services                # Typed API client with token management
│   │   ├── types                   # TypeScript interface definitions
│   │   └── App.tsx                 # Core application shell & polling coordinator
│   ├── package.json
│   └── vite.config.ts              # Proxy forwarding /api to http://127.0.0.1:8000
├── data/                           # Private local storage (uploads, processed, results)
├── docs/                           # Architectural, algorithmic, and deployment docs
└── scripts/                        # Startup and backup automation scripts
```

---

## 4. Key Architectural Decisions & Bug Fixes

1. **IPv4 Loopback Binding (`127.0.0.1` vs `localhost`):**
   - In modern Node.js, `localhost` resolves to IPv6 `::1` by default. Because Uvicorn listens on IPv4 `127.0.0.1:8000`, proxying to `localhost:8000` resulted in `ECONNREFUSED` (HTTP 500 in browser).
   - **Resolution:** Explicitly configured Vite's dev proxy in `vite.config.ts` to target `http://127.0.0.1:8000`.
2. **Native Bcrypt Migration:**
   - `passlib.context.CryptContext` with `bcrypt 4.1+` caused an `AttributeError: module 'bcrypt' has no attribute '__about__'`.
   - **Resolution:** Replaced `passlib` with native `bcrypt.hashpw` and `bcrypt.checkpw`, truncating passwords to the standard 72-byte limit.
3. **Database Schema Auto-Synchronization:**
   - SQLite instances in reload processes could start before Alembic had executed.
   - **Resolution:** `Base.metadata.create_all(bind=engine)` is called directly in `app.main:create_app`, ensuring all tables exist immediately upon instantiation.
4. **Blob Streaming for Protected Media Downloads:**
   - Native HTML `<a>` tags and `<video src="...">` do not automatically attach `Authorization: Bearer <token>` headers.
   - **Resolution:** Implemented `api.getMediaBlobUrl()` which fetches media with the authentication header, converts the response to a local Object URL (`URL.createObjectURL(blob)`), and mounts it into the player.

---

## 5. Primary API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | User account registration |
| `POST` | `/api/v1/auth/login` | User login returning JWT bearer token |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile |
| `GET` | `/api/v1/sessions` | List sessions owned by authenticated user |
| `POST` | `/api/v1/sessions` | Create a new session |
| `POST` | `/api/v1/sessions/{id}/media` | Ingest image or video media asset |
| `GET` | `/api/v1/sessions/media/{id}/file` | Stream media file with HTTP Range support |
| `POST` | `/api/v1/sessions/{id}/analyze` | Enqueue crowd analysis job |
| `GET` | `/api/v1/jobs/{id}` | Poll job progress and status |
| `GET` | `/api/v1/jobs/{id}/chunks` | Progressively stream completed video chunks |
| `POST` | `/api/v1/jobs/{id}/cancel` | Cancel an active job |
| `GET` | `/api/v1/sessions/{id}/results` | Fetch complete aggregate analysis results |
| `GET` | `/api/v1/sessions/{id}/results/export` | Download analysis as structured CSV or JSON |
| `GET` | `/health/ready` | Database readiness check |
| `GET` | `/health/live` | Process liveness check |

---

## 6. Commands to Run Locally

### Automated Startup
```powershell
# PowerShell
.\scripts\run_local.ps1

# Windows Command Prompt
.\scripts\run_local.bat
```

### Manual Startup (Dual Terminal)

**Terminal 1 (Backend):**
```powershell
.\.venv-win\Scripts\Activate.ps1
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 (Frontend):**
```powershell
cd frontend
npm run dev
```

### Running Test Suites
```powershell
# Backend (Pytest)
.\.venv-win\Scripts\pytest.exe -v

# Frontend (Vitest)
cd frontend
npm test -- --run
```

### URLs
- **Web Interface:** `http://localhost:5173`
- **Swagger Documentation:** `http://127.0.0.1:8000/docs`
- **Health Check:** `http://127.0.0.1:8000/health/ready`
