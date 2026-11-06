import tkinter as tk
from ui.state import app_bus, DATABASE_UPDATED
from ui.mobile_panel import MobilePanel


class MobileDialog:
    """In-app mobile companion dialog (modal Toplevel).

    Embeds MobilePanel for all shared UI/server logic; this class only
    handles what is unique to the in-app context:
      - Modal Toplevel lifecycle (transient, grab_set, centering)
      - Pre-session desktop commit (prevent in-flight edits being lost)
      - MobileServer reuse across re-opens
      - Post-session desktop UI refresh (load_object, update_dirty_ui, etc.)
      - Exposing the server instance on parent_ui for reuse
    """

    def __init__(self, parent_ui, root, app_state):
        self.parent_ui = parent_ui
        self.root = root
        self.app_state = app_state
        self.port = 5055

        # Build modal window
        self.win = tk.Toplevel(root)
        self.win.title("Arbor Mobile Companion")
        self.win.geometry("540x730")
        self.win.minsize(500, 690)
        self.win.transient(root)

        # Only lock if simultaneous edit is not enabled
        if hasattr(self.parent_ui, "simultaneous_edit_var") and self.parent_ui.simultaneous_edit_var.get():
            pass
        else:
            self.win.grab_set()

        # Center on parent
        self.win.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() // 2) - (540 // 2)
        y = root.winfo_y() + (root.winfo_height() // 2) - (730 // 2)
        self.win.geometry(f"+{max(0, x)}+{max(0, y)}")

        # Commit any active desktop typing before locking
        if hasattr(self.parent_ui, "commit_current_object"):
            try:
                self.parent_ui.commit_current_object()
            except Exception:
                pass

        # Build panel — reuse an existing server if one is already running
        self.server = getattr(self.parent_ui, '_mobile_server_instance', None)
        self.tunnel = None
        self.port = 5055
        self.qr_image_ref = None
        self.local_url_with_token = ""
        self.public_url_with_token = ""
        self.current_qr_mode = "public"
        self.panel = MobilePanel(
            parent=self.win,
            app_state=self.app_state,
            root_tk=self.root,
            port=self.port,
            on_end_session=self._end_session,
            on_edit=self._on_mobile_edit,
            reuse_server=self.server,
        )

        # Store server reference on parent UI and app state for future reuse
        self.parent_ui._mobile_server_instance = self.panel.server
        self.app_state._mobile_server_instance = self.panel.server

        self.win.protocol("WM_DELETE_WINDOW", self._end_session)

    # ------------------------------------------------------------------
    # Session end
    # ------------------------------------------------------------------

    def _end_session(self):
        """Stop panel, refresh desktop UI, close window."""
        self.panel.stop()

        # Reload the currently displayed object to pick up mobile edits
        if hasattr(self.parent_ui, "load_object") and self.app_state.current_object_id:
            try:
                self.parent_ui.load_object(self.app_state.current_object_id)
            except Exception:
                pass

        app_bus.publish(DATABASE_UPDATED)

        if hasattr(self.parent_ui, "_update_push_to_phone_state"):
            self.parent_ui.root.after(100, self.parent_ui._update_push_to_phone_state)

        # Check for unsaved in-memory changes from mobile session
        if getattr(self.app_state, "dirty", False):
            import config
            prefs = config.load_prefs() if hasattr(config, "load_prefs") else {}
            auto_save = getattr(self.panel, "auto_save_var", None)
            is_auto_save = auto_save.get() if auto_save else prefs.get("mobile_autosave_on_stop", False)

            has_valid_path = bool(
                hasattr(self.parent_ui, "app")
                and getattr(self.parent_ui.app, "output_path", None)
            )

            if is_auto_save and has_valid_path:
                if hasattr(self.parent_ui, "save_session"):
                    self.parent_ui.save_session("MOBILE_SESSION_END")
                elif hasattr(self.parent_ui, "save_database"):
                    self.parent_ui.save_database()
            else:
                from tkinter import messagebox
                try:
                    save_now = messagebox.askyesno(
                        title="Arbor Mobile Companion",
                        message=(
                            "Mobile session ended with unsaved changes in memory.\n\n"
                            "Save the workbook to disk now?"
                        ),
                        parent=self.win,
                    )
                except Exception:
                    save_now = False

                if save_now:
                    if hasattr(self.parent_ui, "save_session"):
                        self.parent_ui.save_session("MOBILE_SESSION_END")
                    elif hasattr(self.parent_ui, "save_database"):
                        self.parent_ui.save_database()

        self.win.destroy()

    # ------------------------------------------------------------------
    # Edit callback — notify desktop UI of each incoming mobile edit
    # ------------------------------------------------------------------

    def _on_mobile_edit(self, oid, summary):
        # <<MobileEdit>> is already fired by MobileServer.update_object() directly on root_tk.
        # Do NOT fire it a second time here — that would cause double load_object(), double
        # refresh_list(), and double autosave in the main window handler.
        # This method is retained as a documented hook for future dialog-specific reactions.
        pass
