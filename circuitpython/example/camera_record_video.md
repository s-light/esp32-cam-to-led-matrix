# camera_record_video — Notes & File Format

Records raw camera frames straight to the SD card, so the group can develop
and test the foreground-extraction algorithm on their own laptops using real
board camera footage — including its actual sensor noise — instead of a
laptop webcam. Only one person needs the hardware in front of them; everyone
else works from a recording.

## Board variant & wiring

Same as `camera_to_sd.py` — see `camera_to_sd.md` for the full pin table.
SD card is 1-bit SDIO (CMD=GPIO38, CLK=GPIO39, D0=GPIO40), no chip-select
needed.

## Usage

1. Flash `camera_record_video.py` as `code.py`.
2. Press **BOOT** to start recording.
3. Move the subject around in front of the camera.
4. Press **BOOT** again to stop (or wait for `MAX_RECORD_SECONDS`, default
   60 s, as a safety net so a forgotten recording doesn't fill the card).
5. Power off, pull the SD card, copy the `rec_NNNN.rawvid` file to your
   computer (e.g. into `pythonOpenCV/`).
6. Play it back through any of the desktop scripts:

   ```bash
   cd pythonOpenCV
   python cam_to_matrix_fg.py rec_0000.rawvid
   ```

   See `pythonOpenCV/video_source.py` — it treats a `.rawvid` path exactly
   like a webcam index, so no script-side branching is needed.

Each run creates a new `rec_NNNN.rawvid` file (existing files on the card
are never overwritten); the loop returns to "press BOOT to start" after each
clip so several clips can be captured in one session.

## File format (`.rawvid`)

```
offset  size  field
0       4     magic bytes b"RVID"
4       2     width          (uint16, little-endian — 160 for QQVGA)
6       2     height         (uint16, little-endian — 120 for QQVGA)
8       1     pixel_format   (uint8 — 0 = RGB565)
9       1     reserved
10      4     frame_count    (uint32, little-endian)
14      —     frame data: frame_count × (width × height × 2 bytes)
```

Struct format string: `"<4sHHBBI"` (14-byte header), usable unchanged from
both CircuitPython's `struct` module and desktop Python's.

Each frame is `width × height` RGB565 pixels, written verbatim from the
camera's frame buffer via `memoryview(frame)` — no per-pixel Python loop, so
recording doesn't cost extra frame rate beyond the SD write itself.

**Byte order**: the ESP32-S3 camera DMA swaps the two bytes of each pixel
relative to standard big-endian RGB565 — the low byte holds `RRRRRGGG`, the
high byte holds `GGGBBBBB` (see `memory/hw_findings.md`). Both
`circuitpython/CIRCUITPY_disc/cam_algo.py`'s `decode_rgb565()` and
`pythonOpenCV/video_source.py`'s `RecordingSource._decode()` account for
this — don't reorder the bytes when reading the file elsewhere.

`frame_count` is written as `0` when recording starts and is only filled in
correctly once recording stops cleanly (the script seeks back and rewrites
the header). A recording interrupted by a power loss will have
`frame_count == 0` in its header even though frame data follows — if you
need to recover one, ignore the header and read `(file_size - 14) //
(width * height * 2)` frames instead.

## Tuning

| Constant | Default | Effect |
|----------|---------|--------|
| `MAX_RECORD_SECONDS` | 60 | Safety cap on a single recording |
| `FRAME_SIZE` / `FRAME_WIDTH` / `FRAME_HEIGHT` | QQVGA / 160 / 120 | Must match the foreground examples if recordings are meant to be a drop-in stand-in for the live camera |

## Storage math

At QQVGA (160×120), each frame is 160 × 120 × 2 = 38 400 bytes. At ~8 fps
that's ~300 KB/s — well inside the 25 MHz SDIO bus this script configures,
and a 60-second clip is ~18 MB.
