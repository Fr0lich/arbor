import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import re
from datetime import datetime
import pandas as pd
from PIL import Image, ImageTk
from io import BytesIO
import requests
from config import DATABASE_CONFIGS, sc, get_recent_files, add_recent_file
from utils import debug_error, fade_in_toplevel

class ZoomableImagePopup:
    def __init__(self, parent, tk_img, source=None, is_online=False):
        self.top = tk.Toplevel(parent)
        self.top.title("Image")

        self._scale = getattr(parent, "_scale", 1.0)
        self._compact = False
        self._last_scale = self._scale
        self._zoom_job = None
        self._resize_job = None

        self.canvas = tk.Canvas(self.top, bg="black")
        self.canvas.pack(fill="both", expand=True)

        # ✅ Original PIL-image (kritisk), starter med thumbnail
        self.orig_img = ImageTk.getimage(tk_img)

        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self._drag_start = None
        self.tk_img = None
        self.img_id = None
        self.source = source
        self.is_online = is_online
        self._stop_event = threading.Event()
        
        # Slett referanser når vinduet lukkes for å unngå minnelekkasje
        self.top.bind("<Destroy>", self._on_close)
        self.top.bind("<Configure>", self._fit_to_window)
        self.canvas.bind("<MouseWheel>", self._on_zoom)
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._do_pan)

        self._fit_to_window()

        if self.source:
            self.top.title("Loading full resolution...")
            threading.Thread(target=self._load_full_res, daemon=True).start()

        fade_in_toplevel(self.top)


    def _on_close(self, event=None):
        if hasattr(self, "_zoom_job") and self._zoom_job:
            try:
                self.top.after_cancel(self._zoom_job)
            except Exception:
                pass
        if hasattr(self, "_resize_job") and self._resize_job:
            try:
                self.top.after_cancel(self._resize_job)
            except Exception:
                pass
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
        self.orig_img = None
        self.tk_img = None

    def _load_full_res(self):
        try:
            if self.is_online:
                r = requests.get(self.source, stream=True, timeout=10)
                if r.status_code == 200:
                    img_data = bytearray()
                    for chunk in r.iter_content(chunk_size=8192):
                        if self._stop_event.is_set():
                            r.close()
                            return
                        img_data.extend(chunk)
                    full_img = Image.open(BytesIO(img_data))
                    full_img.load()
                else:
                    full_img = None
            else:
                full_img = Image.open(self.source)
                full_img.load()
            
            if full_img:
                self.top.after(0, lambda: self._apply_full_res(full_img))
        except Exception as e:
            if not getattr(self, "_stop_event", None) or not self._stop_event.is_set():
                self.top.after(0, lambda: self.top.title("Image (Failed to load full res)"))

    def _apply_full_res(self, full_img):
        if not self.top.winfo_exists():
            return
        self.orig_img = full_img
        self.top.title("Image (Full Resolution)")
        self._fit_to_window()

    def _fit_to_window(self, event=None):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        iw, ih = self.orig_img.size
        self.scale = min(cw / iw, ch / ih)
        self.offset_x = (cw - iw * self.scale) / 2
        self.offset_y = (ch - ih * self.scale) / 2

        # Debounce the high quality configure/resize events
        if hasattr(self, "_resize_job") and self._resize_job:
            try:
                self.top.after_cancel(self._resize_job)
            except Exception:
                pass
            self._resize_job = None

        self._redraw(scale_changed=True, fast_filter=True)
        self._resize_job = self.top.after(200, self._high_quality_resize)

    def _high_quality_resize(self):
        self._resize_job = None
        self._redraw(scale_changed=True, fast_filter=False)

    def _redraw(self, scale_changed=True, fast_filter=False):
        if scale_changed or not self.tk_img or not self.img_id:
            w = int(self.orig_img.width * self.scale)
            h = int(self.orig_img.height * self.scale)

            if w < 1 or h < 1:
                return

            filter_type = Image.NEAREST if fast_filter else Image.LANCZOS
            resized = self.orig_img.resize((w, h), filter_type)
            self.tk_img = ImageTk.PhotoImage(resized)

            self.canvas.delete("all")
            self.img_id = self.canvas.create_image(
                self.offset_x,
                self.offset_y,
                anchor="nw",
                image=self.tk_img
            )
        else:
            if self.img_id:
                self.canvas.coords(self.img_id, self.offset_x, self.offset_y)

    def _on_zoom(self, event):
        factor = 1.1 if event.delta > 0 else 0.9

        old_scale = self.scale
        self.scale *= factor

        mx, my = event.x, event.y
        self.offset_x = mx - (mx - self.offset_x) * (self.scale / old_scale)
        self.offset_y = my - (my - self.offset_y) * (self.scale / old_scale)

        if hasattr(self, "_zoom_job") and self._zoom_job:
            try:
                self.top.after_cancel(self._zoom_job)
            except Exception:
                pass
            self._zoom_job = None

        self._redraw(scale_changed=True, fast_filter=True)
        self._zoom_job = self.top.after(200, self._high_quality_redraw)

    def _high_quality_redraw(self):
        self._zoom_job = None
        self._redraw(scale_changed=True, fast_filter=False)

    def _start_pan(self, event):
        self._drag_start = (event.x, event.y)

    def _do_pan(self, event):
        if not self._drag_start:
            return

        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]

        self.offset_x += dx
        self.offset_y += dy
        self._drag_start = (event.x, event.y)

        self._redraw(scale_changed=False)

