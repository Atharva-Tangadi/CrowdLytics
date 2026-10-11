"""Scientific benchmark and performance evaluation script."""
import time
import numpy as np
from app.cv.localization.detector import DetectionPoint
from app.cv.clustering.hac import HierarchicalClusterer
from app.cv.closeness.estimator import ClosenessEstimator
from app.cv.motion.analyzer import VideoMotionAnalyzer


def benchmark_pipeline(n_points_list=[20, 50, 100, 300, 500]):
    print("=" * 70)
    print("AERIAL CROWD INTELLIGENCE — SCIENTIFIC BENCHMARK & EVALUATION")
    print("=" * 70)

    clusterer = HierarchicalClusterer(distance_threshold=40.0, linkage_method="ward")
    estimator = ClosenessEstimator()

    results = []

    for n in n_points_list:
        # Generate synthetic crowd distributed in 3 distinct clusters
        np.random.seed(42)
        c1 = np.random.normal(loc=[50, 50], scale=8, size=(n // 3, 2))
        c2 = np.random.normal(loc=[180, 70], scale=10, size=(n // 3, 2))
        c3 = np.random.normal(loc=[120, 190], scale=12, size=(n - 2 * (n // 3), 2))
        all_coords = np.vstack([c1, c2, c3])

        points = [
            DetectionPoint(x=float(x), y=float(y), confidence=0.85)
            for x, y in all_coords
        ]

        # 1. Benchmark HAC
        t0 = time.perf_counter()
        clustering_res = clusterer.cluster(points)
        hac_latency_ms = (time.perf_counter() - t0) * 1000.0

        # 2. Benchmark Closeness & KDTree
        t0 = time.perf_counter()
        closeness_res = estimator.compute_all(clustering_res.clusters)
        closeness_latency_ms = (time.perf_counter() - t0) * 1000.0

        total_latency_ms = hac_latency_ms + closeness_latency_ms

        coph = clustering_res.cophenetic_correlation or 0.0

        results.append({
            "n": n,
            "clusters_detected": len(clustering_res.clusters),
            "hac_ms": hac_latency_ms,
            "closeness_ms": closeness_latency_ms,
            "total_ms": total_latency_ms,
            "cophenetic": coph,
            "mean_nn_px": closeness_res.global_mean_nn_distance
        })

        print(f"Crowd Size N={n:3d} | HAC: {hac_latency_ms:6.2f}ms | Closeness: {closeness_latency_ms:5.2f}ms | Total: {total_latency_ms:6.2f}ms | Cophenetic: {coph:.4f} | Clusters: {len(clustering_res.clusters)}")

    print("=" * 70)
    return results


if __name__ == "__main__":
    benchmark_pipeline()
