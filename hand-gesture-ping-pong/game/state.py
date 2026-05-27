"""Game state classes — central data model for all mutable game state."""

import random
import math
from collections import deque
from game.config import (
    WINDOW_HEIGHT, PADDLE_HEIGHT, POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX, TRAIL_LENGTH,
)


# =================================================================
#  DATA CLASSES
# =================================================================

class Ball:
    """Represents a ball in the game."""
    __slots__ = ("x", "y", "vx", "vy", "curve", "is_main", "trail", "alive", "hit_count")

    def __init__(self, x, y, vx, vy, is_main=True):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.curve = 0.0        # Spin factor — gradually deflects vy
        self.is_main = is_main
        self.trail = deque(maxlen=TRAIL_LENGTH)  # O(1) append, no manual trim needed
        self.alive = True
        self.hit_count = 0


class PowerUpItem:
    """A collectible power-up floating on the court."""
    __slots__ = ("x", "y", "type", "spawn_time", "pulse_phase")

    def __init__(self, x, y, ptype):
        self.x = float(x)
        self.y = float(y)
        self.type = ptype
        self.spawn_time = 0.0
        self.pulse_phase = random.uniform(0, 2 * math.pi)


class Obstacle:
    """A bouncing obstacle block on the court."""
    __slots__ = ("x", "y", "w", "h", "vy")

    def __init__(self, x, y, w, h, vy):
        self.x = float(x)
        self.y = float(y)
        self.w = int(w)
        self.h = int(h)
        self.vy = float(vy)


class Shockwave:
    """An expanding ring effect from a paddle hit."""
    __slots__ = ("x", "y", "color", "start_time")

    def __init__(self, x, y, color, start_time):
        self.x = int(x)
        self.y = int(y)
        self.color = color
        self.start_time = start_time


class FloatingText:
    """A floating score-popup text that drifts upward and fades."""
    __slots__ = ("x", "y", "text", "color", "start_time")

    def __init__(self, x, y, text, color, start_time):
        self.x = float(x)
        self.y = float(y)
        self.text = text
        self.color = color
        self.start_time = start_time


# =================================================================
#  GAME STATE
# =================================================================

class GameState:
    """Central game-state container — passed to all subsystems."""

    def __init__(self):
        # --- Core state machine ---
        self.game_state = "START"
        self.previous_state = ""       # state to return to from MENU
        self.menu_selection = 0
        self.settings_return_state = "START"  # where ESC from SETTINGS goes

        # --- Settings ---
        self.settings = {
            "score_to_win": 5,
            "difficulty": 1,
            "game_mode": 0,
            "ai_enabled": False,
            "color_theme": 0,
            "sound_enabled": True,
            "music_volume": 90,
            "sfx_volume": 20,
            "show_hand_skeleton": True,
            "obstacles_enabled": False,
            "selected_setting": 0,
        }

        # --- Scores ---
        self.score = [0, 0]
        self.high_score = 0
        self.winner = ""

        # --- Timing ---
        self.current_time = 0.0
        self.dt = 0.0
        self.countdown_start = 0.0
        self.play_start_time = 0.0

        # --- Balls ---
        self.balls = []

        # --- Paddles ---
        center = float(WINDOW_HEIGHT // 2 - PADDLE_HEIGHT // 2)
        self.left_paddle_y = center
        self.right_paddle_y = center
        self.left_paddle_target = center
        self.right_paddle_target = center
        self.left_paddle_height = PADDLE_HEIGHT
        self.right_paddle_height = PADDLE_HEIGHT

        # --- Effects ---
        self.particles = []
        self.shockwaves = []
        self.floating_texts = []
        self.screen_shake_time = 0.0
        self.screen_shake_intensity = 0
        self.hit_animation_time = 0.0

        # --- Combo ---
        self.combo_count = 0
        self.max_combo = 0
        self.combo_display_time = 0.0

        # --- Power-ups ---
        self.powerups = []
        self.active_effects = {}
        self.next_powerup_time = 0.0

        # --- Obstacles ---
        self.obstacles = []

        # --- Hand tracking results ---
        self.hand_pos = {"Left": None, "Right": None}
        self.hand_landmarks = {"Left": None, "Right": None}
        self.fist_state = {"Left": False, "Right": False}

        # --- Gesture timing ---
        self.start_gesture_time = None
        self.restart_gesture_time = None
        self.fist_pause_cooldown = 0.0

        # --- Mode-specific ---
        self.survival_rally = 0

        # --- Background animation ---
        self.bg_offset = 0.0
        self.bg_pulse = 0.0

        # --- Score flash ---
        self.score_flash_time = [0.0, 0.0]   # timestamp when each side last scored

        # --- Stats bookkeeping ---
        self.stats_saved = False

        # --- UI flags ---
        self.show_exit_confirm = False

    def reset_for_new_game(self):
        """Reset state for a new game while keeping settings."""
        self.score = [0, 0]
        self.winner = ""
        self.balls.clear()
        self.particles.clear()
        self.shockwaves.clear()
        self.floating_texts.clear()
        self.powerups.clear()
        self.active_effects.clear()
        self.obstacles.clear()
        self.combo_count = 0
        self.max_combo = 0
        self.combo_display_time = 0.0
        self.survival_rally = 0
        self.hit_animation_time = 0.0
        self.screen_shake_time = 0.0
        self.left_paddle_height = PADDLE_HEIGHT
        self.right_paddle_height = PADDLE_HEIGHT
        self.score_flash_time = [0.0, 0.0]
        self.stats_saved = False
        self.next_powerup_time = self.current_time + random.uniform(
            POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX
        )
