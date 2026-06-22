"""
Camera → LED matrix, foreground-only with power cap — desktop version of
circuitpython/example/cam_to_matrix_fg.py.

Side-by-side window shows three panels:
  Left   — camera feed with crop zone outlined
  Centre — background reference (what was captured)
  Right  — LED matrix simulation (foreground pixels only)

Background subtraction uses numpy array ops instead of a Python pixel loop,
which is substantially faster on the desktop.  The logic and constants are
otherwise identical to the CircuitPython version.

Controls
--------
  Q          quit
  Space / B  recapture background
"""

import time
import cv2
import numpy as np
from led_simulator import LedMatrix, make_label, side_by_side

# ── Configuration ─────────────────────────────────────────────────────────────

CAMERA_INDEX = 0
WIDTH        = 16
HEIGHT       = 32
WARMUP_FRAMES = 8

# Background subtraction
DIFF_THRESHOLD    = 30    # 0–765 (sum of per-channel abs diff); lower = more sensitive
BG_CAPTURE_FRAMES = 6     # frames averaged for the background reference

# Power cap
MAX_BRIGHTNESS     = 0.90   # absolute ceiling (desktop: can go higher than hardware)
CURRENT_PER_LED_MA = 60     # mA per LED at full white
POWER_BUDGET_MA    = 1500   # target max current for the matrix

# ── Matrix and camera setup ───────────────────────────────────────────────────

matrix = LedMatrix(WIDTH, HEIGHT, brightness=MAX_BRIGHTNESS,
                   window_title="Cam → Matrix (FG)")

cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    raise RuntimeError(f"Could not open camera index {CAMERA_INDEX}")

print(f"Camera: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}×"
      f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

print("Warming up …")
for _ in range(WARMUP_FRAMES):
    cap.read()

# ── Crop helpers ──────────────────────────────────────────────────────────────

def compute_crop(frame_w, frame_h):
    crop_w  = frame_h // 2
    x_start = (frame_w - crop_w) // 2
    return x_start, x_start + crop_w

def get_small(frame):
    """Return a WIDTH×HEIGHT RGB float32 crop of the frame (0–255)."""
    h, w = frame.shape[:2]
    x0, x1 = compute_crop(w, h)
    crop  = frame[:, x0:x1]
    small = cv2.resize(crop, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)
    return small.astype(np.float32)

def annotate_camera(frame):
    out = frame.copy()
    h, w = out.shape[:2]
    x0, x1 = compute_crop(w, h)
    cv2.rectangle(out, (x0, 0), (x1, h - 1), (0, 220, 0), 2)
    cv2.putText(out, "crop", (x0 + 4, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 1, cv2.LINE_AA)
    return out

# ── Background reference ──────────────────────────────────────────────────────
#
# Stored as a float32 numpy array of shape (HEIGHT, WIDTH, 3) in BGR.
# float32 lets us accumulate frames for averaging without overflow.

_background = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)

def capture_background():
    """Average BG_CAPTURE_FRAMES frames into _background."""
    global _background

    # Brief white flash on the matrix to signal capture.
    matrix.fill((60, 60, 60))
    matrix.show()
    time.sleep(0.1)

    accum = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
    captured = 0
    while captured < BG_CAPTURE_FRAMES:
        ret, frame = cap.read()
        if not ret:
            continue
        accum += get_small(frame)
        captured += 1

    _background = accum / BG_CAPTURE_FRAMES

    matrix.fill((0, 0, 0))
    matrix.show()
    print("Background captured.")

# ── Power cap ─────────────────────────────────────────────────────────────────

_BUDGET_PX = POWER_BUDGET_MA / CURRENT_PER_LED_MA

def apply_power_cap(lit_count):
    if lit_count == 0:
        matrix.brightness = MAX_BRIGHTNESS
        return
    needed = lit_count / _BUDGET_PX
    matrix.brightness = min(MAX_BRIGHTNESS, MAX_BRIGHTNESS / max(needed, 1.0))

# ── Frame processing ──────────────────────────────────────────────────────────

def apply_frame_foreground(frame):
    """Subtract background, mask near-background pixels, fill matrix.

    Returns the number of lit (foreground) pixels.
    Uses numpy operations instead of a Python pixel loop for speed.
    """
    small = get_small(frame)   # float32 BGR, shape (H, W, 3)

    # Per-pixel Manhattan distance across all three channels.
    diff = np.sum(np.abs(small - _background), axis=2)   # shape (H, W)
    mask = diff >= DIFF_THRESHOLD                          # True = foreground

    lit = int(np.count_nonzero(mask))

    for y in range(HEIGHT):
        for x in range(WIDTH):
            if mask[y, x]:
                b, g, r = small[y, x]
                matrix.set_pixel(x, y, (int(r), int(g), int(b)))
            else:
                matrix.set_pixel(x, y, (0, 0, 0))

    return lit

def background_preview():
    """Return a display-ready BGR uint8 image of the current background."""
    bg_uint8 = np.clip(_background, 0, 255).astype(np.uint8)
    # Scale up to a visible size while keeping pixel-perfect look.
    return cv2.resize(bg_uint8, (WIDTH * 8, HEIGHT * 8), interpolation=cv2.INTER_NEAREST)

# ── Startup ───────────────────────────────────────────────────────────────────

print("Capturing initial background — keep the scene empty …")
capture_background()
print(f"Power budget: {POWER_BUDGET_MA} mA → max ~{int(_BUDGET_PX)} fully-lit pixels")
print("Press Space or B to recapture background, Q to quit.")

# ── Main loop ─────────────────────────────────────────────────────────────────

frame_count = 0
t_report    = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        print("capture failed")
        continue

    lit = apply_frame_foreground(frame)
    apply_power_cap(lit)

    cam_panel    = make_label(annotate_camera(frame), "Camera")
    bg_panel     = make_label(background_preview(),   "Background ref")
    matrix_panel = make_label(matrix.render(),        "LED Matrix (FG only)")

    cv2.imshow("Cam → Matrix (FG)", side_by_side(cam_panel, bg_panel, matrix_panel))

    frame_count += 1
    now = time.time()
    if now - t_report >= 2.0:
        print(
            f"{frame_count / (now - t_report):.1f} fps  |  "
            f"{lit} lit px  |  brightness {matrix.brightness:.2f}  |  "
            f"~{int(lit * CURRENT_PER_LED_MA * matrix.brightness)} mA"
        )
        frame_count = 0
        t_report    = now

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    if key in (ord(' '), ord('b')):
        print("Recapturing background …")
        capture_background()

cap.release()
cv2.destroyAllWindows()
