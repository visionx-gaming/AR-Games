# Hand Pong

An arcade ping-pong game you play with your hands. A webcam tracks your hands (MediaPipe), and the
game draws everything itself (OpenCV + NumPy into a pygame/SDL window). Built for a walk-up office
tournament, but it is a normal game too: three modes, a CPU opponent, two-player, themes, settings.

- Python 3.11, Windows (tested), webcam recommended (the game is playable with the keyboard alone)
- Everything runs on the CPU. No GPU needed. All sounds and music are synthesised at start-up.

## Run it

```
venv\Scripts\python.exe main.py                       # normal game
venv\Scripts\python.exe main.py --event               # tournament qualifier (also in the main menu)
venv\Scripts\python.exe main.py --finals              # tournament finals    (also in the main menu)
run_tests.bat                                         # checks everything, about 30 seconds
```

First time on a new machine:

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

| Flag | Meaning |
|------|---------|
| `--event` | Start on the qualifier leaderboard |
| `--finals` | Start on the finals bracket |
| `--restart-finals` | With `--finals`: throw away the saved bracket and build a new one |
| `--attempts N` | Qualifier attempts per person (default 1) |
| `--time SECONDS` | Game length of Time Attack / the qualifier, 15-300 s (this run only; default is the saved setting, 60) |
| `--difficulty easy\|medium\|hard` | CPU difficulty for tournament runs (default medium; from the menu it uses your Settings) |
| `--no-camera-feed` | Hide the camera picture for this run (tracking still works) |
| `--no-fist-pause` | Kept for compatibility: the two-fists pause gesture is off by default |

## Playing

**Modes** (main menu): Classic (first to N points), Survival (keep the rally alive), Time Attack
(most points in 60 s). **Players**: 2 PLAYERS, CPU RIGHT (you on the left) or CPU LEFT (you on the
right). Against the CPU the game gets harder the longer it runs (CPU LEVEL 1-5 shows under the score).

**Hands:** move a hand up and down to move your paddle. On the main menu, show both hands for a second
to start. With two players, the left hand on screen is player 1.

| Key | Action |
|-----|--------|
| `Space` / `Enter` | Start / select |
| `W` `S` `A` `D` or arrows | Menus, and paddles when playing from the keyboard |
| `P` / `R` | Pause / resume |
| `ESC` | In-game menu (or exit confirmation on the main menu) |
| `M` | Settings |
| `H` | How to play (main menu and tournament screens) |
| `F` | Fullscreen |
| `C` | Switch camera |
| `V` | Camera picture on / off (tracking keeps working) |
| `Tab` | Cycle 2 players / CPU right / CPU left (main menu) |

Colour themes: Neon, Retro, Ice, Fire and **Contrast** (a colour-blind-safe blue / orange / yellow set).

Settings (gameplay, audio, display, camera) are saved in `settings.json`. Display and camera rows
follow whatever monitors and cameras are attached (resolution, monitor, camera, quality, rescan).

## Event runbook (qualifier + finals)

**Before the day**
1. Plug in the camera and the monitor, run `run_tests.bat` once, then start the game and set the
   display / camera in Settings (Display and Camera tabs). Check both hands are tracked.
2. Choose the difficulty in Settings (it applies to the qualifier started from the menu), or launch
   with `--event --difficulty easy|medium|hard`.
3. Optional: `V` turns off the camera picture so players are not distracted.

**Qualifier** (`TOURNAMENT QUALIFIER` in the main menu, or `--event`)
- Every player plays one 60-second Time Attack against the CPU (same settings for everyone, no
  power-ups or obstacles). The organiser presses `Space`, the player types their name, picks the side they want (LEFT or RIGHT: `Tab` / arrows / click, the CPU takes the other) and presses `Enter`.
- Game length: `-` / `+` on the leaderboard change it in 15 s steps (15-300 s, saved), or use `--time N`, or Settings > Gameplay > TIME LIMIT while Time Attack is the selected mode. The CPU ramp scales with it.
- Ranking: best attempt by points scored minus conceded, then fewer conceded, then the longer rally, then more returns (balls you hit back).
  Equal players share a rank. The leaderboard shows the top 10.
