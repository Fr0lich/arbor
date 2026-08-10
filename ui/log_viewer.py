import tkinter as tk
from tkinter import ttk
import utils

class LogViewerMixin:
    def open_log_viewer_window(self):
        if hasattr(self, "log_win") and self.log_win.winfo_exists():
            self.log_win.focus_set()
            return

        self.log_win = tk.Toplevel(self.root)
        self.log_win.title("Recent Edits")
        utils.center_and_fit_toplevel(self.log_win, 800, 400)

        self._build_log_viewer_ui(self.log_win)

    def _build_log_viewer_ui(self, win):
        from config import sc

        is_dark = getattr(self, "dark_mode_active", False)
        bg_col = "#1e1e2e" if is_dark else "#f9f9f9"
        fg_col = "#cdd6f4" if is_dark else "#1a1c1c"

        win.configure(bg=bg_col)

        hdr = tk.Frame(win, bg=bg_col)
        hdr.pack(fill="x", padx=sc(10), pady=sc(10))
        tk.Label(hdr, text="Recent Edits", font=("Segoe UI", sc(12), "bold"), bg=bg_col, fg=fg_col).pack(side="left")

        tree_frame = ttk.Frame(win)
        tree_frame.pack(fill="both", expand=True, padx=sc(10), pady=(0, sc(10)))

        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical")
        scroll_y.pack(side="right", fill="y")

        tree = ttk.Treeview(tree_frame, columns=("Time", "Action", "ObjectID", "Changes"), show="headings", yscrollcommand=scroll_y.set)
        tree.heading("Time", text="Time")
        tree.heading("Action", text="Action")
        tree.heading("ObjectID", text="Object ID")
        tree.heading("Changes", text="Changes")

        tree.column("Time", width=sc(150), minwidth=sc(100))
        tree.column("Action", width=sc(80), minwidth=sc(60))
        tree.column("ObjectID", width=sc(100), minwidth=sc(60))
        tree.column("Changes", width=sc(450), minwidth=sc(200), stretch=True)

        tree.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=tree.yview)

        # Populate
        df_log = getattr(self.app, "df_log", None)
        if df_log is not None and not df_log.empty:
            cols = df_log.columns
            for row in reversed(list(df_log.itertuples(index=False, name=None))):
                row_dict = dict(zip(cols, row))

                tstamp = row_dict.get("Timestamp", "")
                if "T" in str(tstamp):
                    try:
                        # Extract YYYY-MM-DD HH:MM:SS from ISO format
                        tstamp = str(tstamp).split('.')[0].replace("T", " ")
                    except Exception:
                        pass

                action = row_dict.get("Action", "")
                obj_id = row_dict.get("ObjectID", "")

                # Combine changes
                c_fields = row_dict.get("ChangedFields", "")
                p_fields = row_dict.get("ProblemsChanged", "")
                l_fields = row_dict.get("LocationChanged", "")

                changes_parts = []
                if c_fields and str(c_fields).strip() and str(c_fields) != "(no changes)":
                    changes_parts.append(f"Data: {c_fields}")
                if p_fields and str(p_fields).strip():
                    changes_parts.append(f"Problems: {p_fields}")
                if l_fields and str(l_fields).strip():
                    changes_parts.append(f"Location: {l_fields}")

                changes = " | ".join(changes_parts)
                if not changes and c_fields == "(no changes)":
                    changes = "(no changes)"

                tree.insert("", "end", values=(tstamp, action, obj_id, changes))
