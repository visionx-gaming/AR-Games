"""Main menu, settings, in-game menu, pause, countdown, game over and dialogs.

Built on game.ui.  Each screen exposes
  * a draw function (called every frame by its handler), and
  * where it has mouse targets, a *_rects() function the handler uses for hit
    testing - so drawing and clicking can never drift apart.
"""

import math

from game import ui, widgets
from game.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, GAME_MODE_NAMES, COUNTDOWN_DURATION,
    GESTURE_REQUIRED_DURATION, get_theme,
)
from game.renderer import draw_overlay
from game.settings_screen import PLAYER_MODE_LABELS
from game.stats import high_score_value, HIGH_SCORE_LABELS

CX, CY = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2

VIEWS = {n: widgets.MenuView(n) for n in ("start", "menu")}


# ===================================================================
#  MAIN MENU
# ===================================================================

_MODE_INFO = [
    ("Classic", "Rally for points - first to the target score wins.",
     ["Move your paddle with your hand", "Hit near the edge to angle the ball",
      "First to {target} points wins"]),
    ("Survival", "How long can you keep the ball alive?",
     ["No score - only rally length counts", "The ball speeds up with every hit",
      "Miss once and the run is over"]),
    ("Time Attack", "Score as many points as you can in {secs} seconds.",
     ["The clock only runs during rallies", "Every point resets the serve",
      "Most points when time is up wins"]),
]


def start_rects():
    """Rects of the main-menu items (PLAY, MODE, PLAYERS, NAMES, QUALIFIER, FINALS, SETTINGS, EXIT)."""
    return widgets.stack(ui.MARGIN, 244, 500, [64, 44, 44, 44, 44, 44, 44, 44], gap=8)


def start_items(state):
    s = state.settings
    p1, p2 = s["player1_name"], s["player2_name"]
    return [
        {"id": "play", "label": "PLAY", "kind": "button", "primary": True, "hint": "SPACE"},
        {"id": "mode", "label": "MODE", "kind": "select", "value": GAME_MODE_NAMES[s["game_mode"]].upper()},
        {"id": "players", "label": "PLAYERS", "kind": "segment", "options": PLAYER_MODE_LABELS,
         "index": state.player_mode()},
        {"id": "names", "label": "PLAYER NAMES", "kind": "button", "hint": "N",
         "value": f"{p1}  &  {p2}" if not s["ai_enabled"] else f"{p1}  vs  CPU"},
        {"id": "qualifier", "label": "TOURNAMENT QUALIFIER", "kind": "button",
         "value": "TIME ATTACK VS CPU"},
        {"id": "finals", "label": "TOURNAMENT FINALS", "kind": "button", "value": "TOP PLAYERS"},
        {"id": "settings", "label": "SETTINGS", "kind": "button", "hint": "M"},
        {"id": "exit", "label": "EXIT", "kind": "button", "danger": True, "hint": "ESC"},
    ]


def _fit_name(name, size, max_w):
    while len(name) > 3 and ui.text_width(name, size, "bold") > max_w:
        name = name[:-2] + "."
    return name


