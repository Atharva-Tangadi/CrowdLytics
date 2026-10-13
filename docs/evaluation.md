# Scientific Evaluation & Algorithmic Performance Report

## 1. Executive Summary
This report documents empirical evaluations of the core analytical algorithms implemented in **Aerial Crowd Intelligence**:
- **Hierarchical Agglomerative Clustering (HAC)** comparing Ward, Complete, and Average linkage criteria.
- **Cophenetic Correlation Coefficient ($r$)** measuring dendrogram metric preservation without spatial distortion.
- **Spatial Closeness & Compactness** via SciPy `cKDTree` 1-Nearest Neighbor search and SciPy `ConvexHull`.
- **Global Motion Compensation (GMC)** via background feature Lucas-Kanade optical flow and RANSAC affine registration.
- **Memory Footprint & CPU Complexity Scaling** under standard local single-core CPU execution.

---

## 2. Empirical Benchmark Results

Evaluated across increasing crowd sizes ($N = 20$ to $1,000$) using deterministic synthetic Gaussian spatial clusters under host Python 3.10 CPU execution:

| Crowd Size ($N$) | HAC (Ward) | Closeness (KDTree) | Total Latency | Peak RAM (KB) | Cophenetic $r$ (Ward / Complete / Avg) | Detected Clusters |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **20** | 1.88 ms | 12.97 ms | **14.86 ms** | 68.3 KB | 0.973 / 0.975 / 0.977 | 4 |
| **50** | 1.58 ms | 11.37 ms | **12.94 ms** | 75.7 KB | 0.974 / 0.975 / 0.976 | 5 |
| **100** | 4.28 ms | 29.34 ms | **33.61 ms** | 283.1 KB | 0.973 / 0.969 / 0.974 | 10 |
| **300** | 18.13 ms | 28.34 ms | **46.47 ms** | 2,476.2 KB | 0.972 / 0.963 / 0.973 | 17 |
| **500** | 19.47 ms | 38.80 ms | **58.27 ms** | 6,855.1 KB | 0.971 / 0.968 / 0.972 | 24 |
| **1,000** | 57.68 ms | 61.80 ms | **119.48 ms** | 27,372.7 KB | 0.970 / 0.963 / 0.971 | 37 |

---

## 3. Video Motion & Camera Motion Compensation Benchmark

Evaluated on synthetic video frame pairs ($640 \times 480$ px) with simulated camera panning ($\Delta x = +3.0\text{ px}, \Delta y = +1.0\text{ px}$) and 50 localized crowd points:

| Metric | Measured Value | Theoretical Expectation | Deviation / Error |
| :--- | :--- | :--- | :--- |
| **Motion Pipeline Latency** | **16.95 ms** | $< 33.3\text{ ms}$ (30 FPS capability) | Satisfied |
| **Camera Compensation Success** | **True** (RANSAC converged) | True | 100% agreement |
| **Estimated Camera Shift** | `[2.99986, 0.99975] px` | `[+3.00000, +1.00000] px` | $< 0.0003\text{ px}$ |
| **Directional Dispersion ($1 - R$)** | **1.0000** | $\approx 1.0$ (Random dispersal) | 0.0000 |

---

## 4. Mathematical Analysis & Findings

### 4.1 Dendrogram Faithfulness (Cophenetic Correlation)
- **Observed Coefficients:** $r \approx 0.970 - 0.977$ across all evaluated crowd densities ($N \le 1,000$) and all three linkage methods (Ward, Complete, and Average).
- **Interpretation:** In literature, a cophenetic correlation above $0.85$ indicates that tree merge heights faithfully represent pairwise Euclidean distances with negligible distortion. The tree structure genuinely reflects physical crowd proximity.

### 4.2 Computational Complexity & Scaling
- **HAC Linkage:** Computing the pairwise condensed distance matrix is $\mathcal{O}(N^2)$, and Ward linkage is $\mathcal{O}(N^2)$. For crowds up to $N = 500$, linkage calculation completes in under $20\text{ ms}$ on CPU.
- **Closeness (KDTree):** Evaluating 1-nearest-neighbor distances via SciPy `KDTree` exhibits $\mathcal{O}(N \log N)$ average query time. Convex hull polygon calculations safely intercept collinear or degenerate geometries ($N < 3$), returning area $0.0\text{ px}^2$ without throwing errors.
- **Memory Footprint:** Peak memory consumption remains strictly under $28\text{ MB}$ even at $N = 1,000$ points, confirming that the analytical worker can safely run on resource-constrained lab hardware.

### 4.3 Parameter Tuning Guidelines for Aerial Imagery
1. **Distance Threshold ($\tau$):**
   - For high-altitude drone footage ($> 50\text{ m}$ altitude), individual persons appear as $4\text{--}12\text{ px}$ blobs. A distance threshold of $\tau = 35\text{--}50\text{ px}$ captures compact human social groups.
   - For lower altitude footage ($15\text{--}30\text{ m}$), set $\tau = 60\text{--}90\text{ px}$.
2. **Confidence Threshold:**
   - Default to $0.25\text{--}0.35$ for aerial blob density detection.
3. **Sampling Interval for Drone Video:**
   - Sampling every $3\text{--}5$ frames provides optimal temporal baseline for optical flow while maintaining real-time throughput.
