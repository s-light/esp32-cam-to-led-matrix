"""
LED matrix simulator — desktop stand-in for a physical WS2812 matrix.

Renders each LED as a glowing circle on a black background, mimicking the
look of a real LED panel.  Mirrors the neopixel.NeoPixel interface so the
example scripts need minimal changes compared to their CircuitPython versions.

Snake wiring assumption (same as hardware):
  Pixel 0 at top-right, even rows right→left, odd rows left→right.

Usage
-----
    from led_simulator import LedMatrix

    matrix = LedMatrix(WIDTH, HEIGHT)
    matrix.set_pixel(x, y, (r, g, b))
    matrix.fill((0, 0, 0))
    img = matrix.render()          # numpy BGR image — compose it yourself
    matrix.show()                  # or let the class call imshow directly
"""

import cv2
import numpy as np

# ── Defaults ──────────────────────────────────────────────────────────────────

LED_SIZE     = 14    # LED circle diameter in pixels
LED_SPACING  = 20    # centre-to-centre distance in pixels
LED_PADDING  = 14    # border around the grid in pixels
GLOW_SIGMA   = 9     # Gaussian blur sigma for the bloom effect
GLOW_WEIGHT  = 0.85  # how much the glow layer is blended in (0 = none)


class LedMatrix:
    """Desktop simulator for a WS2812 LED matrix with glow rendering."""

    def __init__(
        self,
        width,
        height,
        led_size    = LED_SIZE,
        spacing     = LED_SPACING,
        padding     = LED_PADDING,
        brightness  = 0.9,
        glow_sigma  = GLOW_SIGMA,
        glow_weight = GLOW_WEIGHT,
        window_title = "LED Matrix",
    ):
        self.width        = width
        self.height       = height
        self.led_size     = led_size
        self.spacing      = spacing
        self.padding      = padding
        self.brightness   = brightness      # mirrors neopixel.NeoPixel.brightness
        self.glow_sigma   = glow_sigma
        self.glow_weight  = glow_weight
        self.window_title = window_title

        self._pixels = [(0, 0, 0)] * (width * height)

        # Pre-compute the rendered image dimensions.
        self.img_w = padding * 2 + (width  - 1) * spacing + led_size
        self.img_h = padding * 2 + (height - 1) * spacing + led_size

    # ── NeoPixel-compatible interface ─────────────────────────────────────────

    def __setitem__(self, index, color):
        self._pixels[index] = color

    def __getitem__(self, index):
        return self._pixels[index]

    def fill(self, color):
        self._pixels = [color] * (self.width * self.height)

    # ── Coordinate mapping ────────────────────────────────────────────────────

    def xy_to_index(self, x, y):
        """Snake layout: pixel 0 at top-right, even rows right→left."""
        if y % 2 == 0:
            return y * self.width + (self.width - 1 - x)
        else:
            return y * self.width + x

    def set_pixel(self, x, y, color):
        self._pixels[self.xy_to_index(x, y)] = color

    # ── Rendering ─────────────────────────────────────────────────────────────

    def render(self):
        """Return a numpy uint8 BGR image of the matrix with glow effect."""
        img = np.zeros((self.img_h, self.img_w, 3), dtype=np.uint8)

        r_led   = self.led_size // 2
        b_scale = self.brightness

        for y in range(self.height):
            for x in range(self.width):
                r, g, b = self._pixels[self.xy_to_index(x, y)]
                cx = self.padding + x * self.spacing
                cy = self.padding + y * self.spacing
                # OpenCV uses BGR channel order.
                bgr = (
                    int(b * b_scale),
                    int(g * b_scale),
                    int(r * b_scale),
                )
                cv2.circle(img, (cx, cy), r_led, bgr, -1, cv2.LINE_AA)

        if self.glow_weight > 0:
            # Bloom: blur the sharp LED image and add it back.
            glow = cv2.GaussianBlur(img, (0, 0), self.glow_sigma)
            img  = cv2.addWeighted(img, 1.0, glow, self.glow_weight, 0)

        return img

    def show(self):
        """Render and display in a named window.  Returns the pressed key."""
        cv2.imshow(self.window_title, self.render())
        return cv2.waitKey(1) & 0xFF


# ── Compositing helpers ───────────────────────────────────────────────────────

def make_label(img, text, color=(180, 180, 180)):
    """Stamp a small label in the top-left corner of a copy of img."""
    out = img.copy()
    cv2.putText(out, text, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
    return out


def side_by_side(*panels, gap=10):
    """Horizontally concatenate panels, scaling each to a common height."""
    target_h = max(p.shape[0] for p in panels)
    resized = []
    for p in panels:
        h, w = p.shape[:2]
        new_w = int(w * target_h / h)
        resized.append(cv2.resize(p, (new_w, target_h), interpolation=cv2.INTER_AREA))
    separator = np.zeros((target_h, gap, 3), dtype=np.uint8)
    combined  = resized[0]
    for r in resized[1:]:
        combined = np.hstack([combined, separator, r])
    return combined
