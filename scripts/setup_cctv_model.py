"""Install and verify the optional general-person CCTV ONNX detector."""
from pathlib import Path
import hashlib
import json
import urllib.request


MODEL_ROOT = Path(__file__).resolve().parents[1] / "backend" / "models"
REVISION = "78c368f74ce73ee28fc7a1be418a598c71b58b52"
MODEL_NAME = "cctv_yolox_s.onnx"
MODEL_URL = (
    "https://huggingface.co/opencv/object_detection_yolox/resolve/"
    f"{REVISION}/object_detection_yolox_2022nov.onnx"
)
MODEL_SHA256 = "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"


def verified_bytes(path: Path) -> bool:
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == MODEL_SHA256


def download_verified() -> None:
    destination = MODEL_ROOT / MODEL_NAME
    if verified_bytes(destination):
        return
    if destination.exists():
        raise SystemExit(f"Existing CCTV model file has an invalid checksum: {destination}")

    temporary = destination.with_suffix(destination.suffix + ".download")
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=120) as response, temporary.open("wb") as target:
            while block := response.read(1024 * 1024):
                target.write(block)
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        if digest != MODEL_SHA256:
            raise SystemExit("CCTV model checksum mismatch; refusing to install it.")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    download_verified()

    (MODEL_ROOT / "cctv_model.json").write_text(json.dumps({
        "name": "OpenCV Zoo YOLOX-S COCO",
        "source": MODEL_URL,
        "revision": REVISION,
        "license": "Apache-2.0 (OpenCV Zoo)",
        "training_data": "COCO 2017",
        "domain_note": "General object detector; not CCTV-specific fine-tuning",
        "sha256": MODEL_SHA256,
        "bytes": (MODEL_ROOT / MODEL_NAME).stat().st_size,
    }, indent=2))
    print(f"Verified CCTV person detector installed under {MODEL_ROOT}")


if __name__ == "__main__":
    main()
