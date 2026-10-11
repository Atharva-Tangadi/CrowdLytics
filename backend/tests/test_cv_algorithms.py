"""Comprehensive automated tests for computer-vision algorithms."""
import pytest
import numpy as np
import cv2

from app.cv.preprocessing.processor import ImagePreprocessor
from app.cv.localization.detector import DeterministicDetector, DetectionPoint, AerialBlobDensityDetector
from app.cv.clustering.hac import HierarchicalClusterer
from app.cv.closeness.estimator import ClosenessEstimator
from app.cv.motion.analyzer import VideoMotionAnalyzer
from app.cv.formation.tracker import FormationTracker, FormationType
from app.cv.visualization.overlay import GroupVisualizer


# --- 1. Preprocessing Tests ---
def test_image_preprocessor_resizing():
    preprocessor = ImagePreprocessor(max_dimension=500)
    img = np.zeros((1000, 2000, 3), dtype=np.uint8)
    processed, scale = preprocessor.preprocess(img)
    
    assert max(processed.shape[:2]) <= 500
    assert scale == 0.25
    assert processed.shape[1] == 500
    assert processed.shape[0] == 250


def test_image_preprocessor_roi_mask():
    preprocessor = ImagePreprocessor(max_dimension=1000)
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    roi = np.zeros((100, 100), dtype=np.uint8)
    roi[20:80, 20:80] = 255  # Active box
    
    processed, _ = preprocessor.preprocess(img, roi_mask=roi)
    assert np.all(processed[0:10, 0:10] == 0)
    assert np.all(processed[30:70, 30:70] == 255)


# --- 2. Localization Tests ---
def test_deterministic_detector_confidence_filtering():
    points = [
        DetectionPoint(x=10, y=20, confidence=0.8),
        DetectionPoint(x=30, y=40, confidence=0.2),  # Below threshold
        DetectionPoint(x=50, y=60, confidence=0.9),
    ]
    detector = DeterministicDetector(predefined_points=points)
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    result = detector.detect(dummy_img, confidence_threshold=0.5)

    assert result.total_count == 2
    assert len(result.points) == 2
    assert result.points[0].x == 10
    assert result.points[1].x == 50


# --- 3. Hierarchical Agglomerative Clustering Tests ---
def test_hac_two_separated_clusters():
    """Verify that two spatially distinct clusters are correctly partitioned."""
    cluster_a = [
        DetectionPoint(x=10, y=10, confidence=0.9),
        DetectionPoint(x=12, y=14, confidence=0.9),
        DetectionPoint(x=14, y=11, confidence=0.9),
    ]
    cluster_b = [
        DetectionPoint(x=200, y=200, confidence=0.9),
        DetectionPoint(x=205, y=202, confidence=0.9),
        DetectionPoint(x=202, y=208, confidence=0.9),
    ]
    all_points = cluster_a + cluster_b

    clusterer = HierarchicalClusterer(distance_threshold=30.0, linkage_method="ward")
    result = clusterer.cluster(all_points)

    assert len(result.clusters) == 2
    assert result.cophenetic_correlation is not None
    assert result.cophenetic_correlation > 0.80  # Low dendrogram distortion

    c1 = result.clusters[0]
    c2 = result.clusters[1]
    assert {c1.size, c2.size} == {3, 3}
    assert np.hypot(c1.centroid[0] - c2.centroid[0], c1.centroid[1] - c2.centroid[1]) > 200.0


def test_hac_empty_and_single_point():
    clusterer = HierarchicalClusterer(distance_threshold=30.0)
    empty_res = clusterer.cluster([])
    assert len(empty_res.clusters) == 0

    single_pt = [DetectionPoint(x=50, y=50, confidence=0.9)]
    single_res = clusterer.cluster(single_pt)
    # Default min_cluster_size is 2, so a single detection is marked unclustered
    assert len(single_res.clusters) == 0
    assert len(single_res.unclustered_points) == 1


# --- 4. Closeness & Spatial Density Tests ---
def test_closeness_estimator_convex_hull_and_nn():
    from app.cv.clustering.hac import ClusterGroup

    # 4 points forming a 10x10 square (area = 100 sq px)
    pts = [
        DetectionPoint(x=0, y=0, confidence=0.9),
        DetectionPoint(x=10, y=0, confidence=0.9),
        DetectionPoint(x=10, y=10, confidence=0.9),
        DetectionPoint(x=0, y=10, confidence=0.9),
    ]
    cluster = ClusterGroup(
        cluster_id=1,
        member_indices=[0, 1, 2, 3],
        member_points=pts,
        centroid=[5.0, 5.0],
        size=4,
        bounding_box=[0.0, 0.0, 10.0, 10.0]
    )

    estimator = ClosenessEstimator()
    metrics = estimator.compute_group_metrics(cluster)

    assert metrics.size == 4
    assert pytest.approx(metrics.convex_hull_area, rel=1e-2) == 100.0
    assert pytest.approx(metrics.mean_nn_distance, rel=1e-2) == 10.0
    assert metrics.density_per_kpx == pytest.approx((4 / 100.0) * 1000.0)
    assert not metrics.is_degenerate


