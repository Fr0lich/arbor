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
        self.configure(bg="#f8f9fa")

        main_frame = tk.Frame(self, padx=sc(16), pady=sc(16), bg="#f8f9fa")
        main_frame.pack(fill="both", expand=True)

        # Header
        header_frame = tk.Frame(main_frame, bg="#f8f9fa")
        header_frame.pack(fill="x", pady=(0, sc(10)))

        header = tk.Label(
            header_frame,
            text="Proposed Taxonomic Updates",
            font=("Segoe UI", sc(12), "bold"),
            fg="#2c302e",
            bg="#f8f9fa"
        )
        header.pack(anchor="w")

        sub_header = tk.Label(
            header_frame,
            text=f"GBIF suggested updates for {len(self.updates)} field(s). Select the changes to apply:",
            font=("Segoe UI", sc(9)),
            fg="#757d77",
            bg="#f8f9fa"
        )
        sub_header.pack(anchor="w", pady=(sc(2), 0))

        # Quick actions if multiple items
        if len(self.updates) > 1:
            act_frame = tk.Frame(main_frame, bg="#f8f9fa")
            act_frame.pack(fill="x", pady=(0, sc(8)))

            ttk.Button(act_frame, text="Select All", command=self._select_all).pack(side="left", padx=(0, sc(6)))
            ttk.Button(act_frame, text="Deselect All", command=self._deselect_all).pack(side="left")

        # Scrollable container
        container_frame = tk.Frame(main_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground="#e9ece5")
        container_frame.pack(fill="both", expand=True, pady=(0, sc(14)))

        self.canvas = tk.Canvas(container_frame, bg="#ffffff", bd=0, highlightthickness=0)
        v_scroll = ttk.Scrollbar(container_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=v_scroll.set)

        self.scrollable_frame = tk.Frame(self.canvas, bg="#ffffff", padx=sc(10), pady=sc(10))
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
            item_frame = tk.Frame(self.scrollable_frame, bg="#ffffff", pady=sc(8), padx=sc(8))
            item_frame.pack(fill="x", expand=True)
            self._bind_mousewheel(item_frame)

            var = tk.BooleanVar(value=update.get("selected", True))
            self.vars.append(var)

            top_row = tk.Frame(item_frame, bg="#ffffff")
            top_row.pack(fill="x", anchor="w")
            self._bind_mousewheel(top_row)

            cb = tk.Checkbutton(
                top_row,
                text=update["field"],
                variable=var,
                font=("Segoe UI", sc(10), "bold"),
                fg="#2c302e",
                bg="#ffffff",
                activebackground="#ffffff",
                cursor="hand2"
            )
            cb.pack(side="left")
            self._bind_mousewheel(cb)

            # Data diff grid
            data_frame = tk.Frame(item_frame, bg="#fafafa", bd=1, relief="solid", padx=sc(10), pady=sc(6))
            data_frame.pack(fill="x", anchor="w", padx=(sc(24), 0), pady=(sc(4), 0))
            self._bind_mousewheel(data_frame)

            # Current (Old)
            lbl_cur_tag = tk.Label(data_frame, text="Current:", font=("Segoe UI", sc(9), "bold"), fg="#c93a40", bg="#fafafa", width=8, anchor="e")
            lbl_cur_tag.grid(row=0, column=0, sticky="w", pady=2)
            lbl_cur_val = tk.Label(data_frame, text=update["current"] or "(Empty)", font=("Segoe UI", sc(9)), fg="#555555", bg="#fafafa", anchor="w")
            lbl_cur_val.grid(row=0, column=1, sticky="w", padx=(sc(6), 0), pady=2)

            # Proposed (GBIF)
            lbl_new_tag = tk.Label(data_frame, text="GBIF:", font=("Segoe UI", sc(9), "bold"), fg="#2b8a3e", bg="#fafafa", width=8, anchor="e")
            lbl_new_tag.grid(row=1, column=0, sticky="w", pady=2)
            lbl_new_val = tk.Label(data_frame, text=update["gbif"], font=("Segoe UI", sc(9), "bold"), fg="#2b8a3e", bg="#fafafa", anchor="w")
            lbl_new_val.grid(row=1, column=1, sticky="w", padx=(sc(6), 0), pady=2)

            for w in (lbl_cur_tag, lbl_cur_val, lbl_new_tag, lbl_new_val):
                self._bind_mousewheel(w)

            # Separator between items (except last)
            if i < len(self.updates) - 1:
                sep = tk.Frame(self.scrollable_frame, height=1, bg="#e9ece5")
                sep.pack(fill="x", pady=(sc(8), sc(4)))
                self._bind_mousewheel(sep)

        # Footer Button Frame
        btn_frame = tk.Frame(main_frame, bg="#f8f9fa")
        btn_frame.pack(fill="x", side="bottom")

        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            font=("Segoe UI", sc(10)),
            bg="#f1f3f5",
            fg="#2c302e",
            bd=1,
            relief="solid",
            width=10,
            cursor="hand2"
        )
        cancel_btn.pack(side="right", padx=(sc(10), 0))

        apply_btn = tk.Button(
            btn_frame,
            text="Apply Selected Updates",
            command=self.apply,
            font=("Segoe UI", sc(10), "bold"),
            bg="#2b8a3e",
            fg="white",
            bd=0,
            padx=sc(12),
            pady=sc(4),
            cursor="hand2"
        )
        apply_btn.pack(side="right")
        apply_btn.bind("<Enter>", lambda e, w=apply_btn: w.config(bg="#3bc954"))
        apply_btn.bind("<Leave>", lambda e, w=apply_btn: w.config(bg="#2b8a3e"))

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
        req_w = max(self.winfo_reqwidth(), sc(520))
        req_h = min(max(self.winfo_reqheight(), sc(380)), sc(600))
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (req_w // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (req_h // 2)
        self.geometry(f"{req_w}x{req_h}+{max(0, x)}+{max(0, y)}")
