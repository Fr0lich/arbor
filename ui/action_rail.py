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

        # Action Rail buttons
        app.pin_btn = tk.Button(
            rail, text="📌",
            font=("Segoe UI Symbol", sc(11)),
            bg=config.RAIL_THEME.get("rail_bg", "#fbfaf8"),
            fg=config.RAIL_THEME.get("icon_active_fg", "#000000"),
            activebackground=config.RAIL_THEME.get("icon_hover_bg", "#e9ece5"),
            bd=0, relief="flat", cursor="hand2",
            command=app.toggle_left_pin
        )
        app.pin_btn.pack(side="top", fill="x", pady=(sc(6), sc(4)), padx=sc(4))
        app.add_tooltip(app.pin_btn, "Toggle Docked / Unpinned Focus Mode")

        app.drawer_btn = tk.Button(
            rail, text="🔍",
            font=("Segoe UI Symbol", sc(11)),
            bg=config.RAIL_THEME.get("rail_bg", "#fbfaf8"),
            fg=config.RAIL_THEME.get("icon_active_fg", "#000000"),
            activebackground=config.RAIL_THEME.get("icon_hover_bg", "#e9ece5"),
            bd=0, relief="flat", cursor="hand2",
            command=app.toggle_floating_drawer
        )
        app.drawer_btn.pack(side="top", fill="x", pady=sc(4), padx=sc(4))
        app.add_tooltip(app.drawer_btn, "Open Object Drawer (Ctrl+O)")

        app.filter_indicator = tk.Label(
            rail, text="⚡",
            font=("Segoe UI Symbol", sc(10), "bold"),
            bg=config.RAIL_THEME.get("rail_bg", "#fbfaf8"),
            fg=config.RAIL_THEME.get("indicator_active_bg", "#C62828"),
            bd=0
        )
        app.filter_indicator.pack(side="top", fill="x", pady=sc(4), padx=sc(4))
        app.filter_indicator.pack_forget()
