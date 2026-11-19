"""Local OpenCV-DNN person detectors for aerial and CCTV camera views.

The aerial YOLO11s weights are fine-tuned for overhead people. The ground-view
detector uses OpenCV Zoo's YOLOX-S COCO weights. Neither downloads weights or
calls external services during analysis.
"""
from pathlib import Path
import hashlib
import cv2
import numpy as np
from app.cv.localization.detector import BaseDetector, DetectionPoint, DetectionResult
from app.core.config import settings


def nms_indices(boxes, scores, score_threshold, iou_threshold):
    if not boxes:
        return []
    return np.asarray(cv2.dnn.NMSBoxes(
        boxes, scores, score_threshold, iou_threshold
    )).reshape(-1).tolist()


class PersonDetector(BaseDetector):
    """Tiled YOLO11s detector for drone and overhead images."""

    def __init__(self, model_path=None, tile_size=384, input_size=640, nms_iou_threshold=.45):
        path = Path(model_path or settings.PERSON_MODEL_PATH)
        if not path.is_file():
            raise ValueError("Person model missing. Run python scripts/setup_person_model.py, then reanalyze.")
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.net = cv2.dnn.readNetFromONNX(str(path))
        self.tile_size = tile_size
        self.input_size = input_size
        self.nms_iou_threshold = nms_iou_threshold
        self.detection_mode = "aerial"

    @staticmethod
    def offsets(length, tile):
        if length <= tile:
            return [0]
        return sorted(set(list(range(0, length-tile+1, max(1,int(tile*.8)))) + [length-tile]))

    @staticmethod
    def letterbox(image, size):
        height, width = image.shape[:2]
        scale = min(size / width, size / height)
        resized_width = max(1, int(round(width * scale)))
        resized_height = max(1, int(round(height * scale)))
        pad_x = (size - resized_width) // 2
        pad_y = (size - resized_height) // 2
        padded = np.full((size, size, 3), 114, np.uint8)
        padded[pad_y:pad_y + resized_height, pad_x:pad_x + resized_width] = cv2.resize(
            image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR
        )
        return padded, scale, pad_x, pad_y

    def detect(self, image, confidence_threshold=.3):
        if image is None or image.size == 0:
            raise ValueError("Input image is empty or invalid.")
        boxes, scores = [], []
        maximum_score = 0.
        height, width = image.shape[:2]
        for y in self.offsets(height, self.tile_size):
            for x in self.offsets(width, self.tile_size):
                tile = image[y:y+self.tile_size, x:x+self.tile_size]
                h, w = tile.shape[:2]
                padded, scale, pad_x, pad_y = self.letterbox(tile, self.input_size)
                self.net.setInput(cv2.dnn.blobFromImage(
                    padded, 1/255., (self.input_size, self.input_size), swapRB=True
                ))
                raw = self.net.forward()[0].T
                if raw.shape[1] != 5:
                    raise ValueError(f"Unsupported single-person YOLO11 output: {raw.shape}")
                confidence = raw[:,4]
                finite = np.isfinite(raw).all(axis=1)
                if finite.any():
                    maximum_score = max(maximum_score, float(confidence[finite].max()))
                # Collect diagnostic candidates in the same forward pass, without
                # changing the user's actual output threshold.
                keep = np.where((confidence >= min(confidence_threshold,.25)) & finite)[0]
                centers = raw[keep,:2]
                sizes = raw[keep,2:4]
                tile_boxes, tile_scores = [], []
                for center,size,score in zip(centers,sizes,confidence[keep]):
                    # Remove centered padding before mapping coordinates to the source tile.
                    cx, cy = (center - [pad_x, pad_y]) / scale
                    if not (0 <= cx < w and 0 <= cy < h):
                        continue
                    bw,bh = size / scale
                    x1,y1 = max(0.,float(cx-bw/2+x)), max(0.,float(cy-bh/2+y))
                    x2,y2 = min(float(width),float(cx+bw/2+x)), min(float(height),float(cy+bh/2+y))
                    if x2>x1 and y2>y1:
                        tile_boxes.append([x1,y1,x2-x1,y2-y1]); tile_scores.append(float(score))
                local_indices = nms_indices(
                    tile_boxes, tile_scores, min(confidence_threshold, .25), self.nms_iou_threshold
                )
                boxes.extend(tile_boxes[index] for index in local_indices)
                scores.extend(tile_scores[index] for index in local_indices)
        indices = nms_indices(boxes, scores, confidence_threshold, self.nms_iou_threshold)
        diagnostic_count = (len(nms_indices(boxes,scores,.25,self.nms_iou_threshold))
                            if boxes and confidence_threshold > .25 else None)
        points = []
        for i in indices:
            x,y,w,h = boxes[int(i)]
            points.append(DetectionPoint(x=x+w/2,y=y+h/2,confidence=scores[int(i)],bbox=[x,y,x+w,y+h]))
        return DetectionResult(points=points,total_count=len(points),
            mean_confidence=float(np.mean([p.confidence for p in points])) if points else 0.,
            model_name="yolo11s_overhead_person",metadata={"sha256":self.sha256,"tile_size":self.tile_size,
            "tile_count":len(self.offsets(height,self.tile_size))*len(self.offsets(width,self.tile_size)),
            "letterbox":"centered","nms_iou_threshold":self.nms_iou_threshold,
            "requested_threshold":confidence_threshold,"max_detection_score":maximum_score,
            "diagnostic_threshold":.25,"candidates_at_diagnostic_threshold":diagnostic_count,
            "recommended_threshold":.25,"candidates_at_recommended_threshold":diagnostic_count,
            "count_semantics":"visible_person_detections", "domain":"aerial_and_overhead"})


