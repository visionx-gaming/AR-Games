"""In-game HUD: player cards with scores, a centre pill for the mode, power-up pills,
and the 'hand lost' warning.  Built on game.ui; replaces the old pixel-text HUD."""

import math

from game import ui, difficulty
from game.config import WINDOW_WIDTH, WINDOW_HEIGHT, POWERUP_TYPES, get_powerup_color
from game.utils import brighten_color

_CARD_W, _CARD_H, _CARD_Y = 292, 66, 18
_FLASH_DUR = 0.5


def _player_card(frame, state, side, name, score, color, show_score):
    x = 24 if side == 0 else WINDOW_WIDTH - 24 - _CARD_W
    ui.panel(frame, x, _CARD_Y, _CARD_W, _CARD_H, 14, alpha=0.62)
    stripe_x = x if side == 0 else x + _CARD_W - 5
    ui.fill_rrect(frame, stripe_x, _CARD_Y + 12, 5, _CARD_H - 24, 2.5, color)

    flash = max(0.0, 1.0 - (state.current_time - state.score_flash_time[side]) / _FLASH_DUR)
    name_x = x + 24 if side == 0 else x + _CARD_W - 24
    anchor = "left" if side == 0 else "right"
    max_name_w = _CARD_W - (110 if show_score else 50)
    ui.text(frame, ui.fit_text(name, 21, "bold", max_name_w), name_x, _CARD_Y + _CARD_H / 2, 21,
            ui.mix(color, (255, 255, 255), 0.25 * flash), anchor, "bold", shadow=True)
    if show_score:
        sx = x + _CARD_W - 24 if side == 0 else x + 24
        sa = "right" if side == 0 else "left"
        col = brighten_color(color, int(flash * 140)) if flash > 0 else ui.TEXT
        ui.text(frame, str(score), sx, _CARD_Y + _CARD_H / 2 + 1, round(32 + 12 * flash), col, sa, "pixel", shadow=True)


def _center_pill(frame, state, theme):
    mode = state.settings["game_mode"]
    cx = WINDOW_WIDTH // 2
    accent = theme["accent"]
    if mode == 1:                                              # Survival: rally counter
        ui.panel(frame, cx - 80, _CARD_Y, 160, _CARD_H, 14, alpha=0.62)
        ui.text(frame, "RALLY", cx, _CARD_Y + 16, 12, ui.TEXT_3, "center", "bold", spacing=2.4)
        ui.text(frame, str(state.survival_rally), cx, _CARD_Y + 43, 26, accent, "center", "pixel", shadow=True)
    elif mode == 2:                                            # Time Attack: clock
        remaining = max(0.0, state.settings["time_limit"] - state.game_time)
        low = remaining < 10
        ui.panel(frame, cx - 75, _CARD_Y, 150, _CARD_H, 14, alpha=0.62,
                 border=ui.DANGER if low else None, border_alpha=0.6 if low else 0.22)
        ui.text(frame, "TIME", cx, _CARD_Y + 16, 12, ui.TEXT_3, "center", "bold", spacing=2.4)
        ui.text(frame, f"{int(remaining) // 60}:{int(remaining) % 60:02d}", cx, _CARD_Y + 43, 34,
                ui.DANGER if low else ui.TEXT, "center", "bold", shadow=True)
    else:                                                      # Classic: target
        label = f"FIRST TO {state.settings['score_to_win']}"
        w = ui.text_width(label, 14, "bold", 1.6) + 30
        ui.panel(frame, cx - w / 2, _CARD_Y + 14, w, 38, 12, alpha=0.55)
        ui.text(frame, label, cx, _CARD_Y + 33, 14, ui.TEXT_2, "center", "bold", spacing=1.6)


def _powerup_pills(frame, state, theme):
    t = state.game_time
    y = _CARD_Y + _CARD_H + 12
    for key, exp in state.active_effects.items():
        rem = exp - t
        if rem <= 0:
            continue
        base = key.replace("_left", "").replace("_right", "")
        info = POWERUP_TYPES.get(base, {})
        color = get_powerup_color(theme, base)
        x, w, h = WINDOW_WIDTH - 24 - 212, 212, 38
        ui.panel(frame, x, y, w, h, 11, alpha=0.62)
        ui.disc(frame, x + 20, y + h / 2 - 2, 6, color)
        ui.text(frame, ui.fit_text(info.get("desc", base).upper(), 14, "bold", w - 96), x + 36, y + h / 2 - 2, 14, ui.TEXT, "left", "bold", spacing=0.6)
        ui.text(frame, f"{rem:.0f}s", x + w - 14, y + h / 2 - 2, 14, ui.TEXT_2, "right", "bold")
        ui.progress_bar(frame, x + 14, y + h - 8, w - 28, 3, rem / info.get("duration", 5.0), color)
        y += h + 8


