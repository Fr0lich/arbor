import tkinter as tk
import sys
import os
import ctypes

# ── User preferences file ────────────────────────────────────────────────────
# When frozen as a PyInstaller exe, __file__ points to a temp extraction folder
# that is deleted on exit.  Use sys.executable (the actual .exe) instead.
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_PREFS_PATH = os.path.join(_BASE_DIR, "user_prefs.json")

# Load/save logic moved to config.py

# ── Enable DPI awareness BEFORE creating the Tk window ───────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception as e:  # Fix: Replace bare except
    pass  # Non-Windows or already set — safe to ignore


# ── Global exception hooks ────────────────────────────────────────────────────

def _install_exception_hooks(root: tk.Tk, ui_ref: list) -> None:
    """
    Install two complementary exception hooks:

    1. root.report_callback_exception  — catches every unhandled exception that
       Tkinter swallows inside after(), trace callbacks, and event bindings.
       By default Tkinter only prints these to stderr (invisible in windowed
       apps), so the crash is completely silent without this override.

    2. sys.excepthook — catches any unhandled exception that escapes the main
       thread entirely (e.g., during startup before mainloop).
    """

    def _show_error_immediately(exc_type, exc_value, exc_tb):
        """Format the traceback and immediately open a scrollable error dialog."""
        import traceback as _tb
        tb_text = "".join(_tb.format_exception(exc_type, exc_value, exc_tb))
        short_msg = f"{exc_type.__name__}: {exc_value}"
        try:
            from utils import debug_error
            debug_error("Unhandled callback exception", short_msg, is_crash=True)
        except Exception as e:  # Fix: Replace bare except
            pass

        # Show the dialog via after() so we never block the event loop
        def _open_dialog():
            active_ui = ui_ref[0] if ui_ref else None
            if active_ui is not None and hasattr(active_ui, "show_traceback_dialog"):
                active_ui.show_traceback_dialog(
                    "⚠ Something went wrong",
                    f"A critical error occurred — the program has paused to prevent data corruption. Please save an emergency backup before closing.\n\n{short_msg}",
                    tb_text,
                    is_crash=True
                )
            else:
                # Fallback: plain messagebox before UI is ready
                from tkinter import messagebox
                try:
                    from utils import get_session_log_path
                    log_path = get_session_log_path()
                except Exception as e:  # Fix: Replace bare except
                    log_path = "logs folder"
                messagebox.showerror(
                    "Unhandled Error",
                    f"{short_msg}\n\nThe full traceback has been saved to:\n{log_path}\n\nTraceback:\n{tb_text}"
                )

        try:
            root.after(0, _open_dialog)
        except Exception as e:  # Fix: Replace bare except
            pass  # root may already be destroyed

    # 1. Tkinter callback exceptions
    def _tk_report(exc_type, exc_value, exc_tb):
        _show_error_immediately(exc_type, exc_value, exc_tb)

    root.report_callback_exception = _tk_report

    # 2. Main-thread uncaught exceptions
    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        _show_error_immediately(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook


def _install_atexit_crash_reporter() -> None:
    """
    Write a human-readable crash report on process exit — including force-close
    via Windows Task Manager (which sends SIGTERM, triggering atexit handlers).
    The file is written only when at least one error was logged this session.
    """
    import atexit

    def _on_exit():
        try:
            from utils import session_had_errors, get_session_log_path
            from datetime import datetime
            if not session_had_errors():
                return
            log_path = get_session_log_path()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"\n{'═' * 80}\n"
                    f"SESSION ENDED — {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                    f"{'═' * 80}\n"
                )
        except Exception as e:  # Fix: Replace bare except
            pass

    atexit.register(_on_exit)


def _check_previous_crash_logs(root: tk.Tk, ui_ref: list) -> None:
    """
    On startup, look for log files from previous sessions that contain errors.
    If found, show a notification banner offering to view the most recent one.
    """
    import threading

    def _background_scan():
        try:
            from utils import _get_log_dir, get_session_log_path
            import glob

            log_dir = _get_log_dir()
            current_log = get_session_log_path()

            # Find all session logs that are not the current one
            pattern = os.path.join(log_dir, "arbor_*.log")
            all_logs = sorted(glob.glob(pattern), reverse=True)
            
            # Clean up/check stale logs safely in thread
            stale_logs = []
            for p in all_logs:
                if p != current_log:
                    try:
                        if os.path.getsize(p) > 0:
                            stale_logs.append(p)
                    except OSError:
                        pass

            if not stale_logs:
                return

            most_recent = stale_logs[0]

            def _show_banner():
                active_ui = ui_ref[0] if ui_ref else None
                if active_ui is None:
                    return
                if hasattr(active_ui, "show_banner"):
                    active_ui.show_banner(
                        f"⚠ Crash log from last session found — click to view",
                        banner_type="warning",
                        duration_ms=12000,
                        action_callback=lambda: active_ui.show_error_log_window(most_recent)
                    )

            root.after(2000, _show_banner)
        except Exception as e:  # Fix: Replace bare except
            pass

    thread = threading.Thread(target=_background_scan, daemon=True)
    thread.start()


