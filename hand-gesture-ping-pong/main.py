"""Hand Pong — Main entry point and game loop.

An AR ping-pong game controlled by hand gestures via webcam.
Run:  python main.py
"""

import os
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")  # before cv2 import

import argparse
import numpy as np
import pygame
import time

from game.config import MAX_FPS, EVENT_MAX_ATTEMPTS, get_theme
from game.state import GameState
from game.sound import SoundManager
from game.stats import load_stats, load_settings, save_settings, set_event_overrides
from game.hand_tracking import HandTracker
from game.camera import open_camera
from game.system import System
from game.display import Display
from game import modes
from game.utils import detect_screen_resolution, fit_to_window
from game import gfx, ui
from game import effects, hud, renderer
from game.flow import FrameCtx
from game.handlers import handle_start, handle_settings, handle_countdown
from game.handlers import handle_playing, handle_paused, handle_gameover, handle_menu
from game.event_handlers import handle_event_home, handle_event_name, handle_finals_home
from game import crashlog

crashlog.install()          # unhandled + native crashes are recorded in crash_log.txt

_parser = argparse.ArgumentParser(description="Hand Pong")
_parser.add_argument("--event", action="store_true",
                     help="tournament mode: walk-up 60 s Time Attack vs CPU with a live leaderboard")
_parser.add_argument("--finals", action="store_true",
                     help="finals: top-4 knockout bracket seeded from the qualifier (event_results.csv)")
_parser.add_argument("--restart-finals", action="store_true",
                     help="with --finals: throw away the saved bracket and seed it again")
_parser.add_argument("--attempts", type=int, default=EVENT_MAX_ATTEMPTS,
                     help="attempts allowed per person in event mode (default %(default)s)")
_parser.add_argument("--difficulty", choices=("easy", "medium", "hard"), default="medium",
                     help="CPU difficulty in event mode (default %(default)s)")
_parser.add_argument("--no-camera-feed", action="store_true",
                     help="hide the camera picture for this run (tracking still works; not saved)")
_parser.add_argument("--no-fist-pause", action="store_true",
                     help="disable the two-fists pause gesture for this run (P still pauses)")
args = _parser.parse_args()

# =====================================================================
#  INITIALIZATION
# =====================================================================
pygame.init()
sound_mgr = SoundManager()
stats = load_stats()
state = GameState()

# Restore settings saved from the previous session
_saved = load_settings()
state.settings.update(_saved)
sound_mgr.set_bgm_volume(state.settings["music_volume"])
sound_mgr.set_sfx_volume(state.settings["sfx_volume"])
if not state.settings["sound_enabled"]:
    sound_mgr.update_enabled(False)

if args.no_fist_pause:
    # Tournament: an accidental double fist must never interrupt a match (P still pauses)
    set_event_overrides(state.settings, {"fist_pause_enabled": False})

if args.no_camera_feed:
    set_event_overrides(state.settings, {"show_camera_feed": False})

if args.event and not args.finals:
    modes.enter_qualifier(state, {"easy": 0, "medium": 1, "hard": 2}[args.difficulty], args.attempts)
    print(f"EVENT MODE: Time Attack vs CPU ({args.difficulty}), {state.event_max_attempts} attempt(s) "
          f"each, {len(state.event_board.ranking())} players already on the board.")

if args.finals:
    modes.enter_finals(state, {"easy": 0, "medium": 1, "hard": 2}[args.difficulty], args.restart_finals)
    print("FINALS:", state.finals_error or
          f"bracket ready, {len(state.finals.results)} match(es) already played.")

# Also makes the process DPI-aware, which must happen before the window exists
detect_screen_resolution()

# The window is shown through SDL (see game/display.py), on the monitor and in the
# mode saved in the settings (a monitor that is no longer attached falls back to the
# primary one; a windowed game opens at the largest 16:9 size that fits that monitor).
# Its size is re-read every frame, so the game renders natively at whatever resolution
# the window / monitor has (see game/gfx.py), up to the render cap set in Settings.
display = Display("Hand Pong", None, state.settings["display_index"], state.settings["fullscreen"])
gfx.set_render_cap(state.settings["render_height"])
gfx.set_k(gfx.k_for_size(*display.size))

