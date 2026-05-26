"""Per-state handler functions extracted from the main game loop.

Each handler receives a FrameCtx (per-frame read-only snapshot) plus the
mutable objects it needs, performs all rendering and input for its state,
and may transition state.game_state.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

import cv2

from game.config import (
    COUNTDOWN_DURATION, GESTURE_REQUIRED_DURATION,
    get_theme, WINDOW_WIDTH, WINDOW_HEIGHT,
)
from game import effects, engine, renderer, screens
from game.screens import MENU_ITEMS, change_setting
from game.stats import record_game_result


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


# ===================================================================
#  HANDLERS
# ===================================================================

def handle_start(ctx: FrameCtx, state, stats, sound_mgr, tracker) -> None:
    if not sound_mgr.lobby_playing and state.settings["sound_enabled"]:
        sound_mgr.start_lobby_music(state.settings["music_volume"])

    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)

    if state.settings["show_hand_skeleton"]:
        renderer.draw_hand_skeletons(ctx.frame, state, ctx.mp_hand_connections)

    screens.show_start_screen(ctx.frame, state, stats)

    if ctx.key in (ord('m'), ord('M')):
        state.settings_return_state = "START"
        state.game_state = "SETTINGS"

    # Space or Enter also starts the game
    if ctx.key in (ord(' '), 13):
        state.reset_for_new_game()
        state.countdown_start = ctx.current_time
        state.game_state = "COUNTDOWN"
        state.start_gesture_time = None
        engine.init_obstacles(state)
        sound_mgr.play_start_jingle()
        if state.settings["sound_enabled"]:
            sound_mgr.start_bgm(state.settings["music_volume"])
        return

    if ctx.hand_pos["Left"] is not None and ctx.hand_pos["Right"] is not None:
        if state.start_gesture_time is None:
            state.start_gesture_time = ctx.current_time
        elif ctx.current_time - state.start_gesture_time >= GESTURE_REQUIRED_DURATION:
            state.reset_for_new_game()
            state.countdown_start = ctx.current_time
            state.game_state = "COUNTDOWN"
            state.start_gesture_time = None
            engine.init_obstacles(state)
            sound_mgr.play_start_jingle()
            if state.settings["sound_enabled"]:
                sound_mgr.start_bgm(state.settings["music_volume"])
    else:
        state.start_gesture_time = None

    # Mouse: click on "PRESS SPACE TO START" text area
    _mx, _my = ctx.mouse_pos
    if ctx.mouse_clicked and 0 <= _mx <= WINDOW_WIDTH:
        cx = WINDOW_WIDTH // 2
        if (cx - 380 <= _mx <= cx + 380) and (260 <= _my <= 320):
            state.reset_for_new_game()
            state.countdown_start = ctx.current_time
            state.game_state = "COUNTDOWN"
            state.start_gesture_time = None
            engine.init_obstacles(state)
            sound_mgr.play_start_jingle()
            if state.settings["sound_enabled"]:
                sound_mgr.start_bgm(state.settings["music_volume"])


def handle_settings(ctx: FrameCtx, state, sound_mgr) -> None:
    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    screens.show_settings_screen(ctx.frame, state)

    new_state = screens.handle_settings_input(ctx.key_raw, state, sound_mgr)
    if new_state:
        # ESC from settings returns to wherever we came from (START or MENU)
        state.game_state = state.settings_return_state if new_state == "START" else new_state

    # Mouse: hover to highlight, left-click to advance (+1), right-click to go back (-1)
    _mx, _my = ctx.mouse_pos
    if 0 <= _mx <= WINDOW_WIDTH:
        cx = WINDOW_WIDTH // 2
        start_y = 100
        s = state.settings
        for i in range(10):
            y = start_y + 65 + i * 42
            if (cx - 280 <= _mx <= cx + 280) and (y - 25 <= _my <= y + 10):
                if s["selected_setting"] != i:
                    s["selected_setting"] = i
                    sound_mgr.play_menu_tick()
                if ctx.mouse_clicked:
                    change_setting(s, i, +1, sound_mgr)
                elif ctx.mouse_right_clicked:
                    change_setting(s, i, -1, sound_mgr)
                break


def handle_countdown(ctx: FrameCtx, state, tracker) -> None:
    engine.update_paddles(state)

    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    renderer.draw_court(ctx.frame, state, ctx.theme)

    if state.settings["obstacles_enabled"]:
        renderer.draw_obstacles(ctx.frame, state, ctx.theme)

    renderer.draw_paddles(ctx.frame, state, ctx.theme, ctx.glow_layer)
    renderer.apply_glow(ctx.frame, ctx.glow_layer)

    if state.settings["show_hand_skeleton"]:
        renderer.draw_hand_skeletons(ctx.frame, state, ctx.mp_hand_connections)

    screens.show_countdown_screen(ctx.frame, state)

    elapsed = ctx.current_time - state.countdown_start
    if elapsed >= COUNTDOWN_DURATION + 0.5:
        engine.reset_ball(state)
        state.game_state = "PLAYING"
        state.play_start_time = ctx.current_time


def handle_playing(ctx: FrameCtx, state, sound_mgr, tracker) -> None:
    if (ctx.fist_state["Left"] and ctx.fist_state["Right"]
            and state.fist_pause_cooldown <= 0):
        state.game_state = "PAUSED"
        state.fist_pause_cooldown = 1.5
        return

    engine.update_paddles(state)
    engine.update_balls(state)
    engine.check_all_collisions(state, sound_mgr)
    engine.update_powerups(state, sound_mgr)
    engine.update_obstacles(state)
    engine.check_time_attack(state)
    effects.update_effects(state, ctx.dt)

    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    renderer.draw_court(ctx.frame, state, ctx.theme, ctx.glow_layer)

    if state.settings["obstacles_enabled"]:
        renderer.draw_obstacles(ctx.frame, state, ctx.theme)

    renderer.draw_powerups(ctx.frame, state, ctx.theme)
    renderer.draw_ball_trails(ctx.frame, state, ctx.theme)
    renderer.draw_balls(ctx.frame, state, ctx.theme, ctx.glow_layer)
    renderer.draw_paddles(ctx.frame, state, ctx.theme, ctx.glow_layer)
    renderer.apply_glow(ctx.frame, ctx.glow_layer)
    renderer.draw_shockwaves(ctx.frame, state)
    renderer.draw_particles(ctx.frame, state)
    renderer.draw_floating_texts(ctx.frame, state)
    renderer.draw_combo(ctx.frame, state, ctx.theme)
    renderer.draw_hud(ctx.frame, state, ctx.theme)

    if state.settings["show_hand_skeleton"]:
        renderer.draw_hand_skeletons(ctx.frame, state, ctx.mp_hand_connections)

    if ctx.key in (ord('p'), ord('P')):
        state.game_state = "PAUSED"
        state.fist_pause_cooldown = 1.5


def handle_paused(ctx: FrameCtx, state, sound_mgr) -> None:
    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    renderer.draw_court(ctx.frame, state, ctx.theme)

    if state.settings["obstacles_enabled"]:
        renderer.draw_obstacles(ctx.frame, state, ctx.theme)

    renderer.draw_paddles(ctx.frame, state, ctx.theme)
    renderer.draw_paused_balls(ctx.frame, state, ctx.theme)
    screens.show_pause_screen(ctx.frame, state)
    renderer.draw_particles(ctx.frame, state)

    if ctx.key in (ord('r'), ord('R')):
        state.game_state = "PLAYING"
        state.fist_pause_cooldown = 1.5
    elif (not ctx.fist_state["Left"] and not ctx.fist_state["Right"]
          and ctx.hand_pos["Left"] is not None
          and ctx.hand_pos["Right"] is not None
          and state.fist_pause_cooldown <= 0):
        state.game_state = "PLAYING"
        state.fist_pause_cooldown = 1.5

    # Mouse: click on "R TO RESUME" text area
    _mx, _my = ctx.mouse_pos
    if ctx.mouse_clicked and 0 <= _mx <= WINDOW_WIDTH:
        cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
        if (cx - 250 <= _mx <= cx + 250) and (cy + 22 <= _my <= cy + 72):
            state.game_state = "PLAYING"
            state.fist_pause_cooldown = 1.5


def handle_menu(ctx: FrameCtx, state, sound_mgr) -> None:
    # Draw frozen game state beneath the overlay
    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    renderer.draw_court(ctx.frame, state, ctx.theme)
    if state.settings["obstacles_enabled"]:
        renderer.draw_obstacles(ctx.frame, state, ctx.theme)
    renderer.draw_paddles(ctx.frame, state, ctx.theme)
    renderer.draw_paused_balls(ctx.frame, state, ctx.theme)

    screens.show_menu_screen(ctx.frame, state)

    UP, DOWN = 2490368, 2621440
    n = len(MENU_ITEMS)

    if ctx.key in (ord('w'), ord('W')) or ctx.key_raw == UP:
        state.menu_selection = (state.menu_selection - 1) % n
        sound_mgr.play_menu_tick()
    elif ctx.key in (ord('s'), ord('S')) or ctx.key_raw == DOWN:
        state.menu_selection = (state.menu_selection + 1) % n
        sound_mgr.play_menu_tick()
    elif ctx.key in (13, ord(' ')):          # Enter or Space — select
        sel = state.menu_selection
        if sel == 0:                          # Resume
            state.game_state = state.previous_state
        elif sel == 1:                        # Settings
            state.settings_return_state = "MENU"
            state.game_state = "SETTINGS"
        elif sel == 2:                        # Quit to Main Menu
            sound_mgr.stop_bgm()
            if state.settings["sound_enabled"]:
                sound_mgr.start_lobby_music(state.settings["music_volume"])
            state.previous_state = ""
            state.game_state = "START"
        elif sel == 3:                        # Quit Game
            state.game_state = "QUIT"
    elif ctx.key == 27:                       # ESC → resume
        state.game_state = state.previous_state

    # Mouse: hover to highlight, click to select
    _mx, _my = ctx.mouse_pos
    if 0 <= _mx <= WINDOW_WIDTH:
        cx_m = WINDOW_WIDTH // 2
        cy_m = WINDOW_HEIGHT // 2
        pw_m, ph_m = 480, 395
        px_m = cx_m - pw_m // 2
        py_m = cy_m - ph_m // 2
        for i in range(len(MENU_ITEMS)):
            iy = py_m + 118 + i * 62
            if (px_m + 14 <= _mx <= px_m + pw_m - 14) and (iy - 30 <= _my <= iy + 16):
                if state.menu_selection != i:
                    state.menu_selection = i
                    sound_mgr.play_menu_tick()
                if ctx.mouse_clicked:
                    if i == 0:
                        state.game_state = state.previous_state
                    elif i == 1:
                        state.settings_return_state = "MENU"
                        state.game_state = "SETTINGS"
                    elif i == 2:
                        sound_mgr.stop_bgm()
                        if state.settings["sound_enabled"]:
                            sound_mgr.start_lobby_music(state.settings["music_volume"])
                        state.previous_state = ""
                        state.game_state = "START"
                    elif i == 3:
                        state.game_state = "QUIT"
                break


def handle_gameover(ctx: FrameCtx, state, stats, sound_mgr) -> None:
    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    effects.update_effects(state, ctx.dt)
    renderer.draw_particles(ctx.frame, state)
    screens.show_game_over_screen(ctx.frame, state, stats)

    if not state.stats_saved:
        record_game_result(stats, state)
        state.stats_saved = True
        sound_mgr.stop_bgm()
        sound_mgr.play_gameover()

    # Space / Enter also restarts
    if ctx.key in (13, ord(' ')):
        state.reset_for_new_game()
        state.countdown_start = ctx.current_time
        state.game_state = "COUNTDOWN"
        state.restart_gesture_time = None
        engine.init_obstacles(state)
        if state.settings["sound_enabled"] and not sound_mgr.bgm_playing:
            sound_mgr.start_bgm(state.settings["music_volume"])
        return

    if ctx.hand_pos["Left"] is not None and ctx.hand_pos["Right"] is not None:
        if state.restart_gesture_time is None:
            state.restart_gesture_time = ctx.current_time
        elif ctx.current_time - state.restart_gesture_time >= GESTURE_REQUIRED_DURATION:
            state.reset_for_new_game()
            state.countdown_start = ctx.current_time
            state.game_state = "COUNTDOWN"
            state.restart_gesture_time = None
            engine.init_obstacles(state)
            if state.settings["sound_enabled"] and not sound_mgr.bgm_playing:
                sound_mgr.start_bgm(state.settings["music_volume"])
    else:
        state.restart_gesture_time = None

    # Mouse: click on "PRESS SPACE TO RESTART" text area
    _mx, _my = ctx.mouse_pos
    if ctx.mouse_clicked and 0 <= _mx <= WINDOW_WIDTH:
        cx = WINDOW_WIDTH // 2
        if (cx - 400 <= _mx <= cx + 400) and (426 <= _my <= 486):
            state.reset_for_new_game()
            state.countdown_start = ctx.current_time
            state.game_state = "COUNTDOWN"
            state.restart_gesture_time = None
            engine.init_obstacles(state)
            if state.settings["sound_enabled"] and not sound_mgr.bgm_playing:
                sound_mgr.start_bgm(state.settings["music_volume"])
