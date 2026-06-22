"""
LED matrix test — 16×32 WS2812, snake layout, top-right origin.

Test sequence (loops forever):
  1. Vertical strip sweeping left → right
  2. Horizontal strip sweeping top → bottom
  3. Plasma animation in blue-green HSV range

Snake wiring convention:
  Pixel 0 is at the top-right corner.
  Even rows run right → left,  odd rows run left → right.

      col  15 14 13 … 1  0
  row 0:   [0  1  2 … 14 15]   right → left
  row 1:   [16 17 18… 30 31]   left  → right
  row 2:   [32 33 34… 46 47]   right → left
  …

Connect the matrix data-in line to a free GPIO.
GPIO14 is the only left-side pin with no dedicated on-board function.
"""

import time
import math
import board
import neopixel

# ── Configuration ─────────────────────────────────────────────────────────────

DATA_PIN   = board.IO14   # change to whichever GPIO the matrix is wired to
WIDTH      = 16           # columns
HEIGHT     = 32           # rows
BRIGHTNESS = 0.15         # 0.0–1.0  (keep low for direct viewing / power budget)

# Sweep speed and hold time for the strip tests
SWEEP_DELAY_S = 0.05   # pause between each step
SWEEP_HOLD_S  = 0.4    # pause after the full sweep finishes

# Plasma duration and speed
PLASMA_DURATION_S = 12.0
PLASMA_SPEED      = 1.4   # higher = faster animation

# Hue range for plasma: 0.333 = green, 0.5 = cyan, 0.667 = blue (all 0.0–1.0)
PLASMA_HUE_MIN = 0.40   # cyan-green
PLASMA_HUE_MAX = 0.70   # blue

# ── NeoPixel setup ────────────────────────────────────────────────────────────

pixels = neopixel.NeoPixel(
    DATA_PIN,
    WIDTH * HEIGHT,
    brightness=BRIGHTNESS,
    auto_write=False,
    pixel_order=neopixel.GRB,
)

# ── Coordinate mapping ────────────────────────────────────────────────────────

def xy_to_index(x, y):
    """Return the pixel index for logical (x, y), honouring the snake layout."""
    if y % 2 == 0:          # even row: right → left
        return y * WIDTH + (WIDTH - 1 - x)
    else:                    # odd row:  left  → right
        return y * WIDTH + x

def set_pixel(x, y, color):
    pixels[xy_to_index(x, y)] = color

def fill_matrix(color):
    pixels.fill(color)

def clear():
    pixels.fill((0, 0, 0))

# ── Color helpers ─────────────────────────────────────────────────────────────

def hsv_to_rgb(h, s, v):
    """Convert HSV (each 0.0–1.0) to an (r, g, b) tuple (each 0–255)."""
    if s == 0.0:
        c = int(v * 255)
        return (c, c, c)
    i = int(h * 6.0)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i %= 6
    if   i == 0: r, g, b = v, t, p
    elif i == 1: r, g, b = q, v, p
    elif i == 2: r, g, b = p, v, t
    elif i == 3: r, g, b = p, q, v
    elif i == 4: r, g, b = t, p, v
    else:        r, g, b = v, p, q
    return (int(r * 255), int(g * 255), int(b * 255))

# ── Test 1: vertical strip, left → right ──────────────────────────────────────

def test_vertical_sweep():
    """Light one full column at a time, scanning from x=0 to x=WIDTH-1."""
    color = (0, 200, 80)
    for x in range(WIDTH):
        clear()
        for y in range(HEIGHT):
            set_pixel(x, y, color)
        pixels.show()
        time.sleep(SWEEP_DELAY_S)
    time.sleep(SWEEP_HOLD_S)

# ── Test 2: horizontal strip, top → bottom ────────────────────────────────────

def test_horizontal_sweep():
    """Light one full row at a time, scanning from y=0 to y=HEIGHT-1."""
    color = (0, 80, 200)
    for y in range(HEIGHT):
        clear()
        for x in range(WIDTH):
            set_pixel(x, y, color)
        pixels.show()
        time.sleep(SWEEP_DELAY_S)
    time.sleep(SWEEP_HOLD_S)

# ── Test 3: plasma animation ──────────────────────────────────────────────────

def test_plasma():
    """
    Animate a sine-wave plasma for PLASMA_DURATION_S seconds.

    Three overlapping sine waves produce the plasma texture; the
    resulting value is mapped onto the blue-green portion of the HSV
    colour wheel.
    """
    t_start = time.monotonic()
    while time.monotonic() - t_start < PLASMA_DURATION_S:
        t = time.monotonic() * PLASMA_SPEED
        for y in range(HEIGHT):
            for x in range(WIDTH):
                # Three sine waves along different axes + time offset
                wave = (
                    math.sin(x * 0.50 + t) +
                    math.sin(y * 0.35 + t * 0.80) +
                    math.sin((x * 0.30 + y * 0.40) + t * 1.20)
                ) / 3.0   # normalise to –1 … +1

                v = (wave + 1.0) / 2.0   # shift to 0.0 … 1.0
                hue = PLASMA_HUE_MIN + v * (PLASMA_HUE_MAX - PLASMA_HUE_MIN)
                set_pixel(x, y, hsv_to_rgb(hue, 1.0, 1.0))
        pixels.show()

# ── Main loop ─────────────────────────────────────────────────────────────────

clear()
pixels.show()
time.sleep(0.3)

while True:
    test_vertical_sweep()
    test_horizontal_sweep()
    test_plasma()