camera = open_camera(state.settings.get("camera_index", 0), state.settings.get("camera_quality", 0))
if camera.ok:
    state.settings["camera_index"] = camera.index
    print(f"Using camera {camera.index}: {camera.size[0]}x{camera.size[1]} "
          f"@ {camera.fps:.0f} fps (press C to switch cameras).")
else:
    print("WARNING: no webcam found - running with keyboard/mouse controls only.")
camera_toast = ""
camera_toast_until = 0.0
last_cam_seq = -1
cam_frame = None      # newest camera frame (mirrored and fitted by the camera thread)

tracker = HandTracker()
tracker.start()


def show_toast(text, seconds=3.0):
    global camera_toast, camera_toast_until
    camera_toast, camera_toast_until = text, time.monotonic() + seconds


def _attach_camera(cam):
    cam.on_small = tracker.send_frame     # frames go camera thread -> tracker directly


_attach_camera(camera)
# Display / camera control for the Settings screen and the C / F hotkeys
system = System(display, camera, state.settings, save_settings, _attach_camera, show_toast, tracker.stats_text)
state.system = system


def _rebuild_render_buffers():
    """(Re)create everything sized to the render frame; run when the render
    resolution changes."""
    global post_overlay, frame_buf
    post_overlay = renderer.create_post_overlay()
    fw, fh = gfx.frame_size()
    frame_buf = np.empty((fh, fw, 3), dtype=np.uint8)
    system.set_target_size((fw, fh))


_rebuild_render_buffers()
glow_layer = renderer.create_glow_layer()   # small, fixed size (see renderer.apply_glow)

clock = pygame.time.Clock()
shown_state, state_entered = state.game_state, 0.0
last_mouse_pos, last_mouse_move, last_click = (-1, -1), 0.0, None
last_time = time.monotonic()
frame_count = 0
fps_display = 0
fps_update_time = time.monotonic()

_HANDLERS = {
    "START":     handle_start,
    "SETTINGS":  handle_settings,
    "COUNTDOWN": handle_countdown,
    "PLAYING":   handle_playing,
    "PAUSED":    handle_paused,
    "GAMEOVER":  handle_gameover,
    "MENU":      handle_menu,
    "EVENT_HOME": handle_event_home,
    "EVENT_NAME": handle_event_name,
    "FINALS_HOME": handle_finals_home,
}

_error_times = []


def _recover_from_screen_error(where):
    """A screen raised: log it, return to the menu and keep the game alive.  If it keeps
    failing (4 errors within 5 s) the original error is raised so the game stops cleanly."""
    crashlog.log_exception(f"error in screen {where}")
    now = time.monotonic()
    _error_times.append(now)
    _error_times[:] = [t for t in _error_times if now - t < 5.0]
    if len(_error_times) >= 4:
        raise
    state.name_edit_active = False
    state.show_exit_confirm = False
    state.finals_withdraw = None
    state.game_state = ("FINALS_HOME" if state.finals is not None else
                        "EVENT_HOME" if state.event_mode else "START")
    show_toast("SOMETHING WENT WRONG  -  DETAILS IN crash_log.txt", 6.0)