def _mode_card(frame, state, stats, theme):
    s = state.settings
    accent = theme["accent"]
    x, y, w, h = 660, 112, 548, 520
    ui.panel(frame, x, y, w, h, 18, alpha=0.74)
    mode = s["game_mode"]
    title, desc, rules = _MODE_INFO[mode]

    ui.text(frame, "SELECTED MODE", x + 32, y + 40, 13, ui.TEXT_3, "left", "bold", spacing=2.2)
    ui.text(frame, title.upper(), x + 32, y + 92, 48, accent, "left", "bold", spacing=1.2, shadow=True)
    ui.text(frame, desc.format(secs=s["time_limit"]), x + 32, y + 138, 19, ui.TEXT_2, "left", "medium")
    for i, rule in enumerate(rules):
        ry = y + 188 + i * 32
        ui.disc(frame, x + 40, ry, 4, accent)
        ui.text(frame, rule.format(target=s["score_to_win"]), x + 58, ry, 18, ui.TEXT_2, "left", "medium")
    ui.hline(frame, x + 32, x + w - 32, y + 298, ui.mix(ui.PANEL, (255, 255, 255), 0.14))

    ui.text(frame, "MATCH", x + 32, y + 330, 13, ui.TEXT_3, "left", "bold", spacing=2.2)
    left = _fit_name(s["player1_name"], 28, 200)
    right = "CPU" if s["ai_enabled"] else _fit_name(s["player2_name"], 28, 200)
    if state.cpu_side() == "left":
        left, right = "CPU", left
    theme_l, theme_r = theme["left_paddle"], theme["right_paddle"]
    wl, wr = ui.text_width(left, 28, "bold"), ui.text_width(right, 28, "bold")
    vs_w = 54
    total = wl + vs_w + wr
    sx = x + w / 2 - total / 2
    ui.text(frame, left, sx, y + 372, 28, theme_l, "left", "bold")
    ui.text(frame, "VS", sx + wl + vs_w / 2, y + 372, 15, ui.TEXT_3, "center", "bold", spacing=2)
    ui.text(frame, right, sx + wl + vs_w, y + 372, 28, theme_r, "left", "bold")

    label = HIGH_SCORE_LABELS[mode]
    tw = (w - 64 - 2 * 14) / 3
    for i, (lab, val) in enumerate(((label, str(high_score_value(stats, mode))),
                                    ("GAMES PLAYED", str(stats.get("total_games", 0))),
                                    ("BEST COMBO", f"x{stats.get('longest_combo', 0)}"))):
        ui.stat_tile(frame, x + 32 + i * (tw + 14), y + 416, tw, 88, lab, val, accent)


def show_start_screen(frame, state, stats):
    theme = get_theme(state.settings)
    accent = theme["accent"]
    now, dt = state.current_time, state.dt
    ui.side_gradient(frame)
    ui.attract_court(frame, now, theme, x0=600, x1=1250)
    ui.logo(frame, ui.MARGIN, 100, accent, now)

    items, rects = start_items(state), start_rects()
    VIEWS["start"].draw(frame, items, rects, theme, now, dt)
    if state.start_gesture_time is not None:          # raise-both-hands progress, on the PLAY button
        frac = (now - state.start_gesture_time) / GESTURE_REQUIRED_DURATION
        x, y, w, h = rects[0]
        ui.progress_bar(frame, x + 22, y + h - 14, w - 44, 5, frac, (255, 255, 255), ui.mix(accent, (0, 0, 0), 0.55))

    _mode_card(frame, state, stats, theme)
    ui.hints(frame, [("W S", "Navigate"), ("A D", "Change"), ("ENTER", "Select"), ("SPACE", "Play"),
                     ("H", "How to play"), ("F", "Fullscreen"), ("C", "Camera")])


# ===================================================================
#  DIALOGS: EXIT CONFIRM, PLAYER NAMES
# ===================================================================

def exit_button_rects():
    return {"yes": (CX - 225, CY + 28, 210, 54), "no": (CX + 15, CY + 28, 210, 54)}


def draw_exit_confirm_dialog(frame, state, selected=1):
    """Modal. selected: 0 = YES, 1 = NO (default)."""
    theme = get_theme(state.settings)
    draw_overlay(frame, 0.72)
    ui.panel(frame, CX - 270, CY - 120, 540, 240, 18, alpha=0.92)
    ui.text(frame, "EXIT GAME?", CX, CY - 62, 38, ui.TEXT, "center", "bold", spacing=1.5, shadow=True)
    ui.text(frame, "Are you sure you want to quit?", CX, CY - 16, 19, ui.TEXT_2, "center", "medium")
    r = exit_button_rects()
    widgets._draw_item(frame, {"kind": "button", "label": "YES, EXIT", "danger": True, "label_size": 24}, r["yes"],
                  1.0 if selected == 0 else 0.0, 1.0, theme["accent"])
    widgets._draw_item(frame, {"kind": "button", "label": "NO, STAY", "primary": True, "label_size": 24}, r["no"],
                  1.0 if selected == 1 else 0.0, 1.0, theme["accent"])
    ui.hints(frame, [("A D", "Choose"), ("ENTER", "Confirm"), ("Y", "Yes"), ("N", "No")], backdrop=True)


def name_field_rects():
    """Clickable (x1, y1, x2, y2) boxes of the two name fields (logical coords)."""
    return [(CX - 250, CY - 52 + i * 100, CX + 250, CY - 4 + i * 100) for i in range(2)]


