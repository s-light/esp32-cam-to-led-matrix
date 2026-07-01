"""
Webcam → .rawvid recorder — desktop counterpart to
circuitpython/example/camera_record_video.py.

Captures a live webcam feed, resizes it to the same 160x120 QQVGA frame the
board examples use, encodes it to RGB565 in the board's DMA byte order, and
writes it to a .rawvid file — so a webcam recording and a board recording
are interchangeable inputs to video_source.py. Handy for drafting a test
clip or a demo when nobody has the board in front of them; real board
footage is noisier and dimmer than a webcam though, so prefer an actual
board recording once one exists (see
circuitpython/example/camera_record_video.md).

Usage
-----
    python record_to_rawvid.py                          # webcam 0, auto-named file
    python record_to_rawvid.py --source 1                # webcam index 1
    python record_to_rawvid.py out.rawvid                # explicit filename
    python record_to_rawvid.py --seconds 20               # auto-stop after 20s

With no filename given, the recording is auto-named
`rec_<start-timestamp>_<duration>s.rawvid` — the timestamp is stamped when
recording starts, the duration is filled in once it stops (it isn't known
up front), so the file is written under a temporary name and renamed at the
end.

Controls
--------
  Q  stop recording early
"""

import argparse
import os
import struct
import time
from datetime import datetime

import cv2
import numpy as np

FRAME_WIDTH = 160
FRAME_HEIGHT = 120
WARMUP_FRAMES = 8

_MAGIC = b"RVID"
_HEADER_FMT = "<4sHHBBI"  # magic, width, height, pixel_format, reserved, frame_count
_PIXEL_FORMAT_RGB565 = 0


def encode_rgb565(frame_bgr):
    """Convert a BGR uint8 frame to raw RGB565 bytes in the board's DMA byte order.

    Inverse of `decode_rgb565` in circuitpython/CIRCUITPY_disc/cam_algo.py —
    see that function's docstring for why the bytes are swapped relative to
    standard big-endian RGB565.
    """
    b = frame_bgr[:, :, 0].astype(np.uint16)
    g = frame_bgr[:, :, 1].astype(np.uint16)
    r = frame_bgr[:, :, 2].astype(np.uint16)

    r5 = r >> 3
    g6 = g >> 2
    b5 = b >> 3

    byte0 = ((r5 << 3) | (g6 >> 3)).astype(np.uint8)  # RRRRRGGG
    byte1 = (((g6 & 0x07) << 5) | b5).astype(np.uint8)  # GGGBBBBB

    return np.dstack([byte0, byte1]).tobytes()  # matches the board's on-wire byte order


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "output",
        nargs="?",
        default=None,
        help="path to write the .rawvid recording to "
        "(default: auto-named rec_<timestamp>_<duration>s.rawvid)",
    )
    p.add_argument("--source", default="0", help="webcam index (default: 0)")
    p.add_argument(
        "--seconds", type=float, default=None, help="stop automatically after N seconds"
    )
    return p.parse_args()


def main():
    args = parse_args()
    source = int(args.source) if args.source.isdigit() else args.source

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open source {source!r}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    print("Warming up ...")
    for _ in range(WARMUP_FRAMES):
        cap.read()

    auto_name = args.output is None
    start_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Duration isn't known until recording stops, so auto-named recordings
    # are written under a temporary name and renamed at the end.
    write_path = args.output if not auto_name else f".rec_{start_stamp}.rawvid.tmp"

    print(
        f"Recording to {'an auto-named file' if auto_name else write_path} — press Q to stop early …"
    )

    with open(write_path, "wb") as f:
        f.write(
            struct.pack(
                _HEADER_FMT,
                _MAGIC,
                FRAME_WIDTH,
                FRAME_HEIGHT,
                _PIXEL_FORMAT_RGB565,
                0,
                0,
            )
        )

        frame_count = 0
        t_start = time.time()
        t_report = t_start

        while True:
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                if (w, h) != (FRAME_WIDTH, FRAME_HEIGHT):
                    frame = cv2.resize(
                        frame, (FRAME_WIDTH, FRAME_HEIGHT), interpolation=cv2.INTER_AREA
                    )

                f.write(encode_rgb565(frame))
                frame_count += 1
                cv2.imshow("Recording - press Q to stop", frame)
            else:
                print("capture failed")

            now = time.time()
            if now - t_report >= 2.0:
                print(
                    f"  {frame_count} frames  |  {frame_count / (now - t_start):.1f} fps avg"
                )
                t_report = now

            if args.seconds is not None and now - t_start >= args.seconds:
                print("--seconds elapsed — stopping.")
                break

            # Still poll the window even on a failed read, so Q always works
            # and the loop can't spin forever unattended.
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

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
            )
        )

    duration_s = round(time.time() - t_start)
    if auto_name:
        final_path = f"rec_{start_stamp}_{duration_s}s.rawvid"
        os.rename(write_path, final_path)
    else:
        final_path = write_path

    print(f"Saved {frame_count} frames ({duration_s}s) to {final_path}")
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
