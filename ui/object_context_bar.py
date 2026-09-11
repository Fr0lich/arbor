import tkinter as tk
from tkinter import ttk
import config
from config import sc
from ui.state import app_bus, OBJECT_LOADED, PROBLEM_STATE_CHANGED, DATABASE_UPDATED


class ObjectContextBar(ttk.Frame):
    """
    Contextual Action Strip for the currently selected specimen object in Arbor.
    Clearly separates local record actions (GBIF lookup, Historical Conflicts, Mobile Push)
    from global application navigation.
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

        self.build_ui()
        self._subscribe_events()

    def _subscribe_events(self):
        if app_bus:
            app_bus.subscribe_managed(self, OBJECT_LOADED, self._on_object_loaded)
            app_bus.subscribe_managed(self, PROBLEM_STATE_CHANGED, self._on_problem_changed)
            app_bus.subscribe_managed(self, DATABASE_UPDATED, self._on_database_updated)

    def build_ui(self):
        # 1px border container
        self.bar_frame = tk.Frame(
            self,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#d1d1d1",
            padx=sc(10),
            pady=sc(4)
        )
        self.bar_frame.pack(fill="x", expand=True, padx=sc(2), pady=(sc(1), sc(2)))

        # Left: Specimen Identifier & Nomenclature
        left_box = tk.Frame(self.bar_frame, bg="#ffffff")
        left_box.pack(side="left", fill="y", anchor="center")

        self.id_badge = tk.Label(
            left_box,
            text="ID: --",
            font=("JetBrains Mono", sc(10), "bold"),
            bg="#e9ece5",
            fg="#2c302e",
            padx=sc(8),
            pady=sc(2),
            relief="solid",
            bd=1,
            highlightbackground="#c4c7c7",
            highlightthickness=1
        )
        self.id_badge.pack(side="left", padx=(0, sc(8)))

        self.name_label = tk.Label(
            left_box,
            text="No Specimen Selected",
            font=("Lora", sc(13), "bold italic"),
            bg="#ffffff",
            fg="#2c302e"
        )
        self.name_label.pack(side="left", padx=(0, sc(8)))

        self.status_badge = tk.Label(
            left_box,
            text="PENDING",
            font=("JetBrains Mono", sc(8), "bold"),
            bg="#fef3c7",
            fg="#92400e",
            padx=sc(6),
            pady=sc(2)
        )
        self.status_badge.pack(side="left", padx=(0, sc(8)))

        # Right: Contextual Action Buttons
        right_box = tk.Frame(self.bar_frame, bg="#ffffff")
        right_box.pack(side="right", fill="y", anchor="center")

        # 1. GBIF Validation Button
        self.gbif_btn = tk.Button(
            right_box,
            text="🧬 Validate GBIF",
            font=("Segoe UI", sc(9), "bold"),
            bg="#f2f5f1",
            fg="#2c302e",
            activebackground="#e9ece5",
            activeforeground="#1b1b1b",
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
            right_box,
            text="📖 Check Books",
            font=("Segoe UI", sc(9), "bold"),
            bg="#f2f5f1",
            fg="#2c302e",
            activebackground="#e9ece5",
            activeforeground="#1b1b1b",
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
            right_box,
            text="📱 Send to Phone",
            font=("Segoe UI", sc(9)),
            bg="#ffffff",
            fg="#757d77",
            activebackground="#f2f5f1",
            activeforeground="#2c302e",
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
        """Update specimen display and contextual button states."""
        if not self.winfo_exists():
            return

        if oid is None:
            oid = getattr(self.app, "current_object_id", None) if self.app else None

        self.current_oid = oid
        if not oid:
            self.id_badge.config(text="ID: --")
            self.name_label.config(text="No Specimen Selected")
            self.status_badge.config(text="NO DATA", bg="#e2e2e2", fg="#757d77")
            self.gbif_btn.config(state="disabled")
            self.hist_btn.config(state="disabled")
            self.mobile_push_btn.config(state="disabled")
            return

        self.gbif_btn.config(state="normal")
        self.hist_btn.config(state="normal")
        self.mobile_push_btn.config(state="normal")

        self.id_badge.config(text=f"ID: {oid}")

        # Fetch active registration data
        genus = ""
        species = ""
        author = ""
        is_reviewed = False
        prob_count = 0

        if self.app:
            # Registration metadata
            if getattr(self.app, "df_reg", None) is not None:
                str_oid = str(oid)
                int_oid = int(oid) if str_oid.isdigit() else None
                row = None
                if str_oid in self.app.df_reg.index:
                    row = self.app.df_reg.loc[str_oid]
                elif int_oid is not None and int_oid in self.app.df_reg.index:
                    row = self.app.df_reg.loc[int_oid]

                if row is not None:
                    try:
                        genus = str(row.get("Genus", "")).strip()
                        if genus in ("nan", "None", "<NA>"): genus = ""
                        species = str(row.get("Species", "")).strip()
                        if species in ("nan", "None", "<NA>"): species = ""
                        author = str(row.get("Author", "")).strip()
                        if author in ("nan", "None", "<NA>"): author = ""
                    except Exception:
                        pass

            # Observation metadata
            if getattr(self.app, "df_obs", None) is not None:
                str_oid = str(oid)
                int_oid = int(oid) if str_oid.isdigit() else None
                obs_row = None
                if str_oid in self.app.df_obs.index:
                    obs_row = self.app.df_obs.loc[str_oid]
                elif int_oid is not None and int_oid in self.app.df_obs.index:
                    obs_row = self.app.df_obs.loc[int_oid]

                if obs_row is not None:
                    try:
                        rev_val = obs_row.get("Reviewed", False)
                        is_reviewed = bool(rev_val) and str(rev_val).lower() not in ("false", "0", "nan", "none")
                        
                        # Count problem flags
                        if self.app.config and "ui_sections" in self.app.config and "problems" in self.app.config["ui_sections"]:
                            for p in self.app.config["ui_sections"]["problems"]:
                                p_name = p.get("name")
                                if p_name and p_name in obs_row:
                                    val = obs_row[p_name]
                                    if bool(val) and str(val).lower() not in ("false", "0", "nan", "none"):
                                        prob_count += 1
                    except Exception:
                        pass

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

        # Status badge formatting
        if is_reviewed and prob_count == 0:
            self.status_badge.config(text="✓ REVIEWED", bg="#dcfce7", fg="#15803d")
        elif prob_count > 0:
            self.status_badge.config(text=f"⚠️ {prob_count} PROBLEM{'S' if prob_count > 1 else ''}", bg="#fee2e2", fg="#b91c1c")
        else:
            self.status_badge.config(text="⏳ UNREVIEWED", bg="#fef3c7", fg="#92400e")

        # Check historical suggestions availability
        if self.main_ui and hasattr(self.main_ui, "_history_cache"):
            sugg = self.main_ui._history_cache.get(str(oid)) or self.main_ui._history_cache.get(int(oid) if str(oid).isdigit() else None)
            if sugg:
                self.hist_btn.config(text=f"📖 Check Books ({len(sugg)})", bg="#e0f2fe", fg="#0369a1")
            else:
                self.hist_btn.config(text="📖 Check Books", bg="#f2f5f1", fg="#2c302e")

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
