"""
Camera → LED matrix live view.

Captures RGB565 frames from the OV2640 at the smallest supported
resolution, downsamples them to fit the 16×32 WS2812 matrix, and
pushes the result out continuously.

Target: ≥ 5 fps (realistically 10–16 fps on ESP32-S3).

Performance strategy
--------------------
* RGB565 pixel format  — no JPEG decode needed.
* Smallest frame size  — less data, faster sensor readout.
* Pre-computed indices — the hot loop does only byte reads + bit ops,
                         no per-frame multiplication or index arithmetic.
* Centred crop         — the camera is landscape (4:3), the matrix is
                         portrait (1:2); we crop a centred vertical
                         slice from the frame so the image isn't squished.

Snake wiring: pixel 0 at top-right, even rows right→left,
              odd rows left→right (same as ledmatrix_test.py).
"""

import time
import math
import board
import microcontroller
import neopixel
import espcamera

# ── Configuration ─────────────────────────────────────────────────────────────

# GPIO14 is the free pin on the left header (board.IO14 not exposed by this firmware)
MATRIX_PIN = microcontroller.pin.GPIO14
WIDTH      = 16           # matrix columns
HEIGHT     = 32           # matrix rows
BRIGHTNESS = 0.20         # 0.0–1.0

# Camera: use the smallest frame that is at least WIDTH × HEIGHT pixels.
# B96X96 (96×96) is the smallest the OV2640 supports.
# Fall back to QQVGA (160×120) if B96X96 doesn't work on your firmware build.
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
    brightness=BRIGHTNESS,
    auto_write=False,
    pixel_order=neopixel.GRB,
)

# ── Camera setup ──────────────────────────────────────────────────────────────

i2c = board.I2C()   # OV2640 config bus

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

cam.vflip   = True  # sensor is mounted upside-down on this board
cam.hmirror = True  # mirror so left/right match viewer expectation

# Discard a few frames so auto-exposure can settle.
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
#
# The frame is landscape; the matrix is portrait (1:2).
# We take a centred vertical crop of the frame that matches the 1:2 ratio,
# then sample it with integer steps.
#
#   crop width  = FRAME_HEIGHT // 2       (half the frame height → 1:2 ratio)
#   crop left   = (FRAME_WIDTH - crop_w) // 2   (centred horizontally)
#
# step_x = crop_w // WIDTH     step_y = FRAME_HEIGHT // HEIGHT

_crop_w    = FRAME_HEIGHT // 2                      # e.g. 96//2 = 48
_crop_left = (FRAME_WIDTH - _crop_w) // 2           # e.g. (96-48)//2 = 24
_step_x    = max(1, _crop_w    // WIDTH)             # e.g. 48//16 = 3
_step_y    = max(1, FRAME_HEIGHT // HEIGHT)          # e.g. 96//32 = 3

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

# ── Hot loop ──────────────────────────────────────────────────────────────────

def apply_frame(frame):
    """Downsample one RGB565 frame onto the pixel buffer (no show() call)."""
    for led, pixel in _SAMPLE_MAP:
        px = frame[pixel]
        # Bitmap stores bytes DMA-order: lo byte first in memory → px low bits = RRRRRGGG
        hi =  px       & 0xFF
        lo = (px >> 8) & 0xFF
        r = hi & 0xF8
        g = ((hi & 0x07) << 5) | ((lo & 0xE0) >> 3)
        b = (lo & 0x1F) << 3
        pixels[led] = (r, g, b)

# ── Main loop ─────────────────────────────────────────────────────────────────

pixels.fill((0, 0, 0))
pixels.show()

frame_count = 0
t_report    = time.monotonic()

while True:
    frame = cam.take()
    if frame is None:
        print("frame timeout")
        continue

    apply_frame(frame)
    pixels.show()
    frame_count += 1

    # Print fps every 2 seconds.
    now = time.monotonic()
    if now - t_report >= 2.0:
        fps = frame_count / (now - t_report)
        print(f"{fps:.1f} fps")
        frame_count = 0
        t_report    = now
