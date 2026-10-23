"""The settings screen: four tabs (gameplay, audio, display, camera) built on game.ui.MenuView.

change_setting() is the single place a setting index turns into a state change; the screen
and the in-game menu both go through it.  Display / camera rows act through state.system.
"""

from game import ui, widgets
from game.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, DIFFICULTY_NAMES, GAME_MODE_NAMES, THEME_NAMES, COLOR_THEMES,
    get_theme,
)
from game.stats import save_settings
from game.system import CAMERA_QUALITIES

CX, CY = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2

VIEW = widgets.MenuView("settings")


_TABS = ["GAMEPLAY", "AUDIO", "DISPLAY", "CAMERA"]
_tab = 0

# Match-defining options can't be changed from the in-game menu.
_LOCKED_IN_GAME = frozenset({0, 1, 2, 3, 9, 10})

# OPPONENT / PLAYERS choices: index == GameState.player_mode()
PLAYER_MODE_LABELS = ["2 PLAYERS", "CPU RIGHT", "CPU LEFT"]

_DESC = {
    0: "How many points a player needs to win a Classic match.",
    1: "Ball speed, and how sharp the CPU opponent is.",
    2: "Classic (first to score), Survival (longest rally) or Time Attack.",
    3: "Two players, or against the CPU. Pick which side the CPU plays: CPU RIGHT puts you on the left, CPU LEFT on the right.",
    4: "Colour theme for the court, paddles and menus.",
    5: "Master switch for all music and sound effects.",
    6: "Volume of the background music.",
    7: "Volume of hits, bounces and menu sounds.",
    8: "Draw the tracked hand skeleton on screen to help you line up.",
    9: "Moving blocks in the middle of the court.",
    10: "Random pick-ups: big paddle, speed boost, slow motion, multi-ball.",
    11: "Windowed, or fullscreen at the monitor's native resolution.",
    12: "Which attached monitor the game uses. Fullscreen always runs at that monitor's native resolution.",
    13: "AUTO renders at the monitor's full resolution. Pick a lower one for a smoother game on a slower PC.",
    14: "Choose among the cameras found. Plugged one in just now? Use RESCAN.",
    15: "AUTO picks the sharpest picture the camera can deliver at a steady frame rate.",
    16: "Look for newly attached cameras.",
    17: "Hide the camera picture behind the game for a distraction-free court. Hand tracking keeps working. Hotkey: V.",
    "i_render": "What the game is actually drawing at right now.",
    "i_cam": "The camera in use and the picture size it delivers.",
    "i_trk": "Hand detections per second, and how old the latest hand position is.",
}


def is_setting_locked(state, idx):
    return state.settings_return_state == "MENU" and idx in _LOCKED_IN_GAME


def change_setting(state, idx, direction, sound_mgr):
    if is_setting_locked(state, idx):
        return
    s = state.settings
    if idx == 0:
        s["score_to_win"] = max(1, min(20, s["score_to_win"] + direction))
    elif idx == 1:
        s["difficulty"] = max(0, min(2, s["difficulty"] + direction))
    elif idx == 2:
        s["game_mode"] = max(0, min(len(GAME_MODE_NAMES) - 1, s["game_mode"] + direction))
    elif idx == 3:
        state.set_player_mode(state.player_mode() + (direction or 1))
    elif idx == 4:
        s["color_theme"] = (s["color_theme"] + direction) % len(THEME_NAMES)
    elif idx == 5:
        s["sound_enabled"] = not s["sound_enabled"]
        sound_mgr.update_enabled(s["sound_enabled"])
        if s["sound_enabled"]:
            # Resume whichever track fits where we'll land: lobby music if
            # settings were opened from the main menu, otherwise the game's BGM.
            if state.settings_return_state == "START":
                sound_mgr.start_lobby_music(s["music_volume"])
            elif not sound_mgr.bgm_playing:
                sound_mgr.start_bgm(s["music_volume"])
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
    elif idx == 10:
        s["powerups_enabled"] = not s["powerups_enabled"]
    elif idx == 17:
        s["show_camera_feed"] = not s.get("show_camera_feed", True)
    elif idx in (11, 12, 13, 14, 15, 16):
        _system_setting(state, idx, direction)
    save_settings(s)


def _system_setting(state, idx, direction):
    """Display / camera settings act on the live window and camera (game.system)."""
    sysm = state.system
    if sysm is None:
        return
    if idx == 11:
        sysm.set_fullscreen(direction > 0)
    elif idx == 12:
        sysm.cycle_display(direction)
    elif idx == 13:
        sysm.cycle_render(direction)
    elif idx == 14:
        sysm.cycle_camera(direction)
    elif idx == 15:
        sysm.cycle_quality(direction)
    elif idx == 16:
        sysm.rescan_cameras()


