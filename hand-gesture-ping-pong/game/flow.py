"""Shared plumbing for the per-state handlers: the per-frame context and the
helpers every screen flow needs."""

from dataclasses import dataclass
from typing import Any

from game import powerups


@dataclass
class FrameCtx:
    """Immutable per-frame data passed to every handler."""
    frame: Any
    theme: dict
    hand_pos: dict
    fist_state: dict
    key: int
    key_raw: int
    current_time: float
    dt: float
    glow_layer: Any
    mp_hand_connections: Any = None
    mouse_pos: tuple = (-1, -1)
    mouse_clicked: bool = False
    mouse_right_clicked: bool = False


def in_rect(x, y, r):
    return r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]


def do_start_game(ctx, state, sound_mgr):
    """Shared helper: transition START → COUNTDOWN."""
    state.reset_for_new_game()
    state.countdown_start = ctx.current_time
    state.game_state = "COUNTDOWN"
    state.start_gesture_time = None
    powerups.init_obstacles(state)
    sound_mgr.play_start_jingle()
    if state.settings["sound_enabled"]:
        sound_mgr.start_bgm(state.settings["music_volume"])
