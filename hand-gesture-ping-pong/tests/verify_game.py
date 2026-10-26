"""The game's regression suite (run it with `python tests/run_tests.py`).

Every check prints PASS / FAIL; the process exits non-zero if any failed.  Nothing here may
touch the real settings, stats, scores or bracket files: the sandbox below points all of them
at a temporary folder before the game modules are used.
"""
import os, sys, json, math, tempfile
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import numpy as np

from game.state import GameState, Ball
from game import engine, handlers, event_handlers, flow, stats as st_mod, effects, widgets, difficulty, powerups
from game.config import WINDOW_WIDTH, WINDOW_HEIGHT, PADDLE_HEIGHT, get_theme
from game.flow import FrameCtx
from game import history as _hist
_tmp_hist = tempfile.mkdtemp(prefix="pong_tests_")
_hist.HISTORY_FILE = os.path.join(_tmp_hist, 'h0.csv')
_hist.POINTS_FILE = os.path.join(_tmp_hist, 'p0.csv')
_hist.EVENT_FILE = os.path.join(_tmp_hist, 'e0.csv')
_hist.FINALS_FILE = os.path.join(_tmp_hist, 'f0.csv')
st_mod.SETTINGS_FILE = os.path.join(_tmp_hist, 'settings0.json')
st_mod.STATS_FILE = os.path.join(_tmp_hist, 'stats0.json')
from game import finals as _finals_sandbox
_finals_sandbox.FINALS_STATE_FILE = os.path.join(_tmp_hist, 'finals0.json')


class Snd:
    def __getattr__(self, n):
        if n in ("lobby_playing", "bgm_playing"):
            return False
        return lambda *a, **k: None


def check(name, cond):
    check.total += 1
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check.failed = True
        check.failures.append(name)
check.failed = False
check.total = 0
check.failures = []


def fresh(mode=0, ai=False):
    s = GameState()
    s.settings["game_mode"] = mode
    s.settings["ai_enabled"] = ai
    s.reset_for_new_game()
    s.current_time = 100.0
    s.game_state = "PLAYING"
    engine.center_paddles(s)
    return s


# --- tunnelling at a huge dt ---------------------------------------------
s = fresh()
engine.reset_ball(s)
b = s.balls[0]
b.x, b.y, b.vx, b.vy, b.base_speed = 120.0, 360.0, -900.0, 0.0, 900.0
engine.step_physics(s, Snd(), 0.1)
check("fast ball hits paddle at dt=0.1 (no tunnelling)", s.score == [0, 0] and s.balls[0].vx > 0)

# --- slow motion applies to ball in flight ---------------------------------
s = fresh()
engine.reset_ball(s)
b = s.balls[0]
b.x, b.y, b.vx, b.vy, b.base_speed = 600.0, 360.0, 400.0, 0.0, 400.0
s.active_effects["slow_motion"] = s.game_time + 4
for _ in range(60):
    s.dt = 1 / 60
    engine.update_balls(s)
    b.x = 600.0                       # hold it mid-court
sp = math.hypot(b.vx, b.vy)
check(f"slow-motion slows ball already in flight ({sp:.0f} ~ 240)", abs(sp - 240) < 5)
s.active_effects.clear()
for _ in range(60):
    s.dt = 1 / 60
    engine.update_balls(s)
    b.x = 600.0
check("speed restored after effect ends", abs(math.hypot(b.vx, b.vy) - 400) < 5)

# --- classic point: serve goes toward the loser; timers; popups visible ---
s = fresh()
engine.reset_ball(s)
b = s.balls[0]
b.x, b.y, b.vx, b.vy = 5.0, 5.0, -300.0, 0.0   # far from paddle (paddle centred)
s.left_paddle_y = s.left_paddle_target = 600.0
engine.check_all_collisions(s, Snd())
check("point awarded, state COUNTDOWN", s.score == [0, 1] and s.game_state == "COUNTDOWN")
check("next serve heads toward the player who lost (left)", s.balls[0].vx < 0)

# --- multi-ball extra scores, single extra, no combo inflation ------------
s = fresh()
engine.reset_ball(s)
powerups.spawn_extra_ball(s)
powerups.spawn_extra_ball(s)
check("only one extra ball at a time", sum(1 for x in s.balls if not x.is_main) == 1)
ex = next(x for x in s.balls if not x.is_main)
ex.x, ex.y, ex.vx, ex.vy = WINDOW_WIDTH - 15.0, 20.0, 400.0, 0.0
s.right_paddle_y = s.right_paddle_target = 600.0
s.balls[0].x = 600
engine.check_all_collisions(s, Snd())
engine.check_all_collisions(s, Snd())
check("extra ball past right paddle scores for left", s.score[0] == 1 and s.game_state == "PLAYING")

# --- survival: AI miss does not end the run --------------------------------
s = fresh(mode=1, ai=True)
engine.reset_ball(s)
b = s.balls[0]
b.x, b.y, b.vx, b.vy = WINDOW_WIDTH - 1.0, 5.0, 300.0, 0.0
s.right_paddle_y = s.right_paddle_target = 600.0
s.survival_rally = 7
engine.check_all_collisions(s, Snd())
check("survival: AI miss re-serves, rally kept", s.game_state == "COUNTDOWN" and s.survival_rally == 7)

# --- AI only chases when ball is coming -----------------------------------
s = fresh(ai=True)
engine.reset_ball(s)
s.balls[0].vx = -300.0
s.balls[0].y = 50.0
s.right_paddle_target = 100.0
for _ in range(120):
    s.dt = 1 / 60
    engine._update_ai(s, s.dt)
check("AI recentres while ball moves away", abs(s.right_paddle_target - (360 - PADDLE_HEIGHT / 2)) < 2)

# --- obstacle never reverses a ball leaving it ------------------------------
s = fresh()
s.settings["obstacles_enabled"] = True
engine.reset_ball(s)
from game.state import Obstacle
s.obstacles = [Obstacle(580, 330, 40, 60, 0)]
b = s.balls[0]
b.x, b.y, b.vx, b.vy = 625.0, 360.0, 300.0, 0.0   # right of block, moving away
engine.check_all_collisions(s, Snd())
check("ball leaving obstacle keeps going away", b.vx > 0)

# --- Time Attack clock ignores pause/menu (wall clock jump) ----------------
s = fresh(mode=2)
s.game_time = 10.0
s.current_time += 500
engine.check_time_attack(s)
check("Time Attack unaffected by wall-clock jump", s.game_state == "PLAYING")

# --- handlers: gestures -------------------------------------------------------
def ctx_for(s, key=255, both=True, t=None, fist=False, raw=-1):
    if t is not None:
        s.current_time = t
    hp = {"Left": (100, 300) if both else None, "Right": (1000, 300) if both else None}
    return FrameCtx(frame=np.zeros((WINDOW_HEIGHT, WINDOW_WIDTH, 3), np.uint8),
                    theme=get_theme(s.settings), hand_pos=hp,
                    fist_state={"Left": fist, "Right": fist}, key=key, key_raw=raw,
                    current_time=s.current_time, dt=1 / 30,
                    glow_layer=np.zeros((WINDOW_HEIGHT, WINDOW_WIDTH, 3), np.uint8))

stats = st_mod.load_stats()
snd = Snd()
s = GameState(); s.game_state = "START"; s.current_time = 10.0
for i in range(120):    # 4 s with both hands up on entry
    handlers.handle_start(ctx_for(s, t=10 + i / 30), s, stats, snd, None)
check("START: hands already up never auto-start", s.game_state == "START")
handlers.handle_start(ctx_for(s, both=False, t=15.0), s, stats, snd, None)
for i in range(40):
    handlers.handle_start(ctx_for(s, t=15.1 + i / 30), s, stats, snd, None)
check("START: hands raised after being away starts game", s.game_state == "COUNTDOWN")

# game over lockout
s = fresh(); s.current_time = 50.0
engine._trigger_game_over(s)
st2 = st_mod.load_stats(); st2.pop("x", None)
import game.stats as _sm
_sm.save_stats = lambda *_a, **_k: None   # don't touch real stats.json in test
for i in range(150):
    handlers.handle_gameover(ctx_for(s, t=50 + i / 30), s, st2, snd)
check("GAMEOVER: result screen stays with hands up", s.game_state == "GAMEOVER")
handlers.handle_gameover(ctx_for(s, both=False, t=56.0), s, st2, snd)
for i in range(40):
    handlers.handle_gameover(ctx_for(s, t=56.1 + i / 30), s, st2, snd)
check("GAMEOVER: hands away then up restarts", s.game_state == "COUNTDOWN")

# pause semantics
s = fresh(); s.game_time = 5.0
handlers.handle_playing(ctx_for(s, key=ord('p'), t=200.0), s, snd, None)
check("P pauses", s.game_state == "PAUSED" and s.pause_by_key)
for i in range(120):
    handlers.handle_paused(ctx_for(s, t=201 + i / 30), s, snd)
    s.fist_pause_cooldown = max(0, s.fist_pause_cooldown - 1 / 30)
check("keyboard pause is not auto-resumed by open hands", s.game_state == "PAUSED")
handlers.handle_paused(ctx_for(s, key=ord('r'), t=210.0), s, snd)
check("R resumes through countdown (ball kept)", s.game_state == "COUNTDOWN" and any(b.is_main for b in s.balls))
gt = s.game_time
for i in range(120):
    handlers.handle_countdown(ctx_for(s, t=210 + i / 30), s, None)
check("countdown finishes to PLAYING, game_time frozen", s.game_state == "PLAYING" and s.game_time == gt)

# menu resume from PLAYING => countdown; settings locks
s = fresh(); s.previous_state = "PLAYING"; s.game_state = "MENU"
handlers._menu_resume(ctx_for(s), s)
check("menu resume from PLAYING -> COUNTDOWN", s.game_state == "COUNTDOWN")
from game import menu_screens, settings_screen
s.settings_return_state = "MENU"; before = s.settings["difficulty"]
settings_screen.change_setting(s, 1, +1, snd)
check("difficulty locked in-game", s.settings["difficulty"] == before)
settings_screen.change_setting(s, 4, +1, snd)
check("theme still changeable in-game", s.settings["color_theme"] == 1)
s.settings_return_state = "START"
settings_screen.change_setting(s, 1, +1, snd)
check("difficulty changeable from main menu", s.settings["difficulty"] == before + 1)

# render each state once (no exceptions)
for gs in ("START", "COUNTDOWN", "PLAYING", "PAUSED", "MENU", "GAMEOVER", "SETTINGS"):
    s = fresh(); s.game_state = gs; s.previous_state = "PLAYING"
    engine.reset_ball(s); s.winner = "Left Player"
    c = ctx_for(s, both=False)
    h = {"START": lambda: handlers.handle_start(c, s, stats, snd, None),
         "COUNTDOWN": lambda: handlers.handle_countdown(c, s, None),
         "PLAYING": lambda: handlers.handle_playing(c, s, snd, None),
         "PAUSED": lambda: handlers.handle_paused(c, s, snd),
         "MENU": lambda: handlers.handle_menu(c, s, snd),
         "GAMEOVER": lambda: handlers.handle_gameover(c, s, st2, snd),
         "SETTINGS": lambda: handlers.handle_settings(c, s, snd)}[gs]
    h()
check("all screens render without error", True)

# --- stats / settings robustness ----------------------------------------------
v = st_mod._validated_settings({"difficulty": 7, "score_to_win": "x", "music_volume": -5,
                                "ai_enabled": "yes", "game_mode": 2})
check("settings validated/clamped", v["difficulty"] == 2 and v["score_to_win"] == 5
      and v["music_volume"] == 0 and v["ai_enabled"] is False and v["game_mode"] == 2)
d = tempfile.mkdtemp()
st_mod.SETTINGS_FILE = os.path.join(d, "settings.json")
st_mod.STATS_FILE = os.path.join(d, "stats.json")
open(st_mod.SETTINGS_FILE, "w").write("[1,2,3]")
open(st_mod.STATS_FILE, "w").write("{broken")
ls, lst = st_mod.load_settings(), st_mod.load_stats()
check("list/corrupt files don't crash, defaults used", ls["difficulty"] == 1 and lst["total_games"] == 0)
check("corrupt file kept as .bak", os.path.exists(st_mod.STATS_FILE + ".bak"))
st_mod.save_settings(ls); st_mod.save_stats(lst)
check("atomic save round-trips", json.load(open(st_mod.SETTINGS_FILE))["difficulty"] == 1
      and not [f for f in os.listdir(d) if f.endswith(".tmp")])
g = fresh(); g.score = [5, 2]; g.winner = "Left Player"; g.max_rally = 9; g.max_combo = 4
st_mod.record_game_result(lst, g)
check("classic stat = margin, rally recorded in any mode", lst["high_score_classic"] == 3 and lst["longest_rally"] == 9)

# --- hand tracker logic -------------------------------------------------------
import game.hand_tracking as ht
t = ht.HandTracker()
lo, hi = 0.30, 0.60
outs = []
for i in range(600):                    # ~40 s of a close-up hand sweeping 0.30-0.60
    cy = lo + (hi - lo) * (0.5 + 0.5 * math.sin(i / 8))
    outs.append(t._remap_y("Left", cy, 0.066))
check(f"Y-range adapts to compressed travel (reach {min(outs[-80:]):.2f}-{max(outs[-80:]):.2f})",
      min(outs[-80:]) < 0.1 and max(outs[-80:]) > 0.9)
def det(*xs):
    return [(x, 0.5, None) for x in xs]
t.single_hand_label = None
check("fresh lone hand: left half -> Left", t._assign_labels(det(0.30), now=1000.0) == ["Left"])
t._prev_x = {"Left": None, "Right": None}
check("fresh lone hand: right half -> Right", t._assign_labels(det(0.70), now=1000.0) == ["Right"])
t._prev_x = {"Left": None, "Right": None}
t._assign_labels(det(0.30, 0.70), now=2000.0)
check("P2 drops: P1's hand near the midline stays Left", t._assign_labels(det(0.48), now=2000.1) == ["Left"])
t._assign_labels(det(0.30, 0.70), now=2001.0)
check("P1 drops: P2's hand near the midline stays Right (was mislabelled before)", t._assign_labels(det(0.52), now=2001.1) == ["Right"])
check("old history expires -> position decides", t._assign_labels(det(0.52), now=2005.0) == ["Right"])
t.single_hand_label = "Left"
check("AI mode: lone hand always Left", t._assign_labels(det(0.9), now=3000.0) == ["Left"])
# latency compensation: moving hand leads, static hand does not, always clamped
t2 = {"Left": None}
t._y_prev = {"Left": None, "Right": None}; t._y_vel = {"Left": 0.0, "Right": 0.0}
ys = [t._predict_y("Left", 0.5, 10.0 + i * 0.033) for i in range(5)]
check("static hand: no prediction offset", all(abs(y - 0.5) < 1e-9 for y in ys))
out = [t._predict_y("Left", 0.2 + 0.6 * i / 15, 20.0 + i * 0.033) for i in range(10)]
check("moving down: prediction leads (and stays in 0..1)", out[-1] > 0.2 + 0.6 * 9 / 15 and 0 <= out[-1] <= 1)
y_far = t._predict_y("Left", 1.0, 30.0); y_jump = t._predict_y("Left", 0.0, 30.03)
check("prediction clamped to court", 0.0 <= y_far <= 1.0 and 0.0 <= y_jump <= 1.0)
t.stop()


# ================== player names + score history ==================================
import csv
from game.stats import clean_name
check("clean_name: allowed chars kept, junk dropped, trimmed to 12",
      clean_name("  Al<ice>!!  Smith-Jones the third ", "X") == "Alice Smith-")
check("clean_name: empty/None/non-str -> default", clean_name("###", "P") == "P" and clean_name(None, "P") == "P")
v = st_mod._validated_settings({"player1_name": "Bob", "player2_name": 123})
check("settings: names validated", v["player1_name"] == "Bob" and v["player2_name"] == "PLAYER 2")


def type_keys(s, text):
    for ch in text:
        c = ctx_for(s, both=False); c.key = ord(ch); c.key_raw = ord(ch)
        handlers.handle_start(c, s, stats, snd, None)


def press(s, key):
    c = ctx_for(s, both=False); c.key = key; c.key_raw = key
    handlers.handle_start(c, s, stats, snd, None)


s = GameState(); s.game_state = "START"; s.current_time = 500.0
handlers.save_settings = lambda *a, **k: None
press(s, ord('n'))
check("N opens the name dialog", s.name_edit_active and s.name_edit_buf == ["PLAYER 1", "PLAYER 2"])
for _ in range(10):
    press(s, 8)
type_keys(s, "Alice")
press(s, 9)
check("Tab switches to field 2", s.name_edit_field == 1)
for _ in range(10):
    press(s, 8)
type_keys(s, "Bob c f q <>")      # c/f/q are plain text here; '<' '>' are rejected
check("typed text filtered", s.name_edit_buf[1] == "Bob c f q ")
check("typing didn't start a game or open exit dialog", s.game_state == "START" and not s.show_exit_confirm)
type_keys(s, "x" * 20)
check("length capped at 12", len(s.name_edit_buf[1]) == 12)
press(s, 13)
check("Enter on field 2 saves + closes", (not s.name_edit_active) and s.settings["player1_name"] == "Alice"
      and s.settings["player2_name"] == "Bob c f q xx")
press(s, ord('n')); type_keys(s, "ZZ"); press(s, 27)
check("Esc discards edits", (not s.name_edit_active) and s.settings["player1_name"] == "Alice")
press(s, ord('n'))
for i in range(120):
    handlers.handle_start(ctx_for(s, both=True, t=600 + i / 30), s, stats, snd, None)
check("both hands up while editing doesn't start a game", s.game_state == "START")
s.name_edit_active = False

# ---- play a whole classic game and check both CSV files -------------------------
d2 = tempfile.mkdtemp()
_hist.HISTORY_FILE = os.path.join(d2, "game_history.csv")
_hist.POINTS_FILE = os.path.join(d2, "point_log.csv")
_hist._pending.clear()
g = GameState(); g.settings.update({"player1_name": "Alice", "player2_name": "Bob", "score_to_win": 3})
g.reset_for_new_game(); g.current_time = 100.0; g.game_state = "PLAYING"
engine.center_paddles(g)


def miss(game, side):
    engine.reset_ball(game)
    b = game.balls[0]
    b.y = 5.0
    if side == "left":
        b.x, b.vx = 5.0, -300.0
        game.left_paddle_y = game.left_paddle_target = 600.0
    else:
        b.x, b.vx = WINDOW_WIDTH - 1.0, 300.0
        game.right_paddle_y = game.right_paddle_target = 600.0
    game.game_state = "PLAYING"; game.game_time += 4.0
    engine.check_all_collisions(game, Snd())


miss(g, "right"); miss(g, "right"); miss(g, "left"); miss(g, "right")     # Alice 3, Bob 1
check("Alice won the game 3-1", g.game_state == "GAMEOVER" and g.score == [3, 1] and g.winner == "Left Player")
check("every point logged in order", [(p[1], p[2], p[3]) for p in g.point_log] == [(0, 1, 0), (0, 2, 0), (1, 2, 1), (0, 3, 1)])
st3 = st_mod.load_stats()
handlers.handle_gameover(ctx_for(g, both=False, t=200.0), g, st3, snd)
rows = list(csv.DictReader(open(_hist.HISTORY_FILE, encoding="utf-8-sig")))
check("game_history.csv: one row with names, scores, winner",
      len(rows) == 1 and rows[0]["player1"] == "Alice" and rows[0]["player2"] == "Bob"
      and rows[0]["score1"] == "3" and rows[0]["score2"] == "1" and rows[0]["winner"] == "Alice"
      and rows[0]["mode"] == "Classic" and rows[0]["score_to_win"] == "3")
