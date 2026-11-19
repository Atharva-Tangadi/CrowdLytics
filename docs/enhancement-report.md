> **Current video pipeline:** see [video playback fixes](video-playback-fixes.md). Real videos use the local overhead-person model; generated dot demonstrations must explicitly select **Synthetic blob demo only**. Old detector limitations below describe the prior version.

> **Current access model:** authentication has been removed. Open the dashboard directly.
> Sessions, media, jobs and exports share one local workspace; historical authentication
> descriptions below are superseded. Legacy data is retained without reassignment.

# Guide-requested enhancement implementation report

## Scope and audit

The attached instructions explicitly require extending the working application.
React/FastAPI/OpenCV/SciPy, authentication, image/video input, HAC, exports and
progressive chunks are retained. The audit map is in `implementation-map.md`.
No user database, upload, local configuration or existing handover document was
modified by this implementation. Existing dirty database/journal changes were
present at the initial audit and are excluded from the source changes.

## Four enhancements

1. **Hull and centroid visualization.** `cv/geometry.py:convex_hull` filters nonfinite
   coordinates, deduplicates points and requires at least three noncollinear
   points. Degenerate hulls are null. Image hulls are stored in existing result
   summary JSON; video hulls remain in per-frame chunks. Centroids reuse HAC.
2. **Cluster direction and speed.** `ClusterMotionTracker` uses one-to-one assignment
   with proximity and size gates. Near-equivalent competing matches and large
   membership changes start new IDs with unavailable motion. Centroid displacement
   is corrected using the full accepted camera affine transform and divided by
   timestamp difference. No group borrows global motion. Smoothed speed is in px/s.
3. **Sudden crowd increase.** `CrowdIncreaseDetector` compares current count against
   a preceding rolling median and MAD, freezes the baseline during a candidate,
   requires absolute and relative increase plus persistence, and suppresses repeat
   alerts. It stores detection/resolution transitions with evidence and per-frame
   status. This is not proof of an organized flash mob.
4. **Static footage.** Static and auto modes retain video and photograph support.
   Static mode permits identity motion on similar low-texture frames. Background
   feature registration checks drift where possible; zoom, scene inconsistency or
   registration failure resets count comparisons. Uncertain camera observations
   do not produce speed. Stationary motion is zero; missing motion is null.

## Formulas and conventions

- Centroid: arithmetic mean of member coordinates.
- Speed: norm(current centroid - camera-transformed previous centroid) / elapsed
  seconds, followed by configurable exponential velocity smoothing.
- Angle: degrees(atan2(-dy, dx)) modulo 360. Right=0, up=90, left=180, down=270.
- Directions are image-relative, never geographic compass measurements.
- No calibration is implemented, so metres/second is never reported.
- Density and spacing retain the existing pixel-based algorithms and semantics.
- Video final count and group table describe the last sampled frame, not unique
  visitors or whole-video average occupancy.

## State and persistence

Event states: WARMING_UP, NORMAL, CANDIDATE, DETECTED, COOLING_DOWN, RESOLVED;
UNAVAILABLE for unreliable input and DISABLED when configured off. Percentage is
null for a zero baseline. Resolution requires count <= baseline + half the
absolute threshold after cooldown; an elevated plateau never emits repeat alerts.
Invalid observations interrupt candidate persistence and discard baseline history.

Existing `summary_data_json` and `frame_data_json` carry annotation version 2,
events, hulls, camera status, timestamp source, configuration and motion units.
No new columns are needed. The result API exposes its exact media_asset_id.
Legacy version-1 video angles remain clockwise and are drawn with their old
convention; legacy displacement is explicitly labeled rather than called px/s.
Old image results lack hull vertices and need reanalysis to show hulls.

## Defaults and configuration

All per-run options are validated in `AnalysisConfigRequest` and persisted.

| Option | Default |
|---|---|
| camera_mode | auto; select static for a fixed monitored scene |
| sample_interval_frames | 5 |
| chunk_duration_sec | 2 seconds |
| association_distance_px | 85 original-image pixels |
| motion_min_displacement_px | 1.5 pixels per observation |
| motion_smoothing | 0.5; 1 disables smoothing |
| crowd_increase.enabled | true |
| window_seconds | 10 |
| min_history_seconds | 3 |
| min_samples | 5 |
| min_absolute | 15 detected points |
| min_percent | 50 |
| mad_multiplier | 3 |
| persistence_seconds | 1 |
| cooldown_seconds | 10 |
| max_gap_seconds | 3 |

The baseline window must exceed minimum history. Very sparse sampling may not
collect sufficient baseline samples; choose settings appropriate to source FPS.
The UI exposes camera mode, event enablement, absolute/relative thresholds,
persistence and baseline window. Other validated options are available through
the existing analyze API. Overlay toggles control hulls, centroids, arrows, speed,
events and detailed metrics. Arrow length is a display setting, not a speed scale.

Example request body for `POST /api/v1/sessions/{id}/analyze`:

```json
{
  "media_asset_id": "the-uploaded-media-id",
  "camera_mode": "static",
  "sample_interval_frames": 5,
  "motion_min_displacement_px": 1.5,
  "crowd_increase": {
    "min_absolute": 15,
    "min_percent": 50,
    "persistence_seconds": 1
  }
}
```

Example valid moving annotation:

```json
{"group_id":1,"motion_speed":8.0,"speed_unit":"px/s",
 "motion_angle_deg":0.0,"direction_label":"RIGHT","motion_status":"MOVING"}
```

First observations return null speed and COLLECTING_HISTORY. Ambiguous observations
return unavailable motion, not a fabricated zero. Motion confidence is a heuristic
availability indicator, not a calibrated statistical probability.

## Related correctness fixes

