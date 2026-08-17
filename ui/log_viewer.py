import tkinter as tk
from tkinter import ttk
import utils

from ui.recent_activity_dialog import open_recent_activity_dialog

class LogViewerMixin:
    def open_log_viewer_window(self):
        """Backward compatibility wrapper for legacy callers."""
        self.open_recent_activity_window(default_tab=1)

    def open_recent_activity_window(self, default_tab=0):
        """
        Opens a unified Recent Activity window.
        """
        # If window is already open, raise/focus and select the appropriate tab
        if hasattr(self, "recent_act_win") and self.recent_act_win and self.recent_act_win.winfo_exists():
            self.recent_act_win.lift()
            self.recent_act_win.focus_force()
            if hasattr(self.recent_act_win, "_select_tab"):
                self.recent_act_win._select_tab("visited" if default_tab == 0 else "edits")
            return

        def do_navigate(oid):
            oid = str(oid)
            # Update main list selection
            if hasattr(self, "object_list") and self.object_list:
                self.object_list.selection_clear(0, tk.END)
                if hasattr(self.app, "active_object_ids") and oid in self.app.active_object_ids:
                    list_idx = self.app.active_object_ids.index(oid)
                    self.object_list.selection_set(list_idx)
                    self.object_list.see(list_idx)
            # Load object
            if hasattr(self, "load_object"):
                self.load_object(oid)

        def on_close():
            self.recent_act_win = None

        self.recent_act_win = open_recent_activity_dialog(
            parent=self.root,
            history_stack=getattr(self, "history_stack", []),
            df_log=getattr(self.app, "df_log", None),
            dark_mode=getattr(self, "dark_mode_active", False),
            default_tab=default_tab,
            get_object_title_fn=getattr(self, "object_title", None),
            live_callbacks={
                "on_navigate": do_navigate,
                "on_close": on_close
            }
        )