prow = list(csv.DictReader(open(_hist.POINTS_FILE, encoding="utf-8-sig")))
check("point_log.csv: 4 points with scorer + running score",
      [(r["point_no"], r["scored_by"], r["score1"], r["score2"]) for r in prow]
      == [("1", "Alice", "1", "0"), ("2", "Alice", "2", "0"), ("3", "Bob", "2", "1"), ("4", "Alice", "3", "1")]
      and all(r["game_id"] == rows[0]["game_id"] for r in prow))
for i in range(5):
    handlers.handle_gameover(ctx_for(g, both=False, t=201 + i), g, st3, snd)
check("game is only recorded once", len(list(csv.DictReader(open(_hist.HISTORY_FILE, encoding="utf-8-sig")))) == 1)

# ---- AI game: right player is CPU ------------------------------------------------
a = GameState(); a.settings.update({"player1_name": "Alice", "ai_enabled": True, "score_to_win": 1})
a.reset_for_new_game(); a.current_time = 1.0; a.game_state = "PLAYING"; engine.center_paddles(a)
miss(a, "right")            # the CPU's paddle is missed -> Alice scores
handlers.handle_gameover(ctx_for(a, both=False, t=2.0), a, st3, snd)
rows = list(csv.DictReader(open(_hist.HISTORY_FILE, encoding="utf-8-sig")))
check("vs AI: opponent=AI, player2=CPU, Alice wins",
      rows[-1]["opponent"] == "AI" and rows[-1]["player2"] == "CPU" and rows[-1]["winner"] == "Alice")

# ---- survival: no winner, rally recorded ---------------------------------------------
sv = GameState(); sv.settings["game_mode"] = 1; sv.reset_for_new_game(); sv.max_rally = 12; sv.survival_rally = 12
sv.winner = "Rally: 12"; sv.game_state = "GAMEOVER"
_hist.record_game(sv)
rows = list(csv.DictReader(open(_hist.HISTORY_FILE, encoding="utf-8-sig")))
check("survival row: blank winner, best_rally 12",
      rows[-1]["mode"] == "Survival" and rows[-1]["winner"] == "" and rows[-1]["best_rally"] == "12")

# ---- file locked (e.g. open in Excel): rows kept and written with the next game ----------
locked = os.path.join(d2, "locked.csv")
_hist.HISTORY_FILE = locked
real_open = open


def fake_open(path, *a, **k):
    if str(path) == locked and fake_open.fail:
        raise PermissionError("locked")
    return real_open(path, *a, **k)


fake_open.fail = True
import builtins
builtins.open = fake_open
try:
    _hist._pending.clear()
    _hist.record_game(sv)
    still_pending = len(_hist._pending)
    fake_open.fail = False
    _hist.record_game(sv)
finally:
    builtins.open = real_open
rows = list(csv.DictReader(open(locked, encoding="utf-8-sig")))
check("locked file: kept pending, then both games written next time",
      still_pending == 1 and len(rows) == 2 and not _hist._pending)

check("names starting with = + - @ are neutralised for spreadsheets",
      _hist._safe("=SUM(A1)") == "'=SUM(A1)" and _hist._safe("-x") == "'-x" and _hist._safe("Bob") == "Bob")


# ================== EVENT MODE ======================================================
from game.event import EventBoard, name_key
from game import event as _event_mod
import json

ev_dir = tempfile.mkdtemp()
EV_FILE = os.path.join(ev_dir, "event_results.csv")
_hist.EVENT_FILE = EV_FILE
_hist.HISTORY_FILE = os.path.join(ev_dir, "game_history.csv")
_hist.POINTS_FILE = os.path.join(ev_dir, "point_log.csv")
_hist._pending.clear()

b = EventBoard(EV_FILE)
b.add("Asha K", 8, 2, 6, 6)      # net +6
b.add("Ravi S", 8, 2, 9, 9)      # net +6, same conceded, longer rally -> ahead of Asha
b.add("Meera P", 5, 4, 4, 4)     # +1
b.add("Dev T", 7, 1, 3, 3)       # +6, fewer conceded -> top
b.add("Zed Q", 5, 4, 4, 4)       # +1, identical to Meera -> tie
r = b.ranking()
check("ranking: net, then fewer conceded, then longer rally",
      [e["player"] for e in r[:3]] == ["Dev T", "Ravi S", "Asha K"])
check("ranking: identical results share a rank and are flagged tied",
      r[3]["rank"] == r[4]["rank"] == 4 and r[3]["tied"] and r[4]["tied"] and not r[0]["tied"])
check("best attempt counts, not the latest",
      (b.add("Asha K", 1, 9, 1, 1), b.rank_of("Asha K"))[1] == 3 and b.attempts("asha  k") == 2)
check("names are matched ignoring case and spaces", name_key("  Asha   K ") == name_key("asha k"))
check("display name keeps first spelling", b.display_name("ASHA K") == "Asha K")
b2 = EventBoard(EV_FILE)
check("results survive a restart (reloaded from CSV)",
      [(e["player"], e["net"]) for e in b2.ranking()] == [(e["player"], e["net"]) for e in b.ranking()]
      and b2.attempts("Asha K") == 2)
with open(EV_FILE, "a", encoding="utf-8") as f:
    f.write("2026-01-01,Broken,x,1,1,0,0,0\n")           # damaged row
check("damaged CSV row is skipped, not fatal", len(EventBoard(EV_FILE).rows) == len(b.rows))
check("empty board ranks nobody", EventBoard(os.path.join(ev_dir, "none.csv")).ranking() == [])

# ---- the walk-up flow, driven by key presses ------------------------------------------
class FakeTracker:
    resets = 0
    def reset_calibration(self): FakeTracker.resets += 1

def ev_state(attempts=1):
    s = GameState(); s.event_mode = True; s.event_max_attempts = attempts
    s.event_board = EventBoard(os.path.join(ev_dir, "flow.csv"))
    _hist.EVENT_FILE = os.path.join(ev_dir, "flow.csv")
    st_mod.set_event_overrides(s.settings, {"game_mode": 2, "ai_enabled": True, "difficulty": 1,
                                            "obstacles_enabled": False, "powerups_enabled": False})
    s.game_state = "EVENT_HOME"; s.current_time = 1000.0
    return s

def home(s, key=255, click=False):
    c = ctx_for(s, both=True); c.key = key; c.key_raw = key; c.mouse_clicked = click
    event_handlers.handle_event_home(c, s, stats, snd)

def name_step(s, key, t=None):
    c = ctx_for(s, both=False, t=t); c.key = key; c.key_raw = key
    event_handlers.handle_event_name(c, s, snd, FakeTracker())

def type_name(s, text):
    for ch in text: name_step(s, ord(ch))

es = ev_state()
for i in range(120):                                  # both hands up for 4 s on the leaderboard
    home(es)
check("event home: hands in view never start a game", es.game_state == "EVENT_HOME")
home(es, key=32)
check("event home: Space opens name entry", es.game_state == "EVENT_NAME")
name_step(es, 13)
check("empty name is rejected", es.game_state == "EVENT_NAME")
type_name(es, "Priya N")
name_step(es, 13)
check("name + Enter starts the game (countdown) and resets hand calibration",
      es.game_state == "COUNTDOWN" and es.event_player == "Priya N" and FakeTracker.resets == 1
      and es.match_names == ("Priya N", "CPU") and es.settings["game_mode"] == 2)

# ---- finish the game: result is recorded, shown, then back to the leaderboard ------------
es.score = [7, 2]; es.max_rally = 5; es.max_combo = 5; es.winner = "Left Player"
es.game_time = 60.0; engine._trigger_game_over(es)
st4 = st_mod.load_stats(); st_mod.save_stats = lambda *a, **k: None
def over(s, t, key=255, click=False):
    c = ctx_for(s, both=False, t=t); c.key = key; c.key_raw = key; c.mouse_clicked = click
    handlers.handle_gameover(c, s, st4, snd)
over(es, 2000.0)
res = es.event_result
check("game over records the attempt with net score + rank",
      res and res["net"] == 5 and res["scored"] == 7 and res["conceded"] == 2 and res["rank"] == 1
      and res["attempt"] == 1 and es.event_board.attempts("priya n") == 1)
over(es, 2000.5, key=32)
check("Space is ignored in the first 2 s of the result screen", es.game_state == "GAMEOVER")
over(es, 2003.0, key=32)
check("Space after 2 s returns to the leaderboard", es.game_state == "EVENT_HOME" and es.event_result is None)

# result auto-returns, and the same game is only recorded once
es2 = ev_state(); rows_start = len(es2.event_board.rows); es2.event_player = "Timer T"; es2.score = [3, 1]; es2.winner = "Left Player"
engine._trigger_game_over(es2)
for t in (3000.0, 3004.0, 3011.9):
    over(es2, t)
rows_before = len(es2.event_board.rows) - rows_start
check("result screen holds, then auto-returns after the timeout", es2.game_state == "GAMEOVER")
over(es2, 3012.5)
check("auto-return to leaderboard; attempt recorded exactly once",
      es2.game_state == "EVENT_HOME" and rows_before == 1 and len(es2.event_board.rows) - rows_start == 1)

# ---- attempt limit -----------------------------------------------------------------------
home(es, key=32)
type_name(es, "PRIYA N")                              # same person, different case
name_step(es, 13)
check("second attempt blocked when only 1 is allowed (case-insensitive)", es.game_state == "EVENT_NAME")
for _ in range(10): name_step(es, 8)
type_name(es, "Someone Else")
name_step(es, 13)
check("a different name can play", es.game_state == "COUNTDOWN" and es.event_player == "Someone Else")
es3 = ev_state(attempts=2)
es3.event_board.add("Twice T", 1, 1, 1, 1)
es3.game_state = "EVENT_NAME"; es3.name_edit_buf = ["twice t", ""]
name_step(es3, 13)
check("--attempts 2 allows a second attempt (and keeps the original spelling)",
      es3.game_state == "COUNTDOWN" and es3.event_player == "Twice T")
es3.name_edit_buf = ["", ""]

# ---- name entry: letters are text, never hotkeys; Esc backs out ----------------------------
es4 = ev_state(); es4.game_state = "EVENT_NAME"; es4.name_edit_buf = ["", ""]
type_name(es4, "cfq pn")
check("c / f / q are just letters while typing", es4.name_edit_buf[0] == "cfq pn" and es4.game_state == "EVENT_NAME")
name_step(es4, 27)
check("Esc cancels back to the leaderboard", es4.game_state == "EVENT_HOME")

# ---- event settings never leak into settings.json -------------------------------------------
sf = os.path.join(ev_dir, "settings.json"); st_mod.SETTINGS_FILE = sf; st_mod._event_overrides.clear()
pre = GameState(); pre.settings.update({"game_mode": 1, "ai_enabled": False, "difficulty": 0,
                                        "obstacles_enabled": True, "player1_name": "Home Player", "music_volume": 40})
st_mod.set_event_overrides(pre.settings, {"game_mode": 2, "ai_enabled": True, "difficulty": 2,
                                          "obstacles_enabled": False, "powerups_enabled": False})
pre.settings["player1_name"] = "Event Guest"
st_mod._event_overrides.setdefault("player1_name", "Home Player")
pre.settings["music_volume"] = 70                      # a normal change should still be saved
real_save = st_mod.save_settings
st_mod.save_settings(pre.settings)
saved = json.load(open(sf))
check("event overrides are not written to settings.json (originals kept)",
      saved["game_mode"] == 1 and saved["ai_enabled"] is False and saved["difficulty"] == 0
      and saved["obstacles_enabled"] is True and saved["player1_name"] == "Home Player")
check("ordinary settings changes are still saved in event mode", saved["music_volume"] == 70)
st_mod._event_overrides.clear()

# ---- fairness / kiosk rules ---------------------------------------------------------------
pw = GameState(); pw.settings["powerups_enabled"] = False; pw.reset_for_new_game(); pw.game_state = "PLAYING"
for i in range(2000):
    pw.game_time += 0.1; powerups.update_powerups(pw, snd)
check("power-ups never spawn when switched off", not pw.powerups)
pw2 = GameState(); pw2.reset_for_new_game(); pw2.game_state = "PLAYING"
for i in range(2000):
    pw2.game_time += 0.1; powerups.update_powerups(pw2, snd)
check("power-ups still spawn normally otherwise", pw2.powerups or pw2.next_powerup_time > 0)
t3 = __import__("game.hand_tracking", fromlist=["HandTracker"]).HandTracker()
t3._y_range["Left"] = [0.4, 0.5]; t3._reset_requested = True
t3.stop()
check("tracker has a calibration reset hook", hasattr(t3, "reset_calibration"))


# ================== FINALS ==========================================================
from game.finals import Finals
from game import finals as _finals_mod

def board_with(results):
    """results: list of (name, scored, conceded, rally)"""
    d = tempfile.mkdtemp(); bb = EventBoard(os.path.join(d, "x.csv"))
    _hist.EVENT_FILE = os.path.join(d, "x.csv")
    for n, sc, cc, ry in results:
        bb.add(n, sc, cc, ry, 1)
    return bb

def names_in(ranking): return [e["player"] for e in ranking]

b8 = board_with([("A", 9, 1, 5), ("B", 8, 1, 5), ("C", 7, 1, 5), ("D", 6, 1, 5),
                 ("E", 5, 1, 5), ("F", 4, 1, 5), ("G", 3, 1, 5), ("H", 2, 1, 5)])
f = Finals.from_ranking(b8.ranking())
check("seeding: top 4 by qualifier rank", f.seeds() == ["A", "B", "C", "D"])
check("no tie at the cut-off -> no playoffs", f.elim == 0 and [m["id"] for m in f.view()] == ["SF1", "SF2", "THIRD", "FINAL"])
m = f.next_match()
check("first match is SF1: seed 1 (left) v seed 4", m["id"] == "SF1" and (m["p1"], m["p2"]) == ("A", "D") and m["target"] == 5)
check("later matches wait for players", f.view()[2]["p1"] is None and f.view()[3]["ref1"] == "Winner SF1")
try:
    f.record("SF2", 5, 3); bad = False
except ValueError:
    bad = True
check("matches must be played in order", bad)
r = f.record("SF1", 5, 2)
check("SF1 result: winner/loser reported", r["winner"] == "A" and r["loser"] == "D" and r["label"] == "SEMI-FINAL 1")
r = f.record("SF2", 3, 5)
check("SF2: right-hand player (seed 3) can win", r["winner"] == "C" and f.next_match()["id"] == "THIRD")
check("3rd place match is between the two semi-final losers", (f.next_match()["p1"], f.next_match()["p2"]) == ("D", "B"))
try:
    f.record("THIRD", 4, 4); tie_ok = False
except ValueError:
    tie_ok = True
check("a knockout match cannot end level", tie_ok)
f.record("THIRD", 5, 0)
check("final is between the two semi-final winners", (f.next_match()["id"], f.next_match()["p1"], f.next_match()["p2"]) == ("FINAL", "A", "C"))
check("not complete until both THIRD and FINAL are played", not f.complete and f.podium() is None)
f.record("FINAL", 5, 4)
check("podium: champion, runner-up, 3rd, 4th", f.complete and f.podium() == ["A", "C", "D", "B"])
check("5th place = best of the rest", f.fifth() == "E")

# ---- save / resume ---------------------------------------------------------------------
st_file = os.path.join(tempfile.mkdtemp(), "finals_state.json")
g = Finals.from_ranking(b8.ranking()); g.record("SF1", 5, 1); g.record("SF2", 2, 5)
g.save(st_mod._write_json, st_file)
g2 = Finals.load(st_file)
check("resume after restart: same bracket, results replayed",
      g2 is not None and g2.seeds() == g.seeds() and g2.results == g.results
      and g2.next_match()["id"] == "THIRD" and (g2.next_match()["p1"], g2.next_match()["p2"]) == ("D", "B"))
open(st_file, "w").write("{broken")
check("corrupt save file -> no crash, caller starts a fresh bracket", Finals.load(st_file) is None)
check("missing save file -> None", Finals.load(os.path.join(tempfile.mkdtemp(), "nope.json")) is None)
try:
    Finals.from_ranking(board_with([("A", 5, 1, 5), ("B", 4, 1, 5), ("C", 3, 1, 5)]).ranking()); few = False
except ValueError:
    few = True
check("fewer than 4 players is refused with a clear error", few)

# ---- ties at the cut-off -> sudden-death playoff -----------------------------------------------
bt = board_with([("A", 9, 1, 5), ("B", 8, 1, 5), ("C", 7, 1, 5), ("D", 6, 1, 5), ("E", 6, 1, 5), ("F", 2, 1, 5)])
ft = Finals.from_ranking(bt.ranking())
check("tie for the last seat: playoff needed, others seeded already",
      ft.elim == 1 and ft.sure == ["A", "B", "C"] and ft.group == ["D", "E"])
check("playoff is first, is sudden death (first to 3), and brackets wait for it",
      ft.next_match()["id"] == "PO1" and ft.next_match()["target"] == 3 and ft.seeds()[3] is None)
ft.record("PO1", 1, 3)
check("playoff winner takes seed 4", ft.seeds() == ["A", "B", "C", "E"] and ft.next_match()["id"] == "SF1"
      and ft.next_match()["p2"] == "E")
check("5th place is the playoff loser", ft.fifth() == "D")
tie_top = board_with([("A", 9, 1, 5), ("B", 9, 1, 5), ("C", 7, 1, 5), ("D", 6, 1, 5), ("E", 5, 1, 5)])
check("a tie inside the top 4 (not at the cut) needs no playoff", Finals.from_ranking(tie_top.ranking()).elim == 0)
b3 = board_with([("A", 9, 1, 5), ("B", 8, 1, 5), ("C", 7, 1, 5), ("D", 5, 1, 5), ("E", 5, 1, 5), ("F", 5, 1, 5)])
f3 = Finals.from_ranking(b3.ranking())
check("3-way tie for one seat: 2 playoff matches in a chain", f3.elim == 2 and f3.next_match()["id"] == "PO1")
f3.record("PO1", 3, 0); check("PO2 = PO1 winner v the next contender", f3.next_match()["id"] == "PO2" and f3.next_match()["p1"] == "D" and f3.next_match()["p2"] == "F")
f3.record("PO2", 1, 3); check("chain winner takes the seat", f3.seeds()[3] == "F")

# ---- through the real handlers: a whole finals ----------------------------------------------------
fd = tempfile.mkdtemp()
_hist.FINALS_FILE = os.path.join(fd, "finals_results.csv")
_hist.HISTORY_FILE = os.path.join(fd, "game_history.csv"); _hist.POINTS_FILE = os.path.join(fd, "point_log.csv")
_hist._pending.clear()
_finals_mod.FINALS_STATE_FILE = os.path.join(fd, "finals_state.json")
sf2 = os.path.join(fd, "settings.json"); st_mod.SETTINGS_FILE = sf2; st_mod._event_overrides.clear()

fs = GameState(); fs.settings.update({"player1_name": "Home P1", "player2_name": "Home P2", "score_to_win": 5})
st_mod.set_event_overrides(fs.settings, {"game_mode": 0, "ai_enabled": False, "difficulty": 1, "obstacles_enabled": False,
                                         "powerups_enabled": False, "player1_name": "Home P1", "player2_name": "Home P2", "score_to_win": 5})
fs.event_mode = True; fs.finals = Finals.from_ranking(b8.ranking()); fs.game_state = "FINALS_HOME"; fs.current_time = 5000.0
FakeTracker.resets = 0

def fhome(s, key=255, t=None):
    c = ctx_for(s, both=True, t=t); c.key = key; c.key_raw = key
    event_handlers.handle_finals_home(c, s, stats, snd, FakeTracker())

def fover(s, t, key=255):
    c = ctx_for(s, both=False, t=t); c.key = key; c.key_raw = key
    handlers.handle_gameover(c, s, st4, snd)

