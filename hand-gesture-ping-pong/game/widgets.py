"""Menu widgets: rect helpers, the MenuView (keyboard + mouse + focus in one place) and the tab bar.

Built on the primitives in game.ui.  A screen declares its items and reacts to the events that
come back from MenuView.input().
"""

from game import keys
from game.ui import (
    DANGER, PANEL, PANEL_HI, TEXT, TEXT_2, TEXT_3, TRACK, WARN, approach, disc, ease_out,
    fill_rrect, fit_text, mix, panel, rrect, text, text_width, triangle,
)


# ===================================================================
#  MENU WIDGETS
# ===================================================================
#
# An item is a dict:
#   {"id": str, "label": str, "kind": "button|select|slider|toggle|segment",
#    "enabled": bool = True, "desc": str,
#    button : "primary": bool, "danger": bool, "hint": "SPACE", "value": "text shown right"
#    select : "value": "Classic", "swatch": (b,g,r) optional
#    slider : "value": 5, "lo": 1, "hi": 20, "step": 1, "fmt": "{}"
#    toggle : "value": bool
#    segment: "options": [..], "index": int}
#
# MenuView.draw() renders, MenuView.input() returns events:
#   ("activate", id) ("adjust", id, +1/-1) ("set", id, value_or_index) ("blocked", id)


def stack(x, y, w, heights, gap=10):
    """Vertical list of rects (x, y, w, h)."""
    out = []
    for h in heights:
        out.append((x, y, w, h))
        y += h + gap
    return out


def _inside(pos, r):
    return r[0] <= pos[0] <= r[0] + r[2] and r[1] <= pos[1] <= r[1] + r[3]


def _control_area(rect, frac=0.44):
    x, y, w, h = rect
    return x + w * frac, x + w - 24


def slider_geometry(rect):
    x, y, w, h = rect
    x0 = x + w * 0.46
    x1 = x + w - 76
    return x0, x1, y + h / 2


def segment_rects(rect, n):
    x, y, w, h = rect
    x0 = x + w * 0.40
    x1 = x + w - 18
    seg = (x1 - x0) / n
    return [(x0 + i * seg, y + 9, seg - 4, h - 18) for i in range(n)]


def select_zones(rect):
    x0, x1 = _control_area(rect)
    y, h = rect[1], rect[3]
    return (x0 - 6, y, 40, h), (x1 - 34, y, 40, h)