def _status_lines(state, theme):
    """Small lines under the centre pill: difficulty, match point, rally."""
    lines = []
    lvl = difficulty.cpu_level(state)
    if lvl:                                                    # vs CPU: level 1-5
        lines.append((f"CPU LEVEL {lvl}", ui.DANGER if lvl >= 4 else ui.TEXT_2))
    else:                                                      # two players: the ball speed multiplier
        mult = difficulty.speed_multiplier(state)
        lines.append((f"SPEED x{mult:.1f}", ui.DANGER if mult >= 1.35 else ui.TEXT_2))
    s = state.settings
    if s["game_mode"] == 0 and s["score_to_win"] > 1:
        one_away = [i for i in (0, 1) if state.score[i] == s["score_to_win"] - 1]
        if one_away:
            glow = 0.5 + 0.5 * math.sin(state.current_time * 6)
            who = "MATCH POINT" if len(one_away) == 1 else "SUDDEN DEATH"
            if len(one_away) == 1:
                who += "  -  " + ui.fit_text(state.match_names[one_away[0]], 13, "bold", 150).upper()
            lines.append((who, ui.mix(ui.GOLD, (255, 255, 255), 0.45 * glow)))
    if s["game_mode"] != 1 and state.game_state == "PLAYING" and state.survival_rally >= 4:
        lines.append((f"RALLY {state.survival_rally}", ui.GOLD if state.survival_rally >= 10 else ui.TEXT))
    return lines


def draw_hud(frame, state, theme):
    mode = state.settings["game_mode"]
    n1, n2 = state.match_names
    show_score = mode != 1
    _player_card(frame, state, 0, n1, state.score[0], theme["left_paddle"], show_score)
    _player_card(frame, state, 1, n2, state.score[1], theme["right_paddle"], show_score)
    _center_pill(frame, state, theme)
    for i, (label, col) in enumerate(_status_lines(state, theme)):
        ui.text(frame, label, WINDOW_WIDTH // 2, _CARD_Y + _CARD_H + 16 + i * 22, 13, col, "center", "bold", spacing=1.8)
    _powerup_pills(frame, state, theme)


def draw_hand_lost(frame, state):
    """Blinking warning at a player's side when their hand isn't tracked."""
    if not state.camera_ok or int(state.current_time * 3) % 2:
        return
    y = 662
    cpu = state.cpu_side()
    if cpu != "left" and state.hand_pos["Left"] is None:
        _lost_chip(frame, 24, y, state.match_names[0], "left")
    if cpu != "right" and state.hand_pos["Right"] is None:
        _lost_chip(frame, WINDOW_WIDTH - 24, y, state.match_names[1], "right")


def _lost_chip(frame, x, y, name, side):
    label = f"{ui.fit_text(name, 16, 'bold', 150)}  -  HAND NOT FOUND"
    w = ui.text_width(label, 16, "bold", 0.6) + 40
    x0 = x if side == "left" else x - w
    ui.fill_rrect(frame, x0, y - 17, w, 34, 10, ui.mix(ui.PANEL, ui.DANGER, 0.35), 0.92)
    ui.rrect(frame, x0, y - 17, w, 34, 10, ui.DANGER, 1)
    ui.disc(frame, x0 + 18, y, 5, ui.DANGER)
    ui.text(frame, label, x0 + 32, y, 16, ui.TEXT, "left", "bold", spacing=0.6)

def draw_global_hud(frame, fps_display, camera_label=None, tracker_stats=""):
    """Small, quiet diagnostics line (FPS, camera, tracker) in the bottom-left corner."""
    label = f"FPS {int(fps_display)}"
    if camera_label is not None:
        label += f"    CAM {camera_label}"
    if tracker_stats:
        label += f"    {tracker_stats}"
    ui.text(frame, label, 14, WINDOW_HEIGHT - 12, 12, (140, 140, 134), "left", "medium", 0.75)


def draw_toast(frame, text):
    """Short status message below the HUD, centred."""
    w = ui.text_width(text, 17, "bold", 0.8) + 44
    ui.panel(frame, WINDOW_WIDTH / 2 - w / 2, 108, w, 40, 12, alpha=0.82)
    ui.text(frame, text, WINDOW_WIDTH / 2, 128, 17, ui.TEXT, "center", "bold", spacing=0.8)


def draw_no_camera_banner(frame):
    """Shown when no webcam is available: the game stays playable by keyboard."""
    msg = "NO CAMERA  -  W / S and the UP / DOWN arrows move the paddles"
    w = ui.text_width(msg, 15, "bold", 0.6) + 44
    ui.fill_rrect(frame, WINDOW_WIDTH / 2 - w / 2, 662, w, 36, 11, ui.mix(ui.PANEL, ui.WARN, 0.28), 0.95)
    ui.rrect(frame, WINDOW_WIDTH / 2 - w / 2, 662, w, 36, 11, ui.WARN, 1)
    ui.text(frame, msg, WINDOW_WIDTH / 2, 680, 15, ui.TEXT, "center", "bold", spacing=0.6)
