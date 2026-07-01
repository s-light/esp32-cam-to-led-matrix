"""
Camera → LED matrix — foreground extraction with contrast correction and grayscale mode.

Based on cam_to_matrix_fg.py.  Two additions:

  3. Contrast correction
     A 256-entry look-up table (built once at startup) maps each 8-bit channel
     value through a linear contrast stretch centred on 128.  CONTRAST_FACTOR
     > 1.0 increases contrast; BRIGHTNESS_OFFSET shifts the input before
     stretching (positive = brighter mid-tones).  The LUT is applied to
     foreground pixels only (after background subtraction), so detection
     sensitivity is unaffected.

  4. Grayscale / monochrome mode
     When GRAYSCALE_MODE is True the output is rendered in a single tint colour
     (GRAY_WHITE).  Each foreground pixel's BT.601 luminance is computed and
     used to scale GRAY_WHITE, giving a power-efficient monochrome look.
     Only one colour channel drives current instead of three independent
     RGB channels, so peak current is lower for the same apparent brightness.

Note on bitmapfilter
     circuitpython's bitmapfilter module operates on the *full* 160×120 frame
     (19 200 pixels) and cannot express per-pixel background subtraction.
     Our hot loop already only visits 512 sampled pixels, so adding a
     bitmapfilter pre-pass would be strictly slower.  It is not used here.
"""

import time
import board
import microcontroller
import neopixel
import espcamera
from digitalio import DigitalInOut, Direction, Pull

# ── Configuration ─────────────────────────────────────────────────────────────

MATRIX_PIN = microcontroller.pin.GPIO14
WIDTH = 16
HEIGHT = 32

# Background subtraction
DIFF_THRESHOLD = 30
BG_CAPTURE_FRAMES = 6

# Power management
MAX_BRIGHTNESS = 0.30
CURRENT_PER_LED_MA = 60
POWER_BUDGET_MA = 500

# Camera
FRAME_SIZE = espcamera.FrameSize.QQVGA
FRAME_WIDTH = 160
FRAME_HEIGHT = 120

XCLK_FREQ = 20_000_000

# ── Contrast correction ───────────────────────────────────────────────────────
#
# Applied to foreground pixels before they reach the matrix.
# CONTRAST_FACTOR = 1.0  → no change
# CONTRAST_FACTOR = 1.5  → modest boost (good starting point)
# CONTRAST_FACTOR = 2.0  → strong boost, may clip highlights
# BRIGHTNESS_OFFSET shifts input values before stretching; positive values
# lift dark mid-tones, negative values push them down.

CONTRAST_FACTOR = 1.5
BRIGHTNESS_OFFSET = 10  # slight lift to compensate for dim LED output


def _build_contrast_lut(factor, offset):
    lut = []
    for v in range(256):
        adjusted = int(128 + factor * (v + offset - 128))
        lut.append(max(0, min(255, adjusted)))
    return lut


_CONTRAST_LUT = _build_contrast_lut(CONTRAST_FACTOR, BRIGHTNESS_OFFSET)

# ── Grayscale / monochrome mode ───────────────────────────────────────────────
#
# Set GRAYSCALE_MODE = True to render output as a single tint.
# GRAY_WHITE is the colour used for "full brightness" pixels.
# Examples:
#   (255, 255, 255)  → pure white  (same current as full-colour)
#   (255, 140,   0)  → amber/warm  (lower blue draw)
#   (  0, 255,   0)  → green       (lowest draw — green LED is most efficient)
#   (255, 200,  80)  → warm white

GRAYSCALE_MODE = True
GRAY_WHITE = (0, 255, 0)

_GW_R, _GW_G, _GW_B = GRAY_WHITE

# ── NeoPixel setup ────────────────────────────────────────────────────────────

pixels = neopixel.NeoPixel(
    MATRIX_PIN,
    WIDTH * HEIGHT,
    brightness=MAX_BRIGHTNESS,
    auto_write=False,
    pixel_order=neopixel.GRB,
)