# =====================
# SETUP UI
# =====================


class StartupDialog:
    """
    Stitch-styled startup launcher dialog.
    Layout:
        win (bg=surface) → centered card (bg=white, 1px outline border)
            header  → arbor + Project Setup
            body    → 3 streamlined sections: Database (+ Profile & Wizard), Image Source, Recent Projects
            footer  → Help | Mobile Companion | LAUNCH SYSTEM
    """

    # ------------------------------------------------------------------
    # Stitch palette tokens (raw tk — not ttk.Style dependent)
    # ------------------------------------------------------------------
    C_BG          = "#fbfaf8"   # surface / window background
    C_CARD        = "#ffffff"   # surface-container-lowest
    C_HEADER_BG   = "#fbfaf8"   # surface
    C_FOOTER_BG   = "#f2f5f1"   # surface-container-low
    C_SURFACE_LOW = "#f2f5f1"   # section header rows
    C_OUTLINE     = "#747878"   # outline — field borders, card border
    C_OUTLINE_VAR = "#c4c7c7"   # outline-variant — separator lines
    C_ON_SURFACE  = "#2c302e"   # primary text
    C_ON_VARIANT  = "#444748"   # secondary text / labels
    C_PRIMARY     = "#000000"   # black — title, active toggle, LAUNCH bg
    C_ON_PRIMARY  = "#ffffff"   # white — LAUNCH text
    C_HOVER       = "#e9ece5"   # surface-container-highest — hover state

    # ------------------------------------------------------------------

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app

        import config as _cfg
        self._scale = getattr(_cfg, "_detected_scale", 1.0)

        # ── Window shell ──────────────────────────────────────────────
        self.win = tk.Toplevel(parent)
        self.win.title("arbor — Project Setup")
        self.win.resizable(True, True)

        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        min_w = min(480, max(360, screen_w - 40))
        min_h = min(520, max(400, screen_h - 80))
        self.win.minsize(min_w, min_h)
        self.win.configure(bg=self.C_BG)

        # Force to front
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.after(500, lambda: self.win.attributes("-topmost", False))
        self.win.focus_force()

        self.completed = False
        self.mobile_mode = False
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

        # State vars
        self.db_path_var      = tk.StringVar()
        self.db_var           = tk.StringVar()
        self.image_mode       = tk.StringVar(value="folder")
        self.image_folder_var = tk.StringVar()

        # Pre-populate DB path from last used
        last = _cfg.get_last_dir("last_db_dir")
        if last and os.path.isfile(last):
            self.db_path_var.set(last)
            self._auto_detect_config(last)

        # Pre-populate image folder path from last used
        last_img_dir = _cfg.get_last_dir("last_image_dir")
        if last_img_dir and os.path.isdir(last_img_dir):
            self.image_folder_var.set(last_img_dir)

        # ── Build card ────────────────────────────────────────────────
        self._build_window()

        # Center after build so winfo_reqwidth() is accurate
        self.win.update_idletasks()
        import utils

        w = int(640 * self._scale)
        h = int(640 * self._scale)

        self.win.geometry(f"{w}x{h}")
        utils.center_and_fit_toplevel(self.win, w, h)

        # Refresh LAUNCH state based on pre-populated path
        self._refresh_launch_state()

        # Tutorial Prompt Hook
        from ui.tutorial import TutorialManager
        tm = TutorialManager()
        prefs = _cfg.load_prefs()
        if not prefs.get("tutorial_skipped", False):
            self.win.after(1000, lambda: tm.start_tutorial("startup_tutorial", self.win))

    # ------------------------------------------------------------------
    # Window construction
    # ------------------------------------------------------------------

    def _build_window(self):
        s = self._scale

        # Card frame (white, 1px outline border)
        card = tk.Frame(
            self.win,
            bg=self.C_CARD,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
            highlightcolor=self.C_OUTLINE,
        )
        self._card = card
        card.pack(fill="both", expand=True, padx=int(12*s), pady=int(12*s))

        # 1. Pinned Header at top (always visible)
        self._build_header(card)

        # 2. Pinned Footer at bottom (always visible)
        self._build_footer(card)

        # 3. Middle Scrollable Container for Body
        container = tk.Frame(card, bg=self.C_CARD)
        container.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(container, bg=self.C_CARD, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        canvas.configure(yscrollcommand=scrollbar.set)

        # Scrollable inner frame (bg = white)
        outer = tk.Frame(canvas, bg=self.C_CARD)
        self._outer = outer  

        canvas_win_id = canvas.create_window((0, 0), window=outer, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_win_id, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_outer_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        outer.bind("<Configure>", _on_outer_configure)

        # Build body inside the scrollable inner frame
        self._build_body(outer)

        # Bind mousewheel recursively to canvas and all child widgets
        self._bind_canvas_mousewheel(canvas, outer)

    def _bind_canvas_mousewheel(self, canvas, frame=None):
        """Bind mousewheel using a custom bindtag instead of recursive widget walking."""
        tag = "StartupDialogScroll"
        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        canvas.bind_class(tag, "<MouseWheel>", _on_mousewheel)

        def _apply_tag(w):
            current_tags = list(w.bindtags())
            if tag not in current_tags:
                w.bindtags((tag,) + tuple(current_tags))
            for child in w.winfo_children():
                _apply_tag(child)

        canvas.bind("<MouseWheel>", _on_mousewheel)
        if frame:
            _apply_tag(frame)

    def _sep(self, parent, color=None, vertical=False):
        """1px separator line."""
        color = color or self.C_OUTLINE_VAR
        if vertical:
            tk.Frame(parent, bg=color, width=1).pack(side="left", fill="y")
        else:
            tk.Frame(parent, bg=color, height=1).pack(fill="x")

    def _label_md(self, parent, text, **kw):
        """label-md: Courier New 9 bold, on-surface-variant."""
        return tk.Label(
            parent, text=text,
            bg=kw.pop("bg", self.C_CARD),
            fg=kw.pop("fg", self.C_ON_VARIANT),
            font=("Courier New", sc(9), "bold"),
            anchor="w", **kw
        )

    def _mono(self, parent, text="", **kw):
        """data-mono: Courier New 10."""
        return tk.Label(
            parent, text=text,
            bg=kw.pop("bg", self.C_CARD),
            fg=kw.pop("fg", self.C_ON_SURFACE),
            font=("Courier New", sc(10)),
            anchor="w", **kw
        )

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self, card):
        s = self._scale
        header = tk.Frame(card, bg=self.C_HEADER_BG, padx=int(16*s), pady=int(12*s))
        header.pack(fill="x")

        tk.Label(
            header, text="arbor",
            bg=self.C_HEADER_BG, fg=self.C_PRIMARY,
            font=("Courier New", sc(9), "bold"),
            anchor="w"
        ).pack(anchor="w")

        tk.Label(
            header, text="Project Setup",
            bg=self.C_HEADER_BG, fg=self.C_ON_SURFACE,
            font=("Segoe UI", sc(18), "bold"),
            anchor="w"
        ).pack(anchor="w", pady=(int(2*s), 0))

        self._sep(header, self.C_OUTLINE_VAR)

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------

    def _build_body(self, card):
        s = self._scale
        body = tk.Frame(card, bg=self.C_CARD, padx=int(16*s), pady=int(16*s))
        body.pack(fill="both", expand=True)

        # 1 — Select Database & Configuration Profile
        self._build_database_section(body)
        tk.Frame(body, bg=self.C_CARD, height=int(18*s)).pack()  # spacer

        # 2 — Image Source toggle
        self._build_image_source(body)
        tk.Frame(body, bg=self.C_CARD, height=int(20*s)).pack()  # spacer

        # 3 — Recent Projects
        self._build_recent_table(body)

    # ------------------------------------------------------------------
    # Section Header helper
    # ------------------------------------------------------------------

    def _build_section_header(self, parent, text, status_type=None):
        s = self._scale
        header_frame = tk.Frame(parent, bg=self.C_CARD)
        header_frame.pack(anchor="w", fill="x", pady=(0, int(4*s)))

        # Determine badge text and color
        badge_text = ""
        badge_color = ""
        if status_type == "required":
            badge_text = " REQUIRED "
            badge_color = "#c93a40"  # Red
        elif status_type == "recommended":
            badge_text = " RECOMMENDED "
            badge_color = "#3a7d44"  # Green
        elif status_type == "optional":
            badge_text = " OPTIONAL "
            badge_color = "#747878"  # Gray

        if badge_text:
            badge_lbl = tk.Label(
                header_frame, text=badge_text,
                bg=badge_color, fg="#ffffff",
                font=("Courier New", sc(8), "bold"),
                padx=4, pady=1
            )
            badge_lbl.pack(side="left", padx=(0, 6))

        lbl = tk.Label(
            header_frame, text=text,
            bg=self.C_CARD,
            fg=self.C_ON_VARIANT,
            font=("Courier New", sc(9), "bold"),
            anchor="w"
        )
        lbl.pack(side="left")

        return header_frame

    # ------------------------------------------------------------------
    # Database Section (File Entry + Profile Dropdown + New DB Button)
    # ------------------------------------------------------------------

    def _build_database_section(self, parent):
        s = self._scale
        self._build_section_header(parent, "Select Database", status_type="required")

        # Database File Entry Row
        row = tk.Frame(parent, bg=self.C_CARD)
        row.tutorial_id = "db_path_entry"
        row.pack(fill="x", expand=True)

        entry = tk.Entry(
            row,
            textvariable=self.db_path_var,
            readonlybackground=self.C_SURFACE_LOW,
            bg=self.C_SURFACE_LOW,
            fg=self.C_ON_SURFACE,
            font=("Courier New", sc(10)),
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
            highlightcolor=self.C_PRIMARY,
            state="readonly",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=int(6*s))

        # Placeholder update
        placeholder = "No database file selected..."
        def _update_placeholder(*_):
            val = self.db_path_var.get()
            if not val:
                entry.config(state="normal")
                entry.delete(0, "end")
                entry.insert(0, placeholder)
                entry.config(state="readonly", fg=self.C_OUTLINE)
            else:
                entry.config(fg=self.C_ON_SURFACE)
        self.db_path_var.trace_add("write", _update_placeholder)
        _update_placeholder()

        # Browse button
        browse_btn = tk.Button(
            row,
            text="…",
            bg=self.C_HEADER_BG,
            fg=self.C_ON_VARIANT,
            font=("Segoe UI", sc(11)),
            relief="flat",
            bd=0,
            cursor="hand2",
            width=3,
            command=self.browse_database,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
        )
        browse_btn.pack(side="right", ipady=int(5*s))
        browse_btn.bind("<Enter>", lambda e: browse_btn.config(bg=self.C_HOVER))
        browse_btn.bind("<Leave>", lambda e: browse_btn.config(bg=self.C_HEADER_BG))

        self.db_path_var.trace_add("write", lambda *_: self._refresh_launch_state())

        # Sub-row for Actions and Database Profile selection
        sub_row = tk.Frame(parent, bg=self.C_CARD)
        sub_row.pack(fill="x", pady=(int(8*s), 0))

        # Prominent "+ Create New Database" button
        create_btn = tk.Button(
            sub_row,
            text="+ Create New Database",
            bg=self.C_SURFACE_LOW,
            fg=self.C_PRIMARY,
            font=("Segoe UI", sc(9), "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=int(10*s),
            pady=int(4*s),
            command=self.create_new_database_startup,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE
        )
        create_btn.pack(side="left")
        create_btn.bind("<Enter>", lambda e: create_btn.config(bg=self.C_HOVER))
        create_btn.bind("<Leave>", lambda e: create_btn.config(bg=self.C_SURFACE_LOW))

        # Database Profile / Config selector on right
        profile_frame = tk.Frame(sub_row, bg=self.C_CARD)
        profile_frame.pack(side="right")

        tk.Label(
            profile_frame,
            text="Profile:",
            bg=self.C_CARD,
            fg=self.C_ON_VARIANT,
            font=("Segoe UI", sc(9), "bold")
        ).pack(side="left", padx=(0, 4))

        db_names = list(DATABASE_CONFIGS.keys())
        if not self.db_var.get() and db_names:
            self.db_var.set(db_names[0])

        self.db_dropdown = ttk.Combobox(
            profile_frame,
            textvariable=self.db_var,
            values=db_names,
            state="readonly",
            cursor="hand2",
            width=18
        )
        self.db_dropdown.pack(side="left")

    def _auto_detect_config(self, path):
        """Auto-detect database configuration from filename, updating self.db_var."""
        if not path:
            return
        basename = os.path.basename(path).lower()
        for name in DATABASE_CONFIGS.keys():
            if name.lower() in basename or basename in name.lower():
                self.db_var.set(name)
                return
        # If no substring match, default to first available
        if DATABASE_CONFIGS and not self.db_var.get():
            self.db_var.set(next(iter(DATABASE_CONFIGS)))

    # ------------------------------------------------------------------
    # Image Source 3-segment toggle
    # ------------------------------------------------------------------

    def _build_image_source(self, parent):
        s = self._scale
        
        # Container frame for everything in the image source section
        self._image_source_container = tk.Frame(parent, bg=self.C_CARD)
        self._image_source_container.tutorial_id = "image_source_frame"
        self._image_source_container.pack(fill="x")
        
        self._build_section_header(self._image_source_container, "Image Source", status_type="recommended")

        toggle_outer = tk.Frame(
            self._image_source_container,
            bg=self.C_CARD,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
        )
        toggle_outer.pack(fill="x")

        segments = [
            ("Online Repository", "online"),
            ("Local Directory",   "folder"),
            ("Offline (No Images)", "offline"),
        ]

        self._seg_buttons = {}

        for i, (label, mode) in enumerate(segments):
            btn = tk.Button(
                toggle_outer,
                text=label,
                font=("Courier New", sc(9), "bold"),
                relief="flat", bd=0, cursor="hand2",
                command=lambda m=mode: self._set_image_mode(m),
            )
            if i < len(segments) - 1:
                btn.pack(side="left", fill="both", expand=True, ipady=int(6*s))
                tk.Frame(toggle_outer, bg=self.C_OUTLINE, width=1).pack(side="left", fill="y")
            else:
                btn.pack(side="left", fill="both", expand=True, ipady=int(6*s))
            self._seg_buttons[mode] = btn

        # Local folder sub-row (hidden unless "folder" is selected)
        self._folder_row = tk.Frame(self._image_source_container, bg=self.C_CARD)
        self._build_folder_picker_row(self._folder_row)

        self._set_image_mode("folder")  # initial state

    def _build_folder_picker_row(self, parent):
        s = self._scale
        self._build_section_header(parent, "Local Image Directory")

        row = tk.Frame(parent, bg=self.C_CARD)
        row.pack(fill="x", expand=True)

        entry = tk.Entry(
            row,
            textvariable=self.image_folder_var,
            readonlybackground=self.C_SURFACE_LOW,
            bg=self.C_SURFACE_LOW,
            fg=self.C_ON_SURFACE,
            font=("Courier New", sc(10)),
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
            highlightcolor=self.C_PRIMARY,
            state="readonly",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=int(6*s))

        placeholder = "No folder selected..."
        def _update_folder_ph(*_):
            val = self.image_folder_var.get()
            if not val:
                entry.config(state="normal")
                entry.delete(0, "end")
                entry.insert(0, placeholder)
                entry.config(state="readonly", fg=self.C_OUTLINE)
            else:
                entry.config(fg=self.C_ON_SURFACE)
        self.image_folder_var.trace_add("write", _update_folder_ph)
        _update_folder_ph()

        btn = tk.Button(
            row,
            text="…",
            bg=self.C_HEADER_BG,
            fg=self.C_ON_VARIANT,
            font=("Segoe UI", sc(11)),
            relief="flat",
            bd=0,
            cursor="hand2",
            width=3,
            command=self.select_folder,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
        )
        btn.pack(side="right", ipady=int(5*s))
        btn.bind("<Enter>", lambda e: btn.config(bg=self.C_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(bg=self.C_HEADER_BG))

    def _set_image_mode(self, mode):
        self.image_mode.set(mode)

        # 1. Update button styles
        for m, btn in self._seg_buttons.items():
            if m == mode:
                btn.config(bg=self.C_PRIMARY, fg=self.C_ON_PRIMARY)
            else:
                btn.config(bg=self.C_CARD, fg=self.C_ON_VARIANT)
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.C_HOVER))
                btn.bind("<Leave>", lambda e, b=btn, bm=m: b.config(
                    bg=self.C_CARD if bm != self.image_mode.get() else self.C_PRIMARY
                ))

        # 2. Show / hide folder row
        if mode == "folder":
            if not self._folder_row.winfo_ismapped():
                self._folder_row.pack(fill="x", pady=(int(6 * self._scale), 0))
                self._folder_row.update_idletasks()
        else:
            if self._folder_row.winfo_ismapped():
                self._folder_row.pack_forget()

    # ------------------------------------------------------------------
    # Recent Projects table
    # ------------------------------------------------------------------

    def _build_recent_table(self, parent):
        s = self._scale
        self._label_md(parent, "Recent Projects", bg=self.C_CARD).pack(
            anchor="w", pady=(0, int(4*s))
        )

        table = tk.Frame(
            parent,
            bg=self.C_CARD,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
        )
        table.pack(fill="both", expand=True)

        # Table header row
        hdr = tk.Frame(table, bg=self.C_SURFACE_LOW, height=int(28*s))
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self._label_md(hdr, "FILE PATH", bg=self.C_SURFACE_LOW).pack(
            side="left", padx=int(8*s), anchor="w"
        )
        self._sep(table, self.C_OUTLINE)

        # Rows
        recent = get_recent_files()

        if not recent:
            empty = tk.Frame(table, bg=self.C_CARD, height=int(28*s))
            empty.pack(fill="x")
            empty.pack_propagate(False)
            tk.Label(
                empty, text="No recent projects",
                bg=self.C_CARD, fg=self.C_ON_VARIANT,
                font=("Courier New", sc(9)), anchor="w"
            ).pack(side="left", padx=int(8*s), anchor="center")
        else:
            for i, entry in enumerate(recent[:5]):
                path = entry.get("path", "")
                self._build_recent_row(table, path, i)

    def _build_recent_row(self, table, path, index):
        s = self._scale
        row = tk.Frame(table, bg=self.C_CARD, height=int(28*s), cursor="hand2")
        row.pack(fill="x")
        row.pack_propagate(False)

        path_lbl = tk.Label(
            row, text=path,
            bg=self.C_CARD, fg=self.C_ON_SURFACE,
            font=("Courier New", sc(9)),
            anchor="w", cursor="hand2"
        )
        path_lbl.pack(side="left", padx=int(8*s), fill="x", expand=True)

        # Hover + click for each widget in the row
        def _hover_on(e):
            row.config(bg=self.C_HOVER)
            path_lbl.config(bg=self.C_HOVER, fg=self.C_PRIMARY)

        def _hover_off(e):
            row.config(bg=self.C_CARD)
            path_lbl.config(bg=self.C_CARD, fg=self.C_ON_SURFACE)

        def _click(e, p=path):
            self.select_recent(p)

        for widget in (row, path_lbl):
            widget.bind("<Enter>", _hover_on)
            widget.bind("<Leave>", _hover_off)
            widget.bind("<Button-1>", _click)

        # Separator between rows (skip after last)
        self._sep(table, self.C_OUTLINE_VAR)

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _build_footer(self, card):
        s = self._scale
        footer = tk.Frame(card, bg=self.C_FOOTER_BG, padx=int(16*s), pady=int(10*s))
        footer.pack(side="bottom", fill="x", expand=False)

        sep = tk.Frame(card, bg=self.C_OUTLINE_VAR, height=1)
        sep.pack(side="bottom", fill="x")

        # Ready status label above buttons (aligned right, inside footer)
        self.ready_status_label = tk.Label(
            footer, text="",
            bg=self.C_FOOTER_BG,
            font=("Segoe UI", sc(9), "bold"),
            anchor="e"
        )
        self.ready_status_label.pack(side="top", fill="x", pady=(0, int(4*s)))

        # Progress bar (hidden by default)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            footer, variable=self.progress_var, maximum=100
        )

        # HELP button (Secondary style: outline/flat, aligned left)
        self.help_btn = tk.Button(
            footer,
            text="Help",
            bg=self.C_CARD,
            fg=self.C_ON_SURFACE,
            font=("Segoe UI", sc(10), "bold"),
            relief="flat", bd=0,
            padx=int(16*s), pady=int(6*s),
            cursor="hand2",
            command=self.show_help,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
        )
        self.help_btn.pack(side="left", padx=(0, 10))
        self.help_btn.bind("<Enter>", lambda e: self.help_btn.config(bg=self.C_HOVER))
        self.help_btn.bind("<Leave>", lambda e: self.help_btn.config(bg=self.C_FOOTER_BG))

        # Status label for loading messages
        self.status_label = tk.Label(
            footer, text="",
            bg=self.C_FOOTER_BG, fg=self.C_ON_VARIANT,
            font=("Segoe UI", sc(9)), anchor="w"
        )
        self.status_label.pack(side="left", padx=int(10*s))

        # LAUNCH SYSTEM button (Primary style: black bg, white text)
        self.continue_btn = tk.Button(
            footer,
            text="LAUNCH SYSTEM",
            bg=self.C_PRIMARY,
            fg=self.C_ON_PRIMARY,
            font=("Segoe UI", sc(10), "bold"),
            relief="flat", bd=0,
            padx=int(24*s), pady=int(8*s),
            cursor="hand2",
            state="disabled",
            command=self.finish,
            highlightthickness=0,
        )
        self.continue_btn.tutorial_id = "launch_button"
        self.continue_btn.pack(side="right")
        self.continue_btn.bind("<Enter>", lambda e: self._launch_hover(True))
        self.continue_btn.bind("<Leave>", lambda e: self._launch_hover(False))

        # 📱 Mobile Companion button (Secondary accent: emerald green)
        self.mobile_mode_btn = tk.Button(
            footer,
            text="📱 Mobile Companion",
            bg="#2d6a4f",
            fg="#ffffff",
            font=("Segoe UI", sc(10), "bold"),
            relief="flat", bd=0,
            padx=int(16*s), pady=int(8*s),
            cursor="hand2",
            state="disabled",
            command=self.launch_mobile_mode,
            highlightthickness=0,
        )
        self.mobile_mode_btn.pack(side="right", padx=(0, 10))
        self.mobile_mode_btn.bind("<Enter>", lambda e: self.mobile_mode_btn.config(bg="#1b4332") if str(self.mobile_mode_btn.cget("state")) != "disabled" else None)
        self.mobile_mode_btn.bind("<Leave>", lambda e: self.mobile_mode_btn.config(bg="#2d6a4f") if str(self.mobile_mode_btn.cget("state")) != "disabled" else None)

    def launch_mobile_mode(self):
        path = self.db_path_var.get().strip()
        if not path or path == "No database file selected...":
            messagebox.showerror("Error", "Please select a database file first.")
            return

        if not self._resolve_config_and_path(path):
            return

        self.mobile_mode = True
        self.completed = True
        self.win.destroy()

    def _launch_hover(self, entering):
        state = str(self.continue_btn.cget("state"))
        if state == "disabled":
            return
        self.continue_btn.config(bg="#333333" if entering else self.C_PRIMARY)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _refresh_launch_state(self):
        path = self.db_path_var.get().strip()
        valid = bool(path) and path != "No database file selected..."
        self.continue_btn.config(state="normal" if valid else "disabled")
        if hasattr(self, "mobile_mode_btn"):
            self.mobile_mode_btn.config(state="normal" if valid else "disabled")
            self.mobile_mode_btn.config(bg="#2d6a4f" if valid else "#888888")
        if valid:
            self.continue_btn.config(bg=self.C_PRIMARY)
            if hasattr(self, "ready_status_label"):
                self.ready_status_label.config(text="Ready to launch!", fg="#3a7d44")
        else:
            self.continue_btn.config(bg="#888888")
            if hasattr(self, "ready_status_label"):
                self.ready_status_label.config(text="Please select a database file.", fg="#c93a40")

    def _show_progress(self, show=True):
        if show:
            self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        else:
            self.progress_bar.pack_forget()
            self.progress_var.set(0)

    # ------------------------------------------------------------------
    # Browse / select commands
    # ------------------------------------------------------------------

    def browse_database(self):
        import config
        path = filedialog.askopenfilename(
            title="Select Database File",
            filetypes=[("Database files", "*.xlsx *.db *.sqlite")],
            initialdir=config.get_last_dir("last_db_dir")
        )
        if not path:
            return
        config.set_last_dir("last_db_dir", path)
        self.db_path_var.set(path)
        self._auto_detect_config(path)
        self._refresh_launch_state()

        # Check for autosave
        base, _ = os.path.splitext(path)
        autosave_path = base + ".autosave.json"
        if not os.path.exists(autosave_path):
            autosave_path = base + ".autosave.xlsx"

        if os.path.exists(autosave_path):
            try:
                autosave_time = datetime.fromtimestamp(os.path.getmtime(autosave_path))
                res = messagebox.askyesno(
                    "Autosave found",
                    f"An autosave was found from {autosave_time.strftime('%d.%m.%Y %H:%M')}.\n\n"
                    f"Do you want to recover from autosave?\n\n"
                    f"(Click No to open the original file)"
                )
                if res:
                    self.db_path_var.set(autosave_path)
            except Exception:
                pass

    def select_folder(self):
        import config
        folder = filedialog.askdirectory(
            initialdir=config.get_last_dir("last_image_dir")
        )
        if folder:
            config.set_last_dir("last_image_dir", folder)
            self.image_folder_var.set(folder)

    def select_recent(self, path):
        """Fill the DB path field from a recent-projects row click."""
        if not os.path.exists(path):
            messagebox.showwarning("File not found", f"Could not find:\n{path}")
            return
        self.db_path_var.set(path)
        self._auto_detect_config(path)
        self._refresh_launch_state()

    def create_new_database_startup(self):
        from ui.new_database_wizard import NewDatabaseWizard
        NewDatabaseWizard(self.win, self.app, self.on_new_db_created)

    def on_db_selected(self, event=None):
        if hasattr(self, "db_var") and self.db_var.get() == "<Create New Database...>":
            self.create_new_database_startup()

    def on_new_db_created(self, file_path=None, profile_name=None):
        from config import DATABASE_CONFIGS
        db_names = list(DATABASE_CONFIGS.keys())
        if hasattr(self, "db_dropdown"):
            self.db_dropdown["values"] = db_names
            if profile_name and profile_name in db_names:
                self.db_var.set(profile_name)
            elif db_names:
                self.db_var.set(db_names[-1])
        if file_path:
            self.db_path_var.set(file_path)
            self._refresh_launch_state()

    def on_close(self):
        self.completed = False
        self.win.destroy()

    def open_excel(self):
        self.browse_database()

    def safe_ui_call(self, func):
        try:
            root = self.parent.winfo_toplevel()
            if root.winfo_exists():
                root.after(0, func)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Finish / launch helpers
    # ------------------------------------------------------------------

    def _resolve_config_and_path(self, path):
        """Resolve database configuration profile and populate app.config."""
        selected_name = self.db_var.get().strip() if hasattr(self, "db_var") else None
        matched_config = DATABASE_CONFIGS.get(selected_name) if selected_name else None

        if matched_config is None:
            # Fall back to filename auto-detection
            basename = os.path.basename(path).lower()
            for name, cfg in DATABASE_CONFIGS.items():
                if name.lower() in basename or basename in name.lower():
                    matched_config = cfg
                    selected_name = name
                    break

        if matched_config is None and DATABASE_CONFIGS:
            # Fall back to first available config
            selected_name = next(iter(DATABASE_CONFIGS))
            matched_config = DATABASE_CONFIGS[selected_name]

        if matched_config is None:
            messagebox.showerror("Error", "No valid database configuration profile found.")
            return False

        self.app.config = matched_config
        self.app.config_name = selected_name
        self.selected_excel_path = path

        # Set image mode properties for main to read
        mode = self.image_mode.get()
        if mode == "folder" and not self.image_folder_var.get():
            messagebox.showerror("Error", "Please select a local image directory or switch to Online/Offline mode.")
            return False

        if mode == "folder":
            import config
            config.set_last_dir("last_image_dir", self.image_folder_var.get())

        self.image_mode_val = mode
        self.image_folder_val = self.image_folder_var.get()

        # Record in recent files
        add_recent_file(path)
        return True

    def finish(self):
        path = self.db_path_var.get().strip()
        if not path or path == "No database file selected...":
            messagebox.showerror("Error", "Please select a database file first.")
            return

        if not self._resolve_config_and_path(path):
            return

        self.completed = True
        self.win.update_idletasks()
        self.win.destroy()

    def show_help(self):
        import config
        prefs = config.load_prefs()
        disable_tutorials = prefs.get("disable_tutorials", False)

        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label="Setup Help", command=self._show_setup_help_msg)

        from ui.tutorial import TutorialManager
        if not disable_tutorials:
            menu.add_command(label="Start Tutorial", command=lambda: TutorialManager().start_tutorial("startup_tutorial", self.win))
            menu.add_command(label="Disable All Tutorials", command=self._toggle_disable_tutorials)
        else:
            menu.add_command(label="Enable Tutorials", command=self._toggle_disable_tutorials)

        try:
            if hasattr(self, "help_btn") and self.help_btn.winfo_exists():
                x = self.help_btn.winfo_rootx()
                y = self.help_btn.winfo_rooty() + self.help_btn.winfo_height()
            else:
                x = 100
                y = 100
            menu.tk_popup(x, y)
        except Exception:
            pass
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _toggle_disable_tutorials(self):
        import config
        prefs = config.load_prefs()
        curr = prefs.get("disable_tutorials", False)
        prefs["disable_tutorials"] = not curr
        config.save_prefs(prefs)

        if not curr:  # meaning we just set it to True (disabled)
            from ui.tutorial import TutorialManager
            TutorialManager().close_tutorial()
            messagebox.showinfo("Tutorials Disabled", "All interactive tutorials have been disabled globally.")
        else:
            messagebox.showinfo("Tutorials Enabled", "Interactive tutorials are now enabled.")

    def _show_setup_help_msg(self):
        messagebox.showinfo(
            "Setup Help",
            "SETUP STEPS\n\n"
            "REQUIRED\n"
            "1. Select or Create a Database\n"
            "   - Choose a .xlsx, .db, or .sqlite file\n"
            "   - Select or verify the matching Configuration Profile\n"
            "   - Or click '+ Create New Database' to build a custom schema\n\n"
            "RECOMMENDED\n"
            "2. Choose Image Source\n"
            "   - Online = images loaded from remote repository\n"
            "   - Local Directory = specify local high-res photo folder\n"
            "   - Offline = work without specimen imagery\n\n"
            "Click LAUNCH SYSTEM to start, or Mobile Companion to serve over LAN.\n\n"
            "TIP: You can change all settings later in the main application."
        )



