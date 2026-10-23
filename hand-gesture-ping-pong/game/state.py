"""Game state classes — central data model for all mutable game state."""

import random
import math
from datetime import datetime
from collections import deque
from game.config import (
    WINDOW_HEIGHT, PADDLE_HEIGHT, POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX, TRAIL_LENGTH,
)


# =================================================================
#  DATA CLASSES
# =================================================================

class Ball:
    """Represents a ball in the game."""
    __slots__ = ("x", "y", "vx", "vy", "curve", "is_main", "trail", "alive", "hit_count", "base_speed")

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
        self.base_speed = (self.vx ** 2 + self.vy ** 2) ** 0.5  # speed before power-up multipliers


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
            "player1_name": "PLAYER 1",
            "player2_name": "PLAYER 2",
            "powerups_enabled": True,
            "fullscreen": False,
            "display_index": 0,
            "render_height": 0,
            "camera_quality": 0,
            "show_camera_feed": True,
            "fist_pause_enabled": False,
            "player_side": 0,
            "camera_index": 0,
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
        self.game_time = 0.0           # gameplay clock: advances only while PLAYING

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
        self.paddle_flash = {"left": None, "right": None}   # (start_time, hue 0-179, strength 0-1)

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
        self.gesture_armed = False     # True once hands have been seen away since entering START/GAMEOVER
        self.gameover_time = 0.0
        self.pause_by_key = False      # paused with P -> hands must not auto-resume

        # --- Input / AI ---
        self.camera_ok = True
        self.mouse_pos = (-1, -1)      # pointer in logical coords, for hover effects
        self.system = None             # game.system.System (display / camera control); None in tests
        self.ai_aim_offset = 0.0

        # --- Mode-specific ---
        self.survival_rally = 0        # rally length (main-ball paddle hits); all modes
        self.max_rally = 0

        # --- Background animation ---
        self.bg_offset = 0.0
        self.bg_pulse = 0.0

        # --- Score flash ---
        self.score_flash_time = [0.0, 0.0]   # timestamp when each side last scored

        # --- Stats bookkeeping ---
        self.stats_saved = False

        # --- UI flags ---
        self.show_exit_confirm = False

        # --- Player names / match record ---
        self.match_names = ("PLAYER 1", "PLAYER 2")   # snapshot taken when a game starts
        self.match_started = ""                       # game id (start time)
        self.point_log = []        # (game_time, scorer_index, score1, score2) per point
        self.name_edit_active = False                 # name-entry dialog open
        self.name_edit_field = 0
        self.name_edit_buf = ["", ""]

        # --- Event (tournament) mode ---
        self.event_mode = False
        self.tournament_exit_confirm = False   # organiser asked to leave the tournament screens
        self.event_board = None           # game.event.EventBoard
        self.event_max_attempts = 1
        self.event_player = ""            # who is playing now
        self.event_result = None          # summary shown after their game
        self.event_result_until = 0.0

        # --- Finals (see game/finals.py) ---
        self.finals = None                # game.finals.Finals
        self.finals_error = ""            # why the bracket couldn't be built
        self.finals_match = None          # the match being played now
        self.finals_result = None         # summary shown after it
        self.finals_withdraw = None       # open "withdraw a player" dialog: {"names", "pick"}
        self.finals_notice = ("", 0.0)    # (text, show-until) message on the bracket screen

    def cpu_side(self):
        """'left' / 'right' - the paddle the CPU plays - or None in 2-player games."""
        s = self.settings
        if not s["ai_enabled"]:
            return None
        return "left" if s.get("player_side", 0) == 1 else "right"

    def player_mode(self):
        """0 = 2 players, 1 = vs CPU (CPU on the right), 2 = vs CPU (CPU on the left)."""
        s = self.settings
        return 0 if not s["ai_enabled"] else 1 + s.get("player_side", 0)

    def set_player_mode(self, mode):
        mode %= 3
        self.settings["ai_enabled"] = mode > 0
        if mode > 0:
            self.settings["player_side"] = mode - 1

    def player_names(self):
        """(left, right) display names for the current settings."""
        s = self.settings
        if self.cpu_side() == "left":
            return "CPU", s["player1_name"]
        return s["player1_name"], ("CPU" if s["ai_enabled"] else s["player2_name"])

    def reset_for_new_game(self):
        """Reset state for a new game while keeping settings."""
        self.score = [0, 0]
        self.winner = ""
        self.balls.clear()
        self.particles.clear()
        self.paddle_flash = {"left": None, "right": None}
        self.shockwaves.clear()
        self.floating_texts.clear()
        self.powerups.clear()
        self.active_effects.clear()
        self.obstacles.clear()
        self.combo_count = 0
        self.max_combo = 0
        self.combo_display_time = 0.0
        self.survival_rally = 0
        self.max_rally = 0
        self.pause_by_key = False
        self.ai_aim_offset = 0.0
        self.hit_animation_time = 0.0
        self.screen_shake_time = 0.0
        self.left_paddle_height = PADDLE_HEIGHT
        self.right_paddle_height = PADDLE_HEIGHT
        self.score_flash_time = [0.0, 0.0]
        self.stats_saved = False
        self.match_names = self.player_names()
        self.match_started = datetime.now().isoformat(timespec="seconds")
        self.point_log = []
        self.game_time = 0.0
        self.next_powerup_time = random.uniform(
            POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX
        )
