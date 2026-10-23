"""Threaded webcam capture, so the game loop never blocks on the camera."""

import json
import os
import subprocess
import sys
import threading
import time

# Skip Media Foundation's slow hardware-transform path (much faster camera
# open).  Must be set before cv2 is first imported.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2

from game.config import (CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, CAMERA_MIN_FPS,
                         DETECTION_WIDTH, DETECTION_HEIGHT)
from game.utils import fit_to_window

# Consecutive failed reads before the camera is reported as lost (~2 s)
_MAX_FAILED_READS = 100


class CameraStream:
    """Reads frames on a background thread and keeps only the newest one.

    The game loop runs at its own rate (physics/render are independent of the
    webcam's fps) and just asks for the latest frame.  A camera that is
    missing or stops delivering is reported through `ok` rather than
    crashing or silently quitting the game.
    """

    def __init__(self, index=0, width=CAMERA_WIDTH, height=CAMERA_HEIGHT, fps=CAMERA_FPS):
        self.index = index
        self.size = (width, height)      # updated to the real size on the first frame
        self.fps = 0.0                   # measured by _try_open
        # (w, h) the game renders at.  When set, frames are mirrored and fitted
        # to it on the camera thread, so the game loop gets them ready-made.
        self.target_size = None
        self.failed_indices = []         # cameras that failed to open before this one worked
        # Called on the camera thread with (small_frame, arrival_time) for every new
        # frame, so the hand tracker gets it immediately instead of waiting for the
        # next game-loop iteration.
        self.on_small = None
        self._cap = None
        # Media Foundation first: on many USB webcams DirectShow only manages
        # a few fps at HD while MSMF delivers the full 30.
        for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY):
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                self._cap = cap
                break
            cap.release()

        if self._cap is not None:
            # MJPEG first: uncompressed capture is bandwidth-limited over USB
            # and gives far lower frame rates on many webcams.
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self._cap.set(cv2.CAP_PROP_FPS, fps)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._lock = threading.Lock()
        self._frame = None
        self._small = None        # detection-sized copy, made on this thread
        self._stamp = 0.0         # perf_counter() when the newest frame arrived
        self._seq = 0
        self._failed = 0
        self._running = False
        self._thread = None

    @property
    def label(self):
        return f"{self.index}  {self.size[0]}x{self.size[1]}"

    @property
    def opened(self):
        return self._cap is not None

    @property
    def ok(self):
        """True while the camera is opened and delivering frames."""
        return self._cap is not None and self._failed < _MAX_FAILED_READS

    def start(self):
        if self._cap is None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def read(self):
        """Return (frame, seq) for the newest (mirrored, fitted) frame; frame is
        None until one arrives. seq increases with every new frame.  The frame
        must be treated as read-only: it is shared with the hand tracker."""
        with self._lock:
            return self._frame, self._seq

    def latest_small(self):
        """(small_frame, arrival_time) for the newest frame, sized for hand
        detection.  Downscaled here, on the camera thread, so neither the game
        loop nor the detector spends time on it."""
        with self._lock:
            return self._small, self._stamp

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap is not None:
            self._cap.release()

    def _loop(self):
        while self._running:
            ret, frame = self._cap.read()
            stamp = time.perf_counter()
            if ret:
                self.size = (frame.shape[1], frame.shape[0])
                frame = cv2.flip(frame, 1)               # mirror: it's a "mirror" game
                target = self.target_size
                if target is not None:
                    frame = fit_to_window(frame, *target)
                small = cv2.resize(frame, (DETECTION_WIDTH, DETECTION_HEIGHT),
                                   interpolation=cv2.INTER_AREA)
                with self._lock:
                    self._frame = frame
                    self._small = small
                    self._stamp = stamp
                    self._seq += 1
                listener = self.on_small
                if listener is not None:
                    listener(small, stamp)
                self._failed = 0
            else:
                self._failed += 1
                time.sleep(0.02)


# ===================================================================
#  CAMERA SELECTION
# ===================================================================

