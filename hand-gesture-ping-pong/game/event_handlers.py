"""Tournament (event) screens' handlers - the walk-up kiosk flow:

    EVENT_HOME (leaderboard) -> EVENT_NAME -> COUNTDOWN/PLAYING -> GAMEOVER -> EVENT_HOME
    FINALS_HOME (bracket)    -> COUNTDOWN/PLAYING -> GAMEOVER -> FINALS_HOME
"""

from game import modes
from game.config import (EVENT_RESULT_SECONDS, FINALS_RESULT_SECONDS, TIME_LIMIT_MAX, TIME_LIMIT_MIN,
                         TIME_LIMIT_STEP)
from game import event_screens, menu_screens, renderer
from game import history, keys, stats as stats_mod
from game.flow import FrameCtx, do_start_game, in_rect
from game.stats import record_game_result, save_settings, clean_name, NAME_CHARS, NAME_MAX_LEN, set_event_overrides


def _help_overlay(ctx: FrameCtx, state) -> bool:
    """HOW TO PLAY on the leaderboard / bracket (H opens; H, Esc, Enter, Space or a click closes).
    Returns True while it is up, so nothing underneath reacts."""
    if state.show_help:
        menu_screens.draw_help_overlay(ctx.frame, state)
        if ctx.key in (27, 13, 32, ord('h'), ord('H')) or ctx.mouse_clicked:
            state.show_help = False
        return True
    if ctx.key in (ord('h'), ord('H')):
        state.show_help = True
        return True
    return False


def _tournament_exit_dialog(ctx: FrameCtx, state, sound_mgr) -> bool:
    """Organiser only (keyboard): Esc asks, Y leaves the tournament, N / Esc stays.
    Returns True while the dialog is up (it takes all input)."""
    if state.tournament_exit_confirm:
        event_screens.draw_tournament_exit_dialog(ctx.frame, state)
        if ctx.key in (ord('y'), ord('Y')):
            modes.leave_tournament(state)
        elif ctx.key in (ord('n'), ord('N'), 27):
            state.tournament_exit_confirm = False
        return True
    if ctx.key == 27:
        state.tournament_exit_confirm = True
        sound_mgr.play_menu_tick()
        return True
    return False


def handle_event_home(ctx: FrameCtx, state, stats, sound_mgr) -> None:
    if not sound_mgr.lobby_playing and state.settings["sound_enabled"]:
        sound_mgr.start_lobby_music(state.settings["music_volume"])

    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    event_screens.show_event_home(ctx.frame, state)
    if _help_overlay(ctx, state):
        return
    if _tournament_exit_dialog(ctx, state, sound_mgr):
        return
    if ctx.key in (ord('-'), ord('+'), ord('=')):             # organiser: game length, 15 s steps
        step = -TIME_LIMIT_STEP if ctx.key == ord('-') else TIME_LIMIT_STEP
        lim = max(TIME_LIMIT_MIN, min(TIME_LIMIT_MAX, state.settings["time_limit"] + step))
        if lim != state.settings["time_limit"]:
            state.settings["time_limit"] = lim
            save_settings(state.settings)
            sound_mgr.play_menu_tick()

    # Keyboard / mouse only: bystanders walking past with their hands up must
    # not be able to start a game with someone else's name (or none).
    if ctx.key in (13, 32) or ctx.mouse_clicked:
        state.name_edit_buf = ["", ""]
        state.event_side = 0
        state.game_state = "EVENT_NAME"


