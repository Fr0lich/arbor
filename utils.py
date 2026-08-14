import traceback
import os
import sys
import threading
import collections
import logging
import logging.handlers
from datetime import datetime
import pandas as pd

# Canonical log directory
def _get_log_dir() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        base = here
    log_dir = os.path.join(base, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

# Initialize standard logging
_SESSION_LOG_PATH: str | None = None
_SESSION_HAS_ERRORS: bool = False

def get_session_log_path() -> str:
    """Return (and create if needed) the path to this session's log file."""
    global _SESSION_LOG_PATH
    if _SESSION_LOG_PATH is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _SESSION_LOG_PATH = os.path.join(_get_log_dir(), f"arbor_{ts}.log")
    return _SESSION_LOG_PATH

_logger_initialized = False
logger = logging.getLogger("arbor")

import queue
import atexit

_log_queue = queue.Queue(-1)
_queue_listener = None

def _setup_logging():
    global _logger_initialized, _queue_listener
    if _logger_initialized:
        return

    log_path = get_session_log_path()

    # Application-specific logger configuration
    logger.setLevel(logging.DEBUG)
    # Prevent logs from propagating to the root logger to avoid duplicates
    logger.propagate = False

    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # File handler
    file_handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Setup asynchronous queue handler
    queue_handler = logging.handlers.QueueHandler(_log_queue)
    logger.addHandler(queue_handler)

    _queue_listener = logging.handlers.QueueListener(
        _log_queue, file_handler, console_handler, respect_handler_level=True
    )
    _queue_listener.start()

    def stop_listener():
        if _queue_listener:
            _queue_listener.stop()

    atexit.register(stop_listener)

    _logger_initialized = True

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
                return prefs.get("advanced", {}).get("log_verbosity", "ERROR")
    except Exception as e:  # Fix: Replace bare except
        pass
    return "ERROR"


def debug_error(context: str, extra: str = "", is_crash: bool = False) -> None:
    """Log an error with full traceback to the session log and to stdout."""
    global _SESSION_HAS_ERRORS
    _SESSION_HAS_ERRORS = True

    _setup_logging()

    crash_prefix = "[CRASH] " if is_crash else ""
    msg = f"{crash_prefix}{context}"
    if extra:
        msg += f" -- {extra}"

    # The standard logger's exception() method will capture and print the traceback
    logger.exception(msg)


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
    """Log a message at the specified level if it meets the verbosity threshold."""
    levels = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}

    req_level = levels.get(level, logging.INFO)

    # We still use the custom cached get_log_level for user verbosity preferences
    current_level = get_log_level()
    min_level = levels.get(current_level, logging.ERROR)

    if req_level < min_level:
        return

    _setup_logging()

    msg = context
    if extra:
        msg += f" -- {extra}"

    logger.log(req_level, msg)