class MenuView:
    def __init__(self, name):
        self.name = name
        self.focus = 0
        self.amt = []
        self.mouse_pos = (-1, -1)
        self.mouse_active = False
        self.last_draw = -100.0
        self.enter_t = 0.0

    # ---- drawing -----------------------------------------------------------------

    def begin(self, now, n):
        if now - self.last_draw > 0.3:                  # (re)entering this screen
            self.enter_t = now
            self.amt = [0.0] * n
        if len(self.amt) != n:
            self.amt = (self.amt + [0.0] * n)[:n]
        self.focus = max(0, min(self.focus, n - 1))
        self.last_draw = now

    def draw(self, frame, items, rects, theme, now, dt, stagger=0.045, slide=34):
        self.begin(now, len(items))
        accent = theme["accent"]
        for i, (item, rect) in enumerate(zip(items, rects)):
            target = 1.0 if i == self.focus else 0.0
            self.amt[i] = approach(self.amt[i], target, dt)
            appear = ease_out((now - self.enter_t - i * stagger) / 0.30)
            if appear <= 0.01:
                continue
            x, y, w, h = rect
            _draw_item(frame, item, (x - (1 - appear) * slide, y, w, h), self.amt[i], appear, accent)

    # ---- input ---------------------------------------------------------------------

    def input(self, ctx, items, rects, activate_keys=(13, 32)):
        events = []
        n = len(items)
        k, raw = ctx.key, ctx.key_raw
        mx, my = ctx.mouse_pos

        if self.mouse_pos[0] >= 0 and (mx - self.mouse_pos[0]) ** 2 + (my - self.mouse_pos[1]) ** 2 > 25:
            self.mouse_active = True
        self.mouse_pos = (mx, my)

        moved = False
        if k in (ord('w'), ord('W')) or raw == keys.UP:
            self.focus = (self.focus - 1) % n
            self.mouse_active, moved = False, True
        elif k in (ord('s'), ord('S')) or raw == keys.DOWN:
            self.focus = (self.focus + 1) % n
            self.mouse_active, moved = False, True
        if self.mouse_active and mx >= 0:
            for i, r in enumerate(rects):
                if _inside((mx, my), r) and i != self.focus:
                    self.focus, moved = i, True
        if moved:
            events.append(("focus", items[self.focus]["id"]))

        item = items[self.focus]
        kind = item["kind"]
        enabled = item.get("enabled", True)

        if k in (ord('a'), ord('A')) or raw == keys.LEFT:
            events.append(self._adjust(item, -1))
        elif k in (ord('d'), ord('D')) or raw == keys.RIGHT:
            events.append(self._adjust(item, +1))
        elif k in activate_keys:
            if kind == "button":
                events.append(("activate", item["id"]) if enabled else ("blocked", item["id"]))
            elif kind == "toggle":
                events.append(self._adjust(item, +1))

        if ctx.mouse_clicked or ctx.mouse_right_clicked:
            for i, r in enumerate(rects):
                if not _inside((mx, my), r):
                    continue
                self.focus = i
                events.append(self._click(items[i], r, (mx, my), ctx.mouse_right_clicked))
                break
        return [e for e in events if e]

    @staticmethod
    def _adjust(item, direction):
        if item["kind"] in ("button", "info"):
            return None
        if not item.get("enabled", True):
            return ("blocked", item["id"])
        return ("adjust", item["id"], direction)

    @staticmethod
    def _click(item, rect, pos, right):
        iid, kind = item["id"], item["kind"]
        if kind == "info":
            return None
        if not item.get("enabled", True):
            return ("blocked", iid)
        if right:
            return ("adjust", iid, -1) if kind != "button" else None
        if kind == "button":
            return ("activate", iid)
        if kind == "toggle":
            return ("adjust", iid, +1)
        if kind == "select":
            left, rightz = select_zones(rect)
            if _inside(pos, left):
                return ("adjust", iid, -1)
            return ("adjust", iid, +1)
        if kind == "segment":
            for i, r in enumerate(segment_rects(rect, len(item["options"]))):
                if _inside(pos, r):
                    return ("set", iid, i)
            return None
        if kind == "slider":
            x0, x1, _ = slider_geometry(rect)
            if x0 - 12 <= pos[0] <= x1 + 12:
                frac = max(0.0, min(1.0, (pos[0] - x0) / (x1 - x0)))
                lo, hi, step = item["lo"], item["hi"], item.get("step", 1)
                val = lo + round((hi - lo) * frac / step) * step
                return ("set", iid, max(lo, min(hi, val)))
        return None


