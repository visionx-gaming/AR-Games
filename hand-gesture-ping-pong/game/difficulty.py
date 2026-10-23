"""How hard a vs-CPU game currently is: the ramp that makes the CPU and the ball sharper the longer
a game runs (see RAMP_* in game.config), and the 1-5 level shown in the HUD."""

from game.config import DIFFICULTY_RAMP_SECONDS, RAMP_PER_POINT, TIME_ATTACK_RAMP_SECONDS


def ramp_progress(state):
    """0..1: how far into its difficulty ramp a vs-CPU game is (always 0 for 2 players)."""
    if not state.settings["ai_enabled"]:
        return 0.0
    if state.settings["game_mode"] == 2:
        p = state.game_time / TIME_ATTACK_RAMP_SECONDS
    else:
        p = state.game_time / DIFFICULTY_RAMP_SECONDS + RAMP_PER_POINT * (state.score[0] + state.score[1])
    return max(0.0, min(1.0, p))


def ramp(state, lohi):
    return lohi[0] + (lohi[1] - lohi[0]) * ramp_progress(state)


def cpu_level(state):
    """1..5 label for the HUD (None when there is no CPU)."""
    return 1 + int(ramp_progress(state) * 4.999) if state.settings["ai_enabled"] else None