def draw_name_dialog(frame, state):
    theme = get_theme(state.settings)
    accent = theme["accent"]
    draw_overlay(frame, 0.78)
    ui.panel(frame, CX - 320, CY - 176, 640, 330, 18, alpha=0.94)
    ui.text(frame, "PLAYER NAMES", CX, CY - 128, 36, ui.TEXT, "center", "bold", spacing=1.5, shadow=True)

    labels = (("PLAYER 1  -  LEFT HAND", theme["left_paddle"]), ("PLAYER 2  -  RIGHT HAND", theme["right_paddle"]))
    caret_on = int(state.current_time * 2) % 2 == 0
    for i, ((x1, y1, x2, y2), (label, col)) in enumerate(zip(name_field_rects(), labels)):
        sel = i == state.name_edit_field
        ui.text(frame, label, x1 + 4, y1 - 16, 13, ui.mix(ui.TEXT_3, col, 0.8 if sel else 0.3), "left", "bold", spacing=1.6)
        ui.fill_rrect(frame, x1, y1, x2 - x1, y2 - y1, 10, ui.mix(ui.PANEL_HI, col, 0.14 if sel else 0.0), 0.95)
        ui.rrect(frame, x1, y1, x2 - x1, y2 - y1, 10, col if sel else ui.mix(ui.PANEL_HI, (255, 255, 255), 0.18), 2 if sel else 1)
        txt = state.name_edit_buf[i]
        ui.text(frame, txt, x1 + 18, (y1 + y2) / 2, 24, ui.TEXT if sel else ui.TEXT_2, "left", "bold")
        if sel and caret_on:
            cx_ = x1 + 18 + ui.text_width(txt, 24, "bold") + 3
            ui.fill_rrect(frame, cx_, y1 + 10, 2.5, (y2 - y1) - 20, 1, accent)
    if state.settings["ai_enabled"]:
        ui.text(frame, "Player 2 is used in 2-player games (VS CPU is on)", CX, CY + 124, 15, ui.TEXT_3, "center", "medium")
    ui.hints(frame, [("TAB", "Switch field"), ("ENTER", "Next / Save"), ("ESC", "Cancel")], backdrop=True)


# ===================================================================
#  IN-GAME MENU  (ESC)
# ===================================================================

_MENU_X, _MENU_Y, _MENU_W, _MENU_H = CX - 240, 110, 480, 500


def menu_rects():
    return widgets.stack(_MENU_X + 30, _MENU_Y + 190, _MENU_W - 60, [60, 56, 56, 56], gap=12)


def menu_screen(ctx, state, sound_mgr):
    """Draw the in-game menu; returns the chosen item index (0-3) or None."""
    theme = get_theme(state.settings)
    now, dt = state.current_time, state.dt
    view = VIEWS["menu"]
    if now - view.last_draw > 0.3:
        view.focus = state.menu_selection
    draw_overlay(ctx.frame, 0.66)
    ui.panel(ctx.frame, _MENU_X, _MENU_Y, _MENU_W, _MENU_H, 20, alpha=0.90)
    ui.text(ctx.frame, "MENU", CX, _MENU_Y + 62, 42, ui.TEXT, "center", "bold", spacing=3, shadow=True)
    n1, n2 = state.match_names
    ui.text(ctx.frame, f"{n1}  {state.score[0]}  -  {state.score[1]}  {n2}", CX, _MENU_Y + 108, 19, ui.TEXT_2, "center", "semi")
    sub_line = "TOURNAMENT  -  GAME ON HOLD" if state.event_mode else GAME_MODE_NAMES[state.settings["game_mode"]].upper() + "  -  MATCH PAUSED"
    ui.text(ctx.frame, sub_line, CX, _MENU_Y + 138, 14, ui.TEXT_3, "center", "bold", spacing=2)
    ui.hline(ctx.frame, _MENU_X + 30, _MENU_X + _MENU_W - 30, _MENU_Y + 164, ui.mix(ui.PANEL, (255, 255, 255), 0.14))

    items = [
        {"id": 0, "label": "RESUME", "kind": "button", "primary": True, "hint": "ESC"},
        {"id": 1, "label": "SETTINGS", "kind": "button"},
        {"id": 2, "label": "ABANDON GAME" if state.event_mode else "QUIT TO MAIN MENU", "kind": "button"},
        {"id": 3, "label": "QUIT GAME", "kind": "button", "danger": True},
    ]
    rects = menu_rects()
    view.draw(ctx.frame, items, rects, theme, now, dt, stagger=0.04, slide=26)
    ui.hints(ctx.frame, [("W S", "Navigate"), ("ENTER", "Select"), ("ESC", "Resume")])

    chosen = None
    for ev in view.input(ctx, items, rects, activate_keys=(13, 32)):
        if ev[0] == "focus":
            sound_mgr.play_menu_tick()
        elif ev[0] == "activate":
            chosen = ev[1]
    state.menu_selection = view.focus
    return chosen