def handle_event_name(ctx: FrameCtx, state, sound_mgr, tracker) -> None:
    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    event_screens.show_event_home(ctx.frame, state)
    event_screens.draw_event_name_dialog(ctx.frame, state)

    board = state.event_board
    buf = state.name_edit_buf[0]
    k = ctx.key

    if ctx.mouse_clicked:
        for i, r in enumerate(event_screens.event_side_rects()):
            if in_rect(*ctx.mouse_pos, r) and state.event_side != i:
                state.event_side = i
                sound_mgr.play_menu_tick()
    if ctx.key_raw in (keys.LEFT, keys.RIGHT) or k == 9:      # Tab / arrows: switch side
        want = 1 if ctx.key_raw == keys.RIGHT else (0 if ctx.key_raw == keys.LEFT else 1 - state.event_side)
        if want != state.event_side:
            state.event_side = want
            sound_mgr.play_menu_tick()
    if k == 27:                                       # Esc: back to the leaderboard
        state.game_state = "EVENT_HOME"
    elif k == 13:                                     # Enter: start (if allowed)
        name = clean_name(buf, "")
        if name and board.attempts(name) < state.event_max_attempts:
            name = board.display_name(name)
            state.event_player = name
            state.event_last_player = ""
            set_event_overrides(state.settings, {"player1_name": name,      # shown in the HUD; never saved
                                                 "player_side": state.event_side})   # 0: CPU on the right, 1: on the left
            tracker.reset_calibration()               # fresh hand calibration per player
            do_start_game(ctx, state, sound_mgr)
        else:
            sound_mgr.play_lose()                     # empty name / no attempts left
    elif k == 8:
        state.name_edit_buf[0] = buf[:-1]
    elif 32 <= k < 127 and chr(k) in NAME_CHARS and len(buf) < NAME_MAX_LEN:
        state.name_edit_buf[0] = buf + chr(k)


def _log_finals_events(state, res, ctx_time):
    """CSV rows + on-screen notice for a withdrawal's consequences."""
    notes = []
    if res.get("replacement"):
        notes.append(f"{res['name']} WITHDREW - {res['replacement']} TAKES THEIR PLACE")
    elif res["name"]:
        notes.append(f"{res['name']} WITHDREW")
    for w in res["walkovers"]:
        history.record_finals_match(w)
        notes.append(f"{w['winner']} ADVANCES BY WALKOVER ({w['label']})")
    state.finals_notice = ("   -   ".join(notes), ctx_time + 10.0)


def _handle_finals_withdraw(ctx: FrameCtx, state, sound_mgr) -> None:
    """Organiser dialog: 1-9 pick the player, Y confirms, N / Esc cancels."""
    w, f = state.finals_withdraw, state.finals
    k = ctx.key
    if k == 27:
        state.finals_withdraw = None
    elif w["pick"] is None:
        if ord('1') <= k < ord('1') + min(9, len(w["names"])):
            w["pick"] = w["names"][k - ord('1')]
            sound_mgr.play_menu_tick()
    elif k in (ord('n'), ord('N')):
        w["pick"] = None
    elif k in (ord('y'), ord('Y')):
        name = w["pick"]
        state.finals_withdraw = None
        try:
            res = f.withdraw(name)
        except ValueError as e:
            print(f"WARNING: withdraw failed: {e}")
            return
        f.save(stats_mod._write_json)
        history.record_finals_match({"label": "WITHDRAWAL", "p1": name, "p2": "", "s1": "", "s2": "",
                                     "winner": "", "note": (f"replaced by {res['replacement']}"
                                                            if res["replacement"] else "no replacement")})
        _log_finals_events(state, res, ctx.current_time)


