"""Finals: a top-4 knockout bracket seeded from the qualifier leaderboard.

    SF1 : seed 1 v seed 4        THIRD : loser SF1 v loser SF2
    SF2 : seed 2 v seed 3        FINAL : winner SF1 v winner SF2

Matches are played in the order  SF1, SF2, THIRD, FINAL.  The higher seed plays
on the left.

Ties at the cut-off.  If players are level on (score, conceded, rally, returns) across the
4th/5th place line, there are more contenders than seats.  They settle it with
sudden-death PLAYOFF matches first:  PO1 = contender 1 v 2, PO2 = winner of PO1
v contender 3, ... until the seats are filled.  (A contender not yet reached by
the chain gets a bye - only possible with 3+ players tied for the last seat(s),
which is very unlikely.)

Withdrawals.  If a player can't continue:
  * before they have played a match, the best-ranked qualifier not in the bracket
    takes over their seat (same seed / same playoff slot);
  * after they have played, or when nobody is left to replace them, they forfeit
    every match still to come: the opponent advances by WALKOVER (recorded as a
    full-score win marked W/O).

Progress is saved to finals_state.json after every match or withdrawal, so a
restart resumes the bracket where it stopped.
"""

import json
import os

from game.config import FINALS_SCORE_TO_WIN, FINALS_PLAYOFF_SCORE

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINALS_STATE_FILE = os.path.join(_PROJECT_ROOT, "finals_state.json")

SEATS = 4
_BRACKET = ("SF1", "SF2", "THIRD", "FINAL")
_LABELS = {"SF1": "SEMI-FINAL 1", "SF2": "SEMI-FINAL 2", "THIRD": "3RD PLACE", "FINAL": "FINAL"}


