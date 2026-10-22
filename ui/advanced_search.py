"""ui/advanced_search.py - Advanced Historical Search Dialog for Tkinter interface.

Provides multi-field criteria search across primary specimen records (app.df_reg)
and attached historical archival ledger books (app.historical_dbs).
Executes queries non-blockingly on a background thread using backend.search.execute_advanced_historical_search.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

import config
from backend.search import execute_advanced_historical_search
from models import AppState


class AdvancedSearchDialog(tk.Toplevel):
    """Modal dialog for executing multi-field historical search in Tkinter."""

    def __init__(
        self,
        parent: tk.Widget,
        app_state: AppState,
        on_applied: Optional[Callable[[list[str]], None]] = None,
    ):
        super().__init__(parent)
        self.withdraw()  # Prevent flashing while layout builds
        self.parent = parent
        self.app = app_state
        self.on_applied = on_applied

        self._worker_thread: Optional[threading.Thread] = None
        self._is_cancelled = False
        self._queue: queue.Queue = queue.Queue()
        self.matched_oids: list[str] = []

        sc = config.sc

        # Colors adhering to Arbor AI UI Design tokens
        self.colors = {
            "surface": "#fbfaf8",
            "card": "#ffffff",
            "low": "#f2f5f1",
            "container": "#e9ece5",
            "border": "#747878",
            "hairline": "#c4c7c7",
            "text": "#2c302e",
            "subtext": "#747878",
            "primary": "#000000",
            "on_primary": "#ffffff",
            "green": "#3a7d44",
        }

        # Fonts
        self.font_title = ("Hanken Grotesk", sc(12), "bold")
        self.font_sub = ("Segoe UI", sc(9))
        self.font_heading = ("Segoe UI", sc(9), "bold")
        self.font_label = ("Segoe UI", sc(9))
        self.font_mono = ("Courier New", sc(10))
        self.font_btn = ("Segoe UI", sc(9), "bold")

        self.title("Advanced Historical Search")
        self.configure(bg=self.colors["surface"])
        self.geometry(f"{sc(620)}x{sc(590)}")
        self.minsize(sc(520), sc(480))

        # Dialog modality & key bindings
        self.transient(parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else parent)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Escape>", lambda e: self.on_close())
        self.bind("<Return>", lambda e: self.start_search())

        self._build_ui()

        # Center on parent window and show
        self.update_idletasks()
        try:
            p_win = parent.winfo_toplevel()
            pw, ph = p_win.winfo_width(), p_win.winfo_height()
            px, py = p_win.winfo_rootx(), p_win.winfo_rooty()
            w, h = self.winfo_width(), self.winfo_height()
            x = max(0, px + (pw - w) // 2)
            y = max(0, py + (ph - h) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

        self.deiconify()
        self.lift()
        self.focus_force()
        self.entry_genus.focus_set()

    def _build_ui(self) -> None:
        sc = config.sc
        pad = sc(14)

        root_frame = tk.Frame(self, bg=self.colors["surface"])
        root_frame.pack(fill="both", expand=True, padx=pad, pady=pad)

        # 1. Header Section
        header_frame = tk.Frame(root_frame, bg=self.colors["surface"])
        header_frame.pack(fill="x", pady=(0, sc(10)))

        lbl_title = tk.Label(
            header_frame,
            text="ADVANCED HISTORICAL SEARCH",
            font=self.font_title,
            fg=self.colors["text"],
            bg=self.colors["surface"],
        )
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(
            header_frame,
            text="Search across active registry records and attached archival historical ledger books.",
            font=self.font_sub,
            fg=self.colors["subtext"],
            bg=self.colors["surface"],
        )
        lbl_sub.pack(anchor="w", pady=(sc(2), 0))

        # 2. Form Card Frame
        form_card = tk.Frame(
            root_frame,
            bg=self.colors["card"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            bd=0,
        )
        form_card.pack(fill="x", pady=(0, sc(10)), ipady=sc(6))

        self.entries: dict[str, tk.Entry] = {}
        fields = [
            ("Genus", "e.g. Quercus, herbaria"),
            ("Species", "e.g. alba, testia"),
            ("Author", "e.g. L., Michx."),
            ("Family", "e.g. Fagaceae"),
            ("Collector", "e.g. Smith, John"),
            ("Locality", "e.g. Ridge trail, County"),
            ("Year", "e.g. 1924"),
        ]

        for row_idx, (fld_name, placeholder) in enumerate(fields):
            row_frame = tk.Frame(form_card, bg=self.colors["card"])
            row_frame.pack(fill="x", padx=sc(12), pady=sc(3))

            lbl = tk.Label(
                row_frame,
                text=f"{fld_name}:",
                font=self.font_label,
                fg=self.colors["text"],
                bg=self.colors["card"],
                width=10,
                anchor="w",
            )
            lbl.pack(side="left")

            entry = tk.Entry(
                row_frame,
                font=self.font_mono,
                bg=self.colors["card"],
                fg=self.colors["text"],
                insertbackground=self.colors["primary"],
                highlightbackground=self.colors["hairline"],
                highlightcolor=self.colors["primary"],
                highlightthickness=1,
                relief="flat",
                bd=0,
            )
            entry.pack(side="left", fill="x", expand=True, ipady=sc(3))
            self.entries[fld_name] = entry

        self.entry_genus = self.entries["Genus"]
        self.entry_species = self.entries["Species"]
        self.entry_author = self.entries["Author"]
        self.entry_family = self.entries["Family"]
        self.entry_collector = self.entries["Collector"]
        self.entry_locality = self.entries["Locality"]
        self.entry_year = self.entries["Year"]

        # 3. Options Card Frame
        opt_card = tk.Frame(
            root_frame,
            bg=self.colors["card"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            bd=0,
        )
        opt_card.pack(fill="x", pady=(0, sc(10)), padx=0)

        inner_opt = tk.Frame(opt_card, bg=self.colors["card"])
        inner_opt.pack(fill="x", padx=sc(12), pady=sc(10))

        # Scope options (Left column)
        scope_frame = tk.Frame(inner_opt, bg=self.colors["card"])
        scope_frame.pack(side="left", fill="both", expand=True)

        tk.Label(
            scope_frame,
            text="SEARCH SCOPE",
            font=self.font_heading,
            fg=self.colors["subtext"],
            bg=self.colors["card"],
        ).pack(anchor="w", pady=(0, sc(4)))

        self.var_scope = tk.StringVar(value="both")
        r_both = tk.Radiobutton(
            scope_frame,
            text="Both (Current & Suggestions)",
            variable=self.var_scope,
            value="both",
            font=self.font_label,
            bg=self.colors["card"],
            fg=self.colors["text"],
            activebackground=self.colors["card"],
            highlightthickness=0,
        )
        r_both.pack(anchor="w")

        r_sugg = tk.Radiobutton(
            scope_frame,
            text="Historical Suggestions Only (Discrepancies)",
            variable=self.var_scope,
            value="suggestions_only",
            font=self.font_label,
            bg=self.colors["card"],
            fg=self.colors["text"],
            activebackground=self.colors["card"],
            highlightthickness=0,
        )
        r_sugg.pack(anchor="w")

        r_curr = tk.Radiobutton(
            scope_frame,
            text="Current Values Only",
            variable=self.var_scope,
            value="current",
            font=self.font_label,
            bg=self.colors["card"],
            fg=self.colors["text"],
            activebackground=self.colors["card"],
            highlightthickness=0,
        )
        r_curr.pack(anchor="w")

        # Vertical divider
        div = tk.Frame(inner_opt, bg=self.colors["hairline"], width=1)
        div.pack(side="left", fill="y", padx=sc(16))

        # Match logic options (Right column)
        logic_frame = tk.Frame(inner_opt, bg=self.colors["card"])
        logic_frame.pack(side="left", fill="both", expand=True)

        tk.Label(
            logic_frame,
            text="MATCH LOGIC",
            font=self.font_heading,
            fg=self.colors["subtext"],
            bg=self.colors["card"],
        ).pack(anchor="w", pady=(0, sc(4)))

        self.var_logic = tk.BooleanVar(value=True)
        r_and = tk.Radiobutton(
            logic_frame,
            text="Match ALL fields (AND)",
            variable=self.var_logic,
            value=True,
            font=self.font_label,
            bg=self.colors["card"],
            fg=self.colors["text"],
            activebackground=self.colors["card"],
            highlightthickness=0,
        )
        r_and.pack(anchor="w")

        r_or = tk.Radiobutton(
            logic_frame,
            text="Match ANY field (OR)",
            variable=self.var_logic,
            value=False,
            font=self.font_label,
            bg=self.colors["card"],
            fg=self.colors["text"],
            activebackground=self.colors["card"],
            highlightthickness=0,
        )
        r_or.pack(anchor="w")

        # 4. Progress bar
        self.progress_bar = ttk.Progressbar(root_frame, mode="determinate", maximum=100)
        self.progress_bar.pack(fill="x", pady=(0, sc(6)))
        self.progress_bar.pack_forget()  # Hide initially

        # 5. Status label & Action Footer
        footer_frame = tk.Frame(root_frame, bg=self.colors["surface"])
        footer_frame.pack(fill="x", side="bottom")

        self.lbl_status = tk.Label(
            footer_frame,
            text="Enter search terms and click Search.",
            font=self.font_sub,
            fg=self.colors["text"],
            bg=self.colors["surface"],
        )
        self.lbl_status.pack(side="left", anchor="w")

        btn_box = tk.Frame(footer_frame, bg=self.colors["surface"])
        btn_box.pack(side="right")

        self.btn_reset = tk.Button(
            btn_box,
            text="Reset / Clear",
            font=self.font_btn,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            activebackground=self.colors["container"],
            relief="flat",
            bd=0,
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            padx=sc(12),
            pady=sc(4),
            cursor="hand2",
            command=self.reset_form,
        )
        self.btn_reset.pack(side="left", padx=(0, sc(6)))

        self.btn_close = tk.Button(
            btn_box,
            text="Close",
            font=self.font_btn,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            activebackground=self.colors["container"],
            relief="flat",
            bd=0,
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            padx=sc(12),
            pady=sc(4),
            cursor="hand2",
            command=self.on_close,
        )
        self.btn_close.pack(side="left", padx=(0, sc(6)))

        self.btn_search = tk.Button(
            btn_box,
            text="Search",
            font=self.font_btn,
            bg=self.colors["primary"],
            fg=self.colors["on_primary"],
            activebackground=self.colors["text"],
            activeforeground=self.colors["on_primary"],
            relief="flat",
            bd=0,
            padx=sc(16),
            pady=sc(4),
            cursor="hand2",
            command=self.start_search,
        )
        self.btn_search.pack(side="left")

    def get_criteria(self) -> dict[str, str]:
        """Extract non-empty search terms from input fields."""
        criteria: dict[str, str] = {}
        for fld, entry in self.entries.items():
            txt = entry.get().strip()
            if txt:
                criteria[fld] = txt
        return criteria

    def get_scope(self) -> str:
        """Return selected search scope."""
        return self.var_scope.get()

    def get_match_all(self) -> bool:
        """Return True for AND logic, False for OR logic."""
        return bool(self.var_logic.get())

    def start_search(self) -> None:
        """Launch background search thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            return

        criteria = self.get_criteria()
        scope = self.get_scope()
        match_all = self.get_match_all()

        # Drain any residual queue items
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break

        # Update UI state
        self.btn_search.config(state="disabled", text="Searching...")
        self.progress_bar.pack(fill="x", pady=(0, config.sc(6)))
        self.progress_bar["value"] = 0
        self.lbl_status.config(text="Querying records and historical books...")

        self._is_cancelled = False
        hist_dbs = getattr(self.app, "historical_dbs", None)

        self._worker_thread = threading.Thread(
            target=self._search_worker,
            args=(self.app.df_reg, hist_dbs, criteria, scope, match_all),
            daemon=True,
        )
        self._worker_thread.start()
        self.after(30, self._poll_queue)

    def _poll_queue(self) -> None:
        """Process messages emitted by background thread safely on the main thread."""
        if not self.winfo_exists():
            return

        has_finished = False
        while not self._queue.empty():
            try:
                msg_type, payload = self._queue.get_nowait()
            except Exception:
                break

            if msg_type == "progress":
                self._on_progress(payload)
            elif msg_type == "finished":
                has_finished = True
                self._on_finished(payload)
                break
            elif msg_type == "error":
                has_finished = True
                self._on_error(payload)
                break

        if not has_finished and self.winfo_exists():
            if self._worker_thread and self._worker_thread.is_alive():
                self.after(30, self._poll_queue)

    def _search_worker(
        self,
        df_reg,
        historical_dbs: list[dict] | None,
        field_criteria: dict[str, str],
        scope: str,
        match_all: bool,
    ) -> None:
        """Worker thread entry point."""
        try:
            results = execute_advanced_historical_search(
                df_reg=df_reg,
                historical_dbs=historical_dbs,
                field_criteria=field_criteria,
                scope=scope,
                match_all=match_all,
                is_cancelled=lambda: self._is_cancelled,
                progress_callback=lambda p: self._queue.put(("progress", p)),
            )
            if not self._is_cancelled:
                self._queue.put(("finished", results))
        except Exception as exc:
            if not self._is_cancelled:
                self._queue.put(("error", str(exc)))

    def _on_progress(self, val: int) -> None:
        if self.winfo_exists():
            self.progress_bar["value"] = val

    def _on_finished(self, matched_oids: list[str]) -> None:
        if not self.winfo_exists():
            return

        self.matched_oids = matched_oids
        self.btn_search.config(state="normal", text="Search")
        self.progress_bar["value"] = 100

        count = len(matched_oids)
        self.lbl_status.config(text=f"Search complete: {count} specimen(s) found.")

        if self.on_applied:
            self.on_applied(matched_oids)

        self.destroy()

    def _on_error(self, err_msg: str) -> None:
        if not self.winfo_exists():
            return
        self.btn_search.config(state="normal", text="Search")
        self.lbl_status.config(text=f"Error: {err_msg}")
        messagebox.showerror("Search Error", f"An error occurred during search:\n{err_msg}", parent=self)

    def reset_form(self) -> None:
        """Clear all inputs and reset options."""
        for entry in self.entries.values():
            entry.delete(0, tk.END)

        self.var_scope.set("both")
        self.var_logic.set(True)
        self.progress_bar.pack_forget()
        self.progress_bar["value"] = 0
        self.lbl_status.config(text="Criteria reset. Enter search terms and click Search.")

    def on_close(self) -> None:
        """Abort active worker thread and close window."""
        self._is_cancelled = True
        self.destroy()
