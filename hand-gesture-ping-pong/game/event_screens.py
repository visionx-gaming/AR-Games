"""Event (qualifier) and finals screens, in the same visual language as the menus."""

import math

from game import ui, widgets
from game.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, EVENT_TITLE, EVENT_LEADERBOARD_ROWS, EVENT_RESULT_SECONDS,
    FINALS_RESULT_SECONDS, TIME_ATTACK_DURATION, get_theme,
)
from game.renderer import draw_overlay
from game.stats import clean_name

CX, CY = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
MEDALS = [(0, 205, 255), (215, 215, 215), (70, 140, 215)]        # gold, silver, bronze (BGR)


def _pulse(now, speed=3.0):
    return 0.5 + 0.5 * math.sin(now * speed)


def _title(frame, text, y, accent):
    ui.text(frame, text, CX, y, 34, accent, "center", "pixel", shadow=True)


def _cta(frame, label, hint, y, accent, now, w=440, h=58):
    """Pulsing primary call-to-action button."""
    widgets._draw_item(frame, {"kind": "button", "label": label, "primary": True, "hint": hint},
                  (CX - w / 2, y, w, h), 0.3 + 0.7 * _pulse(now), 1.0, accent)


# ===================================================================
#  QUALIFIER
# ===================================================================

def show_event_home(frame, state):
    """Leaderboard + 'press space to play' - the screen shown between players."""
    theme = get_theme(state.settings)
    accent = theme["accent"]
    board = state.event_board
    now = state.current_time
    draw_overlay(frame, 0.52)

    _title(frame, EVENT_TITLE.replace("  ", " "), 72, accent)
    ui.text(frame, f"{TIME_ATTACK_DURATION} SECONDS   -   BEAT THE CPU   -   BEST SCORE WINS", CX, 120, 16,
            ui.TEXT_2, "center", "bold", spacing=3)

    ranking = board.ranking()
    x, y, w, h = 190, 150, 900, 462
    ui.panel(frame, x, y, w, h, 20, alpha=0.78)
    cols = {"rank": x + 54, "player": x + 104, "score": x + 560, "points": x + 688, "tries": x + 808}
    for label, cx_, anchor in (("RANK", cols["rank"], "center"), ("PLAYER", cols["player"], "left"),
                               ("SCORE", cols["score"], "center"), ("POINTS", cols["points"], "center"),
                               ("TRIES", cols["tries"], "center")):
        ui.text(frame, label, cx_, y + 34, 13, ui.TEXT_3, anchor, "bold", spacing=2)
    ui.hline(frame, x + 22, x + w - 22, y + 56, ui.mix(ui.PANEL, (255, 255, 255), 0.14))

    rows = ranking[:EVENT_LEADERBOARD_ROWS]
    if not rows:
        ui.text(frame, "NO SCORES YET  -  BE THE FIRST!", CX, y + h / 2, 24, accent, "center", "bold", spacing=1.5)
    for i, e in enumerate(rows):
        ry = y + 92 + i * 37
        if i % 2 == 0:
            ui.fill_rrect(frame, x + 14, ry - 18, w - 28, 36, 9, ui.PANEL_HI, 0.38)
        top = e["rank"] <= 3
        col = MEDALS[e["rank"] - 1] if top else ui.TEXT
        if top:
            ui.disc(frame, cols["rank"], ry, 15, col)
            ui.text(frame, str(e["rank"]), cols["rank"], ry, 18, (24, 20, 18), "center", "bold")
        else:
            ui.text(frame, f"{e['rank']}{'=' if e['tied'] else ''}", cols["rank"], ry, 19, ui.TEXT_3, "center", "bold")
        if top and e["tied"]:
            ui.text(frame, "=", cols["rank"] + 24, ry, 18, ui.TEXT_3, "left", "bold")
        ui.text(frame, ui.fit_text(e["player"], 22, "bold", 380), cols["player"], ry, 22, col, "left", "bold")
        ui.text(frame, f"{e['net']:+d}", cols["score"], ry, 24, col, "center", "bold")
        ui.text(frame, f"{e['scored']} - {e['conceded']}", cols["points"], ry, 18, ui.TEXT_2, "center", "semi")
        ui.text(frame, str(e["attempts"]), cols["tries"], ry, 18, ui.TEXT_2, "center", "semi")

    _cta(frame, "PRESS SPACE TO PLAY", "SPACE", 628, accent, now)
    ui.hints(frame, [("ESC", "Organiser: leave tournament"), ("F", "Fullscreen"), ("C", "Camera")], y=30)
    mx = state.event_max_attempts
    ui.text(frame, f"{len(ranking)} PLAYERS   -   {len(board.rows)} GAMES   -   {mx} ATTEMPT{'S' if mx != 1 else ''} EACH",
            CX, 706, 13, ui.TEXT_3, "center", "bold", spacing=2)


