# ESP32-S3-CAM: capture a JPEG and save it to the SD card.
#
# Board variant: espressif_esp32s3_eye
#   → camera pins are identical to this board
#   → flash reported as 8 MB; if your module has 16 MB the extra space is
#     simply not visible but everything else works fine
#
# Wiring (all on-board, no extra wiring needed):
#   Camera  SIOD=GPIO4  SIOC=GPIO5  VSYNC=GPIO6  HREF=GPIO7
#           XCLK=GPIO15 PCLK=GPIO13
#           D2=GPIO11 D3=GPIO9 D4=GPIO8 D5=GPIO10
#           D6=GPIO12 D7=GPIO18 D8=GPIO17 D9=GPIO16
#   SD card CMD=GPIO38  CLK=GPIO39  D0=GPIO40  (1-bit SDIO, no CS needed)

import time
import board
import busio
import espcamera
import sdioio
import storage

# ── SD card ──────────────────────────────────────────────────────────────────
print("Mounting SD card …")
sd = sdioio.SDCard(
    clock=board.IO39,    # SD_CLK
    command=board.IO38,  # SD_CMD
    data=board.IO40,     # SD_DATA  (1-bit SDIO mode)
    frequency=25_000_000,
)
vfs = storage.VfsFat(sd)
storage.mount(vfs, "/sd")
print("SD card mounted at /sd")

# ── Camera ───────────────────────────────────────────────────────────────────
# The ESP32-S3-EYE board definition exposes named CAMERA_* constants that map
# to the same GPIOs as our board.
print("Initialising camera …")
i2c = busio.I2C(scl=board.IO5, sda=board.IO4)  # SIOC / SIOD

cam = espcamera.Camera(
    data_pins=board.CAMERA_DATA,           # tuple: IO11,IO9,IO8,IO10,IO12,IO18,IO17,IO16
    external_clock_pin=board.CAMERA_XCLK,  # IO15
    pixel_clock_pin=board.CAMERA_PCLK,     # IO13
    vsync_pin=board.CAMERA_VSYNC,          # IO6
    href_pin=board.CAMERA_HREF,            # IO7
    i2c=i2c,
    external_clock_frequency=20_000_000,
    pixel_format=espcamera.PixelFormat.JPEG,
    frame_size=espcamera.FrameSize.SVGA,   # 800×600 — good balance of size/speed
    jpeg_quality=10,                        # 0 = best, 63 = worst; 10 is a safe default
    framebuffer_count=2,                    # double-buffer reduces tearing artefacts
)
print(f"Camera ready: {cam.width}×{cam.height}")

# ── Capture loop ─────────────────────────────────────────────────────────────
NUM_PHOTOS = 3

for i in range(NUM_PHOTOS):
    # Allow auto-exposure to settle on first frame
    if i == 0:
        for _ in range(5):
            cam.take(timeout=1.0)

    frame = cam.take(timeout=1.0)
    if frame is None:
        print(f"  [{i}] timeout — skipping")
        continue

    filename = f"/sd/img_{i:04d}.jpg"
    with open(filename, "wb") as f:
        f.write(frame)
    print(f"  [{i}] saved {len(frame)} bytes → {filename}")
    time.sleep(0.5)

print("Done.")
storage.umount("/sd")
