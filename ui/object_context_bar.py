import tkinter as tk
from tkinter import ttk
import config
from config import sc
from ui.state import app_bus, OBJECT_LOADED, PROBLEM_STATE_CHANGED, DATABASE_UPDATED


class ObjectContextBar(ttk.Frame):
    """
    Curatorial Command Strip for the currently selected specimen object in Arbor.
    Provides clear, high-contrast specimen identity, active problem domain status,
    and direct workflow actions with zero visual noise and O(1) performance.
    """

    def __init__(self, parent, app=None, main_ui=None, **kwargs):
        super().__init__(parent, style="MiddlePane.TFrame", **kwargs)
        self.app = app
        self.main_ui = main_ui

        self.current_oid = None
        self.current_genus = ""
        self.current_species = ""
        self.current_author = ""
        self.problem_count = 0
        self.is_reviewed = False
        self.is_dark = getattr(main_ui, "dark_mode_active", False) if main_ui else False

        self.build_ui()
        self._subscribe_events()

    def set_dark_mode(self, is_dark: bool):
        """Update object context bar colors to match active theme."""
        self.is_dark = bool(is_dark)
        if not self.winfo_exists():
            return

        bg_card = "#212622" if self.is_dark else "#ffffff"
        border_col = "#313244" if self.is_dark else "#d1d1d1"
        fg_text = "#e8ebe9" if self.is_dark else "#2c302e"
        badge_bg = "#181c19" if self.is_dark else "#f2f5f1"
        badge_border = "#313244" if self.is_dark else "#c4c7c7"
        btn_bg = "#2a322c" if self.is_dark else "#f2f5f1"
        btn_active = "#343e37" if self.is_dark else "#e9ece5"
        btn_fg = "#e8ebe9" if self.is_dark else "#2c302e"

        if hasattr(self, "bar_frame") and self.bar_frame.winfo_exists():
            self.bar_frame.config(bg=bg_card, highlightbackground=border_col)
        if hasattr(self, "left_box") and self.left_box.winfo_exists():
            self.left_box.config(bg=bg_card)
        if hasattr(self, "right_box") and self.right_box.winfo_exists():
            self.right_box.config(bg=bg_card)
        if hasattr(self, "id_badge") and self.id_badge.winfo_exists():
            self.id_badge.config(bg=badge_bg, fg=fg_text, highlightbackground=badge_border)
        if hasattr(self, "index_label") and self.index_label.winfo_exists():
            self.index_label.config(bg=bg_card, fg="#9399b2" if self.is_dark else "#757d77")
        if hasattr(self, "name_label") and self.name_label.winfo_exists():
            self.name_label.config(bg=bg_card, fg=fg_text)
        if hasattr(self, "dirty_badge") and self.dirty_badge.winfo_exists():
            self.dirty_badge.config(bg=bg_card)

        if hasattr(self, "gbif_btn") and self.gbif_btn.winfo_exists():
            self.gbif_btn.config(bg=btn_bg, fg=btn_fg, activebackground=btn_active, activeforeground=fg_text)
        if hasattr(self, "hist_btn") and self.hist_btn.winfo_exists():
            self.hist_btn.config(bg=btn_bg, fg=btn_fg, activebackground=btn_active, activeforeground=fg_text)
        if hasattr(self, "mobile_push_btn") and self.mobile_push_btn.winfo_exists():
            self.mobile_push_btn.config(bg=btn_bg, fg=btn_fg, activebackground=btn_active, activeforeground=fg_text)

        self.update_specimen(self.current_oid)

    def _subscribe_events(self):
        if app_bus:
            app_bus.subscribe_managed(self, OBJECT_LOADED, self._on_object_loaded)
            app_bus.subscribe_managed(self, PROBLEM_STATE_CHANGED, self._on_problem_changed)
            app_bus.subscribe_managed(self, DATABASE_UPDATED, self._on_database_updated)

    def build_ui(self):
        bg_card = "#212622" if self.is_dark else "#ffffff"
        border_col = "#313244" if self.is_dark else "#d1d1d1"
        fg_text = "#e8ebe9" if self.is_dark else "#2c302e"
        badge_bg = "#181c19" if self.is_dark else "#f2f5f1"
        badge_border = "#313244" if self.is_dark else "#c4c7c7"
        btn_bg = "#2a322c" if self.is_dark else "#f2f5f1"
        btn_active = "#343e37" if self.is_dark else "#e9ece5"
        btn_fg = "#e8ebe9" if self.is_dark else "#2c302e"

        # 1px border container
        self.bar_frame = tk.Frame(
            self,
            bg=bg_card,
            highlightthickness=1,
            highlightbackground=border_col,
            padx=sc(10),
            pady=sc(4)
        )
        self.bar_frame.pack(fill="x", expand=True, padx=sc(2), pady=(sc(1), sc(2)))

        # Left: Specimen Identifier & Nomenclature
        self.left_box = tk.Frame(self.bar_frame, bg=bg_card)
        self.left_box.pack(side="left", fill="y", anchor="center")

        # Accession ID chip
        self.id_badge = tk.Label(
            self.left_box,
            text="ID: --",
            font=("JetBrains Mono", sc(9), "bold"),
            bg=badge_bg,
            fg=fg_text,
            padx=sc(7),
            pady=sc(2),
            relief="solid",
            bd=1,
            highlightbackground=badge_border,
            highlightthickness=0
        )
        self.id_badge.pack(side="left", padx=(0, sc(6)))

        # Specimen index position counter (e.g., "42 of 1,250")
        self.index_label = tk.Label(
            self.left_box,
            text="",
            font=("Inter", sc(8)),
            bg=bg_card,
            fg="#9399b2" if self.is_dark else "#757d77"
        )
        self.index_label.pack(side="left", padx=(0, sc(8)))

        # Botanical scientific name
        self.name_label = tk.Label(
            self.left_box,
            text="No Specimen Selected",
            font=("Lora", sc(12), "bold italic"),
            bg=bg_card,
            fg=fg_text
        )
        self.name_label.pack(side="left", padx=(0, sc(8)))

        # Status badge (Domain category aware, soft-pill styling)
        self.status_badge = tk.Label(
            self.left_box,
            text="UNREVIEWED",
            font=("JetBrains Mono", sc(8), "bold"),
            bg="#242725" if self.is_dark else "#f2f5f1",
            fg="#9ca3af" if self.is_dark else "#757d77",
            padx=sc(6),
            pady=sc(2),
            relief="solid",
            bd=1,
            highlightthickness=0,
            cursor="hand2"
        )
        self.status_badge.pack(side="left", padx=(0, sc(6)))
        self.status_badge.bind("<Button-1>", self._on_status_badge_clicked)

        # Unsaved changes indicator dot
        self.dirty_badge = tk.Label(
            self.left_box,
            text="● Unsaved",
            font=("Inter", sc(8), "bold"),
            bg=bg_card,
            fg="#d9a036"
        )
        self.dirty_badge.pack(side="left", padx=(sc(4), 0))
        self.dirty_badge.pack_forget()

        # Right: Clean Contextual Action Buttons (Zero emojis)
        self.right_box = tk.Frame(self.bar_frame, bg=bg_card)
        self.right_box.pack(side="right", fill="y", anchor="center")

        # 1. GBIF Validation Button
        self.gbif_btn = tk.Button(
            self.right_box,
            text="GBIF Verify",
            font=("Inter", sc(9), "bold"),
            bg=btn_bg,
            fg=btn_fg,
            activebackground=btn_active,
            activeforeground=fg_text,
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=sc(8),
            pady=sc(2),
            cursor="hand2",
            command=self._on_gbif_clicked
        )
        self.gbif_btn.pack(side="left", padx=sc(3))
        if self.main_ui and hasattr(self.main_ui, "add_tooltip"):
            self.main_ui.add_tooltip(self.gbif_btn, "Validate botanical nomenclature with GBIF Backbone Taxonomy")

        # 2. Historical Conflicts Button
        self.hist_btn = tk.Button(
            self.right_box,
            text="Books",
            font=("Inter", sc(9), "bold"),
            bg=btn_bg,
            fg=btn_fg,
            activebackground=btn_active,
            activeforeground=fg_text,
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=sc(8),
            pady=sc(2),
            cursor="hand2",
            command=self._on_hist_clicked
        )
        self.hist_btn.pack(side="left", padx=sc(3))
        if self.main_ui and hasattr(self.main_ui, "add_tooltip"):
            self.main_ui.add_tooltip(self.hist_btn, "Open Historical Database Conflict Resolver")

        # 3. Contextual Mobile Push
        self.mobile_push_btn = tk.Button(
            self.right_box,
            text="Send to Phone",
            font=("Inter", sc(9)),
            bg=btn_bg,
            fg=btn_fg,
            activebackground=btn_active,
            activeforeground=fg_text,
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=sc(8),
            pady=sc(2),
            cursor="hand2",
            command=self._on_mobile_push_clicked
        )
        self.mobile_push_btn.pack(side="left", padx=sc(3))
        if self.main_ui and hasattr(self.main_ui, "add_tooltip"):
            self.main_ui.add_tooltip(self.mobile_push_btn, "Push this record to active mobile companion session")

    def update_specimen(self, oid=None):
        """Update specimen display and contextual button states with O(1) cached dictionary lookups."""
        if not self.winfo_exists():
            return

        if oid is None:
            oid = getattr(self.app, "current_object_id", None) if self.app else None

        self.current_oid = oid
        if not oid:
            self.id_badge.config(text="ID: --")
            self.index_label.config(text="")
            self.name_label.config(text="No Specimen Selected")
            self.status_badge.config(
                text="NO DATA",
                bg="#242725" if self.is_dark else "#f2f5f1",
                fg="#9ca3af" if self.is_dark else "#757d77",
                relief="flat"
            )
            self.dirty_badge.pack_forget()
            self.gbif_btn.config(state="disabled")
            self.hist_btn.config(state="disabled")
            self.mobile_push_btn.config(state="disabled")
            return

        self.gbif_btn.config(state="normal")
        self.hist_btn.config(state="normal")
        self.mobile_push_btn.config(state="normal")

        self.id_badge.config(text=f"ID: {oid}")

        # Update position counter ("X of N")
        if self.app and getattr(self.app, "active_object_ids", None):
            try:
                idx = self.app.active_object_ids.index(oid) + 1
                total = len(self.app.active_object_ids)
                self.index_label.config(text=f"{idx} of {total:,}")
            except (ValueError, TypeError):
                self.index_label.config(text="")
        else:
            self.index_label.config(text="")

        # Fetch active registration data using O(1) dictionary lookup (Zero df.loc overhead)
        genus = ""
        species = ""
        author = ""
        is_reviewed = False
        prob_count = 0

        reg_dict = self.main_ui._get_reg_dict() if self.main_ui and hasattr(self.main_ui, "_get_reg_dict") else {}
        obs_dict = self.main_ui._get_obs_dict() if self.main_ui and hasattr(self.main_ui, "_get_obs_dict") else {}

        row = reg_dict.get(oid) or reg_dict.get(str(oid)) or (reg_dict.get(int(oid)) if str(oid).isdigit() else {}) or {}
        obs_row = obs_dict.get(oid) or obs_dict.get(str(oid)) or (obs_dict.get(int(oid)) if str(oid).isdigit() else {}) or {}

        if row:
            g_raw = str(row.get("Genus", "")).strip()
            genus = "" if g_raw in ("nan", "None", "<NA>") else g_raw
            s_raw = str(row.get("Species", "")).strip()
            species = "" if s_raw in ("nan", "None", "<NA>") else s_raw
            a_raw = str(row.get("Author", "")).strip()
            author = "" if a_raw in ("nan", "None", "<NA>") else a_raw

        if obs_row:
            rev_val = obs_row.get("Reviewed", False)
            is_reviewed = bool(rev_val) and str(rev_val).lower() not in ("false", "0", "nan", "none")

        # Format Botanical Name
        name_parts = []
        if genus:
            name_parts.append(genus)
        if species:
            name_parts.append(species)
        if author:
            name_parts.append(f"({author})" if not author.startswith("(") else author)

        botanical_name = " ".join(name_parts) if name_parts else "Unclassified Specimen"
        self.name_label.config(text=botanical_name)

        # Retrieve active category themes & conflicts
        active_cats = self.main_ui._get_active_problem_categories(oid) if self.main_ui and hasattr(self.main_ui, "_get_active_problem_categories") else set()
        has_problem = bool(active_cats) or (self.main_ui._get_cached_problem(oid) if self.main_ui and hasattr(self.main_ui, "_get_cached_problem") else getattr(self.main_ui, "_problem_cache", {}).get(oid, False))
        problems_have_history = self.main_ui._problems_have_history(oid) if self.main_ui and hasattr(self.main_ui, "_problems_have_history") else False

        # Soft-pill domain status styling aligning with AI_UI_GUIDE design tokens
        if is_reviewed and not has_problem:
            badge_text = "✓ REVIEWED"
            badge_bg = "#162d1a" if self.is_dark else "#f2f9f3"
            badge_fg = "#85e89d" if self.is_dark else "#3a7d44"
        elif is_reviewed and has_problem:
            badge_text = "REV + PROBLEM"
            badge_bg = "#3b2e15" if self.is_dark else "#fef9e7"
            badge_fg = "#fcd34d" if self.is_dark else "#b45309"
        elif "taxonomy" in active_cats:
            badge_text = "TAXONOMY ISSUE"
            badge_bg = "#3b1c1e" if self.is_dark else "#fdf2f2"
            badge_fg = "#f28b82" if self.is_dark else "#c93a40"
        elif "collection" in active_cats:
            badge_text = "PROVENANCE ERROR"
            badge_bg = "#3b2e15" if self.is_dark else "#fef9e7"
            badge_fg = "#fcd34d" if self.is_dark else "#b45309"
        elif "physical" in active_cats:
            badge_text = "STORAGE AUDIT"
            badge_bg = "#2d2422" if self.is_dark else "#f7f5f4"
            badge_fg = "#d7ccc8" if self.is_dark else "#795548"
        elif "media" in active_cats:
            badge_text = "MEDIA DIGITIZATION"
            badge_bg = "#1a2c3d" if self.is_dark else "#f0f8ff"
            badge_fg = "#7dd3fc" if self.is_dark else "#0284c7"
        elif has_problem and problems_have_history:
            badge_text = "ERROR + CONFLICT"
            badge_bg = "#2a1b3d" if self.is_dark else "#f3e8ff"
            badge_fg = "#d8b4fe" if self.is_dark else "#7b1fa2"
        elif has_problem:
            badge_text = "RECORD ERROR"
            badge_bg = "#3b1c1e" if self.is_dark else "#fdf2f2"
            badge_fg = "#f28b82" if self.is_dark else "#c93a40"
        elif problems_have_history:
            badge_text = "BOOK CONFLICT"
            badge_bg = "#1e293b" if self.is_dark else "#e9f0f5"
            badge_fg = "#93c5fd" if self.is_dark else "#4a7b9d"
        else:
            badge_text = "UNREVIEWED"
            badge_bg = "#242725" if self.is_dark else "#f2f5f1"
            badge_fg = "#9ca3af" if self.is_dark else "#757d77"

        self.status_badge.config(
            text=badge_text,
            bg=badge_bg,
            fg=badge_fg,
            relief="solid"
        )

        # Unsaved edits indicator
        is_dirty = bool(getattr(self.app, "dirty", False))
        if is_dirty:
            if self.dirty_badge.winfo_manager() != "pack":
                self.dirty_badge.pack(side="left", padx=(sc(4), 0))
        else:
            if self.dirty_badge.winfo_manager() == "pack":
                self.dirty_badge.pack_forget()

        # Check historical suggestions availability for clean button label
        if self.main_ui and hasattr(self.main_ui, "_history_cache"):
            sugg = self.main_ui._history_cache.get(str(oid)) or self.main_ui._history_cache.get(int(oid) if str(oid).isdigit() else None)
            if sugg:
                self.hist_btn.config(
                    text=f"Books ({len(sugg)})",
                    bg="#1e2d3d" if self.is_dark else "#e9f0f5",
                    fg="#7dd3fc" if self.is_dark else "#4a7b9d"
                )
            else:
                btn_bg = "#2a322c" if self.is_dark else "#f2f5f1"
                btn_fg = "#e8ebe9" if self.is_dark else "#2c302e"
                self.hist_btn.config(text="Books", bg=btn_bg, fg=btn_fg)

    def _on_status_badge_clicked(self, event=None):
        """Clicking the status badge directly launches the corresponding resolver."""
        if not self.current_oid:
            return
        if self.main_ui and hasattr(self.main_ui, "_history_cache") and self.main_ui._problems_have_history(self.current_oid):
            self._on_hist_clicked()
        elif self.main_ui and hasattr(self.main_ui, "open_problem_resolver_for_object"):
            self.main_ui.open_problem_resolver_for_object(self.current_oid)
        elif self.main_ui and hasattr(self.main_ui, "open_object_problem_resolver"):
            self.main_ui.open_object_problem_resolver()

    def _on_object_loaded(self, *args, **kwargs):
        payload = args[0] if args else kwargs.get("payload", None)
        oid = payload if isinstance(payload, (str, int)) else getattr(payload, "id", None)
        self.update_specimen(oid)

    def _on_problem_changed(self, *args, **kwargs):
        self.update_specimen(self.current_oid)

    def _on_database_updated(self, *args, **kwargs):
        self.update_specimen(self.current_oid)

    def _on_gbif_clicked(self):
        if self.main_ui and hasattr(self.main_ui, "run_gbif_verification_for_current"):
            self.main_ui.run_gbif_verification_for_current()
        elif self.main_ui and hasattr(self.main_ui, "show_gbif_dropdown"):
            self.main_ui.show_gbif_dropdown()

    def _on_hist_clicked(self):
        if self.main_ui and hasattr(self.main_ui, "open_historical_resolver_for_current"):
            self.main_ui.open_historical_resolver_for_current()
        elif self.main_ui and hasattr(self.main_ui, "open_load_data_menu"):
            self.main_ui.open_load_data_menu()

    def _on_mobile_push_clicked(self):
        if self.main_ui and hasattr(self.main_ui, "push_current_to_phone"):
            self.main_ui.push_current_to_phone()
