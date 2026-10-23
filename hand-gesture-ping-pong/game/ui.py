"""UI toolkit: design tokens, smooth shapes, text and small components (menu widgets: game.widgets).

Everything is positioned in the game's logical 1280x720 space and scaled to the
real frame by game.gfx, like the rest of the drawing code.

Design language
  * dark glass panels with a hairline border and smooth (anti-aliased) corners
  * one accent colour per colour theme, used sparingly: focus, primary actions
  * three text colours (primary / secondary / muted) and two typefaces:
    Rajdhani for everything readable, Press Start 2P for the logo and big numerals
  * every interactive row has the same states: idle, focused/hovered, disabled
  * motion: rows slide/fade in, focus glides between states, screens fade

Widgets (game.widgets.MenuView) handle keyboard, mouse and focus in one place, so a
screen only declares its items and reacts to the events that come back.
"""

import math
from collections import OrderedDict

import cv2 as _cv
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from game import gfx
from game import font as _font
from game.config import WINDOW_WIDTH, WINDOW_HEIGHT
from game.renderer import _prep_tile, _composite
from game.utils import scale_color

# ===================================================================
#  DESIGN TOKENS  (BGR)
# ===================================================================

TEXT = (246, 246, 246)
TEXT_2 = (190, 188, 184)          # secondary
TEXT_3 = (128, 124, 120)          # muted
PANEL = (30, 24, 22)              # glass fill
PANEL_HI = (52, 42, 38)           # raised surface (tiles, chips)
TRACK = (74, 68, 64)              # slider / toggle off
DANGER = (84, 84, 238)
SUCCESS = (120, 222, 132)
WARN = (60, 176, 255)
GOLD = (0, 205, 255)

MARGIN = 72                       # outer screen margin


def mix(a, b, t):
    """Blend colour a toward b by t (0..1)."""
    t = max(0.0, min(1.0, t))
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def approach(cur, target, dt, speed=14.0):
    """Exponential smoothing toward target (frame-rate independent)."""
    return cur + (target - cur) * (1.0 - math.exp(-speed * dt))


# ===================================================================
#  SPRITE CACHE + BLITTING
# ===================================================================

_cache = OrderedDict()
_CACHE_LIMIT = 700


def cached(key, build):
    v = _cache.get(key)
    if v is None:
        v = build()
        _cache[key] = v
        if len(_cache) > _CACHE_LIMIT:
            _cache.popitem(last=False)
    else:
        _cache.move_to_end(key)
    return v


def blit(frame, tile, fx, fy, opacity=1.0):
    """Composite a prepared tile (see renderer._prep_tile) at real pixel (fx, fy)."""
    if opacity >= 0.995:
        _composite(frame, tile, fx, fy)
    elif opacity > 0.01:
        bgr, wa, _ = tile
        wa2 = wa * opacity
        _composite(frame, (bgr, wa2, 1.0 - wa2), fx, fy)


# ===================================================================
#  TEXT
# ===================================================================

_CAP_HEIGHT = {}


def _pil_font(px, weight):
    return _font.get(px) if weight == "pixel" else _font.get_ui(px, weight)


def _cap_height(px, weight):
    key = (px, weight)
    if key not in _CAP_HEIGHT:
        f = _pil_font(px, weight)
        asc, _ = f.getmetrics()
        _CAP_HEIGHT[key] = max(1, asc - f.getbbox("H")[1])
    return _CAP_HEIGHT[key]


