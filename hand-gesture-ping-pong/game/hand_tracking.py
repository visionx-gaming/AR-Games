"""Threaded hand detection using MediaPipe."""

import cv2
import numpy as np
import mediapipe as mp
import math
import threading
import time
from game.config import (WINDOW_WIDTH, WINDOW_HEIGHT, HAND_PREDICT_SECONDS,
                         HAND_FILTER_MIN_CUTOFF, HAND_FILTER_BETA)

# Palm-base landmarks only (wrist + 4 MCP joints).
# Excludes fingertips, which shift the centroid heavily when fingers
# move or when the hand fills the frame up close.
_PALM_INDICES = [0, 5, 9, 13, 17]

# Adaptive Y range.  The tracker learns each hand's actual vertical travel and
# remaps it to the full court height, so a close-up hand (compressed range)
# gets the same reach as a distant one.  The range expands instantly when the
# hand goes beyond it and contracts slowly (time-based) toward where the hand
# actually is, but never below _Y_MIN_SPAN of the frame.
_Y_DEFAULT_MIN = 0.15
_Y_DEFAULT_MAX = 0.85
_Y_MIN_SPAN = 0.30
_Y_CONTRACT_RATE = 0.08   # fraction of the gap closed per second

# When a hand disappears for a moment, the remaining hand keeps the label of the
# hand it is closest to (if it is within this normalised x distance and was seen
# this recently), instead of being re-labelled by which half of the frame it is in.
_CONTINUITY_DIST = 0.30
_CONTINUITY_SECONDS = 0.6


