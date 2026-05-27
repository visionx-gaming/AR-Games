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
    get_theme, WINDOW_WIDTH, WINDOW_HEIGHT, GAME_MODE_NAMES,
)
from game import effects, engine, renderer, screens
from game.screens import MENU_ITEMS, change_setting
from game.stats import record_game_result, save_settings


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

_LEFT_RAW = 2424832
_RIGHT_RAW = 2555904
_exit_confirm_sel: int = 1   # 0=YES  1=NO; default to NO for safety


def _do_start_game(ctx, state, sound_mgr):
    """Shared helper: transition START → COUNTDOWN."""
    state.reset_for_new_game()
    state.countdown_start = ctx.current_time
    state.game_state = "COUNTDOWN"
    state.start_gesture_time = None
    engine.init_obstacles(state)
    sound_mgr.play_start_jingle()
    if state.settings["sound_enabled"]:
        sound_mgr.start_bgm(state.settings["music_volume"])


def handle_start(ctx: FrameCtx, state, stats, sound_mgr, tracker) -> None:
    global _exit_confirm_sel

    if not sound_mgr.lobby_playing and state.settings["sound_enabled"]:
        sound_mgr.start_lobby_music(state.settings["music_volume"])

    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)

    if state.settings["show_hand_skeleton"]:
        renderer.draw_hand_skeletons(ctx.frame, state, ctx.mp_hand_connections)

    screens.show_start_screen(ctx.frame, state, stats)

    # ── Exit confirmation dialog ──────────────────────────────────
    if state.show_exit_confirm:
        screens.draw_exit_confirm_dialog(ctx.frame, state, _exit_confirm_sel)

        # Keyboard navigation inside dialog
        if ctx.key_raw == _LEFT_RAW or ctx.key in (ord('a'), ord('A')):
            if _exit_confirm_sel != 0:
                _exit_confirm_sel = 0
                sound_mgr.play_menu_tick()
        elif ctx.key_raw == _RIGHT_RAW or ctx.key in (ord('d'), ord('D')):
            if _exit_confirm_sel != 1:
                _exit_confirm_sel = 1
                sound_mgr.play_menu_tick()

        # Confirm
        if ctx.key in (ord('y'), ord('Y')):
            state.game_state = "QUIT"
        elif ctx.key in (ord('n'), ord('N')) or ctx.key == 27:
            state.show_exit_confirm = False
            _exit_confirm_sel = 1
        elif ctx.key in (13, ord(' ')):
            if _exit_confirm_sel == 0:
                state.game_state = "QUIT"
            else:
                state.show_exit_confirm = False
                _exit_confirm_sel = 1

        # Mouse hover + click
        _mx, _my = ctx.mouse_pos
        cx_w = WINDOW_WIDTH // 2
        cy_w = WINDOW_HEIGHT // 2
        btn_y = cy_w - 110 + 142   # py + 142, py = cy - ph//2 = cy - 110
        yes_cx, no_cx = cx_w - 150, cx_w + 150
        prev = _exit_confirm_sel
        if (yes_cx - 80 <= _mx <= yes_cx + 80) and (btn_y <= _my <= btn_y + 46):
            _exit_confirm_sel = 0
        elif (no_cx - 80 <= _mx <= no_cx + 80) and (btn_y <= _my <= btn_y + 46):
            _exit_confirm_sel = 1
        if _exit_confirm_sel != prev:
            sound_mgr.play_menu_tick()
        if ctx.mouse_clicked:
            if (yes_cx - 80 <= _mx <= yes_cx + 80) and (btn_y <= _my <= btn_y + 46):
                state.game_state = "QUIT"
            elif (no_cx - 80 <= _mx <= no_cx + 80) and (btn_y <= _my <= btn_y + 46):
                state.show_exit_confirm = False
                _exit_confirm_sel = 1
        return  # consume all input while dialog is open

    # ── ESC opens exit confirmation ───────────────────────────────
    if ctx.key == 27:
        state.show_exit_confirm = True
        _exit_confirm_sel = 1
        return

    # ── Mode selection (A/D or arrows to cycle, 1/2/3 direct) ────
    n_modes = len(GAME_MODE_NAMES)
    if ctx.key in (ord('a'), ord('A')) or ctx.key_raw == _LEFT_RAW:
        state.settings["game_mode"] = (state.settings["game_mode"] - 1) % n_modes
        save_settings(state.settings)
        sound_mgr.play_menu_tick()
    elif ctx.key in (ord('d'), ord('D')) or ctx.key_raw == _RIGHT_RAW:
        state.settings["game_mode"] = (state.settings["game_mode"] + 1) % n_modes
        save_settings(state.settings)
        sound_mgr.play_menu_tick()
    elif ctx.key == ord('1') and state.settings["game_mode"] != 0:
        state.settings["game_mode"] = 0
        save_settings(state.settings)
        sound_mgr.play_menu_tick()
    elif ctx.key == ord('2') and state.settings["game_mode"] != 1:
        state.settings["game_mode"] = 1
        save_settings(state.settings)
        sound_mgr.play_menu_tick()
    elif ctx.key == ord('3') and state.settings["game_mode"] != 2:
        state.settings["game_mode"] = 2
        save_settings(state.settings)
        sound_mgr.play_menu_tick()
    elif ctx.key == 9:   # Tab: toggle AI / 2-Player
        state.settings["ai_enabled"] = not state.settings["ai_enabled"]
        save_settings(state.settings)
        sound_mgr.play_menu_tick()
    elif ctx.key in (ord('m'), ord('M')):
        state.settings_return_state = "START"
        state.game_state = "SETTINGS"

    # ── Space or Enter starts the game ────────────────────────────
    if ctx.key in (ord(' '), 13):
        _do_start_game(ctx, state, sound_mgr)
        return

    # ── Wave-both-hands gesture ───────────────────────────────────
    if ctx.hand_pos["Left"] is not None and ctx.hand_pos["Right"] is not None:
        if state.start_gesture_time is None:
            state.start_gesture_time = ctx.current_time
        elif ctx.current_time - state.start_gesture_time >= GESTURE_REQUIRED_DURATION:
            _do_start_game(ctx, state, sound_mgr)
    else:
        state.start_gesture_time = None

    # ── Mouse clicks ─────────────────────────────────────────────
    _mx, _my = ctx.mouse_pos
    if ctx.mouse_clicked and 0 <= _mx <= WINDOW_WIDTH:
        cx_w = WINDOW_WIDTH // 2
        # "PRESS SPACE TO START" area (y=205 in new layout)
        if (cx_w - 380 <= _mx <= cx_w + 380) and (183 <= _my <= 233):
            _do_start_game(ctx, state, sound_mgr)
        # Mode card clicks (y=270–350)
        elif 270 <= _my <= 350:
            card_w_c, card_gap_c = 340, 15
            x0_c = cx_w - (3 * card_w_c + 2 * card_gap_c) // 2
            for i in range(3):
                x1_c = x0_c + i * (card_w_c + card_gap_c)
                if x1_c <= _mx <= x1_c + card_w_c:
                    if state.settings["game_mode"] != i:
                        state.settings["game_mode"] = i
                        save_settings(state.settings)
                        sound_mgr.play_menu_tick()
                    break
        # Player card clicks (y=374–432)
        elif 374 <= _my <= 432:
            p_card_w, p_gap = 500, 20
            p_x0 = cx_w - (2 * p_card_w + p_gap) // 2
            for i in range(2):
                x1_c = p_x0 + i * (p_card_w + p_gap)
                if x1_c <= _mx <= x1_c + p_card_w:
                    want_ai = (i == 1)
                    if state.settings["ai_enabled"] != want_ai:
                        state.settings["ai_enabled"] = want_ai
                        save_settings(state.settings)
                        sound_mgr.play_menu_tick()
                    break


