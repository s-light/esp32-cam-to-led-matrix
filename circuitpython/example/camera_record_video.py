# ESP32-S3-CAM: record raw camera frames to the SD card for offline development.
#
# Captures QQVGA RGB565 frames — the same format and resolution the
# foreground-extraction examples use — straight to a `.rawvid` file, so real
# board camera footage (with its actual sensor noise) can be replayed on a
# laptop via pythonOpenCV/video_source.py. See camera_record_video.md for the
# file format and the SD wiring (shared with camera_to_sd.py).
#
# Press BOOT to start recording, press BOOT again to stop. Recording also
# stops automatically at MAX_RECORD_SECONDS, so a forgotten recording can't
# fill the card.

import os
import struct
import time

import board
import microcontroller
import sdioio
import storage
import espcamera
from digitalio import DigitalInOut, Direction, Pull

# ── Configuration ─────────────────────────────────────────────────────────────

FRAME_SIZE = espcamera.FrameSize.QQVGA
FRAME_WIDTH = 160
FRAME_HEIGHT = 120
XCLK_FREQ = 20_000_000

MAX_RECORD_SECONDS = 60

_MAGIC = b"RVID"
# magic, width, height, pixel_format, reserved, frame_count, duration_ms
_HEADER_FMT = "<4sHHBBII"
_PIXEL_FORMAT_RGB565 = 0

# ── SD card ──────────────────────────────────────────────────────────────────
# 1-bit SDIO — no chip-select pin needed, same wiring as camera_to_sd.py.

print("Mounting SD card …")
sd = sdioio.SDCard(
    clock=board.IO39,
    command=board.IO38,
    data=board.IO40,
    frequency=25_000_000,
)
vfs = storage.VfsFat(sd)
storage.mount(vfs, "/sd")
print("SD card mounted at /sd")

# ── Button setup (GPIO0, active-low) ──────────────────────────────────────────

btn = DigitalInOut(microcontroller.pin.GPIO0)
btn.direction = Direction.INPUT
btn.pull = Pull.UP


def button_pressed():
    return not btn.value


def wait_for_button_edge(pressed):
    while button_pressed() != pressed:
        time.sleep(0.02)
    time.sleep(0.05)  # debounce


# ── Camera setup ──────────────────────────────────────────────────────────────

i2c = board.I2C()

cam = espcamera.Camera(
    data_pins=board.CAMERA_DATA,
    external_clock_pin=board.CAMERA_XCLK,
    pixel_clock_pin=board.CAMERA_PCLK,
    vsync_pin=board.CAMERA_VSYNC,
    href_pin=board.CAMERA_HREF,
    i2c=i2c,
    external_clock_frequency=XCLK_FREQ,
    pixel_format=espcamera.PixelFormat.RGB565,
    frame_size=FRAME_SIZE,
    framebuffer_count=2,
)

print("Warming up camera …")
for _ in range(8):
    cam.take()
print(f"Camera ready: {cam.width}×{cam.height} RGB565")


def _next_filename():
    existing = set(os.listdir("/sd"))
    i = 0
    while f"rec_{i:04d}.rawvid" in existing:
        i += 1
    return f"/sd/rec_{i:04d}.rawvid"


# ── Recording loop ─────────────────────────────────────────────────────────────

print("Press BOOT to start recording …")

while True:
    wait_for_button_edge(pressed=True)

    filename = _next_filename()
    print(f"Recording to {filename} — press BOOT again to stop …")

    with open(filename, "wb") as f:
        # Placeholder header — frame_count and duration_ms are filled in once
        # recording stops (neither is known up front).
        f.write(
            struct.pack(
                _HEADER_FMT,
                _MAGIC,
                FRAME_WIDTH,
                FRAME_HEIGHT,
                _PIXEL_FORMAT_RGB565,
                0,
                0,
                0,
            )
        )

        frame_count = 0
        t_start = time.monotonic()
        t_report = t_start

        while True:
            if button_pressed():
                wait_for_button_edge(pressed=False)
                break
            if time.monotonic() - t_start >= MAX_RECORD_SECONDS:
                print("MAX_RECORD_SECONDS reached — stopping.")
                break

            frame = cam.take()
            if frame is None:
                continue

            f.write(memoryview(frame))
            frame_count += 1

            now = time.monotonic()
            if now - t_report >= 2.0:
                fps = frame_count / (now - t_start)
                print(f"  {frame_count} frames  |  {fps:.1f} fps avg")
                t_report = now

        duration_ms = round((time.monotonic() - t_start) * 1000)

        f.flush()
        f.seek(0)
        f.write(
            struct.pack(
                _HEADER_FMT,
                _MAGIC,
                FRAME_WIDTH,
                FRAME_HEIGHT,
                _PIXEL_FORMAT_RGB565,
                0,
                frame_count,
                duration_ms,
            )
        )

    print(f"Saved {frame_count} frames ({duration_ms / 1000:.1f}s) to {filename}")
    print("Press BOOT to record another clip …")
