import traceback
import os
import sys
from datetime import datetime
import pandas as pd

def fmt_pandas_val(val):
    if pd.isna(val) or val == "":
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


# ── Canonical log directory ──────────────────────────────────────────────────
# Always sits in a "logs/" folder next to the .exe (frozen) or main.py (dev).
def _get_log_dir() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        # Walk up to find main.py so the logs/ folder is always at project root
        here = os.path.dirname(os.path.abspath(__file__))
        base = here
    log_dir = os.path.join(base, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


# One log file per session, created lazily on first error
_SESSION_LOG_PATH: str | None = None
_SESSION_HAS_ERRORS: bool = False   # set to True when any error is logged


def get_session_log_path() -> str:
    """Return (and create if needed) the path to this session's log file."""
    global _SESSION_LOG_PATH
    if _SESSION_LOG_PATH is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _SESSION_LOG_PATH = os.path.join(_get_log_dir(), f"arbor_{ts}.log")
    return _SESSION_LOG_PATH


def session_had_errors() -> bool:
    """Return True if at least one error has been logged this session."""
    return _SESSION_HAS_ERRORS


def debug_error(context: str, extra: str = "") -> None:
    """Log an error with full traceback to the session log and to stdout."""
    global _SESSION_HAS_ERRORS
    _SESSION_HAS_ERRORS = True

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tb = traceback.format_exc()
    msg = f"[{ts}] [ERROR] {context}"
    if extra:
        msg += f" — {extra}"
    msg += f"\n{tb}"

    print(msg)

    log_path = get_session_log_path()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n" + ("─" * 80) + "\n")
    except Exception:
        pass  # Never raise inside an error handler


def center_and_fit_toplevel(win, base_w=None, base_h=None):
    win.update_idletasks()

    req_w = base_w if base_w is not None else win.winfo_reqwidth()
    req_h = base_h if base_h is not None else win.winfo_reqheight()

    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()

    # Cap to 90% of screen height to avoid overflowing behind taskbars
    max_w = int(screen_w * 0.9)
    max_h = int(screen_h * 0.9)

    w = min(req_w, max_w)
    h = min(req_h, max_h)

    x = (screen_w // 2) - (w // 2)
    y = (screen_h // 2) - (h // 2)

    win.geometry(f"{w}x{h}+{x}+{y}")


def get_log_level() -> str:
    """Return the configured log verbosity level."""
    try:
        import json
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        prefs_path = os.path.join(base_dir, "user_prefs.json")
        if os.path.exists(prefs_path):
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
                return prefs.get("advanced", {}).get("log_verbosity", "ERROR")
    except Exception:
        pass
    return "ERROR"


def debug_log(level: str, context: str, extra: str = "") -> None:
    """Log a message at the specified level if it meets the verbosity requirements."""
    levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    current_level = get_log_level()
    
    req_idx = levels.index(level) if level in levels else 1
    curr_idx = levels.index(current_level) if current_level in levels else 3
    
    if req_idx < curr_idx:
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] [{level}] {context}"
    if extra:
        msg += f" — {extra}"
        
    print(msg)
    
    try:
        log_path = get_session_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

