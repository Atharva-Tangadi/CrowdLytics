"""Local OpenCV-DNN YOLO11s inference, fine-tuned for overhead people.

Model source: chanubc/overhead-person-yolo11. See backend/models/README.md.
No runtime downloads, PyTorch dependency or external inference.
"""
from pathlib import Path
import hashlib
import cv2
import numpy as np
from app.cv.localization.detector import BaseDetector, DetectionPoint, DetectionResult
from app.core.config import settings


class PersonDetector(BaseDetector):
    def __init__(self, model_path=None, tile_size=384):
        path = Path(model_path or settings.PERSON_MODEL_PATH)
        if not path.is_file():
            raise ValueError("Person model missing. Run python scripts/setup_person_model.py, then reanalyze.")
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.net = cv2.dnn.readNetFromONNX(str(path))
        self.tile_size = tile_size

    @staticmethod
    def offsets(length, tile):
        if length <= tile:
            return [0]
        return sorted(set(list(range(0, length-tile+1, max(1,int(tile*.8)))) + [length-tile]))

    def detect(self, image, confidence_threshold=.3):
        boxes, scores = [], []
        maximum_score = 0.
        height, width = image.shape[:2]
        for y in self.offsets(height, self.tile_size):
            for x in self.offsets(width, self.tile_size):
                tile = image[y:y+self.tile_size, x:x+self.tile_size]
                h,w = tile.shape[:2]
                scale = min(640/w,640/h)
                padded = np.full((640,640,3),114,np.uint8)
                padded[:int(h*scale),:int(w*scale)] = cv2.resize(tile,(int(w*scale),int(h*scale)))
                self.net.setInput(cv2.dnn.blobFromImage(padded,1/255.,(640,640),swapRB=True))
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
                for center,size,score in zip(centers,sizes,confidence[keep]):
                    # Reject padding predictions; map back to original tile coordinates.
                    cx,cy = center / scale
                    if not (0 <= cx < w and 0 <= cy < h):
                        continue
                    bw,bh = size / scale
                    x1,y1 = max(0.,float(cx-bw/2+x)), max(0.,float(cy-bh/2+y))
                    x2,y2 = min(float(width),float(cx+bw/2+x)), min(float(height),float(cy+bh/2+y))
                    if x2>x1 and y2>y1:
                        boxes.append([x1,y1,x2-x1,y2-y1]); scores.append(float(score))
        indices = np.asarray(cv2.dnn.NMSBoxes(boxes,scores,confidence_threshold,.45)).reshape(-1) if boxes else []
        diagnostic_count = (len(cv2.dnn.NMSBoxes(boxes,scores,.25,.45))
                            if boxes and confidence_threshold > .25 else None)
        points = []
        for i in indices:
            x,y,w,h = boxes[int(i)]
            points.append(DetectionPoint(x=x+w/2,y=y+h/2,confidence=scores[int(i)],bbox=[x,y,x+w,y+h]))
        return DetectionResult(points=points,total_count=len(points),
            mean_confidence=float(np.mean([p.confidence for p in points])) if points else 0.,
            model_name="yolo11s_overhead_person",metadata={"sha256":self.sha256,"tile_size":self.tile_size,
            "requested_threshold":confidence_threshold,"max_detection_score":maximum_score,
            "recommended_threshold":.25,"candidates_at_recommended_threshold":diagnostic_count,
            "count_semantics":"visible_person_detections", "domain":"overhead_ceiling_camera_not_validated_on_this_video"})


def create_detector(backend="auto"):
    from app.cv.localization.detector import AerialBlobDensityDetector
    selected = settings.DEFAULT_DETECTOR if backend == "auto" else backend
    if selected == "person":
        return PersonDetector()
    if selected == "blob":
        return AerialBlobDensityDetector()
    raise ValueError(f"Unsupported detector: {selected}")
