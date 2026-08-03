import tkinter as tk
from models import AppState
from ui.main_window import ObjectProgramUI
from ui.dialogs import StartupDialog
import sys
import os
import json
import ctypes
import config
from utils import debug_error

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
except Exception:
    pass  # Non-Windows or already set — safe to ignore

if __name__ == "__main__":
    try:
        app = AppState()
        root = tk.Tk()
        # root.withdraw()  # Removed: don't hide main window to avoid invisible dialog bug
        
        # ── Detect DPI scale factor (stored for info display only) ──────────────
        # winfo_fpixels('1i') returns pixels-per-inch on this screen.
        detected_dpi = root.winfo_fpixels('1i')
        detected_scale = round(detected_dpi / 96.0, 2)

        config._PREFS_PATH = _PREFS_PATH           # single shared path used everywhere
        
        prefs = config.load_prefs()
        
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

        ui = ObjectProgramUI(root, app)
        
        # Hide main window initially
        root.withdraw()
        
        dialog = StartupDialog(root, app, ui)
        
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
            
        # Dialog completed successfully, show main window
        root.deiconify()
        root.state("zoomed")

        from ui.tutorial import TutorialManager
        TutorialManager().continue_pending_tutorial(root)

        if hasattr(dialog, "selected_excel_path"):
            ui._show_progress("Loading database and images...", 100)
            ui.open_excel_from_path(dialog.selected_excel_path)

        def toggle_fullscreen(event=None):
            root.state("zoomed" if root.state() != "zoomed" else "normal")

        def exit_fullscreen(event=None):
            root.state("normal")

        root.bind("<F11>", toggle_fullscreen)
        root.bind("<Escape>", exit_fullscreen)

        root.mainloop()
    except Exception as e:
        debug_error("Application Error", str(e))
