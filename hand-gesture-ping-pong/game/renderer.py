"""Renderer: all OpenCV drawing functions for game objects and visual effects."""

import cv2
import numpy as np
import math
from game.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, BALL_RADIUS, PADDLE_WIDTH,
    LEFT_PADDLE_X, RIGHT_PADDLE_X, TRAIL_LENGTH,
    HIT_FLASH_DURATION, SHOCKWAVE_DURATION, SHOCKWAVE_MAX_RADIUS,
    FLOATING_TEXT_DURATION, FLOATING_TEXT_SPEED, COMBO_DISPLAY_DURATION,
    POWERUP_TYPES, POWERUP_RADIUS, GLOW_DOWNSCALE,
    GAME_MODE_NAMES, TIME_ATTACK_DURATION,
    get_powerup_color,
)
from game.utils import scale_color, brighten_color


# ===================================================================
#  PRE-COMPUTED OVERLAYS  (created once at startup)
# ===================================================================

def create_scanline_overlay():
    """Create a subtle CRT scanline overlay."""
    overlay = np.zeros((WINDOW_HEIGHT, WINDOW_WIDTH, 3), dtype=np.uint8)
    for y in range(0, WINDOW_HEIGHT, 3):
        overlay[y, :] = [6, 6, 6]
    return overlay


def create_vignette():
    """Create a corner-darkening vignette overlay."""
    Y, X = np.ogrid[:WINDOW_HEIGHT, :WINDOW_WIDTH]
    cx, cy = WINDOW_WIDTH / 2.0, WINDOW_HEIGHT / 2.0
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
    cv2.rectangle(frame, (x + radius, y), (x + w - radius, y + h), color, -1)
    cv2.rectangle(frame, (x, y + radius), (x + w, y + h - radius), color, -1)
    cv2.circle(frame, (x + radius, y + radius), radius, color, -1)
    cv2.circle(frame, (x + w - radius, y + radius), radius, color, -1)
    cv2.circle(frame, (x + radius, y + h - radius), radius, color, -1)
    cv2.circle(frame, (x + w - radius, y + h - radius), radius, color, -1)


