"""
Shared foreground-extraction algorithm.

Pure Python — no numpy, no camera or LED-matrix imports — so the exact same
code runs unmodified on the CircuitPython board (main.py, next to this file)
and on desktop Python (pythonOpenCV/cam_to_matrix_fg.py, which adds this
directory to sys.path before importing). Keeping the algorithm in one file
means a change tested on a laptop ports to the board with no translation
step.

Callers supply a `sample_fn(x, y) -> (r, g, b)` closure over whatever frame
representation they have (a CircuitPython espcamera bitmap, a numpy array,
...) — this module only ever deals in (x, y) coordinates and (r, g, b)
tuples, so it doesn't care which.
"""


def xy_to_index(x, y, width):
    """Snake layout: pixel 0 at top-right, even rows right→left."""
    if y % 2 == 0:
        return y * width + (width - 1 - x)
    else:
        return y * width + x


def build_sample_map(frame_width, frame_height, width, height):
    """Precompute the mapping from LEDs to source-frame sample points.

    Crops a centred, frame_height-tall region out of the frame and samples
    it on a width x height grid (nearest-pixel, no interpolation — matches
    what the board can afford in its hot loop).

    Returns a list of (led_index, dest_x, dest_y, src_x, src_y) — dest_x/y
    is the LED's position in the width x height grid (useful for previews),
    src_x/y is the pixel to read from the source frame.
    """
    crop_w = frame_height // 2
    crop_left = (frame_width - crop_w) // 2
    step_x = max(1, crop_w // width)
    step_y = max(1, frame_height // height)

    sample_map = []
    for y in range(height):
        src_y = y * step_y
        for x in range(width):
            src_x = crop_left + x * step_x
            sample_map.append((xy_to_index(x, y, width), x, y, src_x, src_y))
    return sample_map


def decode_rgb565(raw_pixel):
    """Extract (r, g, b) from one RGB565 pixel using the board's DMA byte order.

    The ESP32-S3 camera DMA swaps the two bytes of each pixel relative to
    standard big-endian RGB565 (see memory/hw_findings.md): the low byte
    holds RRRRRGGG and the high byte holds GGGBBBBB.
    """
    hi = raw_pixel & 0xFF
    lo = (raw_pixel >> 8) & 0xFF
    r = hi & 0xF8
    g = ((hi & 0x07) << 5) | ((lo & 0xE0) >> 3)
    b = (lo & 0x1F) << 3
    return r, g, b


def build_contrast_lut(factor, offset):
    """256-entry LUT: linear contrast stretch centred on 128.

    factor = 1.0 → no change. offset shifts the input before stretching.
    """
    lut = []
    for v in range(256):
        adjusted = int(128 + factor * (v + offset - 128))
        lut.append(max(0, min(255, adjusted)))
    return lut


def capture_background(next_sample_fn, sample_map, frames):
    """Average `frames` samples into a background reference.

    `next_sample_fn()` must return a fresh sample_fn(x, y) each call (e.g.
    by grabbing a new camera frame) — this is what lets the average be taken
    over distinct frames rather than the same one repeatedly.

    Returns a list of (r, g, b), indexed by led_index.
    """
    accum = [[0, 0, 0] for _ in range(len(sample_map))]

    for _ in range(frames):
        sample_fn = next_sample_fn()
        for led, _dx, _dy, src_x, src_y in sample_map:
            r, g, b = sample_fn(src_x, src_y)
            a = accum[led]
            a[0] += r
            a[1] += g
            a[2] += b

    return [(a[0] // frames, a[1] // frames, a[2] // frames) for a in accum]


def apply_foreground(
    sample_fn,
    sample_map,
    background,
    diff_threshold,
    contrast_lut=None,
    grayscale=False,
    gray_color=(255, 255, 255),
):
    """Subtract background, apply optional contrast + grayscale.

    Returns (results, lit_count) where results is a list of
    (led_index, r, g, b) — one entry per LED in sample_map, background
    pixels come back as (0, 0, 0).
    """
    gw_r, gw_g, gw_b = gray_color
    results = []
    lit = 0

    for led, _dx, _dy, src_x, src_y in sample_map:
        r, g, b = sample_fn(src_x, src_y)
        br, bg, bb = background[led]
        diff = abs(r - br) + abs(g - bg) + abs(b - bb)

        if diff >= diff_threshold:
            if contrast_lut is not None:
                r = contrast_lut[r]
                g = contrast_lut[g]
                b = contrast_lut[b]

            if grayscale:
                luma = (r * 77 + g * 150 + b * 29) >> 8
                r, g, b = (gw_r * luma) >> 8, (gw_g * luma) >> 8, (gw_b * luma) >> 8

            results.append((led, r, g, b))
            lit += 1
        else:
            results.append((led, 0, 0, 0))

    return results, lit
