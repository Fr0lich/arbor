import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
from typing import Dict, List, Optional
from config import sc

FONT_UI = ("sans-serif", 10)
FONT_UI_BOLD = ("sans-serif", 10, "bold")
FONT_UI_LG = ("sans-serif", 12, "bold")
FONT_UI_XL = ("sans-serif", 14, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 8)

_fonts_initialized = False
def init_fonts():
    global _fonts_initialized, FONT_UI, FONT_UI_BOLD, FONT_UI_LG, FONT_UI_XL, FONT_MONO, FONT_MONO_SM
    if _fonts_initialized:
        return
    families = tkFont.families()
    ui_family = "Hanken Grotesk" if "Hanken Grotesk" in families else "Helvetica" if "Helvetica" in families else "Segoe UI" if "Segoe UI" in families else "sans-serif"
    mono_family = "JetBrains Mono" if "JetBrains Mono" in families else "Consolas" if "Consolas" in families else "Courier New"

    FONT_UI = (ui_family, sc(10))
    FONT_UI_BOLD = (ui_family, sc(10), "bold")
    FONT_UI_LG = (ui_family, sc(12), "bold")
    FONT_UI_XL = (ui_family, sc(14), "bold")
    FONT_MONO = (mono_family, sc(10))
    FONT_MONO_SM = (mono_family, sc(8))
    _fonts_initialized = True

COLORS = {
    "bg": "#fbfaf8",
    "surface": "#ffffff",
    "surface_dim": "#e9ece5",
    "border": "#d1d1d1",
    "text": "#2c302e",
    "text_muted": "#444748",
    "primary": "#2c302e",
    "on_primary": "#ffffff",
    "error": "#c93a40",
    "error_bg": "#fef2f2",
    "success": "#3a7d44",
    "success_bg": "#f0fdf4",
    "success_border": "#3a7d44",
    "warning": "#f59e0b",
    "conflict": "#0284c7",
}


