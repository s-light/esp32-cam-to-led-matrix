# cam_to_matrix_fg — Notes & Calculations

Extends `cam_to_matrix.py` with foreground-only rendering and a dynamic
power cap.  Everything about camera setup, sample map, crop maths, and
RGB565 decoding is unchanged — see `cam_to_matrix.md` for those details.
This file covers only what is new.

## The power problem

| Scenario | Current draw |
|----------|-------------|
| 512 LEDs, full white, brightness 1.0 | 512 × 60 mA = **30.7 A** |
| 512 LEDs, full white, brightness 0.20 | **6.1 A** |
| 50 lit pixels, brightness 0.20 | **0.6 A** |

Most cheap USB supplies or small lab PSUs are 1–2 A.  Keeping the
majority of pixels black is the only way to stay within budget without
buying a dedicated high-current supply.

## Approach 1 — Background subtraction

### Concept

Capture a reference frame when the scene is empty (no subject in front
of the camera).  For every live frame, compare each pixel against its
reference value.  If the difference is below a threshold the pixel is
background → set it black.  If the difference exceeds the threshold
the pixel belongs to the foreground → show it.

### Background storage

A full 96×96 RGB565 frame is 96 × 96 × 2 = **18 432 bytes**.

Instead of storing the raw frame we store the already-downsampled 16×32
result — the same values we would display anyway:

```
_background = [(r, g, b), …]   # 512 entries × 3 bytes = 1 536 bytes
```

This is 12× smaller and means the comparison runs on the final pixel
values, not on the source frame.

### Averaging for stability

A single captured frame contains sensor noise, especially in low light.
A noisy reference causes pixels to flicker between foreground and
background even when the scene is still.

Averaging `BG_CAPTURE_FRAMES` (default 6) frames before storing:

```python
accum[led][channel] += pixel_value   # for each frame
_background[led] = accum[led] // BG_CAPTURE_FRAMES
```

6 frames ≈ 300–600 ms capture time at 10–20 fps.  The user sees a brief
white flash on the matrix while this happens.

### Diff calculation

Per-pixel Manhattan distance across all three channels:

```python
diff = abs(r - r_bg) + abs(g - g_bg) + abs(b - b_bg)
```

Range: 0 (identical) to 765 (black vs white).

`DIFF_THRESHOLD = 30` means any channel shifting by ~10/255 on average
counts as foreground.  Good starting values:

| Threshold | Behaviour |
|-----------|-----------|
| 15–25 | Very sensitive; picks up subtle shadows and noise |
| 30–50 | Good general use; ignores sensor noise, catches real movement |
| 60–100 | Only strong differences (large object, big colour change) |

### Weakness: lighting changes

A lamp switching on, a cloud passing outside, or the camera
auto-exposure settling will shift all pixels uniformly — suddenly
everything looks like foreground.  The BOOT button lets the user
recapture the background at any time without restarting the script.

## Approach 2 — Dynamic power cap

### Concept

After the foreground mask is applied, count the lit pixels and ask:
*"if all these pixels were full brightness, how much current would
that draw?"*  If it exceeds the budget, reduce `pixels.brightness`
proportionally.

### Calculation

```
budget_px = POWER_BUDGET_MA / CURRENT_PER_LED_MA
           = 1500 mA / 60 mA = 25 pixels
```

At `MAX_BRIGHTNESS = 0.30` and a 1 500 mA budget:

```
max current = lit_px × 60 mA × brightness
            ≤ 1 500 mA

→  brightness ≤ 1500 / (lit_px × 60)
             = budget_px / lit_px × 1.0
```

Scaled to the configured ceiling:

```python
needed = lit_count / budget_px
safe   = MAX_BRIGHTNESS / max(needed, 1.0)
pixels.brightness = min(MAX_BRIGHTNESS, safe)
```

| Lit pixels | brightness (MAX=0.30) | Est. current |
|------------|----------------------|--------------|
| 10 | 0.30 (full) | 180 mA |
| 25 | 0.30 (full) | 450 mA |
| 50 | 0.15 | 450 mA |
| 100 | 0.075 | 450 mA |
| 512 | 0.015 | 460 mA |

The current stays at or below `POWER_BUDGET_MA` regardless of scene
content.  Note `CURRENT_PER_LED_MA = 60` assumes full white; coloured
pixels draw less, so the estimate is conservative (safe).

## Serial output

Every 2 seconds the script prints a status line:

```
12.4 fps  |  38 lit px  |  brightness 0.30  |  ~684 mA
```

This makes it easy to tune `DIFF_THRESHOLD` and `POWER_BUDGET_MA` while
watching the matrix.

## Button wiring

The on-board BOOT button (GPIO0, active-low, internal pull-up) is used
to retrigger background capture.  No external wiring needed.

```
GPIO0 → GND when pressed
Pull-up → 3V3 when released
```

## Tuning guide

| Constant | Default | Effect |
|----------|---------|--------|
| `DIFF_THRESHOLD` | 30 | Lower = more sensitive foreground detection |
| `BG_CAPTURE_FRAMES` | 6 | More = smoother background, slower capture |
| `MAX_BRIGHTNESS` | 0.30 | Absolute brightness ceiling |
| `POWER_BUDGET_MA` | 1500 | Target max current for the matrix |
| `CURRENT_PER_LED_MA` | 60 | Per-LED estimate; 60 mA is worst-case (full white) |

## What is *not* here (possible extensions)

* **Frame differencing** — compare to the *previous* frame instead of a
  fixed background.  Naturally handles lighting changes but stationary
  subjects disappear.  Easy to add: replace `_background` with a copy of
  the previous frame's pixel values.

* **Temporal smoothing** — blend the background slowly toward the live
  frame (`bg = bg * 0.99 + live * 0.01`) so it self-corrects over time
  without a button press.  Costs a multiply per pixel per frame.

* **Per-pixel brightness scaling** — instead of scaling the global
  `pixels.brightness`, reduce individual pixel values so bright foreground
  areas can be prioritised over dim ones within the budget.
