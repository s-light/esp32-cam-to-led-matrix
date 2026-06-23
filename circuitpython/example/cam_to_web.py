"""
Camera → MJPEG web stream.

Connects to WiFi, starts a tiny HTTP server on port 80, and serves a
continuous MJPEG stream that any browser or VLC can open.

Access via:
  http://<ip-address>/          (IP printed on the serial console)
  http://esp32cam.local/        (if mDNS works on your network)

Expected throughput: 1–3 fps at QVGA (320×240).
Bottlenecks are WiFi round-trip latency and CircuitPython's Python-speed
socket loop — not the camera itself.

WiFi credentials go in CIRCUITPY:/settings.toml — see settings.toml.example.
"""

import os
import time
import board
import busio
import wifi
import socketpool
import espcamera

try:
    import mdns
    MDNS_AVAILABLE = True
except ImportError:
    MDNS_AVAILABLE = False

# ── Configuration ─────────────────────────────────────────────────────────────

HOSTNAME     = "esp32cam"     # mDNS name → http://esp32cam.local/
PORT         = 80
FRAME_SIZE   = espcamera.FrameSize.QVGA   # 320×240 — good balance of size/speed
JPEG_QUALITY = 10             # 0 = best, 63 = worst
XCLK_FREQ    = 20_000_000

# ── Camera setup ──────────────────────────────────────────────────────────────

print("Initialising camera ...")
i2c = busio.I2C(scl=board.IO5, sda=board.IO4)

cam = espcamera.Camera(
    data_pins=board.CAMERA_DATA,
    external_clock_pin=board.CAMERA_XCLK,
    pixel_clock_pin=board.CAMERA_PCLK,
    vsync_pin=board.CAMERA_VSYNC,
    href_pin=board.CAMERA_HREF,
    i2c=i2c,
    external_clock_frequency=XCLK_FREQ,
    pixel_format=espcamera.PixelFormat.JPEG,
    frame_size=FRAME_SIZE,
    jpeg_quality=JPEG_QUALITY,
    framebuffer_count=2,
)

# Discard warm-up frames so auto-exposure settles before streaming.
for _ in range(8):
    cam.take(timeout=1.0)
print(f"Camera ready: {cam.width}x{cam.height} JPEG")

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

BOUNDARY = b"frame"

# MJPEG uses multipart HTTP: the browser keeps the connection open and each
# JPEG is delivered as a new multipart part.
STREAM_HEADER = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: multipart/x-mixed-replace;boundary=frame\r\n"
    b"Cache-Control: no-cache\r\n"
    b"Connection: close\r\n"
    b"\r\n"
)

def send_all(conn, data):
    """Send all bytes, looping until done (socket.send may be partial)."""
    mv    = memoryview(data)
    total = 0
    while total < len(mv):
        sent   = conn.send(mv[total:])
        total += sent

def read_request(conn):
    """Read and discard the incoming HTTP request headers."""
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = conn.recv(128)
        if not chunk:
            break
        buf += chunk

def serve_stream(conn):
    """Send MJPEG frames until the client disconnects or an error occurs."""
    send_all(conn, STREAM_HEADER)

    frame_count = 0
    t_start     = time.monotonic()

    while True:
        frame = cam.take(timeout=1.0)
        if frame is None:
            continue

        part_header = (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
            b"\r\n"
        )
        try:
            send_all(conn, part_header)
            send_all(conn, bytes(frame))   # frame is a memoryview; copy to bytes
            send_all(conn, b"\r\n")
        except OSError:
            # Client disconnected.
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

print(f"\nStreaming at  http://{ip}/")
print("Open in a browser or:  vlc http://{ip}/")
print("Press Ctrl-C to stop.\n")

while True:
    try:
        conn, addr = server.accept()
        print(f"Client connected: {addr[0]}")
        read_request(conn)
        serve_stream(conn)
        conn.close()
        print("Client disconnected.")
    except Exception as e:
        print(f"Error: {e}")
        try:
            conn.close()
        except Exception:
            pass
