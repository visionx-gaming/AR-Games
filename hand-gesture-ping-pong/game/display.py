"""Window, input events and frame presentation (pygame / SDL2).

OpenCV's own window (imshow + waitKey) costs ~20 ms to paint a 1080p frame on
Windows, which alone limits the game to ~45 fps there.  Presenting through SDL
takes ~6 ms, and the same window gives us keyboard and mouse events, so the
game no longer needs cv2.imshow/waitKey at all.
"""

import cv2
import numpy as np
import pygame

from game import keys

try:                                    # only used to find which monitor the window is on
    from pygame._sdl2 import video as _sdl_video
except Exception:                       # pragma: no cover - very old pygame
    _sdl_video = None

_NO_KEY = keys.NO_KEY

# Only these keys auto-repeat when held (menu navigation, keyboard paddles).
# Every other key acts once per press, so holding C / F / Space / Esc can't fire
# repeatedly (e.g. cycle the camera back to where it started).
_REPEATABLE = {
    pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d,
    pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
    pygame.K_BACKSPACE,
}

# pygame key -> (plain key, extended key_raw).  Arrows are "extended" keys.
_SPECIAL = {
    pygame.K_UP:        (_NO_KEY, keys.UP),
    pygame.K_DOWN:      (_NO_KEY, keys.DOWN),
    pygame.K_LEFT:      (_NO_KEY, keys.LEFT),
    pygame.K_RIGHT:     (_NO_KEY, keys.RIGHT),
    pygame.K_ESCAPE:    (27, 27),
    pygame.K_RETURN:    (13, 13),
    pygame.K_KP_ENTER:  (13, 13),
    pygame.K_SPACE:     (32, 32),
    pygame.K_TAB:       (9, 9),
    pygame.K_BACKSPACE: (8, 8),
}


