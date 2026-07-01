"""
Camera → LED matrix, foreground-only with power cap, contrast + grayscale.

This is the on-device "final product" script (as opposed to the teaching
examples in circuitpython/example/). The foreground-extraction algorithm
itself lives in cam_algo.py, shared with the desktop OpenCV version in
pythonOpenCV/cam_to_matrix_fg.py, so changes tested on a laptop port here
with no translation step — see cam_algo.py's docstring.

Board: diymore ESP32 S3 CAM running espressif_esp32s3_eye CircuitPython
firmware (see memory/hw_findings.md for the quirks this code works around).
"""

import time
import board
import microcontroller
import neopixel
import espcamera
from digitalio import DigitalInOut, Direction, Pull

import cam_algo

# ── Configuration ─────────────────────────────────────────────────────────────

MATRIX_PIN = microcontroller.pin.GPIO14
WIDTH = 16
HEIGHT = 32

# Background subtraction
DIFF_THRESHOLD = 30
BG_CAPTURE_FRAMES = 6

# Contrast correction (applied to foreground pixels only)
CONTRAST_FACTOR = 1.5
BRIGHTNESS_OFFSET = 10  # slight lift to compensate for dim LED output

# Grayscale / monochrome mode
GRAYSCALE_MODE = True
GRAY_COLOR = (0, 255, 0)

# Power management
MAX_BRIGHTNESS = 0.30
CURRENT_PER_LED_MA = 60
POWER_BUDGET_MA = 500

# Camera
FRAME_SIZE = espcamera.FrameSize.QQVGA
FRAME_WIDTH = 160
FRAME_HEIGHT = 120
XCLK_FREQ = 20_000_000

_CONTRAST_LUT = cam_algo.build_contrast_lut(CONTRAST_FACTOR, BRIGHTNESS_OFFSET)
_SAMPLE_MAP = cam_algo.build_sample_map(FRAME_WIDTH, FRAME_HEIGHT, WIDTH, HEIGHT)

# ── NeoPixel setup ────────────────────────────────────────────────────────────

pixels = neopixel.NeoPixel(
    MATRIX_PIN,
    WIDTH * HEIGHT,
    brightness=MAX_BRIGHTNESS,
    auto_write=False,
    pixel_order=neopixel.GRB,
)

# ── Button setup (GPIO0, active-low) ──────────────────────────────────────────

btn = DigitalInOut(microcontroller.pin.GPIO0)
btn.direction = Direction.INPUT
btn.pull = Pull.UP


def button_pressed():
    return not btn.value


# ── Camera setup ──────────────────────────────────────────────────────────────

i2c = board.I2C()

cam = espcamera.Camera(
    data_pins=board.CAMERA_DATA,
    external_clock_pin=board.CAMERA_XCLK,
    pixel_clock_pin=board.CAMERA_PCLK,
    vsync_pin=board.CAMERA_VSYNC,
    href_pin=board.CAMERA_HREF,
    i2c=i2c,
    external_clock_frequency=XCLK_FREQ,
    pixel_format=espcamera.PixelFormat.RGB565,
    frame_size=FRAME_SIZE,
    framebuffer_count=2,
)

cam.vflip = True
cam.hmirror = True

print("Warming up camera …")
for _ in range(8):
    cam.take()
print(f"Camera ready: {cam.width}×{cam.height} RGB565")

mode_label = f"grayscale {GRAY_COLOR}" if GRAYSCALE_MODE else "colour"
print(
    f"Mode: {mode_label}  |  contrast ×{CONTRAST_FACTOR}  offset {BRIGHTNESS_OFFSET:+d}"
)

# ── Background reference ──────────────────────────────────────────────────────

_background = [(0, 0, 0)] * (WIDTH * HEIGHT)


def _frame_sample_fn(frame):
    def sample_fn(x, y):
        return cam_algo.decode_rgb565(frame[y * FRAME_WIDTH + x])

    return sample_fn


def _next_frame_sample_fn():
    frame = cam.take()
    while frame is None:
        frame = cam.take()
    return _frame_sample_fn(frame)


def capture_background():
    global _background

    pixels.fill((40, 40, 40))
    pixels.show()

    _background = cam_algo.capture_background(
        _next_frame_sample_fn, _SAMPLE_MAP, BG_CAPTURE_FRAMES
    )

    pixels.fill((0, 0, 0))
    pixels.show()
    print("Background captured.")


# ── Power cap ─────────────────────────────────────────────────────────────────

_BUDGET_PX = POWER_BUDGET_MA / CURRENT_PER_LED_MA


def apply_power_cap(lit_count):
    if lit_count == 0:
        pixels.brightness = MAX_BRIGHTNESS
        return
    needed = lit_count / _BUDGET_PX
    pixels.brightness = min(MAX_BRIGHTNESS, MAX_BRIGHTNESS / max(needed, 1.0))


# ── Startup ───────────────────────────────────────────────────────────────────

pixels.fill((0, 0, 0))
pixels.show()

print("Capturing initial background …")
capture_background()
print(f"Power budget: {POWER_BUDGET_MA} mA → max ~{int(_BUDGET_PX)} fully-lit pixels")
print("Press button to recapture background.")

# ── Main loop ─────────────────────────────────────────────────────────────────

frame_count = 0
t_report = time.monotonic()

while True:
    if button_pressed():
        print("Button pressed — recapturing background …")
        capture_background()
        while button_pressed():
            time.sleep(0.05)

    frame = cam.take()
    if frame is None:
        print("frame timeout")
        continue

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
        pixels[led] = (r, g, b)

    apply_power_cap(lit)
    pixels.show()
    frame_count += 1

    now = time.monotonic()
    if now - t_report >= 2.0:
        fps = frame_count / (now - t_report)
        print(
            f"{fps:.1f} fps  |  {lit} lit px  |  "
            f"brightness {pixels.brightness:.2f}  |  "
            f"~{int(lit * CURRENT_PER_LED_MA * pixels.brightness)} mA"
        )
        frame_count = 0
        t_report = now