class _OneEuroFilter:
    """Speed-adaptive low-pass filter (Casiez et al., "1€ filter")."""

    def __init__(self, min_cutoff, beta, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x = None
        self.dx = 0.0
        self.t = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        if self.min_cutoff <= 0:
            return x
        if self.t is None or not (0 < t - self.t < 0.25):     # first sample / after a gap
            self.x, self.dx, self.t = x, 0.0, t
            return x
        dt, self.t = t - self.t, t
        self.dx += self._alpha(self.d_cutoff, dt) * ((x - self.x) / dt - self.dx)
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        self.x += self._alpha(cutoff, dt) * (x - self.x)
        return self.x


class HandTracker:
    """Background-threaded hand-position and gesture detector."""

    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands_detector = self.mp_hands.Hands(
            max_num_hands=2,
            model_complexity=0,
            min_detection_confidence=0.55,   # lower = a hand that (re)appears is picked up sooner
            min_tracking_confidence=0.5,
        )

        self._lock = threading.Lock()
        self._hand_pos = {"Left": None, "Right": None}
        self._hand_landmarks = {"Left": None, "Right": None}
        self._fist_state = {"Left": False, "Right": False}
        self._frame = None
        self._running = False
        self._thread = None

        # When set to "Left"/"Right", a lone detected hand always controls that
        # side (used for single-player vs AI).  None = decide by position.
        self.single_hand_label = None
        # False while the game is on a screen that doesn't use the hands (frames dropped)
        self.accepting = True
        self._reset_requested = False
        # Smoothed vertical velocity (court-heights/s) per label, for prediction
        self._y_prev = {"Left": None, "Right": None}     # (y, time)
        self._y_vel = {"Left": 0.0, "Right": 0.0}
        self._y_filter = {lab: _OneEuroFilter(HAND_FILTER_MIN_CUTOFF, HAND_FILTER_BETA)
                          for lab in ("Left", "Right")}
        # Last seen normalised x (and when) per label, for label continuity
        self._prev_x = {"Left": None, "Right": None}

        # Pipeline health, shown on screen: detections/s, time spent detecting,
        # and camera-frame-arrival -> result age.
        self.detect_fps = 0.0
        self.detect_ms = 0.0
        self.latency_ms = 0.0
        self._last_done = None

        # Adaptive Y range per side — updated only inside the detection thread
        self._y_range = {
            "Left":  [_Y_DEFAULT_MIN, _Y_DEFAULT_MAX],
            "Right": [_Y_DEFAULT_MIN, _Y_DEFAULT_MAX],
        }
        self._last_t = time.perf_counter()

    # ---- Public API ----

    def start(self):
        """Start the detection thread."""
        self._running = True
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the detection thread and release the MediaPipe graph."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        try:
            self.hands_detector.close()
        except Exception:
            pass

    def send_frame(self, small_frame, stamp=None):
        """Hand a detection-sized frame (see CameraStream.latest_small) to the
        detector.  Only the newest frame is kept: if the thread is busy, the
        pending frame is simply replaced.  Not copied, so it must not be
        modified afterwards.  `stamp` is when the frame arrived from the camera
        (perf_counter), used to measure latency."""
        if not self.accepting:
            return
        with self._lock:
            self._frame = (small_frame, stamp)

    def reset_calibration(self):
        """Forget the previous player's hand range / position history.  Called
        between players so the next person starts calibrated from scratch."""
        self._reset_requested = True      # applied by the detection thread

    def stats_text(self):
        return f"TRK {self.detect_fps:.0f}/s {self.latency_ms:.0f}ms"

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
        """Closed fist: at least 3 fingertips closer to the wrist than their
        PIP joints.  Distance-based, so it works for any hand orientation."""
        lm = hand_landmarks.landmark
        wrist = lm[0]

        def dist(p):
            return math.hypot(p.x - wrist.x, p.y - wrist.y)

        curled = sum(
            1 for tip, pip in zip((8, 12, 16, 20), (6, 10, 14, 18))
            if dist(lm[tip]) < dist(lm[pip])
        )
        return curled >= 3

    def _assign_labels(self, detected, now=None):
        """detected is sorted by x. Returns one label per hand."""
        now = time.perf_counter() if now is None else now
        if len(detected) >= 2:
            labels = ["Left", "Right"]
        elif self.single_hand_label in ("Left", "Right"):
            labels = [self.single_hand_label]
        else:
            cx = detected[0][0]
            # A lone hand keeps the identity of whichever hand it is nearest to
            # (so one player's hand dropping out for a frame can't hand their
            # paddle to the other player); with no recent history, use position.
            near = [(abs(cx - x), lab) for lab, (x, t) in
                    ((lab, v) for lab, v in self._prev_x.items() if v is not None)
                    if now - t < _CONTINUITY_SECONDS]
            if near and min(near)[0] < _CONTINUITY_DIST:
                labels = [min(near)[1]]
            else:
                labels = ["Left" if cx < 0.5 else "Right"]
        for d, lab in zip(detected, labels):
            self._prev_x[lab] = (d[0], now)
        return labels

    def _remap_y(self, label, cy_norm, dt):
        """Map a raw palm Y (0-1 of the camera frame) to 0-1 of the court."""
        y_min, y_max = self._y_range[label]
        y_min = min(y_min, cy_norm)
        y_max = max(y_max, cy_norm)
        # Contract slowly toward the hand's position, keeping a minimum span
        k = min(1.0, _Y_CONTRACT_RATE * dt)
        if cy_norm > y_min:
            y_min += (cy_norm - y_min) * k
        if cy_norm < y_max:
            y_max += (cy_norm - y_max) * k
        if y_max - y_min < _Y_MIN_SPAN:
            mid = (y_min + y_max) / 2
            y_min, y_max = mid - _Y_MIN_SPAN / 2, mid + _Y_MIN_SPAN / 2
        self._y_range[label] = [y_min, y_max]
        return max(0.0, min(1.0, (cy_norm - y_min) / (y_max - y_min)))

    def _predict_y(self, label, y, now):
        """Extrapolate the hand's vertical position HAND_PREDICT_SECONDS ahead, using
        a smoothed velocity, to offset the camera + detection delay.  Capped so a
        sudden stop can't overshoot far."""
        prev = self._y_prev[label]
        if prev is not None and 0 < now - prev[1] < 0.2:
            raw_v = (y - prev[0]) / (now - prev[1])
            self._y_vel[label] = self._y_vel[label] * 0.6 + raw_v * 0.4
        else:
            self._y_vel[label] = 0.0
        self._y_prev[label] = (y, now)
        lead = max(-0.08, min(0.08, self._y_vel[label] * HAND_PREDICT_SECONDS))
        return max(0.0, min(1.0, y + lead))

    def _detection_loop(self):
        """Background detection loop."""
        while self._running:
            with self._lock:
                item = self._frame
                self._frame = None      # take ownership; newer frames can arrive

            if self._reset_requested:
                self._reset_requested = False
                self._y_range = {"Left": [_Y_DEFAULT_MIN, _Y_DEFAULT_MAX],
                                 "Right": [_Y_DEFAULT_MIN, _Y_DEFAULT_MAX]}
                self._y_prev = {"Left": None, "Right": None}
                self._y_vel = {"Left": 0.0, "Right": 0.0}
                self._prev_x = {"Left": None, "Right": None}
                for f in self._y_filter.values():
                    f.t = None

            if item is None:
                time.sleep(0.002)
                continue
            small, stamp = item

            now = time.perf_counter()
            dt = min(now - self._last_t, 0.5)
            self._last_t = now

            t_start = time.perf_counter()
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
                detected.sort(key=lambda d: d[0])
                assigned = self._assign_labels(detected)

                for (cx_norm, cy_norm, hand_lm), label in zip(detected, assigned):
                    y = self._y_filter[label](self._remap_y(label, cy_norm, dt), t_start)
                    cy_remapped = self._predict_y(label, y, t_start)
                    pos[label] = (
                        int(cx_norm * WINDOW_WIDTH),
                        int(cy_remapped * WINDOW_HEIGHT),
                    )
                    lm[label] = hand_lm
                    fist[label] = self._is_fist(hand_lm)

            with self._lock:
                self._hand_pos = pos
                self._hand_landmarks = lm
                self._fist_state = fist

            t_done = time.perf_counter()
            a = 0.1
            self.detect_ms += ((t_done - t_start) * 1000 - self.detect_ms) * a
            if stamp is not None:
                self.latency_ms += ((t_done - stamp) * 1000 - self.latency_ms) * a
            if self._last_done is not None:
                self.detect_fps += (1.0 / max(t_done - self._last_done, 1e-3) - self.detect_fps) * a
            self._last_done = t_done
