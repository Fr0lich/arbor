import tkinter as tk
import config
from config import sc


class ActionRail:
    @staticmethod
    def build_rail_ui(app, left):
        # Persistent Action Rail frame on the left edge
        rail = tk.Frame(
            left,
            bg=config.RAIL_THEME.get("rail_bg", "#fbfaf8"),
            highlightthickness=1,
            highlightbackground=config.RAIL_THEME.get("rail_border", "#d1d1d1"),
            width=sc(config.RAIL_THEME.get("rail_width", 40))
        )
        rail.pack_propagate(False)
        app.rail_frame = rail
        rail.pack(side="left", fill="y")

        # Sidebar Collapse / Expand Toggle Button
        is_pinned = getattr(app, "left_pinned", None) and app.left_pinned.get()
        bg_color = config.RAIL_THEME.get("icon_hover_bg", "#e9ece5") if is_pinned else config.RAIL_THEME.get("rail_bg", "#fbfaf8")

        app.pin_btn = tk.Button(
            rail, text="📌",
            font=("Segoe UI Symbol", sc(11)),
            bg=bg_color,
            fg=config.RAIL_THEME.get("icon_active_fg", "#000000"),
            activebackground=config.RAIL_THEME.get("icon_hover_bg", "#e9ece5"),
            bd=0, relief="flat", cursor="hand2",
            command=app.toggle_left_pin
        )
        app.pin_btn.pack(side="top", fill="x", pady=(sc(6), sc(4)), padx=sc(4))
        tooltip_text = "Collapse Sidebar (Ctrl+O)" if is_pinned else "Expand Sidebar (Ctrl+O)"
        app.add_tooltip(app.pin_btn, tooltip_text)

        # Alias for backward compatibility
        app.drawer_btn = app.pin_btn
