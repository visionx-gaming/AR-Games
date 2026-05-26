"""Hand Pong — Main entry point and game loop.

An AR ping-pong game controlled by hand gestures via webcam.
Run:  python main.py
"""

import cv2
import numpy as np
import pygame
import time

from game.config import WINDOW_WIDTH, WINDOW_HEIGHT, get_theme
from game.state import GameState
from game.sound import SoundManager
from game.stats import load_stats
from game.hand_tracking import HandTracker
from game.utils import detect_screen_resolution, letterbox_frame
from game import effects, renderer
from game.handlers import FrameCtx, handle_start, handle_settings, handle_countdown
from game.handlers import handle_playing, handle_paused, handle_gameover, handle_menu

# =====================================================================
#  INITIALIZATION
# =====================================================================
pygame.init()
sound_mgr = SoundManager()
stats = load_stats()
state = GameState()

state.high_score = max(
    stats.get("high_score_classic", 0),
    stats.get("high_score_survival", 0),
    stats.get("high_score_time_attack", 0),
)

screen_width, screen_height = detect_screen_resolution()

cv2.namedWindow("Game", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Game", WINDOW_WIDTH, WINDOW_HEIGHT)
is_fullscreen = False


class _MouseState:
    __slots__ = ("raw_pos", "clicked", "right_clicked")

    def __init__(self):
        self.raw_pos = (-1, -1)
        self.clicked = False
        self.right_clicked = False


_mouse = _MouseState()


def _mouse_cb(event, x, y, flags, param):
    _mouse.raw_pos = (x, y)
    if event == cv2.EVENT_LBUTTONDOWN:
        _mouse.clicked = True
    elif event == cv2.EVENT_RBUTTONDOWN:
        _mouse.right_clicked = True


cv2.setMouseCallback("Game", _mouse_cb)


def _to_game_coords(rx, ry, is_fs, sw, sh):
    """Map raw window mouse coords to game-frame coords (handles letterbox)."""
    if not is_fs or sw <= 0 or sh <= 0:
        return rx, ry
    scale = min(sw / WINDOW_WIDTH, sh / WINDOW_HEIGHT)
    if scale <= 0:
        return rx, ry
    x_off = (sw - int(WINDOW_WIDTH * scale)) // 2
    y_off = (sh - int(WINDOW_HEIGHT * scale)) // 2
    return int((rx - x_off) / scale), int((ry - y_off) / scale)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 60)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

tracker = HandTracker()
tracker.start()

scanline_overlay = renderer.create_scanline_overlay()
vignette_overlay = renderer.create_vignette()
glow_layer = np.zeros((WINDOW_HEIGHT, WINDOW_WIDTH, 3), dtype=np.uint8)

last_time = time.time()
frame_count = 0
fps_display = 0
fps_update_time = time.time()
pump_counter = 0

_HANDLERS = {
    "START":     handle_start,
    "SETTINGS":  handle_settings,
    "COUNTDOWN": handle_countdown,
    "PLAYING":   handle_playing,
    "PAUSED":    handle_paused,
    "GAMEOVER":  handle_gameover,
    "MENU":      handle_menu,
}

# =====================================================================
#  MAIN GAME LOOP
# =====================================================================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]
    if w != WINDOW_WIDTH or h != WINDOW_HEIGHT:
        frame = cv2.resize(frame, (WINDOW_WIDTH, WINDOW_HEIGHT))

    current_time = time.time()
    dt = min(current_time - last_time, 0.1)
    last_time = current_time
    state.current_time = current_time
    state.dt = dt

    key_raw = cv2.waitKeyEx(1)
    key = key_raw & 0xFF if key_raw != -1 else 255

    # Consume and transform mouse events for this frame
    _mrx, _mry = _mouse.raw_pos
    mouse_game_pos = _to_game_coords(_mrx, _mry, is_fullscreen, screen_width, screen_height)
    mouse_clicked = _mouse.clicked
    mouse_right_clicked = _mouse.right_clicked
    _mouse.clicked = False
    _mouse.right_clicked = False

    frame_count += 1
    if current_time - fps_update_time >= 0.5:
        fps_display = frame_count / (current_time - fps_update_time)
        frame_count = 0
        fps_update_time = current_time

    state.fist_pause_cooldown = max(0, state.fist_pause_cooldown - dt)
    state.bg_offset += dt * 25
    state.bg_pulse += dt

    state_at_frame_start = state.game_state

    if state.game_state in ("START", "COUNTDOWN", "PLAYING", "GAMEOVER"):
        tracker.send_frame(frame)
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

    # =================================================================
    #  POST-PROCESSING
    # =================================================================
    shake_x, shake_y = effects.get_screen_shake_offset(state)
    if shake_x != 0 or shake_y != 0:
        frame = effects.apply_screen_shake(frame, shake_x, shake_y)

    renderer.apply_post_processing(frame, scanline_overlay, vignette_overlay)
    renderer.draw_global_hud(frame, fps_display)
    renderer.draw_mouse_cursor(frame, mouse_game_pos)

    if is_fullscreen and screen_width > 0 and screen_height > 0:
        display_frame = letterbox_frame(frame, screen_width, screen_height)
    else:
        display_frame = frame
    cv2.imshow("Game", display_frame)

    pump_counter += 1
    if pump_counter % 10 == 0:
        pygame.event.pump()

    if key in (ord('f'), ord('F')):
        is_fullscreen = not is_fullscreen
        if is_fullscreen:
            cv2.setWindowProperty("Game", cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN)
        else:
            cv2.setWindowProperty("Game", cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Game", WINDOW_WIDTH, WINDOW_HEIGHT)

    # QUIT sentinel set by "Quit Game" menu option
    if state.game_state == "QUIT":
        break

    if key == ord('q'):
        break

    if key == 27:
        if state_at_frame_start in ("PLAYING", "PAUSED", "COUNTDOWN"):
            # Open in-game menu instead of quitting
            state.previous_state = state_at_frame_start
            state.menu_selection = 0
            state.game_state = "MENU"
        elif state_at_frame_start == "GAMEOVER":
            state.game_state = "START"
        elif state_at_frame_start == "START":
            break
        # SETTINGS ESC is handled inside handle_settings → no action needed here

    try:
        if cv2.getWindowProperty("Game", cv2.WND_PROP_VISIBLE) < 1:
            break
    except cv2.error:
        break

# =====================================================================
#  CLEANUP
# =====================================================================
sound_mgr.stop_bgm()
tracker.stop()
cap.release()
cv2.destroyAllWindows()
sound_mgr.cleanup()
pygame.quit()
