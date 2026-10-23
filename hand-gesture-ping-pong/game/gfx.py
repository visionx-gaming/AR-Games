"""Resolution-independent drawing.

All game code (renderer, screens, handlers) draws in a fixed *logical* space of
WINDOW_WIDTH x WINDOW_HEIGHT (1280x720).  The real frame can be any 16:9 size
(16k x 9k pixels); this module is a drop-in replacement for the cv2 drawing
calls that scales logical coordinates, radii, thicknesses and font scales to
the real frame, so the picture is rendered natively at the display's
resolution instead of being up-scaled from 720p.

Usage in a drawing module:   from game import gfx as cv2
Every cv2 name this module doesn't override (constants, addWeighted, resize,
...) is forwarded to the real cv2 unchanged.
"""

import cv2 as _cv2
import numpy as np

from game.config import WINDOW_WIDTH, MIN_RENDER_HEIGHT, MAX_RENDER_HEIGHT

# The frame is (16*K) x (9*K).  K = 80 is exactly the logical 1280x720, and
# K = 120 is Full HD 1920x1080, so scale = K / 80 is exact for common displays.
_BASE_K = WINDOW_WIDTH // 16
_MIN_K = MIN_RENDER_HEIGHT // 9
_MAX_K = MAX_RENDER_HEIGHT // 9

_k = _BASE_K
SCALE = 1.0          # real pixels per logical pixel (read at call time)
_max_k = _MAX_K      # render-resolution cap chosen by the user (settings); default = config maximum


def k_for_size(avail_w, avail_h):
    """Largest 16:9 render size (as K) that fits in avail_w x avail_h."""
    k = min(avail_w // 16, avail_h // 9)
    return max(_MIN_K, min(_max_k, k))


def set_render_cap(height):
    """Limit the render height (0 = no limit beyond MAX_RENDER_HEIGHT). True if it changed."""
    global _max_k
    k = _MAX_K if not height else max(_MIN_K, min(_MAX_K, height // 9))
    changed = k != _max_k
    _max_k = k
    return changed


def set_k(k):
    """Switch the render resolution. Returns True if it changed."""
    global _k, SCALE
    if k == _k:
        return False
    _k = k
    SCALE = k / _BASE_K
    return True


def frame_size():
    """(width, height) in real pixels of the render frame."""
    return 16 * _k, 9 * _k


# ---------------------------------------------------------------------------
#  scaling helpers
# ---------------------------------------------------------------------------

def px(v):
    """Scale a logical length to real pixels."""
    return int(round(v * SCALE))


def _pt(p):
    return (int(round(p[0] * SCALE)), int(round(p[1] * SCALE)))


def _len(v):
    # Keep at least 1px for any positive length so thin lines never vanish
    return max(1, int(round(v * SCALE))) if v > 0 else int(v)


def _thick(t):
    return t if t <= 0 else max(1, int(round(t * SCALE)))


def _poly(p):
    return (np.asarray(p, dtype=np.float64) * SCALE).round().astype(np.int32)


# ---------------------------------------------------------------------------
#  cv2 drawing replacements (same signatures, logical coordinates)
# ---------------------------------------------------------------------------

def line(img, pt1, pt2, color, thickness=1, *args, **kwargs):
    return _cv2.line(img, _pt(pt1), _pt(pt2), color, _thick(thickness), *args, **kwargs)


def rectangle(img, pt1, pt2, color, thickness=1, *args, **kwargs):
    return _cv2.rectangle(img, _pt(pt1), _pt(pt2), color, _thick(thickness), *args, **kwargs)


def circle(img, center, radius, color, thickness=1, *args, **kwargs):
    return _cv2.circle(img, _pt(center), _len(radius), color, _thick(thickness), *args, **kwargs)


def ellipse(img, center, axes, angle, start_angle, end_angle, color, thickness=1,
            *args, **kwargs):
    return _cv2.ellipse(img, _pt(center), (_len(axes[0]), _len(axes[1])), angle,
                        start_angle, end_angle, color, _thick(thickness), *args, **kwargs)


def fillPoly(img, pts, color, *args, **kwargs):
    return _cv2.fillPoly(img, [_poly(p) for p in pts], color, *args, **kwargs)


def polylines(img, pts, is_closed, color, thickness=1, *args, **kwargs):
    return _cv2.polylines(img, [_poly(p) for p in pts], is_closed, color,
                          _thick(thickness), *args, **kwargs)


def putText(img, text, org, font_face, font_scale, color, thickness=1, *args, **kwargs):
    return _cv2.putText(img, text, _pt(org), font_face, font_scale * SCALE, color,
                        _thick(thickness), *args, **kwargs)
