import tkinter as tk
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

        # Store server reference on parent UI for future reuse
        self.parent_ui._mobile_server_instance = self.panel.server

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

        if hasattr(self.parent_ui, "update_dirty_ui"):
            self.parent_ui.update_dirty_ui()
        if hasattr(self.parent_ui, "update_review_progress"):
            self.parent_ui.update_review_progress()

        self.win.destroy()

    # ------------------------------------------------------------------
    # Edit callback — notify desktop UI of each incoming mobile edit
    # ------------------------------------------------------------------

    def _on_mobile_edit(self, oid, summary):
        try:
            self.app_state._mobile_last_edited_oid = oid
            self.root.event_generate("<<MobileEdit>>", when="tail")
        except Exception:
            pass
