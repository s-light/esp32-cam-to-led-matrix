"""
Camera → LED matrix live view — desktop version of
circuitpython/example/cam_to_matrix.py.

Displays a side-by-side window:
  Left  — camera feed with the crop zone outlined in green
  Right — LED matrix simulation with glow effect

Crop logic and snake mapping are identical to the CircuitPython version.
OpenCV's cv2.resize() replaces the manual sample-map byte loop; the result
is equivalent (nearest-neighbour for speed) but written in one line.

Press Q to quit.
"""

import time
import cv2
import numpy as np
from led_simulator import LedMatrix, make_label, side_by_side

# ── Configuration ─────────────────────────────────────────────────────────────

CAMERA_INDEX  = 0
FRAME_WIDTH   = 160    # request this resolution from the camera
FRAME_HEIGHT  = 120    # 160×120 is the minimum most webcams support
WIDTH         = 16
HEIGHT        = 32
WARMUP_FRAMES = 8

# ── Matrix and camera setup ───────────────────────────────────────────────────

matrix = LedMatrix(WIDTH, HEIGHT, brightness=0.9, window_title="Cam -> Matrix")

cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    raise RuntimeError(f"Could not open camera index {CAMERA_INDEX}")

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Camera: requested {FRAME_WIDTH}x{FRAME_HEIGHT}, got {actual_w}x{actual_h}")

print("Warming up ...")
for _ in range(WARMUP_FRAMES):
    cap.read()

# ── Crop calculation ──────────────────────────────────────────────────────────
#
# Camera is landscape (4:3 or 16:9); matrix is portrait (1:2).
# We take a centred vertical slice of the frame that already has a 1:2
# aspect ratio, then resize that slice to WIDTH × HEIGHT.
#
# This is the same crop strategy as in the CircuitPython version, just
# done with cv2.resize() instead of a manual sample map.

def compute_crop(frame_w, frame_h):
    """Return (x_start, x_end) for the centred 1:2 crop."""
    crop_w  = frame_h // 2          # half the height gives 1:2 ratio
    x_start = (frame_w - crop_w) // 2
    x_end   = x_start + crop_w
    return x_start, x_end

def frame_to_matrix(frame):
    """Crop and downsample one BGR frame onto the matrix pixel buffer."""
    h, w = frame.shape[:2]
    x0, x1 = compute_crop(w, h)

    crop  = frame[:, x0:x1]                                       # centred slice
    small = cv2.resize(crop, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)

    for y in range(HEIGHT):
        for x in range(WIDTH):
            b, g, r = small[y, x]
            matrix.set_pixel(x, y, (int(r), int(g), int(b)))

def annotate_camera(frame):
    """Draw the crop zone outline and label on a copy of the frame."""
    out = frame.copy()
    h, w = out.shape[:2]
    x0, x1 = compute_crop(w, h)
    cv2.rectangle(out, (x0, 0), (x1, h - 1), (0, 220, 0), 2)
    cv2.putText(out, "crop", (x0 + 4, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 1, cv2.LINE_AA)
    return out

# ── Main loop ─────────────────────────────────────────────────────────────────

frame_count = 0
t_report    = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        print("capture failed")
        continue

    frame_to_matrix(frame)

    cam_panel    = make_label(annotate_camera(frame), "Camera")
    matrix_panel = make_label(matrix.render(), "LED Matrix (16x32)")
    cv2.imshow("Cam -> Matrix", side_by_side(cam_panel, matrix_panel))

    frame_count += 1
    now = time.time()
    if now - t_report >= 2.0:
        print(f"{frame_count / (now - t_report):.1f} fps")
        frame_count = 0
        t_report    = now

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
