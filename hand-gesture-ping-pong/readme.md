# Hand Gesture Ping Pong

An AR ping-pong game controlled entirely by hand gestures via webcam. Built with Python, OpenCV, MediaPipe, and Pygame.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-green) ![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10%2B-orange)

---

## Features

- **Hand Gesture Control** — Move your hands in front of the webcam to control the paddles. No controllers needed.
- **2-Player & AI Mode** — Play with a friend (both hands on one webcam) or against an adaptive AI opponent.
- **3 Game Modes** — Classic (first to N points), Survival (keep the rally alive), Time Attack (most points in 60s).
- **Power-Ups** — Big Paddle, Speed Boost, Slow Motion, Multi Ball — collected by hitting the ball into them.
- **Arcade UI** — Neon glow effects, animated backgrounds, per-player colored scores with flash animation.
- **8-bit Procedural Audio** — All sound effects and music are synthesized at runtime (no audio files required). Separate music and SFX volume controls.
- **Lobby Music** — Ambient attract-mode music plays on the start screen; switches to game BGM when a match starts.
- **Mouse & Keyboard Support** — Navigate all menus with mouse hover/click or keyboard. Hand gestures are the third input method.
- **Adaptive Hand Tracking** — Works at close and far distances; left/right hands assigned by screen position (immune to MediaPipe label flipping).
- **Combo System** — Consecutive rally hits build a combo multiplier displayed near the ball.
- **Persistent Stats** — High scores, games played, and best combo saved to `stats.json`.
- **Fullscreen Support** — Toggle with `F`; aspect ratio is preserved with letterboxing.
- **Color Themes** — 4 themes: Neon, Retro, Ice, Fire.
- **Optional Obstacles** — Bouncing blocks that deflect the ball for an extra challenge.

---

## Requirements

- Python 3.9 or later
- Webcam

```
opencv-python>=4.8.0
mediapipe>=0.10.0
pygame>=2.6.0
numpy>=1.24.0
screeninfo>=0.8        # optional — used for fullscreen resolution detection
```

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/visionx-gaming/AR-Games.git
cd AR-Games/hand-gesture-ping-pong

# 2. Create and activate a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the game
python main.py
```

---

## Controls

### Hand Gestures (primary)
| Gesture | Action |
|---------|--------|
| Raise both hands | Hold 1 second on start/game-over screen to begin/restart |
| Move hand up/down | Move your paddle |
| Both fists simultaneously | Pause / unpause the game |
| Open both palms (while paused) | Resume |

### Keyboard
| Key | Action |
|-----|--------|
| `Space` / `Enter` | Start game / restart |
| `P` | Pause |
| `R` | Resume from pause |
| `ESC` | Open in-game menu (Resume, Settings, Quit to Menu, Quit) |
| `F` | Toggle fullscreen |
| `M` | Open settings |
| `W` / `S` or `↑` / `↓` | Navigate menus |
| `A` / `D` or `←` / `→` | Change setting value |
| `Q` | Quit |

### Mouse
| Action | Effect |
|--------|--------|
| Hover over menu item | Highlights that item |
| Left-click | Select item / advance setting |
| Right-click (in settings) | Go back on setting value |
| Click start banner | Start game |
| Click restart banner | Restart game |
| Click resume area (paused) | Resume |

---

## Settings

| Setting | Description |
|---------|-------------|
| Score to Win | Points needed to win in Classic mode (1–20) |
| Difficulty | Easy / Medium / Hard — affects ball speed and AI speed |
| Game Mode | Classic / Survival / Time Attack |
| AI Opponent | Toggle AI for the right paddle (single-player mode) |
| Color Theme | Neon / Retro / Ice / Fire |
| Sound | Enable or disable all audio |
| Music Volume | Background music volume (0–100%) |
| SFX Volume | Sound effects volume (0–100%) |
| Hand Skeleton | Show / hide MediaPipe landmark overlay |
| Obstacles | Enable / disable bouncing obstacle blocks |

---

## Project Structure

```
hand-gesture-ping-pong/
├── main.py                 # Game loop, window, input dispatch
└── game/
    ├── config.py           # All constants and color themes
    ├── state.py            # GameState, Ball, PowerUpItem, Obstacle data classes
    ├── engine.py           # Physics, collision, AI, power-up logic
    ├── renderer.py         # All OpenCV drawing functions
    ├── screens.py          # Overlay screens (start, settings, menu, game over, etc.)
    ├── handlers.py         # Per-state handler functions and FrameCtx dataclass
    ├── hand_tracking.py    # Background-threaded MediaPipe hand detection
    ├── sound.py            # Procedural 8-bit SFX and music synthesis
    ├── effects.py          # Particles, shockwaves, screen shake, floating text
    ├── stats.py            # Stats load/save to stats.json
    └── utils.py            # lerp, scale_color, letterbox_frame, screen resolution
```

---

## Tips

- **Distance** — The hand tracker self-calibrates over ~20 seconds. If paddle movement feels off, move your hand across its full range once to calibrate.
- **Lighting** — Good front-facing lighting improves hand detection significantly.
- **Two players on one webcam** — Stand side by side. The leftmost detected hand always controls the left paddle regardless of which hand MediaPipe labels it.
- **Power-ups** — Hit the ball directly into a floating power-up icon to collect it. Big Paddle goes to the side that last touched the ball.
