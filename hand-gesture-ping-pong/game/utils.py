"""Utility functions: math helpers, screen detection, frame processing."""

import cv2
import functools
import numpy as np
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


def detect_screen_resolution():
    """Detect the primary monitor resolution using multiple fallback methods."""
    # Method 1: screeninfo (cross-platform, most reliable if installed)
    try:
        from screeninfo import get_monitors
        mon = get_monitors()[0]
        return mon.width, mon.height
    except Exception:
        pass

    # Method 2: Windows API via ctypes (built-in on Windows, DPI-aware)
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
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


def letterbox_frame(frame, target_w, target_h):
    """Resize frame to fit target dimensions while preserving aspect ratio.
    Pads with black bars (letterbox/pillarbox) as needed."""
    h, w = frame.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    x_off = (target_w - new_w) // 2
    y_off = (target_h - new_h) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    return canvas