def _build_text(s, px, weight, color, spacing, shadow):
    f = _pil_font(px, weight)
    asc, desc = f.getmetrics()
    pad = 3 + (max(2, px // 6) if shadow else 0)
    if spacing:
        total = sum(f.getlength(ch) + spacing for ch in s) - spacing
    else:
        total = f.getlength(s)
    w, h = int(math.ceil(total)) + pad * 2, asc + desc + pad * 2
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    if spacing:
        x = pad
        for ch in s:
            d.text((x, pad), ch, font=f, fill=255)
            x += f.getlength(ch) + spacing
    else:
        d.text((pad, pad), s, font=f, fill=255)
    rgba = Image.new("RGBA", (w, h), (color[2], color[1], color[0], 0))
    rgba.putalpha(mask)
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        off = max(1, px // 14)
        smask = Image.new("L", (w, h), 0)
        smask.paste(mask, (off, off))
        smask = smask.filter(ImageFilter.GaussianBlur(max(1.0, px / 12)))
        sh.putalpha(smask.point(lambda v: int(v * 0.85)))
        rgba = Image.alpha_composite(sh, rgba)
    return _prep_tile(np.array(rgba)), w, h, pad, asc


def text(frame, s, x, y, size, color=TEXT, anchor="left", weight="semi", opacity=1.0,
         spacing=0.0, shadow=False, valign="mid"):
    """Draw text.  x/y are logical; valign 'mid' centres the capital height on y,
    'base' puts the baseline on y.  weight: medium | semi | bold | pixel."""
    if not s or opacity <= 0.01:
        return
    S = gfx.SCALE
    px = max(6, round(size * S))
    sp = round(spacing * S, 1)
    tile, w, h, pad, asc = cached(("t", s, px, weight, color, sp, shadow),
                                  lambda: _build_text(s, px, weight, color, sp, shadow))
    cap = _cap_height(px, weight)
    X, Y = round(x * S), round(y * S)
    tw = w - pad * 2
    fx = X - pad - (tw // 2 if anchor == "center" else tw if anchor == "right" else 0)
    base = Y + (cap // 2 if valign == "mid" else cap if valign == "top" else 0)
    blit(frame, tile, fx, base - pad - asc, opacity)


def fit_text(s, size, weight, max_w):
    """Shorten s with an ellipsis so it fits max_w logical px."""
    if text_width(s, size, weight) <= max_w:
        return s
    while len(s) > 1 and text_width(s + "...", size, weight) > max_w:
        s = s[:-1]
    return s.rstrip() + "..."


_width_cache = {}


def text_width(s, size, weight="semi", spacing=0.0):
    """Logical width of a string (for laying out chips / right-aligned groups).
    Cached: menus ask for the same widths every frame."""
    S = gfx.SCALE
    key = (s, size, weight, spacing, S)
    w = _width_cache.get(key)
    if w is None:
        f = _pil_font(max(6, round(size * S)), weight)
        total = sum(f.getlength(ch) + spacing * S for ch in s) - spacing * S if spacing else f.getlength(s)
        w = total / S
        if len(_width_cache) > 4000:
            _width_cache.clear()
        _width_cache[key] = w
    return w


# ===================================================================
#  SMOOTH SHAPES
# ===================================================================

_SEG = 7
_rr_cache = {}


def _rr_unit_points(w, h, r):
    key = (w, h, r)
    pts = _rr_cache.get(key)
    if pts is None:
        raw = []
        for cx, cy, a0 in ((w - r, r, -90), (w - r, h - r, 0), (r, h - r, 90), (r, r, 180)):
            for i in range(_SEG + 1):
                a = math.radians(a0 + 90.0 * i / _SEG)
                raw.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        pts = (np.array(raw) * 16).round().astype(np.int32)
        if len(_rr_cache) > 300:
            _rr_cache.clear()
        _rr_cache[key] = pts
    return pts


def rrect(img, x, y, w, h, r, color, thickness=0):
    """Anti-aliased rounded rectangle, logical coords.  thickness 0 = filled."""
    S = gfx.SCALE
    W, H = round(w * S * 4) / 4, round(h * S * 4) / 4
    R = max(1.0, min(r * S, W / 2, H / 2))
    pts = _rr_unit_points(W, H, round(R * 4) / 4) + np.array([round(x * S * 16), round(y * S * 16)], np.int32)
    if thickness <= 0:
        _cv.fillConvexPoly(img, pts, color, _cv.LINE_AA, 4)
    else:
        _cv.polylines(img, [pts], True, color, max(1, round(thickness * S)), _cv.LINE_AA, 4)


def _roi(frame, x, y, w, h, pad=0):
    S = gfx.SCALE
    fh, fw = frame.shape[:2]
    x0, y0 = max(0, int((x - pad) * S)), max(0, int((y - pad) * S))
    x1, y1 = min(fw, int((x + w + pad) * S) + 2), min(fh, int((y + h + pad) * S) + 2)
    return slice(y0, y1), slice(x0, x1)


def panel(frame, x, y, w, h, radius=14, fill=PANEL, alpha=0.74, border=None, border_alpha=0.22):
    """Translucent dark panel with a hairline border (only its own area is blended)."""
    rows, cols = _roi(frame, x, y, w, h, pad=2)
    roi = frame[rows, cols]
    if roi.size == 0:
        return
    ov = roi.copy()
    # draw on the ROI at local coordinates (shift the origin)
    S = gfx.SCALE
    lx, ly = x - cols.start / S, y - rows.start / S
    rrect(ov, lx, ly, w, h, radius, fill)
    _cv.addWeighted(ov, alpha, roi, 1.0 - alpha, 0, dst=roi)
    border = border if border is not None else (255, 255, 255)
    rrect(roi, lx, ly, w, h, radius, mix(fill, border, border_alpha), 1)


def fill_rrect(frame, x, y, w, h, radius, color, alpha=1.0):
    """Solid / translucent filled rounded rectangle."""
    if alpha >= 0.995:
        rrect(frame, x, y, w, h, radius, color)
        return
    rows, cols = _roi(frame, x, y, w, h, pad=2)
    roi = frame[rows, cols]
    if roi.size == 0:
        return
    ov = roi.copy()
    S = gfx.SCALE
    rrect(ov, x - cols.start / S, y - rows.start / S, w, h, radius, color)
    _cv.addWeighted(ov, alpha, roi, 1.0 - alpha, 0, dst=roi)


def disc(frame, cx, cy, r, color):
    S = gfx.SCALE
    _cv.circle(frame, (round(cx * S * 16), round(cy * S * 16)), max(1, round(r * S * 16)), color, -1, _cv.LINE_AA, 4)


def triangle(frame, cx, cy, size, direction, color):
    """Small solid chevron/triangle pointing left/right/up/down."""
    S = gfx.SCALE
    s = size
    if direction == "right":
        pts = [(cx - s * 0.5, cy - s), (cx + s * 0.7, cy), (cx - s * 0.5, cy + s)]
    elif direction == "left":
        pts = [(cx + s * 0.5, cy - s), (cx - s * 0.7, cy), (cx + s * 0.5, cy + s)]
    elif direction == "down":
        pts = [(cx - s, cy - s * 0.5), (cx + s, cy - s * 0.5), (cx, cy + s * 0.7)]
    else:
        pts = [(cx - s, cy + s * 0.5), (cx + s, cy + s * 0.5), (cx, cy - s * 0.7)]
    arr = np.array([(round(px * S * 16), round(py * S * 16)) for px, py in pts], np.int32)
    _cv.fillConvexPoly(frame, arr, color, _cv.LINE_AA, 4)


def hline(frame, x1, x2, y, color, thickness=1):
    S = gfx.SCALE
    _cv.line(frame, (round(x1 * S), round(y * S)), (round(x2 * S), round(y * S)), color,
             max(1, round(thickness * S)), _cv.LINE_AA)


def progress_ring(frame, cx, cy, r, frac, color, track=TRACK, thickness=6):
    S = gfx.SCALE
    c, rr, th = (round(cx * S), round(cy * S)), round(r * S), max(1, round(thickness * S))
    _cv.ellipse(frame, c, (rr, rr), 0, 0, 360, track, th, _cv.LINE_AA)
    if frac > 0.002:
        _cv.ellipse(frame, c, (rr, rr), 0, -90, -90 + 360 * min(1.0, frac), color, th, _cv.LINE_AA)


def progress_bar(frame, x, y, w, h, frac, color, track=TRACK):
    fill_rrect(frame, x, y, w, h, h / 2, track)
    if frac > 0.01:
        fill_rrect(frame, x, y, max(h, w * min(1.0, frac)), h, h / 2, color)


# ===================================================================
#  COMMON CHROME
# ===================================================================

def hints(frame, items, y=None, opacity=1.0, backdrop=False):
    """Bottom key-hint bar: [KEY] label  [KEY] label ...  (backdrop=True blanks whatever
    is underneath, for modal dialogs drawn over another screen's hints)."""
    y = WINDOW_HEIGHT - 34 if y is None else y
    if backdrop:
        fill_rrect(frame, 0, y - 28, WINDOW_WIDTH, WINDOW_HEIGHT - y + 28, 0, (8, 6, 6), 0.94)
    widths = []
    for key, label in items:
        kw = max(26, text_width(key, 14, "bold") + 16)
        widths.append((kw, kw + 8 + text_width(label, 15, "medium")))
    gap = 26
    total = sum(w for _, w in widths) + gap * (len(items) - 1)
    x = (WINDOW_WIDTH - total) / 2
    for (key, label), (kw, w) in zip(items, widths):
        fill_rrect(frame, x, y - 13, kw, 26, 7, PANEL_HI, 0.92 * opacity)
        rrect(frame, x, y - 13, kw, 26, 7, mix(PANEL_HI, (255, 255, 255), 0.18), 1)
        text(frame, key, x + kw / 2, y, 14, TEXT, "center", "bold", opacity)
        text(frame, label, x + kw + 8, y, 15, TEXT_3, "left", "medium", opacity)
        x += w + gap


def header(frame, title, subtitle=None, x=MARGIN, y=64, accent=TEXT):
    text(frame, title, x, y, 40, TEXT, "left", "bold", spacing=1.5, shadow=True)
    if subtitle:
        text(frame, subtitle, x + 2, y + 34, 17, TEXT_3, "left", "medium")


_grad_cache = {}


def side_gradient(frame, strength=0.62, extent=0.58):
    """Darken the left side (where menu text sits) with a smooth fade to the right."""
    h, w = frame.shape[:2]
    key = (w, h, strength, extent)
    inv = _grad_cache.get(key)
    if inv is None:
        wc = int(w * extent) + 1                      # the fade ends at `extent`; the rest is untouched
        xs = np.linspace(0.0, 1.0, w, dtype=np.float32)[:wc]
        d = np.clip(1.0 - xs / extent, 0.0, 1.0) ** 1.3 * strength
        inv1 = (1.0 - d)[None, :, None]
        inv = np.ascontiguousarray(np.broadcast_to((inv1 * 255).astype(np.uint8), (h, wc, 3)))
        _grad_cache.clear()
        _grad_cache[key] = inv
    region = frame[:, :inv.shape[1]]
    _cv.multiply(region, inv, dst=region, scale=1.0 / 255)


def attract_court(frame, now, theme, x0=0.0, x1=WINDOW_WIDTH, dim=0.30):
    """A quiet pong rally behind menu screens: ball with a trail, two paddles that follow it."""
    acc = scale_color(theme["accent"], dim)
    S = gfx.SCALE
    cx = (x0 + x1) / 2
    for yy in range(40, WINDOW_HEIGHT - 20, 36):
        _cv.line(frame, (round(cx * S), round(yy * S)), (round(cx * S), round((yy + 16) * S)),
                 scale_color(acc, 0.5), max(1, round(2 * S)))
    span = (x1 - x0) - 130

    def ball_at(t):
        u = (t * 0.30) % 2.0
        return x0 + 65 + span * (u if u < 1 else 2 - u), 360 + 200 * math.sin(t * 1.1)

    bx, by = ball_at(now)
    for i in range(8, 0, -1):
        tx, ty = ball_at(now - i * 0.04)
        disc(frame, tx, ty, max(2, 11 - i), scale_color(acc, 0.85 - i * 0.08))
    disc(frame, bx, by, 11, acc)
    ph = 120
    for px_ in (x0 + 22, x1 - 36):
        py_ = max(30.0, min(WINDOW_HEIGHT - 30.0 - ph, by - ph / 2))
        fill_rrect(frame, px_, py_, 14, ph, 7, scale_color(acc, 0.8))


def fade_in(frame, elapsed, duration=0.28):
    """Fade a screen in from black (cheap: only runs for `duration` after a state change)."""
    if 0 <= elapsed < duration:
        a = ease_out(elapsed / duration)
        _cv.convertScaleAbs(frame, dst=frame, alpha=0.25 + 0.75 * a)


# ===================================================================
#  MISC COMPONENTS
# ===================================================================

def chip(frame, x, y, label, color=TEXT_2, fill=PANEL_HI, size=14, pad=12, h=26):
    """Small rounded label (returns its width)."""
    w = text_width(label, size, "bold", 0.8) + pad * 2
    fill_rrect(frame, x, y, w, h, h / 2.2, fill, 0.9)
    text(frame, label, x + w / 2, y + h / 2, size, color, "center", "bold", spacing=0.8)
    return w


def stat_tile(frame, x, y, w, h, label, value, accent, value_pixel=True):
    fill_rrect(frame, x, y, w, h, 12, PANEL_HI, 0.55)
    rrect(frame, x, y, w, h, 12, mix(PANEL_HI, (255, 255, 255), 0.10), 1)
    text(frame, label, x + w / 2, y + 24, 13, TEXT_3, "center", "bold", spacing=1.0)
    if value_pixel:
        text(frame, value, x + w / 2, y + h - 30, 22, accent, "center", "pixel")
    else:
        text(frame, value, x + w / 2, y + h - 30, 30, accent, "center", "bold")


def logo(frame, x, y, accent, now):
    """HAND PONG wordmark: pixel face with a soft accent glow."""
    for line, off, col in (("HAND", 0, TEXT), ("PONG", 62, accent)):
        glow = scale_color(col, 0.28)
        text(frame, line, x + 3, y + off + 3, 52, glow, "left", "pixel")
        text(frame, line, x, y + off, 52, col, "left", "pixel", shadow=True)
    text(frame, "GESTURE-CONTROLLED ARCADE", x + 3, y + 112, 16, TEXT_3, "left", "semi", spacing=3.2)


# ===================================================================
#  MOUSE CURSOR
# ===================================================================

# Classic arrow, logical px, hot-spot (the tip) at (0, 0).
_ARROW = ((0.0, 0.0), (0.0, 21.0), (5.2, 16.4), (8.9, 24.6), (12.8, 22.8), (9.1, 14.9), (15.6, 14.8))
_RIPPLE_SECONDS = 0.45


def _arrow_points(x, y, dx=0.0, dy=0.0, ox=0.0, oy=0.0):
    """Arrow outline in real-pixel sub-pixel units (x16), shifted by (dx, dy) logical px and
    by (-ox, -oy) real px (to draw into a sub-region)."""
    S = gfx.SCALE
    return np.array([(round(((x + dx + px) * S - ox) * 16), round(((y + dy + py) * S - oy) * 16))
                     for px, py in _ARROW], np.int32)


def draw_cursor(frame, pos, now, accent, click=None):
    """Draw the game's mouse pointer.

    A white arrow with a dark inner outline (readable on any camera picture) and a soft
    halo in the theme's accent colour that breathes gently.  `click` = (x, y, time) of
    the last click: an accent ring expands from it for a moment."""
    mx, my = pos
    if mx < 0 or my < 0 or mx >= WINDOW_WIDTH or my >= WINDOW_HEIGHT:
        return
    S = gfx.SCALE
    fh, fw = frame.shape[:2]

    # --- click ripple: an accent ring that expands and fades ---------------------------------
    if click is not None:
        cx, cy, t0 = click
        age = now - t0
        if 0 <= age < _RIPPLE_SECONDS and cx >= 0:
            u = age / _RIPPLE_SECONDS
            r = 6 + 30 * ease_out(u)
            rows, cols = _roi(frame, cx - r - 6, cy - r - 6, 2 * r + 12, 2 * r + 12)
            roi = frame[rows, cols]
            if roi.size:
                ov = roi.copy()
                c = (round(cx * S - cols.start), round(cy * S - rows.start))
                _cv.circle(ov, c, max(1, round(r * S)), accent, max(1, round((3.2 - 1.8 * u) * S)), _cv.LINE_AA)
                _cv.addWeighted(ov, 0.85 * (1 - u), roi, 1 - 0.85 * (1 - u), 0, dst=roi)

    # --- soft drop shadow (blended, only the pointer's own area) ------------------------------
    rows, cols = _roi(frame, mx - 8, my - 8, 36, 44)
    roi = frame[rows, cols]
    if roi.size:
        ov = roi.copy()
        ox, oy = cols.start, rows.start
        _cv.fillPoly(ov, [_arrow_points(mx, my, 1.8, 2.6, ox, oy)], (0, 0, 0), _cv.LINE_AA, 4)
        _cv.addWeighted(ov, 0.40, roi, 0.60, 0, dst=roi)

    # --- halo -> dark outline -> white body --------------------------------------------------
    pts = _arrow_points(mx, my)
    breathe = 0.5 + 0.5 * math.sin(now * 3.0)
    halo = mix((24, 20, 18), accent, 0.62 + 0.38 * breathe)
    _cv.polylines(frame, [pts], True, halo, max(2, round((4.4 + 0.9 * breathe) * S)), _cv.LINE_AA, 4)
    _cv.polylines(frame, [pts], True, (26, 20, 18), max(1, round(2.6 * S)), _cv.LINE_AA, 4)
    _cv.fillPoly(frame, [pts], (252, 252, 252), _cv.LINE_AA, 4)
