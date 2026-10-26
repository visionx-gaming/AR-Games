"""Per-state handler functions extracted from the main game loop.

Each handler receives a FrameCtx (per-frame read-only snapshot) plus the
mutable objects it needs, performs all rendering and input for its state,
and may transition state.game_state.
"""


from game import event_handlers, modes, powerups
from game.flow import FrameCtx, in_rect, do_start_game
from game.config import COUNTDOWN_DURATION, GESTURE_REQUIRED_DURATION, GAME_MODE_NAMES
from game import effects, engine, hud, menu_screens, renderer, settings_screen
from game import keys, history, stats as stats_mod
from game.stats import record_game_result, save_settings, clean_name, NAME_CHARS, NAME_MAX_LEN


# ===================================================================
#  HANDLERS
# ===================================================================

_LEFT_RAW = keys.LEFT
_RIGHT_RAW = keys.RIGHT
_exit_confirm_sel: int = 1   # 0=YES  1=NO; default to NO for safety


def _resume_play(ctx, state):
    """Resume a paused game through a 3-2-1 countdown (ball and score are kept)."""
    state.countdown_start = ctx.current_time
    state.game_state = "COUNTDOWN"
    state.fist_pause_cooldown = 1.5


def _menu_resume(ctx, state):
    """Leave the in-game menu and return to where it was opened from."""
    prev = state.previous_state
    if prev == "PLAYING":
        _resume_play(ctx, state)
    elif prev == "COUNTDOWN":
        state.countdown_start = ctx.current_time   # restart the interrupted countdown
        state.game_state = "COUNTDOWN"
    else:
        state.game_state = prev or "PAUSED"


def _menu_select(ctx, state, sound_mgr, sel):
    """Run in-game menu item `sel` (Resume / Settings / Main Menu / Quit)."""
    if sel == 0:
        _menu_resume(ctx, state)
    elif sel == 1:
        state.settings_return_state = "MENU"
        state.game_state = "SETTINGS"
    elif sel == 2:
        sound_mgr.stop_bgm()
        if state.settings["sound_enabled"]:
            sound_mgr.start_lobby_music(state.settings["music_volume"])
        state.previous_state = ""
        state.gesture_armed = False
        state.start_gesture_time = None
        if state.event_mode:
            # Tournament: drop this game (nothing is recorded, the attempt is not used up)
            # and go back to the leaderboard / bracket for the organiser
            state.game_state = "FINALS_HOME" if state.finals is not None else "EVENT_HOME"
        else:
            state.game_state = "START"
    elif sel == 3:
        state.game_state = "QUIT"


def _restart_game(ctx, state, sound_mgr):
    """GAMEOVER -> COUNTDOWN for a rematch."""
    state.reset_for_new_game()
    state.countdown_start = ctx.current_time
    state.game_state = "COUNTDOWN"
    state.restart_gesture_time = None
    powerups.init_obstacles(state)
    if state.settings["sound_enabled"] and not sound_mgr.bgm_playing:
        sound_mgr.start_bgm(state.settings["music_volume"])


def _open_name_editor(state):
    state.name_edit_active = True
    state.name_edit_field = 0
    state.name_edit_buf = [state.settings["player1_name"], state.settings["player2_name"]]
    state.start_gesture_time = None


def _handle_name_editor(ctx, state, sound_mgr):
    """Keyboard / mouse input for the player-name dialog."""
    f = state.name_edit_field
    buf = state.name_edit_buf
    k = ctx.key

    if ctx.mouse_clicked:
        for i, (x1, y1, x2, y2) in enumerate(menu_screens.name_field_rects()):
            if x1 <= ctx.mouse_pos[0] <= x2 and y1 <= ctx.mouse_pos[1] <= y2:
                state.name_edit_field = i
                sound_mgr.play_menu_tick()

    if k == 27:                                        # Esc: discard
        state.name_edit_active = False
    elif k == 13:                                      # Enter: next field, then save
        if f == 0:
            state.name_edit_field = 1
            sound_mgr.play_menu_tick()
        else:
            state.settings["player1_name"] = clean_name(buf[0], "PLAYER 1")
            state.settings["player2_name"] = clean_name(buf[1], "PLAYER 2")
            save_settings(state.settings)
            state.name_edit_active = False
            sound_mgr.play_menu_tick()
    elif k == 9 or ctx.key_raw in (keys.UP, keys.DOWN):
        state.name_edit_field = 1 - f
        sound_mgr.play_menu_tick()
    elif k == 8:                                       # Backspace
        buf[f] = buf[f][:-1]
    elif 32 <= k < 127 and chr(k) in NAME_CHARS and len(buf[f]) < NAME_MAX_LEN:
        buf[f] += chr(k)


