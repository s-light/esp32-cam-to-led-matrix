# cam_to_matrix — Notes & Calculations

Live camera feed mapped onto a 16×32 WS2812 matrix.

## Performance budget

Target: ≥ 5 fps → 200 ms per frame budget.

| Step | Time estimate | Notes |
|------|--------------|-------|
| NeoPixel data out | ~15 ms | 512 px × 24 bit × 1.25 µs, native C |
| Camera capture (B96X96 RGB565) | ~20–40 ms | no JPEG decode needed |
| Python downsample loop (512 px) | ~20–40 ms | pre-computed indices, bit-ops only |
| **Total** | **~55–95 ms** | **→ ~10–18 fps expected** |

5 fps (200 ms budget) is comfortable. 10+ fps is realistic.

### Why RGB565 and not JPEG?

JPEG is smaller on the wire but CircuitPython has no built-in JPEG decoder.
RGB565 gives direct pixel access: 2 bytes per pixel, no decode step.

### Why the smallest frame size?

Less data from the sensor → faster DMA transfer → faster `cam.take()`.
B96X96 (96×96) is the smallest the OV2640 supports.
QQVGA (160×120) is the next step up if B96X96 is unavailable in your
firmware build.

### Why pre-compute the sample map?

The hot loop runs every frame. Moving all index arithmetic (multiply,
divide, `xy_to_index`) into a one-time startup pass means the per-frame
work is reduced to:

```
for led, byte in _SAMPLE_MAP:   # 512 iterations
    hi = frame[byte]
    lo = frame[byte + 1]
    pixels[led] = (hi & 0xF8, ..., ...)
```

No multiplication, no function calls — just list iteration and bit ops.

## Aspect ratio & crop

The camera sensor is landscape; the matrix is portrait.

| | Width | Height | Ratio |
|-|-------|--------|-------|
| Camera (B96X96) | 96 | 96 | 1 : 1 |
| Matrix | 16 | 32 | 1 : 2 |

Naively mapping the full 96×96 frame onto 16×32 would compress the
horizontal axis by 2× relative to vertical — everything appears squished.

**Solution: centred vertical crop.**

Take a slice from the camera frame that already has a 1:2 ratio, then
downsample that slice uniformly.

```
crop_width  = FRAME_HEIGHT // 2        # 96 // 2 = 48
crop_left   = (FRAME_WIDTH - 48) // 2  # (96 - 48) // 2 = 24
```

This gives a 48×96 crop, centred horizontally.

```
step_x = crop_width  // WIDTH   # 48 // 16 = 3  (every 3rd column)
step_y = FRAME_HEIGHT // HEIGHT  # 96 // 32 = 3  (every 3rd row)
```

Pixel at matrix position (x, y) comes from frame pixel
`(crop_left + x * step_x,  y * step_y)`.

### Trade-off

The crop narrows the horizontal field of view (you see ~50 % of the
frame width). If you prefer to see the full width at the cost of
distortion, set `_crop_w = FRAME_WIDTH` and `_crop_left = 0`.

## RGB565 decoding

Each pixel in the frame buffer is 2 bytes, big-endian:

```
byte 0:  R R R R R G G G
byte 1:  G G G B B B B B
```

Extraction:

```python
r = hi & 0xF8                              # bits 7-3 → R (lower 3 bits zeroed)
g = ((hi & 0x07) << 5) | ((lo & 0xE0) >> 3)  # 6-bit G
b = (lo & 0x1F) << 3                       # bits 4-0 → B (lower 3 bits zeroed)
```

The missing low bits (R[2:0], B[2:0]) are left as zero — imperceptible
on a low-resolution LED matrix.

## Snake wiring

Pixel 0 is at the **top-right** corner.

```
col  15 14 13 … 1  0
row 0:  [ 0  1  2 … 14 15]   right → left
row 1:  [16 17 18 … 30 31]   left  → right
row 2:  [32 33 34 … 46 47]   right → left
…
```

Index formula:

```python
if y % 2 == 0:                        # even row
    index = y * WIDTH + (WIDTH - 1 - x)
else:                                  # odd row
    index = y * WIDTH + x
```

## Tuning knobs

| Constant | Default | Effect |
|----------|---------|--------|
| `FRAME_SIZE` | `B96X96` | smaller = faster; try `QQVGA` if B96X96 unavailable |
| `BRIGHTNESS` | `0.20` | lower = less power draw, less heat |
| `framebuffer_count` | `2` | `1` saves ~18 kB RAM if needed |
| `_crop_w` | `FRAME_HEIGHT // 2` | increase towards `FRAME_WIDTH` for wider FOV (adds distortion) |
