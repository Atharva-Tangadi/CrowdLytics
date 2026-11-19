"""Evaluate person detectors against boxes manually labelled in a JSON manifest."""
import argparse
import json
from pathlib import Path
import sys

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.cv.evaluation import DetectionMetrics  # noqa: E402
from app.cv.localization.person import create_detector  # noqa: E402


def load_manifest(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or not isinstance(data.get("images"), list):
        raise ValueError("Manifest must be an object with an 'images' list.")
    entries = []
    for index, row in enumerate(data["images"]):
        if not isinstance(row, dict) or not isinstance(row.get("image"), str):
            raise ValueError(f"Image entry {index} must contain an image path.")
        boxes = row.get("boxes")
        if not isinstance(boxes, list) or any(
            not isinstance(box, list) or len(box) != 4 for box in boxes
        ):
            raise ValueError(f"Image entry {index} must have xyxy boxes with four numbers each.")
        image_path = Path(row["image"])
        if not image_path.is_absolute():
            image_path = path.parent / image_path
        entries.append({"image": image_path, "boxes": boxes})
    return entries


def evaluate(manifest: Path, modes: list[str], thresholds: list[float], iou_threshold: float):
    entries = load_manifest(manifest)
    if not entries:
        raise ValueError("The evaluation manifest has no images.")
    results = []
    for mode in modes:
        detector = create_detector(mode)
        for threshold in thresholds:
            metrics = DetectionMetrics()
            for entry in entries:
                image = cv2.imread(str(entry["image"]))
                if image is None:
                    raise ValueError(f"Could not read labelled image: {entry['image']}")
                result = detector.detect(image, confidence_threshold=threshold)
                predicted = [point.bbox for point in result.points if point.bbox is not None]
                metrics.add_image(predicted, entry["boxes"], iou_threshold)
            results.append({
                "mode": mode,
                "model": result.model_name,
                "confidence_threshold": threshold,
                "iou_threshold": iou_threshold,
                **metrics.as_dict(),
            })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSON file containing labelled images and xyxy boxes")
    parser.add_argument("--modes", nargs="+", choices=("aerial", "cctv"), default=("aerial", "cctv"))
    parser.add_argument("--thresholds", nargs="+", type=float, default=(.15, .25, .35, .5, .75))
    parser.add_argument("--iou", type=float, default=.5, help="IoU threshold for a true-positive match")
    parser.add_argument("--output", type=Path, help="Optional path for the full JSON metrics report")
    args = parser.parse_args()
    if not 0 < args.iou <= 1 or any(not 0 <= threshold <= 1 for threshold in args.thresholds):
        parser.error("IoU and confidence thresholds must be within (0, 1] and [0, 1], respectively.")
    results = evaluate(args.manifest, list(args.modes), args.thresholds, args.iou)
    print(json.dumps(results, indent=2))
    if args.output:
        args.output.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