class Finals:
    def __init__(self, snapshot):
        self.snap = snapshot            # {"sure", "group", "seats", "others", "results"}
        self.sure = list(snapshot["sure"])
        self.group = list(snapshot["group"])
        self.group_seats = int(snapshot["seats"])
        self.others = list(snapshot["others"])
        self.withdrawn = list(snapshot.get("withdrawn", []))
        self.elim = len(self.group) - self.group_seats          # playoff matches needed
        self.results = {}                                       # match id -> (s1, s2)
        self.walkovers = set()                                  # ids of matches won by walkover
        self.order = ([f"PO{i + 1}" for i in range(self.elim)]) + list(_BRACKET)
        for r in snapshot.get("results", []):
            self._apply(r["id"], int(r["s1"]), int(r["s2"]), replay=True, wo=bool(r.get("wo")))

    # ---- construction -------------------------------------------------------

    @classmethod
    def from_ranking(cls, ranking):
        """Seed from EventBoard.ranking().  Raises ValueError if fewer than 4 players."""
        if len(ranking) < SEATS:
            raise ValueError(f"need at least {SEATS} players on the leaderboard (have {len(ranking)})")
        cut = ranking[SEATS - 1]["rank"]
        sure = [e["player"] for e in ranking if e["rank"] < cut]
        group = [e["player"] for e in ranking if e["rank"] == cut]
        others = [e["player"] for e in ranking if e["rank"] > cut]
        return cls({"sure": sure, "group": group, "seats": SEATS - len(sure),
                    "others": others, "results": []})

    @classmethod
    def load(cls, path=None):
        """Resume a saved bracket, or None if there isn't a usable one."""
        path = path or FINALS_STATE_FILE
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return cls(data)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save(self, write_json, path=None):
        write_json(path or FINALS_STATE_FILE, self.snap)

    # ---- structure ------------------------------------------------------------

    def _winner_of(self, mid):
        r = self.results.get(mid)
        if r is None:
            return None
        p1, p2 = self._players(mid)
        return p1 if r[0] > r[1] else p2

    def _loser_of(self, mid):
        r = self.results.get(mid)
        if r is None:
            return None
        p1, p2 = self._players(mid)
        return p2 if r[0] > r[1] else p1

    def seeds(self):
        """The four seeds in order; None where a playoff hasn't decided the seat."""
        if self.elim > 0:
            w = self._winner_of(f"PO{self.elim}")
            tail = [w] + self.group[self.elim + 1:]
        else:
            tail = list(self.group)
        return (self.sure + tail)[:SEATS]

    def _players(self, mid):
        """(player1, player2) of a match, None for a side not decided yet."""
        if mid.startswith("PO"):
            i = int(mid[2:])
            p1 = self.group[0] if i == 1 else self._winner_of(f"PO{i - 1}")
            return p1, self.group[i]
        s = self.seeds()
        if mid == "SF1":
            return s[0], s[3]
        if mid == "SF2":
            return s[1], s[2]
        if mid == "THIRD":
            return self._loser_of("SF1"), self._loser_of("SF2")
        return self._winner_of("SF1"), self._winner_of("SF2")      # FINAL

    def _ref_text(self, mid, side):
        if mid.startswith("PO"):
            return "Winner PO%d" % (int(mid[2:]) - 1)
        return {("SF1", 0): "Seed 1", ("SF1", 1): "Seed 4", ("SF2", 0): "Seed 2", ("SF2", 1): "Seed 3",
                ("THIRD", 0): "Loser SF1", ("THIRD", 1): "Loser SF2",
                ("FINAL", 0): "Winner SF1", ("FINAL", 1): "Winner SF2"}[(mid, side)]

    @staticmethod
    def _target(mid):
        return FINALS_PLAYOFF_SCORE if mid.startswith("PO") else FINALS_SCORE_TO_WIN

    # ---- play -------------------------------------------------------------------

    def next_match(self):
        """The next match that can be played now, or None."""
        for mid in self.order:
            if mid in self.results:
                continue
            p1, p2 = self._players(mid)
            if p1 and p2:
                return self._match_view(mid, next_id=mid)
            return None                 # waiting on an earlier match
        return None

    def _apply(self, mid, s1, s2, replay=False, wo=False):
        if mid not in self.order or mid in self.results:
            raise ValueError(f"match {mid} is not playable")
        p1, p2 = self._players(mid)
        if not (p1 and p2):
            raise ValueError(f"match {mid} has no players yet")
        if s1 == s2:
            raise ValueError("a knockout match needs a winner")
        self.results[mid] = (s1, s2)
        if wo:
            self.walkovers.add(mid)
        if not replay:
            entry = {"id": mid, "s1": s1, "s2": s2}
            if wo:
                entry["wo"] = True
            self.snap.setdefault("results", []).append(entry)

    def _summary(self, mid):
        s1, s2 = self.results[mid]
        p1, p2 = self._players(mid)
        winner, loser = (p1, p2) if s1 > s2 else (p2, p1)
        out = {"id": mid, "label": self._label(mid), "p1": p1, "p2": p2, "s1": s1, "s2": s2,
               "winner": winner, "loser": loser, "target": self._target(mid),
               "wo": mid in self.walkovers}
        if out["wo"]:
            gone = [p for p in (p1, p2) if p in self.withdrawn]
            out["note"] = "walkover - " + " and ".join(gone) + " withdrew"
        return out

    def _auto_walkovers(self):
        """Resolve, in order, every match that now involves a withdrawn player.
        Returns the summaries of the walkovers it recorded."""
        out = []
        while True:
            mid = next((m for m in self.order if m not in self.results), None)
            if mid is None:
                break
            p1, p2 = self._players(mid)
            if not (p1 and p2):
                break                           # waiting on an earlier match
            w1, w2 = p1 in self.withdrawn, p2 in self.withdrawn
            if not (w1 or w2):
                break                           # a real match to play
            t = self._target(mid)
            self._apply(mid, 0 if (w1 and not w2) else t, t if (w1 and not w2) else 0, wo=True)
            out.append(self._summary(mid))
        return out

    def record(self, mid, s1, s2):
        """Record a finished match.  Returns a summary dict; summary["walkovers"]
        lists any walkovers this result triggered (a next opponent who withdrew)."""
        nxt = self.next_match()
        if not nxt or nxt["id"] != mid:
            raise ValueError(f"{mid} is not the next match")
        self._apply(mid, s1, s2)
        out = self._summary(mid)
        out["walkovers"] = self._auto_walkovers()
        return out

    # ---- withdrawals --------------------------------------------------------------------

    def alive(self):
        """Players who still have a match to play (the ones who can withdraw)."""
        names = []
        for mid in self.order:
            if mid in self.results:
                continue
            for p in self._players(mid):
                if p and p not in self.withdrawn and p not in names:
                    names.append(p)
        return names

    def withdraw(self, name):
        """A player cannot continue.  Returns {"name", "replacement", "walkovers"}."""
        if name not in self.alive():
            raise ValueError(f"{name} is not an active finalist")
        played = any(name in self._players(mid) for mid in self.results)
        replacement = None
        if not played:
            replacement = next((n for n in self.others if n not in self.withdrawn), None)
        if replacement:
            for lst in (self.sure, self.group):
                if name in lst:
                    lst[lst.index(name)] = replacement
            self.others.remove(replacement)
            self.snap["sure"], self.snap["group"], self.snap["others"] = (
                list(self.sure), list(self.group), list(self.others))
        self.withdrawn.append(name)
        self.snap["withdrawn"] = list(self.withdrawn)
        return {"name": name, "replacement": replacement, "walkovers": self._auto_walkovers()}

    @property
    def complete(self):
        return "FINAL" in self.results and "THIRD" in self.results

    def podium(self):
        """[1st, 2nd, 3rd, 4th] once the finals are complete, else None."""
        if not self.complete:
            return None
        return [self._winner_of("FINAL"), self._loser_of("FINAL"),
                self._winner_of("THIRD"), self._loser_of("THIRD")]

    def fifth(self):
        """Best player who missed the top 4 (by qualifier rank)."""
        qualified = {s for s in self.seeds() if s}
        for name in self.group + self.others:
            if name not in qualified and name not in self.withdrawn:
                return name
        return None

    # ---- views for the UI -----------------------------------------------------------

    def _label(self, mid):
        return f"PLAYOFF {mid[2:]}" if mid.startswith("PO") else _LABELS[mid]

    def _match_view(self, mid, next_id=None):
        p1, p2 = self._players(mid)
        r = self.results.get(mid)
        return {"id": mid, "label": self._label(mid), "p1": p1, "p2": p2,
                "ref1": self._ref_text(mid, 0), "ref2": self._ref_text(mid, 1),
                "s1": r[0] if r else None, "s2": r[1] if r else None,
                "done": r is not None, "wo": mid in self.walkovers,
                "winner": (p1 if r[0] > r[1] else p2) if r else None,
                "target": self._target(mid), "is_next": mid == next_id}

    def view(self):
        nxt = self.next_match()
        nid = nxt["id"] if nxt else None
        return [self._match_view(mid, nid) for mid in self.order]
