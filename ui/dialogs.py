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
            body    → 4 sections: DB path, Import, Image Source, Recent Projects
            footer  → LAUNCH SYSTEM (Primary.TButton style)
    """

    # ------------------------------------------------------------------
    # Stitch palette tokens (raw tk — not ttk.Style dependent)
    # ------------------------------------------------------------------
    C_BG          = "#f9f9f9"   # surface / window background
    C_CARD        = "#ffffff"   # surface-container-lowest
    C_HEADER_BG   = "#f9f9f9"   # surface
    C_FOOTER_BG   = "#f3f3f3"   # surface-container-low
    C_SURFACE_LOW = "#f3f3f3"   # section header rows
    C_OUTLINE     = "#747878"   # outline — field borders, card border
    C_OUTLINE_VAR = "#c4c7c7"   # outline-variant — separator lines
    C_ON_SURFACE  = "#1a1c1c"   # primary text
    C_ON_VARIANT  = "#444748"   # secondary text / labels
    C_PRIMARY     = "#000000"   # black — title, active toggle, LAUNCH bg
    C_ON_PRIMARY  = "#ffffff"   # white — LAUNCH text
    C_HOVER       = "#e2e2e2"   # surface-container-highest — hover state

    # ------------------------------------------------------------------

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app

        import config as _cfg
        self._scale = getattr(_cfg, "_detected_scale", 1.0)


        self._last_scale = self._scale
        self._compact = False


        # ── Window shell ──────────────────────────────────────────────
        self.win = tk.Toplevel(parent)
        self.win.title("arbor — Project Setup")
        self.win.resizable(True, True)
        self.win.minsize(500, 680)
        self.win.configure(bg=self.C_BG)

        self.win.bind("<Configure>", self._on_resize)

        # Force to front
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.after(500, lambda: self.win.attributes("-topmost", False))
        self.win.focus_force()

        self.completed = False
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

        # State vars
        self.db_path_var      = tk.StringVar()
        self.import_path_var  = tk.StringVar()
        self.image_mode       = tk.StringVar(value="online")
        self.image_folder_var = tk.StringVar()

        # Pre-populate DB path from last used
        last = _cfg.get_last_dir("last_db_dir")
        if last and os.path.isfile(last):
            self.db_path_var.set(last)

        # ── Build card ────────────────────────────────────────────────
        self._build_window()

        # Center after build so winfo_reqwidth() is accurate
        self.win.update_idletasks()
        import utils

        w = int(640 * self._scale)
        h = int(680 * self._scale)

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

        # Create container frame to house Canvas and Scrollbar
        container = tk.Frame(self.win, bg=self.C_BG)
        container.pack(fill="both", expand=True)

        # Create Canvas and Scrollbar
        canvas = tk.Canvas(container, bg=self.C_BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        canvas.configure(yscrollcommand=scrollbar.set)

        # Outer padding frame (bg = surface)
        outer = tk.Frame(canvas, bg=self.C_BG)
        self._outer = outer  

        # Create window inside canvas
        canvas_win_id = canvas.create_window((0, 0), window=outer, anchor="nw")

        # Keep outer width dynamically sized to match canvas width
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_win_id, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Update scrollregion when outer size changes
        def _on_outer_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        outer.bind("<Configure>", _on_outer_configure)

        # Card frame (white, 1px outline border)
        card = tk.Frame(
            outer,
            bg=self.C_CARD,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
            highlightcolor=self.C_OUTLINE,
        )
        self._card = card
        card.pack(fill="both", expand=True, padx=20, pady=20)

        self._build_header(card)
        self._build_body(card)
        self._build_footer(card)

        # Bind mouse wheel recursively to scroll canvas
        self._bind_mousewheel_recursive(self.win, canvas)

    def _bind_mousewheel_recursive(self, widget, canvas):
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        tag = f"MW_Tag_{id(widget)}"

        def _apply_tag(w):
            w.bindtags((tag,) + w.bindtags())
            for child in w.winfo_children():
                _apply_tag(child)

        _apply_tag(widget)
        widget.bind_class(tag, "<MouseWheel>", _on_mousewheel)

        def _on_destroy(event):
            if event.widget is widget:
                try:
                    widget.unbind_class(tag, "<MouseWheel>")
                except Exception:
                    pass

        widget.bind("<Destroy>", _on_destroy, add="+")


    def _sep(self, parent, color=None, vertical=False):
        """1px separator line."""
        color = color or self.C_OUTLINE_VAR
        orient = "horizontal" if not vertical else "vertical"
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

        # 1 — Select Database
        self._build_file_row(
            body,
            label_text="Select Database",
            path_var=self.db_path_var,
            entry_bg=self.C_SURFACE_LOW,
            placeholder=None,
            browse_cmd=self.browse_database,
            status_type="required",
            tutorial_id="db_path_entry",
            action_btn_text="+ Create New Database",
            action_cmd=self.create_new_database_startup
        )
        tk.Frame(body, bg=self.C_CARD, height=int(16*s)).pack()  # spacer

        # 2 — Import Excel/CSV (optional)
        self._build_file_row(
            body,
            label_text="Import Excel/CSV (Optional Data Source)",
            path_var=self.import_path_var,
            entry_bg=self.C_CARD,
            placeholder="No file selected...",
            browse_cmd=self.browse_import,
            status_type="optional",
        )
        tk.Frame(body, bg=self.C_CARD, height=int(16*s)).pack()  # spacer

        # 3 — Image Source toggle
        self._build_image_source(body)
        tk.Frame(body, bg=self.C_CARD, height=int(20*s)).pack()  # spacer

        # 4 — Recent Projects
        self._build_recent_table(body)
        tk.Frame(body, bg=self.C_CARD, height=int(8*s)).pack()   # spacer

        # Advanced link (Books / Historical DB — demoted)


        adv = tk.Button(
            body,
            text="Advanced Setup (Books / Historical databases)",
            bg=self.C_SURFACE_LOW,
            fg=self.C_ON_SURFACE,
            font=("Segoe UI", sc(9), "bold"),
            relief="flat",
            bd=0,
            anchor="w",
            cursor="hand2",
            padx=10,
            pady=6,
            command=self._show_advanced,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE
        )

        adv.pack(anchor="w", fill="x", pady=(6, 0))
        
        # Hover effect
        adv.bind("<Enter>", lambda e: adv.config(
            bg=self.C_HOVER,
            fg=self.C_PRIMARY
        ))
        adv.bind("<Leave>", lambda e: adv.config(
            bg=self.C_SURFACE_LOW,
            fg=self.C_ON_SURFACE
        ))

    # ------------------------------------------------------------------
    # Section Header helper
    # ------------------------------------------------------------------

    def _build_section_header(self, parent, text, status_type=None, action_btn_text=None, action_cmd=None):
        s = self._scale
        header_frame = tk.Frame(parent, bg=self.C_CARD)
        header_frame.pack(anchor="w", fill="x", pady=(0, int(2*s)))

        # Determine badge text and color
        badge_text = ""
        badge_color = ""
        if status_type == "required":
            badge_text = " REQUIRED "
            badge_color = "#ba1a1a" # Red
        elif status_type == "recommended":
            badge_text = " RECOMMENDED "
            badge_color = "#3b6934" # Green
        elif status_type == "optional":
            badge_text = " OPTIONAL "
            badge_color = "#747878" # Gray

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

        if action_btn_text and action_cmd:
            btn = tk.Button(
                header_frame, text=action_btn_text,
                bg=self.C_SURFACE_LOW, fg=self.C_PRIMARY,
                font=("Segoe UI", sc(8.5), "bold"),
                relief="flat", bd=0, cursor="hand2",
                padx=sc(6), pady=sc(1),
                command=action_cmd,
                highlightthickness=1, highlightbackground=self.C_OUTLINE
            )
            btn.pack(side="right")
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.C_HOVER))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.C_SURFACE_LOW))

        return header_frame

    # ------------------------------------------------------------------
    # File-row helper (label + entry + browse button)
    # ------------------------------------------------------------------

    def _build_file_row(self, parent, label_text, path_var, entry_bg,
                        placeholder, browse_cmd, status_type=None, tutorial_id=None,
                        action_btn_text=None, action_cmd=None):
        s = self._scale
        self._build_section_header(
            parent, label_text, status_type=status_type,
            action_btn_text=action_btn_text, action_cmd=action_cmd
        )

        row = tk.Frame(parent, bg=self.C_CARD)
        if tutorial_id:
            row.tutorial_id = tutorial_id
        row.pack(fill="x", expand=True)

        entry = tk.Entry(
            row,
            textvariable=path_var,
            readonlybackground=entry_bg,
            bg=entry_bg,
            fg=self.C_ON_SURFACE,
            font=("Courier New", sc(10)),
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
            highlightcolor=self.C_PRIMARY,
            state="readonly",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=int(6*s))

        # Show placeholder in muted color when empty
        if placeholder:
            def _update_placeholder(*_):
                val = path_var.get()
                entry.config(
                    fg=(self.C_OUTLINE if not val else self.C_ON_SURFACE),
                )
                if not val:
                    entry.config(state="normal")
                    entry.delete(0, "end")
                    entry.insert(0, placeholder)
                    entry.config(state="readonly", fg=self.C_OUTLINE)
                else:
                    entry.config(fg=self.C_ON_SURFACE)
            path_var.trace_add("write", _update_placeholder)
            _update_placeholder()

        # Browse button (32×32, attached right, 1px left border via highlight trick)
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
            command=browse_cmd,
            highlightthickness=1,
            highlightbackground=self.C_OUTLINE,
        )
        btn.pack(side="right", ipady=int(5*s))
        btn.bind("<Enter>", lambda e: btn.config(bg=self.C_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(bg=self.C_HEADER_BG))

        if path_var is self.db_path_var:
            # Track changes to enable/disable LAUNCH button
            path_var.trace_add("write", lambda *_: self._refresh_launch_state())

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
                # Right-border separator via a thin frame
                btn.pack(side="left", fill="both", expand=True, ipady=int(6*s))
                tk.Frame(toggle_outer, bg=self.C_OUTLINE, width=1).pack(side="left", fill="y")
            else:
                btn.pack(side="left", fill="both", expand=True, ipady=int(6*s))
            self._seg_buttons[mode] = btn

        # Local folder sub-row (hidden unless "folder" is selected)
        self._folder_row = tk.Frame(self._image_source_container, bg=self.C_CARD)
        self._build_file_row(
            self._folder_row,
            label_text="Local Image Directory",
            path_var=self.image_folder_var,
            entry_bg=self.C_SURFACE_LOW,
            placeholder="No folder selected...",
            browse_cmd=self.select_folder,
        )

        self._set_image_mode("online")  # initial state

    def _set_image_mode(self, mode):
        self.image_mode.set(mode)

        # ✅ 1. Update button styles
        for m, btn in self._seg_buttons.items():
            if m == mode:
                btn.config(bg=self.C_PRIMARY, fg=self.C_ON_PRIMARY)
            else:
                btn.config(bg=self.C_CARD, fg=self.C_ON_VARIANT)

                # Clean rebind
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")

                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.C_HOVER))
                btn.bind("<Leave>", lambda e, b=btn, bm=m: b.config(
                    bg=self.C_CARD if bm != self.image_mode.get() else self.C_PRIMARY
                ))

        # ✅ 2. Show / hide folder row (MUST be outside loop)
        if mode == "folder":
            if not self._folder_row.winfo_ismapped():
                self._folder_row.pack(fill="x", pady=(int(4 * self._scale), 0))
                self._folder_row.update_idletasks()  # ✅ animation polish
                self._resize_to_fit()
        else:
            if self._folder_row.winfo_ismapped():
                self._folder_row.pack_forget()

        # ✅ 3. Enable / disable contents
        state = "normal" if mode == "folder" else "disabled"

        for child in self._folder_row.winfo_children():
            for sub in child.winfo_children():
                try:
                    if isinstance(sub, tk.Label):
                        sub.config(
                            fg=self.C_ON_SURFACE if state == "normal" else self.C_OUTLINE
                        )
                    else:
                        sub.configure(state=state)
                except Exception:
                    pass


    def _resize_to_fit(self):
        try:
            self.win.update_idletasks()
            req_h = self._outer.winfo_reqheight()
            canv_h = self._outer.master.winfo_height()
            if canv_h > 1 and req_h > canv_h:
                cur_win_h = self.win.winfo_height()
                missing_h = req_h - canv_h

                max_h = self.win.winfo_screenheight() - 100
                target_win_h = min(cur_win_h + missing_h, max_h)

                if target_win_h > cur_win_h:
                    geom = self.win.geometry()
                    m = re.match(r"(\d+)x(\d+)([-+]\d+)([-+]\d+)", geom)
                    if m:
                        w, h, x, y = m.groups()
                        self.win.geometry(f"{w}x{target_win_h}{x}{y}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Recent Projects table
    # ------------------------------------------------------------------

    def _build_recent_table(self, parent):
        s = self._scale
        self._label_md(parent, "Recent Projects", bg=self.C_CARD).pack(
            anchor="w", pady=(0, int(2*s))
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
        self._label_md(hdr, "LAST MODIFIED", bg=self.C_SURFACE_LOW).pack(
            side="right", padx=int(8*s), anchor="e"
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
                modified = entry.get("modified", "")
                self._build_recent_row(table, path, modified, i)

    def _build_recent_row(self, table, path, modified, index):
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

        path_lbl._last_width = -1
        import tkinter.font as tkfont

        # Cache font so it's not recreated on every resize event
        lbl_font = tkfont.Font(font=("Courier New", sc(9)))

        def _on_configure(e):
            width = e.width
            if width <= 10 or width == getattr(path_lbl, "_last_width", -1):
                return
            path_lbl._last_width = width

            if lbl_font.measure(path) <= width:
                path_lbl.config(text=path)
                return

            ellipsis = "…"
            low = 0
            high = len(path)
            best_trunc = ""

            while low <= high:
                mid = (low + high) // 2
                trunc = path[-mid:] if mid > 0 else ""
                test_str = ellipsis + trunc

                if lbl_font.measure(test_str) <= width:
                    best_trunc = test_str
                    low = mid + 1
                else:
                    high = mid - 1

            if not best_trunc:
                best_trunc = ellipsis
            path_lbl.config(text=best_trunc)

        path_lbl.bind("<Configure>", _on_configure)

        date_lbl = tk.Label(
            row, text=modified,
            bg=self.C_CARD, fg=self.C_ON_VARIANT,
            font=("Courier New", sc(9)),
            anchor="e", cursor="hand2", width=12
        )
        date_lbl.pack(side="right", padx=int(8*s))

        # Hover + click for each widget in the row
        def _hover_on(e):
            row.config(bg=self.C_HOVER)
            path_lbl.config(bg=self.C_HOVER, fg=self.C_PRIMARY)
            date_lbl.config(bg=self.C_HOVER)

        def _hover_off(e):
            row.config(bg=self.C_CARD)
            path_lbl.config(bg=self.C_CARD, fg=self.C_ON_SURFACE)
            date_lbl.config(bg=self.C_CARD)

        def _click(e, p=path):
            self.select_recent(p)

        for widget in (row, path_lbl, date_lbl):
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
        self._sep(card, self.C_OUTLINE_VAR)

        footer = tk.Frame(card, bg=self.C_FOOTER_BG, padx=int(16*s), pady=int(10*s))
        footer.pack(fill="x", expand=False)

        # Ready status label above buttons (aligned right, inside footer)
        self.ready_status_label = tk.Label(
            footer, text="",
            bg=self.C_FOOTER_BG,
            font=("Segoe UI", sc(9), "bold"),
            anchor="e"
        )
        self.ready_status_label.pack(side="top", fill="x", pady=(0, int(4*s)))

        # Progress bar (hidden by default, shows during loading)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            footer, variable=self.progress_var, maximum=100
        )
        # Not packed yet — shown in _show_progress()





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
        # Enable if path is set and is not the placeholder
        valid = bool(path) and path != "No file selected..."
        self.continue_btn.config(state="normal" if valid else "disabled")
        if valid:
            self.continue_btn.config(bg=self.C_PRIMARY)
            if hasattr(self, "ready_status_label"):
                self.ready_status_label.config(text="Ready to launch!", fg="#3b6934")
        else:
            self.continue_btn.config(bg="#888888")
            if hasattr(self, "ready_status_label"):
                self.ready_status_label.config(text="Please select a database file.", fg="#ba1a1a")

    def _show_progress(self, show=True):
        if show:
            self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        else:
            self.progress_bar.pack_forget()
            self.progress_var.set(0)


    # ------------------------------------------------------------------
    # resize
    # ------------------------------------------------------------------

    def _on_resize(self, event):
        if event.widget != self.win:
            return


        if not hasattr(self, "_last_scale"):
            self._last_scale = self._scale
            self._compact = False


        new_w = self.win.winfo_width()
        new_h = self.win.winfo_height()

        base_w, base_h = 640, 680
        scale = min(new_w / base_w, new_h / base_h)
        scale = max(0.75, min(scale, 1.4))

        # Detect compact mode
        compact = new_w < 580 or new_h < 600

        # Only update if something meaningful changed
        if abs(scale - self._last_scale) < 0.05 and compact == self._compact:
            return

        self._scale = scale
        self._last_scale = scale
        self._compact = compact

        self._apply_adaptive_layout()



    def _apply_adaptive_layout(self):
        s = self._scale

        # Compact mode adjustments
        if self._compact:
            font_small = sc(8)
            font_base = sc(9)
            font_title = sc(14)
            pad = 8
        else:
            font_small = sc(9)
            font_base = sc(10)
            font_title = sc(18)
            pad = 16


        # Adjust outer padding dynamically
        pad = 10 if self._compact else 20
        try:
            if hasattr(self, "_card"):
                self._card.pack_configure(padx=pad, pady=pad)
            else:
                self._outer.pack_configure(padx=pad, pady=pad)
        except Exception:
            pass

        # Update ALL widgets recursively
        def update_widget(widget):
            try:
                # Fonts
                if isinstance(widget, tk.Label):
                    txt = widget.cget("text")

                    if "arbor" in txt:
                        widget.config(font=("Courier New", font_small, "bold"))
                    elif "Project Setup" in txt:
                        widget.config(font=("Segoe UI", font_title, "bold"))
                    elif txt.strip() in ("REQUIRED", "RECOMMENDED", "OPTIONAL"):
                        widget.config(font=("Courier New", font_small, "bold"))
                    else:
                        widget.config(font=("Courier New", font_base))

                elif isinstance(widget, tk.Button):
                    widget.config(font=("Segoe UI", font_base, "bold" if not self._compact else "normal"))

                elif isinstance(widget, tk.Entry):
                    widget.config(font=("Courier New", font_base))

            except Exception:
                pass

            for child in widget.winfo_children():
                update_widget(child)

        update_widget(self.win)



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
        self._refresh_launch_state()

        # Check for autosave
        # Backward-compatible check for the new secure .autosave.json or legacy .autosave.xlsx.
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

    def browse_import(self):
        import config
        path = filedialog.askopenfilename(
            title="Select Import File",
            filetypes=[("Spreadsheet / Database", "*.xlsx *.csv *.db")],
            initialdir=config.get_last_dir("last_db_dir")
        )
        if not path:
            return
        self.import_path_var.set(path)
        self.selected_excel_path = path




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
        self._refresh_launch_state()

    # ------------------------------------------------------------------
    # Advanced setup (demoted Books / Historical)
    # ------------------------------------------------------------------

    def _show_advanced(self):
        """Open a small secondary popup for Books and Historical DB loading."""
        adv_win = tk.Toplevel(self.win)
        adv_win.title("Advanced Setup")
        adv_win.resizable(False, False)
        adv_win.grab_set()

        import utils
        utils.center_and_fit_toplevel(adv_win, int(400 * self._scale), int(280 * self._scale))

        frame = ttk.Frame(adv_win, padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Advanced Data Sources",
                  font=("Segoe UI", sc(11), "bold")).pack(anchor="w", pady=(0, 10))

        # DB config selector (kept for config-mapping)
        ttk.Label(frame, text="Select database config:").pack(anchor="w")
        self.db_var = tk.StringVar()
        db_names = list(DATABASE_CONFIGS.keys())
        db_names.append("<Create New Database...>")
        self.db_dropdown = ttk.Combobox(frame, textvariable=self.db_var,
                                        values=db_names, state="readonly")
        if db_names and len(db_names) > 1:
            self.db_var.set(db_names[0])
        self.db_dropdown.pack(fill="x", pady=(2, 10))
        self.db_dropdown.bind("<<ComboboxSelected>>", self.on_db_selected)

        self.books_label = ttk.Label(frame, text="No books loaded", foreground="gray")
        ttk.Button(frame, text="Load Books", command=self.load_books_startup).pack(fill="x")
        self.books_label.pack(anchor="w", pady=(2, 8))

        self.history_label = ttk.Label(frame, text="No historical databases loaded", foreground="gray")
        ttk.Button(frame, text="Load Earlier Databases",
                   command=self.load_historical_startup).pack(fill="x")
        self.history_label.pack(anchor="w", pady=(2, 8))

        self.progress_bar_adv = ttk.Progressbar(frame, variable=self.progress_var, maximum=100)
        self.progress_bar_adv.pack(fill="x", pady=4)
        self.progress_bar_adv.pack_forget()

        ttk.Button(frame, text="Done", command=adv_win.destroy).pack(anchor="e", pady=(8, 0))

        # Point old progress_bar references to the advanced one
        self.progress_bar = self.progress_bar_adv

    # ------------------------------------------------------------------
    # Existing load methods (unchanged)
    # ------------------------------------------------------------------

    def create_new_database_startup(self):
        from ui.new_database_wizard import NewDatabaseWizard
        NewDatabaseWizard(self.win, self.app, self.on_new_db_created)

    def on_db_selected(self, event=None):
        if hasattr(self, "db_var") and self.db_var.get() == "<Create New Database...>":
            self.create_new_database_startup()

    def on_new_db_created(self, file_path=None, profile_name=None):
        from config import DATABASE_CONFIGS
        db_names = list(DATABASE_CONFIGS.keys())
        new_values = list(db_names)
        new_values.append("<Create New Database...>")
        if hasattr(self, "db_dropdown"):
            self.db_dropdown["values"] = new_values
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

    # Alias for old code that used open_excel
    def open_excel(self):
        self.browse_database()

    def safe_ui_call(self, func):
        try:
            root = self.parent.winfo_toplevel()
            if root.winfo_exists():
                root.after(0, func)
        except Exception:
            pass

    def load_books_startup(self):
        import config
        path = filedialog.askopenfilename(
            title="Select Books Excel file",
            filetypes=[("Database files", "*.xlsx *.db")],
            initialdir=config.get_last_dir("last_book_dir")
        )
        if not path:
            return
        config.set_last_dir("last_book_dir", path)

        selected_db = getattr(self, "db_var", tk.StringVar()).get()
        if selected_db not in DATABASE_CONFIGS:
            messagebox.showerror("Error", "Please select a database config first (Advanced Setup)")
            return
        self.app.config = DATABASE_CONFIGS[selected_db]

        if hasattr(self, "books_label"):
            self.books_label.config(text="Loading Books...", foreground="orange")
        self.continue_btn.config(state="disabled")

        if hasattr(self, "progress_bar"):
            self.progress_bar.pack(fill="x", pady=4)
            self.progress_var.set(5)
        self.win.update_idletasks()

        threading.Thread(target=self._load_books_worker, args=(path,), daemon=True).start()

    def _load_books_worker(self, path):
        try:
            self.safe_ui_call(lambda: self.progress_var.set(10))
            loaded = []
            if path.endswith(".db"):
                from repository import SQLiteRepository
                df_reg, df_obs, *_ = SQLiteRepository.load_sqlite(path, self.app.config)
                loaded.append({
                    "name": "Books: DB", "path": path,
                    "df_reg": df_reg, "reg_by_id": None,
                })
            else:
                from repository import _open_excel_reader, _normalize_object_id_series
                with _open_excel_reader(path) as xls:
                    allowed_cols = set(self.app.config.get("books_columns", []))
                    if "ObjectID" not in allowed_cols:
                        allowed_cols.add("ObjectID")
                    total_sheets = len(xls.sheet_names)
                    for i, sheet_name in enumerate(xls.sheet_names):
                        try:
                            self.safe_ui_call(
                                lambda i=i, t=total_sheets: self.progress_var.set(((i+1) / t) * 100)
                            )
                            df = pd.read_excel(xls, sheet_name=sheet_name,
                                               usecols=lambda x: x in allowed_cols)
                            if "ObjectID" not in df.columns:
                                continue
                            df["ObjectID"] = _normalize_object_id_series(df["ObjectID"])
                            loaded.append({
                                "name": f"Books: {sheet_name}", "path": path,
                                "df_reg": df, "reg_by_id": None,
                            })
                        except Exception as sheet_err:
                            print(f"Error loading sheet {sheet_name}: {sheet_err}")
            self.safe_ui_call(lambda: self._finish_books_load(loaded))
        except Exception as e:
            debug_error("Load Books Failed", str(e))
            err_msg = str(e)
            self.safe_ui_call(
                lambda: (
                    self.books_label.config(text="Load failed", foreground="red")
                    if hasattr(self, "books_label") else None,
                    messagebox.showerror("Error", err_msg),
                    self.continue_btn.config(state="normal"),
                )
            )

    def load_historical_startup(self):
        import config
        paths = filedialog.askopenfilenames(
            title="Select previous Excel databases",
            filetypes=[("Database files", "*.xlsx *.db")],
            initialdir=config.get_last_dir("last_db_dir")
        )
        if not paths:
            return
        config.set_last_dir("last_db_dir", paths[0])
        self.continue_btn.config(state="disabled")
        if hasattr(self, "history_label"):
            self.history_label.config(text="Loading...", foreground="orange")
        if hasattr(self, "progress_bar"):
            self.progress_bar.pack(fill="x", pady=4)
        self.progress_var.set(0)
        self.win.update_idletasks()
        threading.Thread(target=self._load_historical_worker, args=(paths,), daemon=True).start()

    def _load_historical_worker(self, paths):
        try:
            loaded = []
            total = len(paths)
            from repository import SQLiteRepository, ExcelRepository
            for i, path in enumerate(paths, start=1):
                try:
                    if path.endswith(".db"):
                        df_reg, df_obs, *_ = SQLiteRepository.load_sqlite(path, self.app.config)
                    else:
                        df_reg, df_obs, *_ = ExcelRepository.load_excel(path, self.app.config)
                    loaded.append({
                        "name": f"ARK{i}", "path": path,
                        "df_reg": df_reg, "reg_by_id": None,
                    })
                except Exception as e:
                    err_msg = str(e)
                    self.safe_ui_call(
                        lambda: messagebox.showwarning("Load failed", err_msg)
                    )
                self.safe_ui_call(
                    lambda i=i, total=total: self.progress_var.set((i / total) * 100)
                )
            self.safe_ui_call(lambda: self._finish_historical_load(loaded))
        except Exception as e:
            debug_error("Load Historical Failed", str(e))
            err_msg = str(e)
            self.safe_ui_call(
                lambda: (
                    messagebox.showerror("Error", err_msg),
                    self.continue_btn.config(state="normal"),
                )
            )

    def _finish_historical_load(self, loaded):
        if hasattr(self, "progress_bar"):
            self.progress_bar.pack_forget()
        from collections import OrderedDict
        self.ui._history_cache = OrderedDict()
        if not loaded:
            if hasattr(self, "history_label"):
                self.history_label.config(text="No valid databases loaded", foreground="red")
            self.continue_btn.config(state="normal")
            return
        if not self.app.historical_dbs:
            self.app.historical_dbs = []
        self.app.historical_dbs.extend(loaded)
        if hasattr(self, "history_label"):
            self.history_label.config(text=f"{len(loaded)} databases loaded", foreground="green")
        self.continue_btn.config(state="normal")
        oid = self.app.current_object_id
        if oid:
            try:
                self.ui.update_history_indicator(oid)
            except Exception:
                pass

    def _finish_books_load(self, loaded):
        if hasattr(self, "progress_bar"):
            self.progress_bar.pack_forget()
        from collections import OrderedDict
        self.ui._history_cache = OrderedDict()
        if not loaded:
            if hasattr(self, "books_label"):
                self.books_label.config(text="No valid sheets found", foreground="red")
            self.continue_btn.config(state="normal")
            return
        if not self.app.historical_dbs:
            self.app.historical_dbs = []
        self.app.historical_dbs.extend(loaded)
        oid = self.app.current_object_id
        if oid:
            self.ui.update_history_indicator(oid)
        if hasattr(self, "books_label"):
            self.books_label.config(text=f"Books loaded ({len(loaded)} sheets)", foreground="green")
        self.continue_btn.config(state="normal")

    # ------------------------------------------------------------------
    # Finish / launch
    # ------------------------------------------------------------------

    def finish(self):
        path = self.db_path_var.get().strip()
        if not path:
            messagebox.showerror("Error", "Please select a database file first.")
            return

        # Map path to a DATABASE_CONFIG by matching file stem, or default to first
        matched_config = None
        matched_name = None
        basename = os.path.basename(path).lower()

        for name, cfg in DATABASE_CONFIGS.items():
            if name.lower() in basename or basename in name.lower():
                matched_config = cfg
                matched_name = name
                break

        if matched_config is None:
            # Fall back to first available config
            matched_name = next(iter(DATABASE_CONFIGS))
            matched_config = DATABASE_CONFIGS[matched_name]

        self.app.config = matched_config
        self.app.config_name = matched_name
        self.completed = True

        # Record in recent files
        add_recent_file(path)

        # Set image mode properties for main to read
        mode = self.image_mode.get()
        if mode == "folder" and not self.image_folder_var.get():
            messagebox.showerror("Error", "Please select a local image directory or switch to Online/Offline mode.")
            return

        self.image_mode_val = mode
        self.image_folder_val = self.image_folder_var.get()
        self.selected_excel_path = path

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

        if not curr: # meaning we just set it to True (disabled)
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
            "1. Select a database file (.xlsx, .db, .sqlite)\n\n"
            "RECOMMENDED\n"
            "2. Choose image source\n"
            "   - Online = images loaded from repository\n"
            "   - Local Directory = select local image folder\n"
            "   - Offline = no images\n\n"
            "OPTIONAL\n"
            "3. Import Excel/CSV = additional observation data\n\n"
            "Click LAUNCH SYSTEM to start.\n\n"
            "TIP: You can change all settings later in the program."
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
            bg_color = "#1e1e2e"
            fg_title = "#cdd6f4"
            fg_status = "#a6adc8"
            bar_trough = "#313244"
            bar_color = "#cba6f7"
        else:
            bg_color = "#f9f9f9"
            fg_title = "#1a1c1c"
            fg_status = "#444748"
            bar_trough = "#e2e2e2"
            bar_color = "#000000"

        self.win.configure(bg=bg_color)
        self.win.resizable(False, False)
        
        # Center the splash window
        from config import sc
        import utils
        utils.center_and_fit_toplevel(self.win, sc(450), sc(180))
        
        # Prevent user closing it manually
        self.win.protocol("WM_DELETE_WINDOW", lambda: None)
        self.win.grab_set()
        
        # Title Label
        tk.Label(
            self.win,
            text="Initializing Application",
            font=("Segoe UI", sc(14), "bold"),
            bg=bg_color,
            fg=fg_title
        ).pack(pady=(sc(24), sc(10)))
        
        # Progress status label (saved as attribute to easily update)
        self.status_lbl = tk.Label(
            self.win,
            text="Loading Excel database...",
            font=("Courier New", sc(9)),
            bg=bg_color,
            fg=fg_status
        )
        self.status_lbl.pack(pady=(0, sc(8)))
        
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
            self.win,
            style="Splash.Horizontal.TProgressbar",
            orient="horizontal",
            mode="determinate"
        )
        self.progress_bar.pack(fill="x", padx=sc(35), pady=sc(10))
        
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


