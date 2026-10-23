"""Utility functions: math helpers, screen detection, frame processing."""

import cv2
import functools
from game.config import WINDOW_WIDTH, WINDOW_HEIGHT


def lerp(current, target, factor):
    """Linear interpolation."""
    return current + (target - current) * factor


@functools.lru_cache(maxsize=512)
def scale_color(color, factor):
    """Scale a BGR color tuple by a factor, clamping to 0-255.
    Cached: each unique (color, factor) pair is computed only once."""
    return tuple(max(0, min(255, int(c * factor))) for c in color)


@functools.lru_cache(maxsize=256)
def brighten_color(color, amount=80):
    """Brighten a BGR color by adding a fixed amount, clamping to 255.
    Cached: repeated calls with the same arguments return instantly."""
    return tuple(min(255, c + amount) for c in color)


def fit_to_window(frame, target_w=WINDOW_WIDTH, target_h=WINDOW_HEIGHT):
    """Fit a camera frame to the render frame (target_w x target_h).

    A 16:9-ish frame is scaled to the target height and centre-cropped, so the
    picture is never stretched (a frame that already matches needs no scaling
    at all).  Other shapes (e.g. 4:3) are stretched to keep their full field
    of view.
    """
    h, w = frame.shape[:2]
    if w == target_w and h == target_h:
        return frame
    aspect = w / h
    target = target_w / target_h
    if target < aspect <= target * 1.2:
        new_w = round(w * target_h / h)
        if new_w != w:
            frame = cv2.resize(frame, (new_w, target_h), interpolation=cv2.INTER_LINEAR)
        x0 = (new_w - target_w) // 2
        return frame[:, x0:x0 + target_w].copy()
    return cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)


def detect_screen_resolution():
    """Detect the primary monitor resolution using multiple fallback methods."""
    # Method 1: Windows API. Becoming DPI-aware first guarantees the reported
    # size is in the same physical pixels as the fullscreen window, even with
    # display scaling (this used to be skipped whenever screeninfo was present).
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        pass

    # Method 2: screeninfo (cross-platform, if installed)
    try:
        from screeninfo import get_monitors
        mon = get_monitors()[0]
        return mon.width, mon.height
    except Exception:
        pass

    # Method 3: tkinter (usually bundled with Python)
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        return sw, sh
    except Exception:
        pass

    # Final fallback: use game window size
    return WINDOW_WIDTH, WINDOW_HEIGHT

