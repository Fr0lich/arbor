import traceback
import os
import sys
import threading
import collections
from datetime import datetime
import pandas as pd
from loguru import logger

def fmt_pandas_val(val):
    if pd.isna(val) or val == "":
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


import re

def sanitize_df_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Sanitize DataFrame string columns to prevent CSV/Excel formula injection
    and remove illegal XML characters.

    Prepends a single quote to strings starting with dangerous characters
    (=, +, -, @, \t, \r, cmd|) to force Excel to treat them as plain text.
    Removes timezone information from datetime objects.
    """
    if df is None or df.empty:
        return df

    df_safe = df.copy()
    if df_safe.columns.duplicated().any():
        seen = {}
        new_cols = []
        for col in df_safe.columns:
            c_str = str(col).strip()
            if c_str in seen:
                seen[c_str] += 1
                new_cols.append(f"{c_str}.{seen[c_str]}")
            else:
                seen[c_str] = 0
                new_cols.append(c_str)
        df_safe.columns = new_cols

    dangerous_starts = ('=', '+', '-', '@', '\t', '\r')

    # ILLEGAL_CHARACTERS_RE pattern from openpyxl/cell/cell.py
    ILLEGAL_CHARACTERS_RE = re.compile(r'[\000-\010]|[\013-\014]|[\016-\037]')

    for col in df_safe.columns:
        s = df_safe[col]
        if s.dtype.name == 'category':
            df_safe[col] = s.astype('object')
            s = df_safe[col]

        # Fast path for timezone aware series
        if hasattr(s.dtype, "tz") and s.dtype.tz is not None:
            df_safe[col] = s.dt.tz_localize(None)
            continue

        # Skip numeric and boolean columns (cannot contain injection strings, XML control chars, or timezones)
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
            continue

        def sanitize_val(x):
            # 1. Remove timezone from timestamps and datetimes
            if isinstance(x, (pd.Timestamp, datetime)) and getattr(x, "tzinfo", None) is not None:
                x = x.tz_localize(None) if isinstance(x, pd.Timestamp) else x.replace(tzinfo=None)

            # 2. Sanitize strings
            if isinstance(x, str):
                if x.lstrip().startswith(dangerous_starts) or x.lstrip().lower().startswith("cmd|"):
                    x = f"'{x}"
                x = ILLEGAL_CHARACTERS_RE.sub('', x)
            return x

        df_safe[col] = df_safe[col].map(sanitize_val)

    return df_safe


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


# -- Loguru Diagnostic & Logging Infrastructure --------------------------------
_logger_initialized = False
_logger_lock = threading.Lock()


def _ensure_logger_configured() -> None:
    """Initialize Loguru with standard console and rotated/compressed file sinks."""
    global _logger_initialized
    if _logger_initialized:
        return
    with _logger_lock:
        if _logger_initialized:
            return

        # Remove default sink to prevent duplicate console printing
        logger.remove()

        def _log_filter(record):
            try:
                current = get_log_level()
                return record["level"].no >= logger.level(current).no
            except Exception:
                return True

        # Console sink with clean timestamp and level formatting
        logger.add(
            sys.stdout,
            format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {message}",
            filter=_log_filter,
            backtrace=False,
            diagnose=False
        )

        # File sink with automatic 10MB rotation, 7-day retention, zip compression, and lockless async enqueue
        try:
            log_file = get_session_log_path()
            logger.add(
                log_file,
                format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {message}",
                filter=_log_filter,
                rotation="10 MB",
                retention="7 days",
                compression="zip",
                enqueue=True,
                backtrace=True,
                diagnose=True,
                encoding="utf-8"
            )
            import atexit
            atexit.register(logger.complete)
        except Exception:
            pass

        _logger_initialized = True


_ensure_logger_configured()

# Legacy stubs preserved for backward compatibility
_log_queue: collections.deque = collections.deque()
_log_queue_lock = threading.Lock()


def _ensure_flush_thread() -> None:
    """Legacy stub maintained for backward compatibility (Loguru handles enqueue natively)."""
    pass


def _flush_loop() -> None:
    """Legacy stub maintained for backward compatibility."""
    pass


def _flush_log_queue() -> None:
    """Legacy stub maintained for backward compatibility."""
    pass


def debug_error(context: str, extra: str = "", is_crash: bool = False) -> None:
    """Log an error with full traceback to the session log and to stdout."""
    global _SESSION_HAS_ERRORS
    _SESSION_HAS_ERRORS = True

    _ensure_logger_configured()

    crash_prefix = "[CRASH] " if is_crash else ""
    msg = f"{crash_prefix}{context}"
    if extra:
        msg += f" -- {extra}"

    exc = sys.exc_info()
    if exc[0] is not None:
        logger.opt(depth=1, exception=exc).error(msg)
    else:
        logger.opt(depth=1).error(msg)

    try:
        logger.complete()
    except Exception:
        pass


# -- Canonical resource path resolver -----------------------------------------
def get_resource_path(relative_path: str) -> str:
    """
    Resolve absolute path to a resource file.
    Checks:
    1. PyInstaller extraction temp dir (sys._MEIPASS)
    2. Next to the executable (sys.executable dir)
    3. Source repository root
    """
    if getattr(sys, "frozen", False):
        # 1. Check bundled in PyInstaller _MEIPASS
        meipass_dir = getattr(sys, "_MEIPASS", "")
        if meipass_dir:
            cand = os.path.join(meipass_dir, relative_path)
            if os.path.exists(cand):
                return cand

        # 2. Check next to the executable
        exe_dir = os.path.dirname(sys.executable)
        cand = os.path.join(exe_dir, relative_path)
        if os.path.exists(cand):
            return cand
        return cand  # Return expected path even if missing so errors are clear

    # 3. Development mode: relative to project root
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, relative_path)
    return cand


def fade_in_toplevel(win, target_alpha=1.0, duration_ms=120, step_ms=15):
    """Ensure window opacity is set to target_alpha immediately and safely."""
    try:
        if win.winfo_exists():
            win.attributes("-alpha", target_alpha)
            win.deiconify()
    except Exception:
        pass



def center_and_fit_toplevel(win, base_w=None, base_h=None):
    win.update_idletasks()

    req_w = base_w if base_w is not None else win.winfo_reqwidth()
    req_h = base_h if base_h is not None else win.winfo_reqheight()

    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()

    # Restrict maximum size to leave room for Windows taskbar and window borders on laptops
    max_w = max(400, int(screen_w * 0.92))
    max_h = max(450, int(screen_h * 0.88))

    w = min(req_w, max_w)
    h = min(req_h, max_h)

    x = max(0, (screen_w // 2) - (w // 2))
    y = max(0, (screen_h // 2) - (h // 2))

    win.geometry(f"{w}x{h}+{x}+{y}")
    fade_in_toplevel(win)




def debug_log(level: str, context: str, extra: str = "") -> None:
    """Log a message at the specified level if it meets the verbosity threshold."""
    _ensure_logger_configured()
    msg = context
    if extra:
        msg += f" -- {extra}"
    level_name = level.upper() if level else "INFO"
    if level_name not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        level_name = "INFO"
    logger.opt(depth=1).log(level_name, msg)


# ── Fast Fuzzy Matching (rapidfuzz with difflib fallback) ─────────────────────
try:
    from rapidfuzz import fuzz, process
    _HAS_RAPIDFUZZ = True
except ImportError:
    import difflib
    _HAS_RAPIDFUZZ = False


def fuzzy_score(query: str, target: str) -> float:
    """Calculate fuzzy similarity score (0.0 to 100.0) between query and target.

    Uses rapidfuzz.fuzz.WRatio when installed, with a zero-dependency
    fallback to difflib.SequenceMatcher.
    """
    if not query or not target:
        return 0.0
    q = query.strip().lower()
    t = target.strip().lower()
    if q == t:
        return 100.0
    if q in t:
        # Boost direct substring matches
        return 90.0 + (len(q) / max(len(t), 1)) * 10.0

    if _HAS_RAPIDFUZZ:
        return float(fuzz.WRatio(q, t))
    else:
        matcher = difflib.SequenceMatcher(None, q, t)
        return matcher.ratio() * 100.0


def fuzzy_extract(query: str, choices: list[str], limit: int = 10, score_cutoff: float = 55.0) -> list[tuple[str, float]]:
    """Extract top fuzzy matching choices for a query, sorted by score descending."""
    if not query or not choices:
        return []

    q = query.strip().lower()

    if _HAS_RAPIDFUZZ:
        results = process.extract(
            q,
            choices,
            scorer=fuzz.WRatio,
            limit=limit,
            score_cutoff=score_cutoff
        )
        return [(match, float(score)) for match, score, _ in results]
    else:
        scored = []
        for choice in choices:
            score = fuzzy_score(q, choice)
            if score >= score_cutoff:
                scored.append((choice, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