def draw_tournament_exit_dialog(frame, state):
    """Organiser prompt: leave the tournament screens and go back to the main menu."""
    draw_overlay(frame, 0.78)
    ui.panel(frame, CX - 300, CY - 110, 600, 220, 18, alpha=0.94)
    ui.text(frame, "LEAVE TOURNAMENT?", CX, CY - 56, 34, ui.TEXT, "center", "bold", spacing=1.5, shadow=True)
    ui.text(frame, "Back to the main menu. Scores and the bracket stay saved.", CX, CY - 8, 18, ui.TEXT_2, "center", "medium")
    ui.text(frame, "Y  =  LEAVE          N  =  STAY", CX, CY + 48, 22, ui.WARN, "center", "bold", spacing=2)
    ui.hints(frame, [("Y", "Leave"), ("N / ESC", "Stay")], backdrop=True)


def draw_event_name_dialog(frame, state):
    """Single-field name entry, with live feedback about attempts."""
    theme = get_theme(state.settings)
    accent = theme["accent"]
    board = state.event_board
    draw_overlay(frame, 0.82)
    ui.panel(frame, CX - 330, CY - 160, 660, 320, 20, alpha=0.95)
    ui.text(frame, "ENTER YOUR NAME", CX, CY - 106, 36, ui.TEXT, "center", "bold", spacing=1.5, shadow=True)

    buf = state.name_edit_buf[0]
    x1, y1, x2, y2 = CX - 260, CY - 56, CX + 260, CY - 4
    col = theme["left_paddle"]
    ui.fill_rrect(frame, x1, y1, x2 - x1, y2 - y1, 10, ui.mix(ui.PANEL_HI, col, 0.14), 0.95)
    ui.rrect(frame, x1, y1, x2 - x1, y2 - y1, 10, col, 2)
    ui.text(frame, buf, x1 + 20, (y1 + y2) / 2, 26, ui.TEXT, "left", "bold")
    if int(state.current_time * 2) % 2 == 0:
        ui.fill_rrect(frame, x1 + 20 + ui.text_width(buf, 26, "bold") + 3, y1 + 11, 2.5, (y2 - y1) - 22, 1, accent)

    name = clean_name(buf, "")
    mx = state.event_max_attempts
    if not name:
        msg, mcol = "Type your name, then press ENTER", ui.TEXT_3
    else:
        n = board.attempts(name)
        if n >= mx:
            msg, mcol = f"Already played {n} of {mx}  -  no attempts left", ui.DANGER
        elif n > 0:
            msg, mcol = f"Welcome back  -  attempt {n + 1} of {mx}", ui.SUCCESS
        else:
            msg, mcol = f"Attempt 1 of {mx}  -  good luck!", ui.SUCCESS
    ui.text(frame, msg, CX, CY + 36, 19, mcol, "center", "bold")
    ui.text(frame, "Use first name + initial so it stays unique", CX, CY + 76, 15, ui.TEXT_3, "center", "medium")
    ui.hints(frame, [("ENTER", "Start"), ("ESC", "Cancel")], backdrop=True)


