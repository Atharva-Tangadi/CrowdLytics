# Local overhead person detector

Run `python scripts/setup_person_model.py` once from the repository root.
Inference uses OpenCV DNN locally; there are no network requests during analysis.

Selected weights: **chanubc/overhead-person-yolo11**, fine-tuned YOLO11s, single
person class, ONNX opset 12. Tile size 384, input 640, RGB / 255, top-left letterbox.
Source: https://huggingface.co/chanubc/overhead-person-yolo11
Pinned revision: 8dbb94a4948e526e111dbb8b1f2d0cc8d941ed22
SHA-256: 9b310c8d77fb9383dcd6ae342f319cc6941242937909fc82d42fc50d1125886e

Attribution: chanubc; upstream Ultralytics YOLO11. The model card declares CC BY 4.0
and identifies overhead-person (Roboflow Universe) training data. See the source
model card and https://www.ultralytics.com/license for upstream license terms.
The source's published metrics are not validation on the user's crowd footage.

The blob detector remains an explicit synthetic/demo option. The person detector
fails clearly when its weights are absent; it never silently falls back to blobs.