def test_closeness_degenerate_collinear_points():
    from app.cv.clustering.hac import ClusterGroup
    # 3 collinear points
    pts = [
        DetectionPoint(x=10, y=10, confidence=0.9),
        DetectionPoint(x=20, y=20, confidence=0.9),
        DetectionPoint(x=30, y=30, confidence=0.9),
    ]
    cluster = ClusterGroup(
        cluster_id=1,
        member_indices=[0, 1, 2],
        member_points=pts,
        centroid=[20.0, 20.0],
        size=3,
        bounding_box=[10.0, 10.0, 30.0, 30.0]
    )
    estimator = ClosenessEstimator()
    metrics = estimator.compute_group_metrics(cluster)
    assert metrics.is_degenerate or metrics.convex_hull_area == 0.0


# --- 5. Video Motion & Camera Compensation Tests ---
def test_video_motion_directional_consistency():
    analyzer = VideoMotionAnalyzer(min_motion_threshold=0.5)

    # Synthetic moving pattern: create white squares on black background
    f1 = np.zeros((200, 200), dtype=np.uint8)
    f2 = np.zeros((200, 200), dtype=np.uint8)

    # Draw point pattern shifted to the right (dx = +10, dy = 0 => angle = 0 degrees)
    for (x, y) in [(50, 50), (60, 50), (50, 60), (60, 60)]:
        cv2.circle(f1, (x, y), 3, 255, -1)
        cv2.circle(f2, (x + 10, y), 3, 255, -1)

    pts = [(50.0, 50.0), (60.0, 50.0), (50.0, 60.0), (60.0, 60.0)]
    result = analyzer.analyze_motion(f1, f2, crowd_points=pts)

    assert result.dominant_direction_deg is not None
    # Angle should be approximately 0 degrees (pointing right in image space)
    assert abs(result.dominant_direction_deg - 0.0) < 5.0 or abs(result.dominant_direction_deg - 360.0) < 5.0
    assert result.directional_dispersion < 0.1  # High directional coherence
    assert result.mean_speed == pytest.approx(10.0, abs=1.0)


# --- 6. Group Formation Dynamics Tests ---
def test_formation_tracker_merge_and_expansion():
    from app.cv.clustering.hac import ClusterGroup
    from app.cv.closeness.estimator import GroupClosenessMetrics

    tracker = FormationTracker()

    # Time Window 1: Two separate clusters
    c1 = ClusterGroup(cluster_id=1, member_indices=[0, 1], member_points=[], centroid=[50.0, 50.0], size=2, bounding_box=[40, 40, 60, 60])
    c2 = ClusterGroup(cluster_id=2, member_indices=[2, 3], member_points=[], centroid=[70.0, 70.0], size=2, bounding_box=[60, 60, 80, 80])
    m1 = GroupClosenessMetrics(cluster_id=1, size=2, mean_nn_distance=10, median_nn_distance=10, mean_pairwise_distance=10, dispersion=5, convex_hull_area=50, density_per_kpx=40, is_degenerate=False)
    m2 = GroupClosenessMetrics(cluster_id=2, size=2, mean_nn_distance=10, median_nn_distance=10, mean_pairwise_distance=10, dispersion=5, convex_hull_area=50, density_per_kpx=40, is_degenerate=False)

    # Time Window 2: Merged into one single cluster
    c_merged = ClusterGroup(cluster_id=1, member_indices=[0, 1, 2, 3], member_points=[], centroid=[60.0, 60.0], size=4, bounding_box=[40, 40, 80, 80])
    m_merged = GroupClosenessMetrics(cluster_id=1, size=4, mean_nn_distance=12, median_nn_distance=12, mean_pairwise_distance=15, dispersion=15, convex_hull_area=200, density_per_kpx=20, is_degenerate=False)

    records = tracker.analyze_temporal_transitions([c1, c2], [m1, m2], [c_merged], [m_merged])

    types = [r.formation_type for r in records]
    assert FormationType.MERGING in types


# --- 7. Overlay Visualizer Test ---
def test_group_visualizer_rendering():
    visualizer = GroupVisualizer()
    img = np.zeros((300, 300, 3), dtype=np.uint8)

    pts = [
        DetectionPoint(x=50, y=50, confidence=0.9),
        DetectionPoint(x=100, y=50, confidence=0.9),
        DetectionPoint(x=75, y=100, confidence=0.9),
    ]
    from app.cv.clustering.hac import ClusterGroup
    cluster = ClusterGroup(
        cluster_id=1,
        member_indices=[0, 1, 2],
        member_points=pts,
        centroid=[75.0, 66.6],
        size=3,
        bounding_box=[50.0, 50.0, 100.0, 100.0]
    )

    annotated = visualizer.render_overlays(img, [cluster], motion_vectors=[])
    assert annotated.shape == img.shape
    # Check that overlay pixels are modified (non-black pixels present)
    assert np.any(annotated > 0)
