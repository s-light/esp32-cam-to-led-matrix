---
name: hw-findings
description: Hardware findings for the diymore ESP32 S3 CAM board running espressif_esp32s3_eye CircuitPython firmware
metadata:
  type: project
---

Board: diymore ESP32 S3 CAM (ESP32-S3-N16R8, OV2640), running `espressif_esp32s3_eye` CircuitPython firmware.

**Why:** These quirks are not in any datasheet — discovered through live debugging.

**How to apply:** Refer to these before touching camera init, pin assignments, or frame decoding.

## Pin naming
- `board.IO14` does NOT exist in this firmware — use `microcontroller.pin.GPIO14` for the WS2812 matrix data line (the only free GPIO on the left header).
- `board.BACKLIGHT` = GPIO48 — claimed by the firmware (display backlight), cannot be reused.
- `board.SCL` = GPIO5, `board.SDA` = GPIO4 — these ARE the camera SCCB lines.
- Only one raw IO pin is exposed by name: `board.IO3`.

## I2C / camera SCCB
- `board.I2C()` works for camera SCCB **once external pull-up resistors are in place**.
- The board has NO external pull-ups on GPIO4/GPIO5 by default — the 3.3 V reading on a multimeter comes from ESP32-S3 internal pull-ups, which CircuitPython's `busio.I2C` disables during its check.
- Fix: 4.7 kΩ resistors from GPIO4 → 3.3 V and GPIO5 → 3.3 V.
- `bitbangio.I2C` bypasses the pull-up check but `espcamera` rejects it (type mismatch).
- The `digitalio` pull-up + deinit trick does NOT work (pull-up state is reset on deinit).

## Camera frame format
- `cam.take()` accepts NO arguments in this firmware build (`timeout=` raises TypeError).
- `espcamera.FrameSize.B96X96` does NOT exist — use `QQVGA` (160×120) instead.
- The frame returned by `cam.take()` is a **`displayio.Bitmap`** (one uint16 element per pixel). Use pixel index = `y * width + x`. Linear indexing `frame[i]` works; `len()` does NOT; `tobytes()` does NOT exist.
- **Byte order is DMA-swapped**: the ESP32-S3 camera DMA places the RRRRRGGG byte at the *low* position of the uint16, and GGGBBBBB at the *high* position — opposite to standard big-endian RGB565. Correct decode: `hi = px & 0xFF` (RRRRRGGG), `lo = (px >> 8) & 0xFF` (GGGBBBBB).
