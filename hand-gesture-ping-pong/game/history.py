"""Game history: every finished game is appended to CSV files.

  game_history.csv   one row per game  (players, final scores, winner, mode, ...)
  point_log.csv      one row per point (who scored, running score, game time)

Both open directly in Excel / Google Sheets.  A game's rows are tied together
by `game_id`.  If a file can't be written (typically because it is open in
Excel, which locks it on Windows) the rows are kept in memory and written with
the next game instead of being lost.
"""

import csv
import os
from datetime import datetime

from game.config import DIFFICULTY_NAMES, GAME_MODE_NAMES

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(_PROJECT_ROOT, "game_history.csv")
POINTS_FILE = os.path.join(_PROJECT_ROOT, "point_log.csv")
EVENT_FILE = os.path.join(_PROJECT_ROOT, "event_results.csv")
FINALS_FILE = os.path.join(_PROJECT_ROOT, "finals_results.csv")

GAME_FIELDS = [
    "game_id", "ended_at", "mode", "difficulty", "opponent",
    "player1", "player2", "score1", "score2", "winner",
    "score_to_win", "duration_s", "best_combo", "best_rally",
]
EVENT_FIELDS = [
    "timestamp", "player", "attempt", "scored", "conceded", "net", "best_rally", "best_combo",
]
FINALS_FIELDS = [
    "timestamp", "match", "player1", "player2", "score1", "score2", "winner", "note",
]
POINT_FIELDS = [
    "game_id", "point_no", "game_time_s", "scored_by",
    "player1", "player2", "score1", "score2",
]

# (path attribute name, fields, rows) not yet written to disk
_pending = []
_warned = False


def _safe(value):
    """Stop a name like '=SUM(A1)' from being run as a formula when the CSV is
    opened in a spreadsheet."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _append(path, fields, rows):
    """Append rows to a CSV, writing the header (and a BOM, so Excel reads it
    as UTF-8) when the file is new.  Returns True on success."""
    global _warned
    try:
        is_new = not os.path.exists(path) or os.path.getsize(path) == 0
        with open(path, "a", newline="", encoding="utf-8-sig" if is_new else "utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            if is_new:
                w.writeheader()
            w.writerows(rows)
        return True
    except OSError as e:
        if not _warned:
            _warned = True
            print(f"WARNING: could not write {os.path.basename(path)} ({e}). "
                  "Close it if it's open in Excel; scores will be saved with the next game.")
        return False


def flush():
    """Try to write everything still pending."""
    global _warned
    still = []
    for which, fields, rows in _pending:
        path = {"history": HISTORY_FILE, "points": POINTS_FILE, "event": EVENT_FILE,
                "finals": FINALS_FILE}[which]
        if not _append(path, fields, rows):
            still.append((which, fields, rows))
    _pending[:] = still
    if not still:
        _warned = False


def _winner_name(state, names):
    w = state.winner
    if w.startswith("Left"):
        return names[0]
    if w.startswith("Right"):
        return names[1]
    return "Draw" if w == "Draw" else ""        # Survival has no winner


def record_game(state):
    """Queue and write the finished game described by `state`."""
    names = state.match_names
    mode = state.settings["game_mode"]
    game_id = state.match_started

    game_row = {
        "game_id": game_id,
        "ended_at": datetime.now().isoformat(timespec="seconds"),
        "mode": GAME_MODE_NAMES[mode],
        "difficulty": DIFFICULTY_NAMES[state.settings["difficulty"]],
        "opponent": "AI" if state.settings["ai_enabled"] else "2 Player",
        "player1": names[0],
        "player2": names[1],
        "score1": state.score[0],
        "score2": state.score[1],
        "winner": _winner_name(state, names),
        "score_to_win": state.settings["score_to_win"] if mode == 0 else "",
        "duration_s": round(state.game_time, 1),
        "best_combo": state.max_combo,
        "best_rally": state.max_rally,
    }
    point_rows = [{
        "game_id": game_id,
        "point_no": i,
        "game_time_s": t,
        "scored_by": names[scorer],
        "player1": names[0],
        "player2": names[1],
        "score1": s1,
        "score2": s2,
    } for i, (t, scorer, s1, s2) in enumerate(state.point_log, start=1)]

    _pending.append(("history", GAME_FIELDS, [{k: _safe(v) for k, v in game_row.items()}]))
    if point_rows:
        _pending.append(("points", POINT_FIELDS,
                         [{k: _safe(v) for k, v in r.items()} for r in point_rows]))
    flush()


def record_event_attempt(row):
    """Append one qualifier attempt (see game/event.py) to event_results.csv."""
    out = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "player": row["player"],
        "attempt": row["attempt"],
        "scored": row["scored"],
        "conceded": row["conceded"],
        "net": row["net"],
        "best_rally": row["rally"],
        "best_combo": row["combo"],
    }
    _pending.append(("event", EVENT_FIELDS, [{k: _safe(v) for k, v in out.items()}]))
    flush()


def record_finals_match(res):
    """Append one finished finals match (see game/finals.py) to finals_results.csv."""
    out = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "match": res["label"],
        "player1": res["p1"],
        "player2": res["p2"],
        "score1": res["s1"],
        "score2": res["s2"],
        "winner": res["winner"],
        "note": res.get("note", ""),
    }
    _pending.append(("finals", FINALS_FIELDS, [{k: _safe(v) for k, v in out.items()}]))
    flush()
