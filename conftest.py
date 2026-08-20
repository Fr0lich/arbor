import os
import tkinter as tk

# Remove any pre-existing environment variables pointing to restricted WindowsApps paths
for var in ("TCL_LIBRARY", "TK_LIBRARY"):
    val = os.environ.get(var, "")
    if "WindowsApps" in val:
        os.environ.pop(var, None)

# Monkeypatch tk.Tk.__init__ to automatically recover if a TclError occurs during Tcl interpreter creation
_original_tk_init = tk.Tk.__init__

def _safe_tk_init(self, *args, **kwargs):
    try:
        _original_tk_init(self, *args, **kwargs)
    except tk.TclError:
        # Tcl failed to initialize, likely due to invalid or restricted TCL_LIBRARY/TK_LIBRARY environment variables.
        # Clear them and retry.
        os.environ.pop("TCL_LIBRARY", None)
        os.environ.pop("TK_LIBRARY", None)
        _original_tk_init(self, *args, **kwargs)

tk.Tk.__init__ = _safe_tk_init
