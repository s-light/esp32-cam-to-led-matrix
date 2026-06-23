"""
Camera → MJPEG web stream (JPEG experiment).

The espressif_esp32s3_eye firmware sometimes refuses to return frames
when PixelFormat.JPEG is used (cam.take() returns None).  This script
tries several configurations to find one that works, then streams
multipart/x-mixed-replace with image/jpeg parts — no per-pixel
conversion, so throughput should be much higher than the BMP version.

If JPEG turns out to be completely broken on this firmware, the script
raises a RuntimeError with a clear message (no silent fallback).

Endpoints:
  http://<ip>/          — MJPEG reconfigurestream (open in browser or VLC)
  http://<ip>/frame     — single JPEG frame (save with curl)

WiFi credentials go in CIRCUITPY:/settings.toml — see settings.toml.example.
"""

import os
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

HOSTNAME  = "esp32cam"
PORT      = 80
XCLK_FREQ = 20_000_000

# ── Camera setup — try JPEG with several frame sizes ─────────────────────────
#
# JPEG mode sometimes only works with certain frame sizes.  We try a short list
# in order from smallest to largest and use the first one that yields a frame.

_JPEG_CANDIDATES = [
    espcamera.FrameSize.QQVGA,   # 160×120
    espcamera.FrameSize.QVGA,    # 320×240
    espcamera.FrameSize.CIF,     # 400×296
    espcamera.FrameSize.VGA,     # 640×480
]

print("Initialising camera (JPEG) ...")
i2c = board.I2C()

cam = espcamera.Camera(
    data_pins=board.CAMERA_DATA,
    external_clock_pin=board.CAMERA_XCLK,
    pixel_clock_pin=board.CAMERA_PCLK,
    vsync_pin=board.CAMERA_VSYNC,
    href_pin=board.CAMERA_HREF,
    i2c=i2c,
    external_clock_frequency=XCLK_FREQ,
    pixel_format=espcamera.PixelFormat.JPEG,
    frame_size=espcamera.FrameSize.QQVGA,
    framebuffer_count=1,   # JPEG mode often needs 1 buffer, not 2
)
cam.vflip   = True
cam.hmirror = True
# colorbar intentionally OFF — it may interfere with JPEG encoding

# Try taking a frame with the initial config before any reconfigure.
print("Probing JPEG output ...")
print(f"  frame_available at init: {cam.frame_available}")
frame = None
for attempt in range(16):
    f = cam.take()
    if f is not None:
        frame = f
        print(f"  got frame at init on attempt {attempt}")
        break
    print(f"  init attempt {attempt}: None  frame_available={cam.frame_available}")

# If that failed, try reconfigure through the candidate sizes.
if frame is None:
    for fs in _JPEG_CANDIDATES:
        print(f"  reconfigure frame_size={fs} ...")
        cam.reconfigure(
            pixel_format=espcamera.PixelFormat.JPEG,
            frame_size=fs,
            framebuffer_count=1,
        )
        for attempt in range(16):
            f = cam.take()
            if f is not None:
                frame = f
                print(f"  got frame on attempt {attempt}  frame_available={cam.frame_available}")
                break
            print(f"  attempt {attempt}: None  frame_available={cam.frame_available}")
        if frame is not None:
            break

if frame is None:
    raise RuntimeError(
        "cam.take() returned None for all JPEG configurations.\n"
        "JPEG pixel format is not supported by this firmware build."
    )

print(f"Frame type : {type(frame)}")
print(f"Frame len  : {len(frame)} bytes")
print(f"Camera ready: {cam.width}x{cam.height} JPEG  quality={_QUALITY}")

# ── WiFi ──────────────────────────────────────────────────────────────────────

ssid     = os.getenv("CIRCUITPY_WIFI_SSID")
password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

if not ssid:
    raise RuntimeError("CIRCUITPY_WIFI_SSID not set in settings.toml")

print(f"Connecting to {ssid!r} ...")
wifi.radio.connect(ssid, password)
ip = str(wifi.radio.ipv4_address)
print(f"Connected — IP: {ip}")

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

def jpeg_len(frame):
    """Find the actual JPEG length by locating the EOI marker (FF D9)."""
    # The memoryview may be sized to the full buffer; scan backwards for EOI.
    for i in range(len(frame) - 1, 0, -1):
        if frame[i - 1] == 0xFF and frame[i] == 0xD9:
            return i + 1
    return len(frame)

def serve_single(conn):
    frame = cam.take()
    if frame is None:
        conn.send(b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\n")
        return
    n = jpeg_len(frame)
    send_all(conn,
        b"HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\n"
        b"Content-Length: " + str(n).encode() + b"\r\n"
        b"Connection: close\r\n\r\n"
    )
    send_all(conn, frame[:n])

def serve_stream(conn):
    send_all(conn, STREAM_HEADER)
    frame_count = 0
    t_start = time.monotonic()
    while True:
        frame = cam.take()
        if frame is None:
            print("  frame is None")
            continue
        try:
            n = jpeg_len(frame)
            part = (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(n).encode() + b"\r\n"
                b"\r\n"
            )
            send_all(conn, part)
            send_all(conn, frame[:n])
            send_all(conn, b"\r\n")
        except OSError:
            break
        frame_count += 1
        elapsed = time.monotonic() - t_start
        if elapsed >= 5.0:
            print(f"  {frame_count / elapsed:.1f} fps  |  last JPEG {n} B")
            frame_count = 0
            t_start = time.monotonic()

# ── Server loop ───────────────────────────────────────────────────────────────

pool   = socketpool.SocketPool(wifi.radio)
server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
server.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)
server.bind(("", PORT))
server.listen(1)

print(f"\nLive stream:   http://{ip}/")
print(f"Single frame:  http://{ip}/frame  (save as JPEG)")
print(f"VLC:           vlc http://{ip}/")
print("Press Ctrl-C to stop.\n")

while True:
    try:
        conn, addr = server.accept()
        print(f"Client connected: {addr[0]}")
        path = read_request(conn)
        if path == "/frame":
            serve_single(conn)
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
