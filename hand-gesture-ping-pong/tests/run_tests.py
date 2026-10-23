"""One command to check the whole game:

    venv\\Scripts\\python.exe tests\\run_tests.py           (or double-click run_tests.bat)

    -v / --verbose   show every PASS line, not just failures and the summary
    -k TEXT          only show lines containing TEXT (e.g. -k multi)

The suite runs in its own process (a native crash in a test fails the run instead of killing
it) and writes only to a temporary folder.  As a guard, this runner fingerprints the real
settings / stats / score files before and after, and fails the run if a test touched them.
"""
import argparse
import hashlib
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_FILES = ["settings.json", "stats.json", "game_history.csv", "point_log.csv",
              "event_results.csv", "finals_results.csv", "finals_state.json"]
NOISE = ("W0000", "INFO:", "WARNING: All log messages", "pygame ", "Hello from the pygame",
         "could not write locked.csv", "[camera] scan failed")      # expected output of the tests that provoke them


def fingerprint():
    out = {}
    for name in REAL_FILES:
        path = os.path.join(ROOT, name)
        out[name] = hashlib.md5(open(path, "rb").read()).hexdigest() if os.path.exists(path) else None
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true", help="print every check")
    ap.add_argument("-k", metavar="TEXT", help="only print lines containing TEXT")
    args = ap.parse_args()

    before = fingerprint()
    start = time.time()
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "verify_game.py")],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = (proc.stdout or "").splitlines()
    fails = [l for l in lines if l.startswith("FAIL ")]
    for l in lines:
        if args.k and args.k.lower() not in l.lower():
            continue
        if args.verbose or l.startswith("FAIL") or not l.startswith("PASS"):
            if l.strip() and not any(n in l for n in NOISE):
                print(l)
    if proc.returncode != 0 and not fails:               # crashed before / between checks
        print("\nTEST PROCESS FAILED (exit code %s):" % proc.returncode)
        print("\n".join((proc.stderr or "").splitlines()[-25:]))
    touched = [n for n, h in fingerprint().items() if before[n] != h]
    if touched:
        print("\nERROR: the tests modified real game files: " + ", ".join(touched))
    ok = proc.returncode == 0 and not touched
    print(f"\n{'OK' if ok else 'FAILED'}  ({time.time() - start:.0f}s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