def handle_start(ctx: FrameCtx, state, stats, sound_mgr, tracker) -> None:
    global _exit_confirm_sel

    if not sound_mgr.lobby_playing and state.settings["sound_enabled"]:
        sound_mgr.start_lobby_music(state.settings["music_volume"])

    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)

    if state.settings["show_hand_skeleton"]:
        renderer.draw_hand_skeletons(ctx.frame, state, ctx.mp_hand_connections)

    menu_screens.show_start_screen(ctx.frame, state, stats)

    # ── How-to-play overlay (any of H / Esc / Enter / Space / a click closes it) ──
    if state.show_help:
        menu_screens.draw_help_overlay(ctx.frame, state)
        if ctx.key in (27, 13, 32, ord('h'), ord('H')) or ctx.mouse_clicked:
            state.show_help = False
        return
    if ctx.key in (ord('h'), ord('H')) and not state.name_edit_active and not state.show_exit_confirm:
        state.show_help = True
        return

    # ── Player-name dialog (takes all input while open) ───────────
    if state.name_edit_active:
        menu_screens.draw_name_dialog(ctx.frame, state)
        _handle_name_editor(ctx, state, sound_mgr)
        return

    # ── Exit confirmation dialog ──────────────────────────────────
    if state.show_exit_confirm:
        menu_screens.draw_exit_confirm_dialog(ctx.frame, state, _exit_confirm_sel)

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

        # Mouse hover + click (button rects come from the screen that draws them)
        mx, my = ctx.mouse_pos
        rects = menu_screens.exit_button_rects()
        over = {k: in_rect(mx, my, r) for k, r in rects.items()}
        prev = _exit_confirm_sel
        if over["yes"]:
            _exit_confirm_sel = 0
        elif over["no"]:
            _exit_confirm_sel = 1
        if _exit_confirm_sel != prev:
            sound_mgr.play_menu_tick()
        if ctx.mouse_clicked:
            if over["yes"]:
                state.game_state = "QUIT"
            elif over["no"]:
                state.show_exit_confirm = False
                _exit_confirm_sel = 1
        return  # consume all input while dialog is open

    # ── ESC opens exit confirmation ───────────────────────────────
    if ctx.key == 27:
        state.show_exit_confirm = True
        _exit_confirm_sel = 1
        return

    # ── Keyboard shortcuts (1/2/3 pick a mode, Tab swaps 2P/CPU) ──
    if ctx.key in (ord('1'), ord('2'), ord('3')):
        mode = ctx.key - ord('1')
        if state.settings["game_mode"] != mode:
            state.settings["game_mode"] = mode
            save_settings(state.settings)
            sound_mgr.play_menu_tick()
    elif ctx.key == 9:   # Tab: 2 players -> CPU on the right -> CPU on the left
        state.set_player_mode(state.player_mode() + 1)
        save_settings(state.settings)
        sound_mgr.play_menu_tick()
    elif ctx.key in (ord('m'), ord('M')):
        state.settings_return_state = "START"
        state.game_state = "SETTINGS"
        return
    elif ctx.key in (ord('n'), ord('N')):
        _open_name_editor(state)
        return

    # ── Space starts the game ─────────────────────────────────────
    if ctx.key == ord(' '):
        do_start_game(ctx, state, sound_mgr)
        return

    # ── Show-both-hands gesture ───────────────────────────────────
    # Edge-triggered: hands must first be seen away after entering this
    # screen, so returning here with both hands up never auto-starts a game.
    if ctx.hand_pos["Left"] is None or ctx.hand_pos["Right"] is None:
        state.gesture_armed = True
        state.start_gesture_time = None
    elif state.gesture_armed:
        if state.start_gesture_time is None:
            state.start_gesture_time = ctx.current_time
        elif ctx.current_time - state.start_gesture_time >= GESTURE_REQUIRED_DURATION:
            do_start_game(ctx, state, sound_mgr)
            return

    # ── Menu widgets: W/S move, A/D change, Enter/click select ─────
    n_modes = len(GAME_MODE_NAMES)
    items, rects = menu_screens.start_items(state), menu_screens.start_rects()
    for ev in menu_screens.VIEWS["start"].input(ctx, items, rects, activate_keys=(13,)):
        kind, iid = ev[0], ev[1]
        if kind == "focus":
            sound_mgr.play_menu_tick()
        elif kind == "activate":
            if iid == "play":
                do_start_game(ctx, state, sound_mgr)
                return
            if iid == "names":
                _open_name_editor(state)
                return
            if iid == "qualifier":
                modes.enter_qualifier(state)
                sound_mgr.play_menu_tick()
                return
            if iid == "finals":
                modes.enter_finals(state)
                sound_mgr.play_menu_tick()
                return
            if iid == "settings":
                state.settings_return_state = "START"
                state.game_state = "SETTINGS"
                return
            if iid == "exit":
                state.show_exit_confirm = True
                _exit_confirm_sel = 1
                return
        elif kind == "adjust" and iid == "mode":
            state.settings["game_mode"] = (state.settings["game_mode"] + ev[2]) % n_modes
            save_settings(state.settings)
            sound_mgr.play_menu_tick()
        elif kind == "adjust" and iid == "players":
            state.set_player_mode(state.player_mode() + ev[2])
            save_settings(state.settings)
            sound_mgr.play_menu_tick()
        elif kind == "set" and iid == "players":
            state.set_player_mode(ev[2])
            save_settings(state.settings)
            sound_mgr.play_menu_tick()


