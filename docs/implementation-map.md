> **Current access model:** authentication has been removed. Open the dashboard directly.
> Sessions, media, jobs and exports share one local workspace; historical authentication
> descriptions below are superseded. Legacy data is retained without reassignment.

# Enhancement implementation map

Audit completed before implementation. Existing stack: React/TypeScript/Vite/Tailwind,
FastAPI/Pydantic/SQLAlchemy, OpenCV/SciPy/NumPy, optional Celery/Redis, SQLite or PostgreSQL.

| Requirement | Reuse | Gap and implementation location |
|---|---|---|
| Hulls and centroids | `cv/clustering/hac.py:HierarchicalClusterer`, `cv/closeness/estimator.py`, `ResultCanvas.tsx` | Image hull vertices are not persisted; video degeneracies become fake polygons. Add shared geometry helper and persist annotations in existing summary JSON. |
| Cluster motion | `analysis_worker.py:StableGroupTracker`, `cv/motion/analyzer.py` | Greedy IDs and optical-flow magnitude lack elapsed time; scaled coordinates are inconsistent. Add conservative centroid association, timestamped px/s, camera registration quality and explicit statuses. Preserve legacy optical-flow API. |
| Sudden increase | Existing frame count and chunk JSON | Add configurable robust historical baseline, persistence, cooldown and resolution state machine; persist transitions and evidence. |
| Static video | Existing OpenCV decode and chunk pipeline | Add explicit static/auto camera modes, zero-versus-unknown handling, timestamp fallback and scene reset. |
| UI/API | Existing auth, job/result APIs, Canvas, MetricsOverview, NewAnalysisModal | Extend typed annotations and controls; use exact job media; causal bounded overlay lookup. |

Related fixes: cooperative cancellation, private-path validation, upload limits,
Celery compose switch/PostgreSQL driver, missing chunk migration, loopback Vite,
isolated tests. No existing database or uploaded dataset will be migrated or reset
by this implementation task. No model weights will be downloaded implicitly.

Verification: pure synthetic geometry/motion/event tests, isolated image/video API
regressions, frontend synchronization/control tests and production build.
Real-world detector accuracy requires labeled aerial data and is not asserted.
