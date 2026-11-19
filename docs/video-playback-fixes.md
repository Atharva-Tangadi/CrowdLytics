# Video counting, cluster continuity and stored analytics

The supplied screen recording was inspected as evidence, not as instructions.
Its corresponding uploaded crosswalk video was found in the existing database.
The old run counted only a handful of contrast blobs and its metric cards showed
the last analyzed frame rather than the playback position. Frequent cluster
reassignment prevented useful motion estimates.

## Changes

- Real footage defaults to **YOLO11s overhead-person**, tiled at 384px with a
  640px model input. It runs through the existing OpenCV DNN dependency. Model
  source/revision, SHA-256 and attribution are recorded in `backend/models/`.
  Weights are installed locally and are not downloaded during analysis.
- Default UI confidence is 0.25. A 0.9 threshold, as used in the recorded run,
  discards difficult detections. The old blob algorithm is explicitly a synthetic
  demonstration option, and tests select it for dot fixtures.
- A learned-model run uses anonymous point tracks and forward/backward-checked
  Lucas–Kanade flow from previous locations. This supplies velocities even when
  the group centroid changes due to member entry/exit. Measurements are original
  image px/s. Camera uncertainty suppresses motion; static mode is explicit.
- Groups retain membership-based IDs. New nearby tracked people may join a
  group; an independent frame's HAC label no longer replaces its identity.
  Spatial-neighborhood grouping is the default UI option; HAC remains selectable.
- Short detection misses can be bridged by valid optical flow for at most 0.6s.
  Such observations are labeled TRACKED, separately from visible detections.
  A group remains while tracked members remain; an exited group is not painted
  indefinitely. Sustained spatial separation or coherent opposing flow is split
  only after 0.75s, preserving the parent ID for the largest child.
- Hulls and centroids update with tracked members. One/two-member groups use a
  padded bounding rectangle instead of an invalid polygon. Direction arrows are
  fixed-length display aids. Opposing flows may correctly report MIXED DIRECTIONS.
- Playback now has its own count cards, group table, count timeline and group
  lifetimes. Values change at analyzed timestamps; seeking uses causal coverage,
  never the final count or a future sample. Playback pauses if it overtakes
  progressive analysis and resumes when its segment is ready.
- Every sample persists count, tracked count, groups, IDs, geometry, motion,
  spatial metrics, camera/detector status and events in AnalysisChunk. A weighted
  occupancy summary and per-group lifetimes are saved in the final result JSON.
- `GET /api/v1/jobs/{id}/analytics` restores the stored timeline.
  `/analytics/export?format=json|csv` exports all samples, rather than only final
  groups. CSV repeats the frame count per group row; do not sum those repeated
  counts as independent people. JSON retains hull vertices and member track IDs.
- A **Reanalyze this media with improved detector** button reuses an existing
  upload. Old runs remain saved, with a notice that reanalysis is needed.

## Setup and use

```powershell
.\.venv-win\Scripts\python.exe scripts/setup_person_model.py
.\scripts\run_local.ps1
```

The selected model is already installed in this workspace. On another machine,
setup downloads one 37.9MB ONNX file and verifies a pinned checksum. There are no
new PyTorch dependencies and all inference remains local. Docker builds include
the locally installed weights; run setup before building on a fresh checkout.

For a fixed-camera crosswalk: choose Overhead person model, Spatial neighborhoods,
confidence 25%, distance 40–50px and Static drone. Distance is a scene-dependent
grouping parameter, not a calibrated social distance. Use Auto for camera drift;
large camera/scene changes invalidate continuity.

Refresh the dashboard after a saved analysis finishes outside the browser. Select
its session and play or seek. The prominent count and group rows follow playback.
Use Download timeline JSON/CSV for the stored time series.

## Validation and limits

Tests cover tiled coordinate mapping and duplicate suppression, member continuity
across temporary missed detections, measured direction, mixed flows, delayed
splitting, timestamp count changes, persistence/export round trips, prior APIs,
image/video regressions and login-free access. All use isolated test databases.

The actual crosswalk was additionally processed in an isolated database before
saving a new run in the workspace. The old runs/uploads were preserved. Full-clip
validation has 60 samples over approximately 9.91s; candidate detections vary
from 69 to 155. These are estimates, not ground-truth validation or unique-person
counts. Several tracks retain IDs over all 60 samples; groups also enter, leave
and split. Final verification after threshold recovery: 67 backend tests, 8 frontend tests, production build.

The overhead model was selected after comparing generic and head-localization
models on the source footage; those candidates missed most of this top-down
scene. The chosen weights still have false positives/negatives and are not a
replacement for labeled aerial evaluation. Source-published metrics must not be
represented as accuracy on this video. No physical speed calibration is present.
Processing on CPU can be slower than playback; buffering is intentional.

Model: https://huggingface.co/chanubc/overhead-person-yolo11
Upstream inference/export reference: https://docs.ultralytics.com/integrations/onnx/


## Later all-zero runs: cause and recovery

The later screen recording was traced to two saved runs using a 0.90 minimum
model score. The earlier positive run used 0.25, with the same model checksum and
source media. All 60 samples in each strict run contained zero accepted detections;
this was a filter outcome, not lost annotations or missing model weights.

A source-frame check measured a maximum score of about 0.827 and 123 candidates
at 0.25, while correctly returning zero at 0.90. Candidate diagnostics are now
computed in the same inference pass and persisted with new frame annotations.
The user's selected threshold is never silently lowered.

The setup screen labels the control Minimum detection score, explains that it is
not model accuracy, warns about strict settings and offers an explicit 25% reset.
Empty saved runs show an explanation and a button to reopen an earlier positive
run. Saved analysis history lists threshold, peak count and status; selected-run
results are retrieved by job ID, rather than accidentally returning the latest
session result when an earlier run was chosen.

API additions: GET /api/v1/sessions/{session_id}/jobs and
GET /api/v1/jobs/{job_id}/results. Missing resources retain 404 behavior.

A new run (63246788-0704-40d7-b1b4-b3dd42eb7b8f) was saved in demo 2 using the
latest settings with only the threshold changed to 0.25. It completed with 60
samples, 69–155 candidate detections and stored clusters/motion/analytics. Prior
runs and source media were preserved. The running local API was checked directly:
it serves five saved runs and the new completed 60-sample timeline.
