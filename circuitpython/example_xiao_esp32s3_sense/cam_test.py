"""
Port of ../example/cam_test.py for the Seeed Studio XIAO ESP32S3 Sense.

Untested — see README "Board variants" section for the pin differences
that make this board need its own copies instead of running unchanged.
"""

import board, busio, espcamera

i2c = busio.I2C(board.CAM_SCL, board.CAM_SDA)  # board.I2C() is the Grove header, not the camera

cam = espcamera.Camera(
    data_pins=board.CAM_DATA,
    external_clock_pin=board.CAM_XCLK,
    pixel_clock_pin=board.CAM_PCLK,
    vsync_pin=board.CAM_VSYNC,
    href_pin=board.CAM_HREF,
    i2c=i2c,
    external_clock_frequency=20_000_000,
    pixel_format=espcamera.PixelFormat.RGB565,
    frame_size=espcamera.FrameSize.QQVGA,
)
print("camera OK:", cam.width, "x", cam.height)