# ===================================================================
#  PAUSE
# ===================================================================

def pause_resume_rect():
    return (CX - 160, CY + 44, 320, 60)


def show_pause_screen(frame, state):
    theme = get_theme(state.settings)
    draw_overlay(frame, 0.58)
    pulse = 0.82 + 0.18 * math.sin(state.current_time * 3.0)
    ui.text(frame, "PAUSED", CX, CY - 62, 84, ui.mix((0, 0, 0), ui.TEXT, pulse), "center", "bold", spacing=8, shadow=True)
    ui.text(frame, "Raise both open palms, or press R, to resume", CX, CY - 4, 19, ui.TEXT_2, "center", "medium")
    mx, my = state.mouse_pos
    r = pause_resume_rect()
    hot = r[0] <= mx <= r[0] + r[2] and r[1] <= my <= r[1] + r[3]
    widgets._draw_item(frame, {"kind": "button", "label": "RESUME", "primary": True, "hint": "R"}, r,
                  1.0 if hot else 0.0, 1.0, theme["accent"])
    ui.hints(frame, [("R", "Resume"), ("ESC", "Menu")])


# ===================================================================
#  COUNTDOWN
# ===================================================================

def _name_plate(frame, x, y, w, h, role, name, sub, color, align):
    ui.panel(frame, x, y, w, h, 16, alpha=0.78)
    edge_x = x if align == "left" else x + w - 5
    ui.fill_rrect(frame, edge_x, y + 14, 5, h - 28, 2.5, color)
    ui.text(frame, role, x + w / 2, y + 30, 13, ui.TEXT_3, "center", "bold", spacing=2.4)
    ui.text(frame, _fit_name(name, 34, w - 40), x + w / 2, y + 72, 34, color, "center", "bold", shadow=True)
    ui.text(frame, sub, x + w / 2, y + 112, 14, ui.TEXT_3, "center", "bold", spacing=2)


def _mode_line(state):
    s = state.settings
    if s["game_mode"] == 0:
        return f"FIRST TO {s['score_to_win']} POINTS"
    if s["game_mode"] == 1:
        return "SURVIVE AS LONG AS YOU CAN"
    return f"{state.settings['time_limit']} SECONDS  -  MOST POINTS WINS"


def _point_banner(frame, state):
    """Between rallies: who just scored, in the "GET READY" line for two seconds.  True if drawn."""
    if state.last_point is None or state.settings["game_mode"] == 1:
        return False
    side, t0 = state.last_point
    age = state.current_time - t0
    if not 0 <= age < 2.0:
        return False
    theme = get_theme(state.settings)
    col = theme["left_paddle"] if side == 0 else theme["right_paddle"]
    pop = 1.0 + 0.25 * max(0.0, 1.0 - age / 0.3) ** 2
    fade = min(1.0, (2.0 - age) / 0.4)
    name = ui.fit_text(state.match_names[side], 30, "bold", 420).upper()
    label_w = ui.text_width("POINT  ", 30, "bold", 1.5)
    name_w = ui.text_width(name, 30, "bold", 1.5)
    x0 = CX - (label_w + name_w) / 2
    ui.text(frame, "POINT", x0, CY - 168, round(30 * pop), ui.TEXT_2, "left", "bold", opacity=fade, spacing=1.5)
    ui.text(frame, name, x0 + label_w, CY - 168, round(30 * pop), col, "left", "bold", opacity=fade, spacing=1.5, shadow=True)
    return True


def _hand_icon(frame, cx, cy, s, color):
    """A flat open hand: palm, four fingers, thumb (s = palm width)."""
    ui.fill_rrect(frame, cx - s / 2, cy - s * 0.1, s, s * 0.8, s * 0.22, color)
    for i in range(4):
        fh = s * (0.62 if i in (1, 2) else 0.5)
        ui.fill_rrect(frame, cx - s / 2 + i * s * 0.27, cy - s * 0.1 - fh, s * 0.2, fh + s * 0.2, s * 0.1, color)
    ui.fill_rrect(frame, cx - s * 0.72, cy + s * 0.12, s * 0.42, s * 0.2, s * 0.1, color)


