"""Game configuration constants, difficulty settings, and color themes."""

# =================================================================
#  WINDOW
# =================================================================
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 720

# =================================================================
#  BALL
# =================================================================
BALL_RADIUS = 20
TRAIL_LENGTH = 15
SPEED_INCREMENT = 15
MAX_BALL_SPEED = 900

# =================================================================
#  PADDLE
# =================================================================
PADDLE_HEIGHT = 200
PADDLE_WIDTH = 20
LEFT_PADDLE_X = 10
RIGHT_PADDLE_X = WINDOW_WIDTH - 10
PADDLE_LERP_FACTOR = 0.35

# =================================================================
#  DIFFICULTY
# =================================================================
DIFFICULTY_NAMES = ["Easy", "Medium", "Hard"]
DIFFICULTY_SPEEDS = [350, 450, 550]
DIFFICULTY_AI_SPEEDS = [200, 350, 500]

# =================================================================
#  GESTURES & TIMING
# =================================================================
GESTURE_REQUIRED_DURATION = 1.0
COUNTDOWN_DURATION = 3

# =================================================================
#  HAND DETECTION
# =================================================================
DETECTION_WIDTH = 320
DETECTION_HEIGHT = 240

# =================================================================
#  VISUAL EFFECTS
# =================================================================
HIT_FLASH_DURATION = 0.15
PARTICLE_GRAVITY = 300
SHOCKWAVE_DURATION = 0.35
SHOCKWAVE_MAX_RADIUS = 80
SCREEN_SHAKE_DURATION = 0.25
SCREEN_SHAKE_INTENSITY = 12
FLOATING_TEXT_DURATION = 1.2
FLOATING_TEXT_SPEED = 80
GLOW_DOWNSCALE = 4

# =================================================================
#  POWER-UPS
# =================================================================
POWERUP_SPAWN_MIN = 8.0
POWERUP_SPAWN_MAX = 14.0
POWERUP_LIFETIME  = 10.0  # seconds before an uncollected power-up disappears
POWERUP_RADIUS = 22
POWERUP_TYPES = {
    "big_paddle":  {"duration": 5.0, "label": "BIG",  "desc": "Bigger Paddle"},
    "speed_boost": {"duration": 5.0, "label": "FAST", "desc": "Speed Boost"},
    "slow_motion": {"duration": 4.0, "label": "SLOW", "desc": "Slow Motion"},
    "multi_ball":  {"duration": 6.0, "label": "x2",   "desc": "Multi Ball"},
}
BIG_PADDLE_MULTIPLIER = 1.5
SPEED_BOOST_MULTIPLIER = 1.3
SLOW_MOTION_MULTIPLIER = 0.6

# =================================================================
#  OBSTACLES
# =================================================================
OBSTACLE_COUNT = 3
OBSTACLE_MIN_SIZE = 30
OBSTACLE_MAX_SIZE = 60
OBSTACLE_SPEED_MIN = 50
OBSTACLE_SPEED_MAX = 150

# =================================================================
#  COMBO
# =================================================================
COMBO_DISPLAY_DURATION = 1.5

# =================================================================
#  GAME MODES
# =================================================================
GAME_MODE_NAMES = ["Classic", "Survival", "Time Attack"]
TIME_ATTACK_DURATION = 60

# =================================================================
#  COLOR THEMES  (BGR format for OpenCV)
# =================================================================
COLOR_THEMES = [
    {
        "name": "Neon",
        "ball":          (100, 255, 0),
        "ball_hit":      (255, 100, 0),
        "left_paddle":   (50, 100, 255),
        "right_paddle":  (255, 100, 50),
        "court":         (200, 255, 0),
        "glow":          (150, 255, 0),
        "bg_grid":       (60, 80, 0),
        "score_popup":   (0, 255, 255),
        "powerup_big":   (0, 255, 0),
        "powerup_fast":  (0, 165, 255),
        "powerup_slow":  (255, 100, 255),
        "powerup_multi": (0, 255, 255),
        "obstacle":      (120, 120, 120),
    },
    {
        "name": "Retro",
        "ball":          (255, 255, 255),
        "ball_hit":      (0, 255, 255),
        "left_paddle":   (255, 255, 255),
        "right_paddle":  (255, 255, 255),
        "court":         (100, 100, 100),
        "glow":          (180, 180, 180),
        "bg_grid":       (30, 30, 30),
        "score_popup":   (255, 255, 255),
        "powerup_big":   (0, 255, 0),
        "powerup_fast":  (0, 200, 255),
        "powerup_slow":  (200, 100, 255),
        "powerup_multi": (0, 255, 255),
        "obstacle":      (80, 80, 80),
    },
    {
        "name": "Ice",
        "ball":          (255, 220, 100),
        "ball_hit":      (255, 255, 220),
        "left_paddle":   (50, 180, 255),
        "right_paddle":  (255, 220, 100),
        "court":         (255, 220, 150),
        "glow":          (255, 230, 180),
        "bg_grid":       (60, 40, 20),
        "score_popup":   (255, 255, 100),
        "powerup_big":   (100, 255, 100),
        "powerup_fast":  (100, 200, 255),
        "powerup_slow":  (255, 150, 200),
        "powerup_multi": (100, 255, 255),
        "obstacle":      (200, 180, 140),
    },
    {
        "name": "Fire",
        "ball":          (0, 140, 255),
        "ball_hit":      (0, 50, 255),
        "left_paddle":   (0, 80, 255),
        "right_paddle":  (0, 200, 255),
        "court":         (0, 100, 200),
        "glow":          (0, 100, 200),
        "bg_grid":       (0, 20, 40),
        "score_popup":   (0, 220, 255),
        "powerup_big":   (0, 255, 100),
        "powerup_fast":  (50, 180, 255),
        "powerup_slow":  (200, 80, 255),
        "powerup_multi": (0, 255, 255),
        "obstacle":      (0, 80, 150),
    },
]

THEME_NAMES = [t["name"] for t in COLOR_THEMES]


def get_theme(settings):
    """Get the current color theme dict from settings."""
    idx = settings.get("color_theme", 0) % len(COLOR_THEMES)
    return COLOR_THEMES[idx]


def get_powerup_color(theme, ptype):
    """Get the display color for a power-up type."""
    mapping = {
        "big_paddle":  "powerup_big",
        "speed_boost": "powerup_fast",
        "slow_motion": "powerup_slow",
        "multi_ball":  "powerup_multi",
    }
    return theme.get(mapping.get(ptype, "powerup_big"), (255, 255, 255))
