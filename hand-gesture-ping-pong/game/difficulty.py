"""How hard a game currently is: the ramp that makes the ball (and, against the CPU, the CPU) sharper
the longer a game runs (see RAMP_* in game.config), the 1-5 CPU level and the ball speed multiplier
shown in the HUD.  The ball speeds up in two-player games too."""

from game.config import DIFFICULTY_RAMP_SECONDS, RAMP_BALL_SPEED, RAMP_PER_POINT, TIME_ATTACK_RAMP_SECONDS


def ramp_progress(state):
    """0..1: how far into its difficulty ramp the current game is."""
    if state.settings["game_mode"] == 2:
        p = state.game_time / TIME_ATTACK_RAMP_SECONDS
    else:
        p = state.game_time / DIFFICULTY_RAMP_SECONDS + RAMP_PER_POINT * (state.score[0] + state.score[1])
    return max(0.0, min(1.0, p))


def ramp(state, lohi):
    return lohi[0] + (lohi[1] - lohi[0]) * ramp_progress(state)


def speed_multiplier(state):
    """Ball speed multiplier from the ramp (1.0 at the start of a game)."""
    return ramp(state, RAMP_BALL_SPEED)


def cpu_level(state):
    """1..5 label for the HUD (None when there is no CPU)."""
    return 1 + int(ramp_progress(state) * 4.999) if state.settings["ai_enabled"] else None