def _help_card(frame, x, y, w, h, n, title, lines, theme):
    ui.panel(frame, x, y, w, h, 16, alpha=0.55)
    ui.disc(frame, x + 28, y + 30, 14, theme["accent"])
    ui.text(frame, str(n), x + 28, y + 30, 17, (24, 20, 18), "center", "bold")
    ui.text(frame, title, x + 52, y + 30, 19, ui.TEXT, "left", "bold", spacing=1.0)
    for i, ln in enumerate(lines):
        ui.text(frame, ln, x + 22, y + h - 64 + i * 24, 16, ui.TEXT_2, "left", "medium")


def draw_help_overlay(frame, state):
    """HOW TO PLAY: three pictured steps, the rules of the selected mode and a few tips."""
    theme = get_theme(state.settings)
    acc, now = theme["accent"], state.current_time
    draw_overlay(frame, 0.90)
    px, py, pw, ph = CX - 480, 56, 960, 608
    ui.panel(frame, px, py, pw, ph, 22, alpha=0.97)
    ui.text(frame, "HOW TO PLAY", CX, py + 50, 38, ui.TEXT, "center", "bold", spacing=2, shadow=True)

    cw, ch, cy0 = 290, 250, py + 92
    xs = [px + 24 + i * (cw + 18) for i in range(3)]
    # 1. stand back, hand up
    _help_card(frame, xs[0], cy0, cw, ch, 1, "STAND BACK", ["About one metre from the camera.", "Keep your hand up and open."], theme)
    ui.rrect(frame, xs[0] + 55, cy0 + 56, 180, 100, 12, ui.TEXT_3, 2)               # the camera's view
    _hand_icon(frame, xs[0] + 145, cy0 + 118, 46, ui.mix(acc, (255, 255, 255), 0.2))
    # 2. move the hand = move the paddle
    _help_card(frame, xs[1], cy0, cw, ch, 2, "MOVE YOUR HAND", ["Up and down moves your paddle.", "Hit near the edge to angle the ball."], theme)
    bob = math.sin(now * 2.6) * 24
    ui.fill_rrect(frame, xs[1] + 232, cy0 + 82 + bob, 10, 56, 5, theme["left_paddle"])
    _hand_icon(frame, xs[1] + 120, cy0 + 118 + bob, 42, ui.mix(acc, (255, 255, 255), 0.2))
    ui.triangle(frame, xs[1] + 60, cy0 + 70, 8, "up", ui.TEXT_3)
    ui.triangle(frame, xs[1] + 60, cy0 + 168, 8, "down", ui.TEXT_3)
    # 3. sides
    _help_card(frame, xs[2], cy0, cw, ch, 3, "YOUR SIDE", ["Left of the picture is player 1,", "right is player 2 (or the CPU)."], theme)
    ui.rrect(frame, xs[2] + 55, cy0 + 56, 180, 100, 12, ui.TEXT_3, 2)
    ui.hline(frame, xs[2] + 145, xs[2] + 146, cy0 + 56, ui.TEXT_3)
    ui.fill_rrect(frame, xs[2] + 144, cy0 + 60, 2, 92, 1, ui.TEXT_3)
    ui.text(frame, "P1", xs[2] + 100, cy0 + 106, 26, theme["left_paddle"], "center", "bold")
    ui.text(frame, "P2", xs[2] + 190, cy0 + 106, 26, theme["right_paddle"], "center", "bold")

    ty = cy0 + ch + 38
    ui.text(frame, "THE GAME", px + 36, ty, 13, ui.TEXT_3, "left", "bold", spacing=2.4)
    ui.text(frame, "THIS MODE", px + 36, ty + 66, 13, ui.TEXT_3, "left", "bold", spacing=2.4)
    ui.text(frame, "NO CAMERA OR TROUBLE", px + 36, ty + 132, 13, ui.TEXT_3, "left", "bold", spacing=2.4)
    if state.event_mode:
        rule = (f"Beat the CPU for {state.settings['time_limit']} seconds. Every point counts; your best attempt goes on the leaderboard."
                if state.finals is None else "Head to head, first to the target score. Tell the organiser if you need to withdraw.")
    else:
        rule = _mode_line(state).capitalize() + "."
    ui.text(frame, "Rally for points. Miss the ball and your opponent scores. The ball speeds up the longer you play.",
            px + 36, ty + 28, 17, ui.TEXT_2, "left", "medium")
    ui.text(frame, rule, px + 36, ty + 94, 17, ui.TEXT_2, "left", "medium")
    ui.text(frame, "W / S or the arrow keys move a paddle.  C switches camera.  Good light on your hand helps a lot.",
            px + 36, ty + 160, 17, ui.TEXT_2, "left", "medium")
    ui.hints(frame, [("H / ESC", "Close")], backdrop=True)


