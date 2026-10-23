"""Renderer: all OpenCV drawing functions for game objects and visual effects."""

import numpy as np
import math
from PIL import Image, ImageDraw, ImageFilter
from game import font as _font
from game import gfx
import cv2 as _cv                # real cv2: pixel-space operations and constants
from game.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, BALL_RADIUS, PADDLE_WIDTH, LEFT_PADDLE_X, RIGHT_PADDLE_X,
    HIT_FLASH_DURATION, SHOCKWAVE_DURATION, SHOCKWAVE_MAX_RADIUS, FLOATING_TEXT_DURATION,
    FLOATING_TEXT_SPEED, COMBO_DISPLAY_DURATION, POWERUP_TYPES, POWERUP_RADIUS, GLOW_DOWNSCALE,
    PADDLE_FLASH_SECONDS, get_powerup_color,
)
from game.utils import scale_color, brighten_color


# ===================================================================
#  PRE-COMPUTED OVERLAYS  (created once at startup)
# ===================================================================

def create_scanline_overlay():
    """Create a subtle CRT scanline overlay."""
    w, h = gfx.frame_size()
    overlay = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(0, h, max(2, gfx.px(3))):
        overlay[y, :] = [6, 6, 6]
    return overlay


def create_vignette():
    """Create a corner-darkening vignette overlay."""
    w, h = gfx.frame_size()
    Y, X = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    dx = (X.astype(np.float32) - cx) / cx
    dy = (Y.astype(np.float32) - cy) / cy
    d = np.sqrt(dx * dx + dy * dy)
    v = np.clip(d * 0.25, 0, 1)
    v_u8 = (v * 25).astype(np.uint8)
    return np.dstack([v_u8, v_u8, v_u8])


# ===================================================================
#  BASIC DRAWING HELPERS
# ===================================================================

def draw_rounded_rect(frame, x, y, w, h, color, radius=10):
    """Draw a filled rounded rectangle."""
    gfx.rectangle(frame, (x + radius, y), (x + w - radius, y + h), color, -1)
    gfx.rectangle(frame, (x, y + radius), (x + w, y + h - radius), color, -1)
    gfx.circle(frame, (x + radius, y + radius), radius, color, -1)
    gfx.circle(frame, (x + w - radius, y + radius), radius, color, -1)
    gfx.circle(frame, (x + radius, y + h - radius), radius, color, -1)
    gfx.circle(frame, (x + w - radius, y + h - radius), radius, color, -1)


def draw_overlay(frame, alpha=0.5):
    """Draw a semi-transparent dark overlay over the frame (in-place)."""
    # Blending with black is just darkening: scale the frame in place
    _cv.convertScaleAbs(frame, dst=frame, alpha=1.0 - alpha)


def _scale_to_px(scale: float) -> int:
    """Map legacy cv2 scale float → Press Start 2P pixel size.

    A continuous formula rather than a coarse bucket table: pulsing/animated
    scale values (combo pop, countdown beat, score-flash growth) now render
    at a genuinely different size each step instead of several distinct
    inputs collapsing onto the same fixed pixel size."""
    return max(6, round(scale * 15 + 3))


_TEXT_CACHE: dict = {}
_CACHE_LIMIT = 300


def _cache_put(cache: dict, key, value) -> None:
    if len(cache) >= _CACHE_LIMIT:
        del cache[next(iter(cache))]
    cache[key] = value


def _prep_tile(arr):
    """RGBA text image -> (BGR pixels, alpha weights, 1-alpha weights), computed
    once when the text is cached so drawing it is a single blend call."""
    a = arr[:, :, 3].astype(np.float32) * (1.0 / 255.0)
    return np.ascontiguousarray(arr[:, :, 2::-1]), a, 1.0 - a


def _composite(frame, tile, fx: int, fy: int) -> None:
    """Alpha-composite a prepared text tile (see _prep_tile) onto the frame in place."""
    bgr, wa, wb = tile
    h_f, w_f = frame.shape[:2]
    th, tw = wa.shape
    sx1 = max(0, -fx);         sy1 = max(0, -fy)
    ex  = min(fx + tw, w_f)
    ey  = min(fy + th, h_f)
    if ex <= max(0, fx) or ey <= max(0, fy):
        return
    sx2 = sx1 + ex - max(0, fx)
    sy2 = sy1 + ey - max(0, fy)
    fx1, fy1 = max(0, fx), max(0, fy)
    if (sx1, sy1, sx2, sy2) != (0, 0, tw, th):          # clipped at a frame edge
        bgr = np.ascontiguousarray(bgr[sy1:sy2, sx1:sx2])
        wa = np.ascontiguousarray(wa[sy1:sy2, sx1:sx2])
        wb = np.ascontiguousarray(wb[sy1:sy2, sx1:sx2])
    roi = frame[fy1:ey, fx1:ex]
    roi[:] = _cv.blendLinear(bgr, np.ascontiguousarray(roi), wa, wb)


