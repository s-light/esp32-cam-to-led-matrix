# JPEG streaming on ESP32-S3 CAM — investigation notes

Board: diymore ESP32 S3 CAM (ESP32-S3-N16R8, OV2640)  
Firmware: `espressif_esp32s3_eye` CircuitPython (as of 2026-06)

## Result

**JPEG pixel format does not work on this firmware build.**  
`cam.take()` returns `None` and `cam.frame_available` stays `False` regardless of
configuration.  The `espressif_esp32s3_eye` CircuitPython build appears to omit the
ESP32-S3 camera JPEG pipeline, likely to save flash/RAM.

## What was tried

| Parameter | Values tried | Outcome |
|-----------|-------------|---------|
| `pixel_format` | `PixelFormat.JPEG` | always None |
| `frame_size` | QQVGA (160×120), QVGA (320×240), CIF (400×296), VGA (640×480) | None for all |
| `framebuffer_count` | 1 | None |
| `quality` (`cam.quality`) | 10 | None |
| `colorbar` | True / False | no effect |
| Initial init (no reconfigure) | QQVGA + JPEG | None |
| `cam.frame_available` | checked before/after reconfigure and each take() | always False |

### API discoveries along the way

- `cam.frame_size = fs` → `AttributeError: cannot set attribute` — frame_size is read-only after init.  Use `cam.reconfigure(...)` instead.
- `cam.reconfigure(..., jpeg_quality=N)` → `TypeError: unexpected keyword argument` — `jpeg_quality` is not a valid `reconfigure` kwarg.
- `cam.jpeg_quality = N` → `AttributeError: cannot set attribute` — also read-only or not exposed.
- `cam.quality = N` — this one is writable (no error), but had no effect on the None returns.
- `cam.frame_available` — bool property, readable, always False in JPEG mode on this firmware.
- `cam.colorbar = True` — writable, enables OV2640 built-in test pattern; may interfere with JPEG; left off for probing.

## Current workaround

`cam_to_web.py` streams RGB565 frames wrapped in a minimal BMP header
(BI_BITFIELDS, 16 bpp).  Achieves ~2–3 fps over WiFi at 160×120.

Bottleneck: per-pixel Python loop to byte-swap and pack each pixel into the row
buffer (19 200 iterations per frame).

## Paths forward

### 1. Custom CircuitPython firmware build

The most promising option.  The `espressif_esp32s3_eye` board definition can be
cloned and modified to enable JPEG in the camera pipeline.

Key files in the CircuitPython source tree:
- `ports/espressif/boards/espressif_esp32s3_eye/` — board definition
- `ports/espressif/common-hal/espcamera/Camera.c` — camera C implementation
- Check `sdkconfig` / `menuconfig` for `CONFIG_CAMERA_JPEG_*` options

The ESP-IDF camera driver (`esp32-camera` component) supports JPEG natively on the
ESP32-S3; it just needs to be enabled and the CircuitPython binding wired up.

Reference: https://github.com/espressif/esp32-camera

### 2. Use ESP-IDF / Arduino directly

Skip CircuitPython entirely for the streaming use-case and run the Espressif
`esp32-camera` example firmware (CameraWebServer Arduino sketch).  That gives
MJPEG out of the box and is well tested on OV2640.  The LED matrix could still
run on a separate microcontroller.

### 3. Optimise the RGB565 BMP path

Even without JPEG, throughput can improve:

- **`ulab` / `numpy`-style bulk copy** — if a future firmware exposes the frame
  buffer as a flat bytearray, a single `memoryview` assignment could replace the
  Python loop entirely.
- **Send raw RGB565 with a custom viewer** — skip BMP framing; stream raw bytes
  and decode on the PC side with a small Python/OpenCV receiver.
- **Reduce resolution further** — if a smaller FrameSize becomes available (e.g.
  96×96) the loop shrinks proportionally.
- **Double-buffer on the camera side** — `framebuffer_count=2` lets the sensor
  capture the next frame while the current one is being sent.

### 4. Check newer CircuitPython firmware releases

The `espressif_esp32s3_eye` firmware is actively maintained.  A future release may
enable JPEG.  Worth re-testing after each new stable release.

Download: https://circuitpython.org/board/espressif_esp32s3_eye/
