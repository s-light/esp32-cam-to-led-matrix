"""
Camera → LED matrix — foreground-only with power cap.

Extends cam_to_matrix.py with two additions:

  1. Background subtraction
     A reference frame is captured at startup and stored as a 16×32
     RGB array.  Each live frame is compared pixel-by-pixel against
     this reference; pixels that differ less than DIFF_THRESHOLD are
     set to black.  Only the foreground (people, objects) lights up.
     Press the BOOT button (GPIO0) at any time to recapture the
     background — useful after lighting changes.

  2. Dynamic power cap
     After the foreground mask is applied, the number of lit pixels is
     counted.  If that count would push current draw above POWER_BUDGET_MA
     (assuming CURRENT_PER_LED_MA per fully-bright pixel), brightness is
     scaled down automatically to stay within budget.

Everything else (camera init, sample map, snake layout) is identical to
cam_to_matrix.py so you can diff the two files to see exactly what changed.
"""

import time
import board
import microcontroller
import neopixel
import espcamera
from digitalio import DigitalInOut, Direction, Pull

# ── Configuration ─────────────────────────────────────────────────────────────

# GPIO14 is the free pin on the left header (board.IO14 not exposed by this firmware)
MATRIX_PIN = microcontroller.pin.GPIO14
WIDTH      = 16           # matrix columns
HEIGHT     = 32           # matrix rows

# Background subtraction
DIFF_THRESHOLD    = 30    # 0–255 per channel sum; lower = more sensitive
BG_CAPTURE_FRAMES = 6     # frames averaged for a stable background reference

# Power management
MAX_BRIGHTNESS      = 0.30   # absolute ceiling (0.0–1.0)
CURRENT_PER_LED_MA  = 60     # mA per LED at full white, full brightness
POWER_BUDGET_MA     = 1500   # mA total budget for the matrix (e.g. 1.5 A supply)

# Camera
FRAME_SIZE   = espcamera.FrameSize.QQVGA
FRAME_WIDTH  = 160
FRAME_HEIGHT = 120
# For B96X96 uncomment these two lines instead (if supported by firmware):
# FRAME_SIZE   = espcamera.FrameSize.B96X96
# FRAME_WIDTH, FRAME_HEIGHT = 96, 96

XCLK_FREQ = 20_000_000

# ── NeoPixel setup ────────────────────────────────────────────────────────────

pixels = neopixel.NeoPixel(
    MATRIX_PIN,
    WIDTH * HEIGHT,
    brightness=MAX_BRIGHTNESS,
    auto_write=False,
    pixel_order=neopixel.GRB,
)

# ── Button setup (BOOT = GPIO0, active-low) ───────────────────────────────────

btn = DigitalInOut(board.IO0)
btn.direction = Direction.INPUT
btn.pull = Pull.UP

def button_pressed():
    return not btn.value   # active-low

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

print("Warming up camera …")
for _ in range(8):
    cam.take()
print(f"Camera ready: {cam.width}×{cam.height} RGB565")

# ── Coordinate mapping ────────────────────────────────────────────────────────

def xy_to_index(x, y):
    """Snake layout: pixel 0 at top-right, even rows right→left."""
    if y % 2 == 0:
        return y * WIDTH + (WIDTH - 1 - x)
    else:
        return y * WIDTH + x

# ── Pre-compute sample map ────────────────────────────────────────────────────
# (identical to cam_to_matrix.py — see that file for the crop/ratio explanation)

