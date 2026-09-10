import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional
from config import sc

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
        self.parent = parent
        self.title("GBIF Updates Available")
        self.minsize(sc(520), sc(380))
        self.transient(parent)
        self.grab_set()

        self.updates = updates
        self.result_data = None  # Will hold combined data if approved
        self.vars = []

        self._build_ui()
        self.center_window(parent)

    def _build_ui(self):
        # Determine theme palette
        is_dark = getattr(self.parent, "dark_mode_active", False) if hasattr(self.parent, "dark_mode_active") else False
        bg_color = "#181c19" if is_dark else "#fbfaf8"
        fg_title = "#e8ebe9" if is_dark else "#2c302e"
        fg_muted = "#a6adc8" if is_dark else "#757d77"
        border_color = "#2c302e" if is_dark else "#dadada"
        card_bg = "#111412" if is_dark else "#ffffff"
        chip_old_bg = "#231515" if is_dark else "#fef2f2"
        chip_old_fg = "#c93a40"
        chip_new_bg = "#122416" if is_dark else "#f0fdf4"
        chip_new_fg = "#3a7d44"
        btn_primary_bg = "#3a7d44" if is_dark else "#2c302e"
        btn_primary_hover = "#4b9e57" if is_dark else "#3d4240"
        btn_sec_bg = bg_color
        btn_sec_fg = fg_title
        btn_sec_hover = "#242a25" if is_dark else "#e9ece5"

        self.configure(bg=bg_color)

        main_frame = tk.Frame(self, padx=sc(16), pady=sc(14), bg=bg_color)
        main_frame.pack(fill="both", expand=True)

        # Header
        header_frame = tk.Frame(main_frame, bg=bg_color)
        header_frame.pack(fill="x", pady=(0, sc(10)))

        header = tk.Label(
            header_frame,
            text="Proposed Taxonomic Updates",
            font=("Segoe UI", sc(12), "bold"),
            fg=fg_title,
            bg=bg_color
        )
        header.pack(anchor="w")

        sub_header = tk.Label(
            header_frame,
            text=f"GBIF suggested updates for {len(self.updates)} field(s). Select the changes to apply:",
            font=("Segoe UI", sc(9)),
            fg=fg_muted,
            bg=bg_color
        )
        sub_header.pack(anchor="w", pady=(sc(2), 0))

        # Quick actions if multiple items
        if len(self.updates) > 1:
            act_frame = tk.Frame(main_frame, bg=bg_color)
            act_frame.pack(fill="x", pady=(0, sc(8)))

            sel_all_btn = tk.Button(
                act_frame, text="Select All", command=self._select_all,
                font=("Segoe UI", sc(9)), bg=btn_sec_bg, fg=btn_sec_fg,
                relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3),
                highlightthickness=1, highlightbackground=border_color, highlightcolor=border_color
            )
            sel_all_btn.pack(side="left", padx=(0, sc(6)))
            sel_all_btn.bind("<Enter>", lambda e: sel_all_btn.config(bg=btn_sec_hover))
            sel_all_btn.bind("<Leave>", lambda e: sel_all_btn.config(bg=btn_sec_bg))

            desel_all_btn = tk.Button(
                act_frame, text="Deselect All", command=self._deselect_all,
                font=("Segoe UI", sc(9)), bg=btn_sec_bg, fg=btn_sec_fg,
                relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3),
                highlightthickness=1, highlightbackground=border_color, highlightcolor=border_color
            )
            desel_all_btn.pack(side="left")
            desel_all_btn.bind("<Enter>", lambda e: desel_all_btn.config(bg=btn_sec_hover))
            desel_all_btn.bind("<Leave>", lambda e: desel_all_btn.config(bg=btn_sec_bg))

        # Scrollable container
        container_frame = tk.Frame(main_frame, bg=bg_color, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
        container_frame.pack(fill="both", expand=True, pady=(0, sc(12)))

        self.canvas = tk.Canvas(container_frame, bg=bg_color, bd=0, highlightthickness=0)
        v_scroll = ttk.Scrollbar(container_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=v_scroll.set)

        self.scrollable_frame = tk.Frame(self.canvas, bg=bg_color, padx=sc(8), pady=sc(8))
        self.scroll_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.scrollable_frame.bind("<Configure>", lambda e: self._on_frame_configure())
        self.canvas.bind("<Configure>", lambda e: self._on_canvas_configure())

        # Mouse wheel support
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.scrollable_frame)

        # Build item rows
        for i, update in enumerate(self.updates):
            item_frame = tk.Frame(
                self.scrollable_frame,
                bg=card_bg,
                bd=1,
                relief="solid",
                highlightbackground=border_color,
                highlightthickness=1,
                pady=sc(8),
                padx=sc(10)
            )
            item_frame.pack(fill="x", expand=True, pady=(0, sc(8)))
            self._bind_mousewheel(item_frame)

            var = tk.BooleanVar(value=update.get("selected", True))
            self.vars.append(var)

            top_row = tk.Frame(item_frame, bg=card_bg)
            top_row.pack(fill="x", anchor="w")
            self._bind_mousewheel(top_row)

            cb = tk.Checkbutton(
                top_row,
                text=update["field"],
                variable=var,
                font=("Segoe UI", sc(10), "bold"),
                fg=fg_title,
                bg=card_bg,
                activebackground=card_bg,
                activeforeground=fg_title,
                selectcolor=card_bg,
                bd=0,
                highlightthickness=0,
                cursor="hand2"
            )
            cb.pack(side="left")
            self._bind_mousewheel(cb)

            # Data diff grid
            data_frame = tk.Frame(item_frame, bg=card_bg, padx=sc(24), pady=sc(4))
            data_frame.pack(fill="x", anchor="w")
            data_frame.columnconfigure(0, weight=1)
            data_frame.columnconfigure(1, weight=1)
            self._bind_mousewheel(data_frame)

            # Current (Old)
            old_chip = tk.Frame(
                data_frame,
                bg=chip_old_bg,
                bd=1,
                relief="solid",
                highlightbackground="#c93a40",
                highlightthickness=1,
                padx=sc(8),
                pady=sc(4)
            )
            old_chip.grid(row=0, column=0, sticky="ew", padx=(0, sc(6)))
            self._bind_mousewheel(old_chip)

            lbl_cur_tag = tk.Label(old_chip, text="CURRENT", font=("JetBrains Mono", sc(8), "bold"), fg=chip_old_fg, bg=chip_old_bg)
            lbl_cur_tag.pack(anchor="w")
            lbl_cur_val = tk.Label(old_chip, text=update["current"] or "(Empty)", font=("JetBrains Mono", sc(9.5)), fg=fg_title if update["current"] else fg_muted, bg=chip_old_bg, anchor="w")
            lbl_cur_val.pack(anchor="w")

            # Proposed (GBIF)
            new_chip = tk.Frame(
                data_frame,
                bg=chip_new_bg,
                bd=1,
                relief="solid",
                highlightbackground=chip_new_fg,
                highlightthickness=1,
                padx=sc(8),
                pady=sc(4)
            )
            new_chip.grid(row=0, column=1, sticky="ew", padx=(sc(6), 0))
            self._bind_mousewheel(new_chip)

            lbl_new_tag = tk.Label(new_chip, text="PROPOSED (GBIF)", font=("JetBrains Mono", sc(8), "bold"), fg=chip_new_fg, bg=chip_new_bg)
            lbl_new_tag.pack(anchor="w")
            lbl_new_val = tk.Label(new_chip, text=update["gbif"], font=("JetBrains Mono", sc(9.5), "bold"), fg=chip_new_fg, bg=chip_new_bg, anchor="w")
            lbl_new_val.pack(anchor="w")

            for w in (lbl_cur_tag, lbl_cur_val, lbl_new_tag, lbl_new_val):
                self._bind_mousewheel(w)

        # Footer Button Frame
        btn_frame = tk.Frame(main_frame, bg=bg_color)
        btn_frame.pack(fill="x", side="bottom")

        cancel_btn = tk.Button(
            btn_frame,
            text="CANCEL",
            command=self.destroy,
            font=("Segoe UI", sc(9.5), "bold"),
            bg=btn_sec_bg,
            fg=btn_sec_fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=sc(14),
            pady=sc(5),
            highlightthickness=1,
            highlightbackground=border_color,
            highlightcolor=border_color
        )
        cancel_btn.pack(side="right", padx=(sc(8), 0))
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg=btn_sec_hover))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg=btn_sec_bg))

        apply_btn = tk.Button(
            btn_frame,
            text="APPLY SELECTED UPDATES",
            command=self.apply,
            font=("Segoe UI", sc(9.5), "bold"),
            bg=btn_primary_bg,
            fg="#ffffff",
            relief="flat",
            bd=0,
            padx=sc(16),
            pady=sc(6),
            cursor="hand2"
        )
        apply_btn.pack(side="right")
        apply_btn.bind("<Enter>", lambda e, w=apply_btn: w.config(bg=btn_primary_hover))
        apply_btn.bind("<Leave>", lambda e, w=apply_btn: w.config(bg=btn_primary_bg))

    def _select_all(self):
        for v in self.vars:
            v.set(True)

    def _deselect_all(self):
        for v in self.vars:
            v.set(False)

    def _on_frame_configure(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self):
        self.canvas.itemconfig(self.scroll_window, width=self.canvas.winfo_width())

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

    def center_window(self, parent):
        self.update_idletasks()
        req_w = max(self.winfo_reqwidth(), sc(540))
        req_h = min(max(self.winfo_reqheight(), sc(380)), sc(600))
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (req_w // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (req_h // 2)
        self.geometry(f"{req_w}x{req_h}+{max(0, x)}+{max(0, y)}")
