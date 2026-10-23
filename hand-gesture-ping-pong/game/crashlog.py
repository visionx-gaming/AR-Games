"""Crash evidence: unhandled errors (and native crashes) are written to crash_log.txt.

The terminal window usually closes with the game, so a traceback printed there is
lost.  The log sits next to the game; send its last entries when reporting a crash.
"""

import faulthandler
import os
import sys
import traceback
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crash_log.txt")
_fault_file = None


def _stamp(context):
    return f"\n=== {datetime.now().isoformat(timespec='seconds')}  {context} ===\n"


def log_exception(context, exc_info=None):
    """Append the current (or given) exception with a header. Never raises."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(_stamp(context))
            traceback.print_exception(*(exc_info or sys.exc_info()), file=f)
    except OSError:
        pass


def install():
    """Log uncaught exceptions, and hard crashes (segfaults in a driver / library)."""
    global _fault_file
    default_hook = sys.excepthook

    def hook(exc_type, exc, tb):
        log_exception("uncaught exception", (exc_type, exc, tb))
        default_hook(exc_type, exc, tb)

    sys.excepthook = hook
    try:
        _fault_file = open(LOG_PATH, "a", encoding="utf-8")
        faulthandler.enable(file=_fault_file, all_threads=True)      # a native crash writes here
    except OSError:
        pass


def cleanup():
    """Normal exit: stop the fault handler and remove the log if nothing was recorded."""
    global _fault_file
    try:
        faulthandler.disable()
        if _fault_file is not None:
            _fault_file.close()
            _fault_file = None
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) == 0:
            os.remove(LOG_PATH)
    except OSError:
        pass