- Every game is appended to `event_results.csv` (open it in Excel any time; if Excel has it locked, the
  game keeps the rows and writes them on the next game).
- `F` fullscreen and `C` camera work on the leaderboard. Players cannot reach the menu or quit.
- To leave the tournament screens (organiser only): `ESC`, then `Y`. Scores stay saved.

**Finals** (`TOURNAMENT FINALS` in the main menu, or `--finals`)
- The bracket is built from the qualifier ranking: semi-finals 1 v 4 and 2 v 3, then the 3rd-place
  match and the final. Matches are first to 5 (sudden-death playoffs to 3 break ties for the last seat).
- The next match is shown on screen with a hand check for both players. `Space` / `Enter` starts it.
- **Withdraw a player:** press `W`, pick the player with `1`-`9`, confirm with `Y` (`N` / `ESC` cancels).
  The next ranked player takes the seat, or the opponent advances by walkover.
- The bracket is saved after every match in `finals_state.json`, so you can close and reopen the game.
  Results go to `finals_results.csv`. Start over with `--finals --restart-finals`.

**Files the game writes** (all in the project folder, all ignored by git)

| File | Contents |
|------|----------|
| `settings.json`, `stats.json` | Your settings, high scores |
| `game_history.csv`, `point_log.csv` | Every normal game, and every point of it |
| `event_results.csv` | Qualifier games |
| `finals_results.csv`, `finals_state.json` | Finals matches and the live bracket |
| `crash_log.txt` | Only exists after a crash (empty ones are removed on exit) |

**If something goes wrong**
- No hand tracking: check lighting; `C` switches camera; Settings > Camera > RESCAN.
- Game closed unexpectedly: restart it. Scores and the bracket are already on disk; read `crash_log.txt`.
- A finals player no-shows: withdraw them (`W`).
- Do not delete `event_results.csv` during the event; copy it somewhere safe at breaks.

## Project layout

```
main.py                  window, camera, per-frame loop, hotkeys, command-line flags
game/
  config.py              constants, colour themes
  state.py               GameState and the small data classes
  engine.py              paddles, CPU, ball physics, collisions, scoring
  difficulty.py          the vs-CPU difficulty ramp and CPU level
  powerups.py            power-ups and obstacle blocks
  handlers.py            per-screen frame handlers (menu, play, pause, game over ...)
  event_handlers.py      tournament screens' handlers (leaderboard, name, finals)
  flow.py                FrameCtx and helpers shared by the handlers
  modes.py               enter / leave the qualifier and finals at run time
  event.py, finals.py    qualifier leaderboard, finals bracket (with withdrawals)
  history.py, stats.py   CSV result files, settings and stats files
  ui.py                  design tokens, text, panels, cursor and other drawing helpers
  widgets.py             menu widgets (MenuView, tabs)
  menu_screens.py        main menu, in-game menu, pause, countdown, game over, dialogs
  settings_screen.py     the settings screen and change_setting()
  event_screens.py       leaderboard, finals bracket, tournament dialogs
  hud.py                 in-game HUD and overlays
  renderer.py            background, court, ball, paddles, effects drawing
  gfx.py                 resolution-independent drawing primitives
  display.py, system.py  SDL window / monitors, live display and camera control
  camera.py              threaded camera capture and camera scanning
  hand_tracking.py       MediaPipe hand detection, smoothing and prediction
  sound.py, effects.py   synthesised audio, particles and screen shake
  crashlog.py, keys.py, font.py, utils.py
assets/fonts/            Rajdhani and Press Start 2P
tests/                   verify_game.py (the checks) and run_tests.py (the runner)
```

## Tests

`run_tests.bat` runs about 400 checks in a separate process and writes only to a temporary folder.
It also fingerprints `settings.json`, `stats.json` and the result files before and after, and fails
if a test touched them. `run_tests.bat -v` shows every check, `-k "text"` filters by name. Add new
checks with `check("what should be true", condition)` in `tests/verify_game.py`.