_crop_w    = FRAME_HEIGHT // 2
_crop_left = (FRAME_WIDTH - _crop_w) // 2
_step_x    = max(1, _crop_w     // WIDTH)
_step_y    = max(1, FRAME_HEIGHT // HEIGHT)

# Each entry: (led_index, frame_pixel_index)
# Frame is a uint16 Bitmap: one element per pixel, bytes DMA-swapped (lo=RRRRRGGG, hi=GGGBBBBB).
_SAMPLE_MAP = []
for _y in range(HEIGHT):
    _src_y = _y * _step_y
    for _x in range(WIDTH):
        _src_x = _crop_left + _x * _step_x
        _led   = xy_to_index(_x, _y)
        _pixel = _src_y * FRAME_WIDTH + _src_x
        _SAMPLE_MAP.append((_led, _pixel))

print(
    f"Sample map: crop {_crop_w}×{FRAME_HEIGHT} "
    f"at x={_crop_left}, step {_step_x}×{_step_y} → {WIDTH}×{HEIGHT}"
)

# ── Background reference ──────────────────────────────────────────────────────
#
# Stored as a flat list of (r, g, b) tuples, indexed by led_index.
# Only 512 × 3 bytes — tiny compared to a full camera frame.

_background = [(0, 0, 0)] * (WIDTH * HEIGHT)

def _decode_rgb565(frame, pixel):
    """Extract (r, g, b) from a uint16 RGB565 frame at the given pixel index."""
    px = frame[pixel]
    hi =  px       & 0xFF
    lo = (px >> 8) & 0xFF
    r = hi & 0xF8
    g = ((hi & 0x07) << 5) | ((lo & 0xE0) >> 3)
    b = (lo & 0x1F) << 3
    return r, g, b

def capture_background():
    """Average BG_CAPTURE_FRAMES frames into _background.

    Averaging reduces noise so the diff threshold can be set tighter
    without flickering on static scenes.
    """
    global _background

    # Flash all pixels white briefly so the user knows a capture is happening.
    pixels.fill((40, 40, 40))
    pixels.show()

    accum = [[0, 0, 0] for _ in range(WIDTH * HEIGHT)]

    for _ in range(BG_CAPTURE_FRAMES):
        frame = cam.take()
        if frame is None:
            continue
        for led, pixel in _SAMPLE_MAP:
            r, g, b = _decode_rgb565(frame, pixel)
            accum[led][0] += r
            accum[led][1] += g
            accum[led][2] += b

    _background = [
        (acc[0] // BG_CAPTURE_FRAMES,
         acc[1] // BG_CAPTURE_FRAMES,
         acc[2] // BG_CAPTURE_FRAMES)
        for acc in accum
    ]

    pixels.fill((0, 0, 0))
    pixels.show()
    print("Background captured.")

# ── Power cap ─────────────────────────────────────────────────────────────────
#
# Max pixels that fit in the budget at full brightness:
#   budget_px = POWER_BUDGET_MA / CURRENT_PER_LED_MA
#
# If more pixels are lit we scale brightness linearly so that:
#   lit_px × CURRENT_PER_LED_MA × brightness ≤ POWER_BUDGET_MA

_BUDGET_PX = POWER_BUDGET_MA / CURRENT_PER_LED_MA   # ~25 px at 1500 mA / 60 mA

def apply_power_cap(lit_count):
    """Adjust pixels.brightness to stay within the current budget."""
    if lit_count == 0:
        pixels.brightness = MAX_BRIGHTNESS
        return
    needed = lit_count / _BUDGET_PX          # ratio: how many times over budget
    safe   = MAX_BRIGHTNESS / max(needed, 1.0)
    pixels.brightness = min(MAX_BRIGHTNESS, safe)

# ── Hot loop ──────────────────────────────────────────────────────────────────

def apply_frame_foreground(frame):
    """Downsample frame, subtract background, black-out near-background pixels.

    Returns the number of lit (foreground) pixels.
    """
    lit = 0
    for led, pixel in _SAMPLE_MAP:
        r, g, b = _decode_rgb565(frame, pixel)

        br, bg, bb = _background[led]
        diff = abs(r - br) + abs(g - bg) + abs(b - bb)

        if diff >= DIFF_THRESHOLD:
            pixels[led] = (r, g, b)
            lit += 1
        else:
            pixels[led] = (0, 0, 0)

    return lit

# ── Startup ───────────────────────────────────────────────────────────────────

pixels.fill((0, 0, 0))
pixels.show()

print("Capturing initial background …")
capture_background()
print(f"Power budget: {POWER_BUDGET_MA} mA → max ~{int(_BUDGET_PX)} fully-lit pixels")
print("Press BOOT button to recapture background.")

# ── Main loop ─────────────────────────────────────────────────────────────────

frame_count = 0
t_report    = time.monotonic()

while True:
    # Recapture background on button press.
    if button_pressed():
        print("Button pressed — recapturing background …")
        capture_background()
        # Debounce: wait for release.
        while button_pressed():
            time.sleep(0.05)

    frame = cam.take()
    if frame is None:
        print("frame timeout")
        continue

    lit = apply_frame_foreground(frame)
    apply_power_cap(lit)
    pixels.show()
    frame_count += 1

    # Print fps + power info every 2 seconds.
    now = time.monotonic()
    if now - t_report >= 2.0:
        fps = frame_count / (now - t_report)
        print(
            f"{fps:.1f} fps  |  {lit} lit px  |  "
            f"brightness {pixels.brightness:.2f}  |  "
            f"~{int(lit * CURRENT_PER_LED_MA * pixels.brightness)} mA"
        )
        frame_count = 0
        t_report    = now