def draw_arcade_text(frame, text, cx, y, scale, color, thickness=3, shadow=True):
    """Center-aligned Press Start 2P text with neon glow.  y = baseline.

    thickness > 3 adds a pixel stroke around the glyph for extra boldness
    (e.g. titles, score-flash emphasis); thickness <= 3 is normal weight.
    """
    S   = gfx.SCALE
    px  = max(6, round(_scale_to_px(scale) * S))     # glyphs are re-rendered at native size
    r, g, b = color[2], color[1], color[0]          # BGR → RGB
    stroke = max(0, round((int(thickness) - 3) * S)) if int(thickness) > 3 else 0

    key = (text, px, r, g, b, shadow, stroke, round(S * 100))
    if key not in _TEXT_CACHE:
        fnt  = _font.get(px)
        bbox = fnt.getbbox(text)                     # (x0, y0, x1, y1)
        tw   = bbox[2] - bbox[0]
        th   = bbox[3] - bbox[1]
        pad  = round(7 * S) + stroke
        sw, sh = tw + pad * 2, th + pad * 2

        # Silhouette mask for glow layers (stroke widens the glyph)
        sil = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(sil).text(
            (pad - bbox[0], pad - bbox[1]), text, font=fnt, fill=255,
            stroke_width=stroke, stroke_fill=255)

        surf = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))

        if shadow:
            sh_mask = Image.new("L", (sw, sh), 0)
            ImageDraw.Draw(sh_mask).text(
                (pad - bbox[0] + max(1, round(2 * S)), pad - bbox[1] + max(1, round(3 * S))),
                text, font=fnt, fill=160)
            sh_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 255))
            sh_layer.putalpha(sh_mask)
            surf = Image.alpha_composite(surf, sh_layer)

        # Outer glow (large blur, very dim)
        g1 = Image.new("RGBA", (sw, sh), (r // 5, g // 5, b // 5, 255))
        g1.putalpha(sil.filter(ImageFilter.GaussianBlur(5 * S)))
        surf = Image.alpha_composite(surf, g1)

        # Mid glow
        g2 = Image.new("RGBA", (sw, sh), (r // 2, g // 2, b // 2, 255))
        g2.putalpha(sil.filter(ImageFilter.GaussianBlur(2 * S)))
        surf = Image.alpha_composite(surf, g2)

        # Main fill
        fill = Image.new("RGBA", (sw, sh), (r, g, b, 255))
        fill.putalpha(sil)
        surf = Image.alpha_composite(surf, fill)

        tile = _prep_tile(np.array(surf))
        _cache_put(_TEXT_CACHE, key, (tile, tw, th, pad))
    else:
        tile, tw, th, pad = _TEXT_CACHE[key]

    # y is baseline; top of glyph = y - th; subtract pad for surface origin
    _composite(frame, tile, round(cx * S) - tw // 2 - pad, round(y * S) - th - pad)


# ===================================================================
#  NEON GLOW HELPERS
# ===================================================================

# The bloom is drawn on a small layer (logical size / GLOW_DOWNSCALE, i.e. 320x180
# whatever the render resolution), and only the areas that actually contain
# glow sources are blurred, up-scaled and added.  Previously the whole frame was
# down-scaled, blurred, up-scaled and added every frame - the single most
# expensive step at 1080p.
_GLOW_INV = 1.0 / GLOW_DOWNSCALE
_GLOW_MARGIN = 8                 # blur kernel 15 reaches 7 px beyond a source
_glow_boxes = []                 # glow-layer areas drawn into this frame
_glow_up = {}                    # reusable up-scale buffers


def create_glow_layer():
    return np.zeros((WINDOW_HEIGHT // GLOW_DOWNSCALE, WINDOW_WIDTH // GLOW_DOWNSCALE, 3), np.uint8)


def _draw_to_glow(glow_layer, center, radius, color):
    """Draw a circular glow source (logical coordinates)."""
    g = _GLOW_INV
    cx, cy, r = center[0] * g, center[1] * g, (radius + 4) * g
    _cv.circle(glow_layer, (round(cx), round(cy)), max(1, round(r)), color, -1)
    _glow_boxes.append((cx - r, cy - r, cx + r, cy + r))


def _draw_rect_to_glow(glow_layer, x, y, w, h, color):
    """Draw a rectangular glow source (logical coordinates)."""
    g = _GLOW_INV
    x0, y0, x1, y1 = (x - 2) * g, (y - 2) * g, (x + w + 2) * g, (y + h + 2) * g
    _cv.rectangle(glow_layer, (round(x0), round(y0)), (round(x1), round(y1)), color, -1)
    _glow_boxes.append((x0, y0, x1, y1))


def _merge_boxes(boxes):
    """Union overlapping boxes so no area gets its glow added twice."""
    merged = True
    while merged:
        merged = False
        out = []
        for b in boxes:
            for o in out:
                if b[0] < o[2] and o[0] < b[2] and b[1] < o[3] and o[1] < b[3]:
                    o[0], o[1] = min(o[0], b[0]), min(o[1], b[1])
                    o[2], o[3] = max(o[2], b[2]), max(o[3], b[3])
                    merged = True
                    break
            else:
                out.append(list(b))
        boxes = out
    return boxes


def apply_glow(frame, glow_layer):
    """Blur the glow sources drawn this frame and add them onto the frame."""
    if not _glow_boxes:
        return
    gh, gw = glow_layer.shape[:2]
    fh, fw = frame.shape[:2]
    sx, sy = fw / gw, fh / gh
    m = _GLOW_MARGIN
    boxes = []
    for x0, y0, x1, y1 in _glow_boxes:
        b = [max(0, int(x0) - m), max(0, int(y0) - m),
             min(gw, int(x1) + m + 1), min(gh, int(y1) + m + 1)]
        if b[2] > b[0] and b[3] > b[1]:
            boxes.append(b)
    _glow_boxes.clear()
    for x0, y0, x1, y1 in _merge_boxes(boxes):
        blurred = _cv.GaussianBlur(glow_layer[y0:y1, x0:x1], (15, 15), 0,
                                   borderType=_cv.BORDER_CONSTANT)
        X0, Y0 = round(x0 * sx), round(y0 * sy)
        X1, Y1 = min(fw, round(x1 * sx)), min(fh, round(y1 * sy))
        if X1 <= X0 or Y1 <= Y0:
            continue
        size = (X1 - X0, Y1 - Y0)
        up = _glow_up.get(size)
        if up is None:
            up = _glow_up[size] = np.empty((size[1], size[0], 3), np.uint8)
            if len(_glow_up) > 64:
                _glow_up.clear()
                _glow_up[size] = up
        _cv.resize(blurred, size, dst=up, interpolation=_cv.INTER_LINEAR)
        roi = frame[Y0:Y1, X0:X1]
        _cv.add(roi, up, dst=roi)


# ===================================================================
#  ANIMATED BACKGROUND
# ===================================================================

# The camera picture is darkened to 45% (it used to be a 55% black overlay drawn
# here every frame).  That is now done while copying the camera frame into the
# render buffer: one pass over the pixels instead of a copy plus a darken pass.
_BG_BRIGHTNESS = 0.45


def prepare_background(camera_frame, dst):
    """Copy the camera frame into the render buffer, darkened for the background."""
    _cv.convertScaleAbs(camera_frame, dst=dst, alpha=_BG_BRIGHTNESS)


_backdrop_cache = {}


def prepare_plain_background(dst):
    """Camera picture switched off: a dark, softly vignetted backdrop instead."""
    key = dst.shape
    bg = _backdrop_cache.get(key)
    if bg is None:
        import numpy as np
        h, w = key[:2]
        yy = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
        xx = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
        v = 1.0 - 0.45 * np.minimum(1.0, xx * xx * 0.6 + yy * yy * 0.9)
        base = np.array([30, 24, 20], np.float32)          # BGR, a deep blue-black
        bg = (v[:, :, None] * base).astype(np.uint8)
        _backdrop_cache.clear()
        _backdrop_cache[key] = bg
    dst[:] = bg


def draw_animated_bg(frame, state, theme):
    """Slowly-scrolling grid over the (already darkened, see prepare_background)
    camera picture.  Grid lines are full-length, axis-aligned and 1 logical px
    wide, so they are written as array slices rather than gfx.line calls."""
    grid_color = theme["bg_grid"]
    spacing = 60
    offset = int(state.bg_offset) % spacing
    S = gfx.SCALE
    h, w = frame.shape[:2]
    t = max(1, round(S))

    # Vertical lines (scrolling)
    for x in range(-spacing + offset, WINDOW_WIDTH + spacing, spacing):
        X = round(x * S)
        x0, x1 = max(0, X), min(w, X + t)
        if x1 > x0:
            frame[:, x0:x1] = grid_color

    # Horizontal lines (static)
    for y in range(0, WINDOW_HEIGHT, spacing):
        Y = round(y * S)
        frame[Y:Y + t, :] = grid_color


# ===================================================================
#  COURT
# ===================================================================

def draw_court(frame, state, theme, glow_layer=None):
    """Draw center dashed line, center circle, and border lines."""
    cx = WINDOW_WIDTH // 2
    court_color = scale_color(theme["court"], 0.5)

    # Dashed center line
    dash, gap = 20, 15
    y = 0
    while y < WINDOW_HEIGHT:
        gfx.line(frame, (cx, y), (cx, min(y + dash, WINDOW_HEIGHT)), court_color, 2)
        y += dash + gap

    # Center circle
    gfx.circle(frame, (cx, WINDOW_HEIGHT // 2), 50, court_color, 2)

    # Top / bottom border glow
    border_color = scale_color(theme["court"], 0.3)
    gfx.line(frame, (0, 2), (WINDOW_WIDTH, 2), border_color, 2)
    gfx.line(frame, (0, WINDOW_HEIGHT - 2), (WINDOW_WIDTH, WINDOW_HEIGHT - 2),
             border_color, 2)


# ===================================================================
#  BALL
# ===================================================================

def draw_paused_balls(frame, state, theme):
    """Draw balls in PAUSED state — frozen snapshot with no trails or glow."""
    for ball in state.balls:
        if ball.alive:
            gfx.circle(frame, (ball.x, ball.y), BALL_RADIUS, theme["ball"], -1)


def draw_balls(frame, state, theme, glow_layer=None):
    """Draw all balls with multi-layer neon glow."""
    for ball in state.balls:
        if not ball.alive:
            continue

        # Color selection
        if state.current_time - state.hit_animation_time < HIT_FLASH_DURATION:
            color = theme["ball_hit"]
        else:
            color = theme["ball"]

        center = (ball.x, ball.y)

        # Glow layers (outer → inner)
        gfx.circle(frame, center, BALL_RADIUS + 12, scale_color(color, 0.10), -1)
        gfx.circle(frame, center, BALL_RADIUS + 7,  scale_color(color, 0.20), -1)
        gfx.circle(frame, center, BALL_RADIUS + 3,  scale_color(color, 0.35), -1)
        # Core
        gfx.circle(frame, center, BALL_RADIUS, color, -1)
        # Highlight
        gfx.circle(frame, center, max(1, BALL_RADIUS - 6),
                   brighten_color(color, 60), -1)

        # Bloom on glow layer
        if glow_layer is not None:
            _draw_to_glow(glow_layer, center, BALL_RADIUS,
                          scale_color(color, 0.5))


def draw_ball_trails(frame, state, theme):
    """Draw fading trails + speed lines for all balls."""
    for ball in state.balls:
        if not ball.alive or len(ball.trail) < 2:
            continue

        if state.current_time - state.hit_animation_time < HIT_FLASH_DURATION:
            color = theme["ball_hit"]
        else:
            color = theme["ball"]

        # Dot trail
        for i, pos in enumerate(ball.trail):
            alpha = (i + 1) / len(ball.trail)
            r = max(2, int(BALL_RADIUS * alpha * 0.6))
            gfx.circle(frame, pos, r, scale_color(color, alpha * 0.4), -1)

        # Speed lines at high velocity
        speed = math.sqrt(ball.vx ** 2 + ball.vy ** 2)
        if speed > 500 and len(ball.trail) >= 3:
            for i in range(max(0, len(ball.trail) - 4), len(ball.trail) - 1):
                p1, p2 = ball.trail[i], ball.trail[i + 1]
                a = (i + 1) / len(ball.trail)
                gfx.line(frame, p1, p2, scale_color(color, a * 0.3), 2)


# ===================================================================
#  PADDLES
# ===================================================================

def _flash(state, side):
    """(0..1 strength fading out, BGR hit colour) while a paddle is lit, else (0, None)."""
    f = state.paddle_flash.get(side)
    if f is None:
        return 0.0, None
    t = (state.current_time - f[0]) / PADDLE_FLASH_SECONDS
    if not 0 <= t < 1:
        return 0.0, None
    from game.effects import hit_color
    return (1 - t) ** 1.5 * f[2], hit_color(f[1] + int(t * 30))   # colour drifts as it fades


def draw_paddles(frame, state, theme, glow_layer=None):
    """Draw both paddles with neon glow; a struck paddle blazes in the hit colour."""
    lf, lc = _flash(state, "left")
    rf, rc = _flash(state, "right")
    _draw_neon_paddle(frame, LEFT_PADDLE_X, state.left_paddle_y,
                      PADDLE_WIDTH, state.left_paddle_height,
                      theme["left_paddle"], glow_layer, lf, lc)
    _draw_neon_paddle(frame, RIGHT_PADDLE_X - PADDLE_WIDTH, state.right_paddle_y,
                      PADDLE_WIDTH, state.right_paddle_height,
                      theme["right_paddle"], glow_layer, rf, rc)


def _blend(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def _draw_neon_paddle(frame, x, y, w, h, color, glow_layer=None, flash=0.0, flash_color=None):
    """Draw a single paddle with outer glow + inner highlight (flash: 0..1 hit light-up)."""
    if flash > 0:
        hot = _blend(color, flash_color, min(1.0, flash * 1.6))
        e = int(4 + 16 * flash)                              # glow swells, then settles
        gfx.rectangle(frame, (x - e, y - e), (x + w + e, y + h + e), scale_color(hot, 0.14 + 0.2 * flash), -1)
        gfx.rectangle(frame, (x - e // 2, y - e // 2), (x + w + e // 2, y + h + e // 2),
                      scale_color(hot, 0.3 + 0.3 * flash), -1)
        draw_rounded_rect(frame, x, y, w, h, hot, 8)
        if w > 8 and h > 8:
            draw_rounded_rect(frame, x + 3, y + 3, w - 6, h - 6, _blend(hot, (255, 255, 255), 0.35 + 0.55 * flash), 5)
        if glow_layer is not None:
            _draw_rect_to_glow(glow_layer, x - e // 2, y - e // 2, w + e, h + e, scale_color(hot, 0.35 + 0.5 * flash))
        return
    # Outer glow
    g = 6
    gfx.rectangle(frame, (x - g, y - g), (x + w + g, y + h + g),
                  scale_color(color, 0.15), -1)
    g2 = 3
    gfx.rectangle(frame, (x - g2, y - g2), (x + w + g2, y + h + g2),
                  scale_color(color, 0.30), -1)
    # Core
    draw_rounded_rect(frame, x, y, w, h, color, 8)
    # Inner highlight
    if w > 8 and h > 8:
        draw_rounded_rect(frame, x + 3, y + 3, w - 6, h - 6,
                          brighten_color(color, 40), 5)
    # Bloom
    if glow_layer is not None:
        _draw_rect_to_glow(glow_layer, x, y, w, h, scale_color(color, 0.4))


# ===================================================================
#  EFFECTS RENDERING
# ===================================================================

def draw_shockwaves(frame, state):
    """Draw expanding shockwave rings."""
    for sw in state.shockwaves:
        elapsed = state.current_time - sw.start_time
        progress = elapsed / SHOCKWAVE_DURATION
        if progress >= 1:
            continue
        radius = int(SHOCKWAVE_MAX_RADIUS * progress)
        alpha = 1.0 - progress
        thickness = max(1, int(3 * alpha))
        gfx.circle(frame, (sw.x, sw.y), radius,
                   scale_color(sw.color, alpha * 0.6), thickness)


def draw_particles(frame, state):
    """Draw all active particles."""
    for p in state.particles:
        alpha = max(0, p["life"] / p["max_life"])
        r = max(1, int(p["radius"] * alpha))
        gfx.circle(frame, (p["x"], p["y"]), r, scale_color(p["color"], alpha), -1)


def draw_floating_texts(frame, state):
    """Draw floating score popups drifting upward."""
    for ft in state.floating_texts:
        elapsed = state.current_time - ft.start_time
        progress = elapsed / FLOATING_TEXT_DURATION
        if progress >= 1:
            continue
        alpha_q = round((1.0 - progress) * 8) / 8   # quantise → 8 alpha levels
        y_off = int(FLOATING_TEXT_SPEED * elapsed)
        draw_arcade_text(frame, ft.text,
                         int(ft.x), int(ft.y) - y_off,
                         1.2, scale_color(ft.color, alpha_q), thickness=2)


def draw_combo(frame, state, theme):
    """Draw combo counter near the main ball with arcade styling."""
    if state.combo_count < 2:
        return
    elapsed = state.current_time - state.combo_display_time
    if elapsed > COMBO_DISPLAY_DURATION:
        return

    main_ball = next((b for b in state.balls if b.is_main), None)
    if not main_ball:
        return

    alpha = max(0, 1.0 - elapsed / COMBO_DISPLAY_DURATION)
    pulse = 1.0 + 0.15 * math.sin(state.current_time * 10)
    bx = min(max(int(main_ball.x) + 65, 80), WINDOW_WIDTH - 80)
    by = max(int(main_ball.y) - 35, 40)
    draw_arcade_text(frame, f"x{state.combo_count}", bx, by,
                     0.85 * pulse, scale_color(theme["score_popup"], alpha),
                     thickness=2)


# ===================================================================
#  POWER-UPS
# ===================================================================

def draw_powerups(frame, state, theme):
    """Draw power-up items on the court with pulsing animation."""
    for pu in state.powerups:
        info = POWERUP_TYPES[pu.type]
        color = get_powerup_color(theme, pu.type)

        # Pulse
        pulse = math.sin(state.current_time * 4 + pu.pulse_phase) * 0.2 + 1.0
        radius = int(POWERUP_RADIUS * pulse)
        center = (int(pu.x), int(pu.y))

        # Glow layers
        gfx.circle(frame, center, radius + 8, scale_color(color, 0.15), -1)
        gfx.circle(frame, center, radius + 4, scale_color(color, 0.30), -1)
        gfx.circle(frame, center, radius, color, -1)
        gfx.circle(frame, center, max(1, radius - 6),
                   brighten_color(color, 60), -1)

        # Label
        label = info["label"]
        ts = _cv.getTextSize(label, _cv.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        tx = int(pu.x) - ts[0] // 2
        ty = int(pu.y) + ts[1] // 2
        gfx.putText(frame, label, (tx, ty),
                    _cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)


# ===================================================================
#  OBSTACLES
# ===================================================================

def draw_obstacles(frame, state, theme):
    """Draw obstacle blocks with border glow."""
    for obs in state.obstacles:
        c = theme["obstacle"]
        ix, iy = int(obs.x), int(obs.y)
        # Glow
        gfx.rectangle(frame, (ix - 3, iy - 3),
                      (ix + obs.w + 3, iy + obs.h + 3),
                      scale_color(c, 0.3), -1)
        # Core
        gfx.rectangle(frame, (ix, iy),
                      (ix + obs.w, iy + obs.h), c, -1)
        # Border
        gfx.rectangle(frame, (ix, iy),
                      (ix + obs.w, iy + obs.h),
                      brighten_color(c, 60), 2)


# ===================================================================
#  HUD
# ===================================================================

# ===================================================================
#  HAND SKELETONS
# ===================================================================

def draw_hand_skeletons(frame, state, hand_connections):
    """Draw MediaPipe hand landmarks and connections."""
    w, h = WINDOW_WIDTH, WINDOW_HEIGHT      # logical space; gfx scales to the frame
    for side in ("Left", "Right"):
        lm = state.hand_landmarks.get(side)
        if lm is None:
            continue
        points = [(int(l.x * w), int(l.y * h)) for l in lm.landmark]
        color = (255, 200, 0) if side == "Left" else (0, 200, 255)
        for conn in hand_connections:
            gfx.line(frame, points[conn[0]], points[conn[1]], color, 2)
        for pt in points:
            gfx.circle(frame, pt, 4, (255, 255, 255), -1)


# ===================================================================
#  POST-PROCESSING
# ===================================================================

def create_post_overlay():
    """Scanlines + vignette merged into one overlay (a single subtract per frame)."""
    return _cv.add(create_scanline_overlay(), create_vignette())


def apply_post_processing(frame, overlay):
    """Apply the scanline/vignette overlay (in-place subtract)."""
    _cv.subtract(frame, overlay, frame)