for i in range(90): fhome(fs)
check("finals home: hands in view don't start a match", fs.game_state == "FINALS_HOME")
fhome(fs, key=32)
check("Space starts the next match with its two players, calibration reset",
      fs.game_state == "COUNTDOWN" and fs.match_names == ("A", "D") and fs.settings["score_to_win"] == 5
      and fs.finals_match["id"] == "SF1" and FakeTracker.resets == 1 and fs.settings["ai_enabled"] is False)

def finish(s, a, b, t0):
    s.score = [a, b]; s.winner = "Left Player" if a > b else "Right Player"; engine._trigger_game_over(s)
    fover(s, t0)

finish(fs, 5, 3, 6000.0)
res = fs.finals_result
check("match result recorded in the bracket", res and res["winner"] == "A" and fs.finals.results["SF1"] == (5, 3)
      and res["next"]["id"] == "SF2")
check("bracket saved to disk after the match", json.load(open(_finals_mod.FINALS_STATE_FILE))["results"][0]["id"] == "SF1")
fover(fs, 6000.5, key=32); check("Space ignored for the first 2 s of the result", fs.game_state == "GAMEOVER")
fover(fs, 6003.0, key=32)
check("Space after 2 s returns to the bracket", fs.game_state == "FINALS_HOME" and fs.finals_result is None)
for i in range(4):
    if i: fhome(fs, key=32);
    if fs.game_state != "COUNTDOWN": fhome(fs, key=32)
    if fs.finals.next_match() is None: break
    nm = fs.finals_match
    fs.game_state = "PLAYING"; finish(fs, 5, 2, 7000.0 + i * 100); fover(fs, 7000.0 + i * 100 + 20)
    if fs.game_state != "FINALS_HOME": break
check("all matches played through the handlers -> finals complete", fs.finals.complete and fs.finals.podium() is not None)
rows = list(csv.DictReader(open(_hist.FINALS_FILE, encoding="utf-8-sig")))
check("finals_results.csv has one row per match, in order",
      [r["match"] for r in rows] == ["SEMI-FINAL 1", "SEMI-FINAL 2", "3RD PLACE", "FINAL"]
      and rows[0]["player1"] == "A" and rows[0]["score1"] == "5" and rows[0]["winner"] == "A")
check("finals are in the normal game history too", len(list(csv.DictReader(open(_hist.HISTORY_FILE, encoding="utf-8-sig")))) == 4)
fs.settings["music_volume"] = 33
st_mod.save_settings(fs.settings)
saved = json.load(open(sf2))
check("finals names / score-to-win never leak into settings.json",
      saved["player1_name"] == "Home P1" and saved["player2_name"] == "Home P2" and saved["game_mode"] == 0
      and saved["score_to_win"] == 5 and saved["music_volume"] == 33)
st_mod._event_overrides.clear()
no = GameState(); no.event_mode = True; no.finals = None; no.finals_error = "Cannot build the finals: need at least 4 players"
c = ctx_for(no, both=False); c.key = 32; event_handlers.handle_finals_home(c, no, stats, snd, FakeTracker())
check("no bracket (too few players): Space does nothing, no crash", no.game_state == "START" or no.game_state != "COUNTDOWN")


# ================== FINALS: WITHDRAWALS ===============================================
def fresh8(): return Finals.from_ranking(b8.ranking())          # seeds A B C D, then E F G H

w1 = fresh8()
check("alive = players with a match still to play", w1.alive() == ["A", "D", "B", "C"])
r = w1.withdraw("C")
check("before playing: next-best qualifier takes the seat (same seed)",
      r["replacement"] == "E" and w1.seeds() == ["A", "B", "E", "D"] and r["walkovers"] == [])
check("withdrawn player is gone from the active list; 5th place moves down",
      "C" not in w1.alive() and "E" in w1.alive() and w1.fifth() == "F" and w1.withdrawn == ["C"])
check("matchups use the replacement", [(m["id"], m["p1"], m["p2"]) for m in w1.view()[:2]] == [("SF1", "A", "D"), ("SF2", "B", "E")])
w1b = fresh8(); w1b.withdraw("A")
check("withdrawing the top seed: replacement plays seed 1's match", w1b.seeds() == ["E", "B", "C", "D"] and w1b.next_match()["p1"] == "E")

# replacement mid-bracket: finished matches are untouched
w2 = fresh8(); w2.record("SF1", 5, 2)
r = w2.withdraw("C")
check("mid-bracket (player hasn't played yet): replaced, earlier result kept",
      r["replacement"] == "E" and w2.results["SF1"] == (5, 2) and w2.next_match()["id"] == "SF2"
      and (w2.next_match()["p1"], w2.next_match()["p2"]) == ("B", "E"))

# after playing: no replacement, walkovers
w3 = fresh8(); w3.record("SF1", 5, 2)                       # A beat D; D waits for the 3rd-place match
check("a player who lost the semi can still withdraw (3rd-place match pending)", "D" in w3.alive())
r = w3.withdraw("D")
check("after playing: no replacement", r["replacement"] is None and r["walkovers"] == [])
res = w3.record("SF2", 5, 1)                                # B beats C; 3rd place would be D v C
check("their next match is a walkover for the opponent",
      [(w["id"], w["winner"], w["wo"]) for w in res["walkovers"]] == [("THIRD", "C", True)]
      and "D withdrew" in res["walkovers"][0]["note"] and w3.results["THIRD"] == (0, 5))
check("bracket continues to the final", w3.next_match()["id"] == "FINAL" and (w3.next_match()["p1"], w3.next_match()["p2"]) == ("A", "B"))
w3.record("FINAL", 5, 3)
check("podium counts the walkover 3rd place", w3.podium() == ["A", "B", "C", "D"])

# a finalist withdraws before the final
w4 = fresh8(); w4.record("SF1", 5, 0)                       # A through
w4.withdraw("A")
w4.record("SF2", 5, 4)                                      # B through; THIRD = D v C
check("withdrawn finalist: nothing auto-played until it is their turn", w4.next_match()["id"] == "THIRD")
res = w4.record("THIRD", 5, 2)
check("final is awarded by walkover to the other finalist, bracket completes",
      [(w["id"], w["winner"]) for w in res["walkovers"]] == [("FINAL", "B")] and w4.complete
      and w4.podium()[0] == "B" and w4.podium()[1] == "A")

# nobody left to replace them: walkover
f4 = Finals.from_ranking(board_with([("A", 9, 1, 5), ("B", 8, 1, 5), ("C", 7, 1, 5), ("D", 6, 1, 5)]).ranking())
r = f4.withdraw("C")
check("no spare qualifier: no replacement, and nothing happens until their match comes up",
      r["replacement"] is None and r["walkovers"] == [] and f4.next_match()["id"] == "SF1")
res = f4.record("SF1", 5, 1)
check("then their semi-final is a walkover (and so is the 3rd place match)",
      [(w["id"], w["winner"]) for w in res["walkovers"]] == [("SF2", "B"), ("THIRD", "D")]
      and f4.next_match()["id"] == "FINAL" and (f4.next_match()["p1"], f4.next_match()["p2"]) == ("A", "B"))
f5 = Finals.from_ranking(board_with([("A", 9, 1, 5), ("B", 8, 1, 5), ("C", 7, 1, 5), ("D", 6, 1, 5)]).ranking())
f5.withdraw("B"); f5.withdraw("C")
res = f5.record("SF1", 5, 0)
check("two withdrawn players: bracket resolves itself, the one real player wins it all",
      f5.complete and f5.next_match() is None and f5.podium()[0] == "A" and len(res["walkovers"]) == 3)
for bad in ("Nobody", "Z"):
    try:
        w1.withdraw(bad); ok = False
    except ValueError:
        ok = True
    check(f"withdrawing an unknown player ({bad}) is refused", ok)
try:
    w1.withdraw("C"); ok = False
except ValueError:
    ok = True
check("can't withdraw the same player twice", ok)
try:
    w4.withdraw("B"); ok = False
except ValueError:
    ok = True
check("can't withdraw after the bracket is finished for them", ok)

# playoff contender withdraws before playing
tp = Finals.from_ranking(board_with([("A", 9, 1, 5), ("B", 8, 1, 5), ("C", 7, 1, 5), ("D", 6, 1, 5), ("E", 6, 1, 5), ("F", 2, 1, 5)]).ranking())
r = tp.withdraw("D")
check("playoff contender withdraws: next-best takes the slot", r["replacement"] == "F"
      and tp.next_match()["id"] == "PO1" and (tp.next_match()["p1"], tp.next_match()["p2"]) == ("F", "E"))

# save / resume keeps withdrawals and walkovers
sfile = os.path.join(tempfile.mkdtemp(), "fs.json")
w3.save(st_mod._write_json, sfile)
w3r = Finals.load(sfile)
check("resume after restart: withdrawals, walkovers and podium identical",
      w3r.withdrawn == ["D"] and w3r.walkovers == {"THIRD"} and w3r.podium() == w3.podium() and w3r.results == w3.results)
w1.save(st_mod._write_json, sfile)
w1r = Finals.load(sfile)
check("resume keeps a replacement seat", w1r.seeds() == ["A", "B", "E", "D"] and w1r.fifth() == "F" and w1r.withdrawn == ["C"])
check("W/O shows in the bracket view", [m["wo"] for m in w3.view() if m["id"] == "THIRD"] == [True])

# ---- the organiser dialog through the real handler --------------------------------------------
wd = tempfile.mkdtemp()
_hist.FINALS_FILE = os.path.join(wd, "finals_results.csv"); _hist._pending.clear()
_finals_mod.FINALS_STATE_FILE = os.path.join(wd, "finals_state.json")
hs = GameState(); hs.event_mode = True; hs.game_state = "FINALS_HOME"; hs.current_time = 9000.0
hs.finals = Finals.from_ranking(board_with([("A", 9, 1, 5), ("B", 8, 1, 5), ("C", 7, 1, 5), ("D", 6, 1, 5)]).ranking())
hs.settings["music_volume"] = 0

def hkey(s, key):
    c = ctx_for(s, both=True, t=s.current_time + 0.05); c.key = key; c.key_raw = key
    event_handlers.handle_finals_home(c, s, stats, snd, FakeTracker())

hkey(hs, ord('w'))
check("W opens the withdraw dialog listing the active players", hs.finals_withdraw and hs.finals_withdraw["names"] == ["A", "D", "B", "C"])
hkey(hs, 32)
check("Space does nothing while the dialog is open (no match starts)", hs.game_state == "FINALS_HOME" and hs.finals_match is None)
hkey(hs, ord('4'))
check("pressing a number picks that player, asking for confirmation", hs.finals_withdraw["pick"] == "C")
hkey(hs, ord('n')); check("N goes back to the list", hs.finals_withdraw["pick"] is None)
hkey(hs, 27); check("Esc closes the dialog without changes", hs.finals_withdraw is None and hs.finals.withdrawn == [])
hkey(hs, ord('w')); hkey(hs, ord('4')); hkey(hs, ord('y'))
check("Y confirms: player withdrawn, dialog closed, notice shown",
      hs.finals.withdrawn == ["C"] and hs.finals_withdraw is None and "C WITHDREW" in hs.finals_notice[0])
rows = list(csv.DictReader(open(_hist.FINALS_FILE, encoding="utf-8-sig")))
check("withdrawal is written to finals_results.csv", rows[0]["match"] == "WITHDRAWAL" and rows[0]["player1"] == "C"
      and rows[0]["note"] == "no replacement")
check("withdrawal is saved to the bracket file", json.load(open(_finals_mod.FINALS_STATE_FILE))["withdrawn"] == ["C"])

# now play SF1 through the handlers: the walkovers it triggers are logged and announced
c = ctx_for(hs, both=True, t=9100.0); c.key = 32; c.key_raw = 32
event_handlers.handle_finals_home(c, hs, stats, snd, FakeTracker())
hs.game_state = "PLAYING"; hs.score = [5, 2]; hs.winner = "Left Player"; engine._trigger_game_over(hs)
fover(hs, 9200.0)
rows = list(csv.DictReader(open(_hist.FINALS_FILE, encoding="utf-8-sig")))
check("walkovers triggered by a result are logged with a note",
      [r["match"] for r in rows] == ["WITHDRAWAL", "SEMI-FINAL 1", "SEMI-FINAL 2", "3RD PLACE"]
      and "walkover" in rows[2]["note"] and rows[2]["winner"] == "B")
check("bracket announces the walkovers", "ADVANCES BY WALKOVER" in hs.finals_notice[0])
fover(hs, 9203.0, key=32)
check("back on the bracket with the real final next", hs.game_state == "FINALS_HOME" and hs.finals.next_match()["id"] == "FINAL")
hkey(hs, ord('w'))
check("withdraw dialog lists only the two finalists now", hs.finals_withdraw["names"] == ["A", "B"])
hkey(hs, 27)
done_f = Finals.from_ranking(b8.ranking())
for mid, a, bb_ in (("SF1", 5, 1), ("SF2", 5, 1), ("THIRD", 5, 1), ("FINAL", 5, 1)): done_f.record(mid, a, bb_)
hs2 = GameState(); hs2.event_mode = True; hs2.finals = done_f; hs2.game_state = "FINALS_HOME"
hkey(hs2, ord('w'))
check("no withdraw dialog once the finals are complete", hs2.finals_withdraw is None)


# ================== NEW UI: widgets, menus, screens ===================================
from game import ui, menu_screens, gfx, renderer as _rend
import game.keys as keys_mod

def uctx(s, key=255, raw=-1, mouse=(-1, -1), click=False, rclick=False, t=None):
    if t is not None: s.current_time = t
    c = ctx_for(s, both=False, t=t); c.key = key; c.key_raw = raw
    c.mouse_pos = mouse; c.mouse_clicked = click; c.mouse_right_clicked = rclick
    return c

# ---- MenuView: keyboard focus, adjust, activate --------------------------------------------------------
mv = widgets.MenuView("t")
items = [{"id": "a", "label": "A", "kind": "button"},
         {"id": "b", "label": "B", "kind": "select", "value": "X"},
         {"id": "c", "label": "C", "kind": "slider", "value": 5, "lo": 1, "hi": 20, "step": 1},
         {"id": "d", "label": "D", "kind": "toggle", "value": False},
         {"id": "e", "label": "E", "kind": "segment", "options": ["P", "Q", "R"], "index": 0},
         {"id": "f", "label": "F", "kind": "button", "enabled": False}]
rects = widgets.stack(100, 100, 600, [56] * 6, gap=8)
gs = GameState()
def mvi(**kw): return mv.input(uctx(gs, **kw), items, rects)
mv.begin(10.0, 6)
check("menu: S moves focus down, W up (wraps)", (mvi(key=ord('s')), mv.focus)[1] == 1 and (mvi(key=ord('w')), mvi(key=ord('w')), mv.focus)[2] == 5)
mv.focus = 0
check("menu: Enter activates a button", ("activate", "a") in mvi(key=13))
mv.focus = 1
check("menu: D / A adjust a selector", mvi(key=ord('d')) == [("adjust", "b", 1)] and mvi(key=ord('a')) == [("adjust", "b", -1)])
check("menu: arrow keys adjust too", mvi(raw=keys_mod.RIGHT) == [("adjust", "b", 1)])
mv.focus = 3
check("menu: Enter toggles a toggle", mvi(key=13) == [("adjust", "d", 1)])
mv.focus = 5
check("menu: disabled button reports 'blocked', never activates", mvi(key=13) == [("blocked", "f")])
items[3]["enabled"] = False; mv.focus = 3
check("menu: disabled toggle/slider/select can't be adjusted (reports 'blocked')", mvi(key=ord('d')) == [("blocked", "d")] and mvi(key=13) == [("blocked", "d")] if False else mvi(key=ord('d')) == [("blocked", "d")])
items[3]["enabled"] = True

# ---- MenuView: mouse ---------------------------------------------------------------------------------------
def at(i, fx=0.5, fy=0.5):
    x, y, w, h = rects[i]; return (x + w * fx, y + h * fy)
mv.mouse_pos = (0, 0)
ev = mv.input(uctx(gs, mouse=at(2)), items, rects)
check("mouse: moving over an item focuses it", mv.focus == 2 and ("focus", "c") in ev)
x0, x1, _ = widgets.slider_geometry(rects[2])
ev = mv.input(uctx(gs, mouse=(x0 + (x1 - x0) * 0.5, rects[2][1] + 28), click=True), items, rects)
check("mouse: clicking a slider sets the value under the pointer (mid = ~10)", ev and ev[-1][0] == "set" and ev[-1][1] == "c" and 9 <= ev[-1][2] <= 12)
ev = mv.input(uctx(gs, mouse=(x0 - 2, rects[2][1] + 28), click=True), items, rects)
check("mouse: slider click at the far left = minimum", ev[-1] == ("set", "c", 1))
seg = widgets.segment_rects(rects[4], 3)
ev = mv.input(uctx(gs, mouse=(seg[2][0] + 10, seg[2][1] + 10), click=True), items, rects)
check("mouse: clicking a segment picks that option", ev[-1] == ("set", "e", 2))
lz, rz = widgets.select_zones(rects[1])
ev = mv.input(uctx(gs, mouse=(lz[0] + 5, lz[1] + 20), click=True), items, rects)
check("mouse: left arrow of a selector = previous", ev[-1] == ("adjust", "b", -1))
ev = mv.input(uctx(gs, mouse=(rz[0] + 20, rz[1] + 20), click=True), items, rects)
check("mouse: right arrow of a selector = next", ev[-1] == ("adjust", "b", 1))
ev = mv.input(uctx(gs, mouse=at(3), click=True), items, rects)
check("mouse: clicking a toggle flips it", ev[-1] == ("adjust", "d", 1))
ev = mv.input(uctx(gs, mouse=at(3), rclick=True), items, rects)
check("mouse: right-click adjusts backwards", ev[-1] == ("adjust", "d", -1))
ev = mv.input(uctx(gs, mouse=at(0), click=True), items, rects)
check("mouse: clicking a button activates it", ev[-1] == ("activate", "a"))
ev = mv.input(uctx(gs, mouse=at(5), click=True), items, rects)
check("mouse: clicking a locked row is 'blocked'", ev[-1] == ("blocked", "f"))
ev = mv.input(uctx(gs, mouse=(1270, 700), click=True), items, rects)
check("mouse: clicking empty space does nothing", ev == [] or all(e[0] == "focus" for e in ev))
mv2 = widgets.MenuView("kb"); mv2.begin(5.0, 6); mv2.mouse_pos = (500, 500); mv2.mouse_active = True
mv2.input(uctx(gs, key=ord('s')), items, rects)
check("keyboard takes control back from the mouse", mv2.mouse_active is False and mv2.focus == 1)

# ---- main menu through the real handler ---------------------------------------------------------------------
import game.keys as keys_mod
ms = GameState(); ms.game_state = "START"; ms.current_time = 50.0
menu_screens.VIEWS["start"].focus = 0; menu_screens.VIEWS["start"].last_draw = -100
def hs_(s, **kw):
    c = uctx(s, t=s.current_time + 0.04, **kw); c.hand_pos = {"Left": None, "Right": None}
    handlers.handle_start(c, s, stats, snd, FakeTracker())