def handle_finals_home(ctx: FrameCtx, state, stats, sound_mgr, tracker) -> None:
    """Bracket / podium screen between finals matches."""
    if not sound_mgr.lobby_playing and state.settings["sound_enabled"]:
        sound_mgr.start_lobby_music(state.settings["music_volume"])

    renderer.draw_animated_bg(ctx.frame, state, ctx.theme)
    event_screens.show_finals_home(ctx.frame, state)
    if state.settings["show_hand_skeleton"] and state.finals and not state.finals.complete:
        renderer.draw_hand_skeletons(ctx.frame, state, ctx.mp_hand_connections)

    if state.finals_withdraw is not None:             # dialog open: it takes all input
        event_screens.draw_finals_withdraw_dialog(ctx.frame, state)
        _handle_finals_withdraw(ctx, state, sound_mgr)
        return
    if _help_overlay(ctx, state):
        return
    if _tournament_exit_dialog(ctx, state, sound_mgr):
        return
    if (ctx.key in (ord('w'), ord('W')) and state.finals is not None
            and not state.finals.complete):
        names = state.finals.alive()
        if names:
            state.finals_withdraw = {"names": names, "pick": None}
        return

    nxt = state.finals.next_match() if state.finals else None
    if nxt and (ctx.key in (13, 32) or ctx.mouse_clicked):
        state.finals_match = nxt
        # Names / target score for this match.  Overrides, so none of it is saved.
        set_event_overrides(state.settings, {"player1_name": nxt["p1"], "player2_name": nxt["p2"],
                                             "score_to_win": nxt["target"]})
        tracker.reset_calibration()
        do_start_game(ctx, state, sound_mgr)


def _handle_finals_gameover(ctx: FrameCtx, state, stats, sound_mgr) -> None:
    f, m = state.finals, state.finals_match
    if not state.stats_saved:
        record_game_result(stats, state)
        history.record_game(state)
        try:
            res = f.record(m["id"], state.score[0], state.score[1])
            f.save(stats_mod._write_json)
            history.record_finals_match(res)
            for w in res["walkovers"]:                  # a next opponent had already withdrawn
                history.record_finals_match(w)
            if res["walkovers"]:
                state.finals_notice = ("   -   ".join(
                    f"{w['winner']} ADVANCES BY WALKOVER ({w['label']})" for w in res["walkovers"]),
                    ctx.current_time + FINALS_RESULT_SECONDS + 10.0)
            res["next"] = f.next_match()
            res["complete"] = f.complete
            state.finals_result = res
        except ValueError as e:                     # shouldn't happen; never strand the screen
            print(f"WARNING: finals result not recorded: {e}")
            state.finals_result = None
        state.event_result_until = ctx.current_time + FINALS_RESULT_SECONDS
        state.stats_saved = True
        sound_mgr.stop_bgm()
        sound_mgr.play_gameover()

    if state.finals_result is not None:
        event_screens.show_finals_result(ctx.frame, state)
    shown = ctx.current_time - (state.event_result_until - FINALS_RESULT_SECONDS)
    if (state.finals_result is None or ctx.current_time >= state.event_result_until
            or (shown > 2.0 and (ctx.key in (13, 32) or ctx.mouse_clicked))):
        state.finals_result = None
        state.finals_match = None
        state.game_state = "FINALS_HOME"


def _handle_event_gameover(ctx: FrameCtx, state, stats, sound_mgr) -> None:
    if state.finals is not None:
        _handle_finals_gameover(ctx, state, stats, sound_mgr)
        return
    if not state.stats_saved:
        record_game_result(stats, state)
        history.record_game(state)
        me = 1 if state.cpu_side() == "left" else 0          # the person's paddle: their score first
        state.event_result = state.event_board.add(
            state.event_player, state.score[me], state.score[1 - me],
            state.max_rally, state.max_combo, state.total_hits)
        state.event_last_player = state.event_player
        state.event_result_until = ctx.current_time + EVENT_RESULT_SECONDS
        state.stats_saved = True
        sound_mgr.stop_bgm()
        sound_mgr.play_gameover()

    event_screens.show_event_result(ctx.frame, state)

    # Next player: after the timeout, or when the volunteer presses Space/Enter
    # (not in the first 2 s, so a key press from the game itself can't skip it).
    shown = ctx.current_time - (state.event_result_until - EVENT_RESULT_SECONDS)
    if (ctx.current_time >= state.event_result_until
            or (shown > 2.0 and (ctx.key in (13, 32) or ctx.mouse_clicked))):
        state.event_result = None
        state.game_state = "EVENT_HOME"