def handle_settings(ctx: FrameCtx, state, sound_mgr) -> None:
    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    # Draws the screen and handles all its input; True = leave (Esc)
    if settings_screen.settings_screen(ctx, state, sound_mgr):
        # Back to wherever we came from (main menu or the in-game menu)
        state.game_state = state.settings_return_state


def handle_countdown(ctx: FrameCtx, state, tracker) -> None:
    engine.apply_keyboard_paddles(state, ctx.key, ctx.key_raw)
    engine.update_paddles(state)
    effects.update_effects(state, ctx.dt)

    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    renderer.draw_court(ctx.frame, state, ctx.theme)

    if state.settings["obstacles_enabled"]:
        renderer.draw_obstacles(ctx.frame, state, ctx.theme)

    renderer.draw_paused_balls(ctx.frame, state, ctx.theme)
    renderer.draw_paddles(ctx.frame, state, ctx.theme, ctx.glow_layer)
    renderer.apply_glow(ctx.frame, ctx.glow_layer)
    renderer.draw_shockwaves(ctx.frame, state)
    renderer.draw_particles(ctx.frame, state)
    renderer.draw_floating_texts(ctx.frame, state)
    hud.draw_hud(ctx.frame, state, ctx.theme)

    if state.settings["show_hand_skeleton"]:
        renderer.draw_hand_skeletons(ctx.frame, state, ctx.mp_hand_connections)

    menu_screens.show_countdown_screen(ctx.frame, state)

    elapsed = ctx.current_time - state.countdown_start
    if elapsed >= COUNTDOWN_DURATION + 0.5:
        # Between points / after a resume the ball already exists; only a
        # fresh game needs one created here.
        if not any(b.is_main for b in state.balls):
            engine.reset_ball(state)
        state.game_state = "PLAYING"


def handle_playing(ctx: FrameCtx, state, sound_mgr, tracker) -> None:
    if (state.settings.get("fist_pause_enabled", False)
            and ctx.fist_state["Left"] and ctx.fist_state["Right"]
            and state.fist_pause_cooldown <= 0):
        state.game_state = "PAUSED"
        state.pause_by_key = False
        state.fist_pause_cooldown = 1.5
        return

    state.game_time += ctx.dt
    engine.apply_keyboard_paddles(state, ctx.key, ctx.key_raw)
    engine.update_paddles(state)
    engine.step_physics(state, sound_mgr, ctx.dt)
    if state.game_state == "PLAYING":
        powerups.update_powerups(state, sound_mgr)
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
    hud.draw_hud(ctx.frame, state, ctx.theme)
    hud.draw_hand_lost(ctx.frame, state)

    if state.settings["show_hand_skeleton"]:
        renderer.draw_hand_skeletons(ctx.frame, state, ctx.mp_hand_connections)

    if ctx.key in (ord('p'), ord('P')):
        state.game_state = "PAUSED"
        state.pause_by_key = True
        state.fist_pause_cooldown = 1.5