def _hand_chip(frame, state, hand, cx, y):
    """Under a player's name plate: is their hand being tracked yet?"""
    if not state.camera_ok:
        label, col = "KEYBOARD  W / S", ui.TEXT_2
    elif state.hand_pos[hand] is not None:
        label, col = "HAND READY", ui.SUCCESS
    elif int(state.current_time * 2.5) % 2:
        label, col = "SHOW YOUR HAND", ui.TEXT_3
    else:
        label, col = "SHOW YOUR HAND", ui.WARN
    w = ui.text_width(label, 14, "bold", 0.8) + 34
    ui.chip(frame, cx - w / 2, y, label, col, h=28, size=14, pad=17)


def show_countdown_screen(frame, state):
    theme = get_theme(state.settings)
    draw_overlay(frame, 0.40)
    left_name, right_name = state.player_names()
    cpu = state.cpu_side()
    _name_plate(frame, 52, CY - 70, 280, 140, "COMPUTER" if cpu == "left" else "PLAYER 1",
                left_name, "AUTO" if cpu == "left" else "LEFT HAND", theme["left_paddle"], "left")
    _name_plate(frame, WINDOW_WIDTH - 332, CY - 70, 280, 140,
                "COMPUTER" if cpu == "right" else ("PLAYER 1" if cpu == "left" else "PLAYER 2"),
                right_name, "AUTO" if cpu == "right" else "RIGHT HAND", theme["right_paddle"], "right")

    for side, name, plate_cx in (("Left", "left", 192), ("Right", "right", WINDOW_WIDTH - 192)):
        if cpu != name:
            _hand_chip(frame, state, side, plate_cx, CY + 84)

    remaining = COUNTDOWN_DURATION - (state.current_time - state.countdown_start)
    if not _point_banner(frame, state):
        ui.text(frame, "GET READY", CX, CY - 168, 24, ui.TEXT_2, "center", "bold", spacing=6)
    if remaining > 0:
        frac = 1.0 - (remaining % 1)
        ui.progress_ring(frame, CX, CY, 104, frac, theme["accent"], ui.mix(ui.PANEL, (255, 255, 255), 0.10), 7)
        pop = 1.0 + 0.10 * (1.0 - frac)
        ui.text(frame, str(math.ceil(remaining)), CX, CY + 2, round(76 * pop), ui.TEXT, "center", "pixel", shadow=True)
    else:
        ui.progress_ring(frame, CX, CY, 104, 1.0, ui.SUCCESS, ui.SUCCESS, 7)
        ui.text(frame, "GO!", CX, CY + 2, 56, ui.SUCCESS, "center", "pixel", shadow=True)
    ui.chip(frame, CX - ui.text_width(_mode_line(state), 15, "bold", 0.8) / 2 - 12, CY + 150, _mode_line(state), ui.TEXT_2, h=30, size=15)


# ===================================================================
#  GAME OVER
# ===================================================================

def gameover_rects():
    return {"rematch": (CX - 316, 506, 306, 62), "menu": (CX + 10, 506, 306, 62)}