# Highest device index probed.  Laptops with an external webcam typically
# expose the built-in camera as 0 and the external one as 1.
MAX_CAMERA_INDEX = 6
_FIRST_FRAME_TIMEOUT = 5.0     # some USB cameras need several seconds to start streaming


_FPS_PROBE_SECONDS = 1.0
# Modes tried in order: the configured one, then a safe fallback
_MODES = list(dict.fromkeys([(CAMERA_WIDTH, CAMERA_HEIGHT), (1280, 720), (640, 480)]))


def _modes_for(max_height):
    """The capture modes to try, best first, never above max_height (0 = no limit)."""
    modes = [m for m in _MODES if not max_height or m[1] <= max_height]
    return modes or [_MODES[-1]]


def _try_open(index, max_height=0):
    """Open camera `index` and return a started stream only if it actually
    delivers frames (some devices open fine but never produce an image, e.g.
    infrared / virtual cameras).  Tries the best resolution first (at most
    max_height, if given) and steps down if it can't sustain CAMERA_MIN_FPS.
    None on failure."""
    modes = _modes_for(max_height)
    for n, (w, h) in enumerate(modes):
        cam = CameraStream(index, w, h)
        if not cam.opened:
            return None
        cam.start()
        deadline = time.monotonic() + _FIRST_FRAME_TIMEOUT
        while time.monotonic() < deadline and cam.read()[0] is None:
            time.sleep(0.02)
        if cam.read()[0] is None:
            cam.stop()
            return None
        seq0 = cam.read()[1]
        time.sleep(_FPS_PROBE_SECONDS)
        cam.fps = (cam.read()[1] - seq0) / _FPS_PROBE_SECONDS
        last_mode = n == len(modes) - 1
        if cam.fps >= CAMERA_MIN_FPS or last_mode:
            return cam
        cam.stop()
    return None


def open_camera(preferred=0, max_height=0):
    """Open the preferred camera, else the first one that works.
    Always returns a CameraStream (check `.ok`)."""
    order = [preferred] + [i for i in range(MAX_CAMERA_INDEX) if i != preferred]
    for i in order:
        cam = _try_open(i, max_height)
        if cam is not None:
            return cam
    return CameraStream(preferred)


def open_specific(index, max_height=0):
    """Open exactly camera `index` (no fallback to other devices); None if it fails."""
    return _try_open(index, max_height)


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROBE_CODE = (
    "import sys, json; sys.path.insert(0, sys.argv[1]);"
    "from game.camera import _probe_in_process;"
    "print('PROBE:' + json.dumps(_probe_in_process(set(json.loads(sys.argv[2])))))"
)


def probe_cameras(skip=(), timeout=25):
    """Find attached cameras without keeping them open: [{"index", "w", "h"}], where
    w x h is the best size each delivers.  Devices in `skip` (the one in use) are
    not touched.

    Opening a camera is a call into the OS camera driver, and probing devices while
    another one is streaming can hang or crash a driver.  So it runs in a separate
    process: whatever happens there cannot take the game down (worst case: no
    cameras reported).  Slow (about a second per device) - call from a thread."""
    try:
        out = subprocess.run(
            [sys.executable, "-c", _PROBE_CODE, _PROJECT_ROOT, json.dumps(sorted(skip))],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        for line in reversed(out.splitlines()):
            if line.startswith("PROBE:"):
                return json.loads(line[len("PROBE:"):])
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print(f"[camera] scan failed: {e}")
    return []


def _probe_in_process(skip=()):
    """The actual probing (run in the child process started by probe_cameras)."""
    found = []
    for i in range(MAX_CAMERA_INDEX):
        if i in skip:
            continue
        cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
        try:
            if not cap.isOpened():
                continue
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            deadline = time.monotonic() + 2.5
            while time.monotonic() < deadline:
                ok, frame = cap.read()
                if ok and frame is not None:
                    found.append({"index": i, "w": frame.shape[1], "h": frame.shape[0]})
                    break
        finally:
            cap.release()
    return found

