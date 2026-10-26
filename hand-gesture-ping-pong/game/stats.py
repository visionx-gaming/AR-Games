"""Persistent game statistics and settings — load/save from JSON files.

Files are written atomically (temp file + replace) so a crash mid-write can't
corrupt them, loaded values are validated/clamped so a hand-edited or damaged
file can't crash the game, and an unreadable file is kept as `.bak` instead of
being silently overwritten.
"""

import json
import os
import tempfile

from game.config import COLOR_THEMES

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS_FILE    = os.path.join(_PROJECT_ROOT, "stats.json")
SETTINGS_FILE = os.path.join(_PROJECT_ROOT, "settings.json")

DEFAULT_SETTINGS = {
    "score_to_win":       5,
    "difficulty":         1,
    "game_mode":          0,
    "ai_enabled":         False,
    "color_theme":        0,
    "sound_enabled":      True,
    "music_volume":       90,
    "sfx_volume":         20,
    "show_hand_skeleton": True,
    "obstacles_enabled":  False,
    "camera_index":       0,
    "player1_name":       "PLAYER 1",
    "player2_name":       "PLAYER 2",
    "powerups_enabled":   True,
    "fullscreen":         False,
    "display_index":      0,
    "render_height":      0,
    "camera_quality":     0,
    "show_camera_feed":   True,
    "fist_pause_enabled": False,
    "player_side":        0,
}

# key -> (min, max) for ints; bool settings are listed in _BOOL_SETTINGS
_INT_RANGES = {
    "score_to_win": (1, 20),
    "difficulty":   (0, 2),
    "game_mode":    (0, 2),
    "player_side":  (0, 1),          # vs CPU: 0 = you play the left paddle, 1 = the right
    "color_theme":  (0, len(COLOR_THEMES) - 1),
    "music_volume": (0, 100),
    "sfx_volume":   (0, 100),
    "camera_index": (0, 9),
    "display_index": (0, 15),
}

# settings that may only take one of a fixed set of values
_INT_CHOICES = {
    "render_height": (0, 540, 720, 1080, 1440, 2160),     # 0 = automatic (native, up to the maximum)
    "camera_quality": (0, 720, 480),                       # 0 = automatic (best the camera sustains)
}
_BOOL_SETTINGS = ("ai_enabled", "sound_enabled", "show_hand_skeleton", "obstacles_enabled",
                  "powerups_enabled", "fullscreen", "show_camera_feed",
                  "fist_pause_enabled")

DEFAULT_STATS = {
    "high_score_classic": 0,        # best winning margin
    "high_score_survival": 0,       # best rally
    "high_score_time_attack": 0,    # best single-player score
    "total_games": 0,
    "total_wins_left": 0,
    "total_wins_right": 0,
    "longest_combo": 0,
    "longest_rally": 0,
}

HIGH_SCORE_KEYS   = ["high_score_classic", "high_score_survival", "high_score_time_attack"]
HIGH_SCORE_LABELS = ["BEST MARGIN", "BEST RALLY", "BEST SCORE"]

_warned_write = False

# ===================================================================
#  PLAYER NAMES
# ===================================================================

NAME_MAX_LEN = 12
NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _.-'")


def clean_name(value, default):
    """A safe display name: allowed characters only, spaces collapsed, at most
    NAME_MAX_LEN long.  Falls back to `default` if nothing usable is left."""
    if not isinstance(value, str):
        return default
    text = "".join(c for c in value if c in NAME_CHARS)
    text = " ".join(text.split())[:NAME_MAX_LEN].strip()
    return text or default



# ===================================================================
#  FILE HELPERS
# ===================================================================

def _read_json(path):
    """Return the JSON object stored at `path`, or None if missing/unusable.
    An unusable (corrupt / non-object) file is moved aside to `<path>.bak`."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        data = None
    if isinstance(data, dict):
        return data
    try:
        os.replace(path, path + ".bak")
    except OSError:
        pass
    return None


def _write_json(path, data):
    """Atomically write `data` as JSON. Warns once (instead of failing
    silently) if the location isn't writable."""
    global _warned_write
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except OSError as e:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        if not _warned_write:
            _warned_write = True
            print(f"WARNING: could not save {os.path.basename(path)}: {e}")


