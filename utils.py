import traceback
import os
import sys
import threading
import collections
from datetime import datetime
import pandas as pd

def fmt_pandas_val(val):
    if pd.isna(val) or val == "":
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


def parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "1", "yes", "y", "t", "on"):
            return True
        return False
    return False


# -- Canonical log directory --------------------------------------------------
# Always sits in a "logs/" folder next to the .exe (frozen) or main.py (dev).
def _get_log_dir() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        base = here
    log_dir = os.path.join(base, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


# One log file per session, created lazily on first error
_SESSION_LOG_PATH: str | None = None
_SESSION_HAS_ERRORS: bool = False


def get_session_log_path() -> str:
    """Return (and create if needed) the path to this session''s log file."""
    global _SESSION_LOG_PATH
    if _SESSION_LOG_PATH is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _SESSION_LOG_PATH = os.path.join(_get_log_dir(), f"arbor_{ts}.log")
    return _SESSION_LOG_PATH


def session_had_errors() -> bool:
    """Return True if at least one error has been logged this session."""
    return _SESSION_HAS_ERRORS


# -- P1-C: In-memory log level cache ------------------------------------------
# Previously get_log_level() read user_prefs.json on every debug_log() call.
# Now it is read once and cached. Call reload_log_level() when the user
# changes their verbosity preference in settings.
_cached_log_level: str | None = None
_log_level_lock = threading.Lock()


def get_log_level() -> str:
    """Return the configured log verbosity level from the in-memory cache."""
    global _cached_log_level
    if _cached_log_level is not None:
        return _cached_log_level
    with _log_level_lock:
        if _cached_log_level is not None:
            return _cached_log_level
        _cached_log_level = _read_log_level_from_disk()
    return _cached_log_level


def reload_log_level() -> None:
    """Invalidate and re-read the log level from user_prefs.json.

    Call this after the user changes their verbosity setting in advanced
    settings so the cache stays consistent.
    """
    global _cached_log_level
    with _log_level_lock:
        _cached_log_level = _read_log_level_from_disk()


def _read_log_level_from_disk() -> str:
    """Read verbosity from user_prefs.json. Returns ''ERROR'' on any failure."""
    try:
        import json
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        prefs_path = os.path.join(base_dir, "user_prefs.json")
        if os.path.exists(prefs_path):
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
                if isinstance(prefs, dict):
                    return prefs.get("log_verbosity", prefs.get("advanced", {}).get("log_verbosity", "ERROR"))
    except Exception as e:
        pass
    return "ERROR"


# -- P1-D: Asynchronous log queue ---------------------------------------------
# Previously every debug_log() call did a synchronous file open/write/close on
# the main UI thread. Under heavy event firing this added disk-I/O latency.
#
# Solution: collect entries in an in-memory deque; flush to disk in a single
# batched write every LOG_FLUSH_INTERVAL_S seconds on a background daemon.
# debug_error() bypasses the queue and writes directly so crash records always
# survive even if the process is killed immediately afterwards.

LOG_FLUSH_INTERVAL_S = 5.0

_log_queue: collections.deque = collections.deque()
_log_queue_lock = threading.Lock()
_log_flush_thread: threading.Thread | None = None
_log_flush_stop = threading.Event()


def _ensure_flush_thread() -> None:
    global _log_flush_thread
    if _log_flush_thread is not None and _log_flush_thread.is_alive():
        return
    _log_flush_stop.clear()
    t = threading.Thread(target=_flush_loop, daemon=True, name="log-flush")
    t.start()
    _log_flush_thread = t


def _flush_loop() -> None:
    while not _log_flush_stop.wait(timeout=LOG_FLUSH_INTERVAL_S):
        _flush_log_queue()


def _flush_log_queue() -> None:
    with _log_queue_lock:
        if not _log_queue:
            return
        entries = list(_log_queue)
        _log_queue.clear()
    try:
        log_path = get_session_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(entries) + "\n")
    except Exception as e:
        pass


def debug_error(context: str, extra: str = "", is_crash: bool = False) -> None:
    """Log an error with full traceback to the session log and to stdout.

    Always writes directly to disk (bypasses the async queue) so crash records
    survive even if the process is terminated immediately afterwards.
    """
    global _SESSION_HAS_ERRORS
    _SESSION_HAS_ERRORS = True

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tb = traceback.format_exc()
    crash_prefix = "[CRASH] " if is_crash else ""
    msg = f"[{ts}] [ERROR] {crash_prefix}{context}"
    if extra:
        msg += f" -- {extra}"
    msg += f"\n{tb}"

    print(msg)

    log_path = get_session_log_path()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n" + ("-" * 80) + "\n")
    except Exception as e:
        pass


def center_and_fit_toplevel(win, base_w=None, base_h=None):
    win.update_idletasks()

    req_w = base_w if base_w is not None else win.winfo_reqwidth()
    req_h = base_h if base_h is not None else win.winfo_reqheight()

    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()

    max_w = int(screen_w * 0.9)
    max_h = int(screen_h * 0.9)

    w = min(req_w, max_w)
    h = min(req_h, max_h)

    x = (screen_w // 2) - (w // 2)
    y = (screen_h // 2) - (h // 2)

    win.geometry(f"{w}x{h}+{x}+{y}")


def debug_log(level: str, context: str, extra: str = "") -> None:
    """Log a message at the specified level if it meets the verbosity threshold.

    P1-C: Uses the in-memory cached log level -- no disk I/O per call.
    P1-D: Enqueues the entry for batched background flush -- no synchronous
          file open/write/close on the calling (UI) thread.
    """
    levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    current_level = get_log_level()

    req_idx  = levels.index(level)         if level         in levels else 1
    curr_idx = levels.index(current_level) if current_level in levels else 3

    if req_idx < curr_idx:
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] [{level}] {context}"
    if extra:
        msg += f" -- {extra}"

    print(msg)

    with _log_queue_lock:
        _log_queue.append(msg)

    _ensure_flush_thread()