_settings_last_mouse_pos: tuple = (-1, -1)
_settings_mouse_active: bool = False
_SETTINGS_NAV_KEYS = frozenset([
    ord('w'), ord('W'), ord('s'), ord('S'),
    ord('a'), ord('A'), ord('d'), ord('D'),
])
_SETTINGS_NAV_RAW = frozenset([2490368, 2621440, 2424832, 2555904])  # UP DOWN LEFT RIGHT


def handle_settings(ctx: FrameCtx, state, sound_mgr) -> None:
    global _settings_last_mouse_pos, _settings_mouse_active

    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    screens.show_settings_screen(ctx.frame, state)

    # Keyboard navigation → keyboard claims control
    _k = ctx.key_raw & 0xFF if ctx.key_raw != -1 else 255
    if _k in _SETTINGS_NAV_KEYS or ctx.key_raw in _SETTINGS_NAV_RAW:
        _settings_mouse_active = False

    new_state = screens.handle_settings_input(ctx.key_raw, state, sound_mgr)
    if new_state:
        # ESC from settings returns to wherever we came from (START or MENU)
        state.game_state = state.settings_return_state if new_state == "START" else new_state

    # Mouse moves > 5 px → mouse reclaims control
    _mx, _my = ctx.mouse_pos
    _lx, _ly = _settings_last_mouse_pos
    if _lx >= 0:
        dx, dy = _mx - _lx, _my - _ly
        if dx * dx + dy * dy > _MOUSE_THRESH_SQ:
            _settings_mouse_active = True
    _settings_last_mouse_pos = (_mx, _my)

    # Hover highlight: only in mouse mode. Clicks always work.
    if 0 <= _mx <= WINDOW_WIDTH:
        cx = WINDOW_WIDTH // 2
        start_y = 100
        s = state.settings
        for i in range(10):
            y = start_y + 65 + i * 42
            if (cx - 280 <= _mx <= cx + 280) and (y - 25 <= _my <= y + 10):
                if _settings_mouse_active and s["selected_setting"] != i:
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


# Last recorded mouse position and whether the mouse is currently "driving"
# menu navigation. Keyboard press claims control; mouse must move more than
# _MOUSE_THRESH pixels to reclaim it — filters out jitter on the same frame.
_menu_last_mouse_pos: tuple = (-1, -1)
_menu_mouse_active: bool = False
_MOUSE_THRESH_SQ: int = 25          # 5 px radius squared


def handle_menu(ctx: FrameCtx, state, sound_mgr) -> None:
    global _menu_last_mouse_pos, _menu_mouse_active

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
        _menu_mouse_active = False          # keyboard claims control
    elif ctx.key in (ord('s'), ord('S')) or ctx.key_raw == DOWN:
        state.menu_selection = (state.menu_selection + 1) % n
        sound_mgr.play_menu_tick()
        _menu_mouse_active = False          # keyboard claims control
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

    # Mouse hover — only when the mouse has moved enough to reclaim control
    _mx, _my = ctx.mouse_pos
    _lx, _ly = _menu_last_mouse_pos
    if _lx >= 0:                             # skip on the very first frame
        dx, dy = _mx - _lx, _my - _ly
        if dx * dx + dy * dy > _MOUSE_THRESH_SQ:
            _menu_mouse_active = True        # deliberate mouse movement
    _menu_last_mouse_pos = (_mx, _my)

    if _menu_mouse_active and 0 <= _mx <= WINDOW_WIDTH:
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