- Per-job media selection and cancellation of stale UI requests prevent cross-job
  overlays. Object URLs are revoked on replacement.
- Causal binary-search annotation lookup never selects future frames and rejects
  annotations beyond coverage. Legacy annotations have bounded coverage too.
- Canvas uses intrinsic media dimensions and the same responsive aspect ratio as
  the video. Arrow geometry honors both angle versions.
- Chunk polling accepts `after_index`; the client merges new chunks by ID.
- Cooperative video cancellation and conditional completion preserve cancelled
  status. Decode handles are released on failure/cancellation.
- Upload byte limits and video duration/metadata validation are enforced; private
  path checks use actual ancestry instead of string prefixes.
- Docker enables Celery dispatch, declares the PostgreSQL driver and permits
  configured-size uploads through Nginx. Vite binds to loopback.
- Alembic now versions analysis_chunks and tolerates its prior create_all creation.
- New conftest isolates every backend test in temporary storage/database, including
  the legacy fixtures that drop tables. Never run those fixtures against user data.

## Run locally

From repository root:

```powershell
.\.venv-win\Scripts\python.exe -m pip install -e "./backend[dev]"
cd frontend
npm ci
cd ..
.\scripts\run_local.ps1
```

The startup script applies Alembic migrations. This task tested migration on a
temporary fresh database; it deliberately did not migrate the user's database.
Back up the existing database and uploads before applying migrations locally.
Frontend: http://127.0.0.1:5173 ; API docs: http://127.0.0.1:8000/api/v1/docs .
Docker alternative: `docker compose -f deployment/docker/compose.yaml up -d --build`.
Docker services were not launched during this task.

## Tests and verification

```powershell
.\.venv-win\Scripts\python.exe -m pytest backend/tests
cd frontend
npm test
npm run build
```

Verified: 55 backend tests passed in the full regression run, plus the subsequently
added active-cancellation test passed separately (56 tests total across those
runs). Five frontend tests passed; TypeScript/Vite production build passed.
Tests cover directional/diagonal/stationary/jitter motion, irregular timestamps,
ambiguous association, affine coordinate compensation, hull degeneracy, robust
counts, zero baseline, spikes, gradual growth, persistence/cooldown/resolution,
static video, event persistence, media ownership, chunk cursors, exports,
cancellation, fresh migrations, causal seeking and image canvas coordinates.
Existing tests were preserved. No real-world accuracy claim is made.

Windows sandbox restricted Python's event-loop socketpair; backend API tests were
run with local socket access using the same isolated test database/storage.
Non-failing warnings: Starlette/httpx deprecation and Node CommonJS/ESM warnings.

## Guide demonstration

1. Run `python scripts/generate_demo.py` with the project environment. It refuses
   to overwrite existing demo files. Synthetic files are generated in
   `data/temporary/guide-demo/` (also generated during this task).
2. Start the app, register/login and create a session named Image demonstration.
3. Upload clusters.png and analyze. Show two spatial groups, hulls and centroids;
   toggle hulls and centroids. Explain that still-image speed is unavailable.
4. Create another session, upload static-crowd-increase.mp4 and select Static drone.
5. Analyze using defaults. The synthetic group moves right about 8 px/s. The
   count rises from 3 to 27 at approximately 5 seconds; persistence should confirm
   an increase around 6 seconds, subject to decoding and the heuristic detector.
6. Seek before and after the increase. Show time-aligned event evidence and arrows;
   toggle speed/events/details. A single sustained increase produces one alert.
7. Export JSON to inspect annotations/configuration/events, and CSV for group speeds.
8. Start another video analysis and use Cancel analysis to demonstrate cancellation.

## Limitations and intentionally deferred work

- The existing blob detector remains the default. No learned model weights or
  external inference were downloaded. Aerial detector/point-model training,
  SAHI, density estimation, ByteTrack and real-ground calibration discussed as
  alternatives require a separate data/model evaluation effort; they are not
  claimed implemented by these four enhancements.
- Synthetic tests demonstrate logic, not person-detection accuracy or safety.
- Low-texture static mode assumes similar frames have a fixed camera; subtle
  unobservable motion cannot be distinguished perfectly. Auto mode is conservative.
- Registration handles modest affine motion; parallax, large zoom and scene cuts
  can make results unavailable. Count alerts require a stable monitored scene.
- Group IDs restart after disappearance, large membership changes or ambiguity;
  there is no biometric or individual re-identification.
- Existing formation classifier and degenerate-density fallback remain heuristic.
- OpenCV presentation timestamps are preferred; FPS fallback is explicitly recorded.
  Annotation coverage uses the configured sample interval; irregular long gaps are
  deliberately left without an overlay rather than displaying stale results.
- Media playback still uses authenticated Blob loading and may use substantial
  browser memory for large files. Range-delivery redesign is deferred.
- Celery/Redis/PostgreSQL deployment was configuration-reviewed, not integration-run.

## Source file inventory

Created: geometry.py, motion/groups.py, motion/scene.py,
formation/crowd_increase.py, migration 7b821a01_chunks.py, backend tests/conftest.py,
test_enhancements.py, test_enhancement_workflow.py, test_migrations.py,
frontend annotations.ts, annotations.test.ts, ResultCanvas.test.tsx,
scripts/generate_demo.py, docs/implementation-map.md, this report.

Updated: backend schemas/api.py, models/entities.py, api/v1/jobs.py,
api/v1/media.py, storage/service.py, workers/analysis_worker.py, pyproject.toml;
frontend App.tsx, ResultCanvas.tsx, MetricsOverview.tsx, NewAnalysisModal.tsx,
services/api.ts, types/api.ts, vite.config.ts, nginx.conf;
deployment/docker/compose.yaml and README.md.