def _display_value(sysm):
    ds = sysm.displays()
    i = min(sysm.current_display(), len(ds) - 1)
    d = ds[i]
    return f"DISPLAY {i + 1}  -  {d['w']}x{d['h']}" + ("  (PRIMARY)" if d["primary"] and len(ds) > 1 else "")


def _render_value(sysm):
    h = sysm.render_height()
    (fw, fh), _native = sysm.render_info()
    return f"{'AUTO' if not h else str(h) + 'P'}  -  {fw}x{fh}"


def _camera_value(sysm):
    st = sysm.camera_status()
    if st["switching"]:
        return f"SWITCHING TO CAMERA {st['target']}..."
    cams = sysm.cameras()
    if not cams:
        return "NONE FOUND"
    cur = next((c for c in cams if c["active"]), cams[0])
    return f"CAMERA {cur['index']}  -  {cur['w']}x{cur['h']}"


def _settings_items(state, tab):
    s = state.settings

    def mk(idx, **kw):
        item = {"id": idx, "enabled": not is_setting_locked(state, idx), "desc": _DESC[idx]}
        item.update(kw)                      # explicit values (e.g. enabled=False) win
        return item

    sysm = state.system

    if tab == 0:
        return [
            mk(2, label="GAME MODE", kind="select", value=GAME_MODE_NAMES[s["game_mode"]].upper()),
            mk(1, label="DIFFICULTY", kind="segment", options=[n.upper() for n in DIFFICULTY_NAMES],
               index=s["difficulty"]),
            mk(0, label="SCORE TO WIN", kind="slider", value=s["score_to_win"], lo=1, hi=20, step=1),
            mk(3, label="OPPONENT", kind="segment", options=PLAYER_MODE_LABELS, index=state.player_mode()),
            mk(9, label="OBSTACLES", kind="toggle", value=s["obstacles_enabled"]),
            mk(10, label="POWER-UPS", kind="toggle", value=s["powerups_enabled"]),
        ]
    if tab == 1:
        return [
            mk(5, label="SOUND", kind="toggle", value=s["sound_enabled"]),
            mk(6, label="MUSIC VOLUME", kind="slider", value=s["music_volume"], lo=0, hi=100, step=10, fmt="{}%"),
            mk(7, label="EFFECTS VOLUME", kind="slider", value=s["sfx_volume"], lo=0, hi=100, step=10, fmt="{}%"),
        ]
    ti = s["color_theme"] % len(COLOR_THEMES)
    theme_rows = [
        mk(4, label="COLOR THEME", kind="select", value=THEME_NAMES[ti].upper(), swatch=COLOR_THEMES[ti]["accent"]),
        mk(8, label="HAND SKELETON", kind="toggle", value=s["show_hand_skeleton"]),
    ]
    na = "NOT AVAILABLE"
    if tab == 2:
        (fw, fh), (nw, nh) = sysm.render_info() if sysm else ((0, 0), (0, 0))
        return [
            mk(11, label="WINDOW MODE", kind="segment", options=["WINDOWED", "FULLSCREEN"],
               index=1 if (sysm and sysm.is_fullscreen()) else 0, enabled=sysm is not None),
            mk(12, label="MONITOR", kind="select", value=_display_value(sysm) if sysm else na, enabled=sysm is not None),
            mk(13, label="RESOLUTION", kind="select", value=_render_value(sysm) if sysm else na, enabled=sysm is not None),
        ] + theme_rows + [
            {"id": "i_render", "label": "RENDERING", "kind": "info", "desc": _DESC["i_render"],
             "value": f"{fw}x{fh} on a {nw}x{nh} display" if sysm else na},
        ]
    cur = (sysm.quality() if sysm else 0)
    qi = next((i for i, (v, _) in enumerate(CAMERA_QUALITIES) if v == cur), 0)
    st = sysm.camera_status() if sysm else None
    cam_info = (f"CAMERA {st['index']}  |  {st['w']}x{st['h']}  |  {st['fps']:.0f} FPS" if st and st["ok"]
                else "NOT CONNECTED")
    n_found = len(sysm.cameras()) if sysm else 0
    return [
        mk(17, label="CAMERA PICTURE", kind="toggle", value=s.get("show_camera_feed", True)),
        mk(14, label="CAMERA", kind="select", value=_camera_value(sysm) if sysm else na, enabled=sysm is not None),
        mk(15, label="CAMERA QUALITY", kind="segment", options=[n for _, n in CAMERA_QUALITIES], index=qi,
           enabled=sysm is not None),
        mk(16, label="RESCAN CAMERAS", kind="button", enabled=sysm is not None,
           value="SCANNING..." if (sysm and sysm.scanning) else f"{n_found} FOUND"),
        {"id": "i_cam", "label": "ACTIVE CAMERA", "kind": "info", "desc": _DESC["i_cam"], "value": cam_info},
        {"id": "i_trk", "label": "HAND TRACKING", "kind": "info", "desc": _DESC["i_trk"],
         "value": sysm.tracker_text() if sysm else na},
    ]


