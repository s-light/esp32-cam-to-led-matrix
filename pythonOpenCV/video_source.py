"""
Unified video source — treats a webcam index and a recorded .rawvid file the
same way, so example scripts can run against either without branching.

Usage
-----
    from video_source import open_source

    cap = open_source(sys.argv[1] if len(sys.argv) > 1 else 0)
    ret, frame = cap.read()   # frame is a BGR uint8 numpy array, like cv2.VideoCapture
    cap.release()

A .rawvid file is produced by the board-side
circuitpython/example/camera_record_video.py script — see its README for the
on-disk format. Recordings loop automatically when they reach the end, so a
short capture can drive a long testing session.
"""

import struct

import cv2
import numpy as np

_MAGIC = b"RVID"
# magic, width, height, pixel_format, reserved, frame_count, duration_ms
_HEADER_FMT = "<4sHHBBII"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)
_PIXEL_FORMAT_RGB565 = 0


def open_source(source):
    """Return a cv2.VideoCapture-like object for a webcam index or a recording path.

    `source` is a webcam index (int, or a numeric string) or a filesystem
    path to a .rawvid recording.
    """
    if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
        return cv2.VideoCapture(int(source))
    return RecordingSource(source)


class RecordingSource:
    """Plays back a .rawvid recording through the cv2.VideoCapture interface."""

    def __init__(self, path):
        self._file = open(path, "rb")
        header = self._file.read(_HEADER_SIZE)
        magic, width, height, pixel_format, _reserved, frame_count, duration_ms = (
            struct.unpack(_HEADER_FMT, header)
        )
        if magic != _MAGIC:
            raise ValueError(f"{path} is not a .rawvid recording (bad magic)")
        if pixel_format != _PIXEL_FORMAT_RGB565:
            raise ValueError(f"Unsupported pixel format {pixel_format} in {path}")

        self.width = width
        self.height = height
        self.frame_count = frame_count
        self.duration_ms = duration_ms
        self._frame_bytes = width * height * 2
        self._data_start = _HEADER_SIZE

    @property
    def fps(self):
        """Average capture rate, or None if the recording doesn't say (e.g. it
        was interrupted before its header could be finalized — see
        camera_record_video.md)."""
        if self.duration_ms <= 0 or self.frame_count <= 0:
            return None
        return self.frame_count / (self.duration_ms / 1000)

    def get(self, prop_id):
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return self.width
        if prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.height
        return 0

    def set(self, prop_id, value):
        return False  # resolution is fixed by the recording

    def read(self):
        raw = self._file.read(self._frame_bytes)
        if len(raw) < self._frame_bytes:
            # End of recording — loop back to the first frame.
            self._file.seek(self._data_start)
            raw = self._file.read(self._frame_bytes)
            if len(raw) < self._frame_bytes:
                return False, None
        return True, self._decode(raw)

    def _decode(self, raw):
        """Convert raw RGB565 bytes (board byte order) to a BGR uint8 frame.

        The ESP32-S3 camera DMA swaps the two bytes of each pixel relative to
        standard big-endian RGB565: the low byte holds RRRRRGGG and the high
        byte holds GGGBBBBB (see memory/hw_findings.md). This mirrors
        `decode_rgb565` in circuitpython/CIRCUITPY_disc/cam_algo.py.
        """
        px = np.frombuffer(raw, dtype="<u2").reshape(self.height, self.width)
        hi = (px & 0xFF).astype(np.uint8)
        lo = ((px >> 8) & 0xFF).astype(np.uint8)
        r = hi & 0xF8
        g = ((hi & 0x07) << 5) | ((lo & 0xE0) >> 3)
        b = (lo & 0x1F) << 3
        return np.dstack([b, g, r])  # BGR for OpenCV

    def release(self):
        self._file.close()

    def isOpened(self):
        return not self._file.closed
