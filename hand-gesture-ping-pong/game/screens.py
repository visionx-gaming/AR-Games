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

def show_start_screen(frame, state, stats):
    """Arcade-style title screen."""
    theme = get_theme(state.settings)
    tc = theme["court"]
    draw_overlay(frame, 0.62)
    cx = WINDOW_WIDTH // 2

    # ── Top neon bar ──────────────────────────────────────────────
    draw_neon_line(frame, 40, 48, WINDOW_WIDTH - 40, 48, tc, 2)

    # ── TITLE ─────────────────────────────────────────────────────
    draw_arcade_text(frame, "HAND  PONG", cx, 155, 3.6, (0, 255, 200), thickness=5)
    draw_arcade_text(frame, "AR PING PONG  *  HAND GESTURE CONTROL",
                     cx, 198, 0.70, scale_color(tc, 0.75), thickness=1, shadow=False)

    # ── Divider ───────────────────────────────────────────────────
    draw_neon_line(frame, 100, 222, WINDOW_WIDTH - 100, 222, tc, 1)

    # ── START PROMPT (pulsing) ────────────────────────────────────
    p1 = 0.5 + 0.5 * math.sin(state.current_time * 2.5)
    sc = (int(0 * p1), int(255 * (0.5 + 0.5 * p1)), int(255 * (0.5 + 0.5 * p1)))
    draw_arcade_text(frame, ">>  PRESS  SPACE  TO  START  <<",
                     cx, 290, 1.22, sc, thickness=3)

    # ── OR divider ────────────────────────────────────────────────
    draw_arcade_text(frame, "-  OR  -", cx, 330, 0.60,
                     (75, 75, 75), thickness=1, shadow=False)

    # ── GESTURE PROMPT ────────────────────────────────────────────
    p2 = 0.45 + 0.55 * abs(math.sin(state.current_time * 1.8))
    wc = (int(220 * p2), int(220 * p2), 0)
    draw_arcade_text(frame, "WAVE BOTH HANDS", cx, 368, 0.95, wc,
                     thickness=2, shadow=False)

    if state.start_gesture_time is not None:
        _draw_gesture_arc(frame, cx, 405,
                          state.current_time - state.start_gesture_time)

    # ── STATS PANEL ───────────────────────────────────────────────
    high = max(stats.get("high_score_classic", 0),
               stats.get("high_score_survival", 0),
               stats.get("high_score_time_attack", 0))

    px, py, pw, ph = cx - 375, 446, 750, 115
    draw_panel(frame, px, py, pw, ph, tc)

    cols = [
        ("HIGH SCORE",   str(high),                             cx - 242),
        ("GAMES PLAYED", str(stats.get("total_games", 0)),      cx),
        ("BEST COMBO",   f"x{stats.get('longest_combo', 0)}", cx + 242),
    ]
    for label, value, lx in cols:
        draw_arcade_text(frame, label, lx, py + 36, 0.50,
                         (130, 130, 130), thickness=1, shadow=False)
        draw_arcade_text(frame, value, lx, py + 84, 1.30,
                         (0, 255, 255), thickness=3)

    for dx in [cx - 120, cx + 120]:
        cv2.line(frame, (dx, py + 14), (dx, py + ph - 14),
                 scale_color(tc, 0.40), 1)

    # ── BOTTOM BAR ────────────────────────────────────────────────
    draw_neon_line(frame, 40, WINDOW_HEIGHT - 70, WINDOW_WIDTH - 40,
                   WINDOW_HEIGHT - 70, tc, 1)
    draw_arcade_text(frame,
                     "[M] Settings    [F] Fullscreen    [ESC] Quit",
                     cx, WINDOW_HEIGHT - 32, 0.52,
                     (100, 100, 100), thickness=1, shadow=False)


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
    draw_panel(frame, WINDOW_WIDTH - 240, cy - 62, 200, 124, rc, fill=(8, 8, 18))
    draw_arcade_text(frame, "P2", WINDOW_WIDTH - 140, cy - 12, 1.0, rc, thickness=2)
    draw_arcade_text(frame, "RIGHT", WINDOW_WIDTH - 140, cy + 36, 0.54,
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
    if state.winner == "Draw":
        result_text, result_col = "IT'S  A  DRAW !", (0, 220, 255)
    elif state.settings["game_mode"] == 1:
        result_text = f"SURVIVED  {state.survival_rally}  RALLIES !"
        result_col = (0, 255, 180)
    else:
        result_text = f"{state.winner.upper()}  WINS !"
        result_col = (80, 255, 80) if "Left" in state.winner else (80, 180, 255)

    draw_arcade_text(frame, result_text, cx, 192, 1.35, result_col, thickness=3)

    draw_neon_line(frame, 120, 216, WINDOW_WIDTH - 120, 216, (30, 0, 200), 1)

    # ── Score line ────────────────────────────────────────────────
    mode = state.settings["game_mode"]
    if mode == 1:
        score_text = f"Total Rally : {state.survival_rally}"
    else:
        score_text = f"Score   Left {state.score[0]}   :   Right {state.score[1]}"
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