def _draw_item(frame, item, rect, a, appear, accent):
    x, y, w, h = rect
    kind = item["kind"]
    enabled = item.get("enabled", True)
    primary = item.get("primary", False)
    danger = item.get("danger", False)
    op = appear * (1.0 if enabled else 0.5)
    tint = DANGER if danger else accent

    if primary:
        base = mix(accent, (0, 0, 0), 0.30)
        col = mix(base, (255, 255, 255), 0.22 * a)
        fill_rrect(frame, x, y, w, h, 14, col, 0.96 * appear)
        if a > 0.02:
            rrect(frame, x - 1, y - 1, w + 2, h + 2, 15, mix(col, (255, 255, 255), 0.5), 1)
        label_col, label_size = (24, 20, 18), 28
    else:
        fill = mix(PANEL, tint, 0.20 * a)
        panel(frame, x, y, w, h, 12, fill, 0.55 + 0.30 * a, border=tint, border_alpha=0.12 + 0.55 * a)
        if a > 0.04:
            fill_rrect(frame, x + 1, y + 8, 4, h - 16, 2, tint, a * appear)
        label_col = mix(TEXT_2, TEXT, a)
        label_size = 22
    label_size = item.get("label_size", label_size)        # dialogs force equal sizes
    text(frame, item["label"], x + 24, y + h / 2, label_size, label_col, "left", "bold", op, spacing=0.8 if primary else 0.4)

    if kind == "button":
        right_edge = x + w - 22
        if item.get("hint"):
            kw = max(30, text_width(item["hint"], 14, "bold") + 18)
            chip_col = mix(accent, (0, 0, 0), 0.55) if primary else PANEL_HI
            fill_rrect(frame, right_edge - kw, y + h / 2 - 13, kw, 26, 7, chip_col, 0.9 * op)
            text(frame, item["hint"], right_edge - kw / 2, y + h / 2, 14, TEXT if not primary else (240, 240, 240), "center", "bold", op)
            right_edge -= kw + 14
        elif a > 0.3 and not primary:
            triangle(frame, x + w - 28, y + h / 2, 6, "right", mix(TEXT_3, tint, a))
            right_edge -= 26
        if item.get("value"):
            room = right_edge - (x + 24 + text_width(item["label"], label_size, "bold", 0.4) + 24)
            text(frame, fit_text(item["value"], 18, "semi", max(40, room)), right_edge, y + h / 2, 18,
                 TEXT_2 if not primary else label_col, "right", "semi", op)
    elif kind == "info":
        text(frame, fit_text(item["value"], 19, "semi", w * 0.62), x + w - 24, y + h / 2, 19, TEXT_2, "right", "semi", op)
    elif kind == "select":
        left, right = select_zones(rect)
        x0, x1 = _control_area(rect)
        ac = mix(TEXT_3, accent, a)
        triangle(frame, x0 + 12, y + h / 2, 6, "left", ac)
        triangle(frame, x1 - 12, y + h / 2, 6, "right", ac)
        cx = (x0 + x1) / 2
        if item.get("swatch"):
            disc(frame, cx - text_width(item["value"], 21, "bold") / 2 - 18, y + h / 2, 8, item["swatch"])
        text(frame, item["value"], cx, y + h / 2, 21, TEXT, "center", "bold", op)
    elif kind == "toggle":
        on = bool(item["value"])
        pw, ph = 56, 28
        px, py = x + w - 24 - pw, y + h / 2 - ph / 2
        fill_rrect(frame, px, py, pw, ph, ph / 2, accent if on else TRACK, op)
        knob_x = px + (pw - ph / 2 - 3) if on else px + ph / 2 + 3
        disc(frame, knob_x, py + ph / 2, ph / 2 - 4, (250, 250, 250))
        text(frame, "ON" if on else "OFF", px - 14, y + h / 2, 17, TEXT if on else TEXT_3, "right", "bold", op)
    elif kind == "slider":
        x0, x1, ty = slider_geometry(rect)
        lo, hi = item["lo"], item["hi"]
        frac = (item["value"] - lo) / max(1, (hi - lo))
        fill_rrect(frame, x0, ty - 3, x1 - x0, 6, 3, TRACK, op)
        if frac > 0.01:
            fill_rrect(frame, x0, ty - 3, max(6, (x1 - x0) * frac), 6, 3, accent, op)
        disc(frame, x0 + (x1 - x0) * frac, ty, 9 + 2 * a, (250, 250, 250))
        text(frame, item.get("fmt", "{}").format(item["value"]), x + w - 22, y + h / 2, 21, TEXT, "right", "bold", op)
    elif kind == "segment":
        for i, (r, name) in enumerate(zip(segment_rects(rect, len(item["options"])), item["options"])):
            active = i == item["index"]
            fill_rrect(frame, r[0], r[1], r[2], r[3], 9, accent if active else PANEL_HI, (0.95 if active else 0.75) * op)
            text(frame, name, r[0] + r[2] / 2, r[1] + r[3] / 2, 16, (24, 20, 18) if active else TEXT_2, "center", "bold", op)

    if not enabled:
        # tag beside the label, clear of the (dimmed) control on the right
        lx = x + 24 + text_width(item["label"], label_size, "bold", 0.4) + 16
        fill_rrect(frame, lx, y + h / 2 - 11, 74, 22, 6, mix(PANEL, WARN, 0.25), 0.95 * appear)
        text(frame, "LOCKED", lx + 37, y + h / 2, 12, WARN, "center", "bold", appear, spacing=1.2)


# ===================================================================
#  TABS
# ===================================================================

def tab_rects(x, y, labels, w=156, h=40, gap=8):
    return [(x + i * (w + gap), y, w, h) for i in range(len(labels))]


def draw_tabs(frame, rects, labels, active, accent, anim=None):
    for i, (r, name) in enumerate(zip(rects, labels)):
        on = i == active
        if on:
            fill_rrect(frame, *r, 10, mix(PANEL, accent, 0.30), 0.95)
            rrect(frame, *r, 10, accent, 1)
            fill_rrect(frame, r[0] + 14, r[1] + r[3] - 4, r[2] - 28, 3, 1.5, accent)
        else:
            fill_rrect(frame, *r, 10, PANEL, 0.55)
        text(frame, name, r[0] + r[2] / 2, r[1] + r[3] / 2 - (1 if on else 0), 18, TEXT if on else TEXT_3, "center", "bold", spacing=1.2)
