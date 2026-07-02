"""
Camera → LED matrix, foreground-only with power cap — desktop version of
circuitpython/CIRCUITPY_disc/main.py.

Runs against a live webcam (default) or a recorded board camera video (see
video_source.py):

    python cam_to_matrix_fg.py            # webcam index 0
    python cam_to_matrix_fg.py 1          # webcam index 1
    python cam_to_matrix_fg.py rec_0000.rawvid   # recorded board footage

The foreground-extraction algorithm (background subtraction, contrast LUT,
grayscale) lives in circuitpython/CIRCUITPY_disc/cam_algo.py and is imported
from there (see the sys.path shim below), so this script and the on-device
main.py always run identical logic — a change tested here ports to the board
with no translation step.

Side-by-side window shows three panels:
  Left   — camera feed with crop zone outlined
  Centre — background reference (what was captured)
  Right  — LED matrix simulation (foreground pixels only)

Controls
--------
  Q          quit
  Space / B  recapture background
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np

from led_simulator import LedMatrix, make_label, side_by_side
from video_source import open_source

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "circuitpython" / "CIRCUITPY_disc")
)
import cam_algo  # noqa: E402 — path shim above must run first

# ── Configuration ─────────────────────────────────────────────────────────────

SOURCE = sys.argv[1] if len(sys.argv) > 1 else 0
WIDTH = 16
HEIGHT = 32
WARMUP_FRAMES = 8

# Background subtraction
DIFF_THRESHOLD = 30  # 0–765 (sum of per-channel abs diff); lower = more sensitive
BG_CAPTURE_FRAMES = 6  # frames averaged for the background reference

# Contrast correction (applied to foreground pixels only)
CONTRAST_FACTOR = 1.5
BRIGHTNESS_OFFSET = 10

# Grayscale / monochrome mode
GRAYSCALE_MODE = True
GRAY_COLOR = (0, 255, 0)

# Power cap
MAX_BRIGHTNESS = 0.90  # absolute ceiling (desktop: can go higher than hardware)
CURRENT_PER_LED_MA = 60  # mA per LED at full white
POWER_BUDGET_MA = 2100  # current bench PSU rating (a higher-capacity PSU is planned)

# ── Matrix and camera setup ───────────────────────────────────────────────────

matrix = LedMatrix(
    WIDTH, HEIGHT, brightness=MAX_BRIGHTNESS, window_title="Cam -> Matrix (FG)"
)

cap = open_source(SOURCE)
if not cap.isOpened():
    raise RuntimeError(f"Could not open source {SOURCE!r}")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 160)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 120)

actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 160
actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 120
print(f"Source: {SOURCE!r} — {actual_w}x{actual_h}")

print("Warming up ...")
for _ in range(WARMUP_FRAMES):
    cap.read()

_CONTRAST_LUT = cam_algo.build_contrast_lut(CONTRAST_FACTOR, BRIGHTNESS_OFFSET)
_SAMPLE_MAP = cam_algo.build_sample_map(actual_w, actual_h, WIDTH, HEIGHT)

# ── Crop helpers (for the camera preview panel only) ──────────────────────────


def compute_crop(frame_w, frame_h):
    crop_w = frame_h // 2
    x_start = (frame_w - crop_w) // 2
    return x_start, x_start + crop_w


def annotate_camera(frame):
    out = frame.copy()
    h, w = out.shape[:2]
    x0, x1 = compute_crop(w, h)
    cv2.rectangle(out, (x0, 0), (x1, h - 1), (0, 220, 0), 2)
    cv2.putText(
        out,
        "crop",
        (x0 + 4, 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 220, 0),
        1,
        cv2.LINE_AA,
    )
    return out


# ── Background reference ──────────────────────────────────────────────────────

_background = [(0, 0, 0)] * (WIDTH * HEIGHT)


def _frame_sample_fn(frame):
    def sample_fn(x, y):
        b, g, r = frame[y, x]
        return int(r), int(g), int(b)

    return sample_fn


def _next_frame_sample_fn():
    ret, frame = cap.read()
    while not ret:
        ret, frame = cap.read()
    return _frame_sample_fn(frame)


def capture_background():
    global _background

    matrix.fill((60, 60, 60))
    matrix.show()
    time.sleep(0.1)

    _background = cam_algo.capture_background(
        _next_frame_sample_fn, _SAMPLE_MAP, BG_CAPTURE_FRAMES
    )

    matrix.fill((0, 0, 0))
    matrix.show()
    print("Background captured.")


def background_preview():
    """Return a display-ready BGR uint8 image of the current background."""
    img = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for led, dx, dy, _sx, _sy in _SAMPLE_MAP:
        r, g, b = _background[led]
        img[dy, dx] = (b, g, r)
    return cv2.resize(img, (WIDTH * 8, HEIGHT * 8), interpolation=cv2.INTER_NEAREST)


# ── Power cap ─────────────────────────────────────────────────────────────────

_BUDGET_PX = POWER_BUDGET_MA / CURRENT_PER_LED_MA


def apply_power_cap(lit_count):
    if lit_count == 0:
        matrix.brightness = MAX_BRIGHTNESS
        return
    needed = lit_count / _BUDGET_PX
    matrix.brightness = min(MAX_BRIGHTNESS, MAX_BRIGHTNESS / max(needed, 1.0))


# ── Frame processing ──────────────────────────────────────────────────────────


def render_frame(frame):
    """Run the shared algorithm and push the result into the matrix simulator.

    Returns the number of lit (foreground) pixels.
    """
    results, lit = cam_algo.apply_foreground(
        _frame_sample_fn(frame),
        _SAMPLE_MAP,
        _background,
        DIFF_THRESHOLD,
        contrast_lut=_CONTRAST_LUT,
        grayscale=GRAYSCALE_MODE,
        gray_color=GRAY_COLOR,
    )
    for led, r, g, b in results:
        matrix[led] = (r, g, b)
    return lit


# ── Startup ───────────────────────────────────────────────────────────────────

mode_label = f"grayscale {GRAY_COLOR}" if GRAYSCALE_MODE else "colour"
print(
    f"Mode: {mode_label}  |  contrast ×{CONTRAST_FACTOR}  offset {BRIGHTNESS_OFFSET:+d}"
)
print("Capturing initial background — keep the scene empty …")
capture_background()
print(f"Power budget: {POWER_BUDGET_MA} mA → max ~{int(_BUDGET_PX)} fully-lit pixels")
print("Press Space or B to recapture background, Q to quit.")

# ── Main loop ─────────────────────────────────────────────────────────────────

frame_count = 0
t_report = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        print("capture failed")
        continue

    lit = render_frame(frame)
    apply_power_cap(lit)

    cam_panel = make_label(annotate_camera(frame), "Camera")
    bg_panel = make_label(background_preview(), "Background ref")
    matrix_panel = make_label(matrix.render(), "LED Matrix (FG only)")

    cv2.imshow("Cam -> Matrix (FG)", side_by_side(cam_panel, bg_panel, matrix_panel))

    frame_count += 1
    now = time.time()
    if now - t_report >= 2.0:
        print(
            f"{frame_count / (now - t_report):.1f} fps  |  "
            f"{lit} lit px  |  brightness {matrix.brightness:.2f}  |  "
            f"~{int(lit * CURRENT_PER_LED_MA * matrix.brightness)} mA"
        )
        frame_count = 0
        t_report = now

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    if key in (ord(" "), ord("b")):
        print("Recapturing background …")
        capture_background()

cap.release()
cv2.destroyAllWindows()