def show_game_over_screen(frame, state, stats):
    theme = get_theme(state.settings)
    accent = theme["accent"]
    mode = state.settings["game_mode"]
    draw_overlay(frame, 0.68)
    ui.panel(frame, CX - 380, 78, 760, 520, 22, alpha=0.84)

    n1, n2 = state.match_names
    if state.winner == "Draw":
        label, headline, hcol = "MATCH COMPLETE", "IT'S A DRAW", ui.WARN
    elif mode == 1:
        label, headline, hcol = "RUN COMPLETE", f"{state.survival_rally} RALLIES", ui.SUCCESS
    elif "Left" in state.winner:
        label, headline, hcol = "MATCH COMPLETE", f"{_fit_name(n1, 56, 640)} WINS", (ui.SUCCESS if state.cpu_side() != "left" else DANGER_SOFT)
    else:
        label, headline, hcol = "MATCH COMPLETE", f"{_fit_name(n2, 56, 640)} WINS", (80, 180, 255) if state.cpu_side() != "right" else DANGER_SOFT
    age = max(0.0, state.current_time - state.gameover_time)
    ui.text(frame, label, CX, 120, 14, ui.TEXT_3, "center", "bold", spacing=4)
    pop = 1.0 + 0.30 * max(0.0, 1.0 - age / 0.45) ** 2                  # the headline lands with a bounce
    ui.text(frame, headline.upper(), CX, 176, round(56 * pop), hcol, "center", "bold", spacing=1.5, shadow=True)

    if mode == 1:
        ui.text(frame, str(state.survival_rally), CX, 280, 64, accent, "center", "pixel", shadow=True)
    else:
        ls, rs = state.score
        lw, rw = ls > rs, rs > ls
        count = min(1.0, age / 0.8)                                       # scores count up from 0
        ui.text(frame, str(round(ls * count)), CX - 130, 280, 60, accent if lw else ui.TEXT_2, "center", "pixel", shadow=lw)
        ui.text(frame, "-", CX, 280, 40, ui.TEXT_3, "center", "pixel")
        ui.text(frame, str(round(rs * count)), CX + 130, 280, 60, accent if rw else ui.TEXT_2, "center", "pixel", shadow=rw)
        ui.text(frame, _fit_name(n1, 22, 220), CX - 130, 334, 22, theme["left_paddle"], "center", "bold")
        ui.text(frame, _fit_name(n2, 22, 220), CX + 130, 334, 22, theme["right_paddle"], "center", "bold")

    tw, gap = 200, 16
    x0 = CX - (3 * tw + 2 * gap) / 2
    tiles = ((HIGH_SCORE_LABELS[mode], str(state.high_score)), ("BEST COMBO", f"x{max(1, state.max_combo)}"),
             ("BEST RALLY", str(state.max_rally)))
    for i, (lab, val) in enumerate(tiles):
        ui.stat_tile(frame, x0 + i * (tw + gap), 384, tw, 92, lab, val, accent)

    if state.new_best:
        pulse = 0.5 + 0.5 * math.sin(state.current_time * 5)
        ui.chip(frame, x0 + 8, 366, "NEW BEST", ui.mix(ui.GOLD, (255, 255, 255), 0.4 * pulse), h=24, size=13)

    r = gameover_rects()
    mx, my = state.mouse_pos
    for key, lab, primary, hint in (("rematch", "PLAY AGAIN", True, "SPACE"), ("menu", "MAIN MENU", False, "ESC")):
        x, y, w, h = r[key]
        hot = x <= mx <= x + w and y <= my <= y + h
        widgets._draw_item(frame, {"kind": "button", "label": lab, "primary": primary, "hint": hint, "label_size": 24}, r[key],
                      1.0 if hot else 0.0, 1.0, accent)
    if state.restart_gesture_time is not None:
        frac = (state.current_time - state.restart_gesture_time) / GESTURE_REQUIRED_DURATION
        x, y, w, h = r["rematch"]
        ui.progress_bar(frame, x + 22, y + h - 14, w - 44, 5, frac, (255, 255, 255), ui.mix(accent, (0, 0, 0), 0.55))
    ui.hints(frame, [("SPACE", "Play again"), ("ESC", "Main menu"), ("HANDS", "Raise both to rematch")])

    # celebrate a win by a person (not a CPU win, not a draw); a Survival run only for a new best
    won_side = "left" if "Left" in state.winner else ("right" if "Right" in state.winner else None)
    celebrate = state.new_best if mode == 1 else (won_side is not None and state.cpu_side() != won_side)
    if celebrate:
        wcol = theme["left_paddle"] if won_side == "left" else theme["right_paddle"]
        ui.confetti(frame, age - 0.15, [wcol, accent, ui.GOLD, (255, 255, 255)], avoid=(CX - 380, 78, 760, 520))


DANGER_SOFT = (96, 96, 240)
