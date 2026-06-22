"""
LED matrix test — desktop version using the LED simulator.

Identical test sequence as circuitpython/example/ledmatrix_test.py:
  1. Vertical strip sweeping left → right
  2. Horizontal strip sweeping top → bottom
  3. Plasma animation in blue-green HSV range

Press Q to quit at any time.
"""

import time
import math
import cv2
from led_simulator import LedMatrix

# ── Configuration ─────────────────────────────────────────────────────────────

WIDTH  = 16
HEIGHT = 32

SWEEP_DELAY_S    = 0.05
SWEEP_HOLD_S     = 0.4
PLASMA_DURATION_S = 12.0
PLASMA_SPEED      = 1.4
PLASMA_HUE_MIN    = 0.40   # cyan-green
PLASMA_HUE_MAX    = 0.70   # blue

# ── Matrix setup ──────────────────────────────────────────────────────────────

matrix = LedMatrix(WIDTH, HEIGHT, brightness=0.9, window_title="LED Matrix Test")

# ── Color helper ──────────────────────────────────────────────────────────────

def hsv_to_rgb(h, s, v):
    """h, s, v each 0.0–1.0 → (r, g, b) each 0–255."""
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
    color = (0, 200, 80)
    for x in range(WIDTH):
        matrix.fill((0, 0, 0))
        for y in range(HEIGHT):
            matrix.set_pixel(x, y, color)
        if matrix.show() == ord('q'):
            return False
        time.sleep(SWEEP_DELAY_S)
    time.sleep(SWEEP_HOLD_S)
    return True

# ── Test 2: horizontal strip, top → bottom ────────────────────────────────────

def test_horizontal_sweep():
    color = (0, 80, 200)
    for y in range(HEIGHT):
        matrix.fill((0, 0, 0))
        for x in range(WIDTH):
            matrix.set_pixel(x, y, color)
        if matrix.show() == ord('q'):
            return False
        time.sleep(SWEEP_DELAY_S)
    time.sleep(SWEEP_HOLD_S)
    return True

# ── Test 3: plasma animation ──────────────────────────────────────────────────

def test_plasma():
    t_start = time.time()
    while time.time() - t_start < PLASMA_DURATION_S:
        t = time.time() * PLASMA_SPEED
        for y in range(HEIGHT):
            for x in range(WIDTH):
                wave = (
                    math.sin(x * 0.50 + t) +
                    math.sin(y * 0.35 + t * 0.80) +
                    math.sin((x * 0.30 + y * 0.40) + t * 1.20)
                ) / 3.0
                v   = (wave + 1.0) / 2.0
                hue = PLASMA_HUE_MIN + v * (PLASMA_HUE_MAX - PLASMA_HUE_MIN)
                matrix.set_pixel(x, y, hsv_to_rgb(hue, 1.0, 1.0))
        if matrix.show() == ord('q'):
            return False
    return True

# ── Main loop ─────────────────────────────────────────────────────────────────

matrix.fill((0, 0, 0))
matrix.show()

running = True
while running:
    running = test_vertical_sweep()
    if running:
        running = test_horizontal_sweep()
    if running:
        running = test_plasma()

cv2.destroyAllWindows()
