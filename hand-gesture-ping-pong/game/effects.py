"""Visual effects: particles, shockwaves, floating text, screen shake, combo."""

import random
import math
import cv2
import numpy as np
from game.config import (
    PARTICLE_GRAVITY, SHOCKWAVE_DURATION, FLOATING_TEXT_DURATION,
    SCREEN_SHAKE_DURATION, SCREEN_SHAKE_INTENSITY,
)
from game.state import Shockwave, FloatingText


# =================================================================
#  SPAWNING
# =================================================================

def spawn_particles(state, x, y, color, count=10):
    """Create burst of particles at position."""
    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(100, 400)
        life = random.uniform(0.2, 0.5)
        state.particles.append({
            "x": float(x), "y": float(y),
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "life": life,
            "max_life": life,  # store actual start life so alpha fades from 1.0
            "color": color,
            "radius": random.randint(2, 6),
        })


_hue_cursor = [0]


def hit_color(hue):
    """Vivid BGR colour for an OpenCV hue (0-179)."""
    return tuple(int(c) for c in cv2.cvtColor(np.uint8([[[hue % 180, 235, 255]]]), cv2.COLOR_HSV2BGR)[0, 0])


def paddle_hit(state, side, ball, speed_frac=0.5):
    """Paddle strike: the paddle lights up in a fresh colour each hit, and a fan of
    sparks in that colour sprays out the way the ball is leaving."""
    _hue_cursor[0] = (_hue_cursor[0] + 37) % 180          # every hit a different colour
    hue = _hue_cursor[0]
    strength = max(0.4, min(1.0, speed_frac))
    state.paddle_flash[side] = (state.current_time, hue, strength)
    col = hit_color(hue)
    d = 1 if side == "left" else -1                       # direction the ball leaves in
    for i in range(int(8 + 10 * strength)):
        a = random.uniform(-1.1, 1.1)
        sp = random.uniform(200, 520) * (0.7 + 0.5 * strength)
        life = random.uniform(0.25, 0.55)
        state.particles.append({
            "x": float(ball.x), "y": float(ball.y),
            "vx": math.cos(a) * sp * d, "vy": math.sin(a) * sp,
            "life": life, "max_life": life,
            "color": hit_color(hue + random.randint(-14, 14)),
            "radius": random.randint(2, 5),
        })
    add_shockwave(state, ball.x, ball.y, col)


def add_shockwave(state, x, y, color):
    """Add an expanding shockwave ring effect."""
    state.shockwaves.append(Shockwave(x, y, color, state.current_time))


def add_floating_text(state, x, y, text, color):
    """Add a floating score popup that drifts upward."""
    state.floating_texts.append(FloatingText(x, y, text, color, state.current_time))


def trigger_screen_shake(state, intensity=SCREEN_SHAKE_INTENSITY):
    """Trigger a screen shake effect."""
    state.screen_shake_time = state.current_time
    state.screen_shake_intensity = intensity


# =================================================================
#  COMBO
# =================================================================

def increment_combo(state):
    """Increment combo counter on successful paddle hit."""
    state.combo_count += 1
    state.combo_display_time = state.current_time
    if state.combo_count > state.max_combo:
        state.max_combo = state.combo_count


def reset_combo(state):
    """Reset combo on miss."""
    state.combo_count = 0


# =================================================================
#  UPDATE
# =================================================================

def update_effects(state, dt):
    """Update all visual effects — tick lifetimes, remove expired."""
    # Particles
    alive = []
    for p in state.particles:
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["vy"] += PARTICLE_GRAVITY * dt
        p["life"] -= dt
        if p["life"] > 0:
            alive.append(p)
    state.particles = alive

    # Shockwaves
    state.shockwaves = [
        sw for sw in state.shockwaves
        if state.current_time - sw.start_time < SHOCKWAVE_DURATION
    ]

    # Floating texts
    state.floating_texts = [
        ft for ft in state.floating_texts
        if state.current_time - ft.start_time < FLOATING_TEXT_DURATION
    ]


# =================================================================
#  SCREEN SHAKE
# =================================================================

def get_screen_shake_offset(state):
    """Compute current screen-shake offset (x, y). Returns (0, 0) if inactive."""
    if state.screen_shake_time <= 0:
        return 0, 0
    elapsed = state.current_time - state.screen_shake_time
    if elapsed > SCREEN_SHAKE_DURATION:
        return 0, 0
    decay = 1.0 - (elapsed / SCREEN_SHAKE_DURATION)
    intensity = state.screen_shake_intensity * decay
    return (
        int(random.uniform(-intensity, intensity)),
        int(random.uniform(-intensity, intensity)),
    )


def apply_screen_shake(frame, offset_x, offset_y):
    """Apply screen shake by translating the frame."""
    if offset_x == 0 and offset_y == 0:
        return frame
    h, w = frame.shape[:2]
    M = np.float32([[1, 0, offset_x], [0, 1, offset_y]])
    return cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
