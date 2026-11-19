"""One-time verified model download. Analysis never contacts the network."""
from pathlib import Path
import hashlib
import json
import urllib.request

MODEL_SHA256 = "9b310c8d77fb9383dcd6ae342f319cc6941242937909fc82d42fc50d1125886e"
MODEL_URL = "https://huggingface.co/chanubc/overhead-person-yolo11/resolve/8dbb94a4948e526e111dbb8b1f2d0cc8d941ed22/best.onnx"


def main():
    directory = Path(__file__).resolve().parents[1] / "backend" / "models"
    directory.mkdir(exist_ok=True)
    destination = directory / "overhead_person.onnx"
    data = destination.read_bytes() if destination.exists() else urllib.request.urlopen(MODEL_URL,timeout=120).read()
    if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
        raise SystemExit("Model checksum mismatch; model was not installed.")
    if not destination.exists():
        temporary = destination.with_suffix('.download')
        temporary.write_bytes(data)
        temporary.replace(destination)
    (directory / "model.json").write_text(json.dumps({"name":"YOLO11s overhead person", "source":MODEL_URL,
        "sha256":MODEL_SHA256,"bytes":len(data),"model_card_license":"CC-BY-4.0", "attribution":"chanubc/overhead-person-yolo11; Ultralytics YOLO11 base"},indent=2))
    print(f"Verified local model: {destination}")


if __name__ == '__main__':
    main()
