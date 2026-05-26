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