# ===================================================================
#  STATS
# ===================================================================

def load_stats():
    """Load stats from file, merging with defaults for any new fields."""
    merged = dict(DEFAULT_STATS)
    data = _read_json(STATS_FILE)
    if data:
        for k, v in data.items():
            if k in DEFAULT_STATS:
                if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
                    merged[k] = v
            else:
                merged[k] = v
    return merged


def save_stats(stats):
    """Save stats to JSON file."""
    _write_json(STATS_FILE, stats)


def high_score_value(stats, mode):
    """The stored high score for a game mode."""
    return stats.get(HIGH_SCORE_KEYS[mode], 0)


def record_game_result(stats, state):
    """Update and persist stats from a finished game.

    Extracted from main.py so the game-over handler stays clean and this
    logic is independently testable.
    """
    mode = state.settings["game_mode"]
    hs_key = HIGH_SCORE_KEYS[mode]

    if mode == 0:                    # Classic: how decisively you won
        current_high = abs(state.score[0] - state.score[1])
    elif mode == 1:                  # Survival: rally length
        current_high = state.survival_rally
    else:                            # Time Attack: best score
        current_high = max(state.score)
    new_best = current_high > stats.get(hs_key, 0)
    if new_best:
        stats[hs_key] = current_high

    stats["total_games"] = stats.get("total_games", 0) + 1

    if state.max_combo > stats.get("longest_combo", 0):
        stats["longest_combo"] = state.max_combo
    if state.max_rally > stats.get("longest_rally", 0):
        stats["longest_rally"] = state.max_rally

    if state.winner.startswith("Left"):
        stats["total_wins_left"] = stats.get("total_wins_left", 0) + 1
    elif state.winner.startswith("Right"):
        stats["total_wins_right"] = stats.get("total_wins_right", 0) + 1

    save_stats(stats)
    return new_best


# ===================================================================
#  SETTINGS PERSISTENCE
# ===================================================================

def _validated_settings(data):
    """Merge `data` over the defaults, dropping or clamping bad values."""
    merged = dict(DEFAULT_SETTINGS)
    for key, (lo, hi) in _INT_RANGES.items():
        v = data.get(key)
        if isinstance(v, int) and not isinstance(v, bool):
            merged[key] = max(lo, min(hi, v))
    for key, allowed in _INT_CHOICES.items():
        v = data.get(key)
        if isinstance(v, int) and not isinstance(v, bool) and v in allowed:
            merged[key] = v
    for key in _BOOL_SETTINGS:
        v = data.get(key)
        if isinstance(v, bool):
            merged[key] = v
    for key in ("player1_name", "player2_name"):
        merged[key] = clean_name(data.get(key), DEFAULT_SETTINGS[key])
    return merged


def load_settings():
    """Load settings from file, validated, merged with defaults."""
    data = _read_json(SETTINGS_FILE)
    return _validated_settings(data or {})


# Event mode forces some settings (Time Attack vs CPU, no power-ups, ...) and
# uses the player-name setting for whoever is playing.  Those values must never
# reach settings.json, or the normal game would start up in event configuration.
_event_overrides = {}       # key -> the value saved before the event started


def set_event_overrides(settings, overrides):
    """Force `overrides` on the live settings, remembering what was saved."""
    for k, v in overrides.items():
        _event_overrides.setdefault(k, settings.get(k))
        settings[k] = v


def clear_event_overrides(settings):
    """Put back the values that were saved before any event override was applied."""
    for k, v in _event_overrides.items():
        settings[k] = v
    _event_overrides.clear()


def save_settings(settings):
    """Persist settings to JSON, excluding transient UI state."""
    to_save = {k: v for k, v in settings.items() if k in DEFAULT_SETTINGS}
    to_save.update(_event_overrides)
    _write_json(SETTINGS_FILE, to_save)
