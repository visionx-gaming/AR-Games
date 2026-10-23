"""Live display + camera control, used by the settings screen and the hotkeys.

The game window and the webcam are created in main.py; this class owns the
operations on them so the UI can offer them without freezing the game:

  Display   fullscreen / windowed, which monitor, render resolution (cap)
  Camera    which device, capture quality, rescanning for newly attached devices

Anything slow (opening a camera takes a couple of seconds) happens on a
background thread; poll() is called every frame to finish it, to notice monitors
being plugged in or removed, and to keep the saved settings in step.
"""

import threading
import time

import pygame

from game import crashlog, gfx
from game import camera as cam_mod

RENDER_HEIGHTS = (2160, 1440, 1080, 720, 540)          # selectable render caps (0 = auto)
CAMERA_QUALITIES = ((0, "AUTO (BEST)"), (720, "720P"), (480, "480P"))


class System:
    def __init__(self, display, camera, settings, save, attach_camera, toast, tracker_text=None):
        self.display = display
        self.camera = camera
        self.settings = settings
        self._save = save
        self._attach = attach_camera          # called with every new CameraStream
        self.toast = toast                    # toast(text) - short on-screen message
        self._tracker_text = tracker_text or (lambda: "")
        self.target_size = None               # (w, h) cameras should mirror + fit to
        self._found = []                      # probed devices other than the active one
        self._scan = None                     # {"thread", "result"} while scanning
        self.scanned_once = False
        self._switch = None                   # {"thread", "index", "result", "done"}
        self._display_count = pygame.display.get_num_displays()
        self._next_check = 0.0
        self._cycle_after_scan = 0            # a C press that arrived before the first scan finished
        self.apply_render_settings()
        # No camera scan at startup: it happens when the CAMERA tab opens, on RESCAN, or the
        # first time C is pressed - never while the game is busy starting up.

    # ===================================================================
    #  DISPLAY
    # ===================================================================

    def displays(self):
        return self.display.displays()

    def current_display(self):
        return self.display.current_display_index()

    def is_fullscreen(self):
        return self.display.fullscreen

    def native_size(self):
        return self.display.native_size()

    def apply_render_settings(self):
        """Push the saved resolution preference into the renderer."""
        h = self.settings.get("render_height", 0)
        gfx.set_render_cap(h)
        self.display.fill_window = h != 0

    def set_fullscreen(self, on):
        self.display.set_fullscreen(bool(on))
        self.settings["fullscreen"] = bool(on)
        self._save(self.settings)

    def toggle_fullscreen(self):
        self.set_fullscreen(not self.display.fullscreen)

    def set_display(self, index):
        if self.display.move_to_display(index):
            self.settings["display_index"] = index
            self._save(self.settings)

    def cycle_display(self, direction):
        n = len(self.displays())
        if n > 1:
            self.set_display((self.current_display() + direction) % n)

    def render_options(self):
        """[0 (auto), then each cap that fits this display's native height]."""
        native_h = self.native_size()[1]
        return [0] + [h for h in RENDER_HEIGHTS if h <= native_h]

    def render_height(self):
        return self.settings.get("render_height", 0)

    def set_render_height(self, h):
        self.settings["render_height"] = h
        self.apply_render_settings()
        self._save(self.settings)

    def cycle_render(self, direction):
        opts = self.render_options()
        cur = self.render_height()
        i = opts.index(cur) if cur in opts else 0
        self.set_render_height(opts[(i + direction) % len(opts)])

    def render_info(self):
        """((render w, h), (native w, h)) right now."""
        return gfx.frame_size(), self.native_size()

    # ===================================================================
    #  CAMERA
    # ===================================================================

    def set_target_size(self, size):
        self.target_size = size
        self.camera.target_size = size

    def cameras(self):
        """Known cameras: [{"index", "w", "h", "active"}], ordered by index."""
        out = {c["index"]: {"index": c["index"], "w": c["w"], "h": c["h"], "active": False} for c in self._found}
        cam = self.camera
        if cam.opened:
            out[cam.index] = {"index": cam.index, "w": cam.size[0], "h": cam.size[1], "active": True}
        return [out[i] for i in sorted(out)]

    @property
    def scanning(self):
        return self._scan is not None and self._scan["thread"].is_alive()

    @property
    def switching(self):
        return self._switch is not None and not self._switch["done"]

    def rescan_cameras(self):
        """Look for attached cameras in the background (skips the one in use)."""
        if self.scanning:
            return
        skip = {self.camera.index} if self.camera.opened else set()
        job = {"result": None}

        def work():
            job["result"] = cam_mod.probe_cameras(skip)

        job["thread"] = threading.Thread(target=work, daemon=True)
        self._scan = job
        job["thread"].start()

    def camera_status(self):
        cam = self.camera
        return {"index": cam.index, "w": cam.size[0], "h": cam.size[1], "fps": cam.fps,
                "ok": cam.ok, "switching": self.switching,
                "target": self._switch["index"] if self.switching else None}

    def tracker_text(self):
        return self._tracker_text()

    def quality(self):
        return self.settings.get("camera_quality", 0)

    def select_camera(self, index):
        """Switch to camera `index` without blocking the game."""
        if self.switching:
            return False
        job = {"index": index, "result": None, "done": False}
        max_h = self.quality()
        old = self.camera

        def work():
            try:
                same = old.opened and old.index == index
                if same:
                    old.stop()                      # same device: release it before reopening
                job["result"] = cam_mod.open_specific(index, max_h)
                if job["result"] is None and same and max_h:
                    job["result"] = cam_mod.open_specific(index, 0)    # don't leave it dead: retry on auto
            finally:
                job["done"] = True

        job["thread"] = threading.Thread(target=work, daemon=True)
        self._switch = job
        job["thread"].start()
        self.toast("SWITCHING CAMERA...")
        return True

    def cycle_camera(self, direction=1):
        """Next known camera (the C hotkey / settings arrows)."""
        cams = self.cameras()
        if len(cams) <= 1:
            if not self.scanned_once and not self.scanning:
                self._cycle_after_scan = direction         # look first, then switch if one turns up
                self.rescan_cameras()
                self.toast("LOOKING FOR CAMERAS...")
            elif self.scanning:
                self._cycle_after_scan = direction
            else:
                self.rescan_cameras()
                self.toast("NO OTHER CAMERA FOUND  -  SCANNING...")
            return
        indices = [c["index"] for c in cams]
        cur = self.camera.index
        pos = indices.index(cur) if cur in indices else -1
        self.select_camera(indices[(pos + direction) % len(indices)])

    def set_quality(self, q):
        if q == self.quality():
            return
        self.settings["camera_quality"] = q
        self._save(self.settings)
        if self.camera.opened:
            self.select_camera(self.camera.index)

    def cycle_quality(self, direction):
        values = [v for v, _ in CAMERA_QUALITIES]
        i = values.index(self.quality()) if self.quality() in values else 0
        self.set_quality(values[max(0, min(len(values) - 1, i + direction))])

    # ===================================================================
    #  PER-FRAME
    # ===================================================================

    def poll(self, now=None):
        """Finish background work and watch for monitors being (un)plugged.
        An error in here is logged, never allowed to stop the game."""
        try:
            self._poll(time.monotonic() if now is None else now)
        except Exception:
            crashlog.log_exception("System.poll")

    def _poll(self, now):

        if self._scan is not None and self._scan["result"] is not None and not self._scan["thread"].is_alive():
            self._found = self._scan["result"]
            self._scan["result"] = None
            self.scanned_once = True
            if self._cycle_after_scan:
                direction, self._cycle_after_scan = self._cycle_after_scan, 0
                if len(self.cameras()) > 1:
                    self.cycle_camera(direction)
                else:
                    self.toast("NO OTHER CAMERA FOUND")

        sw = self._switch
        if sw is not None and sw["done"]:
            self._switch = None
            new = sw["result"]
            if new is not None:
                old = self.camera
                new.target_size = self.target_size
                self.camera = new
                self._attach(new)
                if old is not new and old.opened:
                    old.stop()
                self.settings["camera_index"] = new.index
                self._save(self.settings)
                self.toast(f"CAMERA {new.label}  @ {new.fps:.0f} FPS")
                self.rescan_cameras()
            else:
                self.toast(f"CAMERA {sw['index']} COULD NOT BE OPENED")

        if now >= self._next_check:
            self._next_check = now + 1.0
            n = pygame.display.get_num_displays()
            if n != self._display_count:
                self._display_count = n
                self.toast(f"DISPLAYS CHANGED  -  {n} CONNECTED")
                if self.current_display() >= n or self.settings.get("display_index", 0) >= n:
                    self.display.move_to_display(0)
                    self.settings["display_index"] = 0
                    self._save(self.settings)
                self.apply_render_settings()