def show_event_result(frame, state):
    """What the player just scored, and where that puts them."""
    theme = get_theme(state.settings)
    accent = theme["accent"]
    r = state.event_result
    now = state.current_time
    mx = state.event_max_attempts
    draw_overlay(frame, 0.70)
    ui.panel(frame, CX - 390, 56, 780, 608, 22, alpha=0.86)

    ui.text(frame, "TIME UP", CX, 100, 14, ui.TEXT_3, "center", "bold", spacing=5)
    ui.text(frame, ui.fit_text(r["player"], 46, "bold", 640), CX, 156, 46, accent, "center", "bold", spacing=1, shadow=True)
    ui.text(frame, "YOUR SCORE", CX, 214, 13, ui.TEXT_3, "center", "bold", spacing=3)
    net = r["net"]
    ncol = ui.SUCCESS if net > 0 else (ui.DANGER if net < 0 else ui.TEXT_2)
    ui.text(frame, f"{net:+d}", CX, 292, 84, ncol, "center", "pixel", shadow=True)
    ui.text(frame, f"YOU  {r['scored']}      CPU  {r['conceded']}", CX, 352, 22, ui.TEXT_2, "center", "bold", spacing=1)

    ui.panel(frame, CX - 310, 392, 620, 170, 16, alpha=0.7)
    medal = MEDALS[r["rank"] - 1] if r["rank"] <= 3 else accent
    ui.disc(frame, CX - 218, 452, 30, medal)
    ui.text(frame, f"#{r['rank']}", CX - 218, 452, 24, (24, 20, 18), "center", "bold")
    ui.text(frame, f"RANK {r['rank']} OF {r['players']}" + ("  (TIED)" if r["tied"] else ""), CX - 168, 442, 34, medal,
            "left", "bold", spacing=1)
    if r["attempt"] > 1 and r["is_best"]:
        p = 0.65 + 0.35 * _pulse(now, 6)
        ui.text(frame, "NEW PERSONAL BEST!", CX - 168, 482, 18, ui.mix((0, 0, 0), ui.GOLD, p), "left", "bold", spacing=1.5)
    elif r["attempt"] > 1:
        ui.text(frame, f"Your best stays {r['prev_best_net']:+d}", CX - 168, 482, 18, ui.TEXT_2, "left", "semi")
    left = mx - r["attempt"]
    ui.text(frame, f"ATTEMPT {r['attempt']} OF {mx}   -   " + ("NO ATTEMPTS LEFT" if left <= 0 else f"{left} LEFT"),
            CX, 530, 14, ui.TEXT_3, "center", "bold", spacing=2)

    remaining = max(0.0, state.event_result_until - now)
    ui.progress_bar(frame, CX - 200, 594, 400, 6, remaining / EVENT_RESULT_SECONDS, accent)
    ui.text(frame, f"Next player in {int(remaining) + 1}   -   press SPACE to skip", CX, 628, 15, ui.TEXT_3, "center", "medium")


# ===================================================================
#  FINALS
# ===================================================================

_BOX_W, _BOX_H = 340, 122
_BOX_POS = {"SF1": (60, 116), "SF2": (60, 260), "FINAL": (470, 188), "THIRD": (880, 188)}


def _draw_match_box(frame, x, y, m, state, theme):
    accent = theme["accent"]
    w, h = _BOX_W, _BOX_H
    now = state.current_time
    if m["is_next"]:
        ui.panel(frame, x, y, w, h, 16, alpha=0.82, border=accent, border_alpha=0.45 + 0.4 * _pulse(now))
    else:
        ui.panel(frame, x, y, w, h, 16, alpha=0.62 if m["done"] else 0.5)
    ui.text(frame, m["label"], x + 20, y + 26, 13, accent if m["is_next"] else ui.TEXT_3, "left", "bold", spacing=1.8)
    if not m["done"]:
        ui.text(frame, f"FIRST TO {m['target']}", x + w - 20, y + 26, 12, ui.TEXT_3, "right", "bold", spacing=1.4)
    for i, (name, ref, score) in enumerate(((m["p1"], m["ref1"], m["s1"]), (m["p2"], m["ref2"], m["s2"]))):
        ry = y + 66 + i * 34
        if name is None:
            ui.text(frame, ref, x + 20, ry, 17, ui.TEXT_3, "left", "medium")
            continue
        won = m["done"] and m["winner"] == name
        col = ui.GOLD if won else (ui.TEXT_3 if m["done"] else ui.TEXT)
        ui.text(frame, ui.fit_text(name, 20, "bold", w - 120), x + 20, ry, 20, col, "left", "bold")
        if m["wo"]:
            ui.text(frame, "W/O" if won else "OUT", x + w - 22, ry, 15, col, "right", "bold")
        elif score is not None:
            ui.text(frame, str(score), x + w - 22, ry, 22, col, "right", "bold")


