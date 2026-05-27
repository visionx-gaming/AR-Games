"""Overlay screens: start, settings, countdown, pause, game over, menu."""

import cv2
import math
from game.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT,
    DIFFICULTY_NAMES, GAME_MODE_NAMES, THEME_NAMES, COUNTDOWN_DURATION,
    GESTURE_REQUIRED_DURATION, get_theme,
)
from game.renderer import (
    draw_overlay, draw_arcade_text, draw_panel, draw_neon_line,
)
from game.utils import scale_color
from game.stats import save_settings


# ===================================================================
#  START SCREEN
# ===================================================================

_MODE_DESCS = [
    "First to score wins",
    "Survive as long as possible",
    "Most points in 60 seconds",
]
_PLAYER_NAMES = ["2  PLAYER", "VS  AI"]
_PLAYER_DESCS = ["Both hands  ·  local co-op", "Left hand  ·  CPU plays right"]
_PLAYER_SEL_COLS = [(0, 200, 80), (0, 80, 255)]   # green / red-orange (BGR)


def show_start_screen(frame, state, stats):
    """Arcade-style title screen."""
    theme = get_theme(state.settings)
    tc = theme["court"]
    draw_overlay(frame, 0.62)
    cx = WINDOW_WIDTH // 2

    # ── Top neon bar ──────────────────────────────────────────────
    draw_neon_line(frame, 40, 48, WINDOW_WIDTH - 40, 48, tc, 2)

    # ── TITLE ─────────────────────────────────────────────────────
    draw_arcade_text(frame, "HAND  PONG", cx, 116, 2.8, (0, 255, 200), thickness=5)
    draw_arcade_text(frame, "AR PING PONG  *  HAND GESTURE CONTROL",
                     cx, 152, 0.64, scale_color(tc, 0.75), thickness=1, shadow=False)

    # ── Divider ───────────────────────────────────────────────────
    draw_neon_line(frame, 100, 172, WINDOW_WIDTH - 100, 172, tc, 1)

    # ── START PROMPT (pulsing) ────────────────────────────────────
    p1 = 0.5 + 0.5 * math.sin(state.current_time * 2.5)
    sc = (int(0 * p1), int(255 * (0.5 + 0.5 * p1)), int(255 * (0.5 + 0.5 * p1)))
    draw_arcade_text(frame, ">>  PRESS  SPACE  TO  START  <<",
                     cx, 205, 1.22, sc, thickness=3)

    if state.start_gesture_time is not None:
        _draw_gesture_arc(frame, cx, 236,
                          state.current_time - state.start_gesture_time)

    # ── MODE SELECTOR ─────────────────────────────────────────────
    draw_arcade_text(frame, "SELECT  GAME  MODE", cx, 258,
                     0.60, scale_color(tc, 0.72), thickness=1, shadow=False)

    s = state.settings
    current_mode = s["game_mode"]
    card_w, card_h = 340, 80
    card_gap = 15
    total_cw = 3 * card_w + 2 * card_gap
    x0 = cx - total_cw // 2

    for i in range(3):
        x1 = x0 + i * (card_w + card_gap)
        y1 = 270
        cx_c = x1 + card_w // 2
        selected = i == current_mode
        fill = scale_color(tc, 0.07) if selected else (6, 6, 16)
        bdr = tc if selected else scale_color(tc, 0.28)
        draw_panel(frame, x1, y1, card_w, card_h, bdr, fill=fill)
        nm_col = (0, 255, 255) if selected else scale_color(tc, 0.50)
        draw_arcade_text(frame, GAME_MODE_NAMES[i], cx_c, y1 + 36,
                         0.85 if selected else 0.76, nm_col,
                         thickness=2 if selected else 1)
        desc_col = (145, 145, 145) if selected else (72, 72, 72)
        (dw, _), _ = cv2.getTextSize(_MODE_DESCS[i], cv2.FONT_HERSHEY_DUPLEX, 0.46, 2)
        cv2.putText(frame, _MODE_DESCS[i], (cx_c - dw // 2, y1 + 62),
                    cv2.FONT_HERSHEY_DUPLEX, 0.46, desc_col, 2)
        if selected:
            cv2.rectangle(frame, (x1 + 4, y1 + 3), (x1 + card_w - 4, y1 + 6),
                          scale_color(tc, 0.65), -1)

    # ── PLAYER SELECTOR ──────────────────────────────────────────
    draw_arcade_text(frame, "SELECT  PLAYERS", cx, 362,
                     0.60, scale_color(tc, 0.72), thickness=1, shadow=False)

    ai_on = s["ai_enabled"]
    p_card_w, p_card_h = 500, 58
    p_gap = 20
    p_x0 = cx - (2 * p_card_w + p_gap) // 2

    for i in range(2):
        x1 = p_x0 + i * (p_card_w + p_gap)
        y1 = 374
        cx_c = x1 + p_card_w // 2
        selected = (i == 1) == ai_on          # card 0 = 2P, card 1 = AI
        sel_col = _PLAYER_SEL_COLS[i]
        fill = tuple(int(c * 0.08) for c in sel_col) if selected else (6, 6, 16)
        bdr = sel_col if selected else scale_color(tc, 0.28)
        draw_panel(frame, x1, y1, p_card_w, p_card_h, bdr, fill=fill)
        nm_col = sel_col if selected else scale_color(tc, 0.50)
        draw_arcade_text(frame, _PLAYER_NAMES[i], cx_c, y1 + 26,
                         0.82 if selected else 0.72, nm_col,
                         thickness=2 if selected else 1)
        desc_col = tuple(int(c * 0.70) for c in sel_col) if selected else (72, 72, 72)
        (dw, _), _ = cv2.getTextSize(_PLAYER_DESCS[i], cv2.FONT_HERSHEY_DUPLEX, 0.42, 1)
        cv2.putText(frame, _PLAYER_DESCS[i], (cx_c - dw // 2, y1 + 46),
                    cv2.FONT_HERSHEY_DUPLEX, 0.42, desc_col, 1)
        if selected:
            cv2.rectangle(frame, (x1 + 4, y1 + 3), (x1 + p_card_w - 4, y1 + 6),
                          sel_col, -1)

    # ── NAV HINTS ────────────────────────────────────────────────
    cv2.putText(frame,
                "A/D or  ← ►  change mode     [1] [2] [3]  direct select",
                (cx - 278, 447), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (75, 75, 75), 1)
    cv2.putText(frame,
                "Tab  toggle AI / 2-Player                Space  start game",
                (cx - 278, 461), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (75, 75, 75), 1)

    # ── STATS PANEL ───────────────────────────────────────────────
    high = max(stats.get("high_score_classic", 0),
               stats.get("high_score_survival", 0),
               stats.get("high_score_time_attack", 0))

    px, py, pw, ph = cx - 375, 472, 750, 90
    draw_panel(frame, px, py, pw, ph, tc)

    cols = [
        ("HIGH SCORE",   str(high),                             cx - 242),
        ("GAMES PLAYED", str(stats.get("total_games", 0)),      cx),
        ("BEST COMBO",   f"x{stats.get('longest_combo', 0)}", cx + 242),
    ]
    for label, value, lx in cols:
        draw_arcade_text(frame, label, lx, py + 28, 0.50,
                         (130, 130, 130), thickness=1, shadow=False)
        draw_arcade_text(frame, value, lx, py + 72, 1.18,
                         (0, 255, 255), thickness=3)

    for dx in [cx - 120, cx + 120]:
        cv2.line(frame, (dx, py + 12), (dx, py + ph - 12),
                 scale_color(tc, 0.40), 1)

    # ── BOTTOM BAR ────────────────────────────────────────────────
    draw_neon_line(frame, 40, WINDOW_HEIGHT - 70, WINDOW_WIDTH - 40,
                   WINDOW_HEIGHT - 70, tc, 1)
    draw_arcade_text(frame,
                     "[M] Settings    [F] Fullscreen    [ESC] Quit",
                     cx, WINDOW_HEIGHT - 32, 0.52,
                     (100, 100, 100), thickness=1, shadow=False)


def draw_exit_confirm_dialog(frame, state, selected=1):
    """Exit confirmation modal. selected: 0=YES 1=NO."""
    theme = get_theme(state.settings)
    tc = theme["court"]
    cx = WINDOW_WIDTH // 2
    cy = WINDOW_HEIGHT // 2

    draw_overlay(frame, 0.80)

    pw, ph = 540, 220
    px, py = cx - pw // 2, cy - ph // 2
    draw_panel(frame, px, py, pw, ph, tc, fill=(8, 8, 24))

    draw_arcade_text(frame, "EXIT  GAME ?", cx, py + 52, 1.5,
                     (40, 40, 255), thickness=3)
    draw_neon_line(frame, px + 18, py + 68, px + pw - 18, py + 68,
                   scale_color(tc, 0.40), 1)

    cv2.putText(frame, "Are you sure you want to quit?",
                (px + 66, py + 108), cv2.FONT_HERSHEY_DUPLEX, 0.56,
                (160, 160, 160), 1)

    btn_y = py + 142
    btn_h = 46
    yes_cx, no_cx = cx - 150, cx + 150

    for i, (bcx, label, sel_c, unsel_c) in enumerate([
        (yes_cx, "YES", (0, 60, 220), scale_color(tc, 0.30)),
        (no_cx,  "NO",  (0, 190, 70), scale_color(tc, 0.30)),
    ]):
        sel = selected == i
        bdr = sel_c if sel else unsel_c
        fill = tuple(int(c * 0.14) for c in sel_c) if sel else (6, 6, 16)
        cv2.rectangle(frame, (bcx - 80, btn_y), (bcx + 80, btn_y + btn_h), fill, -1)
        cv2.rectangle(frame, (bcx - 80, btn_y), (bcx + 80, btn_y + btn_h), bdr,
                      2 if sel else 1)
        draw_arcade_text(frame, label, bcx, btn_y + 33,
                         0.90 if sel else 0.78, sel_c if sel else scale_color(tc, 0.45),
                         thickness=2 if sel else 1)

    cv2.putText(frame,
                "Y / Enter  confirm       N / ESC  cancel",
                (px + 96, py + ph - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.40,
                (80, 80, 80), 1)


# ===================================================================
#  SETTINGS SCREEN
# ===================================================================

def show_settings_screen(frame, state):
    """Draw the settings menu overlay with arcade styling."""
    theme = get_theme(state.settings)
    tc = theme["court"]
    draw_overlay(frame, 0.72)
    cx = WINDOW_WIDTH // 2
    start_y = 100

    # Panel — spans all items
    draw_panel(frame, cx - 340, 50, 680, 592, tc, fill=(8, 8, 18))

    # Header
    draw_arcade_text(frame, "SETTINGS", cx, start_y, 2.0, (0, 255, 200), thickness=3)
    draw_neon_line(frame, cx - 322, start_y + 18, cx + 322, start_y + 18,
                   scale_color(tc, 0.55), 1)

    s = state.settings
    items = [
        f"Score to Win:  {s['score_to_win']}",
        f"Difficulty:    {DIFFICULTY_NAMES[s['difficulty']]}",
        f"Game Mode:     {GAME_MODE_NAMES[s['game_mode']]}",
        f"AI Opponent:   {'ON' if s['ai_enabled'] else 'OFF  (2 Player)'}",
        f"Color Theme:   {THEME_NAMES[s['color_theme']]}",
        f"Sound:         {'ON' if s['sound_enabled'] else 'OFF'}",
        f"Music Volume:  {s['music_volume']}%",
        f"SFX Volume:    {s['sfx_volume']}%",
        f"Hand Skeleton: {'ON' if s['show_hand_skeleton'] else 'OFF'}",
        f"Obstacles:     {'ON' if s['obstacles_enabled'] else 'OFF'}",
    ]

    for i, item in enumerate(items):
        y = start_y + 65 + i * 42   # preserved — matches mouse hit detection
        selected = i == s["selected_setting"]

        if selected:
            cv2.rectangle(frame, (cx - 320, y - 25), (cx + 320, y + 12),
                          scale_color(tc, 0.10), -1)
            cv2.rectangle(frame, (cx - 320, y - 25), (cx + 320, y + 12),
                          scale_color(tc, 0.45), 1)
            draw_arcade_text(frame, ">  " + item, cx, y, 0.68,
                             (0, 255, 255), thickness=2)
        else:
            cv2.putText(frame, "   " + item, (cx - 295, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, (155, 155, 155), 1)

    # Bottom hint bar
    hint_y = start_y + 65 + len(items) * 42 + 14
    draw_neon_line(frame, cx - 322, hint_y - 14, cx + 322, hint_y - 14,
                   scale_color(tc, 0.30), 1)
    cv2.putText(frame,
                "W/S Navigate    A/D Change    L-Click Advance    R-Click Back    ESC Return",
                (cx - 308, hint_y + 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (90, 90, 90), 1)


def handle_settings_input(key_raw, state, sound_mgr):
    """Process keyboard input on the settings screen."""
    s = state.settings
    num = 10
    key = key_raw & 0xFF if key_raw != -1 else 255

    UP, DOWN, LEFT, RIGHT = 2490368, 2621440, 2424832, 2555904

    if key in (ord('w'), ord('W')) or key_raw == UP:
        s["selected_setting"] = (s["selected_setting"] - 1) % num
        sound_mgr.play_menu_tick()
    elif key in (ord('s'), ord('S')) or key_raw == DOWN:
        s["selected_setting"] = (s["selected_setting"] + 1) % num
        sound_mgr.play_menu_tick()
    elif key in (ord('a'), ord('A')) or key_raw == LEFT:
        change_setting(s, s["selected_setting"], -1, sound_mgr)
    elif key in (ord('d'), ord('D')) or key_raw == RIGHT:
        change_setting(s, s["selected_setting"], +1, sound_mgr)
    elif key == 27:
        return "START"
    return None


def change_setting(s, idx, direction, sound_mgr):
    """Change a single setting value."""
    if idx == 0:
        s["score_to_win"] = max(1, min(20, s["score_to_win"] + direction))
    elif idx == 1:
        s["difficulty"] = max(0, min(2, s["difficulty"] + direction))
    elif idx == 2:
        s["game_mode"] = max(0, min(len(GAME_MODE_NAMES) - 1,
                                     s["game_mode"] + direction))
    elif idx == 3:
        s["ai_enabled"] = not s["ai_enabled"]
    elif idx == 4:
        s["color_theme"] = (s["color_theme"] + direction) % len(THEME_NAMES)
    elif idx == 5:
        s["sound_enabled"] = not s["sound_enabled"]
        sound_mgr.update_enabled(s["sound_enabled"])
    elif idx == 6:
        s["music_volume"] = max(0, min(100, s["music_volume"] + direction * 10))
        sound_mgr.set_bgm_volume(s["music_volume"])
    elif idx == 7:
        s["sfx_volume"] = max(0, min(100, s["sfx_volume"] + direction * 10))
        sound_mgr.set_sfx_volume(s["sfx_volume"])
    elif idx == 8:
        s["show_hand_skeleton"] = not s["show_hand_skeleton"]
    elif idx == 9:
        s["obstacles_enabled"] = not s["obstacles_enabled"]
    save_settings(s)


# ===================================================================
#  COUNTDOWN SCREEN
# ===================================================================

def show_countdown_screen(frame, state):
    """Draw the 3-2-1-GO! countdown with player panels and arcade styling."""
    theme = get_theme(state.settings)
    tc = theme["court"]
    lc = theme["left_paddle"]
    rc = theme["right_paddle"]
    draw_overlay(frame, 0.48)
    cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2

    elapsed = state.current_time - state.countdown_start
    remaining = COUNTDOWN_DURATION - elapsed

    # ── P1 panel (left) ───────────────────────────────────────────────
    draw_panel(frame, 40, cy - 62, 200, 124, lc, fill=(8, 8, 18))
    draw_arcade_text(frame, "P1", 140, cy - 12, 1.0, lc, thickness=2)
    draw_arcade_text(frame, "LEFT", 140, cy + 36, 0.54,
                     scale_color(lc, 0.60), thickness=1, shadow=False)

    # ── P2 panel (right) ──────────────────────────────────────────────
    ai = state.settings["ai_enabled"]
    p2_label = "AI" if ai else "P2"
    p2_sub = "CPU" if ai else "RIGHT"
    draw_panel(frame, WINDOW_WIDTH - 240, cy - 62, 200, 124, rc, fill=(8, 8, 18))
    draw_arcade_text(frame, p2_label, WINDOW_WIDTH - 140, cy - 12, 1.0, rc, thickness=2)
    draw_arcade_text(frame, p2_sub, WINDOW_WIDTH - 140, cy + 36, 0.54,
                     scale_color(rc, 0.60), thickness=1, shadow=False)

    # ── Countdown number / GO! ────────────────────────────────────────
    if remaining > 0:
        pulse = 3.0 + (remaining % 1) * 0.5
        frac = 1.0 - (remaining % 1)
        num_color = (int(frac * 80), int(180 + frac * 75), 255)
        draw_arcade_text(frame, str(math.ceil(remaining)), cx, cy + 38,
                         pulse, num_color, thickness=5)
    else:
        draw_arcade_text(frame, "GO!", cx, cy + 38, 3.0, (0, 255, 100), thickness=5)

    # ── Hint ─────────────────────────────────────────────────────────
    draw_neon_line(frame, cx - 185, cy + 95, cx + 185, cy + 95,
                   scale_color(tc, 0.22), 1)
    cv2.putText(frame, "Get ready!",
                (cx - 56, cy + 118), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (90, 90, 90), 1)


# ===================================================================
#  PAUSE SCREEN
# ===================================================================

def show_pause_screen(frame, state):
    """Draw the pause overlay."""
    theme = get_theme(state.settings)
    tc = theme["court"]
    draw_overlay(frame, 0.52)
    cx = WINDOW_WIDTH // 2
    cy = WINDOW_HEIGHT // 2

    p = 0.7 + 0.3 * abs(math.sin(state.current_time * 3.0))
    pc = (int(60 * p), int(60 * p), int(255 * p))

    draw_arcade_text(frame, "PAUSED", cx, cy - 35, 2.8, pc, thickness=4)
    draw_neon_line(frame, cx - 230, cy + 5, cx + 230, cy + 5,
                   scale_color(pc, 0.35), 1)
    draw_arcade_text(frame, "PRESS  R  TO  RESUME", cx, cy + 52,
                     0.85, (180, 180, 180), thickness=2, shadow=False)
    draw_arcade_text(frame, "Open both palms to resume",
                     cx, cy + 88, 0.62, (110, 110, 110), thickness=1, shadow=False)
    draw_arcade_text(frame, "ESC  ->  In-Game Menu",
                     cx, cy + 128, 0.55, (90, 90, 90), thickness=1, shadow=False)


# ===================================================================
#  IN-GAME MENU SCREEN
# ===================================================================

MENU_ITEMS = ["Resume", "Settings", "Quit to Main Menu", "Quit Game"]


def show_menu_screen(frame, state):
    """Draw the in-game ESC menu as a centered neon panel."""
    theme = get_theme(state.settings)
    tc = theme["court"]
    draw_overlay(frame, 0.72)

    cx = WINDOW_WIDTH // 2
    cy = WINDOW_HEIGHT // 2

    pw, ph = 480, 395
    px, py = cx - pw // 2, cy - ph // 2

    draw_panel(frame, px, py, pw, ph, tc, fill=(8, 8, 18))

    # Header
    draw_arcade_text(frame, "GAME  MENU", cx, py + 52, 1.75,
                     (0, 255, 200), thickness=3)
    draw_neon_line(frame, px + 18, py + 68, px + pw - 18, py + 68,
                   scale_color(tc, 0.55), 1)

    # Items
    for i, item in enumerate(MENU_ITEMS):
        iy = py + 118 + i * 62
        selected = i == state.menu_selection

        if selected:
            cv2.rectangle(frame,
                          (px + 14, iy - 30), (px + pw - 14, iy + 16),
                          scale_color(tc, 0.12), -1)
            cv2.rectangle(frame,
                          (px + 14, iy - 30), (px + pw - 14, iy + 16),
                          scale_color(tc, 0.55), 1)
            cv2.putText(frame, ">", (px + 28, iy),
                        cv2.FONT_HERSHEY_DUPLEX, 0.9, tc, 2)
        else:
            cv2.rectangle(frame,
                          (px + 14, iy - 30), (px + pw - 14, iy + 16),
                          scale_color(tc, 0.06), -1)

        col = (0, 255, 255) if selected else scale_color(tc, 0.55)
        thick = 2 if selected else 1
        draw_arcade_text(frame, item, cx + 14, iy, 0.82,
                         col, thickness=thick, shadow=True)

    # Hints bar
    draw_neon_line(frame, px + 18, py + ph - 46,
                   px + pw - 18, py + ph - 46,
                   scale_color(tc, 0.40), 1)
    cv2.putText(frame,
                "W/S  Navigate    Enter/Space  Select    ESC  Resume",
                (px + 20, py + ph - 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (95, 95, 95), 1)


# ===================================================================
#  GAME OVER SCREEN
# ===================================================================

def show_game_over_screen(frame, state, stats):
    """Arcade-style game-over screen."""
    theme = get_theme(state.settings)
    tc = theme["court"]
    draw_overlay(frame, 0.65)
    cx = WINDOW_WIDTH // 2

    # ── Top bar ───────────────────────────────────────────────────
    draw_neon_line(frame, 40, 45, WINDOW_WIDTH - 40, 45, (30, 0, 200), 2)

    # ── GAME OVER ─────────────────────────────────────────────────
    draw_arcade_text(frame, "GAME  OVER", cx, 138, 3.2, (40, 40, 255), thickness=5)

    # ── Result line ───────────────────────────────────────────────
    ai = state.settings["ai_enabled"]
    if state.winner == "Draw":
        result_text, result_col = "IT'S  A  DRAW !", (0, 220, 255)
    elif state.settings["game_mode"] == 1:
        result_text = f"SURVIVED  {state.survival_rally}  RALLIES !"
        result_col = (0, 255, 180)
    elif "Left" in state.winner:
        result_text = "YOU  WIN !" if ai else "P1  WINS !"
        result_col = (60, 255, 80)
    else:
        result_text = "AI  WINS !" if ai else "P2  WINS !"
        result_col = (0, 80, 255) if ai else (80, 180, 255)

    draw_arcade_text(frame, result_text, cx, 192, 1.75, result_col, thickness=3)

    draw_neon_line(frame, 120, 216, WINDOW_WIDTH - 120, 216, (30, 0, 200), 1)

    # ── Score line ────────────────────────────────────────────────
    mode = state.settings["game_mode"]
    if mode == 1:
        score_text = f"Total Rally : {state.survival_rally}"
    elif ai:
        score_text = f"Score   You {state.score[0]}   :   AI {state.score[1]}"
    else:
        score_text = f"Score   P1 {state.score[0]}   :   P2 {state.score[1]}"
    draw_arcade_text(frame, score_text, cx, 262, 1.0,
                     (200, 200, 200), thickness=2, shadow=False)

    # ── Stats panel ───────────────────────────────────────────────
    px, py, pw, ph = cx - 345, 294, 690, 118
    draw_panel(frame, px, py, pw, ph, tc)

    rally_val = str(state.survival_rally) if mode == 1 else "-"
    cols = [
        ("BEST COMBO",  f"x{state.max_combo}" if state.max_combo >= 1 else "x1", cx - 205),
        ("HIGH SCORE",  str(state.high_score),                                    cx),
        ("BEST RALLY",  rally_val,                                                 cx + 205),
    ]
    for label, value, lx in cols:
        draw_arcade_text(frame, label, lx, py + 36, 0.50,
                         (130, 130, 130), thickness=1, shadow=False)
        draw_arcade_text(frame, value, lx, py + 84, 1.30,
                         (0, 255, 255), thickness=3)
    for dx in [cx - 100, cx + 100]:
        cv2.line(frame, (dx, py + 14), (dx, py + ph - 14),
                 scale_color(tc, 0.40), 1)

    # ── Restart prompt (pulsing) ──────────────────────────────────
    p1 = 0.5 + 0.5 * math.sin(state.current_time * 2.5)
    rc = (int(0 * p1), int(255 * (0.5 + 0.5 * p1)), int(255 * (0.5 + 0.5 * p1)))
    draw_arcade_text(frame, ">>  PRESS  SPACE  TO  RESTART  <<",
                     cx, 456, 1.12, rc, thickness=3)

    # ── Gesture option ────────────────────────────────────────────
    draw_arcade_text(frame, "-  OR  -", cx, 494, 0.58,
                     (75, 75, 75), thickness=1, shadow=False)

    p2 = 0.45 + 0.55 * abs(math.sin(state.current_time * 1.8))
    wc = (int(200 * p2), int(200 * p2), 0)
    draw_arcade_text(frame, "WAVE BOTH HANDS", cx, 530,
                     0.90, wc, thickness=2, shadow=False)

    if state.restart_gesture_time is not None:
        _draw_gesture_arc(frame, cx, 568,
                          state.current_time - state.restart_gesture_time)

    # ── Bottom bar ────────────────────────────────────────────────
    draw_neon_line(frame, 40, WINDOW_HEIGHT - 55,
                   WINDOW_WIDTH - 40, WINDOW_HEIGHT - 55, (30, 0, 200), 1)
    draw_arcade_text(frame,
                     "[SPACE] Restart    [ESC] Main Menu",
                     cx, WINDOW_HEIGHT - 22, 0.52,
                     (100, 100, 100), thickness=1, shadow=False)


# ===================================================================
#  SHARED HELPERS
# ===================================================================

def _draw_gesture_arc(frame, cx, cy, elapsed):
    """Draw a circular progress arc for a hold gesture."""
    progress = min(1.0, elapsed / GESTURE_REQUIRED_DURATION)
    end_angle = int(-90 + 360 * progress)
    bg_color = (40, 80, 40)
    fg_color = (0, 255, 200)
    cv2.ellipse(frame, (cx, cy), (30, 30), 0, -90, 270, bg_color, 2)
    cv2.ellipse(frame, (cx, cy), (30, 30), 0, -90, end_angle, fg_color, 3)
    pct = f"{int(progress * 100)}%"
    (tw, _), _ = cv2.getTextSize(pct, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
    cv2.putText(frame, pct, (cx - tw // 2, cy + 7),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, fg_color, 1)
