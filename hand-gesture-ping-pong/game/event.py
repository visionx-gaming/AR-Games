"""Event (tournament) mode: attempts, results and the leaderboard.

Every finished qualifier attempt is appended to event_results.csv (one row per
attempt), so the standings survive a restart and can be checked or corrected in
Excel.  The leaderboard ranks each player by their BEST attempt:

    1. higher net score (points scored minus points conceded)
    2. fewer points conceded
    3. longer best rally
    (still equal  ->  same rank; settle it with a sudden-death game)
"""

import csv
import os

from game import history


def name_key(name):
    """Identity of a player: case and extra spaces don't matter."""
    return " ".join(str(name).casefold().split())


class EventBoard:
    def __init__(self, path=None):
        self.path = path or history.EVENT_FILE
        self.rows = []              # one dict per attempt, in the order played
        self._display = {}          # name key -> name as first typed
        self._load()

    # ---- persistence -----------------------------------------------------

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    try:
                        self._ingest({
                            "player": r["player"],
                            "attempt": int(r["attempt"]),
                            "scored": int(r["scored"]),
                            "conceded": int(r["conceded"]),
                            "rally": int(r["best_rally"]),
                            "combo": int(r["best_combo"]),
                        })
                    except (KeyError, ValueError, TypeError):
                        continue            # skip a damaged / hand-edited row
        except OSError as e:
            print(f"WARNING: could not read {self.path}: {e}")

    def _ingest(self, row):
        key = name_key(row["player"])
        if not key:
            return None
        self._display.setdefault(key, row["player"])
        row["key"] = key
        row["net"] = row["scored"] - row["conceded"]
        self.rows.append(row)
        return row

    # ---- queries -----------------------------------------------------------

    def attempts(self, name):
        key = name_key(name)
        return sum(1 for r in self.rows if r["key"] == key)

    def display_name(self, name):
        """The spelling this player first used (keeps the board tidy if they
        come back as 'rahul s' after being 'Rahul S')."""
        return self._display.get(name_key(name), name)

    def ranking(self):
        """Players ranked by best attempt.  Equal players share a rank."""
        best = {}
        for r in self.rows:
            k = r["key"]
            score = (r["net"], -r["conceded"], r["rally"])
            if k not in best or score > best[k]["score"]:
                best[k] = {"score": score, "row": r}
        order = sorted(best.values(), key=lambda b: b["score"], reverse=True)
        out, last, rank = [], None, 0
        for i, b in enumerate(order, start=1):
            if b["score"] != last:
                rank, last = i, b["score"]
            r = b["row"]
            out.append({
                "rank": rank, "player": self._display[r["key"]], "key": r["key"],
                "net": r["net"], "scored": r["scored"], "conceded": r["conceded"],
                "rally": r["rally"], "attempts": self.attempts(r["key"]),
            })
        for e in out:
            e["tied"] = sum(1 for o in out if o["rank"] == e["rank"]) > 1
        return out

    def rank_of(self, name):
        key = name_key(name)
        for e in self.ranking():
            if e["key"] == key:
                return e["rank"]
        return None

    def best_of(self, name):
        key = name_key(name)
        mine = [r for r in self.rows if r["key"] == key]
        return max(mine, key=lambda r: (r["net"], -r["conceded"], r["rally"])) if mine else None

    # ---- recording -----------------------------------------------------------

    def add(self, name, scored, conceded, best_rally, best_combo):
        """Record a finished attempt. Returns a summary for the result screen."""
        name = self.display_name(name)
        prev_best = self.best_of(name)
        row = self._ingest({"player": name, "attempt": self.attempts(name) + 1,
                            "scored": scored, "conceded": conceded,
                            "rally": best_rally, "combo": best_combo})
        history.record_event_attempt(row)
        new_best = self.best_of(name)
        me = next(e for e in self.ranking() if e["key"] == row["key"])
        return {
            "player": name,
            "attempt": row["attempt"],
            "scored": scored,
            "conceded": conceded,
            "net": row["net"],
            "rank": me["rank"],
            "tied": me["tied"],
            "players": len(self.ranking()),
            "is_best": new_best is row,
            "prev_best_net": prev_best["net"] if prev_best else None,
        }
