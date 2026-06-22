"""
Camera capture → save to disk — desktop version of camera_to_sd.py.

Warms up the webcam (auto-exposure settle), then captures NUM_PHOTOS
JPEG images and saves them to the current directory as img_0000.jpg …

Press Q in the preview window to quit early.
"""

import time
import cv2

# ── Configuration ─────────────────────────────────────────────────────────────

CAMERA_INDEX = 0          # webcam index (0 = default system camera)
NUM_PHOTOS   = 3
WARMUP_FRAMES = 8         # frames discarded for auto-exposure to settle
OUTPUT_DIR   = "."        # directory to write images into

# ── Camera setup ──────────────────────────────────────────────────────────────

cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    raise RuntimeError(f"Could not open camera index {CAMERA_INDEX}")

print(f"Camera opened: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}×"
      f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

# ── Warm up ───────────────────────────────────────────────────────────────────

print(f"Warming up ({WARMUP_FRAMES} frames) …")
for _ in range(WARMUP_FRAMES):
    cap.read()

# ── Capture loop ──────────────────────────────────────────────────────────────

for i in range(NUM_PHOTOS):
    ret, frame = cap.read()
    if not ret:
        print(f"  [{i}] capture failed — skipping")
        continue

    filename = f"{OUTPUT_DIR}/img_{i:04d}.jpg"
    cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"  [{i}] saved {frame.shape[1]}×{frame.shape[0]} → {filename}")

    # Show preview.
    cv2.imshow("Captured", frame)
    if cv2.waitKey(500) & 0xFF == ord('q'):
        break

    time.sleep(0.3)

print("Done.")
cap.release()
cv2.destroyAllWindows()
