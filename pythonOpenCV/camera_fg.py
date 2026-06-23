"""
Foreground extraction — plain camera view, no LED matrix.

Shows a side-by-side window:
  Left  — live camera feed
  Right — foreground mask applied to the same frame (background = black)

Controls
--------
  Q          quit
  Space / B  recapture background
"""

import time
import cv2
import numpy as np
from led_simulator import make_label, side_by_side

# ── Configuration ─────────────────────────────────────────────────────────────

CAMERA_INDEX      = 0
FRAME_WIDTH       = 160
FRAME_HEIGHT      = 120
DIFF_THRESHOLD    = 30    # 0–765 sum of per-channel abs diff; lower = more sensitive
BG_CAPTURE_FRAMES = 6     # frames averaged for the background reference

# ── Camera setup ──────────────────────────────────────────────────────────────

cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    raise RuntimeError(f"Could not open camera index {CAMERA_INDEX}")

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Camera: requested {FRAME_WIDTH}x{FRAME_HEIGHT}, got {actual_w}x{actual_h}")

# ── Background capture ────────────────────────────────────────────────────────

_background = np.zeros((actual_h, actual_w, 3), dtype=np.float32)

def capture_background():
    global _background
    print("Capturing background ...")
    accum    = np.zeros((actual_h, actual_w, 3), dtype=np.float32)
    captured = 0
    while captured < BG_CAPTURE_FRAMES:
        ret, frame = cap.read()
        if not ret:
            continue
        accum    += frame.astype(np.float32)
        captured += 1
    _background = accum / BG_CAPTURE_FRAMES
    print("Done.")

# ── Foreground extraction ─────────────────────────────────────────────────────

def extract_foreground(frame):
    """Return a copy of frame with background pixels set to black."""
    diff = np.sum(np.abs(frame.astype(np.float32) - _background), axis=2)
    mask = (diff >= DIFF_THRESHOLD).astype(np.uint8)          # 1 = foreground
    return frame * mask[:, :, np.newaxis]                      # broadcast mask

# ── Startup ───────────────────────────────────────────────────────────────────

print("Keep the scene empty for background capture ...")
capture_background()
print(f"Threshold: {DIFF_THRESHOLD}  |  Press Space/B to recapture, Q to quit.")

# ── Main loop ─────────────────────────────────────────────────────────────────

while True:
    ret, frame = cap.read()
    if not ret:
        print("capture failed")
        continue

    fg = extract_foreground(frame)

    cam_panel = make_label(frame.copy(), "Camera")
    fg_panel  = make_label(fg,           f"Foreground (threshold={DIFF_THRESHOLD})")
    cv2.imshow("Foreground extraction", side_by_side(cam_panel, fg_panel))

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    if key in (ord(' '), ord('b')):
        capture_background()

cap.release()
cv2.destroyAllWindows()
