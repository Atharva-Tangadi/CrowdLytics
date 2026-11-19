> **Current video pipeline:** see [video playback fixes](video-playback-fixes.md). Real videos use the local overhead-person model; generated dot demonstrations must explicitly select **Synthetic blob demo only**. Old detector limitations below describe the prior version.

> **Current access model:** authentication has been removed. Open the dashboard directly.
> Sessions, media, jobs and exports share one local workspace; historical authentication
> descriptions below are superseded. Legacy data is retained without reassignment.

# Aerial Crowd Intelligence — User Guide & Demonstration Manual

## 1. System Overview
**Aerial Crowd Intelligence** is an authenticated, local-first academic platform designed to analyze the spatial grouping, closeness, and collective behavior of crowds observed in high-altitude aerial photographs and drone video footage.

The application strictly focuses on **group-level and crowd-level patterns**. It does not perform face recognition, biometric profiling, or person re-identification.

---

## 2. Core Operational Modes

### 2.1 Mode 1: Aerial Photograph Analysis
- **Supported Inputs:** High-resolution JPEG and PNG images.
- **Analytical Pipeline:**
  1. Image validation and resolution-aware downscaling ($\le 1920\text{ px}$).
  2. Multi-scale adaptive Otsu blob density localization for sub-20px heads/bodies.
  3. **Hierarchical Agglomerative Clustering (HAC)** with distance cut-off $\tau$.
  4. 1-Nearest Neighbor (NN) closeness evaluation via SciPy `KDTree`.
  5. Minimum bounding convex hull polygons and local density calculations.
- **Zero-Motion Guarantee:** Movement direction and formation dynamics are strictly disabled and returned as `null` / `N/A`. The system never hallucinates motion from a still image.

### 2.2 Mode 2: Drone Video Analysis
- **Supported Inputs:** MP4 video files.
- **Analytical Pipeline:**
  1. Configurable frame sampling (default: every 3--5 frames).
  2. Spatial point localization and HAC grouping per frame window.
  3. **Global Motion Compensation (GMC):** Lucas-Kanade optical flow on background features outside crowd clusters with RANSAC affine registration to subtract drone camera drift.
  4. Compensated crowd velocity vectors ($\vec{v}_{\text{crowd}} = \vec{v}_{\text{raw}} - \vec{v}_{\text{cam}}$).
  5. Circular mean collective direction ($\bar{\theta} \in [0^\circ, 360^\circ)$) and circular variance ($1 - R$).
  6. **Temporal Formation Transitions:** Tracks whether crowd clusters are Merging, Splitting, Expanding, Contracting, Converging, or Dispersing.

---

## 3. Step-by-Step Demonstration Workflow

### Step 1: Authentication & User Registration
1. Navigate to `http://localhost:5173`.
2. On the welcome screen, select **Sign up** to create an account (e.g. `analyst@crowdlytics.local` / `SecurePassword123`).
3. Log in. The JWT token is securely managed by the client application.

### Step 2: Create an Analysis Session
1. In the left sidebar under **Sessions**, type a session title (e.g., `City Plaza Demonstration`) into the input field.
2. Click the `+` button. The session will appear in your sidebar and automatically become active.

### Step 3: Analyze an Aerial Photograph
1. Click the **Analyze Media** button in the top right.
2. Drag and drop or browse for an aerial photograph (JPEG or PNG).
3. Review media metadata (width, height, file size).
4. Configure analytical parameters:
   - **Confidence Threshold:** Set between $0.20$ and $0.40$ (default: $0.30$).
   - **Distance Threshold ($\tau$):** Set the cophenetic distance cut-off in pixels (default: $50.0\text{ px}$).
   - **Linkage Method:** Select `Ward` (minimum variance), `Complete` (maximum distance), or `Average`.
5. Click **Run Analysis Pipeline**.
6. The animated progress bar displays stages:
   - `Loading media asset` $\to$ `Preprocessing image` $\to$ `Localizing crowd members` $\to$ `Performing hierarchical clustering` $\to$ `Computing closeness & spatial density` $\to$ `Analysis complete`.
7. **Inspect Results:**
   - **Canvas Overlay:** Review the color-coded bounding boxes, group cross-markers, and cluster tags.
   - **Metric Cards:** Inspect Total Crowd Count, Cluster Count, and Mean Closeness (NN distance).
   - **Hierarchy Table:** Inspect individual group centroids, convex hull areas, mean NN distances, and density per $1,000\text{ px}^2$.
8. **Export Data:**
   - Click **Export JSON** or **Export CSV** to download authenticated aggregate results.

### Step 4: Analyze a Drone Video
1. In the active session, click **Analyze Media**.
2. Select an MP4 video (e.g., sample drone footage).
3. Review video metadata: resolution, duration, frame rate, and frame count.
4. Click **Run Analysis Pipeline**.
5. Observe progress stages:
   - `Sampling video frames` $\to$ `Analyzing frame X` $\to$ `Finalizing video analysis results`.
6. **Inspect Video Results:**
   - Collective Direction: Displays circular mean angle in degrees (e.g., $352.5^\circ$).
   - Formation Dynamics: Displays classified state (e.g., `stationary`, `converging`, `expanding`, `merging`, `splitting`).
   - Group state breakdown in the hierarchy table.

### Step 5: Data Deletion & Session Cleanup
1. To delete an analysis session, hover over the session in the left sidebar and click the **Trash** icon.
2. Confirm deletion. The backend cascades database records and removes the physical media assets from `data/uploads/`.