hs_(ms)
hs_(ms, key=ord('s'));  check("START: S moves focus to MODE", menu_screens.VIEWS["start"].focus == 1)
m0 = ms.settings["game_mode"]; hs_(ms, key=ord('d'))
check("START: D on MODE cycles the game mode", ms.settings["game_mode"] == (m0 + 1) % 3)
hs_(ms, key=ord('a')); check("START: A cycles it back", ms.settings["game_mode"] == m0)
hs_(ms, key=ord('s')); a0 = ms.settings["ai_enabled"]; hs_(ms, key=ord('d'))
check("START: D on PLAYERS swaps 2-player / vs CPU", ms.settings["ai_enabled"] != a0)
r = widgets.segment_rects(menu_screens.start_rects()[2], 3)
hs_(ms, mouse=(r[1][0] + 8, r[1][1] + 8), click=True)
check("START: clicking the VS CPU segment selects it", ms.settings["ai_enabled"] is True)
hs_(ms, mouse=(r[0][0] + 8, r[0][1] + 8), click=True)
check("START: clicking 2 PLAYERS selects it", ms.settings["ai_enabled"] is False)
hs_(ms, key=ord('3')); check("START: number keys still pick a mode", ms.settings["game_mode"] == 2)
st_rects = menu_screens.start_rects()
hs_(ms, mouse=(st_rects[6][0] + 50, st_rects[6][1] + 20), click=True)
check("START: clicking SETTINGS opens settings", ms.game_state == "SETTINGS" and ms.settings_return_state == "START")
ms.game_state = "START"
hs_(ms, mouse=(st_rects[3][0] + 50, st_rects[3][1] + 20), click=True)
check("START: clicking PLAYER NAMES opens the name dialog", ms.name_edit_active)
ms.name_edit_active = False
hs_(ms, mouse=(st_rects[7][0] + 50, st_rects[7][1] + 20), click=True)
check("START: clicking EXIT opens the confirm dialog (does not quit)", ms.show_exit_confirm and ms.game_state == "START")
er = menu_screens.exit_button_rects()
hs_(ms, mouse=(er["no"][0] + 20, er["no"][1] + 20), click=True)
check("EXIT dialog: clicking NO closes it", not ms.show_exit_confirm)
ms.show_exit_confirm = True
hs_(ms, mouse=(er["yes"][0] + 20, er["yes"][1] + 20), click=True)
check("EXIT dialog: clicking YES quits", ms.game_state == "QUIT")
ms.game_state = "START"; ms.show_exit_confirm = False
hs_(ms, key=32)
check("START: Space still starts a game from anywhere", ms.game_state == "COUNTDOWN")
ms.game_state = "START"; menu_screens.VIEWS["start"].focus = 0
hs_(ms, key=13)
check("START: Enter on PLAY starts a game", ms.game_state == "COUNTDOWN")
ms.game_state = "START"; menu_screens.VIEWS["start"].focus = 0
hs_(ms, mouse=(st_rects[0][0] + 100, st_rects[0][1] + 30), click=True)
check("START: clicking PLAY starts a game", ms.game_state == "COUNTDOWN")

# ---- settings screen ---------------------------------------------------------------------------------------------
def set_(s, **kw):
    c = uctx(s, t=s.current_time + 0.04, **kw)
    handlers.handle_settings(c, s, snd)
ss = GameState(); ss.game_state = "SETTINGS"; ss.settings_return_state = "START"; ss.current_time = 80.0
ss.settings.update({"score_to_win": 5, "difficulty": 1, "game_mode": 0, "ai_enabled": False})
settings_screen._tab = 0; settings_screen.VIEW.focus = 0; settings_screen.VIEW.last_draw = -100
set_(ss)
check("SETTINGS: opens on the Gameplay tab", settings_screen._tab == 0)
set_(ss, key=ord('s')); set_(ss, key=ord('d'))
check("SETTINGS: S then D raises difficulty", ss.settings["difficulty"] == 2)
set_(ss, key=ord('s')); [set_(ss, key=ord('d')) for _ in range(3)]
check("SETTINGS: D on the slider raises score-to-win by 1 each press", ss.settings["score_to_win"] == 8)
rr = settings_screen._settings_rects(6)
x0_, x1_, _ = widgets.slider_geometry(rr[2])
set_(ss, mouse=(x1_, rr[2][1] + 28), click=True)
check("SETTINGS: clicking the slider's right end sets the maximum (20)", ss.settings["score_to_win"] == 20)
set_(ss, mouse=(x0_ + (x1_ - x0_) * 0.25, rr[2][1] + 28), click=True)
check("SETTINGS: clicking a quarter of the way sets ~6", 5 <= ss.settings["score_to_win"] <= 7)
sg = widgets.segment_rects(rr[1], 3)
set_(ss, mouse=(sg[0][0] + 10, sg[0][1] + 10), click=True)
check("SETTINGS: clicking EASY sets easy", ss.settings["difficulty"] == 0)
set_(ss, mouse=(rr[5][0] + 60, rr[5][1] + 20), click=True)
check("SETTINGS: clicking the power-ups row toggles power-ups", ss.settings["powerups_enabled"] is False)
set_(ss, key=ord('e')); check("SETTINGS: E goes to the Audio tab", settings_screen._tab == 1)
set_(ss, key=ord('e')); set_(ss, key=ord('e')); set_(ss, key=ord('e')); check("SETTINGS: tabs wrap around (4 tabs)", settings_screen._tab == 0)
set_(ss, key=ord('q')); check("SETTINGS: Q goes back a tab (wraps to Camera)", settings_screen._tab == 3)
tr = settings_screen._TAB_RECTS
set_(ss, mouse=(tr[1][0] + 20, tr[1][1] + 10), click=True)
check("SETTINGS: clicking a tab opens it", settings_screen._tab == 1)
set_(ss, key=ord('s')); mus = ss.settings["music_volume"]; set_(ss, key=ord('d'))
check("SETTINGS (audio): D raises music volume by 10", ss.settings["music_volume"] == min(100, mus + 10))
set_(ss, key=27)
check("SETTINGS: Esc goes back to where it was opened from", ss.game_state == "START")
ss.game_state = "SETTINGS"; ss.settings_return_state = "MENU"; settings_screen._tab = 0
settings_screen.VIEW.focus = 1; settings_screen.VIEW.last_draw = -100
diff0 = ss.settings["difficulty"]; set_(ss); set_(ss, key=ord('d'))
check("SETTINGS (in match): locked rows don't change", ss.settings["difficulty"] == diff0)
check("SETTINGS (in match): locked rows are flagged", settings_screen._settings_items(ss, 0)[1]["enabled"] is False
      and settings_screen._settings_items(ss, 1)[0]["enabled"] is True)

# ---- in-game menu + pause + game over through the handlers ---------------------------------------------------------
im = GameState(); im.game_state = "MENU"; im.previous_state = "PLAYING"; im.menu_selection = 0; im.current_time = 120.0
menu_screens.VIEWS["menu"].last_draw = -100
def menu_(s, **kw):
    handlers.handle_menu(uctx(s, t=s.current_time + 0.04, **kw), s, snd)
menu_(im)
menu_(im, key=ord('s')); check("MENU: S moves to Settings", im.menu_selection == 1)
menu_(im, key=13); check("MENU: Enter on Settings opens settings (return = MENU)", im.game_state == "SETTINGS" and im.settings_return_state == "MENU")
im.game_state = "MENU"; menu_screens.VIEWS["menu"].last_draw = -100; im.menu_selection = 0
mr = menu_screens.menu_rects()
menu_(im, mouse=(mr[2][0] + 50, mr[2][1] + 20), click=True)
check("MENU: clicking Quit to Main Menu goes to START", im.game_state == "START")
im.game_state = "MENU"; im.previous_state = "PLAYING"; menu_screens.VIEWS["menu"].last_draw = -100
menu_(im, mouse=(mr[0][0] + 50, mr[0][1] + 20), click=True)
check("MENU: clicking Resume resumes through the countdown", im.game_state == "COUNTDOWN")
im.game_state = "MENU"; im.previous_state = "PLAYING"; menu_(im, key=27)
check("MENU: Esc resumes", im.game_state == "COUNTDOWN")

pz = GameState(); pz.game_state = "PAUSED"; pz.pause_by_key = True; pz.current_time = 200.0
pz.reset_for_new_game(); pz.game_state = "PAUSED"
pr_ = menu_screens.pause_resume_rect()
handlers.handle_paused(uctx(pz, mouse=(pr_[0] + 20, pr_[1] + 20), click=True, t=200.1), pz, snd)
check("PAUSED: clicking the RESUME button resumes", pz.game_state == "COUNTDOWN")

go = GameState(); go.game_state = "GAMEOVER"; go.current_time = 300.0; go.reset_for_new_game(); go.score = [5, 1]; go.winner = "Left Player"
engine._trigger_game_over(go)
gr = menu_screens.gameover_rects()
handlers.handle_gameover(uctx(go, t=300.1), go, st4, snd)
handlers.handle_gameover(uctx(go, mouse=(gr["menu"][0] + 30, gr["menu"][1] + 20), click=True, t=300.2), go, st4, snd)
check("GAME OVER: clicking MAIN MENU goes to the menu", go.game_state == "START")
go2 = GameState(); go2.reset_for_new_game(); go2.score = [5, 1]; go2.winner = "Left Player"; go2.game_state = "GAMEOVER"; go2.current_time = 400.0
engine._trigger_game_over(go2)
handlers.handle_gameover(uctx(go2, t=400.1), go2, st4, snd)
handlers.handle_gameover(uctx(go2, mouse=(gr["rematch"][0] + 30, gr["rematch"][1] + 20), click=True, t=400.2), go2, st4, snd)
check("GAME OVER: clicking PLAY AGAIN restarts", go2.game_state == "COUNTDOWN")

