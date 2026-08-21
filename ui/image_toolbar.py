"""
Image Toolbar Component for Arbor

Features:
  - Standard (Compact) and Large (Prominent icon-focused) button designs
  - Integrated Design Toggle pill ('Compact' <-> 'Large')
  - Rich hover effects, tooltips, & active click micro-interactions
  - Live Zoom & Rotation status badge in monospace typography
  - Full Light & Dark theme support following AI_UI_GUIDE.md tokens
  - Callback/Observer interface for host window integration
  - Standalone test harness with interactive canvas preview
"""

import tkinter as tk
import math
from typing import Dict, Callable, Optional

# Design Tokens from AI_UI_GUIDE.md
COLORS_LIGHT = {
    "surface": "#fbfaf8",
    "surface_container_low": "#f2f5f1",
    "surface_container": "#e9ece5",
    "surface_container_high": "#e9ece5",
    "surface_container_highest": "#e9ece5",
    "card_bg": "#ffffff",
    "on_surface": "#2c302e",
    "on_surface_variant": "#4c4546",
    "outline": "#7e7576",
    "outline_variant": "#cfc4c5",
    "primary": "#000000",
    "on_primary": "#ffffff",
    "primary_container": "#1b1b1b",
    "secondary": "#3a7d44",
    "on_secondary": "#ffffff",
    "secondary_container": "#adf0a6",
    "on_secondary_container": "#326f34",
    "badge_bg": "#e9ece5",
    "badge_fg": "#2c302e",
    "btn_bg": "#f2f5f1",
    "btn_fg": "#2c302e",
    "btn_border": "#cfc4c5",
    "btn_hover_bg": "#e9ece5",
    "btn_hover_border": "#7e7576",
    "btn_active_bg": "#3a7d44",
    "btn_active_fg": "#ffffff",
    "toggle_bg": "#e9ece5",
    "toggle_active_bg": "#000000",
    "toggle_active_fg": "#ffffff",
    "toggle_inactive_fg": "#4c4546",
    "tooltip_bg": "#2c302e",
    "tooltip_fg": "#ffffff"
}

COLORS_DARK = {
    "surface": "#181c19",
    "surface_container_low": "#212622",
    "surface_container": "#181c19",
    "surface_container_high": "#1e221f",
    "surface_container_highest": "#141715",
    "card_bg": "#1e221f",
    "on_surface": "#e8ebe9",
    "on_surface_variant": "#bac2de",
    "outline": "#45475a",
    "outline_variant": "#585b70",
    "primary": "#e8ebe9",
    "on_primary": "#181c19",
    "primary_container": "#141715",
    "secondary": "#a6e3a1",
    "on_secondary": "#181c19",
    "secondary_container": "#1e221f",
    "on_secondary_container": "#a6e3a1",
    "badge_bg": "#141715",
    "badge_fg": "#e8ebe9",
    "btn_bg": "#1e221f",
    "btn_fg": "#e8ebe9",
    "btn_border": "#45475a",
    "btn_hover_bg": "#141715",
    "btn_hover_border": "#a6e3a1",
    "btn_active_bg": "#a6e3a1",
    "btn_active_fg": "#181c19",
    "toggle_bg": "#141715",
    "toggle_active_bg": "#a6e3a1",
    "toggle_active_fg": "#181c19",
    "toggle_inactive_fg": "#bac2de",
    "tooltip_bg": "#e8ebe9",
    "tooltip_fg": "#181c19"
}


