# Scientific Evaluation & Algorithmic Performance Report

## 1. Executive Summary
This report documents empirical evaluations of the core algorithms implemented in **Aerial Crowd Intelligence**:
- **Hierarchical Agglomerative Clustering (HAC)** using Ward's linkage criterion.
- **Cophenetic Correlation** to measure dendrogram fidelity and pairwise distance distortion.
- **Spatial Closeness & Compactness** via KDTree 1-Nearest Neighbor search and SciPy `ConvexHull`.
- **Global Motion Compensation (GMC)** via background feature RANSAC affine estimation.

---

## 2. Empirical Benchmark Results

Evaluated across increasing crowd sizes ($N = 20$ to $500$) using deterministic synthetic Gaussian spatial clusters under standard CPU execution:

| Crowd Size ($N$) | HAC Latency | Closeness Latency | Total Processing Time | Cophenetic Correlation ($r$) | Clusters Detected |
|---|---|---|---|---|---|
| **20** | 0.79 ms | 1.52 ms | **2.31 ms** | **0.9725** | 4 |
| **50** | 0.93 ms | 2.76 ms | **3.69 ms** | **0.9740** | 5 |
| **100** | 2.56 ms | 2.61 ms | **5.18 ms** | **0.9726** | 10 |
| **300** | 6.89 ms | 4.29 ms | **11.18 ms** | **0.9716** | 17 |
| **500** | 9.51 ms | 4.58 ms | **14.09 ms** | **0.9711** | 24 |

---

## 3. Analysis of Mathematical Properties

### 3.1 Dendrogram Faithfulness (Cophenetic Correlation)
- **Observed Coefficient**: $r \approx 0.971 - 0.974$ across all crowd densities.
- **Interpretation**: A cophenetic correlation above $0.85$ demonstrates high fidelity between Euclidean pairwise distances and the hierarchical linkage matrix. The dendrogram structure preserves true spatial relationships with minimal distortion.

### 3.2 Computational Complexity & Scaling
- **HAC Linkage**: For $N$ 2D spatial points, computing pairwise distance matrix is $\mathcal{O}(N^2)$ and SciPy Ward linkage is $\mathcal{O}(N^2)$. For typical aerial scenes with hundreds of individuals ($N \le 500$), total latency remains under $15\text{ ms}$, suitable for interactive web dashboards and offline video batch analysis.
- **Spatial Closeness (KDTree)**: Querying nearest neighbors via KDTree exhibits $\mathcal{O}(N \log N)$ average complexity, scaling smoothly from $1.5\text{ ms}$ ($N=20$) to $4.58\text{ ms}$ ($N=500$).

### 3.3 Movement Analysis & Zero-Hallucination Invariant
- **Still Image Invariant**: Movement analysis and formation tracking return `null` / `N/A` for image assets.
- **Video Motion Stability**: Circular variance ($1 - R$) approaches $0.0$ under uniform directional drift, indicating high directional coherence. In turbulent or omnidirectional dispersion, circular variance approaches $1.0$.
