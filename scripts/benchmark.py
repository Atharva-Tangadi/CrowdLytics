"""Scientific benchmark and performance evaluation script.
Profiles latency, memory footprint, cophenetic correlation, and optical flow on local hardware.
"""
import time
import tracemalloc
import numpy as np
import cv2
from app.cv.localization.detector import DetectionPoint
from app.cv.clustering.hac import HierarchicalClusterer
from app.cv.closeness.estimator import ClosenessEstimator
from app.cv.motion.analyzer import VideoMotionAnalyzer


def benchmark_pipeline(n_points_list=[20, 50, 100, 300, 500, 1000]):
    print("=" * 80)
    print("AERIAL CROWD INTELLIGENCE — EMPIRICAL BENCHMARK & EVALUATION")
    print("=" * 80)

    clusterer_ward = HierarchicalClusterer(distance_threshold=40.0, linkage_method="ward")
    clusterer_complete = HierarchicalClusterer(distance_threshold=40.0, linkage_method="complete")
    clusterer_avg = HierarchicalClusterer(distance_threshold=40.0, linkage_method="average")
    estimator = ClosenessEstimator()

    results = []

    for n in n_points_list:
        np.random.seed(42)
        c1 = np.random.normal(loc=[50, 50], scale=8, size=(n // 3, 2))
        c2 = np.random.normal(loc=[180, 70], scale=10, size=(n // 3, 2))
        c3 = np.random.normal(loc=[120, 190], scale=12, size=(n - 2 * (n // 3), 2))
        all_coords = np.vstack([c1, c2, c3])

        points = [
            DetectionPoint(x=float(x), y=float(y), confidence=0.85)
            for x, y in all_coords
        ]

        tracemalloc.start()

        # 1. Benchmark HAC (Ward)
        t0 = time.perf_counter()
        clustering_res = clusterer_ward.cluster(points)
        hac_latency_ms = (time.perf_counter() - t0) * 1000.0

        # 2. Benchmark Closeness (KDTree & ConvexHull)
        t0 = time.perf_counter()
        closeness_res = estimator.compute_all(clustering_res.clusters)
        closeness_latency_ms = (time.perf_counter() - t0) * 1000.0

        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # 3. Linkage comparison
        res_complete = clusterer_complete.cluster(points)
        res_avg = clusterer_avg.cluster(points)

        total_latency_ms = hac_latency_ms + closeness_latency_ms
        coph_ward = clustering_res.cophenetic_correlation or 0.0
        coph_complete = res_complete.cophenetic_correlation or 0.0
        coph_avg = res_avg.cophenetic_correlation or 0.0

        peak_kb = peak_mem / 1024.0

        results.append({
            "n": n,
            "clusters_ward": len(clustering_res.clusters),
            "hac_ms": hac_latency_ms,
            "closeness_ms": closeness_latency_ms,
            "total_ms": total_latency_ms,
            "peak_kb": peak_kb,
            "cophenetic_ward": coph_ward,
            "cophenetic_complete": coph_complete,
            "cophenetic_avg": coph_avg,
            "mean_nn_px": closeness_res.global_mean_nn_distance
        })

        print(
            f"Crowd N={n:4d} | HAC: {hac_latency_ms:6.2f}ms | Closeness: {closeness_latency_ms:6.2f}ms | "
            f"Total: {total_latency_ms:6.2f}ms | Peak RAM: {peak_kb:6.1f} KB | "
            f"Cophenetic (W/C/A): {coph_ward:.3f}/{coph_complete:.3f}/{coph_avg:.3f} | Clusters: {len(clustering_res.clusters):2d}"
        )

    # 4. Motion Analysis Benchmark
    print("-" * 80)
    print("VIDEO MOTION ESTIMATION & CAMERA COMPENSATION BENCHMARK")
    print("-" * 80)
    analyzer = VideoMotionAnalyzer()

    # Generate synthetic 640x480 frame pair
    f1 = np.zeros((480, 640, 3), dtype=np.uint8)
    f2 = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add background textures
    np.random.seed(42)
    bg_pts = np.random.randint(20, 460, size=(100, 2))
    for x, y in bg_pts:
        cv2.circle(f1, (x, y), 3, (120, 120, 120), -1)
        cv2.circle(f2, (x + 3, y + 1), 3, (120, 120, 120), -1)  # Camera pan (+3, +1)

    # Add crowd points
    crowd_pts = [(float(x), float(y)) for x, y in np.random.randint(100, 300, size=(50, 2))]

    t0 = time.perf_counter()
    motion_res = analyzer.analyze_motion(f1, f2, crowd_points=crowd_pts)
    motion_ms = (time.perf_counter() - t0) * 1000.0

    print(f"Motion Latency: {motion_ms:.2f} ms | Cam Compensated: {motion_res.camera_motion_compensated} | Shift: {motion_res.camera_shift}")
    print(f"Dominant Direction: {motion_res.dominant_direction_deg}° | Dispersion: {motion_res.directional_dispersion:.4f}")
    print("=" * 80)

    return results


if __name__ == "__main__":
    benchmark_pipeline()
