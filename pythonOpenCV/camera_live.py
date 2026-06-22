"""
Simple camera live-view.

Press Q to quit.
"""

import cv2

# ── Configuration ─────────────────────────────────────────────────────────────

CAMERA_INDEX = 0
FRAME_WIDTH  = 640
FRAME_HEIGHT = 480

# ── Setup ─────────────────────────────────────────────────────────────────────

cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    raise RuntimeError(f"Could not open camera index {CAMERA_INDEX}")

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Camera: requested {FRAME_WIDTH}x{FRAME_HEIGHT}, got {actual_w}x{actual_h}")
print("Press Q to quit.")

# ── Main loop ─────────────────────────────────────────────────────────────────

while True:
    ret, frame = cap.read()
    if not ret:
        print("capture failed")
        break

    cv2.imshow("Camera", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