class Tooltip:
    """Simple non-intrusive tooltip on hover."""
    def __init__(self, widget: tk.Widget, text: str, get_colors_fn: Callable):
        self.widget = widget
        self.text = text
        self.get_colors = get_colors_fn
        self.tip_window = None

        self.widget.bind("<Enter>", self.show_tip, add="+")
        self.widget.bind("<Leave>", self.hide_tip, add="+")

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") if self.widget.bbox("insert") else (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 10
        y = y + self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        colors = self.get_colors()
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)

        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background=colors["tooltip_bg"],
            foreground=colors["tooltip_fg"],
            font=("Segoe UI", 8, "normal"),
            padx=6,
            pady=3
        )
        label.pack()

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class ImageToolbarButton(tk.Frame):
    """
    Custom styled image action button supporting Compact & Large visual modes,
    hover elevation, active click feedback, and tooltips.
    """

    def __init__(
        self,
        parent,
        icon: str,
        label: str,
        tooltip_text: str,
        command: Callable,
        mode: str = "standard",
        colors: dict = None,
        shortcut: str = ""
    ):
        super().__init__(parent, bg=colors["btn_bg"], cursor="hand2")
        self.parent = parent
        self.icon_symbol = icon
        self.label_text = label
        self.tooltip_text = tooltip_text
        self.command = command
        self.mode = mode
        self.colors = colors or COLORS_LIGHT
        self.shortcut = shortcut
        self._is_hovered = False

        self.configure(
            highlightthickness=1,
            highlightbackground=self.colors["btn_border"],
            highlightcolor=self.colors["btn_hover_border"]
        )

        # Build inner contents
        self.container = tk.Frame(self, bg=self.colors["btn_bg"])
        self.container.pack(fill="both", expand=True, padx=2, pady=2)

        self.icon_label = tk.Label(
            self.container,
            text=self.icon_symbol,
            bg=self.colors["btn_bg"],
            fg=self.colors["btn_fg"]
        )
        
        self.text_label = tk.Label(
            self.container,
            text=self.label_text,
            bg=self.colors["btn_bg"],
            fg=self.colors["on_surface_variant"]
        )

        self.update_mode(mode)
        self._bind_events()
        Tooltip(self, f"{tooltip_text} ({shortcut})" if shortcut else tooltip_text, lambda: self.colors)

    def update_mode(self, mode: str):
        self.mode = mode
        if mode == "large":
            self.icon_label.config(font=("Segoe UI", 13, "bold"))
            self.text_label.config(font=("Segoe UI", 8, "bold"))
            self.icon_label.pack(side="left", padx=(8, 4), pady=5)
            self.text_label.pack(side="left", padx=(0, 8), pady=5)
        else:
            self.icon_label.config(font=("Segoe UI", 9, "bold"))
            self.text_label.config(font=("Segoe UI", 8, "bold"))
            self.icon_label.pack(side="left", padx=(4, 2), pady=2)
            if self.label_text:
                self.text_label.pack(side="left", padx=(0, 4), pady=2)
            else:
                self.text_label.pack_forget()

        self._apply_colors()

    def update_colors(self, colors: dict):
        self.colors = colors
        self._apply_colors()

    def _apply_colors(self):
        bg = self.colors["btn_hover_bg"] if self._is_hovered else self.colors["btn_bg"]
        border = self.colors["btn_hover_border"] if self._is_hovered else self.colors["btn_border"]
        fg = self.colors["btn_fg"]
        fg_sub = self.colors["on_surface_variant"]

        self.config(bg=bg, highlightbackground=border)
        self.container.config(bg=bg)
        self.icon_label.config(bg=bg, fg=fg)
        self.text_label.config(bg=bg, fg=fg_sub)

    def _bind_events(self):
        for widget in (self, self.container, self.icon_label, self.text_label):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<ButtonPress-1>", self._on_press)
            widget.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, event=None):
        self._is_hovered = True
        self._apply_colors()

    def _on_leave(self, event=None):
        self._is_hovered = False
        self._apply_colors()

    def _on_press(self, event=None):
        active_bg = self.colors["btn_active_bg"]
        active_fg = self.colors["btn_active_fg"]
        self.config(bg=active_bg)
        self.container.config(bg=active_bg)
        self.icon_label.config(bg=active_bg, fg=active_fg)
        self.text_label.config(bg=active_bg, fg=active_fg)

    def _on_release(self, event=None):
        self._apply_colors()
        if self.command:
            self.command()


