# CircuitPython Camera Example

Captures JPEG photos and saves them to the SD card using the built-in
`espcamera` module — no extra libraries required.

## Board variant to install

**`espressif_esp32s3_eye`**
→ https://circuitpython.org/board/espressif_esp32s3_eye/

All camera GPIOs on the ESP32-S3-CAM are identical to the ESP32-S3-EYE board
definition, so the named `board.CAMERA_*` constants map correctly out of the box.

| What | ESP32-S3-EYE firmware | Our board |
|------|----------------------|-----------|
| Flash | 8 MB | likely 8 or 16 MB |
| PSRAM | 8 MB OPI | 8 MB |
| Camera pins | ✓ match | — |

If your module has 16 MB flash and the EYE firmware doesn't boot, use
`espressif_esp32s3_devkitc_1_n16r8` instead and replace the `board.CAMERA_*`
constants in the script with explicit `board.IOxx` pin objects (see pin table
below).

## Camera pin mapping

| Signal | GPIO | `board.*` (EYE variant) |
|--------|------|------------------------|
| SIOD (SDA) | 4 | `board.IO4` / `board.SDA` |
| SIOC (SCL) | 5 | `board.IO5` / `board.SCL` |
| VSYNC | 6 | `board.CAMERA_VSYNC` |
| HREF | 7 | `board.CAMERA_HREF` |
| D2 | 11 | `board.CAMERA_DATA[0]` |
| D3 | 9 | `board.CAMERA_DATA[1]` |
| D4 | 8 | `board.CAMERA_DATA[2]` |
| D5 | 10 | `board.CAMERA_DATA[3]` |
| D6 | 12 | `board.CAMERA_DATA[4]` |
| D7 | 18 | `board.CAMERA_DATA[5]` |
| D8 | 17 | `board.CAMERA_DATA[6]` |
| D9 | 16 | `board.CAMERA_DATA[7]` |
| PCLK | 13 | `board.CAMERA_PCLK` |
| XCLK | 15 | `board.CAMERA_XCLK` |

## SD card wiring

The on-board SD slot uses **1-bit SDIO** — no chip-select pin is needed.
CircuitPython's `sdioio` module handles this natively.

| Signal | GPIO |
|--------|------|
| CMD | 38 |
| CLK | 39 |
| D0 (DATA) | 40 |

## How to flash

1. Hold **BOOT**, tap **RST**, release **BOOT** to enter download mode.
2. Flash with `esptool` or the CircuitPython web installer.
3. Copy `camera_to_sd.py` to the CIRCUITPY drive as `code.py`.

## What the script does

1. Mounts the SD card at `/sd` via `sdioio`.
2. Opens an I2C bus on GPIO4/5 and initialises the OV2640.
3. Discards 5 warm-up frames so auto-exposure settles.
4. Captures 3 JPEG photos at SVGA (800×600) with quality 10.
5. Writes them as `img_0000.jpg` … `img_0002.jpg` on the SD card.
6. Unmounts the SD card cleanly.

## Tuning

| Parameter | Script default | Notes |
|-----------|---------------|-------|
| `frame_size` | `SVGA` (800×600) | `QVGA` (320×240) is faster; `UXGA` (1600×1200) is max for OV2640 |
| `jpeg_quality` | `10` | 0 = best quality / largest file, 63 = worst |
| `framebuffer_count` | `2` | `1` saves RAM if you run out |
| `NUM_PHOTOS` | `3` | set to any number or loop forever |

## Sources

- [espcamera — CircuitPython docs](https://docs.circuitpython.org/en/stable/shared-bindings/espcamera/index.html)
- [Capturing Camera Images with CircuitPython — Adafruit](https://learn.adafruit.com/capturing-camera-images-with-circuitpython/working-with-espcamera)
- [CircuitPython — ESP32-S3-EYE download](https://circuitpython.org/board/espressif_esp32s3_eye/)
