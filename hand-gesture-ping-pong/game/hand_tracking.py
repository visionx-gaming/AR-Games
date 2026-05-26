"""Threaded hand detection using MediaPipe."""

import cv2
import numpy as np
import mediapipe as mp
import threading
import time
from game.config import DETECTION_WIDTH, DETECTION_HEIGHT, WINDOW_WIDTH, WINDOW_HEIGHT

# Palm-base landmarks only (wrist + 4 MCP joints).
# Excludes fingertips, which shift the centroid heavily when fingers
# move or when the hand fills the frame up close.
_PALM_INDICES = [0, 5, 9, 13, 17]

# Y-range defaults and decay.  The tracker learns each hand's actual Y
# travel range over time and remaps accordingly, so a close-up hand
# (compressed range) gets the same effective control as a distant one.
_Y_DEFAULT_MIN = 0.15
_Y_DEFAULT_MAX = 0.85
_Y_DECAY = 0.997   # per detection frame; range contracts ~1% per second → recalibrates in ~20 s


class HandTracker:
    """Background-threaded hand-position and gesture detector."""

    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands_detector = self.mp_hands.Hands(
            max_num_hands=2,
            model_complexity=0,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )

        self._lock = threading.Lock()
        self._hand_pos = {"Left": None, "Right": None}
        self._hand_landmarks = {"Left": None, "Right": None}
        self._fist_state = {"Left": False, "Right": False}
        self._frame = None
        self._running = False
        self._thread = None
        self._frame_counter = 0

        # Adaptive Y range per side — updated only inside the detection thread
        self._y_range = {
            "Left":  [_Y_DEFAULT_MIN, _Y_DEFAULT_MAX],
            "Right": [_Y_DEFAULT_MIN, _Y_DEFAULT_MAX],
        }

    # ---- Public API ----

    def start(self):
        """Start the detection thread."""
        self._running = True
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the detection thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def send_frame(self, frame):
        """Send a frame for processing. Drops frames if the thread is busy.
        Only processes every 2nd frame for performance."""
        self._frame_counter += 1
        if self._frame_counter % 2 != 0:
            return
        with self._lock:
            self._frame = frame.copy()

    def get_results(self):
        """Get latest detection results (thread-safe copy)."""
        with self._lock:
            return (
                dict(self._hand_pos),
                dict(self._hand_landmarks),
                dict(self._fist_state),
            )

    @property
    def mp_hand_connections(self):
        """Access MediaPipe hand connections for skeleton drawing."""
        return self.mp_hands.HAND_CONNECTIONS

    # ---- Internal ----

    @staticmethod
    def _is_fist(hand_landmarks):
        """Detect closed fist: at least 3 fingertips below their PIP joints."""
        tips = [8, 12, 16, 20]
        pips = [6, 10, 14, 18]
        curled = sum(
            1 for tip, pip in zip(tips, pips)
            if hand_landmarks.landmark[tip].y > hand_landmarks.landmark[pip].y
        )
        return curled >= 3

    def _detection_loop(self):
        """Background detection loop."""
        while self._running:
            with self._lock:
                frame = self._frame

            if frame is None:
                time.sleep(0.005)
                continue

            small = cv2.resize(frame, (DETECTION_WIDTH, DETECTION_HEIGHT))
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            results = self.hands_detector.process(rgb)

            pos = {"Left": None, "Right": None}
            lm = {"Left": None, "Right": None}
            fist = {"Left": False, "Right": False}

            if results.multi_hand_landmarks:
                # --- Collect palm centers for all detected hands ---
                detected = []
                for hand_lm in results.multi_hand_landmarks:
                    px = [hand_lm.landmark[i].x for i in _PALM_INDICES]
                    py = [hand_lm.landmark[i].y for i in _PALM_INDICES]
                    detected.append((float(np.mean(px)), float(np.mean(py)), hand_lm))

                # --- Assign labels by X screen position, not anatomy ---
                # Sorting by X and labelling left→right is unambiguous:
                # it works whether two players each use one hand, or one
                # person uses both hands, and is immune to MediaPipe's
                # anatomical label flipping when hands are close together.
                detected.sort(key=lambda d: d[0])

                if len(detected) == 1:
                    cx = detected[0][0]
                    assigned = ["Left" if cx < 0.5 else "Right"]
                else:
                    assigned = ["Left", "Right"]

                for (cx_norm, cy_norm, hand_lm), label in zip(detected, assigned):
                    # --- Adaptive Y range (distance compensation) ---
                    y_min, y_max = self._y_range[label]
                    y_min = min(y_min, cy_norm)
                    y_max = max(y_max, cy_norm)
                    y_min = y_min * _Y_DECAY + _Y_DEFAULT_MIN * (1 - _Y_DECAY)
                    y_max = y_max * _Y_DECAY + _Y_DEFAULT_MAX * (1 - _Y_DECAY)
                    self._y_range[label] = [y_min, y_max]

                    span = max(y_max - y_min, 0.1)
                    cy_remapped = max(0.0, min(1.0, (cy_norm - y_min) / span))

                    center = (
                        int(cx_norm * WINDOW_WIDTH),
                        int(cy_remapped * WINDOW_HEIGHT),
                    )
                    pos[label] = center
                    lm[label] = hand_lm
                    fist[label] = self._is_fist(hand_lm)

            with self._lock:
                self._hand_pos = pos
                self._hand_landmarks = lm
                self._fist_state = fist
                self._frame = None

            time.sleep(0.001)