class Display:
    def __init__(self, title, windowed_size=None, display_index=0, fullscreen=False):
        self.title = title
        self._wrapper = None            # see _window()
        self._keepalive = []            # every window wrapper ever made: never freed
        pygame.display.set_caption(title)
        n = max(1, pygame.display.get_num_displays())
        display_index = display_index if 0 <= display_index < n else 0
        self.windowed_size = tuple(windowed_size) if windowed_size else self.default_windowed_size(display_index)
        self.fullscreen = bool(fullscreen)
        self.fill_window = False        # scale a smaller (user-capped) frame up to fill the window
        self.quit_requested = False
        self._held = set()              # keys currently down (to recognise repeats)
        self._layout = None             # (sw, sh, ox, oy, nw, nh) of the last present
        self._ox = self._oy = 0         # where the frame sits inside the window
        self._scale = 1.0               # window pixels per frame pixel
        self._set_mode(display_index)
        # Held keys repeat like they did with waitKey (menus, keyboard paddles)
        pygame.key.set_repeat(350, 35)

    # ---- window ---------------------------------------------------------

    def _recreate_window(self):
        """SDL ignores `display=` for a window that already exists (it resizes it but
        leaves it on the same monitor), so moving to another monitor means making a
        fresh window there."""
        pygame.display.quit()
        pygame.display.init()
        pygame.display.set_caption(self.title)
        pygame.key.set_repeat(350, 35)

    def _set_mode(self, display_index, move=False):
        if move:
            self._recreate_window()
        if self.fullscreen:
            pygame.display.set_mode((0, 0), pygame.FULLSCREEN, display=display_index)
        else:
            pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE, display=display_index)
        pygame.mouse.set_visible(False)     # the game draws its own cursor
        self._layout = None
        self._wrapper = None                # the SDL window may be new: wrap it afresh on next use

    def _window(self):
        """pygame's wrapper object for the SDL window, created ONCE per window and kept alive.

        Window.from_display_module() stores a raw pointer to the wrapper inside the SDL
        window.  If the wrapper is garbage-collected (as happens when it is created just
        to read one property), SDL keeps a dangling pointer, and the next window event after
        the window is rebuilt (monitor change, fullscreen toggle) follows it and crashes the
        whole process with an access violation.  Keeping every wrapper alive avoids that."""
        if self._wrapper is None:
            self._wrapper = _sdl_video.Window.from_display_module()
            self._keepalive.append(self._wrapper)
        return self._wrapper

    def _current_display_index(self):
        if _sdl_video is None:
            return 0
        try:
            return self._window().display_index
        except Exception:
            return 0

    current_display_index = _current_display_index

    # ---- monitors ------------------------------------------------------------

    @staticmethod
    def displays():
        """Attached monitors: [{"index", "w", "h", "primary"}] at their native desktop size."""
        return [{"index": i, "w": w, "h": h, "primary": i == 0}
                for i, (w, h) in enumerate(pygame.display.get_desktop_sizes())]

    def native_size(self):
        sizes = pygame.display.get_desktop_sizes()
        idx = self._current_display_index()
        return sizes[idx] if 0 <= idx < len(sizes) else self.size

    @staticmethod
    def default_windowed_size(index):
        """Largest 16:9 window that fits comfortably (88%) on monitor `index`."""
        sizes = pygame.display.get_desktop_sizes()
        sw, sh = sizes[index] if 0 <= index < len(sizes) else (1280, 720)
        w = int(min(0.88 * sw, 0.88 * sh * 16 / 9)) // 16 * 16
        return (max(640, w), max(360, w * 9 // 16))

    def move_to_display(self, index):
        """Move the window (or fullscreen) to monitor `index`. False if there is no such monitor."""
        if not 0 <= index < pygame.display.get_num_displays():
            return False
        if index == self._current_display_index():
            return True
        if not self.fullscreen:
            dw, dh = self.default_windowed_size(index)
            if self.windowed_size == self.default_windowed_size(self._current_display_index()):
                self.windowed_size = (dw, dh)               # untouched default: re-fit to the new monitor
            else:                                            # user-sized: keep, but never bigger than the monitor
                self.windowed_size = (min(self.windowed_size[0], dw), min(self.windowed_size[1], dh))
        self._set_mode(index, move=True)
        return True

    def set_fullscreen(self, on):
        """Go fullscreen (native resolution of the current monitor) or back to a window."""
        if on == self.fullscreen:
            return
        idx = self._current_display_index()
        if on:
            self.windowed_size = self.size
        self.fullscreen = on
        self._set_mode(idx)

    @property
    def size(self):
        """Current drawing-area size of the window, in pixels."""
        return pygame.display.get_surface().get_size()

    def toggle_fullscreen(self):
        """Switch between windowed and native-resolution fullscreen on the
        monitor the window is currently on."""
        self.set_fullscreen(not self.fullscreen)

    # ---- input ------------------------------------------------------------

    @staticmethod
    def _translate(ev):
        special = _SPECIAL.get(ev.key)
        if special:
            return special
        ch = ev.unicode
        if len(ch) == 1 and 0 < ord(ch) < 128:
            return ord(ch), ord(ch)
        return _NO_KEY, -1

    def poll(self):
        """Process pending events. Returns (key, key_raw, mouse_pos,
        left_clicked, right_clicked); mouse_pos is (-1, -1) when the pointer
        is outside the window."""
        key, key_raw = _NO_KEY, -1
        clicked = right = False
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.quit_requested = True
            elif ev.type == pygame.KEYDOWN:
                is_repeat = ev.key in self._held
                self._held.add(ev.key)
                if is_repeat and ev.key not in _REPEATABLE:
                    continue
                k, raw = self._translate(ev)
                if k != _NO_KEY or raw != -1:
                    key, key_raw = k, raw
            elif ev.type == pygame.KEYUP:
                self._held.discard(ev.key)
            elif ev.type == pygame.WINDOWFOCUSLOST:
                self._held.clear()
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1:
                    clicked = True
                elif ev.button == 3:
                    right = True
        pos = pygame.mouse.get_pos() if pygame.mouse.get_focused() else (-1, -1)
        return key, key_raw, pos, clicked, right

    def to_frame(self, pos):
        """Window pixel position -> position inside the rendered frame."""
        if pos[0] < 0 or pos[1] < 0:
            return (-1, -1)
        return (int((pos[0] - self._ox) / self._scale),
                int((pos[1] - self._oy) / self._scale))

    # ---- output -----------------------------------------------------------

    def present(self, frame):
        """Show a BGR uint8 frame, blitted 1:1 and centred (letterboxed); it is
        only scaled down if the window is smaller than the frame."""
        fh, fw = frame.shape[:2]
        screen = pygame.display.get_surface()
        sw, sh = screen.get_size()

        if fw <= sw and fh <= sh:
            # Fits: show 1:1 (centred, with thin black bars if not an exact
            # match).  Never rescale just to fill a few leftover pixels - the
            # game already renders at the largest 16:9 size that fits.
            nw, nh, s = fw, fh, 1.0
            if self.fill_window and min(sw / fw, sh / fh) > 1.05:
                # The user capped the render resolution below the window's: scale up to fill
                s = min(sw / fw, sh / fh)
                nw, nh = int(fw * s), int(fh * s)
                frame = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
        else:
            # Window smaller than the render frame: shrink to fit
            s = min(sw / fw, sh / fh)
            nw, nh = max(1, int(fw * s)), max(1, int(fh * s))
            frame = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
        ox, oy = (sw - nw) // 2, (sh - nh) // 2
        self._scale = s
        layout = (sw, sh, ox, oy, nw, nh)
        if layout != self._layout:          # only repaint the black bars when needed
            screen.fill((0, 0, 0))
            self._layout = layout
        self._ox, self._oy = ox, oy

        masks = screen.get_masks()
        if screen.get_bytesize() == 4 and masks[:3] == (0xFF0000, 0xFF00, 0xFF):
            # Window memory is B,G,R,X per pixel: convert straight into it (one
            # multi-threaded pass) instead of wrapping the frame in a surface and
            # letting SDL convert + blit it - saves several ms per 1080p frame.
            buf = screen.get_buffer()
            try:
                px = np.frombuffer(buf, np.uint8).reshape(sh, screen.get_pitch() // 4, 4)
                cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA, dst=px[oy:oy + nh, ox:ox + nw])
                del px
            finally:
                del buf                     # unlocks the surface before flip()
        else:
            surf = pygame.image.frombuffer(np.ascontiguousarray(frame).data, (nw, nh), "BGR")
            screen.blit(surf, (ox, oy))
        pygame.display.flip()
