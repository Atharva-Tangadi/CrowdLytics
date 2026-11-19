"""Generate synthetic guide-demo media; no downloads or personal data.

Run with the project Python: python scripts/generate_demo.py
Existing files are never overwritten. This demonstrates behavior, not accuracy.
"""
from pathlib import Path
import cv2
import numpy as np


def main():
    root = Path(__file__).resolve().parents[1] / "data" / "temporary" / "guide-demo"
    root.mkdir(parents=True, exist_ok=True)
    image_path, video_path = root / "clusters.png", root / "static-crowd-increase.mp4"
    if image_path.exists() or video_path.exists():
        raise SystemExit(f"Demo files already exist in {root}; refusing to overwrite.")
    image = np.zeros((360,640,3),np.uint8)
    for x,y in [(60,80),(80,80),(70,100),(300,200),(320,200),(310,220)]:
        cv2.circle(image,(x,y),4,(255,255,255),-1)
    cv2.imwrite(str(image_path),image)
    writer = cv2.VideoWriter(str(video_path),cv2.VideoWriter_fourcc(*'mp4v'),10,(640,360))
    if not writer.isOpened():
        raise SystemExit("MP4 encoder unavailable")
    for i in range(120):
        frame = np.zeros_like(image)
        shift = round(i*.8)
        points = [(60+shift,80),(80+shift,80),(70+shift,100)]
        if i >= 50:
            points += [(320+x*20,180+y*20) for x in range(6) for y in range(4)]
        for point in points:
            cv2.circle(frame,point,4,(255,255,255),-1)
        writer.write(frame)
    writer.release()
    print(f"Synthetic image: {image_path}\nSynthetic static video: {video_path}")


if __name__ == "__main__":
    main()