# =====================
# SPLASH LOADING SCREEN
# =====================

class LoadingWindow:
    def __init__(self, parent_root, excel_path, ui):
        self.parent = parent_root
        self.ui = ui
        self.excel_path = excel_path
        
        self.win = tk.Toplevel(self.parent)
        self.win.title("arbor — Loading Database")

        # Determine theme palette
        is_dark = getattr(self.ui, "dark_mode_active", False)

        if is_dark:
            bg_color = "#181c19"
            fg_title = "#e8ebe9"
            fg_status = "#a6adc8"
            bar_trough = "#141715"
            bar_color = "#3a7d44"
            border_color = "#2c302e"
        else:
            bg_color = "#fbfaf8"
            fg_title = "#2c302e"
            fg_status = "#444748"
            bar_trough = "#e9ece5"
            bar_color = "#3a7d44"
            border_color = "#dadada"

        self.win.configure(bg=bg_color)
        self.win.resizable(False, False)
        
        # Center the splash window
        from config import sc
        import utils
        utils.center_and_fit_toplevel(self.win, sc(460), sc(190))
        
        # Prevent user closing it manually
        self.win.protocol("WM_DELETE_WINDOW", lambda: None)
        self.win.grab_set()

        # Inner container card with subtle 1px border
        card = tk.Frame(self.win, bg=bg_color, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=sc(10), pady=sc(10))
        
        # Header Label
        tk.Label(
            card,
            text="Initializing Application",
            font=("Segoe UI", sc(13), "bold"),
            bg=bg_color,
            fg=fg_title
        ).pack(pady=(sc(18), sc(6)))
        
        # Progress status label (saved as attribute to easily update)
        self.status_lbl = tk.Label(
            card,
            text="Loading Excel database...",
            font=("JetBrains Mono", sc(9)),
            bg=bg_color,
            fg=fg_status
        )
        self.status_lbl.pack(pady=(0, sc(12)))
        
        # Progress Bar
        style = ttk.Style(self.win)
        style.theme_use("clam")
        style.configure(
            "Splash.Horizontal.TProgressbar",
            troughcolor=bar_trough,
            background=bar_color,
            thickness=sc(8),
            borderwidth=0
        )
        self.progress_bar = ttk.Progressbar(
            card,
            style="Splash.Horizontal.TProgressbar",
            orient="horizontal",
            mode="determinate"
        )
        self.progress_bar.pack(fill="x", padx=sc(28), pady=(0, sc(16)))
        
        # Register on UI instance
        self.ui._loading_window = self
        
        # Start database load
        self.ui._show_progress("Loading database...", 100)
        self.ui.open_excel_from_path(excel_path)
        
    def update_progress_bar(self, value=None, maximum=None):
        if not self.win.winfo_exists():
            return
        if value is not None:
            self.progress_bar["value"] = value
        if maximum is not None:
            self.progress_bar["maximum"] = maximum
            
    def update_status_text(self, text):
        if not self.win.winfo_exists():
            return
        self.status_lbl.config(text=text)
                
    def finish(self, text="Ready"):
        # Unregister loading window
        self.ui._loading_window = None
        try:
            self.win.destroy()
        except Exception:
            pass
        
        # Show main window
        try:
            self.parent.attributes("-alpha", 1.0)
        except Exception:
            pass
        self.parent.deiconify()
        self.parent.state("zoomed")
        
        # Run tutorial manager
        from ui.tutorial import TutorialManager
        TutorialManager().continue_pending_tutorial(self.parent)