def show_finals_home(frame, state):
    theme = get_theme(state.settings)
    accent = theme["accent"]
    now = state.current_time
    draw_overlay(frame, 0.55)
    f = state.finals

    if f is None:
        _title(frame, "FINALS", 90, accent)
        ui.text(frame, state.finals_error.upper() or "NO BRACKET", CX, 330, 22, ui.DANGER, "center", "bold", spacing=1)
        ui.text(frame, "Run the TOURNAMENT QUALIFIER from the main menu first", CX, 380, 18, ui.TEXT_3, "center", "medium")
        return
    if f.complete:
        _draw_podium(frame, state, theme)
        return

    _title(frame, "FINALS", 72, accent)
    view = f.view()
    po = [m for m in view if m["id"].startswith("PO")]
    for m in view:
        if m["id"] in _BOX_POS:
            _draw_match_box(frame, *_BOX_POS[m["id"]], m, state, theme)
    for i, m in enumerate(po):
        _draw_match_box(frame, 60 + i * 360, 412, m, state, theme)
    if po:
        ui.text(frame, "SUDDEN-DEATH PLAYOFF FOR A FINALS SEAT  -  TIED ON SCORE, POINTS AND RALLY", CX, 396, 13, ui.WARN,
                "center", "bold", spacing=1.6)

    # bracket connectors: semi-finals -> final
    lc = ui.mix(ui.PANEL, (255, 255, 255), 0.30)
    ui.hline(frame, 400, 435, 177, lc, 2)
    ui.hline(frame, 400, 435, 321, lc, 2)
    ui.fill_rrect(frame, 434, 177, 2, 144, 1, lc)
    ui.hline(frame, 435, 470, 249, lc, 2)

    text, until = state.finals_notice
    if text and now < until:
        ui.text(frame, text, CX, 556, 17, ui.WARN, "center", "bold", spacing=0.6)

    nxt = f.next_match()
    if nxt:
        ui.text(frame, f"NEXT  -  {nxt['label']}", CX, 584, 14, ui.TEXT_3, "center", "bold", spacing=3)
        ui.text(frame, f"{ui.fit_text(nxt['p1'], 26, 'bold', 300)}   (LEFT)    vs    {ui.fit_text(nxt['p2'], 26, 'bold', 300)}   (RIGHT)",
                CX, 616, 24, ui.TEXT, "center", "bold")
        _cta(frame, "START MATCH", "SPACE", 636, accent, now, w=340, h=52)
        lo, ro = state.hand_pos["Left"] is not None, state.hand_pos["Right"] is not None
        ui.text(frame, f"LEFT HAND {'OK' if lo else 'NOT SEEN'}", 60, 704, 14, ui.SUCCESS if lo else ui.DANGER, "left", "bold", spacing=1.4)
        ui.text(frame, f"RIGHT HAND {'OK' if ro else 'NOT SEEN'}", WINDOW_WIDTH - 60, 704, 14, ui.SUCCESS if ro else ui.DANGER,
                "right", "bold", spacing=1.4)
    ui.hints(frame, [("W", "Withdraw a player"), ("F", "Fullscreen"), ("C", "Camera")], y=30)


def _draw_podium(frame, state, theme):
    now = state.current_time
    first, second, third, fourth = state.finals.podium()
    p = 0.7 + 0.3 * _pulse(now, 2.5)
    ui.text(frame, "CHAMPION", CX, 92, 54, ui.mix((0, 0, 0), ui.GOLD, p), "center", "bold", spacing=8, shadow=True)

    bottom = 568
    for name, place, x, top in ((second, 2, CX - 355, 410), (first, 1, CX - 120, 336), (third, 3, CX + 115, 458)):
        col = MEDALS[place - 1]
        ui.panel(frame, x, top, 240, bottom - top, 16, fill=ui.mix(ui.PANEL, col, 0.22), alpha=0.9, border=col, border_alpha=0.8)
        ui.text(frame, str(place), x + 120, top + 80, 64, col, "center", "pixel", shadow=True)
        size = 34 if place == 1 else 28
        ui.text(frame, ui.fit_text(name, size, "bold", 330), x + 120, top - 34, size, col, "center", "bold", shadow=True)
    ui.text(frame, f"4TH   {fourth}", CX, 610, 22, ui.TEXT_2, "center", "bold")
    fifth = state.finals.fifth()
    if fifth:
        ui.text(frame, f"5TH   {fifth}     (best of the rest from the qualifier)", CX, 644, 17, ui.TEXT_3, "center", "medium")
    ui.text(frame, "CONGRATULATIONS TO ALL OUR PLAYERS!", CX, 690, 17, theme["accent"], "center", "bold", spacing=2)