class CctvPersonDetector(BaseDetector):
    """OpenCV Zoo YOLOX-S COCO detector for ground-level camera views."""

    input_size = 640
    tile_size = 640
    nms_iou_threshold = .5
    strides = (8, 16, 32)

    def __init__(self, model_path=None):
        path = Path(model_path or settings.CCTV_MODEL_PATH)
        if not path.is_file():
            raise ValueError(
                "CCTV person model missing. Run python scripts/setup_cctv_model.py, then reanalyze."
            )
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.net = cv2.dnn.readNetFromONNX(str(path))
        self.detection_mode = "cctv"
        grids = []
        expanded_strides = []
        for stride in self.strides:
            grid_size = self.input_size // stride
            grid_x, grid_y = np.meshgrid(np.arange(grid_size), np.arange(grid_size))
            grids.append(np.stack((grid_x, grid_y), axis=2).reshape(1, -1, 2))
            expanded_strides.append(np.full((1, grid_size * grid_size, 1), stride))
        self.grids = np.concatenate(grids, axis=1).astype(np.float32)
        self.expanded_strides = np.concatenate(expanded_strides, axis=1).astype(np.float32)

    def detect(self, image, confidence_threshold=.3):
        if image is None or image.size == 0:
            raise ValueError("Input image is empty or invalid.")
        height, width = image.shape[:2]
        boxes, scores = [], []
        maximum_score = 0.
        for y in PersonDetector.offsets(height, self.tile_size):
            for x in PersonDetector.offsets(width, self.tile_size):
                tile = image[y:y + self.tile_size, x:x + self.tile_size]
                tile_height, tile_width = tile.shape[:2]
                padded, scale, pad_x, pad_y = PersonDetector.letterbox(tile, self.input_size)
                self.net.setInput(cv2.dnn.blobFromImage(padded, 1., (self.input_size, self.input_size)))
                output = np.asarray(self.net.forward())
                if output.size == 0 or output.shape[-1] != 85:
                    raise ValueError(f"Unsupported YOLOX COCO output: {output.shape}")
                raw = output.reshape(-1, 85)
                if raw.shape[0] != self.grids.shape[1]:
                    raise ValueError(f"Unexpected YOLOX anchor count: {raw.shape}")

                finite = np.isfinite(raw[:, :6]).all(axis=1)
                person_scores = raw[:, 4] * raw[:, 5]
                valid = finite & (person_scores >= min(confidence_threshold, .25))
                if finite.any():
                    maximum_score = max(maximum_score, float(person_scores[finite].max()))
                if not valid.any():
                    continue

                selected = np.flatnonzero(valid)
                centers = (raw[selected, :2] + self.grids[0, selected]) * self.expanded_strides[0, selected]
                sizes = np.exp(np.clip(raw[selected, 2:4], -20, 20)) * self.expanded_strides[0, selected]
                tile_boxes, tile_scores = [], []
                for center, size, score in zip(centers, sizes, person_scores[selected]):
                    center_x = (center[0] - pad_x) / scale
                    center_y = (center[1] - pad_y) / scale
                    if not (0 <= center_x < tile_width and 0 <= center_y < tile_height):
                        continue
                    box_width, box_height = size / scale
                    x1 = max(0., float(center_x - box_width / 2 + x))
                    y1 = max(0., float(center_y - box_height / 2 + y))
                    x2 = min(float(width), float(center_x + box_width / 2 + x))
                    y2 = min(float(height), float(center_y + box_height / 2 + y))
                    if x2 > x1 and y2 > y1:
                        tile_boxes.append([x1, y1, x2 - x1, y2 - y1])
                        tile_scores.append(float(score))
                local_indices = nms_indices(
                    tile_boxes, tile_scores, min(confidence_threshold, .25), self.nms_iou_threshold
                )
                boxes.extend(tile_boxes[index] for index in local_indices)
                scores.extend(tile_scores[index] for index in local_indices)

        indices = nms_indices(boxes, scores, confidence_threshold, self.nms_iou_threshold)
        diagnostic_count = (len(nms_indices(boxes, scores, .25, self.nms_iou_threshold))
                            if boxes and confidence_threshold > .25 else None)
        points = []
        for index in indices:
            x, y, box_width, box_height = boxes[int(index)]
            score = scores[int(index)]
            points.append(DetectionPoint(
                x=x + box_width / 2, y=y + box_height / 2, confidence=score,
                bbox=[x, y, x + box_width, y + box_height]
            ))
        return DetectionResult(
            points=points, total_count=len(points),
            mean_confidence=float(np.mean([point.confidence for point in points])) if points else 0.,
            model_name="yolox_s_coco_person",
            metadata={
                "sha256": self.sha256, "input_size": [self.input_size, self.input_size],
                "tile_size": self.tile_size, "tile_count": len(PersonDetector.offsets(height,self.tile_size)) *
                len(PersonDetector.offsets(width,self.tile_size)), "letterbox": "centered",
                "nms_iou_threshold": self.nms_iou_threshold,
                "requested_threshold": confidence_threshold, "max_detection_score": maximum_score,
                "diagnostic_threshold": .25, "candidates_at_diagnostic_threshold": diagnostic_count,
                "recommended_threshold": .25, "candidates_at_recommended_threshold": diagnostic_count,
                "count_semantics": "visible_person_detections",
                "domain": "ground_level_general_person_coco",
            },
        )


def create_detector(backend="auto"):
    from app.cv.localization.detector import AerialBlobDensityDetector
    selected = settings.DEFAULT_DETECTOR if backend == "auto" else backend
    if selected in {"person", "aerial"}:
        return PersonDetector()
    if selected == "cctv":
        return CctvPersonDetector()
    if selected == "blob":
        return AerialBlobDensityDetector()
    raise ValueError(f"Unsupported detector: {selected}")