class SegmentedDesignToggle(tk.Frame):
    """Segmented pill switch allowing real-time swapping between 'Compact' and 'Large' button design modes."""

    def __init__(self, parent, current_mode: str = "standard", on_toggle: Callable = None, colors: dict = None):
        super().__init__(parent, bg=colors["toggle_bg"], highlightthickness=1, highlightbackground=colors["outline_variant"])
        self.current_mode = current_mode
        self.on_toggle = on_toggle
        self.colors = colors or COLORS_LIGHT

        self.btn_std = tk.Label(
            self,
            text="Compact",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=3,
            cursor="hand2"
        )
        self.btn_large = tk.Label(
            self,
            text="Large",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=3,
            cursor="hand2"
        )

        self.btn_std.pack(side="left", padx=2, pady=2)
        self.btn_large.pack(side="left", padx=2, pady=2)

        self.btn_std.bind("<Button-1>", lambda e: self.set_mode("standard"))
        self.btn_large.bind("<Button-1>", lambda e: self.set_mode("large"))

        self.update_colors(self.colors)

    def set_mode(self, mode: str):
        if self.current_mode != mode:
            self.current_mode = mode
            self._render_state()
            if self.on_toggle:
                self.on_toggle(mode)

    def update_colors(self, colors: dict):
        self.colors = colors
        self.config(bg=colors["toggle_bg"], highlightbackground=colors["outline_variant"])
        self._render_state()

    def _render_state(self):
        if self.current_mode == "standard":
            self.btn_std.config(
                bg=self.colors["toggle_active_bg"],
                fg=self.colors["toggle_active_fg"]
            )
            self.btn_large.config(
                bg=self.colors["toggle_bg"],
                fg=self.colors["toggle_inactive_fg"]
            )
        else:
            self.btn_std.config(
                bg=self.colors["toggle_bg"],
                fg=self.colors["toggle_inactive_fg"]
            )
            self.btn_large.config(
                bg=self.colors["toggle_active_bg"],
                fg=self.colors["toggle_active_fg"]
            )