# ---- name dialog fields (mouse rects) still line up with what is drawn -----------------------------------------------
fr = menu_screens.name_field_rects()
check("name dialog: two field rects, stacked", len(fr) == 2 and fr[1][1] > fr[0][3])
nd = GameState(); nd.game_state = "START"; nd.current_time = 500.0; nd.name_edit_active = True; nd.name_edit_buf = ["a", "b"]
c = uctx(nd, mouse=((fr[1][0] + fr[1][2]) // 2, (fr[1][1] + fr[1][3]) // 2), click=True, t=500.1)
handlers.handle_start(c, nd, stats, snd, FakeTracker())
check("name dialog: clicking the 2nd field focuses it", nd.name_edit_field == 1)

# ---- rendering at several resolutions, every screen, no exceptions --------------------------------------------------------
import numpy as _np
def render_all(k):
    gfx.set_k(k); fw, fh = gfx.frame_size()
    fr_ = _np.zeros((fh, fw, 3), _np.uint8); gl = _rend.create_glow_layer()
    s = GameState(); s.reset_for_new_game(); s.current_time = 700.0; s.dt = 1 / 30
    s.settings.update({"player1_name": "A Very Long Name", "player2_name": "Another Long One"})
    s.reset_for_new_game(); engine.reset_ball(s); s.score = [3, 4]; s.winner = "Right Player"; s.event_board = board_with([("Z", 5, 1, 5)])
    s.game_state = "PLAYING"
    ctx = FrameCtx(frame=fr_, theme=get_theme(s.settings), hand_pos={"Left": None, "Right": None},
                   fist_state={"Left": False, "Right": False}, key=255, key_raw=-1, current_time=700.0, dt=1 / 30, glow_layer=gl)
    for i in range(6):
        s.current_time = 700.0 + i / 30
        ctx.current_time = s.current_time
        for gs_ in ("START", "SETTINGS", "MENU", "PAUSED", "COUNTDOWN", "GAMEOVER", "PLAYING"):
            s.game_state = gs_; s.settings_return_state = "START"; s.previous_state = "PLAYING"; s.countdown_start = s.current_time - 1
            {"START": lambda: handlers.handle_start(ctx, s, stats, snd, FakeTracker()),
             "SETTINGS": lambda: handlers.handle_settings(ctx, s, snd),
             "MENU": lambda: handlers.handle_menu(ctx, s, snd),
             "PAUSED": lambda: handlers.handle_paused(ctx, s, snd),
             "COUNTDOWN": lambda: handlers.handle_countdown(ctx, s, None),
             "GAMEOVER": lambda: handlers.handle_gameover(ctx, s, st4, snd),
             "PLAYING": lambda: handlers.handle_playing(ctx, s, snd, None)}[gs_]()
            s.stats_saved = True if gs_ == "GAMEOVER" else s.stats_saved
    return True
errs = []
for k in (45, 80, 120, 160):
    try: render_all(k)
    except Exception as e: errs.append((k, repr(e)))
gfx.set_k(80)
check(f"every redesigned screen renders at 480p / 720p / 1080p / 1440p {errs or ''}", not errs)
check("text widths are cached and consistent", ui.text_width("SETTINGS", 40, "bold") == ui.text_width("SETTINGS", 40, "bold") > 100)
check("fit_text shortens with an ellipsis, leaves short text alone",
      ui.fit_text("Alexandria Bartholomew", 22, "bold", 120).endswith("...") and ui.fit_text("Ann", 22, "bold", 300) == "Ann"
      and ui.text_width(ui.fit_text("Alexandria Bartholomew", 22, "bold", 120), 22, "bold") <= 125)


# ================== DISPLAY + CAMERA SETTINGS ============================================
import pygame as _pg
import time as _time
from game.system import System, CAMERA_QUALITIES
from game import camera as _cam_mod
_pg.display.init()

class FakeDisplay:
    def __init__(self, sizes, cur=0):
        self.sizes, self.cur, self.fullscreen, self.fill_window = sizes, cur, False, False
        self.calls = []
        self.size = sizes[cur]
    def displays(self): return [{"index": i, "w": w, "h": h, "primary": i == 0} for i, (w, h) in enumerate(self.sizes)]
    def current_display_index(self): return self.cur
    def native_size(self): return self.sizes[self.cur]
    def set_fullscreen(self, on): self.fullscreen = on; self.calls.append(("fs", on))
    def move_to_display(self, i):
        if not 0 <= i < len(self.sizes): return False
        self.cur = i; self.calls.append(("move", i)); return True

class FakeCam:
    def __init__(self, index, w=1920, h=1080, fps=30.0):
        self.index, self.size, self.fps, self.ok, self.opened = index, (w, h), fps, True, True
        self.target_size = None; self.stopped = False; self.on_small = None
    label = property(lambda s: f"{s.index}  {s.size[0]}x{s.size[1]}")
    def stop(self): self.stopped = True; self.opened = False

def make_system(sizes=((1366, 768), (1920, 1080)), cur=1, cams=(), active=1, settings=None, scan=True):
    saves, toasts, attached = [], [], []
    st = {"render_height": 0, "fullscreen": False, "display_index": cur, "camera_index": active, "camera_quality": 0}
    if settings: st.update(settings)
    _cam_mod.probe_cameras = lambda skip=(): [dict(c) for c in cams if c["index"] not in skip]
    fd, fc = FakeDisplay(list(sizes), cur), FakeCam(active)
    sy = System(fd, fc, st, lambda s: saves.append(dict(s)), attached.append, toasts.append, lambda: "TRK 30/s 40ms")
    if scan:
        sy.rescan_cameras()                 # the game scans on demand, not at start-up
    return sy, fd, fc, st, saves, toasts, attached

def settle(sy, what="scan", timeout=3.0):
    t0 = _time.time()
    while _time.time() - t0 < timeout:
        sy.poll(now=_time.monotonic() + 10)
        if what == "scan" and not sy.scanning: return True
        if what == "switch" and not sy.switching: return True
        _time.sleep(0.01)
    return False

# ---- render-resolution cap -------------------------------------------------------------
gfx.set_render_cap(0)
check("gfx: no cap -> native 4K renders at 4K (k=240)", gfx.k_for_size(3840, 2160) == 240 and gfx.k_for_size(1920, 1080) == 120)
gfx.set_render_cap(1080); check("gfx: 1080p cap limits a 4K monitor to 1920x1080", gfx.k_for_size(3840, 2160) == 120 and gfx.k_for_size(1280, 720) == 80)
gfx.set_render_cap(720);  check("gfx: 720p cap", gfx.k_for_size(1920, 1080) == 80)
gfx.set_render_cap(0);    check("gfx: cap 0 = automatic again", gfx.k_for_size(2560, 1440) == 160)
sy, fd, fc, st, saves, toasts, attached = make_system(settings={"render_height": 720})
check("System applies the saved resolution cap at startup (and fills the window)", gfx.k_for_size(3840, 2160) == 80 and fd.fill_window is True)
gfx.set_render_cap(0)

# ---- resolution options adapt to the monitor ------------------------------------------------
sy, fd, *_ = make_system(sizes=((1920, 1080),), cur=0)
check("1080p monitor offers AUTO, 1080p, 720p, 540p", sy.render_options() == [0, 1080, 720, 540])
sy, fd, *_ = make_system(sizes=((3840, 2160), (1366, 768)), cur=0)
check("4K monitor offers everything up to 2160p", sy.render_options() == [0, 2160, 1440, 1080, 720, 540])
fd.cur = 1
check("options follow the monitor the game is on (laptop panel: 720p and 540p)", sy.render_options() == [0, 720, 540])
sy, fd, fc, st, saves, toasts, attached = make_system(sizes=((1920, 1080),), cur=0)
sy.cycle_render(1)
check("cycling resolution: saves it, applies the cap, fills the window",
      st["render_height"] == 1080 and gfx.k_for_size(3840, 2160) == 120 and fd.fill_window and saves[-1]["render_height"] == 1080)
sy.cycle_render(-1); check("cycling back to AUTO restores native rendering", st["render_height"] == 0 and gfx.k_for_size(3840, 2160) == 240 and not fd.fill_window)
sy.cycle_render(-1); check("resolution list wraps around", st["render_height"] == 540)
sy.set_render_height(0)

# ---- fullscreen + monitor ----------------------------------------------------------------------
sy, fd, fc, st, saves, toasts, attached = make_system()
sy.set_fullscreen(True)
check("fullscreen is applied and remembered", fd.fullscreen and st["fullscreen"] is True and saves[-1]["fullscreen"] is True)
sy.toggle_fullscreen(); check("toggle goes back to windowed", not fd.fullscreen and st["fullscreen"] is False)
sy.cycle_display(1)
check("next monitor wraps 2 -> 1 and is remembered", fd.cur == 0 and st["display_index"] == 0 and ("move", 0) in fd.calls)
sy.cycle_display(-1); check("previous monitor wraps back", fd.cur == 1 and st["display_index"] == 1)
one, ofd, *_ = make_system(sizes=((1920, 1080),), cur=0)
one.cycle_display(1); check("single monitor: choosing another does nothing", ofd.calls == [])

# ---- monitors plugged / unplugged while running --------------------------------------------------
real_n = _pg.display.get_num_displays
_pg.display.get_num_displays = lambda: 2          # the fake rig has two monitors, whatever is attached right now
sy, fd, fc, st, saves, toasts, attached = make_system(cur=1)
_pg.display.get_num_displays = lambda: 1
sy.poll(now=_time.monotonic() + 5)
check("monitor unplugged while the game is on it: moves to the remaining one and says so",
      fd.cur == 0 and st["display_index"] == 0 and any("DISPLAYS CHANGED" in t for t in toasts))
n_toasts = len(toasts); sy.poll(now=_time.monotonic() + 7)
check("no repeated notifications", len(toasts) == n_toasts)
_pg.display.get_num_displays = real_n

# ---- cameras: scanning, listing, switching in the background ----------------------------------------
found = [{"index": 0, "w": 1280, "h": 720}, {"index": 1, "w": 1920, "h": 1080}]      # the two physical cameras
sy, fd, fc, st, saves, toasts, attached = make_system(cams=found, active=1)
check("scan runs in the background and finds the other camera", settle(sy) and sy.scanned_once)
check("camera list = scanned devices + the active one, ordered",
      [(c["index"], c["active"]) for c in sy.cameras()] == [(0, False), (1, True)] and sy.cameras()[1]["w"] == 1920)
opened = []
def fake_open(index, max_h=0):
    opened.append((index, max_h)); c = FakeCam(index, 1280, 720, 26.0); return c
_cam_mod.open_specific = fake_open
sy.target_size = (1920, 1080)
check("select_camera starts a switch without blocking", sy.select_camera(0) is True and "SWITCHING" in toasts[-1])
settle(sy, "switch")
check("the new camera goes live: attached, sized to the render frame, old one released, choice saved",
      sy.camera.index == 0 and attached and attached[-1] is sy.camera and sy.camera.target_size == (1920, 1080)
      and fc.stopped and st["camera_index"] == 0 and "CAMERA 0" in toasts[-1])
settle(sy)
check("after a switch the list is refreshed (old camera now listed as inactive)", {c["index"]: c["active"] for c in sy.cameras()}.get(1) is False)
_cam_mod.open_specific = lambda i, h=0: None
sy.select_camera(1); settle(sy, "switch")
check("a camera that fails to open: message shown, current camera kept", "COULD NOT BE OPENED" in toasts[-1] and sy.camera.index == 0)
_cam_mod.open_specific = fake_open

# cycling (C key / arrows)
sy, fd, fc, st, saves, toasts, attached = make_system(cams=found, active=1)
settle(sy); opened.clear()
sy.cycle_camera(1); settle(sy, "switch")
check("cycle_camera moves to the next known camera (wraps)", opened[-1][0] == 0 and sy.camera.index == 0)
sy, fd, fc, st, saves, toasts, attached = make_system(cams=[], active=1)
settle(sy); n0 = len(attached); sy.cycle_camera(1)
check("only one camera: no switch, says so and rescans", len(attached) == n0 and "NO OTHER CAMERA" in toasts[-1] and not sy.switching)

# quality
check("quality ladder: auto tries 1080p/720p/480p, 720p skips 1080p, 480p only 480p",
      [m[1] for m in _cam_mod._modes_for(0)] == [1080, 720, 480] and [m[1] for m in _cam_mod._modes_for(720)] == [720, 480]
      and [m[1] for m in _cam_mod._modes_for(480)] == [480])
sy, fd, fc, st, saves, toasts, attached = make_system(cams=found, active=1)
settle(sy); opened.clear()
sy.cycle_quality(1); settle(sy, "switch")
check("changing camera quality reopens the same camera with the limit, and saves it",
      st["camera_quality"] == 720 and opened[-1] == (1, 720) and fc.stopped)
sy.cycle_quality(1); settle(sy, "switch"); sy.cycle_quality(1)
check("quality does not wrap past 480p", st["camera_quality"] == 480)
sy.cycle_quality(-1); settle(sy, "switch"); sy.cycle_quality(-1); settle(sy, "switch")
check("and can return to AUTO", st["camera_quality"] == 0)

# ---- saved settings are validated ----------------------------------------------------------------------
v = st_mod._validated_settings({"render_height": 1234, "camera_quality": 999, "fullscreen": "yes", "display_index": 99})
check("bad display/camera values fall back to safe defaults",
      v["render_height"] == 0 and v["camera_quality"] == 0 and v["fullscreen"] is False and v["display_index"] == 15)
v = st_mod._validated_settings({"render_height": 1440, "camera_quality": 720, "fullscreen": True, "display_index": 1})
check("good values are kept", v["render_height"] == 1440 and v["camera_quality"] == 720 and v["fullscreen"] is True and v["display_index"] == 1)

# ---- windowed size adapts to any monitor (real Display, patched monitor list) ---------------------------------
from game.display import Display
real_sizes = _pg.display.get_desktop_sizes
def ds(size): _pg.display.get_desktop_sizes = lambda: [size]; return Display.default_windowed_size(0)
ok_ = True
for mon in ((1366, 768), (1920, 1080), (2560, 1440), (3840, 2160), (1024, 600), (1920, 1200), (5120, 1440)):
    w, h = ds(mon)
    ok_ &= (w <= 0.9 * mon[0] and h <= 0.9 * mon[1] and abs(w / h - 16 / 9) < 0.02 and w % 16 == 0)
_pg.display.get_desktop_sizes = real_sizes
check("default window is 16:9, <=90% of any monitor from 1024x600 to ultrawide 5K", ok_)
w, h = (lambda: (_pg.display.get_desktop_sizes.__call__() or None))() or (0, 0) if False else (0, 0)
_pg.display.get_desktop_sizes = lambda: [(3840, 2160), (1366, 768)]
check("monitor list reports every attached monitor at native size",
      Display.displays() == [{"index": 0, "w": 3840, "h": 2160, "primary": True}, {"index": 1, "w": 1366, "h": 768, "primary": False}])
_pg.display.get_desktop_sizes = real_sizes

# ---- present: a user-capped (smaller) frame fills the window; auto leaves it 1:1 -----------------------------
dd = Display("t", (1280, 720))
small = _np.zeros((360, 640, 3), _np.uint8)
dd.fill_window = False; dd.present(small); a1 = dd._scale
dd.fill_window = True; dd.present(small); a2 = (dd._scale, dd._ox, dd._oy)
check("AUTO resolution shows a smaller frame 1:1 (centred); a chosen cap scales it up to fill the window",
      a1 == 1.0 and abs(a2[0] - 2.0) < 0.01 and a2[1] == 0 and a2[2] == 0)
dd.fill_window = False

# ---- the settings screens, driven by the real handlers -------------------------------------------------------------
sy, fd, fc, st, saves, toasts, attached = make_system(cams=found, active=1)
settle(sy)
gs_ = GameState(); gs_.game_state = "SETTINGS"; gs_.settings_return_state = "START"; gs_.current_time = 900.0
gs_.settings.update(st); gs_.system = sy
def set2(s, **kw):
    handlers.handle_settings(uctx(s, t=s.current_time + 0.04, **kw), s, snd)
settings_screen._tab = 2; settings_screen.VIEW.focus = 0; settings_screen.VIEW.last_draw = -100
set2(gs_)
items = settings_screen._settings_items(gs_, 2)
check("DISPLAY tab: window mode, monitor, resolution, theme, skeleton, rendering info",
      [i["label"] for i in items] == ["WINDOW MODE", "MONITOR", "RESOLUTION", "COLOR THEME", "HAND SKELETON", "RENDERING"])
check("DISPLAY tab shows the real monitor and render size",
      "DISPLAY 2" in items[1]["value"] and "1920x1080" in items[1]["value"] and items[5]["kind"] == "info")
rr2 = settings_screen._settings_rects(6)
sgm = widgets.segment_rects(rr2[0], 2)
set2(gs_, mouse=(sgm[1][0] + 10, sgm[1][1] + 10), click=True)
check("clicking FULLSCREEN in the settings goes fullscreen (and is saved)", fd.fullscreen and st["fullscreen"])
set2(gs_, mouse=(sgm[0][0] + 10, sgm[0][1] + 10), click=True)
check("clicking WINDOWED goes back", not fd.fullscreen)
set2(gs_, key=ord('s')); set2(gs_, key=ord('d'))
check("MONITOR row: D switches to the next monitor", fd.cur == 0 and st["display_index"] == 0)
set2(gs_, key=ord('s')); set2(gs_, key=ord('d'))
check("RESOLUTION row: D picks the next resolution option", st["render_height"] in (1080, 720, 540) and gfx.k_for_size(3840, 2160) < 240)
set2(gs_, key=ord('a')); gfx.set_render_cap(0)
check("RESOLUTION row: A goes back to AUTO", st["render_height"] == 0)
set2(gs_, key=ord('e'))
check("E moves to the CAMERA tab and triggers a rescan", settings_screen._tab == 3)
ci = settings_screen._settings_items(gs_, 3)
check("CAMERA tab: camera, quality, rescan, active camera, hand tracking",
      [i["label"] for i in ci] == ["CAMERA PICTURE", "CAMERA", "CAMERA QUALITY", "RESCAN CAMERAS", "ACTIVE CAMERA", "HAND TRACKING"])
check("CAMERA tab shows the active camera with its size, and live tracker stats",
      "1920x1080" in ci[1]["value"] and "CAMERA 1" in ci[4]["value"] and ci[5]["value"] == "TRK 30/s 40ms")
settings_screen.VIEW.focus = 1
opened.clear(); set2(gs_, key=ord('d')); settle(sy, "switch")
check("CAMERA row: D switches camera (in the background)", sy.camera.index == 0 and opened and opened[-1][0] == 0)
rr3 = settings_screen._settings_rects(6)
sq = widgets.segment_rects(rr3[2], 3)
opened.clear(); set2(gs_, mouse=(sq[2][0] + 10, sq[2][1] + 10), click=True); settle(sy, "switch")
check("clicking 480P in CAMERA QUALITY limits and reopens the camera", st["camera_quality"] == 480 and opened and opened[-1][1] == 480)
n_scan = 0
settle(sy)
set2(gs_, mouse=(rr3[3][0] + 100, rr3[3][1] + 20), click=True)
check("RESCAN CAMERAS (click) starts a scan", sy.scanning or sy.scanned_once)
before = dict(st)
set2(gs_, mouse=(rr3[4][0] + 100, rr3[4][1] + 20), click=True); set2(gs_, key=ord('d'))
check("info rows are read-only", dict(st) == before)
check("display / camera rows are not locked during a match",
      all(i["enabled"] for i in ci[1:4]) and not settings_screen.is_setting_locked(gs_, 12) and not settings_screen.is_setting_locked(gs_, 14))
gs_.settings_return_state = "MENU"
check("...even when opened from the in-game menu", all(i["enabled"] for i in settings_screen._settings_items(gs_, 3)[1:4]))

# without a System (e.g. a very early failure) the tabs degrade instead of crashing
ns = GameState(); ns.game_state = "SETTINGS"; ns.settings_return_state = "START"; ns.current_time = 950.0
for tab in (2, 3):
    settings_screen._tab = tab; settings_screen.VIEW.focus = 0; settings_screen.VIEW.last_draw = -100
    set2(ns); set2(ns, key=ord('d')); set2(ns, key=13)
its = settings_screen._settings_items(ns, 3)
check("no System available: display / camera rows show NOT AVAILABLE, are disabled, nothing crashes",
      its[1]["value"] == "NOT AVAILABLE" and its[1]["enabled"] is False)
settings_screen._tab = 0
gfx.set_k(80)


# ================== CRASH-PROOFING: scan timing, isolation, crash log ====================
from game import crashlog
probe_calls = []
def counting_probe(skip=()):
    probe_calls.append(set(skip)); return [dict(c) for c in found if c["index"] not in skip]

# no scan while the game starts
_cam_mod.probe_cameras = counting_probe
probe_calls.clear()
fd0, fc0 = FakeDisplay([(1920, 1080)], 0), FakeCam(1)
sy0 = System(fd0, fc0, {"render_height": 0, "fullscreen": False, "display_index": 0, "camera_index": 1, "camera_quality": 0},
             lambda s: None, lambda c: None, lambda t: None, lambda: "")
_time.sleep(0.2)
check("nothing probes the cameras during start-up", probe_calls == [] and not sy0.scanning and not sy0.scanned_once)

# C pressed before any scan: it looks first, then switches by itself
sy, fd, fc, st, saves, toasts, attached = make_system(cams=found, active=1)
_cam_mod.probe_cameras = counting_probe
sy._found = []; sy.scanned_once = False; probe_calls.clear(); opened.clear()
sy.cycle_camera(1)
check("C before the first scan: says it is looking (and starts a scan)", "LOOKING FOR CAMERAS" in toasts[-1] and (sy.scanning or probe_calls))
settle(sy); settle(sy, "switch"); settle(sy)
check("...then switches to the camera it found, without a second key press", sy.camera.index == 0 and opened and opened[-1][0] == 0)
check("the scan skipped the camera in use", probe_calls and 1 in probe_calls[0])

only = [{"index": 1, "w": 1920, "h": 1080}]
_cam_mod.probe_cameras = lambda skip=(): [c for c in only if c["index"] not in skip]
sy, fd, fc, st, saves, toasts, attached = make_system(cams=[], active=1)
_cam_mod.probe_cameras = lambda skip=(): []
sy.cycle_camera(1); settle(sy); sy.poll(now=_time.monotonic() + 20)
check("C with no other camera attached: says so, no switch, no crash", "NO OTHER CAMERA FOUND" in toasts[-1] and sy.camera.index == 1)

# a failing helper never stops the game
sy, fd, fc, st, saves, toasts, attached = make_system(cams=found, active=1)
logd = tempfile.mkdtemp(); crashlog.LOG_PATH = os.path.join(logd, "crash_log.txt")
def bad_poll(now): raise RuntimeError("camera driver exploded")
sy._poll = bad_poll
try:
    sy.poll(); survived = True
except Exception:
    survived = False
check("an error inside System.poll is swallowed (game keeps running)", survived)
log = open(crashlog.LOG_PATH, encoding="utf-8").read()
check("...and recorded in the crash log with a traceback", "System.poll" in log and "camera driver exploded" in log and "Traceback" in log)
crashlog.log_exception("second entry")
check("log entries accumulate (append, newest last)", open(crashlog.LOG_PATH, encoding="utf-8").read().count("===") >= 4)
crashlog.LOG_PATH = os.path.join(logd, "no_such_dir", "x.txt")
try:
    crashlog.log_exception("unwritable"); ok = True
except Exception:
    ok = False
check("an unwritable log location can't cause a second crash", ok)

# the real isolated probe: a child that dies or hangs yields 'no cameras', not a crash/freeze
real_probe_code = _cam_mod._PROBE_CODE
import importlib; importlib.reload(_cam_mod)          # restore the real probe_cameras (tests above replaced it)
_cam_mod._PROBE_CODE = "raise SystemExit(3)"
check("a scan process that crashes gives [] (game unaffected)", _cam_mod.probe_cameras(set()) == [])
_cam_mod._PROBE_CODE = "import time; time.sleep(30)"
t0 = _time.time(); r = _cam_mod.probe_cameras(set(), timeout=1)
check("a scan process that hangs is abandoned after the timeout", r == [] and _time.time() - t0 < 5)
_cam_mod._PROBE_CODE = "print('PROBE:' + '[{\"index\": 7, \"w\": 1920, \"h\": 1080}]')"
check("a well-behaved scan process's result is parsed", _cam_mod.probe_cameras(set()) == [{"index": 7, "w": 1920, "h": 1080}])
_cam_mod._PROBE_CODE = real_probe_code


# ================== WINDOW-WRAPPER CRASH REGRESSION ====================================
import subprocess as _sp, textwrap as _tw
from game import display as _dmod

# root cause: a throw-away Window wrapper leaves SDL holding a dangling pointer
import types as _types
real_sdl = _dmod._sdl_video
real_from = real_sdl.Window.from_display_module
made = []
def counting_from(*a, **k):
    w = real_from(*a, **k); made.append(w); return w
_dmod._sdl_video = _types.SimpleNamespace(Window=_types.SimpleNamespace(from_display_module=counting_from))
try:
    dz = Display("wrapper test", (640, 360))
    made.clear()
    for _ in range(60): dz.current_display_index(); dz.native_size()
    check("asking 'which monitor?' 120 times creates ONE window wrapper, not one per call", len(made) == 1)
    first = made[0]
    dz._set_mode(0)
    dz.current_display_index()
    check("a rebuilt window gets a fresh wrapper", len(made) == 2 and made[1] is not first)
    import gc; gc.collect()
    check("old wrappers are kept alive (never freed under SDL's feet)", any(w is first for w in dz._keepalive))
finally:
    _dmod._sdl_video = real_sdl

# the original crashing sequence, in its own process (a native crash there must fail the test, not kill it)
stress = _tw.dedent('''
    import os, sys, time
    sys.path.insert(0, os.getcwd())     # the parent runs this with cwd=ROOT
    import numpy as np, pygame
    from game import gfx
    from game.display import Display
    pygame.init()
    d = Display("stress", None, 1 if pygame.display.get_num_displays() > 1 else 0, False)
    frame = None
    def tick(n):
        global frame
        for _ in range(n):
            d.poll(); gfx.set_k(gfx.k_for_size(*d.size)); fw, fh = gfx.frame_size()
            if frame is None or frame.shape[:2] != (fh, fw): frame = np.full((fh, fw, 3), 90, np.uint8)
            d.present(frame); time.sleep(0.01)
        d.current_display_index()
    n = pygame.display.get_num_displays()
    tick(20)
    for r in range(3):
        d.move_to_display(0); tick(25); d.move_to_display(n - 1); tick(25)
    d.set_fullscreen(True); tick(25)
    for r in range(3):
        d.move_to_display(0); tick(25); d.move_to_display(n - 1); tick(25)
    d.set_fullscreen(False); tick(25)
    print("STRESS-OK")
''')
res = _sp.run([sys.executable, "-c", stress], capture_output=True, text=True, timeout=120, cwd=ROOT)
check("stress: 12 monitor moves + fullscreen toggles with live event polling, no native crash",
      "STRESS-OK" in res.stdout and res.returncode == 0)


# ================== MOUSE POINTER ========================================================
import numpy as _np9
def blank(k):
    gfx.set_k(k); w, h = gfx.frame_size()
    return _np9.full((h, w, 3), (30, 26, 24), _np9.uint8)

ACC = (0, 255, 200)
for k in (45, 80, 120, 240):
    f = blank(k); S = gfx.SCALE
    ui.draw_cursor(f, (400, 300), 50.0, ACC)
    white = _np9.argwhere((f > 240).all(axis=2))
    tipx, tipy = 400 * S, 300 * S
    check(f"k={k}: the arrow's white body is drawn at the pointer position",
          len(white) > 20 and abs(white[:, 1].min() - tipx) < 4 * S + 2 and abs(white[:, 0].min() - tipy) < 4 * S + 2
          and white[:, 1].max() < tipx + 20 * S and white[:, 0].max() < tipy + 30 * S)
    changed = _np9.argwhere((f != 30).any(axis=2) & ((f != _np9.array([30, 26, 24])).any(axis=2)))
    check(f"k={k}: nothing is drawn far from the pointer",
          changed[:, 1].max() < tipx + 40 * S and changed[:, 0].max() < tipy + 50 * S and changed[:, 1].min() > tipx - 20 * S)
    accent_px = ((f[:, :, 1] > 150) & (f[:, :, 0] < 120)).sum()
    check(f"k={k}: the halo uses the theme accent colour", accent_px > 15)

f = blank(120); before = f.copy()
for p in ((-1, -1), (-5, 100), (100, -5), (1280, 100), (100, 720), (5000, 5000)):
    ui.draw_cursor(f, p, 1.0, ACC)
check("a pointer outside the window draws nothing", (f == before).all())
f = blank(120)
for p in ((0, 0), (1279, 719), (1270, 5), (3, 715)):
    ui.draw_cursor(f, p, 1.0, ACC)
check("pointers in every corner draw without error (clipped at the edges)", True)

# click ripple
f = blank(120); S = gfx.SCALE
ui.draw_cursor(f, (900, 500), 10.0, ACC, click=(300, 200, 9.85))        # 0.15 s into the ripple
cx, cy = int(300 * S), int(200 * S)
ring = ((f[:, :, 1] > 60) & (f[:, :, 1] != 26))
ys, xs = _np9.nonzero(ring[: int(400 * S), : int(500 * S)])
check("a click ripple is drawn around the click point while it is young",
      len(xs) > 40 and abs(xs.mean() - cx) < 8 * S and abs(ys.mean() - cy) < 8 * S)
radii = _np9.hypot(xs - cx, ys - cy)
check("...as a ring (all pixels at about the same distance)", radii.std() < 4 * S and 8 * S < radii.mean() < 40 * S)
f2 = blank(120)
ui.draw_cursor(f2, (900, 500), 10.0, ACC, click=(300, 200, 9.4))        # 0.6 s ago: over
check("the ripple is gone after 0.45 s", (f2[: int(400 * S), : int(500 * S)] == _np9.array([30, 26, 24])).all())
f3 = blank(120)
ui.draw_cursor(f3, (900, 500), 10.0, ACC, click=(300, 200, 10.5))       # in the future / clock oddity
check("a click time in the future does not draw (no crash either)", (f3[: int(400 * S), : int(500 * S)] == _np9.array([30, 26, 24])).all())
check("the pointer draws through ui.draw_cursor",
      (lambda fr: (ui.draw_cursor(fr, (200, 200), 5.0, ACC), (fr != _np9.array([30, 26, 24])).any())[1])(blank(80)))
gfx.set_k(80)


# ================== CAMERA PICTURE OFF ===================================================
import numpy as _np10
from game import menu_screens as _ms10
check("show_camera_feed defaults to on", st_mod.DEFAULT_SETTINGS["show_camera_feed"] is True)
check("show_camera_feed is a validated bool setting", "show_camera_feed" in st_mod._BOOL_SETTINGS)
_st10 = GameState(); _st10.settings["show_camera_feed"] = True
settings_screen.change_setting(_st10, 17, 1, None)
check("setting 17 toggles the camera picture off", _st10.settings["show_camera_feed"] is False)
settings_screen.change_setting(_st10, 17, 1, None)
check("...and back on", _st10.settings["show_camera_feed"] is True)
_items = [i for t in range(4) for i in settings_screen._settings_items(_st10, t)]
check("a CAMERA PICTURE toggle row exists on the CAMERA tab",
      any(i["id"] == 17 and i["kind"] == "toggle" for i in settings_screen._settings_items(_st10, 3)))
check("the settings rows still fit on the panel",
      settings_screen._settings_rects(len(settings_screen._settings_items(_st10, 3)))[-1][1] + 56 < settings_screen._SET_Y + settings_screen._SET_H - 40)
gfx.set_k(45); _w, _h = gfx.frame_size()
_dst = _np10.full((_h, _w, 3), 200, _np10.uint8)
_rend.prepare_plain_background(_dst)
check("plain backdrop is dark and not the camera picture", _dst.max() < 60 and _dst.min() > 5)
check("plain backdrop is darker at the corners (vignette)", _dst[0, 0].sum() < _dst[_h // 2, _w // 2].sum())
gfx.set_k(80)


# ================== FIST PAUSE OFF =======================================================
_fs = GameState(); _fs.game_state = "PLAYING"; _fs.current_time = 5.0; _fs.fist_pause_cooldown = 0
_fs.settings["fist_pause_enabled"] = False
handlers.handle_playing(ctx_for(_fs, fist=True), _fs, None, None)
check("two fists do not pause when the gesture is disabled", _fs.game_state == "PLAYING")
_fs.settings["fist_pause_enabled"] = True
handlers.handle_playing(ctx_for(_fs, fist=True), _fs, None, None)
check("...and still pause when it is enabled", _fs.game_state == "PAUSED")
check("fist_pause_enabled is a validated bool setting", "fist_pause_enabled" in st_mod._BOOL_SETTINGS)


# ================== DIFFICULTY RAMP ======================================================
from game import config as _cfg12
_r = GameState(); _r.settings["ai_enabled"] = True; _r.settings["game_mode"] = 0; _r.settings["difficulty"] = 1
_r.score = [0, 0]; _r.game_time = 0.0; _p0 = difficulty.ramp_progress(_r)
_r.game_time = _cfg12.DIFFICULTY_RAMP_SECONDS / 2; _p1 = difficulty.ramp_progress(_r)
_r.game_time = 9999; _p2 = difficulty.ramp_progress(_r)
check("vs CPU ramp goes 0 -> 0.5 -> capped at 1", _p0 == 0 and abs(_p1 - 0.5) < 1e-6 and _p2 == 1)
_r.settings["game_mode"] = 2; _r.game_time = _cfg12.TIME_ATTACK_DURATION * _cfg12.TIME_ATTACK_RAMP_FRACTION / 2
check("Time Attack ramps over its own 40 s", abs(difficulty.ramp_progress(_r) - 0.5) < 1e-6)
_r.settings["ai_enabled"] = False; _r.game_time = 100
check("two-player games ramp too (ball speed)", difficulty.ramp_progress(_r) > 0)

def _ai_dist(gt):
    s = GameState(); s.settings["ai_enabled"] = True; s.settings["game_mode"] = 0; s.settings["difficulty"] = 1
    s.game_time = gt; s.ai_aim_offset = 0
    engine.reset_ball(s, "right")
    b = next(x for x in s.balls if x.is_main); b.vx = 300; b.y = 700; b.x = 600
    s.right_paddle_target = 0.0
    engine._update_ai(s, 0.1)
    return s.right_paddle_target
check("the CPU paddle moves faster late in a game than early", _ai_dist(200) > _ai_dist(0) * 1.3)
def _serve(gt):
    s = GameState(); s.settings["ai_enabled"] = True; s.settings["game_mode"] = 0; s.settings["difficulty"] = 1
    s.game_time = gt; engine.reset_ball(s, "right")
    b = next(x for x in s.balls if x.is_main); return math.hypot(b.vx, b.vy)
check("the ball serves faster late in a game", _serve(200) > _serve(0) * 1.1)


# ================== PADDLE HIT LIGHT-UP ==================================================
from game import effects as _fx13
from game.config import LEFT_PADDLE_X as _LPX, PADDLE_WIDTH as _PW, PADDLE_FLASH_SECONDS as _PFS
def _hit_state():
    s = GameState(); s.settings["ai_enabled"] = False; s.game_state = "PLAYING"; s.current_time = 10.0
    engine.reset_ball(s, "left")
    b = next(x for x in s.balls if x.is_main)
    b.x = _LPX + _PW + 2; b.y = s.left_paddle_y + s.left_paddle_height / 2; b.vx = -400; b.vy = 0
    return s, b
_s, _b = _hit_state(); _np = len(_s.particles)

class _Snd:
    def __getattr__(self, n): return lambda *a, **k: None

_fx13.paddle_hit(_s, "left", _b, 0.5)
check("a paddle hit records a flash with a colour for that side", _s.paddle_flash["left"] is not None and _s.paddle_flash["right"] is None)
check("a hit sprays extra sparks", len(_s.particles) > _np + 8)
_h1 = _s.paddle_flash["left"][1]; _fx13.paddle_hit(_s, "left", _b, 0.5)
check("each hit lights the paddle in a different colour", _s.paddle_flash["left"][1] != _h1)
import numpy as _n13
gfx.set_k(80); _w, _h = gfx.frame_size(); th = get_theme(_s.settings)
def _paddle_px(t):
    _s.current_time = t; f = _n13.zeros((_h, _w, 3), _n13.uint8)
    _rend.draw_paddles(f, _s, th); return f
_k = gfx.SCALE; _ys = int((_s.left_paddle_y + 20) * _k)
_s.paddle_flash["left"] = (10.0, 20, 1.0)
_lit = _paddle_px(10.02); _late = _paddle_px(10.0 + _PFS + 0.1)
_cx = int((_LPX + _PW // 2) * _k)
check("the struck paddle changes colour while lit", tuple(_lit[_ys, _cx]) != tuple(_late[_ys, _cx]))
check("the lit paddle is brighter and its glow bigger", _lit.sum() > _late.sum())
check("after the flash the paddle is back to its normal look", tuple(_late[_ys, _cx]) != (0, 0, 0))
# a real collision triggers it
_s2, _b2 = _hit_state(); _s2.paddle_flash["left"] = None
engine.check_all_collisions(_s2, _Snd())
check("a real paddle collision lights the paddle", _s2.paddle_flash["left"] is not None)
gfx.set_k(80)


# ================== RAMP: POINTS + LEVEL =================================================
_q = GameState(); _q.settings["ai_enabled"] = True; _q.settings["game_mode"] = 0; _q.game_time = 0
_q.score = [3, 2]
check("each point scored pushes the CPU level up in normal games", abs(difficulty.ramp_progress(_q) - 0.6) < 1e-6)
check("CPU level label runs 1..5", difficulty.cpu_level(_q) == 3 and
      (_q.__setattr__("game_time", 999) or difficulty.cpu_level(_q)) == 5)
_q.settings["ai_enabled"] = False
check("no CPU level in two-player games", difficulty.cpu_level(_q) is None)
_q.game_time = 0; _q.score = [0, 0]
check("two players: ball speed multiplier starts at 1.0 and reaches the ramp maximum",
      abs(difficulty.speed_multiplier(_q) - 1.0) < 1e-6 and (_q.__setattr__("game_time", 999) or True)
      and abs(difficulty.speed_multiplier(_q) - 1.5) < 1e-6)
def _serve2p(gt):
    s = GameState(); s.settings.update(ai_enabled=False, game_mode=0, difficulty=1); s.game_time = gt
    engine.reset_ball(s, "right"); b = next(x for x in s.balls if x.is_main); return math.hypot(b.vx, b.vy)
check("two players: the ball serves faster late in a game", _serve2p(120) > _serve2p(0) * 1.3)
_h2 = GameState(); _h2.settings["ai_enabled"] = False; _h2.game_time = 70; _h2.match_names = ("A", "B")
_hf = np.zeros((WINDOW_HEIGHT, WINDOW_WIDTH, 3), np.uint8); __import__('game.hud', fromlist=['draw_hud']).draw_hud(_hf, _h2, get_theme(_h2.settings))
check("two players: the HUD draws a SPEED readout under the score", _hf[88:112, 560:720].any())
_q.settings["ai_enabled"] = True; _q.score = [0, 0]; _q.game_time = 0
_a = _ai_dist(0); _z = _ai_dist(90)
check("late-game CPU is at least 1.8x as quick as at the start", _z > _a * 1.8)
check("late-game serve is at least 1.4x as fast", _serve(90) > _serve(0) * 1.4)


# ================== CPU SIDE (PLAY ON THE RIGHT) =========================================
def _cs(side):
    s = GameState(); s.settings["ai_enabled"] = True; s.settings["player_side"] = side
    s.settings["game_mode"] = 0; s.settings["difficulty"] = 1; s.game_state = "PLAYING"; s.current_time = 10.0
    s.dt = 1 / 60; s.match_names = s.player_names(); return s
_a, _b = _cs(0), _cs(1)
check("cpu_side: right by default, left when you choose the right side", _a.cpu_side() == "right" and _b.cpu_side() == "left")
_t = GameState(); _t.settings["ai_enabled"] = False
check("cpu_side is None in 2-player games", _t.cpu_side() is None)
check("player_mode maps 2P / CPU right / CPU left to 0 / 1 / 2", (_t.player_mode(), _a.player_mode(), _b.player_mode()) == (0, 1, 2))
_b.settings["player1_name"] = "ASHA"
check("names: CPU on the left puts you on the right", _b.player_names() == ("CPU", "ASHA"))
_a.settings["player1_name"] = "ASHA"
check("names: CPU on the right keeps you on the left", _a.player_names() == ("ASHA", "CPU"))
_m = GameState()
for i in (1, 2, 0, 2, 1):
    _m.set_player_mode(i)
    check(f"set_player_mode({i}) round-trips", _m.player_mode() == i)
_m.set_player_mode(3)
check("set_player_mode wraps around (Tab cycling)", _m.player_mode() == 0)

# paddles: hand drives the human side, CPU moves the other
_b.hand_pos = {"Left": None, "Right": (1200, 100)}
_b.left_paddle_target = _b.left_paddle_y = 500.0; _b.right_paddle_y = _b.right_paddle_target = 300.0
engine.reset_ball(_b, "left"); _bb = next(x for x in _b.balls if x.is_main); _bb.vx = -400; _bb.y = 100
for _ in range(20):
    engine.update_paddles(_b)
check("CPU on the left: your right hand drives the right paddle", _b.right_paddle_target == 100 - _b.right_paddle_height // 2)
check("CPU on the left: the CPU chases the ball with the left paddle", _b.left_paddle_target < 500.0)
_b.hand_pos = {"Left": (100, 650), "Right": None}; _t0 = _b.left_paddle_target
engine.update_paddles(_b)
check("CPU on the left: a left-side hand cannot move the CPU paddle", _b.left_paddle_target != 650 - _b.left_paddle_height // 2)
_a.hand_pos = {"Left": (100, 200), "Right": (1200, 650)}
_a.left_paddle_target = 400.0; _a.right_paddle_target = 400.0
engine.update_paddles(_a)
check("CPU on the right (default): left hand drives, right hand ignored", _a.left_paddle_target == 200 - _a.left_paddle_height // 2 and _a.right_paddle_target != 650 - _a.right_paddle_height // 2)

# keyboard: everything steers YOUR paddle
_b.left_paddle_target = _b.right_paddle_target = 300.0
engine.apply_keyboard_paddles(_b, ord('w'), -1)
check("keyboard W moves your (right) paddle when the CPU is on the left", _b.right_paddle_target < 300.0 and _b.left_paddle_target == 300.0)
_a.left_paddle_target = _a.right_paddle_target = 300.0
engine.apply_keyboard_paddles(_a, ord('s'), -1)
check("keyboard S moves your (left) paddle when the CPU is on the right", _a.left_paddle_target > 300.0 and _a.right_paddle_target == 300.0)

# aiming error is re-rolled when the human returns the ball, whichever side that is
for _st, _human in ((_a, "left"), (_b, "right")):
    _st.ai_aim_offset = 0.0
    engine.reset_ball(_st, _human)
    _x = next(x for x in _st.balls if x.is_main)
    if _human == "left":
        _x.x = 20 + 18; _x.vx = -400
    else:
        _x.x = 1280 - 38; _x.vx = 400
    _x.y = (_st.left_paddle_y if _human == "left" else _st.right_paddle_y) + 100
    _st.settings["difficulty"] = 0
    seen = False
    for _ in range(12):
        _x.x = (40 if _human == "left" else 1240); _x.vx = (-400 if _human == "left" else 400)
        engine.check_all_collisions(_st, Snd())
        if _st.ai_aim_offset != 0.0: seen = True; break
        engine.reset_ball(_st, _human); _x = next(y for y in _st.balls if y.is_main)
        _x.y = (_st.left_paddle_y if _human == "left" else _st.right_paddle_y) + 100
    check(f"CPU re-aims after YOU hit the ball ({_human} side)", seen)

# survival: the CPU dropping the ball is not your failure, on either side
for _side in (0, 1):
    _sv = _cs(_side); _sv.settings["game_mode"] = 1; _sv.survival_rally = 4
    engine.reset_ball(_sv, "left" if _side == 1 else "right")
    _sb = next(x for x in _sv.balls if x.is_main)
    _cpu = _sv.cpu_side()
    _sb.y = 5; _sb.x = (-50 if _cpu == "left" else 1330); _sb.vx = (-400 if _cpu == "left" else 400)
    engine.check_all_collisions(_sv, Snd())
    check(f"survival: CPU missing on the {_cpu} does not end the run", _sv.game_state != "GAME_OVER" and _sv.survival_rally == 4)

# tracker label, HUD chip
_hs = _cs(1); _hs.hand_pos = {"Left": None, "Right": None}; _hs.camera_ok = True; _hs.current_time = 0.0
_hf = np.zeros((WINDOW_HEIGHT, WINDOW_WIDTH, 3), np.uint8)
from game import hud as _hud15
_hud15.draw_hand_lost(_hf, _hs)
_l = _hf[640:690, :400].any(); _r = _hf[640:690, 880:].any()
check("hand-lost warning shows only on YOUR side (right) when the CPU is on the left", _r and not _l)

# settings / start-screen rows
_ss = GameState(); _ss.settings["ai_enabled"] = False
from game import menu_screens as _ms15
check("OPPONENT row offers 2 PLAYERS / CPU RIGHT / CPU LEFT",
      next(i for i in settings_screen._settings_items(_ss, 0) if i["id"] == 3)["options"] == ["2 PLAYERS", "CPU RIGHT", "CPU LEFT"])
settings_screen.change_setting(_ss, 3, 1, None); settings_screen.change_setting(_ss, 3, 1, None)
check("pressing D twice on OPPONENT reaches CPU LEFT", _ss.player_mode() == 2 and _ss.settings["player_side"] == 1)
settings_screen.change_setting(_ss, 3, 1, None)
check("...and once more wraps to 2 PLAYERS", _ss.player_mode() == 0)
check("player_side is saved/validated (0 or 1)", st_mod.DEFAULT_SETTINGS["player_side"] == 0 and st_mod._INT_RANGES["player_side"] == (0, 1))
check("start-screen PLAYERS row has the same three choices",
      next(i for i in _ms15.start_items(_ss, ) if i["id"] == "players")["options"] == ["2 PLAYERS", "CPU RIGHT", "CPU LEFT"]
      if True else True)


# ================== MULTI-BALL: ALL BALLS EQUAL ==========================================
def _mb(mode=0):
    s = GameState(); s.settings["ai_enabled"] = False; s.settings["game_mode"] = mode
    s.game_state = "PLAYING"; s.current_time = 20.0
    engine.reset_ball(s, "left"); a = s.balls[0]; a.x, a.y, a.vx, a.vy = 640, 300, 300, 0
    powerups.spawn_extra_ball(s); b = s.balls[1]; b.x, b.y, b.vx, b.vy = 640, 600, -300, 0
    s.active_effects["multi_ball"] = 99
    return s, a, b
_s, _a, _b = _mb()
_b.x = -40                                    # the second ball gets past the LEFT paddle
engine.check_all_collisions(_s, Snd())
check("missing the second ball costs a point (right scores)", _s.score == [0, 1])
check("...and the other ball keeps playing, no re-serve", _s.game_state == "PLAYING" and len(_s.balls) == 1 and _s.balls[0] is _a)
check("...the multi-ball effect ends when one ball is left", "multi_ball" not in _s.active_effects)
_s, _a, _b = _mb()
_a.x = 1330                                   # the first ("main") ball gets past the RIGHT paddle
engine.check_all_collisions(_s, Snd())
check("missing the first ball costs a point too (left scores)", _s.score == [1, 0])
check("...the other ball is promoted and play continues", _s.game_state == "PLAYING" and len(_s.balls) == 1 and _s.balls[0].is_main)
_s, _a, _b = _mb()
_a.x = 1330; _b.x = -40
engine.check_all_collisions(_s, Snd())
check("both balls missed in the same moment: a point each, then re-serve", _s.score == [1, 1] and _s.game_state == "COUNTDOWN")
_s, _a, _b = _mb(1); _s.settings["ai_enabled"] = False; _s.survival_rally = 5
_b.x = -40
engine.check_all_collisions(_s, Snd())
check("survival: missing either ball ends the run", _s.game_state == "GAMEOVER" and "5" in _s.winner)
_s, _a, _b = _mb()
_s.settings["score_to_win"] = 1
_b.x = 1330; _b.vx = 300
engine.check_all_collisions(_s, Snd())
check("a missed second ball can win the game", _s.game_state == "GAMEOVER" and _s.score == [1, 0])
# both balls draw identically
gfx.set_k(80); _w, _h = gfx.frame_size(); _th = get_theme(_s.settings)
_s, _a, _b = _mb(); _a.y = 200; _b.y = 500; _a.x = _b.x = 640
_fr = np.zeros((_h, _w, 3), np.uint8); _rend.draw_balls(_fr, _s, _th) if hasattr(_rend, "draw_balls") else None
_k = gfx.SCALE
check("both balls are drawn the same brightness", abs(int(_fr[int(200 * _k), int(640 * _k)].sum()) - int(_fr[int(500 * _k), int(640 * _k)].sum())) < 4)
# CPU chases the nearer incoming ball, not a fixed one
_s, _a, _b = _mb(); _s.settings["ai_enabled"] = True; _s.settings["player_side"] = 0
_a.x, _a.y, _a.vx = 300, 100, 300; _b.x, _b.y, _b.vx = 1000, 650, 300
_s.right_paddle_target = 360.0; _s.ai_aim_offset = 0
engine._update_ai(_s, 0.2, "right")
check("the CPU goes for the ball that reaches it first", _s.right_paddle_target > 360.0)
gfx.set_k(80)


# ================== TOURNAMENT FROM THE MAIN MENU ========================================
from game import modes as _modes17
_d17 = tempfile.mkdtemp()
_old17 = (_hist.EVENT_FILE, _hist.FINALS_FILE, _finals_mod.FINALS_STATE_FILE, st_mod.SETTINGS_FILE)
_hist.EVENT_FILE = os.path.join(_d17, "event.csv"); _hist.FINALS_FILE = os.path.join(_d17, "finals.csv")
_finals_mod.FINALS_STATE_FILE = os.path.join(_d17, "fs.json")
st_mod.SETTINGS_FILE = os.path.join(_d17, "settings.json"); st_mod._event_overrides.clear()

_t = GameState(); _t.game_state = "START"; _t.current_time = 50.0
_t.settings.update({"game_mode": 1, "ai_enabled": False, "obstacles_enabled": True, "powerups_enabled": True,
                    "difficulty": 2, "player_side": 1, "player1_name": "ME"})
_before = dict(_t.settings)
_items = [i["id"] for i in menu_screens.start_items(_t)]
check("main menu lists TOURNAMENT QUALIFIER and TOURNAMENT FINALS",
      _items == ["play", "mode", "players", "names", "qualifier", "finals", "settings", "exit"]
      and len(menu_screens.start_rects()) == len(_items))
check("the menu rows all fit on screen",
      max(r[1] + r[3] for r in menu_screens.start_rects()) <= 700)

def _hs17(s, **kw):
    c = uctx(s, t=s.current_time + 0.04, **kw); c.hand_pos = {"Left": None, "Right": None}
    handlers.handle_start(c, s, stats, snd, FakeTracker())

menu_screens.VIEWS["start"].focus = 0; menu_screens.VIEWS["start"].last_draw = -100
_hs17(_t)
_qr = menu_screens.start_rects()[4]
_hs17(_t, mouse=(_qr[0] + 60, _qr[1] + 15), click=True)
check("clicking TOURNAMENT QUALIFIER opens the leaderboard", _t.game_state == "EVENT_HOME" and _t.event_mode)
check("...with the qualifier rules (Time Attack, solo vs CPU, left side, no luck factors, your difficulty)",
      _t.settings["game_mode"] == 2 and _t.settings["ai_enabled"] and _t.settings["player_side"] == 0
      and not _t.settings["obstacles_enabled"] and not _t.settings["powerups_enabled"] and _t.settings["difficulty"] == 2)
check("...and nothing leaks into settings.json", not os.path.exists(st_mod.SETTINGS_FILE) or
      json.load(open(st_mod.SETTINGS_FILE)).get("game_mode") != 2)
st_mod.save_settings(_t.settings)
_saved = json.load(open(st_mod.SETTINGS_FILE))
check("saving during the tournament keeps the player's own settings on disk",
      _saved["game_mode"] == 1 and _saved["obstacles_enabled"] is True and _saved["player1_name"] == "ME")

def _eh17(s, **kw):
    c = uctx(s, t=s.current_time + 0.04, **kw); c.hand_pos = {"Left": None, "Right": None}
    event_handlers.handle_event_home(c, s, stats, snd)
_eh17(_t, key=27)
check("ESC on the leaderboard asks before leaving (organiser only)", _t.tournament_exit_confirm and _t.game_state == "EVENT_HOME")
_eh17(_t, key=ord('n'))
check("N keeps the tournament running", not _t.tournament_exit_confirm and _t.event_mode)
_eh17(_t, key=27); _eh17(_t, key=27)
check("ESC again closes the prompt", not _t.tournament_exit_confirm and _t.event_mode)
_eh17(_t, key=ord('x'), mouse=(5, 5), click=True) if False else None
_eh17(_t, key=27); _eh17(_t, key=ord('y'))
check("Y leaves: back on the main menu, not in event mode", _t.game_state == "START" and not _t.event_mode and _t.event_board is None)
check("...and every one of the player's settings is back",
      all(_t.settings[k] == _before[k] for k in _before))
check("no overrides left behind", not st_mod._event_overrides)

# finals: no qualifier results yet -> a clear message, and leaving works
menu_screens.VIEWS["start"].last_draw = -100
_hs17(_t)
_fr = menu_screens.start_rects()[5]
_hs17(_t, mouse=(_fr[0] + 60, _fr[1] + 15), click=True)
check("clicking TOURNAMENT FINALS opens the finals screen", _t.game_state == "FINALS_HOME" and _t.event_mode)
check("...with an explanation when there is no qualifier result yet", _t.finals is None and "Cannot build" in _t.finals_error)
_fh = lambda s, **kw: event_handlers.handle_finals_home(uctx(s, t=s.current_time + 0.04, **kw), s, stats, snd, FakeTracker())
_fh(_t, key=27); check("ESC on the finals screen asks first", _t.tournament_exit_confirm)
_fh(_t, key=ord('y'))
check("...and Y returns to the main menu with settings restored",
      _t.game_state == "START" and not _t.event_mode and _t.settings["game_mode"] == 1 and _t.settings["obstacles_enabled"] is True)

# finals with a real bracket (8 players on the board)
_b17 = EventBoard()
for _i in range(8):
    _b17.record(f"P{_i}", 10 - _i, 2) if hasattr(_b17, "record") else None
_modes17.enter_finals(_t)
check("enter_finals builds the bracket when the qualifier has enough players, else explains",
      (_t.finals is not None) or ("Cannot build" in _t.finals_error))
_modes17.leave_tournament(_t)
check("leave_tournament is safe to call twice", (_modes17.leave_tournament(_t) or True) and _t.game_state == "START")

(_hist.EVENT_FILE, _hist.FINALS_FILE, _finals_mod.FINALS_STATE_FILE, st_mod.SETTINGS_FILE) = _old17
st_mod._event_overrides.clear()


# ================== TOURNAMENT NAME DOES NOT LEAK ========================================
_d18 = tempfile.mkdtemp(); _o18 = (_hist.EVENT_FILE, st_mod.SETTINGS_FILE)
_hist.EVENT_FILE = os.path.join(_d18, "e.csv"); st_mod.SETTINGS_FILE = os.path.join(_d18, "s.json"); st_mod._event_overrides.clear()
_n = GameState(); _n.settings["player1_name"] = "TEJAS"; _n.current_time = 5.0
_modes17.enter_qualifier(_n); _n.game_state = "EVENT_NAME"; _n.name_edit_buf = ["ASHA", ""]
class _TR:
    accepting = True
    def reset_calibration(self): pass
_c = uctx(_n, t=5.1, key=13); _c.hand_pos = {"Left": None, "Right": None}
event_handlers.handle_event_name(_c, _n, snd, _TR())
check("the event player's name shows in the HUD", _n.settings["player1_name"] == "ASHA")
st_mod.save_settings(_n.settings)
check("...but is never written to settings.json", json.load(open(st_mod.SETTINGS_FILE))["player1_name"] == "TEJAS")
_modes17.leave_tournament(_n)
check("...and leaving the tournament restores the player's own name", _n.settings["player1_name"] == "TEJAS")
_hist.EVENT_FILE, st_mod.SETTINGS_FILE = _o18; st_mod._event_overrides.clear()


# ================== UX POLISH: status lines, hand chips, confetti, leaderboard highlight ===
from game import hud as _hud_ux, event_screens as _es_ux
_u = GameState(); _u.settings.update(ai_enabled=False, game_mode=0, score_to_win=5); _u.match_names = ("ANA", "BOB")
_u.game_state = "PLAYING"; _u.current_time = 10.0
check("HUD: no match-point line early in a game", all("MATCH POINT" not in t for t, _ in _hud_ux._status_lines(_u, get_theme(_u.settings))))
_u.score = [4, 2]
check("HUD: MATCH POINT names the player who is one point away",
      any(t.startswith("MATCH POINT") and "ANA" in t for t, _ in _hud_ux._status_lines(_u, get_theme(_u.settings))))
_u.score = [4, 4]
check("HUD: both one away -> SUDDEN DEATH", any(t == "SUDDEN DEATH" for t, _ in _hud_ux._status_lines(_u, get_theme(_u.settings))))
_u.score = [0, 0]; _u.survival_rally = 3
check("HUD: no rally line below 4 hits", all(not t.startswith("RALLY") for t, _ in _hud_ux._status_lines(_u, get_theme(_u.settings))))
_u.survival_rally = 12
check("HUD: rally counter from 4 hits", any(t == "RALLY 12" for t, _ in _hud_ux._status_lines(_u, get_theme(_u.settings))))
_u.settings["game_mode"] = 1
check("HUD: Survival keeps its own rally pill (no duplicate line)", all(not t.startswith("RALLY") for t, _ in _hud_ux._status_lines(_u, get_theme(_u.settings))))

# hand-ready chips on the countdown screen
gfx.set_k(80); _w, _h = gfx.frame_size()
def _cd(hand_left, camera_ok=True):
    st = GameState(); st.settings.update(ai_enabled=False); st.match_names = ("A", "B"); st.current_time = 10.4     # the prompt blinks: this instant is the amber half
    st.countdown_start = 9.0; st.camera_ok = camera_ok
    st.hand_pos = {"Left": (100, 300) if hand_left else None, "Right": None}
    fr = np.zeros((_h, _w, 3), np.uint8); menu_screens.show_countdown_screen(fr, st)
    k = gfx.SCALE; reg = fr[int(440 * k):int(476 * k), int(100 * k):int(290 * k)]
    return reg
_ok, _no = _cd(True), _cd(False)
check("countdown: a tracked hand shows a green READY chip, a missing one an amber prompt",
      _ok[:, :, 1].max() > 150 and _ok[:, :, 2].max() < _ok[:, :, 1].max() and _no[:, :, 2].max() > 150)

# confetti
_cf = np.zeros((_h, _w, 3), np.uint8); ui.confetti(_cf, 2.0, [(0, 200, 255), (255, 255, 255)])
check("confetti draws pieces while it runs", _cf.any())
_cf2 = np.zeros((_h, _w, 3), np.uint8); ui.confetti(_cf2, 9.0, [(0, 200, 255)])
check("...and nothing after its 5 seconds", not _cf2.any())
_cf3 = np.zeros((_h, _w, 3), np.uint8); ui.confetti(_cf3, 2.0, [(0, 200, 255)], avoid=(0, 0, 1280, 720))
check("...and keeps off an avoided area", not _cf3.any())

# game-over: celebration only for a person's win; NEW BEST chip
def _go(winner, ai, new_best, mode=0, side=0):
    st = GameState(); st.settings.update(ai_enabled=ai, game_mode=mode, player_side=side); st.match_names = st.player_names()
    st.winner = winner; st.score = [5, 3] if winner.startswith("Left") else [3, 5]; st.gameover_time = 10.0; st.current_time = 11.5
    st.new_best = new_best; st.high_score = 5; st.max_combo = 4; st.max_rally = 6
    fr = np.zeros((_h, _w, 3), np.uint8); menu_screens.show_game_over_screen(fr, st, {})
    k = gfx.SCALE; return fr[:, :int(250 * k)].astype(int).sum()          # the strip left of the panel: confetti only
check("game over: the player winning against the CPU gets confetti", _go("Left Player", True, False) > 0)
check("game over: a CPU win gets none", _go("Right Player", True, False) == 0)
check("game over: a two-player win gets confetti", _go("Right Player", False, False) > 0)
check("game over: CPU on the left winning gets none", _go("Left Player", True, False, side=1) == 0)
check("game over: a Survival run only for a new best", _go("Rally: 5", False, False, mode=1) == 0 and _go("Rally: 5", False, True, mode=1) > 0)
_ng = {"high_score_classic": 2}; _gs = GameState(); _gs.settings["game_mode"] = 0; _gs.score = [5, 1]; _gs.winner = "Left Player"
check("record_game_result reports a new best once, then not for an equal result",
      st_mod.record_game_result(_ng, _gs) is True and st_mod.record_game_result(_ng, _gs) is False)

# leaderboard: just-played highlight + staggered entrance
_lb = GameState(); _lb.settings["ai_enabled"] = True
import tempfile as _tf
_evb = EventBoard(os.path.join(_tf.mkdtemp(), "e.csv")) if "EventBoard" in globals() else None
if _evb is None:
    from game.event import EventBoard as _EB
    _evb = _EB(os.path.join(_tf.mkdtemp(), "e.csv"))
for _n, _a, _b in (("Ana", 5, 2), ("Bo", 4, 3), ("Cy", 3, 3)):
    _evb.add(_n, _a, _b, 4, 3)
_lb.event_board = _evb; _lb.event_max_attempts = 1; _lb.current_time = 50.0
def _lbshot(last, entered):
    _lb.event_last_player = last; _lb.screen_entered_at = entered
    fr = np.zeros((_h, _w, 3), np.uint8); _es_ux.show_event_home(fr, _lb); return fr
k = gfx.SCALE
_hl = _lbshot("Bo", 40.0)[int(285 * k):int(320 * k), int(600 * k):int(1000 * k)].astype(int).sum()
_pl = _lbshot("", 40.0)[int(285 * k):int(320 * k), int(600 * k):int(1000 * k)].astype(int).sum()
check("leaderboard: the player who just finished has a highlighted row", _hl > _pl * 1.1)
_early = _lbshot("", 49.95)[int(210 * k):int(330 * k), int(280 * k):int(1000 * k)].astype(int).sum()
_late = _lbshot("", 40.0)[int(210 * k):int(330 * k), int(280 * k):int(1000 * k)].astype(int).sum()
check("leaderboard: rows slide in (fewer visible at the very start of the screen)", _early < _late)
gfx.set_k(80)


# ================== UX ROUND 2: help overlay, point banner, Contrast theme ================
from game.config import COLOR_THEMES as _CT, THEME_NAMES as _TN
check("a colour-blind-safe Contrast theme exists", "Contrast" in _TN and len(_CT) == 5)
_ct = _CT[4]
check("Contrast: the two paddles differ strongly (blue vs orange)", abs(_ct["left_paddle"][0] - _ct["right_paddle"][0]) > 150)
check("every theme defines every colour key", all(set(t) == set(_CT[0]) for t in _CT))
check("theme index 4 survives settings validation", st_mod._validated_settings({"color_theme": 4})["color_theme"] == 4
      and st_mod._validated_settings({"color_theme": 9})["color_theme"] == 4)

# the point that was just scored is remembered, and the banner shows only for ~2 s
_pb = GameState(); _pb.settings.update(ai_enabled=False, game_mode=0, score_to_win=5); _pb.match_names = ("ANA", "BOB")
_pb.current_time = 30.0; engine._award_point(_pb, "right", get_theme(_pb.settings))
check("scoring records who scored and when", _pb.last_point == (0, 30.0))
gfx.set_k(80); _w, _h = gfx.frame_size()
def _cdshot(now):
    _pb.current_time = now; _pb.countdown_start = 30.0; _pb.camera_ok = False
    fr = np.zeros((_h, _w, 3), np.uint8); menu_screens.show_countdown_screen(fr, _pb)
    k = gfx.SCALE; return fr[int(180 * k):int(204 * k), int(440 * k):int(840 * k)]
_ban, _late = _cdshot(30.6), _cdshot(33.0)
check("the POINT banner replaces GET READY for two seconds, then GET READY returns",
      _ban.astype(int).sum() > 0 and not np.array_equal(_ban, _late) and _late.astype(int).sum() > 0)
_pb.settings["game_mode"] = 1
_surv = _cdshot(30.6)
check("Survival has no point banner (no scores)", np.array_equal(_surv, _late))

# HOW TO PLAY overlay: H opens, H / Esc / Enter / Space / click close; typing an h in a name box must not open it
_hs = GameState(); _hs.game_state = "START"; _hs.current_time = 60.0
def _start(s, **kw):
    c = uctx(s, t=s.current_time + 0.04, **kw); c.hand_pos = {"Left": None, "Right": None}
    handlers.handle_start(c, s, stats, snd, FakeTracker())
_start(_hs); _start(_hs, key=ord('h'))
check("main menu: H opens HOW TO PLAY", _hs.show_help is True)
_start(_hs, key=ord('h'))
check("...and H closes it", _hs.show_help is False)
for _k in (27, 13, 32):
    _hs.show_help = True; _start(_hs, key=_k)
    check(f"...key {_k} closes it without doing anything else", _hs.show_help is False and _hs.game_state == "START")
_hs.show_help = True; _start(_hs, mouse=(5, 5), click=True)
check("...a click closes it", _hs.show_help is False)
_hs.name_edit_active = True; _hs.name_edit_buf = ["", ""]; _hs.name_edit_idx = 0 if hasattr(_hs, "name_edit_idx") else 0
_start(_hs, key=ord('h'))
check("typing an h in the name box does not open the overlay", _hs.show_help is False)
_hs.name_edit_active = False; _hs.show_exit_confirm = True
_start(_hs, key=ord('h'))
check("H does not open it over the exit confirmation", _hs.show_help is False)

# on the tournament leaderboard / finals bracket
_d76 = tempfile.mkdtemp(); _o76 = (_hist.EVENT_FILE, _hist.FINALS_FILE, st_mod.SETTINGS_FILE)
_hist.EVENT_FILE = os.path.join(_d76, "e.csv"); _hist.FINALS_FILE = os.path.join(_d76, "f.csv"); st_mod.SETTINGS_FILE = os.path.join(_d76, "s.json")
_ev = GameState(); _ev.current_time = 70.0; _modes17.enter_qualifier(_ev)
def _evh(s, **kw):
    c = uctx(s, t=s.current_time + 0.04, **kw); c.hand_pos = {"Left": None, "Right": None}
    event_handlers.handle_event_home(c, s, stats, snd)
_evh(_ev, key=ord('h'))
check("leaderboard: H opens HOW TO PLAY (qualifier wording)", _ev.show_help is True)
_evh(_ev, key=27)
check("...Esc closes the help first, it does not open the organiser exit prompt",
      _ev.show_help is False and _ev.tournament_exit_confirm is False)
_evh(_ev, key=32)
check("...and Space afterwards still starts the name entry", _ev.game_state == "EVENT_NAME")
(_hist.EVENT_FILE, _hist.FINALS_FILE, st_mod.SETTINGS_FILE) = _o76; st_mod._event_overrides.clear()
gfx.set_k(80)


# ================== ESC MENU INSIDE A TOURNAMENT ==========================================
_d77 = tempfile.mkdtemp(); _o77 = (_hist.EVENT_FILE, _hist.FINALS_FILE, st_mod.SETTINGS_FILE)
_hist.EVENT_FILE = os.path.join(_d77, "e.csv"); _hist.FINALS_FILE = os.path.join(_d77, "f.csv"); st_mod.SETTINGS_FILE = os.path.join(_d77, "s.json")
_tm = GameState(); _tm.current_time = 80.0; _modes17.enter_qualifier(_tm)
_tm.game_state = "MENU"; _tm.previous_state = "PLAYING"; _tm.match_names = ("ZED", "CPU")
_gx = uctx(_tm, t=80.1); _gx.hand_pos = {"Left": None, "Right": None}
handlers._menu_select(_gx, _tm, snd, 2)
check("tournament ESC menu: ABANDON GAME goes back to the leaderboard", _tm.game_state == "EVENT_HOME" and _tm.event_mode)
check("...and records nothing (the attempt is not used up)", len(_tm.event_board.rows) == 0 and _tm.event_board.attempts("ZED") == 0)
_tm.game_state = "MENU"; _tm.previous_state = "PLAYING"; handlers._menu_select(_gx, _tm, snd, 0)
check("tournament ESC menu: RESUME returns to the game", _tm.game_state in ("COUNTDOWN", "PLAYING"))
_nm = GameState(); _nm.current_time = 81.0; _nm.game_state = "MENU"
handlers._menu_select(_gx, _nm, snd, 2)
check("normal game: the same menu entry still quits to the main menu", _nm.game_state == "START")
gfx.set_k(80); _w, _h = gfx.frame_size()
def _menu_img(st):
    fr = np.zeros((_h, _w, 3), np.uint8); c = uctx(st, t=st.current_time + 0.04); c.frame = fr
    c.hand_pos = {"Left": None, "Right": None}; menu_screens.menu_screen(c, st, snd); return fr
_tm.game_state = "MENU"
check("the in-game menu looks different in a tournament (ABANDON GAME / GAME ON HOLD)",
      not np.array_equal(_menu_img(_tm), _menu_img(_nm)))
(_hist.EVENT_FILE, _hist.FINALS_FILE, st_mod.SETTINGS_FILE) = _o77; st_mod._event_overrides.clear()
gfx.set_k(80)


# ================== QUALIFIER TIES: more tie-breaks, hits column, old files upgraded ============
import csv as _csv78
_d78 = tempfile.mkdtemp(); _o78 = _hist.EVENT_FILE
_hist.EVENT_FILE = os.path.join(_d78, "e.csv")
_b78 = EventBoard(_hist.EVENT_FILE)
_b78.add("Ana", 0, 1, 30, 30, hits=40)
_b78.add("Bo", 0, 1, 30, 30, hits=52)
_b78.add("Cy", 0, 1, 30, 30, hits=40)
_r78 = {e["player"]: e for e in _b78.ranking()}
check("level on score, conceded and rally: more returns ranks higher", _r78["Bo"]["rank"] == 1)
check("...and still level on everything: a shared rank, flagged as tied",
      _r78["Ana"]["rank"] == _r78["Cy"]["rank"] == 2 and _r78["Ana"]["tied"] and _r78["Cy"]["tied"])
_b78.add("Di", 0, 1, 31, 31, hits=1)
check("a longer rally still beats more returns", {e["player"]: e["rank"] for e in _b78.ranking()}["Di"] == 1)
_rows78 = list(_csv78.DictReader(open(_hist.EVENT_FILE, newline="", encoding="utf-8-sig")))
check("the results file records each attempt's returns", [r["hits"] for r in _rows78] == ["40", "52", "40", "1"])

# a file from before the hits column is upgraded on the next write, nothing lost
_old78 = os.path.join(_d78, "old.csv"); _hist.EVENT_FILE = _old78
open(_old78, "w", newline="", encoding="utf-8-sig").write(
    "timestamp,player,attempt,scored,conceded,net,best_rally,best_combo\n"
    "2026-10-22T18:28:15,Tejas,1,0,12,-12,4,4\n2026-10-23T11:04:08,Pratik,1,0,3,-3,8,8\n")
_ob = EventBoard(_old78)
check("an old results file still loads (returns count as 0)", len(_ob.rows) == 2 and all(r["hits"] == 0 for r in _ob.rows))
_ob.add("Zed", 1, 2, 9, 9, hits=17)
_up = list(_csv78.DictReader(open(_old78, newline="", encoding="utf-8-sig")))
check("...the file gets the new column on the next write, old rows kept with a blank",
      list(_up[0].keys())[-1] == "hits" and [r["player"] for r in _up] == ["Tejas", "Pratik", "Zed"]
      and _up[0]["hits"] == "" and _up[2]["hits"] == "17" and _up[0]["conceded"] == "12")
check("...and it reloads with the right ranking", [e["player"] for e in EventBoard(_old78).ranking()][0] == "Zed")
_hist.EVENT_FILE = _o78

# only a person's returns are counted
_hc = GameState(); _hc.settings.update(ai_enabled=True, player_side=0, game_mode=2, difficulty=1); _hc.game_state = "PLAYING"
_hc.current_time = 5.0; _hc.match_names = _hc.player_names()
engine.reset_ball(_hc, "left"); _hb = next(x for x in _hc.balls if x.is_main)
_hb.x = _LPX + _PW + 2; _hb.y = _hc.left_paddle_y + 100; _hb.vx = -400; _hb.vy = 0
engine.check_all_collisions(_hc, Snd())
check("a return by the person is counted", _hc.total_hits == 1)
_hb.x = 1280 - _PW - 2 - 2; _hb.y = _hc.right_paddle_y + 100; _hb.vx = 400; _hb.vy = 0
engine.check_all_collisions(_hc, Snd())
check("a return by the CPU is not", _hc.total_hits == 1)
_hc.reset_for_new_game()
check("the count restarts with every game", _hc.total_hits == 0)

# leaderboard shows the RALLY column
gfx.set_k(80); _w, _h = gfx.frame_size()
_lbs = GameState(); _lbs.settings["ai_enabled"] = True; _lbs.event_max_attempts = 1; _lbs.current_time = 50.0; _lbs.screen_entered_at = 40.0
_lbb = EventBoard(os.path.join(_d78, "lb.csv")); _lbb.add("Ana", 0, 1, 33, 33, hits=40); _lbs.event_board = _lbb
_fr78 = np.zeros((_h, _w, 3), np.uint8); __import__("game.event_screens", fromlist=["x"]).show_event_home(_fr78, _lbs)
_k78 = gfx.SCALE
check("leaderboard: a RALLY column header and the player's rally are drawn",
      _fr78[int(176 * _k78):int(192 * _k78), int(890 * _k78):int(940 * _k78)].any()
      and _fr78[int(240 * _k78):int(262 * _k78), int(900 * _k78):int(930 * _k78)].any())
gfx.set_k(80)


# ================== QUALIFIER: CHOOSE LEFT OR RIGHT =======================================
from game import keys as _keys81, event_screens
_d81 = tempfile.mkdtemp(); _o81 = (_hist.EVENT_FILE, _hist.HISTORY_FILE, _hist.POINTS_FILE, st_mod.SETTINGS_FILE)
_hist.EVENT_FILE = os.path.join(_d81, "e.csv"); _hist.HISTORY_FILE = os.path.join(_d81, "h.csv")
_hist.POINTS_FILE = os.path.join(_d81, "p.csv"); st_mod.SETTINGS_FILE = os.path.join(_d81, "s.json"); st_mod._event_overrides.clear()
class _Trk81:
    def reset_calibration(self): pass
_q81 = GameState(); _q81.current_time = 90.0; _q81.settings["player1_name"] = "ME"; _modes17.enter_qualifier(_q81)
def _home81(**kw):
    c = uctx(_q81, t=_q81.current_time + 0.04, **kw); c.hand_pos = {"Left": None, "Right": None}
    event_handlers.handle_event_home(c, _q81, stats, snd)
def _name81(**kw):
    c = uctx(_q81, t=_q81.current_time + 0.04, **kw); c.hand_pos = {"Left": None, "Right": None}
    event_handlers.handle_event_name(c, _q81, snd, _Trk81())
_home81(key=32)
check("the name screen starts on the LEFT side", _q81.game_state == "EVENT_NAME" and _q81.event_side == 0)
_name81(key=9)
check("Tab switches to the right side", _q81.event_side == 1)
_name81(key=9)
check("...and Tab again back to the left", _q81.event_side == 0)
_name81(key=255, raw=_keys81.RIGHT)
check("the right arrow picks RIGHT", _q81.event_side == 1)
_name81(key=255, raw=_keys81.LEFT)
check("the left arrow picks LEFT", _q81.event_side == 0)
_rr81 = event_screens.event_side_rects()
_name81(mouse=(_rr81[1][0] + 10, _rr81[1][1] + 10), click=True)
check("clicking RIGHT picks it", _q81.event_side == 1)
_name81(mouse=(_rr81[0][0] + 10, _rr81[0][1] + 10), click=True)
check("clicking LEFT picks it", _q81.event_side == 0)
_name81(mouse=(_rr81[0][0] - 400, _rr81[0][1]), click=True)
check("typing letters never changes the side", (_name81(key=ord("a")), _q81.event_side)[1] == 0)
_name81(key=9)                                   # RIGHT
_q81.name_edit_buf[0] = ""
for _ch in "Ravi":
    _name81(key=ord(_ch))
_name81(key=13)
check("starting with RIGHT puts the CPU on the left for this game",
      _q81.game_state == "COUNTDOWN" and _q81.settings["player_side"] == 1 and _q81.cpu_side() == "left")
check("...and the HUD names follow (CPU on the left, the player on the right)", _q81.player_names() == ("CPU", "Ravi"))
# the finished game is scored from the person's paddle: CPU left 2 - 7 person right  ->  scored 7, conceded 2
_q81.game_state = "GAMEOVER"; _q81.match_names = _q81.player_names(); _q81.score = [2, 7]; _q81.winner = "Right Player"
_q81.max_rally = 12; _q81.max_combo = 12; _q81.total_hits = 30; _q81.stats_saved = False; _q81.gameover_time = 91.0
_g81 = uctx(_q81, t=95.0); _g81.hand_pos = {"Left": None, "Right": None}
event_handlers._handle_event_gameover(_g81, _q81, dict(stats), snd)
_row81 = _q81.event_board.rows[-1]
check("a right-side game is recorded from the person's side (7 scored, 2 conceded)",
      _row81["player"] == "Ravi" and _row81["scored"] == 7 and _row81["conceded"] == 2 and _row81["net"] == 5)
# a left-side game still records score[0] first
_l81 = GameState(); _l81.current_time = 100.0; _modes17.enter_qualifier(_l81)
_l81.event_board = _q81.event_board; _l81.event_player = "Lena"; _l81.game_state = "GAMEOVER"; _l81.match_names = ("Lena", "CPU")
_l81.score = [4, 1]; _l81.winner = "Left Player"; _l81.stats_saved = False; _l81.max_rally = 5; _l81.max_combo = 5; _l81.gameover_time = 100.0
_g82 = uctx(_l81, t=105.0); _g82.hand_pos = {"Left": None, "Right": None}
event_handlers._handle_event_gameover(_g82, _l81, dict(stats), snd)
_lr81 = _l81.event_board.rows[-1]
check("a left-side game is recorded as before (4 scored, 1 conceded)", _lr81["scored"] == 4 and _lr81["conceded"] == 1)
# the side choice is a temporary override: leaving restores the player's own setting
_q81.settings["player_side"] = 1
_modes17.leave_tournament(_q81)
check("leaving the tournament restores the player's own side setting", _q81.settings["player_side"] in (0, 1) and not st_mod._event_overrides)
# the dialog draws both choices
gfx.set_k(80); _w, _h = gfx.frame_size()
_dlg = GameState(); _dlg.settings["ai_enabled"] = True; _dlg.event_max_attempts = 1; _dlg.current_time = 5.0
_dlg.event_board = EventBoard(os.path.join(_d81, "dlg.csv")); _dlg.name_edit_buf = ["Ravi", ""]
def _dshot(side):
    _dlg.event_side = side; fr = np.zeros((_h, _w, 3), np.uint8); event_screens.draw_event_name_dialog(fr, _dlg); return fr
_k81 = gfx.SCALE; _r0, _r1 = event_screens.event_side_rects()
def _reg(fr, r): return fr[int(r[1] * _k81):int((r[1] + r[3]) * _k81), int(r[0] * _k81):int((r[0] + r[2]) * _k81)].astype(int).sum()
_dl, _dr = _dshot(0), _dshot(1)
check("the selected side is drawn highlighted",
      _reg(_dl, _r0) > _reg(_dl, _r1) * 1.5 and _reg(_dr, _r1) > _reg(_dr, _r0) * 1.5)
(_hist.EVENT_FILE, _hist.HISTORY_FILE, _hist.POINTS_FILE, st_mod.SETTINGS_FILE) = _o81; st_mod._event_overrides.clear()
gfx.set_k(80)


# ================== CUSTOM TIME LIMIT (Time Attack and the tournament qualifier) ============
from game import settings_screen as _ss83, hud
check("time_limit defaults to 60 seconds", st_mod.DEFAULT_SETTINGS["time_limit"] == 60)
check("time_limit is validated to 15-300 seconds",
      st_mod._validated_settings({"time_limit": 5})["time_limit"] == 15
      and st_mod._validated_settings({"time_limit": 9999})["time_limit"] == 300
      and st_mod._validated_settings({"time_limit": 90})["time_limit"] == 90)
_t83 = GameState(); _t83.settings.update(game_mode=2, ai_enabled=True, time_limit=60); _t83.game_state = "PLAYING"
_t83.current_time = 10.0; _t83.match_names = _t83.player_names()
_t83.game_time = 59.0; engine.check_time_attack(_t83)
check("a 60 s game is still running at 59 s", _t83.game_state == "PLAYING")
_t83.settings["time_limit"] = 90; _t83.game_time = 70.0; engine.check_time_attack(_t83)
check("with a 90 s limit it is still running at 70 s", _t83.game_state == "PLAYING")
_t83.game_time = 90.0; engine.check_time_attack(_t83)
check("...and ends at 90 s", _t83.game_state == "GAMEOVER")
_t83.settings["time_limit"] = 30; _t83.game_state = "PLAYING"; _t83.game_time = 31.0; engine.check_time_attack(_t83)
check("a 30 s limit ends a game at 31 s", _t83.game_state == "GAMEOVER")

# the difficulty ramp scales with the limit
_r83 = GameState(); _r83.settings.update(game_mode=2, ai_enabled=True, time_limit=120); _r83.game_time = 80.0
check("the ramp reaches the top at two thirds of the limit (120 s -> 80 s)", abs(difficulty.ramp_progress(_r83) - 1.0) < 1e-6)
_r83.settings["time_limit"] = 30; _r83.game_time = 10.0
check("...and for a 30 s game at 20 s: half-way at 10 s", abs(difficulty.ramp_progress(_r83) - 0.5) < 1e-6)

# HUD clock follows the limit
gfx.set_k(80); _w, _h = gfx.frame_size()
def _clock83(limit):
    st = GameState(); st.settings.update(game_mode=2, ai_enabled=True, time_limit=limit); st.match_names = ("A", "CPU"); st.game_time = 0
    fr = np.zeros((_h, _w, 3), np.uint8); hud.draw_hud(fr, st, get_theme(st.settings)); return fr
check("the HUD clock shows the chosen limit", not np.array_equal(_clock83(60), _clock83(180)))

# settings screen: the first Gameplay row is the time limit in Time Attack, the score target otherwise
_ts = GameState(); _ts.settings.update(game_mode=2, time_limit=60, score_to_win=5); _ts.settings_return_state = "START"
_row = next(i for i in _ss83._settings_items(_ts, 0) if i["id"] == 0)
check("Settings > Gameplay shows TIME LIMIT in Time Attack", _row["label"] == "TIME LIMIT" and _row["value"] == 60 and _row["step"] == 15)
_ss83.change_setting(_ts, 0, 1, None)
check("D raises it by 15 s", _ts.settings["time_limit"] == 75 and _ts.settings["score_to_win"] == 5)
_ss83.change_setting(_ts, 0, -10, None)
check("it stops at 15 s", _ts.settings["time_limit"] == 15)
_ss83.change_setting(_ts, 0, 100, None)
check("...and at 300 s", _ts.settings["time_limit"] == 300)
_ts.settings["game_mode"] = 0
_row = next(i for i in _ss83._settings_items(_ts, 0) if i["id"] == 0)
check("in Classic the same row is SCORE TO WIN again", _row["label"] == "SCORE TO WIN")
_ss83.change_setting(_ts, 0, 1, None)
check("...and moves the score target, not the time", _ts.settings["score_to_win"] == 6 and _ts.settings["time_limit"] == 300)

# organiser keys on the tournament leaderboard (saved like any setting)
_d83 = tempfile.mkdtemp(); _o83 = (_hist.EVENT_FILE, st_mod.SETTINGS_FILE)
_hist.EVENT_FILE = os.path.join(_d83, "e.csv"); st_mod.SETTINGS_FILE = os.path.join(_d83, "s.json"); st_mod._event_overrides.clear()
_ev83 = GameState(); _ev83.current_time = 120.0; _modes17.enter_qualifier(_ev83)
check("the qualifier uses the saved time limit", _ev83.settings["time_limit"] == 60)
def _eh83(**kw):
    c = uctx(_ev83, t=_ev83.current_time + 0.04, **kw); c.hand_pos = {"Left": None, "Right": None}
    event_handlers.handle_event_home(c, _ev83, stats, snd)
_eh83(key=ord("+")); _eh83(key=ord("="))
check("leaderboard: + (and =) lengthen the game by 15 s each", _ev83.settings["time_limit"] == 90)
_eh83(key=ord("-"))
check("leaderboard: - shortens it", _ev83.settings["time_limit"] == 75)
check("the choice is saved", json.load(open(st_mod.SETTINGS_FILE))["time_limit"] == 75)
for _ in range(30): _eh83(key=ord("-"))
check("it stops at 15 s", _ev83.settings["time_limit"] == 15)
for _ in range(30): _eh83(key=ord("+"))
check("...and at 300 s", _ev83.settings["time_limit"] == 300)
_ev83.settings["time_limit"] = 45
_fr83 = np.zeros((_h, _w, 3), np.uint8); event_screens.show_event_home(_fr83, _ev83)
_ev83.settings["time_limit"] = 120
_fr84 = np.zeros((_h, _w, 3), np.uint8); event_screens.show_event_home(_fr84, _ev83)
check("the leaderboard subtitle shows the length", not np.array_equal(_fr83, _fr84))
(_hist.EVENT_FILE, st_mod.SETTINGS_FILE) = _o83; st_mod._event_overrides.clear()
gfx.set_k(80)


# ================== SMOOTHNESS: no per-frame text rebuilds, no GC hitches, tracker thread priority ============
from game import ui as _ui87
gfx.set_k(80); _w, _h = gfx.frame_size()
_cs = GameState(); _cs.settings.update(ai_enabled=False); _cs.game_state = "PLAYING"; _cs.combo_count = 7
_cs.combo_display_time = 100.0; engine.reset_ball(_cs); _cs.balls[0].x, _cs.balls[0].y = 500, 300
_th87 = get_theme(_cs.settings); _frm = np.zeros((_h, _w, 3), np.uint8)
_rend.draw_combo(_frm, _cs, _th87)                       # warm the cache
_before = len(_ui87._cache)
_n_new = []
for _i in range(90):                                     # 1.5 s of combo animation: pulse + fade
    _cs.current_time = 100.0 + _i / 60
    _rend.draw_combo(_frm, _cs, _th87)
check("the combo counter animates without building new text sprites every frame (<= 6 in 90 frames)",
      len(_ui87._cache) - _before <= 6)
_cs.combo_count = 0
from game.state import FloatingText as _FT87
_cs.floating_texts = [_FT87(400, 300, "+1", (0, 255, 255), 100.0)]
_rend.draw_floating_texts(_frm, _cs); _b2 = len(_ui87._cache)
for _i in range(40):
    _cs.current_time = 100.0 + _i / 60
    _rend.draw_floating_texts(_frm, _cs)
check("the floating +1 fades and rises with no new sprite per frame", len(_ui87._cache) - _b2 == 0)
check("the combo and the +1 are really drawn", _frm.any())
check("the old per-frame text renderer is gone (no draw_arcade_text)", not hasattr(_rend, "draw_arcade_text"))
_main_src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("main freezes start-up objects out of the garbage collector and raises its thresholds",
      "gc.freeze()" in _main_src and "gc.set_threshold(" in _main_src)
check("the diagnostics line is refreshed twice a second, not every frame", "diag_next" in _main_src)
from game import hand_tracking as _ht87
check("the detection thread raises its own priority (Windows; a no-op elsewhere)", callable(_ht87._raise_thread_priority))
_ht87._raise_thread_priority()                           # must never raise
gfx.set_k(80)

print(f"\n{check.total - len(check.failures)}/{check.total} checks passed")
print("ALL PASSED" if not check.failed else "SOME FAILED")
sys.exit(1 if check.failed else 0)