# ── Main ──────────────────────────────────────────────────────────────────────

from datetime import datetime   # needed by _on_exit above

if __name__ == "__main__":
    try:
        # Import heavy/third-party modules inside the try block to prevent silent startup/import crashes
        from models import AppState
        from ui.main_window import ObjectProgramUI
        from ui.dialogs import StartupDialog
        import config

        app = AppState()
        root = tk.Tk()
        try:
            root.attributes("-alpha", 0.0)
        except Exception as e:  # Fix: Replace bare except
            pass

        # ── Detect DPI scale factor (stored for info display only) ──────────────
        # winfo_fpixels('1i') returns pixels-per-inch on this screen.
        detected_dpi = root.winfo_fpixels('1i')
        detected_scale = round(detected_dpi / 96.0, 2)

        config._PREFS_PATH = _PREFS_PATH           # single shared path used everywhere

        prefs = config.load_prefs()

        if "autosave_interval" in prefs:
            try:
                config.AUTOSAVE_INTERVAL_MS = int(prefs["autosave_interval"]) * 60 * 1000
            except Exception as e:  # Fix: Replace bare except
                pass

        if "custom_databases" in prefs:
            config.DATABASE_CONFIGS.update(prefs["custom_databases"])

        if "ui_scale" in prefs and prefs.get("user_set"):
            ui_scale = float(prefs["ui_scale"])
        else:
            ui_scale = 1.0
            prefs["detected_scale"] = detected_scale
            prefs["ui_scale"] = ui_scale
            config.save_prefs(prefs)

        config.UI_SCALE = ui_scale
        config._detected_scale = detected_scale

        # ── ui_ref: mutable list so hooks set above can access 'ui' after it's created
        ui_ref = [None]

        # ── Install global error hooks ─────────────────
        _install_exception_hooks(root, ui_ref)
        _install_atexit_crash_reporter()

        # Hide main window initially
        root.withdraw()

        # We do not pass ui to StartupDialog yet, because ui has not been created.
        dialog = StartupDialog(root, app)

        # Ensure startup dialog is forcefully brought to the front
        dialog.win.attributes("-topmost", True)
        dialog.win.update()
        # You can turn off topmost after it's shown if you don't want it permanently stuck above other apps
        dialog.win.attributes("-topmost", False)
        dialog.win.focus_force()

        root.wait_window(dialog.win)

        if not dialog.completed:
            root.destroy()
            sys.exit(0)

        # Dialog completed successfully. Now construct the heavy Main Window UI.
        ui = ObjectProgramUI(root, app)
        ui_ref[0] = ui

        # Apply user configurations determined by the StartupDialog
        if getattr(dialog, "image_mode_val", "online") == "online":
            ui.enable_online_images()
        elif getattr(dialog, "image_mode_val", "online") == "folder":
            ui.image_mode = "folder"
            ui.image_folder = getattr(dialog, "image_folder_val", "")
        elif getattr(dialog, "image_mode_val", "online") == "offline":
            ui.enable_offline_mode()

        ui.apply_config()

        if hasattr(dialog, "selected_excel_path"):
            from ui.dialogs import LoadingWindow
            loading_win = LoadingWindow(root, dialog.selected_excel_path, ui)
        elif hasattr(dialog, "db_path_var") and dialog.db_path_var.get().strip():
            ui.open_excel_from_path(dialog.db_path_var.get().strip())
            try:
                root.attributes("-alpha", 1.0)
            except Exception as e:  # Fix: Replace bare except
                pass
            root.deiconify()
            root.state("zoomed")
            from ui.tutorial import TutorialManager
            TutorialManager().continue_pending_tutorial(root)
        else:
            try:
                root.attributes("-alpha", 1.0)
            except Exception as e:  # Fix: Replace bare except
                pass
            root.deiconify()
            root.state("zoomed")
            from ui.tutorial import TutorialManager
            TutorialManager().continue_pending_tutorial(root)

        # Check for crash logs from previous sessions (shows a banner after 2 s)
        _check_previous_crash_logs(root, ui_ref)

        def toggle_fullscreen(event=None):
            root.state("zoomed" if root.state() != "zoomed" else "normal")

        def exit_fullscreen(event=None):
            root.state("normal")

        root.bind("<F11>", toggle_fullscreen)
        root.bind("<Escape>", exit_fullscreen)

        root.mainloop()
    except Exception as e:
        # Log the error if possible
        try:
            from utils import debug_error
            debug_error("Application Error", str(e))
        except Exception as import_err:
            import logging
            logging.error(f"Could not import utils to log crash: {import_err}")

        # Guarantee that a GUI message box is shown for startup/runtime crashes so they are never silent
        try:
            import traceback as _tb
            tb_text = _tb.format_exc()
            from tkinter import messagebox
            messagebox.showerror(
                "Application Startup Error",
                f"A critical error occurred during startup or execution:\n\n{e}\n\nTraceback:\n{tb_text}"
            )
        except Exception as e:  # Fix: Replace bare except
            pass
