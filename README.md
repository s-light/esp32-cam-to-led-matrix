# esp32-cam-to-led-matrix

Stream a camera image onto a small WS2812 LED matrix using an ESP32-S3-CAM board.
The matrix is 16×32 pixels, wired in a snake pattern starting at the top-right corner.

## Overview

```
┌─────────────────┐        ┌─────────────────┐
│  ESP32-S3-CAM   │        │  WS2812 Matrix  │
│                 │        │    16 × 32 px   │
│  OV2640 ──────────────►  │  snake layout   │
│  GPIO14 ──────────────►  │  top-right      │
└─────────────────┘        └─────────────────┘
```

The main feature is **foreground-only rendering**: a background reference
frame is subtracted each tick so only subjects in front of the camera are
lit — keeping power draw low enough for small USB or lab supplies.

### Examples

| Folder                   | Environment                | What it does                                                                      |
| ------------------------ | -------------------------- | --------------------------------------------------------------------------------- |
| `circuitpython/example/` | CircuitPython on the board | Camera → SD card, matrix test patterns, live cam → matrix, foreground + power cap |
| `pythonOpenCV/`          | Desktop Python + OpenCV    | Same examples running on a PC webcam with an LED matrix simulator (glow effect)   |

### Board variant (CircuitPython)

Two boards are supported:

- **`espressif_esp32s3_eye`** from [circuitpython.org](https://circuitpython.org/board/espressif_esp32s3_eye/) —
  for the ESP32-S3-CAM. All camera GPIOs match the ESP32-S3-CAM pinout exactly.
  See `esp32-s3-cam_pinout.md` / `.svg` for the full pin reference.
- **`esp32-wrover-dev-cam`** from [circuitpython.org](https://circuitpython.org/board/esp32-wrover-dev-cam/) —
  for the Freenove ESP32-WROVER CAM Dev Board.

Both boards expose the camera through the same generic `board.CAMERA_*` names and
`board.I2C()`, so the streaming examples (`cam_test.py`, `cam_to_web*.py`,
`cam_to_matrix*.py`) run unchanged on either board. The recapture button in
`cam_to_matrix_fg*.py` is addressed via `microcontroller.pin.GPIO0` rather than
`board.BOOT`/`board.BUTTON`, since the two boards name that pin differently.

`camera_to_sd.py` is written for the ESP32-S3-CAM's onboard microSD pins and does
not carry over as-is to the Freenove board. If your Freenove board revision has an
SD slot, check its silkscreen — some revisions wire it to GPIO14, which this
project uses for the LED matrix data line.

### Quick start (desktop)

```bash
cd pythonOpenCV
pip install -r requirements.txt
python ledmatrix_test.py      # matrix patterns, no camera needed
python camera_live.py         # plain camera preview
python camera_fg.py         # plain camera preview
python cam_to_matrix.py       # live cam mapped to LED matrix simulator
python cam_to_matrix_fg.py    # foreground-only + power cap (Space to recapture background)
```

## HW

[amazon diymore - ESP32 S3 CAM](https://www.amazon.de/gp/product/B0F4D8ZY6L/)

> ESP32-S3-WROOM CAM
> ESP32-S3-N16R8
> OV2640 Camera
> TF Card Module

## License

<!-- license info -->
<p>
<a rel="license" href="http://creativecommons.org/licenses/by/4.0/">
    <img alt="Creative Commons License" style="border-width:0"
        src="https://i.creativecommons.org/l/by/4.0/88x31.png" />
</a><br />
<span xmlns:dct="http://purl.org/dc/terms/" property="dct:title">
    all files (if not noted otherwise) in PixelDonation repository
</span> by
<a
    xmlns:cc="http://creativecommons.org/ns#"
    href="https://github.com/s-light/magic_lantern"
    property="cc:attributionName"
    rel="cc:attributionURL">
    Stefan Krüger (s-light)
</a>
are licensed under a<br/>
<a rel="license" href="http://creativecommons.org/licenses/by/4.0/">
    Creative Commons Attribution 4.0 International License
</a>.
</p>

all software parts/files are licensed under [MIT](LICENSE).
