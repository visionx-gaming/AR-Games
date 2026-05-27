"""Persistent game statistics and settings — load/save from JSON files."""

import json
import os

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
}

DEFAULT_STATS = {
    "high_score_classic": 0,
    "high_score_survival": 0,
    "high_score_time_attack": 0,
    "total_games": 0,
    "total_wins_left": 0,
    "total_wins_right": 0,
    "longest_combo": 0,
    "longest_rally": 0,
}


def load_stats():
    """Load stats from file, merging with defaults for any new fields."""
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
        merged = dict(DEFAULT_STATS)
        merged.update(data)
        return merged
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_STATS)


def save_stats(stats):
    """Save stats to JSON file."""
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)
    except IOError:
        pass


def record_game_result(stats, state):
    """Update and persist stats from a finished game.

    Extracted from main.py so the game-over handler stays clean and this
    logic is independently testable.
    """
    mode = state.settings["game_mode"]
    mode_key = ["classic", "survival", "time_attack"][mode]
    hs_key = f"high_score_{mode_key}"

    current_high = state.survival_rally if mode == 1 else max(state.score)
    if current_high > stats.get(hs_key, 0):
        stats[hs_key] = current_high

    stats["total_games"] = stats.get("total_games", 0) + 1

    if state.max_combo > stats.get("longest_combo", 0):
        stats["longest_combo"] = state.max_combo
    if state.survival_rally > stats.get("longest_rally", 0):
        stats["longest_rally"] = state.survival_rally

    if state.winner.startswith("Left"):
        stats["total_wins_left"] = stats.get("total_wins_left", 0) + 1
    elif state.winner.startswith("Right"):
        stats["total_wins_right"] = stats.get("total_wins_right", 0) + 1

    save_stats(stats)


# ===================================================================
#  SETTINGS PERSISTENCE
# ===================================================================

def load_settings():
    """Load settings from file, merging with defaults for any missing keys."""
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
        merged = dict(DEFAULT_SETTINGS)
        merged.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        return merged
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)


def save_settings(settings):
    """Persist settings to JSON, excluding transient UI state."""
    to_save = {k: v for k, v in settings.items() if k in DEFAULT_SETTINGS}
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(to_save, f, indent=2)
    except IOError:
        pass