def handle_paused(ctx: FrameCtx, state, sound_mgr) -> None:
    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    renderer.draw_court(ctx.frame, state, ctx.theme)

    if state.settings["obstacles_enabled"]:
        renderer.draw_obstacles(ctx.frame, state, ctx.theme)

    renderer.draw_paddles(ctx.frame, state, ctx.theme)
    renderer.draw_paused_balls(ctx.frame, state, ctx.theme)
    menu_screens.show_pause_screen(ctx.frame, state)
    renderer.draw_particles(ctx.frame, state)

    if ctx.key in (ord('r'), ord('R')):
        _resume_play(ctx, state)
        return
    # Hand-resume only for a gesture pause: a keyboard pause (P) stays paused
    # until the player resumes it, even though their hands are in view.
    if (not state.pause_by_key
            and not ctx.fist_state["Left"] and not ctx.fist_state["Right"]
            and ctx.hand_pos["Left"] is not None
            and ctx.hand_pos["Right"] is not None
            and state.fist_pause_cooldown <= 0):
        _resume_play(ctx, state)
        return

    # Mouse: the RESUME button
    if ctx.mouse_clicked and in_rect(*ctx.mouse_pos, menu_screens.pause_resume_rect()):
        _resume_play(ctx, state)


def handle_menu(ctx: FrameCtx, state, sound_mgr) -> None:
    # Draw frozen game state beneath the overlay
    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    renderer.draw_court(ctx.frame, state, ctx.theme)
    if state.settings["obstacles_enabled"]:
        renderer.draw_obstacles(ctx.frame, state, ctx.theme)
    renderer.draw_paddles(ctx.frame, state, ctx.theme)
    renderer.draw_paused_balls(ctx.frame, state, ctx.theme)

    chosen = menu_screens.menu_screen(ctx, state, sound_mgr)    # draws + handles W/S/Enter/mouse
    if ctx.key == 27:                                       # ESC → resume
        _menu_resume(ctx, state)
    elif chosen is not None:
        _menu_select(ctx, state, sound_mgr, chosen)


# Seconds the result screen stays up before hand gestures can restart.
_GAMEOVER_GESTURE_LOCKOUT = 2.0


def handle_gameover(ctx: FrameCtx, state, stats, sound_mgr) -> None:
    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    effects.update_effects(state, ctx.dt)
    renderer.draw_particles(ctx.frame, state)

    if state.event_mode:
        event_handlers._handle_event_gameover(ctx, state, stats, sound_mgr)
        return

    if not state.stats_saved:
        state.new_best = record_game_result(stats, state)
        history.record_game(state)
        state.high_score = stats_mod.high_score_value(stats, state.settings["game_mode"])
        state.stats_saved = True
        sound_mgr.stop_bgm()
        sound_mgr.play_gameover()

    menu_screens.show_game_over_screen(ctx.frame, state, stats)

    # Space / Enter also restarts
    if ctx.key in (13, ord(' ')):
        _restart_game(ctx, state, sound_mgr)
        return

    # Hand restart is edge-triggered and locked out briefly so the players
    # (still holding both hands up) can read the result first.
    if ctx.hand_pos["Left"] is None or ctx.hand_pos["Right"] is None:
        state.gesture_armed = True
        state.restart_gesture_time = None
    elif (state.gesture_armed
            and ctx.current_time - state.gameover_time >= _GAMEOVER_GESTURE_LOCKOUT):
        if state.restart_gesture_time is None:
            state.restart_gesture_time = ctx.current_time
        elif ctx.current_time - state.restart_gesture_time >= GESTURE_REQUIRED_DURATION:
            _restart_game(ctx, state, sound_mgr)
            return

    # Mouse: PLAY AGAIN / MAIN MENU buttons
    if ctx.mouse_clicked:
        r = menu_screens.gameover_rects()
        if in_rect(*ctx.mouse_pos, r["rematch"]):
            _restart_game(ctx, state, sound_mgr)
        elif in_rect(*ctx.mouse_pos, r["menu"]):
            state.gesture_armed = False
            state.start_gesture_time = None
            state.game_state = "START"
