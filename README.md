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

| Folder                                          | Environment                 | What it does                                                                      |
| ------------------------------------------------ | ---------------------------- | --------------------------------------------------------------------------------- |
| `circuitpython/example/`                        | CircuitPython on the board  | Camera → SD card, matrix test patterns, live cam → matrix, foreground + power cap |
| `circuitpython/example_xiao_esp32s3_sense/`     | CircuitPython on the board  | Same, ported for the XIAO ESP32S3 Sense (untested, see board table below)         |
| `pythonOpenCV/`                                 | Desktop Python + OpenCV     | Same examples running on a PC webcam with an LED matrix simulator (glow effect)   |

### Board variants (CircuitPython)

| Board                                                                             | CircuitPython board id                                                                | Compatibility                                            |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| ESP32-S3-CAM ([amazon diymore](https://www.amazon.de/gp/product/B0F4D8ZY6L/))     | [`espressif_esp32s3_eye`](https://circuitpython.org/board/espressif_esp32s3_eye/)       | Drop-in — real-life tested, see info box below            |
| [Freenove ESP32-WROVER CAM](https://store.freenove.com/products/fnk0060) Dev Board | [`esp32-wrover-dev-cam`](https://circuitpython.org/board/esp32-wrover-dev-cam/)         | Drop-in — untested on real hardware                        |
| [Seeed Studio XIAO ESP32S3 Sense](https://www.seeedstudio.com/XIAO-ESP32S3-Sense-p-5639.html) | [`seeed_xiao_esp32s3_sense`](https://circuitpython.org/board/seeed_xiao_esp32s3_sense/) | No Drop-In — needs the pin changes below, see `circuitpython/example_xiao_esp32s3_sense/` |

The ESP32-S3-CAM and Freenove boards expose the camera through the same generic
`board.CAMERA_*` names and `board.I2C()`, so the streaming examples (`cam_test.py`,
`cam_to_web*.py`, `cam_to_matrix*.py`) run unchanged on either. The recapture
button in `cam_to_matrix_fg*.py` is addressed via `microcontroller.pin.GPIO0`
rather than `board.BOOT`/`board.BUTTON`, since the two boards name that pin
differently.

`camera_to_sd.py` is written for the ESP32-S3-CAM's onboard microSD pins and does
not carry over as-is to the Freenove board. If your Freenove board revision has an
SD slot, check its silkscreen — some revisions wire it to GPIO14, which this
project uses for the LED matrix data line.

> [!info]
> the only real-live tested combination is `espressif_esp32s3_eye` circuitpython firmware flashed on an [amazon `diymore For ESP32 CAM` board](https://www.amazon.de/gp/product/B0F4D8ZY6L/)

#### XIAO ESP32S3 Sense — why it's not a drop-in

This board doesn't follow the generic `board.CAMERA_*` naming, and its GPIO14 is
already used by the camera, so it needs different code rather than just a
firmware swap:

- No `board.CAMERA_*` names at all — pins are named `board.CAM_DATA`,
  `board.CAM_XCLK`, `board.CAM_PCLK`, `board.CAM_HREF`, `board.CAM_VSYNC`
  instead.
- `board.I2C()` is the Grove header (GPIO5/GPIO6), not the camera's control
  bus — the camera needs `busio.I2C(board.CAM_SCL, board.CAM_SDA)` instead.
- GPIO14 is the camera's `CAM_D4` data line on this board, so the LED matrix
  needs a different free pin (GPIO1 / header pin `D0` works).
- No `board.BOOT` / `board.BUTTON` either — same `microcontroller.pin.GPIO0`
  approach as the other boards should work, but is unconfirmed.
- The onboard microSD is wired via SPI (not SDMMC like the ESP32-S3-CAM), so
  `camera_to_sd.py` would need a full rewrite for this board — not attempted.

`circuitpython/example_xiao_esp32s3_sense/` has `cam_test.py`,
`ledmatrix_test.py`, `cam_to_matrix.py`, and `cam_to_matrix_fg.py` already
adapted with these changes. They're untested on real hardware — sensor
orientation (`vflip`/`hmirror`) in particular may need adjusting.

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
