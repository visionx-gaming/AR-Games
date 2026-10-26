"""Game configuration constants, difficulty settings, and color themes."""

# =================================================================
#  WINDOW
# =================================================================
# 16:9, so the game fills a Full HD (1920x1080) screen exactly at 1.5x with
# no black bars, and matches a 1280x720 camera frame with no cropping.
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
# The game always *draws* in this 1280x720 logical space, but renders natively
# at the display's resolution (see game/gfx.py), between these frame heights.
# 2160 = 4K.  Lower MAX_RENDER_HEIGHT if a very high-res display gets too slow.
MIN_RENDER_HEIGHT = 540
MAX_RENDER_HEIGHT = 2160

# =================================================================
#  BALL
# =================================================================
BALL_RADIUS = 20
TRAIL_LENGTH = 15
SPEED_INCREMENT = 15
MAX_BALL_SPEED = 1250
PHYSICS_MAX_STEP = 1.0 / 120.0       # largest physics substep (seconds)
# The serve is slower and flatter than a rally shot, so the receiver has time to
# react (a full-speed Hard serve crosses to the edge in ~1.1 s and was often
# unreturnable).  Normal speed resumes from the first paddle hit.
SERVE_SPEED_FACTOR = 0.65
SERVE_MAX_SLOPE = 0.35               # max |vy / vx| of the serve

# =================================================================
#  PADDLE
# =================================================================
PADDLE_HEIGHT = 200
PADDLE_WIDTH = 20
LEFT_PADDLE_X = 10
RIGHT_PADDLE_X = WINDOW_WIDTH - 10
PADDLE_LERP_FACTOR = 0.5             # per 60 fps frame (~24 ms time constant); converted to a dt-based factor
# Hand tracking lags the real hand (camera + detection).  The tracker extrapolates
# the hand's vertical motion this far ahead to compensate; 0 disables it.
HAND_PREDICT_SECONDS = 0.04
# "One Euro" jitter filter on the hand's vertical position: strong smoothing when
# the hand is (nearly) still - removes paddle shimmer - and almost none when it
# moves fast, so it adds very little lag.  MIN_CUTOFF (Hz): lower = calmer at
# rest.  BETA: higher = less lag when moving.  Set MIN_CUTOFF to 0 to disable.
HAND_FILTER_MIN_CUTOFF = 1.5
HAND_FILTER_BETA = 4.0
KEYBOARD_PADDLE_STEP = 45            # px per key press (keyboard / no-camera fallback)

# =================================================================
#  DIFFICULTY
# =================================================================
DIFFICULTY_NAMES = ["Easy", "Medium", "Hard"]
DIFFICULTY_SPEEDS = [350, 450, 550]
DIFFICULTY_AI_SPEEDS = [200, 350, 500]
# vs-CPU games get harder the longer they run.  The ramp reaches full strength after
# DIFFICULTY_RAMP_SECONDS of play (Time Attack ramps over its own 60 s, so a tournament
# run is hardest at the buzzer).  Start/end multipliers on the CPU's speed and aim error,
# and on the ball's speed.
PADDLE_FLASH_SECONDS = 0.45     # how long a paddle glows after a hit
DIFFICULTY_RAMP_SECONDS = 90      # normal games: full strength after this long ...
RAMP_PER_POINT = 0.12             # ... and every point scored pushes it along too
TIME_ATTACK_RAMP_SECONDS = 40     # Time Attack (tournament) is at full strength 40 s into its 60 s
RAMP_AI_SPEED = (1.0, 1.9)
RAMP_AI_ERROR = (1.0, 0.3)
RAMP_BALL_SPEED = (1.0, 1.5)
DIFFICULTY_AI_ERROR = [90, 50, 20]   # px of aiming error the AI re-rolls on every return

# =================================================================
#  GESTURES & TIMING
# =================================================================
GESTURE_REQUIRED_DURATION = 1.0
COUNTDOWN_DURATION = 3

# =================================================================
#  CAMERA
# =================================================================
# Highest capture mode requested.  The camera is opened at the best of
# 1080p / 720p / 480p that it can sustain at CAMERA_MIN_FPS (see camera.py), so
# the background is sharp on a Full HD display without hurting the frame rate.
CAMERA_WIDTH = 1920
CAMERA_HEIGHT = 1080
CAMERA_FPS = 30
CAMERA_MIN_FPS = 20          # below this, fall back to a lower resolution

# Frame-rate cap for the game loop (the camera is decoupled and runs at its own rate)
MAX_FPS = 60

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
#  EVENT (TOURNAMENT) MODE  -  run with:  python main.py --event
# =================================================================
EVENT_TITLE = "DIWALI  HAND  PONG"
EVENT_MAX_ATTEMPTS = 1          # per person; run with --attempts 2 for a "second chance" round
EVENT_LEADERBOARD_ROWS = 10     # rows shown on the leaderboard
EVENT_RESULT_SECONDS = 12       # how long a player's result stays up before the next player

# =================================================================
#  FINALS  -  run with:  python main.py --finals
# =================================================================
FINALS_SCORE_TO_WIN = 5         # semi-finals, 3rd-place match and final
FINALS_PLAYOFF_SCORE = 3        # sudden-death playoff to break a tie for the last finals seat
FINALS_RESULT_SECONDS = 15      # how long a match result stays up

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
        "accent":        (0, 255, 200),
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
        "accent":        (0, 190, 255),
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
        "accent":        (255, 235, 190),
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
        "accent":        (0, 165, 255),
        "powerup_big":   (0, 255, 100),
        "powerup_fast":  (50, 180, 255),
        "powerup_slow":  (200, 80, 255),
        "powerup_multi": (0, 255, 255),
        "obstacle":      (0, 80, 150),
    },
    {
        "name": "Contrast",                      # colour-blind safe: blue vs orange paddles, yellow ball
        "ball":          (66, 228, 240),
        "ball_hit":      (255, 255, 255),
        "left_paddle":   (233, 180, 86),
        "right_paddle":  (0, 159, 230),
        "court":         (230, 230, 230),
        "glow":          (200, 200, 200),
        "bg_grid":       (60, 60, 60),
        "score_popup":   (66, 228, 240),
        "accent":        (233, 180, 86),
        "powerup_big":   (115, 158, 0),
        "powerup_fast":  (0, 94, 213),
        "powerup_slow":  (167, 121, 204),
        "powerup_multi": (233, 180, 86),
        "obstacle":      (130, 130, 130),
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