# =====================================================================
#  MAIN GAME LOOP
# =====================================================================
# Wrapped in try/finally so cleanup (release the webcam, stop the
# background hand-tracking thread, close the mixer) always runs — even if
# the loop exits via an unexpected exception, a Ctrl+C in the terminal, or
# anything else besides the normal `break` paths below.
try:
    while True:
        # Input first: it also keeps the window responsive
        key, key_raw, mouse_raw, mouse_clicked, mouse_right_clicked = display.poll()
        if display.quit_requested:
            break

        # Finish background camera switches, notice monitors being plugged / unplugged
        system.poll()
        if system.camera is not camera:                   # a new camera went live
            camera, cam_frame, last_cam_seq = system.camera, None, -1

        # Render natively at the window's resolution (largest 16:9 that fits)
        if gfx.set_k(gfx.k_for_size(*display.size)):
            _rebuild_render_buffers()
        frame_w, frame_h = gfx.frame_size()

        # Mouse: window pixels -> rendered frame -> game's logical 1280x720 space
        _fx, _fy = display.to_frame(mouse_raw)
        mouse_game_pos = (-1, -1) if _fx < 0 or _fy < 0 else (
            int(_fx / gfx.SCALE), int(_fy / gfx.SCALE))
        state.mouse_pos = mouse_game_pos              # for hover effects drawn inside screens
        _now = time.monotonic()
        if mouse_game_pos != last_mouse_pos:
            last_mouse_pos, last_mouse_move = mouse_game_pos, _now
        if (mouse_clicked or mouse_right_clicked) and mouse_game_pos[0] >= 0:
            last_click = (mouse_game_pos[0], mouse_game_pos[1], _now)

        # The camera runs on its own thread and delivers frames already
        # mirrored and fitted to the render size; the loop never blocks on it.
        raw, cam_seq = camera.read()
        new_cam_frame = raw is not None and cam_seq != last_cam_seq
        if new_cam_frame:
            last_cam_seq = cam_seq
            cam_frame = raw
        if not state.settings.get("show_camera_feed", True):
            # Picture hidden for a distraction-free court; the camera and tracker keep running
            renderer.prepare_plain_background(frame_buf)
        elif cam_frame is None:
            frame_buf[:] = 0
        elif cam_frame.shape[0] == frame_h and cam_frame.shape[1] == frame_w:
            # Copy + darken in one pass; handlers draw on frame_buf in place
            renderer.prepare_background(cam_frame, frame_buf)
        else:
            # Render size just changed; the camera thread hasn't caught up yet
            renderer.prepare_background(fit_to_window(cam_frame, frame_w, frame_h), frame_buf)
        frame = frame_buf
        state.camera_ok = camera.ok

        current_time = time.monotonic()
        dt = min(current_time - last_time, 0.1)
        last_time = current_time
        state.current_time = current_time
        state.dt = dt

        frame_count += 1
        if current_time - fps_update_time >= 0.5:
            fps_display = frame_count / (current_time - fps_update_time)
            frame_count = 0
            fps_update_time = current_time

        state.fist_pause_cooldown = max(0, state.fist_pause_cooldown - dt)
        state.bg_offset += dt * 25
        state.bg_pulse += dt

        state_at_frame_start = state.game_state
        typing = (state.name_edit_active or state.game_state == "EVENT_NAME"       # letters are text, not hotkeys
                  or state.finals_withdraw is not None)
        # In event mode the public can't reach the menu, quit, camera or fullscreen mid-game;
        # camera / fullscreen stay available to the organiser on the leaderboard screen.
        hotkeys_ok = (not state.event_mode) or state_at_frame_start in ("EVENT_HOME", "FINALS_HOME")

        tracker.single_hand_label = (None if state.cpu_side() is None
                                     else ("Right" if state.cpu_side() == "left" else "Left"))
        # The camera thread feeds the tracker directly; here we only say whether
        # the current screen uses the hands at all.
        tracker.accepting = state.game_state in (
            "START", "COUNTDOWN", "PLAYING", "PAUSED", "GAMEOVER", "FINALS_HOME")
        hand_pos, hand_lm, fist_state = tracker.get_results()
        state.hand_pos = hand_pos
        state.hand_landmarks = hand_lm
        state.fist_state = fist_state

        theme = get_theme(state.settings)
        glow_layer[:] = 0

        ctx = FrameCtx(
            frame=frame,
            theme=theme,
            hand_pos=hand_pos,
            fist_state=fist_state,
            key=key,
            key_raw=key_raw,
            current_time=current_time,
            dt=dt,
            glow_layer=glow_layer,
            mp_hand_connections=tracker.mp_hand_connections,
            mouse_pos=mouse_game_pos,
            mouse_clicked=mouse_clicked,
            mouse_right_clicked=mouse_right_clicked,
        )

        try:
            # Dispatch to the appropriate state handler
            handler = _HANDLERS.get(state.game_state)
            if handler:
                if state.game_state == "START":
                    handler(ctx, state, stats, sound_mgr, tracker)
                elif state.game_state == "SETTINGS":
                    handler(ctx, state, sound_mgr)
                elif state.game_state == "COUNTDOWN":
                    handler(ctx, state, tracker)
                elif state.game_state == "PLAYING":
                    handler(ctx, state, sound_mgr, tracker)
                elif state.game_state == "PAUSED":
                    handler(ctx, state, sound_mgr)
                elif state.game_state == "GAMEOVER":
                    handler(ctx, state, stats, sound_mgr)
                elif state.game_state == "MENU":
                    handler(ctx, state, sound_mgr)
                elif state.game_state == "EVENT_HOME":
                    handler(ctx, state, stats, sound_mgr)
                elif state.game_state == "EVENT_NAME":
                    handler(ctx, state, sound_mgr, tracker)
                elif state.game_state == "FINALS_HOME":
                    handler(ctx, state, stats, sound_mgr, tracker)

        except Exception:
            _recover_from_screen_error(state.game_state)

        # =================================================================
        #  POST-PROCESSING
        # =================================================================
        shake_x, shake_y = effects.get_screen_shake_offset(state)
        if shake_x != 0 or shake_y != 0:
            frame = effects.apply_screen_shake(frame, round(shake_x * gfx.SCALE),
                                               round(shake_y * gfx.SCALE))

        # Fade a screen in when the state changes (menu <-> game, etc.)
        if state.game_state != shown_state:
            shown_state, state_entered = state.game_state, current_time
            state.screen_entered_at = current_time
        ui.fade_in(frame, current_time - state_entered)

        renderer.apply_post_processing(frame, post_overlay)
        hud.draw_global_hud(frame, fps_display, camera.label if camera.ok else None,
                                 tracker.stats_text())
        if current_time < camera_toast_until:
            hud.draw_toast(frame, camera_toast)
        if not state.camera_ok:
            hud.draw_no_camera_banner(frame)
        # The pointer is for menus.  While playing (hands steer the game) it hides after 2.5 s
        # of not being moved, and comes straight back as soon as the mouse moves.
        if state.game_state not in ("PLAYING", "COUNTDOWN") or current_time - last_mouse_move < 2.5:
            ui.draw_cursor(frame, mouse_game_pos, current_time, theme["accent"], last_click)

        display.present(frame)

        # C cycles through the cameras found (switches in the background - the game keeps running)
        if key in (ord('c'), ord('C')) and not typing and hotkeys_ok:
            system.cycle_camera()

        if key in (ord('v'), ord('V')) and not typing and hotkeys_ok:
            state.settings["show_camera_feed"] = not state.settings.get("show_camera_feed", True)
            save_settings(state.settings)
            show_toast("CAMERA PICTURE " + ("ON" if state.settings["show_camera_feed"] else "OFF"), 1.5)

        if key in (ord('f'), ord('F')) and not typing and hotkeys_ok:
            system.toggle_fullscreen()

        # QUIT sentinel set by "Quit Game" menu option
        if state.game_state == "QUIT":
            break

        # Q never quits instantly: it behaves like ESC (in-game menu, which has
        # Quit Game) or opens the exit confirmation on the main menu.
        if key in (ord('q'), ord('Q')) and not typing and not state.event_mode:
            if state_at_frame_start == "START":
                state.show_exit_confirm = True
            else:
                key = 27

        if key == 27:
            in_game = ("PLAYING", "PAUSED", "COUNTDOWN")
            if state_at_frame_start in in_game and state.game_state in in_game:
                # Open in-game menu instead of quitting.  Uses the state the
                # handler left us in, and is skipped if the game just ended
                # this frame (so we never "resume" a finished game).
                state.previous_state = state.game_state
                state.menu_selection = 0
                state.game_state = "MENU"
            elif state_at_frame_start == "GAMEOVER" and not state.event_mode:
                state.gesture_armed = False
                state.start_gesture_time = None
                state.game_state = "START"
            # START ESC handled inside handle_start (opens exit confirm dialog)
            # SETTINGS ESC is handled inside handle_settings → no action needed here

        clock.tick(MAX_FPS)

except KeyboardInterrupt:
    pass

finally:
    # =====================================================================
    #  CLEANUP — always runs: normal break, exception, or Ctrl+C
    # =====================================================================
    sound_mgr.stop_bgm()
    tracker.stop()
    system.camera.stop()
    sound_mgr.cleanup()
    pygame.quit()
    crashlog.cleanup()
