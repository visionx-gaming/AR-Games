"""Switching into / out of the tournament modes (qualifier, finals) at run time.

The same code serves the command-line flags (--event / --finals) and the main-menu
buttons.  Everything here is an override on the live settings: nothing is written to
settings.json, and leave_tournament() puts the player's own settings back."""

import os

from game.config import EVENT_MAX_ATTEMPTS
from game.event import EventBoard
from game.finals import Finals
from game import finals as _finals_mod
from game.stats import set_event_overrides, clear_event_overrides, _write_json


def _reset_flow(state):
    state.event_mode = True
    state.event_board = EventBoard()
    state.finals = None
    state.finals_match = None
    state.finals_error = ""
    state.finals_withdraw = None
    state.tournament_exit_confirm = False
    state.name_edit_active = False
    state.show_exit_confirm = False


def enter_qualifier(state, difficulty=None, attempts=EVENT_MAX_ATTEMPTS):
    """Time Attack vs the CPU, same settings for everybody.  difficulty: 0/1/2."""
    clear_event_overrides(state.settings)                  # start from the player's own settings
    set_event_overrides(state.settings, {
        "game_mode": 2,                     # Time Attack
        "ai_enabled": True,                 # solo vs CPU
        "player_side": 0,                   # always the left paddle
        "difficulty": state.settings["difficulty"] if difficulty is None else difficulty,
        "obstacles_enabled": False,         # no luck factors: pure skill
        "powerups_enabled": False,
        "fist_pause_enabled": False,
        "player1_name": state.settings["player1_name"],     # the current player's name is an override too
    })
    _reset_flow(state)
    state.event_max_attempts = max(1, attempts)
    state.game_state = "EVENT_HOME"


def enter_finals(state, difficulty=None, restart=False):
    """Top-N bracket, two players, one hand each."""
    clear_event_overrides(state.settings)
    set_event_overrides(state.settings, {
        "game_mode": 0,                     # Classic
        "ai_enabled": False,                # two players, one hand each
        "difficulty": state.settings["difficulty"] if difficulty is None else difficulty,
        "obstacles_enabled": False,
        "powerups_enabled": False,
        "fist_pause_enabled": False,
        "player1_name": state.settings["player1_name"],     # per-match names: remembered, not saved
        "player2_name": state.settings["player2_name"],
        "score_to_win": state.settings["score_to_win"],
    })
    _reset_flow(state)
    if restart and os.path.exists(_finals_mod.FINALS_STATE_FILE):
        os.remove(_finals_mod.FINALS_STATE_FILE)
    state.finals = Finals.load()
    if state.finals is None:
        try:
            state.finals = Finals.from_ranking(state.event_board.ranking())
            state.finals.save(_write_json)
        except ValueError as e:
            state.finals_error = f"Cannot build the finals: {e}"
    state.game_state = "FINALS_HOME"


def leave_tournament(state):
    """Back to the normal main menu with the player's own settings restored."""
    clear_event_overrides(state.settings)
    state.event_mode = False
    state.event_board = None
    state.finals = None
    state.finals_match = None
    state.finals_error = ""
    state.finals_withdraw = None
    state.event_player = ""
    state.tournament_exit_confirm = False
    state.name_edit_active = False
    state.game_state = "START"
