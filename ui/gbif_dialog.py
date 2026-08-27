import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Tuple
from config import sc

class GBIFUpdateDialog(tk.Toplevel):
    def __init__(self, parent, updates: List[Dict]):
        """
        updates is a list of dictionaries, e.g.:
        [
            {"field": "Taxonomy", "current": "Quercus robur", "gbif": "Quercus robur", "selected": True, "data": {"genus": "Quercus", "species": "robur"}},
            {"field": "Author", "current": "L.", "gbif": "Linnaeus", "selected": True, "data": {"author": "Linnaeus"}},
        ]
        """
        super().__init__(parent)
        self.title("GBIF Updates Available")
        self.geometry(f"{sc(500)}x{sc(400)}")
        self.transient(parent)
        self.grab_set()

        self.updates = updates
        self.result_data = None  # Will hold combined data if approved
        self.vars = []

        self._build_ui()
        self.center_window(parent)

    def _build_ui(self):
        main_frame = tk.Frame(self, padx=sc(20), pady=sc(20), bg="#f8f9fa")
        main_frame.pack(fill="both", expand=True)

        header = tk.Label(main_frame, text="Select fields to update from GBIF:", font=("Segoe UI", sc(12), "bold"), bg="#f8f9fa")
        header.pack(anchor="w", pady=(0, sc(15)))

        list_frame = tk.Frame(main_frame, bg="#ffffff", bd=1, relief="solid")
        list_frame.pack(fill="both", expand=True, pady=(0, sc(20)))

        for update in self.updates:
            item_frame = tk.Frame(list_frame, bg="#ffffff", pady=sc(10), padx=sc(10), borderwidth=1, relief="flat")
            item_frame.pack(fill="x")

            # Create a subtle separator
            tk.Frame(item_frame, height=1, bg="#e9ecef").pack(side="bottom", fill="x", pady=(sc(10), 0))

            var = tk.BooleanVar(value=update.get("selected", True))
            self.vars.append(var)

            top_row = tk.Frame(item_frame, bg="#ffffff")
            top_row.pack(fill="x", anchor="w")

            cb = tk.Checkbutton(top_row, text=update["field"], variable=var, font=("Segoe UI", sc(10), "bold"), bg="#ffffff", cursor="hand2")
            cb.pack(side="left")

            data_frame = tk.Frame(item_frame, bg="#ffffff")
            data_frame.pack(fill="x", anchor="w", padx=(sc(25), 0), pady=(sc(5), 0))

            tk.Label(data_frame, text="Current:", font=("Segoe UI", sc(9)), fg="#6c757d", bg="#ffffff", width=8, anchor="e").grid(row=0, column=0, sticky="w", pady=2)
            tk.Label(data_frame, text=update["current"] or "(Empty)", font=("Segoe UI", sc(9)), bg="#ffffff").grid(row=0, column=1, sticky="w", pady=2)

            tk.Label(data_frame, text="GBIF:", font=("Segoe UI", sc(9)), fg="#2b8a3e", bg="#ffffff", width=8, anchor="e").grid(row=1, column=0, sticky="w", pady=2)
            tk.Label(data_frame, text=update["gbif"], font=("Segoe UI", sc(9), "bold"), fg="#2b8a3e", bg="#ffffff").grid(row=1, column=1, sticky="w", pady=2)

        btn_frame = tk.Frame(main_frame, bg="#f8f9fa")
        btn_frame.pack(fill="x", side="bottom")

        cancel_btn = tk.Button(btn_frame, text="Cancel", command=self.destroy, font=("Segoe UI", sc(10)), width=10)
        cancel_btn.pack(side="right", padx=(sc(10), 0))

        apply_btn = tk.Button(btn_frame, text="Apply Selected Updates", command=self.apply, font=("Segoe UI", sc(10), "bold"), bg="#2b8a3e", fg="white", width=20, cursor="hand2")
        apply_btn.pack(side="right")
        apply_btn.bind("<Enter>", lambda e, w=apply_btn: w.config(bg="#3bc954"))
        apply_btn.bind("<Leave>", lambda e, w=apply_btn: w.config(bg="#2b8a3e"))

    def apply(self):
        self.result_data = {}
        for update, var in zip(self.updates, self.vars):
            if var.get():
                self.result_data.update(update["data"])
        self.destroy()

    def center_window(self, parent):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