class ImageToolbar(tk.Frame):
    """
    Complete Decoupled Image Toolbar Component.
    
    Provides:
      - Zoom In / Zoom Out / Rotate CW / Rotate CCW / Reset / Fit View buttons
      - Standard vs Large prominent design modes
      - Toggle switch for design modes
      - Monospace status indicator (Zoom % | Rotation Angle)
      - Dark/Light theme switching
      - Callback interface (`live_callbacks`)
    """

    def __init__(
        self,
        parent,
        live_callbacks: Optional[Dict[str, Callable]] = None,
        design_mode: str = "standard",
        dark_mode: bool = False,
        zoom_level: float = 1.0,
        rotation_angle: int = 0
    ):
        self.colors = COLORS_DARK if dark_mode else COLORS_LIGHT
        super().__init__(parent, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["outline_variant"])

        self.parent = parent
        self.live_callbacks = live_callbacks or {}
        self.design_mode = design_mode
        self.dark_mode = dark_mode
        self.zoom_level = zoom_level
        self.rotation_angle = rotation_angle

        self.buttons = {}
        self._build_ui()

    def _build_ui(self):
        self.inner_frame = tk.Frame(self, bg=self.colors["surface_container_low"])
        self.inner_frame.pack(fill="x", expand=True, padx=6, pady=4)

        # Left section: Button Group
        self.btn_container = tk.Frame(self.inner_frame, bg=self.colors["surface_container_low"])
        self.btn_container.pack(side="left", fill="y")

        btn_specs = [
            ("zoom_in", "➕", "Zoom In", "Zoom in on image canvas", self._handle_zoom_in, "Ctrl+Plus"),
            ("zoom_out", "➖", "Zoom Out", "Zoom out on image canvas", self._handle_zoom_out, "Ctrl+Minus"),
            ("rotate_cw", "↻", "Rotate 90°", "Rotate image clockwise", self._handle_rotate_cw, "Ctrl+R"),
            ("rotate_ccw", "↺", "Rotate -90°", "Rotate image counter-clockwise", self._handle_rotate_ccw, "Ctrl+Shift+R"),
            ("reset", "⟲", "Reset", "Reset zoom and rotation", self._handle_reset, "Esc"),
            ("fit", "⤢", "Fit View", "Fit image to viewport", self._handle_fit, "Double-Click"),
        ]

        for key, icon, label, tip, cmd, scut in btn_specs:
            btn = ImageToolbarButton(
                self.btn_container,
                icon=icon,
                label=label,
                tooltip_text=tip,
                command=cmd,
                mode=self.design_mode,
                colors=self.colors,
                shortcut=scut
            )
            btn.pack(side="left", padx=3)
            self.buttons[key] = btn

        # Right section: Status badge and Design Toggle
        self.right_container = tk.Frame(self.inner_frame, bg=self.colors["surface_container_low"])
        self.right_container.pack(side="right", fill="y")

        # Monospace status badge
        self.status_badge = tk.Label(
            self.right_container,
            text=self._format_status_text(),
            font=("Consolas", 9, "bold"),
            bg=self.colors["badge_bg"],
            fg=self.colors["badge_fg"],
            padx=8,
            pady=4,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["outline_variant"]
        )
        self.status_badge.pack(side="left", padx=(0, 8))

        # Design Mode Toggle
        self.toggle_widget = SegmentedDesignToggle(
            self.right_container,
            current_mode=self.design_mode,
            on_toggle=self._handle_design_toggle,
            colors=self.colors
        )
        self.toggle_widget.pack(side="left")

    def _format_status_text(self) -> str:
        pct = int(round(self.zoom_level * 100))
        deg = self.rotation_angle % 360
        return f"🔍 {pct}%  |  ↻ {deg}°"

    def set_status(self, zoom: float, rotation: int):
        self.zoom_level = zoom
        self.rotation_angle = rotation
        if hasattr(self, "status_badge"):
            self.status_badge.config(text=self._format_status_text())

    def set_design_mode(self, mode: str):
        if mode in ("standard", "large") and mode != self.design_mode:
            self.design_mode = mode
            for btn in self.buttons.values():
                btn.update_mode(mode)
            self.toggle_widget.set_mode(mode)

    def set_dark_mode(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.colors = COLORS_DARK if dark_mode else COLORS_LIGHT
        
        self.config(bg=self.colors["surface_container_low"], highlightbackground=self.colors["outline_variant"])
        self.inner_frame.config(bg=self.colors["surface_container_low"])
        self.btn_container.config(bg=self.colors["surface_container_low"])
        self.right_container.config(bg=self.colors["surface_container_low"])

        for btn in self.buttons.values():
            btn.update_colors(self.colors)

        self.status_badge.config(
            bg=self.colors["badge_bg"],
            fg=self.colors["badge_fg"],
            highlightbackground=self.colors["outline_variant"]
        )
        self.toggle_widget.update_colors(self.colors)

    # Callback handlers
    def _handle_zoom_in(self):
        cb = self.live_callbacks.get("zoom_in") or self.live_callbacks.get("on_zoom_in")
        if cb:
            cb()

    def _handle_zoom_out(self):
        cb = self.live_callbacks.get("zoom_out") or self.live_callbacks.get("on_zoom_out")
        if cb:
            cb()

    def _handle_rotate_cw(self):
        cb = self.live_callbacks.get("rotate_cw") or self.live_callbacks.get("on_rotate_cw") or self.live_callbacks.get("rotate")
        if cb:
            cb(90)

    def _handle_rotate_ccw(self):
        cb = self.live_callbacks.get("rotate_ccw") or self.live_callbacks.get("on_rotate_ccw")
        if cb:
            cb(-90)

    def _handle_reset(self):
        cb = self.live_callbacks.get("reset") or self.live_callbacks.get("on_reset")
        if cb:
            cb()

    def _handle_fit(self):
        cb = self.live_callbacks.get("fit") or self.live_callbacks.get("on_fit")
        if cb:
            cb()

    def _handle_design_toggle(self, mode: str):
        self.set_design_mode(mode)
        cb = self.live_callbacks.get("design_toggle") or self.live_callbacks.get("on_style_toggle")
        if cb:
            cb(mode)


def create_image_toolbar(
    parent,
    live_callbacks: Optional[Dict[str, Callable]] = None,
    design_mode: str = "standard",
    dark_mode: bool = False,
    zoom_level: float = 1.0,
    rotation_angle: int = 0
) -> ImageToolbar:
    """1-Line Plug-and-Play Launcher Function to create and return the ImageToolbar instance."""
    toolbar = ImageToolbar(
        parent=parent,
        live_callbacks=live_callbacks,
        design_mode=design_mode,
        dark_mode=dark_mode,
        zoom_level=zoom_level,
        rotation_angle=rotation_angle
    )
    return toolbar


# Standalone Test Harness
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Arbor Image Toolbar - Standalone Test Harness")
    root.geometry("920x650")
    root.configure(bg="#fbfaf8")

    # State variables for simulator
    state = {
        "zoom": 1.0,
        "rotation": 0,
        "dark": False,
        "mode": "standard"
    }

    # Header / Title Card
    header_card = tk.Frame(root, bg="#ffffff", highlightthickness=1, highlightbackground="#cfc4c5", padx=16, pady=12)
    header_card.pack(fill="x", padx=16, pady=(16, 8))

    tk.Label(header_card, text="Image Tool Buttons Redesign", font=("Lora", 16, "bold"), bg="#ffffff", fg="#2c302e").pack(anchor="w")
    tk.Label(header_card, text="Interactive preview testing Compact vs Large button styles, hover micro-interactions, dark mode, and live callbacks.", font=("Segoe UI", 9), bg="#ffffff", fg="#4c4546").pack(anchor="w")

    # Callback implementations for simulation
    def on_zoom_in():
        state["zoom"] = min(4.0, state["zoom"] * 1.25)
        toolbar.set_status(state["zoom"], state["rotation"])
        redraw_specimen()
        log_event(f"Action: Zoom In -> {int(state['zoom']*100)}%")

    def on_zoom_out():
        state["zoom"] = max(0.25, state["zoom"] / 1.25)
        toolbar.set_status(state["zoom"], state["rotation"])
        redraw_specimen()
        log_event(f"Action: Zoom Out -> {int(state['zoom']*100)}%")

    def on_rotate_cw(deg=90):
        state["rotation"] = (state["rotation"] + deg) % 360
        toolbar.set_status(state["zoom"], state["rotation"])
        redraw_specimen()
        log_event(f"Action: Rotate CW -> {state['rotation']}°")

    def on_rotate_ccw(deg=-90):
        state["rotation"] = (state["rotation"] + deg) % 360
        toolbar.set_status(state["zoom"], state["rotation"])
        redraw_specimen()
        log_event(f"Action: Rotate CCW -> {state['rotation']}°")

    def on_reset():
        state["zoom"] = 1.0
        state["rotation"] = 0
        toolbar.set_status(state["zoom"], state["rotation"])
        redraw_specimen()
        log_event("Action: Reset View")

    def on_fit():
        state["zoom"] = 1.0
        state["rotation"] = 0
        toolbar.set_status(state["zoom"], state["rotation"])
        redraw_specimen()
        log_event("Action: Fit View to Canvas")

    def on_style_toggle(mode):
        state["mode"] = mode
        log_event(f"Design Switch: Swapped to '{mode.upper()}' button style")

    callbacks = {
        "zoom_in": on_zoom_in,
        "zoom_out": on_zoom_out,
        "rotate_cw": on_rotate_cw,
        "rotate_ccw": on_rotate_ccw,
        "reset": on_reset,
        "fit": on_fit,
        "design_toggle": on_style_toggle
    }

    # Embed Toolbar Component
    toolbar_frame = tk.Frame(root, bg="#fbfaf8")
    toolbar_frame.pack(fill="x", padx=16, pady=4)

    toolbar = create_image_toolbar(
        toolbar_frame,
        live_callbacks=callbacks,
        design_mode="standard",
        dark_mode=False
    )
    toolbar.pack(fill="x", expand=True)

    # Simulated Interactive Canvas
    canvas_container = tk.Frame(root, bg="#ffffff", highlightthickness=1, highlightbackground="#cfc4c5")
    canvas_container.pack(fill="both", expand=True, padx=16, pady=8)

    canvas = tk.Canvas(canvas_container, bg="#212622" if state["dark"] else "#e9ece5", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    def redraw_specimen():
        canvas.delete("all")
        cw = canvas.winfo_width() or 600
        ch = canvas.winfo_height() or 300
        cx, cy = cw / 2, ch / 2

        bg_color = "#212622" if state["dark"] else "#e9ece5"
        canvas.config(bg=bg_color)

        # Draw grid
        grid_step = int(30 * state["zoom"])
        if grid_step > 5:
            grid_color = "#141715" if state["dark"] else "#e9ece5"
            for x in range(0, cw, grid_step):
                canvas.create_line(x, 0, x, ch, fill=grid_color)
            for y in range(0, ch, grid_step):
                canvas.create_line(0, y, cw, y, fill=grid_color)

        # Simulated Botanical Leaf Specimen
        r = 80 * state["zoom"]
        rad = math.radians(state["rotation"])
        
        # Main stem line
        dx = r * math.sin(rad)
        dy = -r * math.cos(rad)
        stem_color = "#a6e3a1" if state["dark"] else "#3a7d44"
        canvas.create_line(cx - dx, cy - dy, cx + dx, cy + dx, fill=stem_color, width=max(2, int(4 * state["zoom"])))

        # Specimen Oval / Leaf body
        lx1, ly1 = cx - r * 0.6 * state["zoom"], cy - r * state["zoom"]
        lx2, ly2 = cx + r * 0.6 * state["zoom"], cy + r * state["zoom"]
        canvas.create_oval(lx1, ly1, lx2, ly2, outline=stem_color, width=max(1, int(3 * state["zoom"])))

        # Specimen Label Text inside Canvas
        lbl_color = "#e8ebe9" if state["dark"] else "#2c302e"
        canvas.create_text(
            cx, cy,
            text=f"🌿 Botanical Specimen #O-V-OE-0042\nZoom: {int(state['zoom']*100)}% | Angle: {state['rotation']}°",
            fill=lbl_color,
            font=("Lora", max(8, int(11 * min(state["zoom"], 2.0))), "bold"),
            justify="center"
        )

    canvas.bind("<Configure>", lambda e: redraw_specimen())

    # Bottom Control Bar & Log Output
    bottom_frame = tk.Frame(root, bg="#fbfaf8")
    bottom_frame.pack(fill="x", padx=16, pady=(0, 16))

    def toggle_theme():
        state["dark"] = not state["dark"]
        toolbar.set_dark_mode(state["dark"])
        root.config(bg="#181c19" if state["dark"] else "#fbfaf8")
        header_card.config(bg="#1e221f" if state["dark"] else "#ffffff", highlightbackground="#45475a" if state["dark"] else "#cfc4c5")
        for child in header_card.winfo_children():
            child.config(bg="#1e221f" if state["dark"] else "#ffffff", fg="#e8ebe9" if state["dark"] else "#2c302e")
        toolbar_frame.config(bg="#181c19" if state["dark"] else "#fbfaf8")
        canvas_container.config(bg="#1e221f" if state["dark"] else "#ffffff", highlightbackground="#45475a" if state["dark"] else "#cfc4c5")
        bottom_frame.config(bg="#181c19" if state["dark"] else "#fbfaf8")
        dark_btn.config(text="☀️ Light Theme" if state["dark"] else "🌙 Dark Theme")
        redraw_specimen()
        log_event(f"Theme: Switched to {'Dark' if state['dark'] else 'Light'} mode")

    dark_btn = tk.Button(
        bottom_frame,
        text="🌙 Dark Theme",
        command=toggle_theme,
        font=("Segoe UI", 9, "bold"),
        bg="#3a7d44",
        fg="#ffffff",
        activebackground="#326f34",
        activeforeground="#ffffff",
        relief="flat",
        padx=10,
        pady=4,
        cursor="hand2"
    )
    dark_btn.pack(side="left")

    log_label = tk.Label(bottom_frame, text="Status: Ready", font=("Consolas", 9), bg="#fbfaf8", fg="#4c4546")
    log_label.pack(side="right", padx=8)

    def log_event(msg: str):
        log_label.config(text=f"Last Event: {msg}")

    root.mainloop()