_SET_X, _SET_Y, _SET_W, _SET_H = 130, 52, 1020, 604
_TAB_RECTS = widgets.tab_rects(_SET_X + 40, 150, _TABS)


def _settings_rects(n):
    return widgets.stack(_SET_X + 40, 212, _SET_W - 80, [56] * n, gap=8)


def settings_screen(ctx, state, sound_mgr):
    """Draw the settings screen and handle its input.  Returns True to go back."""
    global _tab
    theme = get_theme(state.settings)
    accent = theme["accent"]
    now, dt = state.current_time, state.dt
    s = state.settings

    items = _settings_items(state, _tab)
    rects = _settings_rects(len(items))
    view = VIEW

    # ---- draw ----
    ui.panel(ctx.frame, _SET_X, _SET_Y, _SET_W, _SET_H, 20, alpha=0.80)
    ui.text(ctx.frame, "SETTINGS", _SET_X + 40, 100, 40, ui.TEXT, "left", "bold", spacing=1.5, shadow=True)
    if state.settings_return_state == "MENU":
        ui.chip(ctx.frame, _SET_X + _SET_W - 40 - 250, 86, "IN MATCH  -  SOME OPTIONS LOCKED", ui.WARN, h=28)
    widgets.draw_tabs(ctx.frame, _TAB_RECTS, _TABS, _tab, accent)
    view.draw(ctx.frame, items, rects, theme, now, dt, stagger=0.035, slide=24)
    focused = items[view.focus]
    usable = focused.get("enabled", True)
    note = focused["desc"] + ("   -   Locked while a match is in progress." if not usable else "")
    ui.text(ctx.frame, note, _SET_X + 44, _SET_Y + _SET_H - 38, 17, ui.TEXT_2 if usable else ui.WARN, "left", "medium")
    ui.hints(ctx.frame, [("W S", "Select"), ("A D", "Change"), ("Q E", "Tab"), ("ESC", "Back")])

    # ---- input ----
    new_tab = _tab
    k = ctx.key
    if k in (ord('q'), ord('Q')):
        new_tab = (_tab - 1) % len(_TABS)
    elif k in (ord('e'), ord('E'), 9):
        new_tab = (_tab + 1) % len(_TABS)
    if ctx.mouse_clicked:
        for i, r in enumerate(_TAB_RECTS):
            if r[0] <= ctx.mouse_pos[0] <= r[0] + r[2] and r[1] <= ctx.mouse_pos[1] <= r[1] + r[3]:
                new_tab = i
    if new_tab != _tab:
        _tab = new_tab
        view.focus, view.last_draw = 0, -100.0            # fresh focus + slide-in on the new tab
        sound_mgr.play_menu_tick()
        if _tab == 3 and state.system is not None:
            state.system.rescan_cameras()                  # pick up anything plugged in since
        return False

    for ev in view.input(ctx, items, rects, activate_keys=(13, 32)):
        kind, idx = ev[0], ev[1]
        if kind == "focus":
            sound_mgr.play_menu_tick()
        elif kind == "blocked":
            sound_mgr.play_lose()
        elif kind == "activate":
            change_setting(state, idx, 1, sound_mgr)
            sound_mgr.play_menu_tick()
        elif kind == "adjust":
            change_setting(state, idx, ev[2], sound_mgr)
            sound_mgr.play_menu_tick()
        elif kind == "set":
            if idx == 11:
                change_setting(state, 11, 1 if ev[2] == 1 else -1, sound_mgr)
            elif idx == 15 and state.system is not None:
                cur = next((i for i, (v, _) in enumerate(CAMERA_QUALITIES) if v == state.system.quality()), 0)
                change_setting(state, 15, ev[2] - cur, sound_mgr)
            elif idx == 0:
                change_setting(state, 0, ev[2] - s["score_to_win"], sound_mgr)
            elif idx in (6, 7):
                cur = s["music_volume"] if idx == 6 else s["sfx_volume"]
                change_setting(state, idx, (ev[2] - cur) // 10, sound_mgr)
            elif idx == 1:
                change_setting(state, 1, ev[2] - s["difficulty"], sound_mgr)
            elif idx == 3:
                state.set_player_mode(ev[2])
            sound_mgr.play_menu_tick()
    return k == 27