def show_finals_result(frame, state):
    theme = get_theme(state.settings)
    accent = theme["accent"]
    r = state.finals_result
    now = state.current_time
    draw_overlay(frame, 0.72)
    ui.panel(frame, CX - 400, 70, 800, 570, 22, alpha=0.86)

    ui.text(frame, r["label"], CX, 118, 16, ui.TEXT_3, "center", "bold", spacing=5)
    ui.text(frame, "MATCH COMPLETE", CX, 160, 14, ui.TEXT_3, "center", "bold", spacing=5)
    size = 62 if len(r["winner"]) <= 9 else 46
    ui.text(frame, ui.fit_text(r["winner"], size, "bold", 700), CX, 236, size, ui.GOLD, "center", "bold", spacing=1, shadow=True)
    ui.text(frame, "WINS", CX, 294, 26, ui.SUCCESS, "center", "bold", spacing=6)
    ui.panel(frame, CX - 320, 336, 640, 130, 16, alpha=0.7)
    ui.text(frame, f"{r['s1']}  -  {r['s2']}", CX, 396, 54, accent, "center", "pixel", shadow=True)
    ui.text(frame, f"{ui.fit_text(r['p1'], 20, 'bold', 250)}   vs   {ui.fit_text(r['p2'], 20, 'bold', 250)}", CX, 442, 20,
            ui.TEXT_2, "center", "bold")

    if r["complete"]:
        msg = "THE FINALS ARE COMPLETE  -  SEE THE PODIUM"
    elif r["next"]:
        n = r["next"]
        msg = f"NEXT UP  -  {n['label']}:  {n['p1']}  vs  {n['p2']}"
    else:
        msg = ""
    ui.text(frame, msg, CX, 508, 18, ui.TEXT, "center", "bold", spacing=0.6)
    remaining = max(0.0, state.event_result_until - now)
    ui.progress_bar(frame, CX - 200, 566, 400, 6, remaining / FINALS_RESULT_SECONDS, accent)
    ui.text(frame, f"Continuing in {int(remaining) + 1}   -   press SPACE to skip", CX, 600, 15, ui.TEXT_3, "center", "medium")


def draw_finals_withdraw_dialog(frame, state):
    """Organiser dialog: pick a player by number, then confirm."""
    theme = get_theme(state.settings)
    accent = theme["accent"]
    w = state.finals_withdraw
    draw_overlay(frame, 0.84)
    names = w["names"][:9]
    pw, ph = 660, 230 + 54 * max(len(names), 2)
    px, py = CX - pw // 2, CY - ph // 2
    ui.panel(frame, px, py, pw, ph, 20, alpha=0.95)
    ui.text(frame, "WITHDRAW A PLAYER", CX, py + 60, 36, ui.TEXT, "center", "bold", spacing=1.5, shadow=True)

    if w["pick"] is None:
        for i, n in enumerate(names):
            ry = py + 120 + i * 54
            ui.fill_rrect(frame, px + 40, ry - 22, pw - 80, 46, 11, ui.PANEL_HI, 0.7)
            ui.fill_rrect(frame, px + 54, ry - 13, 28, 26, 7, ui.mix(ui.PANEL, accent, 0.45))
            ui.text(frame, str(i + 1), px + 68, ry, 16, ui.TEXT, "center", "bold")
            ui.text(frame, ui.fit_text(n, 22, "bold", pw - 200), px + 100, ry, 22, ui.TEXT, "left", "bold")
        ui.hints(frame, [("1-9", "Pick player"), ("ESC", "Cancel")], backdrop=True)
    else:
        ui.text(frame, f"Withdraw  {w['pick']}?", CX, py + 140, 30, ui.DANGER, "center", "bold")
        ui.text(frame, "If they have not played yet, the next-best qualifier takes their place;", CX, py + 190, 17, ui.TEXT_2, "center", "medium")
        ui.text(frame, "otherwise their opponent advances by walkover.", CX, py + 218, 17, ui.TEXT_2, "center", "medium")
        ui.hints(frame, [("Y", "Confirm"), ("N", "Back"), ("ESC", "Cancel")], backdrop=True)
