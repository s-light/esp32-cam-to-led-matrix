# SPDX-FileCopyrightText: 2026 stefan krüger
# SPDX-License-Identifier: MIT

import time
import math
import board
import analogio
import neopixel
from adafruit_fancyled.adafruit_fancyled import CHSV, gamma_adjust

# ── hardware ───────────────────────────────────────────────────────────────────
MATRIX_HEIGHT = 32
MATRIX_WIDTH = 16
PIXEL_COUNT = MATRIX_HEIGHT * MATRIX_WIDTH
pixels = neopixel.NeoPixel(board.IO47, PIXEL_COUNT, brightness=1.0, auto_write=False)


# ── strip layout ───────────────────────────────────────────────────────────────
def pixel_xy(i):
    """Map pixel to matrix layout.

    TODO: check layout and implement mapping.
    """
    return i


# ── main ───────────────────────────────────────────────────────────────────────
print("esp32-cam-to-led-matrix - ready")

while True:
    TODO: implement
    return True
