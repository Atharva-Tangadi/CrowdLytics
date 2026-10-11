# Computer Vision & Analytical Algorithms Guide

## 1. Preprocessing & Normalization
- **Resolution-Aware Resizing**: Downscales images exceeding $1920\text{ px}$ along the longest edge while preserving aspect ratio. Scale factor $s = \frac{W_{target}}{W_{orig}}$ is tracked to rescale coordinates back to original image space.
- **Region of Interest (ROI)**: Supports binary masking so calculations can be restricted to designated observation zones.

## 2. Localization
- **Adaptive Blob Density Detection**: Uses Gaussian blurring, Otsu adaptive thresholding, and contour filtering to identify head/person centers in high-altitude imagery where individual targets occupy 4–15 pixels.

## 3. Hierarchical Agglomerative Clustering (HAC)
- **Linkage Criterion**:
  - **Ward's Linkage**: Minimizes the total within-cluster variance. Pairs of clusters with minimum increase in variance are iteratively merged.
  - **Complete Linkage**: Merges clusters based on the maximum distance between points in each cluster.
- **Distance Cut-off ($\tau$)**: Partitions dendrograms into flat clusters where cophenetic distance does not exceed $\tau$ pixels.
- **Cophenetic Correlation Coefficient ($r$)**: Measures the correlation between cophenetic distances in the dendrogram and original Euclidean pairwise distances. Values $\ge 0.85$ indicate low hierarchical distortion.

## 4. Closeness & Spatial Density
- **$k$-Nearest Neighbor Distance**: Evaluated using `scipy.spatial.KDTree` ($k=1$) in $\mathcal{O}(N \log N)$ time.
- **Convex Hull Area**: Evaluates minimum bounding polygon area via SciPy `ConvexHull`. Intercepts collinear or degenerate geometry ($N < 3$) safely.
- **Spatial Density**: Area-normalized density expressed as individuals per $1,000\text{ px}^2$.

## 5. Collective Movement Analysis (Video Only)
- **Global Motion Compensation (GMC)**: Background feature extraction with Lucas-Kanade optical flow and RANSAC affine transformation estimation to subtract drone camera movement.
- **Circular Statistics**:
  - Dominant Direction: $\bar{\theta} = \text{atan2}\left(\sum \sin \theta_i, \sum \cos \theta_i\right) \pmod{360^\circ}$.
  - Circular Variance: $1 - R = 1 - \frac{\|\sum \vec{v}_i\|}{\sum \|\vec{v}_i\|} \in [0, 1]$.
- **Zero Movement Hallucination**: Movement and formation analysis are strictly unavailable for still images.

## 6. Group Formation Dynamics
- **Classification Categories**:
  - **Merging**: Decrease in macro cluster count between consecutive time windows.
  - **Splitting**: Increase in macro cluster count between consecutive time windows.
  - **Expanding**: Cluster convex hull area increase $> 20\%$ with increased dispersion.
  - **Contracting**: Cluster convex hull area decrease $> 20\%$ with reduced dispersion.
  - **Converging**: Mean nearest-neighbor distance decreases by $> 15\%$.
  - **Dispersing**: Mean nearest-neighbor distance increases by $> 15\%$.
  - **Stationary**: Stable spatial geometry.