# ── Button setup (GPIO0, active-low) ──────────────────────────────────────────
# Addressed via microcontroller.pin so this works whether the board exposes it
# as board.BOOT (e.g. espressif_esp32s3_eye) or board.BUTTON (e.g. Freenove
# ESP32-WROVER-DEV-CAM) — both name the same physical pin.

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

# ── Coordinate mapping ────────────────────────────────────────────────────────


def xy_to_index(x, y):
    """Snake layout: pixel 0 at top-right, even rows right→left."""
    if y % 2 == 0:
        return y * WIDTH + (WIDTH - 1 - x)
    else:
        return y * WIDTH + x


# ── Pre-compute sample map ────────────────────────────────────────────────────

_crop_w = FRAME_HEIGHT // 2
_crop_left = (FRAME_WIDTH - _crop_w) // 2
_step_x = max(1, _crop_w // WIDTH)
_step_y = max(1, FRAME_HEIGHT // HEIGHT)

_SAMPLE_MAP = []
for _y in range(HEIGHT):
    _src_y = _y * _step_y
    for _x in range(WIDTH):
        _src_x = _crop_left + _x * _step_x
        _led = xy_to_index(_x, _y)
        _pixel = _src_y * FRAME_WIDTH + _src_x
        _SAMPLE_MAP.append((_led, _pixel))

print(
    f"Sample map: crop {_crop_w}×{FRAME_HEIGHT} "
    f"at x={_crop_left}, step {_step_x}×{_step_y} → {WIDTH}×{HEIGHT}"
)

# ── Background reference ──────────────────────────────────────────────────────

_background = [(0, 0, 0)] * (WIDTH * HEIGHT)


def _decode_rgb565(frame, pixel):
    """Extract (r, g, b) from a uint16 RGB565 frame at the given pixel index."""
    px = frame[pixel]
    hi = px & 0xFF
    lo = (px >> 8) & 0xFF
    r = hi & 0xF8
    g = ((hi & 0x07) << 5) | ((lo & 0xE0) >> 3)
    b = (lo & 0x1F) << 3
    return r, g, b


def capture_background():
    """Average BG_CAPTURE_FRAMES frames into _background."""
    global _background

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
        (
            acc[0] // BG_CAPTURE_FRAMES,
            acc[1] // BG_CAPTURE_FRAMES,
            acc[2] // BG_CAPTURE_FRAMES,
        )
        for acc in accum
    ]

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
    safe = MAX_BRIGHTNESS / max(needed, 1.0)
    pixels.brightness = min(MAX_BRIGHTNESS, safe)


# ── Hot loop ──────────────────────────────────────────────────────────────────


def apply_frame_foreground(frame):
    """Downsample, subtract background, apply contrast + optional grayscale.

    Returns the number of lit (foreground) pixels.
    """
    lit = 0
    lut = _CONTRAST_LUT  # local ref — faster attribute lookup in CP
    gray = GRAYSCALE_MODE

    for led, pixel in _SAMPLE_MAP:
        r, g, b = _decode_rgb565(frame, pixel)

        br, bg, bb = _background[led]
        diff = abs(r - br) + abs(g - bg) + abs(b - bb)

        if diff >= DIFF_THRESHOLD:
            # Contrast correction via LUT
            r = lut[r]
            g = lut[g]
            b = lut[b]

            if gray:
                # BT.601 luma: coefficients sum to 256 so >> 8 gives 0-255
                y = (r * 77 + g * 150 + b * 29) >> 8
                pixels[led] = ((_GW_R * y) >> 8, (_GW_G * y) >> 8, (_GW_B * y) >> 8)
            else:
                pixels[led] = (r, g, b)

            lit += 1
        else:
            pixels[led] = (0, 0, 0)

    return lit


# ── Startup ───────────────────────────────────────────────────────────────────

pixels.fill((0, 0, 0))
pixels.show()

mode_label = f"grayscale {GRAY_WHITE}" if GRAYSCALE_MODE else "colour"
print(f"Mode: {mode_label}  |  contrast ×{CONTRAST_FACTOR}  offset {BRIGHTNESS_OFFSET:+d}")
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

    lit = apply_frame_foreground(frame)
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
