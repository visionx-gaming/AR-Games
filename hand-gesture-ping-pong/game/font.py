"""Font loader.

  * Press Start 2P  - the retro pixel font, used for the logo and big score numerals.
  * Rajdhani        - a clean, readable UI font for menus, labels and descriptions.

Both are kept in assets/fonts so the game works offline.  A missing file is
downloaded once; if that fails the loader falls back to a Windows system UI font
and finally to PIL's built-in font, so the game always starts.
"""

import os
import urllib.request
from PIL import ImageFont

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")
_FONT_PATH = os.path.join(_FONT_DIR, "PressStart2P-Regular.ttf")
_FONT_URL = (
    "https://github.com/google/fonts/raw/main/ofl/pressstart2p/PressStart2P-Regular.ttf"
)

_cache: dict = {}
_available: bool = False


def _ensure() -> bool:
    global _available
    if _available:
        return True
    if os.path.exists(_FONT_PATH):
        _available = True
        return True
    os.makedirs(_FONT_DIR, exist_ok=True)
    try:
        print("[font] Downloading Press Start 2P…")
        urllib.request.urlretrieve(_FONT_URL, _FONT_PATH)
        print("[font] Font downloaded OK.")
        _available = True
        return True
    except Exception as e:
        print(f"[font] Download failed ({e}). Falling back to default font.")
        return False


_ensure()


def get(size: int) -> ImageFont.ImageFont:
    """Return a cached PIL ImageFont for the given pixel size."""
    if not _available:
        return ImageFont.load_default()
    if size not in _cache:
        _cache[size] = ImageFont.truetype(_FONT_PATH, size)
    return _cache[size]


# ---- UI font (Rajdhani) ------------------------------------------------------------------

_UI_FILES = {"medium": "Rajdhani-Medium.ttf", "semi": "Rajdhani-SemiBold.ttf", "bold": "Rajdhani-Bold.ttf"}
_UI_URL = "https://github.com/google/fonts/raw/main/ofl/rajdhani/{}"
_SYSTEM_UI_FONTS = (
    r"C:\Windows\Fonts\bahnschrift.ttf", r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arialbd.ttf",
)
_ui_cache: dict = {}
_ui_paths: dict = {}


def _ui_path(weight):
    if weight in _ui_paths:
        return _ui_paths[weight]
    path = os.path.join(_FONT_DIR, _UI_FILES[weight])
    if not os.path.exists(path):
        try:
            os.makedirs(_FONT_DIR, exist_ok=True)
            urllib.request.urlretrieve(_UI_URL.format(_UI_FILES[weight]), path)
        except Exception as e:
            print(f"[font] Could not download {_UI_FILES[weight]} ({e}); using a system font.")
            path = next((p for p in _SYSTEM_UI_FONTS if os.path.exists(p)), None)
    _ui_paths[weight] = path
    return path


def get_ui(size: int, weight: str = "semi") -> ImageFont.ImageFont:
    """Cached UI font ('medium' | 'semi' | 'bold') at a pixel size."""
    key = (size, weight)
    if key not in _ui_cache:
        path = _ui_path(weight)
        _ui_cache[key] = ImageFont.truetype(path, size) if path else get(size)
    return _ui_cache[key]
