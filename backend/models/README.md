# Local person detectors

Run `python scripts/setup_person_model.py` once from the repository root.
Inference uses OpenCV DNN locally; there are no network requests during analysis.

The **aerial** mode uses **chanubc/overhead-person-yolo11**, fine-tuned YOLO11s,
single person class, ONNX opset 12. It runs overlapping 384px tiles at input size
640, uses RGB / 255, centered letterboxing and per-tile plus global NMS to suppress
duplicate people, including across tile boundaries. High-resolution still images
are tiled at their original resolution instead of being downscaled first.
Source: https://huggingface.co/chanubc/overhead-person-yolo11
Pinned revision: 8dbb94a4948e526e111dbb8b1f2d0cc8d941ed22
SHA-256: 9b310c8d77fb9383dcd6ae342f319cc6941242937909fc82d42fc50d1125886e

Attribution: chanubc; upstream Ultralytics YOLO11. The model card declares CC BY 4.0
and identifies overhead-person (Roboflow Universe) training data. See the source
model card and https://www.ultralytics.com/license for upstream license terms.
The source's published metrics are not validation on the user's crowd footage.

The **CCTV** mode uses OpenCV Zoo's YOLOX-S model pretrained on COCO, filtered to
the person class. Install it separately with `python scripts/setup_cctv_model.py`.
OpenCV loads the pinned ONNX locally; the installer verifies its SHA-256. The model
is a general-view detector, not CCTV-specific fine-tuning, and can miss distant,
small, cropped, or heavily occluded people. The Zoo reports person AP 54.109 on its
COCO 2017 validation evaluation; that is not a CrowdLytics or CCTV accuracy claim.
The model files are Apache-2.0 licensed.

Both modes report boxes, detector confidence, model hash and threshold diagnostics.
Confidence is a filter score, not a probability of correctness or an accuracy claim.
The blob detector remains an explicit synthetic/demo option; missing model weights
raise an error and never silently fall back.

To compare models on manually labelled data, prepare a JSON manifest containing
image-relative `xyxy` bounding boxes and run:

```bash
python scripts/evaluate_detectors.py labelled-crowds.json
```

See the repository README for the manifest shape and how to interpret precision,
recall, F1 and count MAE. Compare models on the same scenes and labels; benchmark
results are data-dependent and do not imply universal accuracy.