class GBIFUpdateDialog(tk.Toplevel):
    def __init__(self, parent, updates: List[Dict]):
        """
        updates is a list of dictionaries, e.g.:
        [
            {"field": "Taxonomy (Spelling)", "current": "Quercus robur", "gbif": "Quercus robur", "selected": True, "data": {"genus": "Quercus", "species": "robur"}},
            {"field": "Author", "current": "L.", "gbif": "Linnaeus", "selected": True, "data": {"author": "Linnaeus"}},
        ]
        """
        super().__init__(parent)
        init_fonts()
        self.parent = parent
        self.title("GBIF Updates Available")
        self.minsize(sc(580), sc(440))
        self.transient(parent)
        self.grab_set()

        self.updates = updates
        self.result_data = None  # Will hold combined data if approved
        self.vars = []

        self._build_ui()
        self.center_window(parent)
        self.bind("<Control-a>", lambda e: self.apply())
        self.bind("<Escape>", lambda e: self.destroy())

    def _build_ui(self):
        is_dark = getattr(self.parent, "dark_mode_active", False) if hasattr(self.parent, "dark_mode_active") else False
        bg = "#181c19" if is_dark else COLORS["bg"]
        surface = "#24273a" if is_dark else COLORS["surface"]
        surface_dim = "#1e2030" if is_dark else COLORS["surface_dim"]
        border = "#363a4f" if is_dark else COLORS["border"]
        text_color = "#cad3f5" if is_dark else COLORS["text"]
        text_muted = "#a5adcb" if is_dark else COLORS["text_muted"]

        self.configure(bg=bg)

        # 1. Top Header Bar (Full-bleed)
        header = tk.Frame(self, bg=surface, height=sc(48))
        header.pack(fill="x", side="top")
        tk.Frame(header, bg=border, height=sc(1)).pack(fill="x", side="bottom")

        tk.Label(
            header,
            text="GBIF_TAXONOMIC_RECONCILIATION",
            font=FONT_UI_LG,
            fg=text_color,
            bg=surface
        ).pack(side="left", padx=sc(16), pady=sc(12))

        # 2. Main content area
        main_area = tk.Frame(self, bg=bg)
        main_area.pack(fill="both", expand=True)

        # Context Header
        ctx_header = tk.Frame(main_area, bg=surface)
        ctx_header.pack(fill="x")
        tk.Frame(ctx_header, bg=border, height=sc(1)).pack(side="bottom", fill="x")

        tk.Label(
            ctx_header,
            text=f"RECORD REVIEW: {len(self.updates)} PROPOSED UPDATE{'S' if len(self.updates) != 1 else ''}",
            font=FONT_UI_XL,
            fg=text_color,
            bg=surface
        ).pack(anchor="w", padx=sc(20), pady=(sc(12), sc(2)))

        tk.Label(
            ctx_header,
            text="Review GBIF taxonomic backbone suggestions below. Select the changes you wish to apply.",
            font=FONT_UI,
            fg=text_muted,
            bg=surface
        ).pack(anchor="w", padx=sc(20), pady=(0, sc(10)))

        # Quick Actions Bar
        if len(self.updates) > 1:
            act_bar = tk.Frame(ctx_header, bg=surface)
            act_bar.pack(fill="x", padx=sc(20), pady=(0, sc(10)))

            sel_all_btn = tk.Button(
                act_bar, text="Select All", command=self._select_all,
                font=FONT_UI_BOLD, bg=surface_dim, fg=text_color,
                relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3),
                highlightthickness=1, highlightbackground=border
            )
            sel_all_btn.pack(side="left", padx=(0, sc(6)))

            desel_all_btn = tk.Button(
                act_bar, text="Deselect All", command=self._deselect_all,
                font=FONT_UI_BOLD, bg=surface_dim, fg=text_color,
                relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3),
                highlightthickness=1, highlightbackground=border
            )
            desel_all_btn.pack(side="left")

        # Scrollable Canvas for Cards
        scroll_container = tk.Frame(main_area, bg=bg)
        scroll_container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(scroll_container, bg=bg, highlightthickness=0)
        v_scroll = ttk.Scrollbar(scroll_container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=v_scroll.set)

        self.scrollable_frame = tk.Frame(self.canvas, bg=bg, padx=sc(16), pady=sc(14))
        self.scroll_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")) if e.widget == self.scrollable_frame else None
        )
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.scroll_window, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.scrollable_frame)

        # Build Cards
        for i, update in enumerate(self.updates):
            field_name = str(update.get("field", "Taxonomy")).upper()
            var = tk.BooleanVar(value=update.get("selected", True))
            self.vars.append(var)

            # Determine category badge
            badge_code = "TAX"
            badge_color = "#C62828"
            if "AUTHOR" in field_name or "COLLECTOR" in field_name:
                badge_code = "PROV"
                badge_color = "#D9A036"
            elif "FAMILY" in field_name or "GENUS" in field_name or "SPECIES" in field_name or "TAXONOMY" in field_name:
                badge_code = "TAX"
                badge_color = "#C62828"

            card = tk.Frame(
                self.scrollable_frame,
                bg=surface,
                highlightbackground=border,
                highlightthickness=1
            )
            card.pack(fill="x", pady=(0, sc(12)))
            self._bind_mousewheel(card)

            # Card Header Bar
            card_hdr = tk.Frame(card, bg="#2c302e" if not is_dark else "#1b1b1b")
            card_hdr.pack(fill="x")
            self._bind_mousewheel(card_hdr)

            tk.Label(
                card_hdr,
                text=f"FIELD: {field_name}",
                font=FONT_UI_BOLD,
                fg="#ffffff",
                bg="#2c302e" if not is_dark else "#1b1b1b"
            ).pack(side="left", padx=sc(12), pady=sc(8))

            tk.Label(
                card_hdr,
                text=badge_code,
                font=FONT_MONO_SM,
                fg="#ffffff",
                bg=badge_color,
                padx=sc(6),
                pady=sc(1)
            ).pack(side="right", padx=sc(12), pady=sc(6))

            card_body = tk.Frame(card, bg=surface, padx=sc(16), pady=sc(14))
            card_body.pack(fill="x")
            self._bind_mousewheel(card_body)

            # 1. Current Value Block
            tk.Label(
                card_body,
                text="CURRENT_VALUE",
                font=FONT_MONO_SM,
                fg=text_muted,
                bg=surface
            ).pack(anchor="w", pady=(0, sc(3)))

            cur_box = tk.Frame(card_body, bg=surface_dim, highlightbackground=border, highlightthickness=1)
            cur_box.pack(fill="x", pady=(0, sc(12)))
            self._bind_mousewheel(cur_box)

            cur_val_str = str(update.get("current", "") or "").strip() or "[BLANK]"
            cur_fg = text_color if cur_val_str != "[BLANK]" else text_muted
            lbl_cur = tk.Label(
                cur_box,
                text=cur_val_str,
                font=FONT_MONO,
                fg=cur_fg,
                bg=surface_dim,
                padx=sc(10),
                pady=sc(8),
                anchor="w"
            )
            lbl_cur.pack(fill="x")
            self._bind_mousewheel(lbl_cur)

            # 2. GBIF Suggestion Block
            tk.Label(
                card_body,
                text="GBIF_SUGGESTION",
                font=FONT_MONO_SM,
                fg=text_muted,
                bg=surface
            ).pack(anchor="w", pady=(0, sc(3)))

            sug_bg = "#f0fdf4" if not is_dark else "#122416"
            sug_border = "#3a7d44" if not is_dark else "#2b8a3e"

            sug_box = tk.Frame(
                card_body,
                bg=sug_bg,
                highlightbackground=sug_border,
                highlightthickness=1,
                cursor="hand2"
            )
            sug_box.pack(fill="x")
            self._bind_mousewheel(sug_box)

            def _toggle_var(v=var):
                v.set(not v.get())
                self._update_stats()

            cb = tk.Checkbutton(
                sug_box,
                text=str(update.get("gbif", "")),
                variable=var,
                font=FONT_MONO,
                fg="#2b8a3e" if not is_dark else "#a6e3a1",
                bg=sug_bg,
                activebackground=sug_bg,
                activeforeground="#2b8a3e" if not is_dark else "#a6e3a1",
                selectcolor=sug_bg,
                bd=0,
                highlightthickness=0,
                padx=sc(8),
                pady=sc(8),
                cursor="hand2",
                command=self._update_stats
            )
            cb.pack(side="left", fill="x", expand=True, anchor="w")
            self._bind_mousewheel(cb)

            # Check for Historical Book Corroboration
            app_state = getattr(self.parent, "app_state", None) or getattr(self.parent, "app", None)
            oid = getattr(app_state, "current_object_id", None) or getattr(self.parent, "current_object_id", None)
            from backend.cross_validation import find_book_matches_for_gbif
            matching_books = find_book_matches_for_gbif(app_state, str(oid or ""), update.get("field", ""), str(update.get("gbif", "")))
            if matching_books:
                book_badge_text = f"✓ In Books ({matching_books[0].replace('Books: ', '')})"
                bk_lbl = tk.Label(
                    sug_box,
                    text=book_badge_text,
                    font=FONT_MONO_SM,
                    fg="#ffffff",
                    bg="#3a7d44" if not is_dark else "#2b8a3e",
                    padx=sc(6),
                    pady=sc(1)
                )
                bk_lbl.pack(side="right", padx=(sc(6), 0))
                self._bind_mousewheel(bk_lbl)

            tag_lbl = tk.Label(
                sug_box,
                text="[GBIF Backbone Match]",
                font=FONT_MONO_SM,
                fg="#3a7d44" if not is_dark else "#89b4fa",
                bg=sug_bg,
                padx=sc(10)
            )
            tag_lbl.pack(side="right")
            self._bind_mousewheel(tag_lbl)

        # 3. Sticky Bottom Footer
        footer = tk.Frame(self, bg=surface_dim, height=sc(48))
        footer.pack(fill="x", side="bottom")
        tk.Frame(footer, bg=border, height=sc(1)).pack(side="top", fill="x")

        self.stats_label = tk.Label(
            footer,
            text="",
            font=FONT_MONO,
            fg=text_muted,
            bg=surface_dim
        )
        self.stats_label.pack(side="left", padx=sc(20), pady=sc(12))

        apply_btn = tk.Button(
            footer,
            text="APPLY SELECTED UPDATES (CTRL+A)",
            command=self.apply,
            font=FONT_UI_BOLD,
            bg="#3a7d44",
            fg="#ffffff",
            relief="flat",
            bd=0,
            padx=sc(18),
            pady=sc(8),
            cursor="hand2"
        )
        apply_btn.pack(side="right", padx=sc(16), pady=sc(6))

        cancel_btn = tk.Button(
            footer,
            text="CLOSE",
            command=self.destroy,
            font=FONT_UI_BOLD,
            bg=surface,
            fg=text_color,
            relief="solid",
            bd=1,
            padx=sc(16),
            pady=sc(8),
            cursor="hand2"
        )
        cancel_btn.pack(side="right", padx=sc(8), pady=sc(6))

        self._update_stats()

    def _update_stats(self):
        sel_count = sum(1 for v in self.vars if v.get())
        total = len(self.vars)
        if hasattr(self, "stats_label") and self.stats_label.winfo_exists():
            self.stats_label.config(text=f"{sel_count} OF {total} UPDATES SELECTED")

    def _select_all(self):
        for v in self.vars:
            v.set(True)
        self._update_stats()

    def _deselect_all(self):
        for v in self.vars:
            v.set(False)
        self._update_stats()

    def _bind_mousewheel(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"), add="+")
        widget.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"), add="+")

    def _on_mousewheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def apply(self):
        self.result_data = {}
        for update, var in zip(self.updates, self.vars):
            if var.get():
                self.result_data.update(update["data"])
        self.destroy()

    def _apply(self):
        self.apply()

    def center_window(self, parent):
        self.update_idletasks()
        req_w = max(self.winfo_reqwidth(), sc(580))
        req_h = min(max(self.winfo_reqheight(), sc(420)), sc(680))
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (req_w // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (req_h // 2)
        self.geometry(f"{req_w}x{req_h}+{max(0, x)}+{max(0, y)}")
