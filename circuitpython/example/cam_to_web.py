"""
Camera → multipart BMP web stream.

JPEG pixel format does not work in the espressif_esp32s3_eye CircuitPython
firmware, so this example captures RGB565 frames and wraps each one in a
minimal BMP header (BI_BITFIELDS, 16 bpp) before sending.  The raw uint16
camera buffer bytes are already little-endian RGB565, matching the
BI_BITFIELDS layout exactly — no per-pixel conversion needed.

Connects to WiFi, starts a tiny HTTP server on port 80.

Access via:
  http://<ip-address>/          (IP printed on the serial console)
  http://esp32cam.local/        (if mDNS works on your network)

WiFi credentials go in CIRCUITPY:/settings.toml — see settings.toml.example.
"""

import os
import struct
import time
import board
import wifi
import socketpool
import espcamera

try:
    import mdns
    MDNS_AVAILABLE = True
except ImportError:
    MDNS_AVAILABLE = False

# ── Configuration ─────────────────────────────────────────────────────────────

HOSTNAME   = "esp32cam"
PORT       = 80
FRAME_SIZE = espcamera.FrameSize.QQVGA   # 160×120
FRAME_W    = 160
FRAME_H    = 120
XCLK_FREQ  = 20_000_000

# ── Camera setup ──────────────────────────────────────────────────────────────

print("Initialising camera ...")
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

# cam.colorbar = True


for _ in range(8):
    cam.take()

print(f"Camera ready: {cam.width}x{cam.height} RGB565")

# ── BMP header (pre-built, constant for every frame) ─────────────────────────
#
# 16-bit BI_BITFIELDS BMP: no per-pixel conversion needed because the camera's
# uint16 buffer bytes are already little-endian RGB565, matching exactly.
# Positive height → bottom-up BMP row order (camera outputs rows bottom-first).

def _make_bmp_header(w, h):
    img_bytes = w * h * 2
    file_size = 66 + img_bytes          # 14 file hdr + 40 DIB hdr + 12 masks
    return struct.pack(
        "<2sIHHIIiiHHIIiiIIIII",
        b"BM", file_size, 0, 0, 66,
        40, w, h, 1, 16, 3, img_bytes, 0, 0, 0, 0,
        0xF800, 0x07E0, 0x001F,
    )

BMP_HEADER      = _make_bmp_header(FRAME_W, FRAME_H)
BMP_CONTENT_LEN = len(BMP_HEADER) + FRAME_W * FRAME_H * 2

# Row-sized buffer — compute and send one row at a time.
_row_buf = bytearray(FRAME_W * 2)

# ── WiFi ──────────────────────────────────────────────────────────────────────

ssid     = os.getenv("CIRCUITPY_WIFI_SSID")
password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

if not ssid:
    raise RuntimeError("CIRCUITPY_WIFI_SSID not set in settings.toml")

print(f"Connecting to {ssid!r} ...")
wifi.radio.connect(ssid, password)
ip = str(wifi.radio.ipv4_address)
print(f"Connected — IP: {ip}")

# ── mDNS ──────────────────────────────────────────────────────────────────────

if MDNS_AVAILABLE:
    mdns_server = mdns.Server(wifi.radio)
    mdns_server.hostname = HOSTNAME
    mdns_server.advertise_service(service_type="_http", protocol="_tcp", port=PORT)
    print(f"mDNS: http://{HOSTNAME}.local/")

# ── Socket helpers ────────────────────────────────────────────────────────────

STREAM_HEADER = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: multipart/x-mixed-replace;boundary=frame\r\n"
    b"Cache-Control: no-cache\r\n"
    b"Connection: close\r\n"
    b"\r\n"
)

PART_HEADER = (
    b"--frame\r\n"
    b"Content-Type: image/bmp\r\n"
    b"Content-Length: " + str(BMP_CONTENT_LEN).encode() + b"\r\n"
    b"\r\n"
)

def send_all(conn, data):
    if not isinstance(data, (bytes, bytearray)):
        data = bytes(data)
    total = 0
    while total < len(data):
        try:
            sent = conn.send(data[total:])
            if not sent:
                raise OSError("send returned 0")
            total += sent
        except OSError as e:
            if e.args[0] == 11:  # EAGAIN — buffer full, retry
                continue
            raise

def read_request(conn):
    """Read request, return URL path (e.g. '/' or '/frame')."""
    conn.settimeout(2.0)
    buf = bytearray(1024)
    n = 0
    try:
        n = conn.recv_into(buf)
    except OSError:
        pass
    conn.settimeout(5.0)
    try:
        return bytes(buf[:n]).split(b" ")[1].decode()
    except Exception:
        return "/"

def serve_frame(conn):
    """Serve a single BMP frame — save with curl or browser Save-As."""
    frame = cam.take()
    if frame is None:
        conn.send(b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\n")
        return
    send_all(conn,
        b"HTTP/1.1 200 OK\r\nContent-Type: image/bmp\r\n"
        b"Content-Length: " + str(BMP_CONTENT_LEN).encode() + b"\r\n"
        b"Connection: close\r\n\r\n"
    )
    send_all(conn, BMP_HEADER)
    for y in range(FRAME_H):
        base = y * FRAME_W
        for x in range(FRAME_W):
            px = frame[base + x]
            _row_buf[x * 2]     = (px >> 8) & 0xFF
            _row_buf[x * 2 + 1] = px & 0xFF
        send_all(conn, _row_buf)

def serve_stream(conn):
    send_all(conn, STREAM_HEADER)

    frame_count = 0
    t_start     = time.monotonic()

    while True:
        frame = cam.take()
        if frame is None:
            continue

        try:
            send_all(conn, PART_HEADER)
            send_all(conn, BMP_HEADER)
            for y in range(FRAME_H):
                base = y * FRAME_W
                for x in range(FRAME_W):
                    px = frame[base + x]
                    _row_buf[x * 2]     = (px >> 8) & 0xFF
                    _row_buf[x * 2 + 1] = px & 0xFF
                send_all(conn, _row_buf)
            send_all(conn, b"\r\n")
        except OSError:
            break

        frame_count += 1
        elapsed = time.monotonic() - t_start
        if elapsed >= 5.0:
            print(f"  {frame_count / elapsed:.1f} fps")
            frame_count = 0
            t_start     = time.monotonic()

# ── Server loop ───────────────────────────────────────────────────────────────

pool   = socketpool.SocketPool(wifi.radio)
server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
server.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)
server.bind(("", PORT))
server.listen(1)

print(f"\nLive stream:   http://{ip}/")
print(f"Single frame:  http://{ip}/frame  (save as BMP)")
print(f"VLC:           vlc http://{ip}/")
print("Press Ctrl-C to stop.\n")

while True:
    try:
        conn, addr = server.accept()
        print(f"Client connected: {addr[0]}")
        path = read_request(conn)
        if path == "/frame":
            serve_frame(conn)
        else:
            serve_stream(conn)
        conn.close()
        print("Client disconnected.")
    except Exception as e:
        print(f"Error: {e}")
        try:
            conn.close()
        except Exception:
            pass