def draw_overlay(frame, alpha=0.5):
    """Draw a semi-transparent dark overlay over the frame (in-place)."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (WINDOW_WIDTH, WINDOW_HEIGHT), (0, 0, 0), -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def draw_arcade_text(frame, text, cx, y, scale, color, thickness=3, shadow=True):
    """Center-aligned bold arcade text with layered shadow + glow effect.

    Achieves a chunky neon look by rendering the same text four times:
    black drop-shadow, wide dim halo, solid fill, bright inner highlight.
    """
    font = cv2.FONT_HERSHEY_DUPLEX
    (tw, _), _ = cv2.getTextSize(text, font, scale, thickness)
    x = cx - tw // 2
    if shadow:
        cv2.putText(frame, text, (x + 3, y + 4), font, scale, (0, 0, 0), thickness + 6)
    cv2.putText(frame, text, (x, y), font, scale, scale_color(color, 0.22), thickness + 12)
    cv2.putText(frame, text, (x, y), font, scale, scale_color(color, 0.55), thickness + 5)
    cv2.putText(frame, text, (x, y), font, scale, color, thickness)
    cv2.putText(frame, text, (x, y), font, scale, brighten_color(color, 70), max(1, thickness - 2))


def draw_panel(frame, x, y, w, h, border_color, fill=(12, 12, 20), alpha=0.80, radius=10):
    """Semi-transparent rounded panel with a three-layer neon border."""
    overlay = frame.copy()
    draw_rounded_rect(overlay, x, y, w, h, fill, radius)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.rectangle(frame, (x - 2, y - 2), (x + w + 2, y + h + 2),
                  scale_color(border_color, 0.28), 5)
    cv2.rectangle(frame, (x, y), (x + w, y + h), border_color, 2)
    cv2.rectangle(frame, (x + 1, y + 1), (x + w - 1, y + h - 1),
                  brighten_color(border_color, 55), 1)


def draw_neon_line(frame, x1, y1, x2, y2, color, thickness=2):
    """Neon line with outer glow halo and bright core."""
    cv2.line(frame, (x1, y1), (x2, y2), scale_color(color, 0.20), thickness + 6)
    cv2.line(frame, (x1, y1), (x2, y2), color, thickness)
    cv2.line(frame, (x1, y1), (x2, y2), brighten_color(color, 60), max(1, thickness - 1))


# ===================================================================
#  NEON GLOW HELPERS
# ===================================================================

def _draw_to_glow(glow_layer, center, radius, color):
    """Draw a circular glow source."""
    cv2.circle(glow_layer, center, radius + 4, color, -1)


def _draw_rect_to_glow(glow_layer, x, y, w, h, color):
    """Draw a rectangular glow source."""
    cv2.rectangle(glow_layer, (x - 2, y - 2), (x + w + 2, y + h + 2), color, -1)


def apply_glow(frame, glow_layer):
    """Blur the glow layer and additively composite onto the frame."""
    small_w = WINDOW_WIDTH // GLOW_DOWNSCALE
    small_h = WINDOW_HEIGHT // GLOW_DOWNSCALE
    small = cv2.resize(glow_layer, (small_w, small_h))
    blurred = cv2.GaussianBlur(small, (15, 15), 0)
    blurred_full = cv2.resize(blurred, (WINDOW_WIDTH, WINDOW_HEIGHT))
    cv2.add(frame, blurred_full, frame)


# ===================================================================
#  ANIMATED BACKGROUND
# ===================================================================

def draw_animated_bg(frame, state, theme):
    """Dark overlay + slowly-scrolling grid lines."""
    draw_overlay(frame, 0.55)

    grid_color = theme["bg_grid"]
    spacing = 60
    offset = int(state.bg_offset) % spacing

    # Vertical lines (scrolling)
    for x in range(-spacing + offset, WINDOW_WIDTH + spacing, spacing):
        cv2.line(frame, (x, 0), (x, WINDOW_HEIGHT), grid_color, 1)

    # Horizontal lines (static)
    for y in range(0, WINDOW_HEIGHT, spacing):
        cv2.line(frame, (0, y), (WINDOW_WIDTH, y), grid_color, 1)


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
        cv2.line(frame, (cx, y), (cx, min(y + dash, WINDOW_HEIGHT)), court_color, 2)
        y += dash + gap

    # Center circle
    cv2.circle(frame, (cx, WINDOW_HEIGHT // 2), 50, court_color, 2)

    # Top / bottom border glow
    border_color = scale_color(theme["court"], 0.3)
    cv2.line(frame, (0, 2), (WINDOW_WIDTH, 2), border_color, 2)
    cv2.line(frame, (0, WINDOW_HEIGHT - 2), (WINDOW_WIDTH, WINDOW_HEIGHT - 2),
             border_color, 2)


# ===================================================================
#  BALL
# ===================================================================

def draw_paused_balls(frame, state, theme):
    """Draw balls in PAUSED state — frozen snapshot with no trails or glow."""
    for ball in state.balls:
        if ball.alive:
            cv2.circle(frame, (int(ball.x), int(ball.y)), BALL_RADIUS, theme["ball"], -1)


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
        if not ball.is_main:
            color = scale_color(color, 0.7)

        center = (int(ball.x), int(ball.y))

        # Glow layers (outer → inner)
        cv2.circle(frame, center, BALL_RADIUS + 12, scale_color(color, 0.10), -1)
        cv2.circle(frame, center, BALL_RADIUS + 7,  scale_color(color, 0.20), -1)
        cv2.circle(frame, center, BALL_RADIUS + 3,  scale_color(color, 0.35), -1)
        # Core
        cv2.circle(frame, center, BALL_RADIUS, color, -1)
        # Highlight
        cv2.circle(frame, center, max(1, BALL_RADIUS - 6),
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
        if not ball.is_main:
            color = scale_color(color, 0.5)

        # Dot trail
        for i, pos in enumerate(ball.trail):
            alpha = (i + 1) / len(ball.trail)
            r = max(2, int(BALL_RADIUS * alpha * 0.6))
            cv2.circle(frame, (int(pos[0]), int(pos[1])),
                       r, scale_color(color, alpha * 0.4), -1)

        # Speed lines at high velocity
        speed = math.sqrt(ball.vx ** 2 + ball.vy ** 2)
        if speed > 500 and len(ball.trail) >= 3:
            for i in range(max(0, len(ball.trail) - 4), len(ball.trail) - 1):
                p1 = (int(ball.trail[i][0]), int(ball.trail[i][1]))
                p2 = (int(ball.trail[i + 1][0]), int(ball.trail[i + 1][1]))
                a = (i + 1) / len(ball.trail)
                cv2.line(frame, p1, p2, scale_color(color, a * 0.3), 2)


# ===================================================================
#  PADDLES
# ===================================================================

def draw_paddles(frame, state, theme, glow_layer=None):
    """Draw both paddles with neon glow."""
    _draw_neon_paddle(frame, LEFT_PADDLE_X, int(state.left_paddle_y),
                      PADDLE_WIDTH, state.left_paddle_height,
                      theme["left_paddle"], glow_layer)
    _draw_neon_paddle(frame, RIGHT_PADDLE_X - PADDLE_WIDTH, int(state.right_paddle_y),
                      PADDLE_WIDTH, state.right_paddle_height,
                      theme["right_paddle"], glow_layer)


def _draw_neon_paddle(frame, x, y, w, h, color, glow_layer=None):
    """Draw a single paddle with outer glow + inner highlight."""
    # Outer glow
    g = 6
    cv2.rectangle(frame, (x - g, y - g), (x + w + g, y + h + g),
                  scale_color(color, 0.15), -1)
    g2 = 3
    cv2.rectangle(frame, (x - g2, y - g2), (x + w + g2, y + h + g2),
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
        cv2.circle(frame, (sw.x, sw.y), radius,
                   scale_color(sw.color, alpha * 0.6), thickness)


def draw_particles(frame, state):
    """Draw all active particles."""
    for p in state.particles:
        alpha = max(0, p["life"] / p["max_life"])
        r = max(1, int(p["radius"] * alpha))
        cv2.circle(frame, (int(p["x"]), int(p["y"])),
                   r, scale_color(p["color"], alpha), -1)


def draw_floating_texts(frame, state):
    """Draw floating score popups drifting upward."""
    for ft in state.floating_texts:
        elapsed = state.current_time - ft.start_time
        progress = elapsed / FLOATING_TEXT_DURATION
        if progress >= 1:
            continue
        alpha = 1.0 - progress
        y_off = int(FLOATING_TEXT_SPEED * elapsed)
        pos = (int(ft.x) - 15, int(ft.y) - y_off)
        cv2.putText(frame, ft.text, pos,
                    cv2.FONT_HERSHEY_DUPLEX, 1.2,
                    scale_color(ft.color, alpha), 3)


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
        cv2.circle(frame, center, radius + 8, scale_color(color, 0.15), -1)
        cv2.circle(frame, center, radius + 4, scale_color(color, 0.30), -1)
        cv2.circle(frame, center, radius, color, -1)
        cv2.circle(frame, center, max(1, radius - 6),
                   brighten_color(color, 60), -1)

        # Label
        label = info["label"]
        ts = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        tx = int(pu.x) - ts[0] // 2
        ty = int(pu.y) + ts[1] // 2
        cv2.putText(frame, label, (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)


# ===================================================================
#  OBSTACLES
# ===================================================================

def draw_obstacles(frame, state, theme):
    """Draw obstacle blocks with border glow."""
    for obs in state.obstacles:
        c = theme["obstacle"]
        ix, iy = int(obs.x), int(obs.y)
        # Glow
        cv2.rectangle(frame, (ix - 3, iy - 3),
                      (ix + obs.w + 3, iy + obs.h + 3),
                      scale_color(c, 0.3), -1)
        # Core
        cv2.rectangle(frame, (ix, iy),
                      (ix + obs.w, iy + obs.h), c, -1)
        # Border
        cv2.rectangle(frame, (ix, iy),
                      (ix + obs.w, iy + obs.h),
                      brighten_color(c, 60), 2)


# ===================================================================
#  HUD
# ===================================================================

def _draw_powerup_pills(frame, state, theme):
    """Active power-up status as colored pills with depleting timer bars."""
    t = state.current_time
    items = []
    for ptype, exp_t in state.active_effects.items():
        rem = exp_t - t
        if rem <= 0:
            continue
        base = ptype.replace("_left", "").replace("_right", "")
        info = POWERUP_TYPES.get(base, {})
        items.append((
            info.get("label", base[:3].upper()),
            rem,
            info.get("duration", 5.0),
            get_powerup_color(theme, base),
        ))

    pill_w, pill_h = 115, 26
    px0 = WINDOW_WIDTH - pill_w - 8
    for i, (label, rem, dur, color) in enumerate(items):
        py = 92 + i * (pill_h + 6)
        ov = frame.copy()
        cv2.rectangle(ov, (px0, py), (px0 + pill_w, py + pill_h),
                      scale_color(color, 0.18), -1)
        cv2.addWeighted(ov, 0.72, frame, 0.28, 0, frame)
        cv2.rectangle(frame, (px0, py), (px0 + pill_w, py + pill_h),
                      scale_color(color, 0.65), 1)
        bar_w = max(0, int((pill_w - 4) * rem / dur))
        if bar_w > 0:
            cv2.rectangle(frame,
                          (px0 + 2, py + pill_h - 5),
                          (px0 + 2 + bar_w, py + pill_h - 2),
                          color, -1)
        cv2.putText(frame, f"{label}  {rem:.1f}s",
                    (px0 + 6, py + 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.43, color, 1)


def draw_hud(frame, state, theme):
    """Draw in-game HUD: arcade scores, player labels, flash, mode info, power-up pills."""
    mode = state.settings["game_mode"]
    cx = WINDOW_WIDTH // 2
    t = state.current_time
    _FLASH_DUR = 0.5

    if mode == 1:                                      # Survival
        draw_arcade_text(frame, f"RALLY  {state.survival_rally}",
                         cx, 68, 1.8, (0, 255, 255), thickness=3)
    else:
        lx, rx = WINDOW_WIDTH // 4, 3 * WINDOW_WIDTH // 4   # 300, 900
        lc, rc = theme["left_paddle"], theme["right_paddle"]

        l_flash = max(0.0, 1.0 - (t - state.score_flash_time[0]) / _FLASH_DUR)
        r_flash = max(0.0, 1.0 - (t - state.score_flash_time[1]) / _FLASH_DUR)

        l_col = brighten_color(lc, int(l_flash * 130)) if l_flash > 0 else lc
        r_col = brighten_color(rc, int(r_flash * 130)) if r_flash > 0 else rc

        # Scores — scale and thickness pulse on flash
        draw_arcade_text(frame, str(state.score[0]), lx, 65,
                         2.2 + l_flash * 0.8, l_col,
                         thickness=3 + int(l_flash * 2))
        draw_arcade_text(frame, str(state.score[1]), rx, 65,
                         2.2 + r_flash * 0.8, r_col,
                         thickness=3 + int(r_flash * 2))

        # P1 / P2 labels — below score baseline
        p2_label = "AI" if state.settings["ai_enabled"] else "P2"
        draw_arcade_text(frame, "P1", lx, 88, 0.52,
                         scale_color(lc, 0.68), thickness=1, shadow=False)
        draw_arcade_text(frame, p2_label, rx, 88, 0.52,
                         scale_color(rc, 0.68), thickness=1, shadow=False)

        # Center: VS divider (Classic) or countdown timer (Time Attack)
        if mode == 2:
            elapsed = t - state.play_start_time
            remaining = max(0, TIME_ATTACK_DURATION - elapsed)
            mins = int(remaining) // 60
            secs = int(remaining) % 60
            tc_col = (0, 0, 255) if remaining < 10 else (0, 200, 255)
            draw_arcade_text(frame, f"{mins}:{secs:02d}",
                             cx, 68, 1.6, tc_col, thickness=3)
        else:
            cv2.putText(frame, "VS", (cx - 14, 62),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (55, 55, 55), 1)

    # Mode label + win condition (bottom center)
    (tw, _), _ = cv2.getTextSize(GAME_MODE_NAMES[mode],
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.putText(frame, GAME_MODE_NAMES[mode],
                (cx - tw // 2, WINDOW_HEIGHT - 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (110, 110, 110), 1)
    if mode == 0:
        label = f"First to {state.settings['score_to_win']}"
        (tw2, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
        cv2.putText(frame, label, (cx - tw2 // 2, WINDOW_HEIGHT - 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (90, 90, 90), 1)

    _draw_powerup_pills(frame, state, theme)


def draw_global_hud(frame, fps_display):
    """Draw FPS counter (top-left) and controls hint (dark bottom strip)."""
    cv2.putText(frame, f"FPS:{int(fps_display)}", (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 150, 0), 1)

    hint = "ESC: Menu  |  F: Fullscreen  |  P: Pause  |  M: Settings"
    (tw, _), _ = cv2.getTextSize(hint, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
    ov = frame.copy()
    cv2.rectangle(ov, (0, WINDOW_HEIGHT - 20), (WINDOW_WIDTH, WINDOW_HEIGHT),
                  (0, 0, 0), -1)
    cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, hint,
                (WINDOW_WIDTH // 2 - tw // 2, WINDOW_HEIGHT - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (75, 75, 75), 1)


# ===================================================================
#  HAND SKELETONS
# ===================================================================

def draw_hand_skeletons(frame, state, hand_connections):
    """Draw MediaPipe hand landmarks and connections."""
    h, w = frame.shape[:2]
    for side in ("Left", "Right"):
        lm = state.hand_landmarks.get(side)
        if lm is None:
            continue
        points = [(int(l.x * w), int(l.y * h)) for l in lm.landmark]
        color = (255, 200, 0) if side == "Left" else (0, 200, 255)
        for conn in hand_connections:
            cv2.line(frame, points[conn[0]], points[conn[1]], color, 2)
        for pt in points:
            cv2.circle(frame, pt, 4, (255, 255, 255), -1)


# ===================================================================
#  POST-PROCESSING
# ===================================================================

def draw_mouse_cursor(frame, mouse_pos, current_time=0.0):
    """Draw an animated neon game-style arrow cursor.

    Classic pointer shape with a pulsing glow and bright tip hotspot.
    Tip (hotspot) is at mouse_pos.
    """
    mx, my = mouse_pos
    if mx < 0 or mx >= WINDOW_WIDTH or my < 0 or my >= WINDOW_HEIGHT:
        return

    # abs(sin) gives a smooth 0→1→0 breathe rather than negative dips
    pulse = 0.55 + 0.45 * abs(math.sin(current_time * 3.0))

    # Classic pointer polygon — 7 points, tip at origin
    #   Left edge goes straight down → diagonal notch → shaft → arrowhead right
    pts = np.array([
        [ 0,  0],   # tip (hotspot)
        [ 0, 16],   # left edge, bottom
        [ 4, 11],   # elbow notch (inner corner)
        [ 4, 20],   # tail, bottom-left
        [ 8, 20],   # tail, bottom-right
        [ 8, 11],   # tail, top-right
        [13, 11],   # arrowhead, outer right
    ], dtype=np.int32) + np.array([[mx, my]])

    # 1 — black drop shadow (shift 2,2)
    cv2.fillPoly(frame, [pts + np.array([[2, 2]])], (0, 0, 0))

    # 2 — two outer glow halos, expanded around the polygon centroid
    c = pts.mean(axis=0)
    for expand, dim in ((1.65, 0.09), (1.28, 0.22)):
        g = (c + (pts - c) * expand).astype(np.int32)
        cv2.fillPoly(frame, [g],
                     (0, int(255 * dim * pulse), int(200 * dim * pulse)))

    # 3 — dark body fill (keeps outline readable)
    cv2.fillPoly(frame, [pts], (0, int(40 * pulse), int(32 * pulse)))

    # 4 — neon outline
    cv2.polylines(frame, [pts], True,
                  (0, int(210 + 45 * pulse), int(165 + 35 * pulse)), 1)

    # 5 — bright rim on the two lit edges of the arrowhead
    rim = (0, int(160 + 95 * pulse), int(125 + 75 * pulse))
    cv2.line(frame, (mx, my), (mx,      my + 16), rim, 1)
    cv2.line(frame, (mx, my), (mx + 13, my + 11), scale_color(rim, 0.7), 1)

    # 6 — pulsing tip: glow ring → neon dot → white hotspot
    gr = 2 + int(2 * pulse)   # glow radius breathes 3 → 4 px
    cv2.circle(frame, (mx, my), gr, (0, int(180 * pulse), int(140 * pulse)), -1)
    cv2.circle(frame, (mx, my), 2,  (0, int(255 * pulse), int(200 * pulse)), -1)
    cv2.circle(frame, (mx, my), 1,  (255, 255, 255), -1)


def apply_post_processing(frame, scanline_overlay, vignette_overlay):
    """Apply scanlines and vignette (in-place subtract)."""
    cv2.subtract(frame, scanline_overlay, frame)
    cv2.subtract(frame, vignette_overlay, frame)
