"""ui/command_palette.py - Universal Command Palette & Quick Switcher for Arbor.

Provides an instant, keyboard-driven omni-bar (Ctrl+K) for:
- Triggering application commands and curatorial tools
- Direct specimen jumping by ObjectID or botanical taxon
- Fuzzy matching across all registered actions and datasets
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Any

from config import sc
import utils


class CommandPalette(tk.Toplevel):
    """Floating Stitch-styled command palette and quick switcher."""

    def __init__(self, main_ui: Any):
        super().__init__(main_ui.root)
        self.ui = main_ui
        self.is_dark = getattr(main_ui, "dark_mode_active", False)

        # Style tokens (Stitch palette)
        self.bg_card = "#181c19" if self.is_dark else "#fbfaf8"
        self.bg_input = "#111412" if self.is_dark else "#ffffff"
        self.bg_hover = "#242a26" if self.is_dark else "#f0f4f1"
        self.bg_selected = "#2e3a31" if self.is_dark else "#e4ede6"
        self.fg_text = "#e8ebe9" if self.is_dark else "#2c302e"
        self.fg_muted = "#8a948d" if self.is_dark else "#757d77"
        self.fg_category = "#4caf50" if self.is_dark else "#3a7d44"
        self.fg_shortcut = "#a6adc8" if self.is_dark else "#535d56"
        self.border_col = "#2c302e" if self.is_dark else "#c4c7c7"

        self.title("Command Palette")
        self.configure(bg=self.bg_card)
        self.transient(main_ui.root)

        # Layout sizing
        width = sc(680)
        height = sc(480)
        utils.center_and_fit_toplevel(self, width, height)

        self._selected_index = 0
        self._current_items: list[dict] = []
        self._commands_registry = self._build_commands_registry()

        self._build_ui()
        self._populate_results()

        # Keyboard and focus bindings
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Down>", self._on_arrow_down)
        self.bind("<Up>", self._on_arrow_up)
        self.bind("<Return>", self._on_enter)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Focus entry immediately
        self.entry.focus_set()

    def _build_commands_registry(self) -> list[dict]:
        """Catalog all executable curatorial commands and tools."""
        ui = self.ui
        cmds = [
            # Curatorial verification
            {
                "type": "command",
                "category": "VERIFICATION",
                "label": "Mark Current Specimen as Reviewed",
                "shortcut": "Ctrl+Enter",
                "icon": "✓",
                "action": lambda: ui.mark_current_as_reviewed() if hasattr(ui, "mark_current_as_reviewed") else None,
            },
            {
                "type": "command",
                "category": "VERIFICATION",
                "label": "Toggle Problem Checkbox",
                "shortcut": "Space",
                "icon": "⚠️",
                "action": lambda: ui._toggle_problem_checkbox(None) if hasattr(ui, "_toggle_problem_checkbox") else None,
            },
            {
                "type": "command",
                "category": "VERIFICATION",
                "label": "Open Historical & GBIF Conflict Resolver",
                "shortcut": "Ctrl+H",
                "icon": "📜",
                "action": lambda: ui.open_history_shortcut(None) if hasattr(ui, "open_history_shortcut") else None,
            },
            {
                "type": "command",
                "category": "VERIFICATION",
                "label": "Open GBIF Backbone Taxonomy Review",
                "shortcut": "Tools",
                "icon": "🌿",
                "action": lambda: (ui.open_gbif_dialog() if hasattr(ui, "open_gbif_dialog") else (ui.batch_gbif_update_action() if hasattr(ui, "batch_gbif_update_action") else None)),
            },
            # Navigation
            {
                "type": "command",
                "category": "NAVIGATION",
                "label": "Previous Specimen",
                "shortcut": "Left",
                "icon": "←",
                "action": lambda: ui._safe_nav_left(None) if hasattr(ui, "_safe_nav_left") else None,
            },
            {
                "type": "command",
                "category": "NAVIGATION",
                "label": "Next Specimen",
                "shortcut": "Right",
                "icon": "→",
                "action": lambda: ui._safe_nav_right(None) if hasattr(ui, "_safe_nav_right") else None,
            },
            {
                "type": "command",
                "category": "NAVIGATION",
                "label": "Navigate Back",
                "shortcut": "Alt+Left",
                "icon": "↩",
                "action": lambda: ui.go_back() if hasattr(ui, "go_back") else None,
            },
            {
                "type": "command",
                "category": "NAVIGATION",
                "label": "Navigate Forward",
                "shortcut": "Alt+Right",
                "icon": "↪",
                "action": lambda: ui.go_forward() if hasattr(ui, "go_forward") else None,
            },
            # Object operations
            {
                "type": "command",
                "category": "SPECIMEN",
                "label": "New Specimen Dialog",
                "shortcut": "Ctrl+N",
                "icon": "＋",
                "action": lambda: ui.add_new_object() if hasattr(ui, "add_new_object") else None,
            },
            {
                "type": "command",
                "category": "SPECIMEN",
                "label": "Quick Create Next Accession",
                "shortcut": "Ctrl+Shift+N",
                "icon": "⚡",
                "action": lambda: ui._shortcut_quick_new_object(None) if hasattr(ui, "_shortcut_quick_new_object") else None,
            },
            {
                "type": "command",
                "category": "SPECIMEN",
                "label": "Duplicate Current Specimen",
                "shortcut": "Ctrl+Shift+D",
                "icon": "📋",
                "action": lambda: ui._shortcut_duplicate_object(None) if hasattr(ui, "_shortcut_duplicate_object") else None,
            },
            {
                "type": "command",
                "category": "SPECIMEN",
                "label": "Delete Current Specimen",
                "shortcut": "Ctrl+Delete",
                "icon": "🗑",
                "action": lambda: ui._shortcut_delete_object(None) if hasattr(ui, "_shortcut_delete_object") else None,
            },
            # Tools & Dialogs
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Database Statistics Dashboard",
                "shortcut": "Ctrl+J",
                "icon": "📊",
                "action": lambda: ui.show_statistics() if hasattr(ui, "show_statistics") else None,
            },
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Mobile Companion Server & QR Code",
                "shortcut": "Tools",
                "icon": "📱",
                "action": lambda: ui.open_mobile_dialog() if hasattr(ui, "open_mobile_dialog") else None,
            },
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Advanced Search & Query Builder",
                "shortcut": "Ctrl+Shift+F",
                "icon": "🔍",
                "action": lambda: ui.open_advanced_search() if hasattr(ui, "open_advanced_search") else None,
            },
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Location & Problem Filter Menu",
                "shortcut": "Ctrl+G",
                "icon": "▼",
                "action": lambda: ui.open_filter_menu() if hasattr(ui, "open_filter_menu") else None,
            },
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Bulk Edit Selected Objects",
                "shortcut": "Tools",
                "icon": "📝",
                "action": lambda: (ui.open_bulk_edit() if hasattr(ui, "open_bulk_edit") else (ui.open_bulk_edit_window() if hasattr(ui, "open_bulk_edit_window") else None)),
            },
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Keyboard Shortcuts HUD",
                "shortcut": "F1",
                "icon": "⌨",
                "action": lambda: ui.show_shortcuts() if hasattr(ui, "show_shortcuts") else None,
            },
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Application Settings",
                "shortcut": "Tools",
                "icon": "⚙",
                "action": lambda: (ui.open_unified_settings() if hasattr(ui, "open_unified_settings") else (ui._open_unified() if hasattr(ui, "_open_unified") else None)),
            },
            # Image tools
            {
                "type": "command",
                "category": "IMAGE",
                "label": "Rotate Specimen Image 90° Clockwise",
                "shortcut": "Alt+R",
                "icon": "↻",
                "action": lambda: ui.rotate_image() if hasattr(ui, "rotate_image") else None,
            },
            {
                "type": "command",
                "category": "IMAGE",
                "label": "Zoom Image In",
                "shortcut": "Ctrl++",
                "icon": "🔍+",
                "action": lambda: ui.zoom_image_in() if hasattr(ui, "zoom_image_in") else None,
            },
            {
                "type": "command",
                "category": "IMAGE",
                "label": "Zoom Image Out",
                "shortcut": "Ctrl+-",
                "icon": "🔍-",
                "action": lambda: ui.zoom_image_out() if hasattr(ui, "zoom_image_out") else None,
            },
            {
                "type": "command",
                "category": "IMAGE",
                "label": "Reset Image Viewport",
                "shortcut": "Ctrl+0",
                "icon": "↺",
                "action": lambda: ui.reset_image_view() if hasattr(ui, "reset_image_view") else None,
            },
            # Presets & Layout
            {
                "type": "command",
                "category": "PRESETS",
                "label": "Apply Default Data Preset",
                "shortcut": "Ctrl+Alt+K",
                "icon": "⚡",
                "action": lambda: ui._apply_default_data_preset_shortcut(None) if hasattr(ui, "_apply_default_data_preset_shortcut") else None,
            },
            {
                "type": "command",
                "category": "PRESETS",
                "label": "Save Current Form as Data Preset",
                "shortcut": "Presets",
                "icon": "💾",
                "action": lambda: ui.save_data_preset_dialog() if hasattr(ui, "save_data_preset_dialog") else None,
            },
            # Panel Visibility Toggles (F6 / F7 / F8)
            {
                "type": "command",
                "category": "LAYOUT",
                "label": "Toggle Left Specimen Directory Panel",
                "shortcut": "F6",
                "icon": "📁",
                "action": lambda: ui.toggle_list_panel_shortcut(None) if hasattr(ui, "toggle_list_panel_shortcut") else None,
            },
            {
                "type": "command",
                "category": "LAYOUT",
                "label": "Toggle Right Registration & Taxonomy Panel",
                "shortcut": "F7",
                "icon": "📋",
                "action": lambda: ui.toggle_reg_panel_shortcut(None) if hasattr(ui, "toggle_reg_panel_shortcut") else None,
            },
            {
                "type": "command",
                "category": "LAYOUT",
                "label": "Toggle Middle Specimen Image Viewport",
                "shortcut": "F8",
                "icon": "🖼️",
                "action": lambda: ui.toggle_images_panel_shortcut(None) if hasattr(ui, "toggle_images_panel_shortcut") else None,
            },
            # Directory Card Customization & View Presets
            {
                "type": "command",
                "category": "VIEW",
                "label": "Card Layout: Standard (78px, 3 Rows)",
                "shortcut": "View",
                "icon": "🗂️",
                "action": lambda: ui.apply_card_persona("standard") if hasattr(ui, "apply_card_persona") else (ui.apply_card_preset("standard") if hasattr(ui, "apply_card_preset") else None),
            },
            {
                "type": "command",
                "category": "VIEW",
                "label": "Card Layout: Compact (64px, 2 Rows)",
                "shortcut": "View",
                "icon": "⚡",
                "action": lambda: ui.apply_card_persona("compact") if hasattr(ui, "apply_card_persona") else (ui.apply_card_preset("compact") if hasattr(ui, "apply_card_preset") else None),
            },
            {
                "type": "command",
                "category": "VIEW",
                "label": "Card Layout: Full Details (92px, Author + Location)",
                "shortcut": "View",
                "icon": "🌿",
                "action": lambda: ui.apply_card_persona("full_detail") if hasattr(ui, "apply_card_persona") else (ui.apply_card_preset("full_detail") if hasattr(ui, "apply_card_preset") else None),
            },
            {
                "type": "command",
                "category": "VIEW",
                "label": "Card Layout: Minimalist (Clean, No Badges/Location)",
                "shortcut": "View",
                "icon": "📖",
                "action": lambda: ui.apply_card_persona("minimalist") if hasattr(ui, "apply_card_persona") else (ui.apply_card_preset("minimalist") if hasattr(ui, "apply_card_preset") else None),
            },
            {
                "type": "command",
                "category": "VIEW",
                "label": "Configure Directory Cards & View Settings...",
                "shortcut": "View",
                "icon": "⚙️",
                "action": lambda: ui.open_unified_settings("appearance") if hasattr(ui, "open_unified_settings") else None,
            },
            {
                "type": "command",
                "category": "VIEW",
                "label": "Toggle Directory Card Location Row (Row 3)",
                "shortcut": "View",
                "icon": "📍",
                "action": lambda: ui.toggle_card_location_row() if hasattr(ui, "toggle_card_location_row") else None,
            },
            {
                "type": "command",
                "category": "VIEW",
                "label": "Toggle Directory Card Status Pill Badges",
                "shortcut": "View",
                "icon": "🏷️",
                "action": lambda: ui.toggle_card_status_badges() if hasattr(ui, "toggle_card_status_badges") else None,
            },
            {
                "type": "command",
                "category": "VIEW",
                "label": "Restore Directory Card Settings to Default",
                "shortcut": "View",
                "icon": "↺",
                "action": lambda: ui.restore_default_card_settings() if hasattr(ui, "restore_default_card_settings") else None,
            },
            # File, Database & Export Operations
            {
                "type": "command",
                "category": "FILE",
                "label": "Export Filtered Dataset (Excel / CSV)...",
                "shortcut": "Export",
                "icon": "📊",
                "action": lambda: ui.export_filtered_list() if hasattr(ui, "export_filtered_list") else None,
            },
            {
                "type": "command",
                "category": "FILE",
                "label": "Open Excel Database...",
                "shortcut": "Ctrl+O",
                "icon": "📂",
                "action": lambda: ui.open_excel() if hasattr(ui, "open_excel") else None,
            },
            {
                "type": "command",
                "category": "FILE",
                "label": "New Database Setup Wizard...",
                "shortcut": "Wizard",
                "icon": "✨",
                "action": lambda: ui.create_new_database() if hasattr(ui, "create_new_database") else None,
            },
            {
                "type": "command",
                "category": "FILE",
                "label": "Save Session As...",
                "shortcut": "File",
                "icon": "💾",
                "action": lambda: ui.save_as() if hasattr(ui, "save_as") else None,
            },
            {
                "type": "command",
                "category": "FILE",
                "label": "Restore Earlier Autosave Backup...",
                "shortcut": "File",
                "icon": "⏪",
                "action": lambda: ui.open_autosave_manager() if hasattr(ui, "open_autosave_manager") else None,
            },
            # Problem Navigation Jumps
            {
                "type": "command",
                "category": "NAVIGATION",
                "label": "Jump to Next Problem",
                "shortcut": "Nav",
                "icon": "⚠",
                "action": lambda: ui.goto_next_problem() if hasattr(ui, "goto_next_problem") else None,
            },
            {
                "type": "command",
                "category": "NAVIGATION",
                "label": "Jump to Next Object with Historical Suggestions",
                "shortcut": "Nav",
                "icon": "📜",
                "action": lambda: ui.goto_next_problem_with_history() if hasattr(ui, "goto_next_problem_with_history") else None,
            },
            # Tools & Batch Operations
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Botanical Whitelist (Ignored Words)",
                "shortcut": "Tools",
                "icon": "🌿",
                "action": lambda: ui.open_ignored_words_editor() if hasattr(ui, "open_ignored_words_editor") else None,
            },
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Open System Log Viewer",
                "shortcut": "Tools",
                "icon": "📑",
                "action": lambda: ui.open_log_viewer_window() if hasattr(ui, "open_log_viewer_window") else None,
            },
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Batch Mark Filtered as Reviewed",
                "shortcut": "Batch",
                "icon": "✓",
                "action": lambda: ui.batch_set_reviewed_true() if hasattr(ui, "batch_set_reviewed_true") else None,
            },
            {
                "type": "command",
                "category": "TOOLS",
                "label": "Batch Unmark Filtered as Reviewed",
                "shortcut": "Batch",
                "icon": "⚪",
                "action": lambda: ui.batch_set_reviewed_false() if hasattr(ui, "batch_set_reviewed_false") else None,
            },
            {
                "type": "command",
                "category": "SESSION",
                "label": "Save Session Manually",
                "shortcut": "Ctrl+S",
                "icon": "💾",
                "action": lambda: ui.save_session("SAVE") if hasattr(ui, "save_session") else None,
            },
            # Help & Interactive Tutorials
            {
                "type": "command",
                "category": "HELP",
                "label": "Interactive Tutorial: Specimen Review & Verification",
                "shortcut": "Help",
                "icon": "🎓",
                "action": lambda: ui.start_tutorial_flow("review") if hasattr(ui, "start_tutorial_flow") else None,
            },
            {
                "type": "command",
                "category": "HELP",
                "label": "Interactive Tutorial: Historical & GBIF Conflict Resolution",
                "shortcut": "Help",
                "icon": "🎓",
                "action": lambda: ui.start_tutorial_flow("discrepancy") if hasattr(ui, "start_tutorial_flow") else None,
            },
            {
                "type": "command",
                "category": "HELP",
                "label": "Interactive Tutorial: Database Creation & New Accessions",
                "shortcut": "Help",
                "icon": "🎓",
                "action": lambda: ui.start_tutorial_flow("database") if hasattr(ui, "start_tutorial_flow") else None,
            },
            {
                "type": "command",
                "category": "HELP",
                "label": "Open Help Center",
                "shortcut": "Help",
                "icon": "🏛️",
                "action": lambda: ui.open_help_window() if hasattr(ui, "open_help_window") else None,
            },
            {
                "type": "command",
                "category": "HELP",
                "label": "Open User Guide (Documentation)",
                "shortcut": "Help",
                "icon": "📖",
                "action": lambda: ui.show_main_help() if hasattr(ui, "show_main_help") else None,
            },
            {
                "type": "command",
                "category": "HELP",
                "label": "Check for Application Updates (GitHub)",
                "shortcut": "Help",
                "icon": "🔄",
                "action": lambda: ui.check_for_updates_action() if hasattr(ui, "check_for_updates_action") else None,
            },
        ]
        return cmds

    def _build_ui(self):
        pad_x = sc(16)
        pad_y = sc(12)

        # Header Search Frame
        header = tk.Frame(self, bg=self.bg_card, padx=pad_x, pady=pad_y)
        header.pack(fill="x")

        search_container = tk.Frame(
            header,
            bg=self.bg_input,
            bd=1,
            relief="solid",
            highlightbackground=self.border_col,
            highlightthickness=1,
            padx=sc(10),
            pady=sc(8)
        )
        search_container.pack(fill="x")

        tk.Label(
            search_container,
            text="🔍",
            font=("Segoe UI", sc(11)),
            fg=self.fg_muted,
            bg=self.bg_input
        ).pack(side="left", padx=(0, sc(8)))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_search_changed())

        self.entry = tk.Entry(
            search_container,
            textvariable=self.search_var,
            font=("Segoe UI", sc(11)),
            fg=self.fg_text,
            bg=self.bg_input,
            bd=0,
            relief="flat",
            insertbackground=self.fg_text
        )
        self.entry.pack(side="left", fill="x", expand=True)

        # Results container
        results_frame = tk.Frame(self, bg=self.bg_card, padx=pad_x)
        results_frame.pack(fill="both", expand=True, pady=(0, pad_y))

        self.canvas = tk.Canvas(results_frame, bg=self.bg_card, bd=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.canvas.yview)
        self.items_frame = tk.Frame(self.canvas, bg=self.bg_card)

        self.canvas.create_window((0, 0), window=self.items_frame, anchor="nw", tags="inner_frame")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.items_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig("inner_frame", width=e.width)
        )

        from ui.scroll_helper import bind_mousewheel
        bind_mousewheel(self.canvas, self.items_frame)

        # Footer hint bar
        footer = tk.Frame(self, bg=self.bg_card, padx=pad_x, pady=sc(6))
        footer.pack(fill="x", side="bottom")
        tk.Label(
            footer,
            text="↑ / ↓ Navigate  •  Enter Select  •  Esc Close",
            font=("Segoe UI", sc(8.5)),
            fg=self.fg_muted,
            bg=self.bg_card
        ).pack(side="left")

    def _on_search_changed(self):
        query = self.search_var.get().strip()
        self._populate_results(query)

    def _populate_results(self, query: str = ""):
        # Clear existing items
        for widget in self.items_frame.winfo_children():
            widget.destroy()

        self._current_items.clear()
        self._selected_index = 0

        q = query.lower()

        # 1. Matching commands
        matching_commands = []
        for cmd in self._commands_registry:
            if not q:
                matching_commands.append((cmd, 100.0))
            else:
                score = utils.fuzzy_score(q, f"{cmd['label']} {cmd['category']}")
                if score >= 55.0 or q in cmd['label'].lower():
                    matching_commands.append((cmd, score))

        matching_commands.sort(key=lambda x: x[1], reverse=True)

        # 2. Matching specimens (if database is loaded and query is typed)
        matching_specimens = []
        app_state = getattr(self.ui, "app", getattr(self.ui, "app_state", None))
        if app_state and getattr(app_state, "df_reg", None) is not None and q:
            df_reg = app_state.df_reg
            df_obs = getattr(app_state, "df_obs", None)

            # Check direct ID matches or genus/species matches
            for oid in df_reg.index[:1000]:  # Cap scan for high performance
                oid_str = str(oid)
                genus = str(df_reg.loc[oid, "Genus"]) if "Genus" in df_reg.columns and not pd_isna(df_reg.loc[oid, "Genus"]) else ""
                species = str(df_reg.loc[oid, "Species"]) if "Species" in df_reg.columns and not pd_isna(df_reg.loc[oid, "Species"]) else ""
                taxon = f"{genus} {species}".strip()

                is_match = False
                spec_score = 0.0

                if q == oid_str.lower() or oid_str.lower().startswith(q):
                    is_match = True
                    spec_score = 100.0
                elif q in taxon.lower():
                    is_match = True
                    spec_score = 90.0
                elif len(q) >= 3 and taxon:
                    spec_score = utils.fuzzy_score(q, taxon)
                    if spec_score >= 65.0:
                        is_match = True

                if is_match:
                    # Check reviewed / problem status
                    is_reviewed = False
                    has_problem = False
                    if df_obs is not None and oid in df_obs.index:
                        from repository import REVIEWED_COLUMN
                        if REVIEWED_COLUMN in df_obs.columns:
                            is_reviewed = bool(df_obs.loc[oid, REVIEWED_COLUMN])

                    status_icon = "🟢" if is_reviewed else "⚪"
                    matching_specimens.append({
                        "type": "specimen",
                        "oid": oid,
                        "label": f"#{oid_str} — {taxon or 'Unidentified specimen'}",
                        "shortcut": "Reviewed" if is_reviewed else "Jump",
                        "icon": status_icon,
                        "score": spec_score,
                    })
                    if len(matching_specimens) >= 15:
                        break

            matching_specimens.sort(key=lambda x: x["score"], reverse=True)

        # Assemble final item list
        combined = []
        if matching_specimens:
            combined.extend(matching_specimens[:10])

        top_commands = [c[0] for c in matching_commands[:15]]
        combined.extend(top_commands)

        self._current_items = combined

        # Render list items
        if not self._current_items:
            empty_lbl = tk.Label(
                self.items_frame,
                text="No commands or specimens matched your search.",
                font=("Segoe UI", sc(10), "italic"),
                fg=self.fg_muted,
                bg=self.bg_card,
                pady=sc(20)
            )
            empty_lbl.pack()
            return

        current_category = None
        for idx, item in enumerate(self._current_items):
            cat = "SPECIMENS" if item.get("type") == "specimen" else item.get("category", "COMMANDS")
            if cat != current_category:
                current_category = cat
                cat_hdr = tk.Label(
                    self.items_frame,
                    text=current_category,
                    font=("Segoe UI", sc(8), "bold"),
                    fg=self.fg_category,
                    bg=self.bg_card,
                    padx=sc(8),
                    pady=sc(3),
                    anchor="w"
                )
                cat_hdr.pack(fill="x", pady=(sc(6), sc(1)))

            row_frame = tk.Frame(
                self.items_frame,
                bg=self.bg_selected if idx == self._selected_index else self.bg_card,
                padx=sc(10),
                pady=sc(6),
                cursor="hand2"
            )
            row_frame.pack(fill="x", pady=sc(1))
            row_frame.bind("<Button-1>", lambda e, i=idx: self._select_and_execute(i))

            # Icon
            icon_lbl = tk.Label(
                row_frame,
                text=item.get("icon", "•"),
                font=("Segoe UI", sc(10)),
                fg=self.fg_text,
                bg=row_frame["bg"]
            )
            icon_lbl.pack(side="left", padx=(0, sc(8)))
            icon_lbl.bind("<Button-1>", lambda e, i=idx: self._select_and_execute(i))

            # Label
            label_lbl = tk.Label(
                row_frame,
                text=item.get("label", ""),
                font=("Segoe UI", sc(9.5)),
                fg=self.fg_text,
                bg=row_frame["bg"]
            )
            label_lbl.pack(side="left")
            label_lbl.bind("<Button-1>", lambda e, i=idx: self._select_and_execute(i))

            # Shortcut / Meta badge
            shortcut = item.get("shortcut", "")
            if shortcut:
                sc_lbl = tk.Label(
                    row_frame,
                    text=shortcut,
                    font=("JetBrains Mono", sc(8)),
                    fg=self.fg_shortcut,
                    bg=row_frame["bg"]
                )
                sc_lbl.pack(side="right")
                sc_lbl.bind("<Button-1>", lambda e, i=idx: self._select_and_execute(i))

    def _update_row_selection(self):
        # Update row highlight visuals
        row_widgets = [w for w in self.items_frame.winfo_children() if isinstance(w, tk.Frame)]
        for i, row in enumerate(row_widgets):
            bg = self.bg_selected if i == self._selected_index else self.bg_card
            row.configure(bg=bg)
            for child in row.winfo_children():
                child.configure(bg=bg)

    def _on_arrow_down(self, event=None):
        if not self._current_items:
            return "break"
        self._selected_index = (self._selected_index + 1) % len(self._current_items)
        self._update_row_selection()
        return "break"

    def _on_arrow_up(self, event=None):
        if not self._current_items:
            return "break"
        self._selected_index = (self._selected_index - 1) % len(self._current_items)
        self._update_row_selection()
        return "break"

    def _on_enter(self, event=None):
        if 0 <= self._selected_index < len(self._current_items):
            self._select_and_execute(self._selected_index)
        return "break"

    def _select_and_execute(self, index: int):
        if not (0 <= index < len(self._current_items)):
            return
        item = self._current_items[index]
        self.destroy()

        if item.get("type") == "specimen":
            oid = item.get("oid")
            if oid is not None:
                if hasattr(self.ui, "select_object_id"):
                    self.ui.select_object_id(oid)
                elif hasattr(self.ui, "load_object"):
                    self.ui.load_object(oid)
        elif item.get("type") == "command":
            action = item.get("action")
            if callable(action):
                self.ui.root.after(50, action)


def pd_isna(val):
    """Safe NA check without importing full pandas in header."""
    return val is None or val != val or str(val).lower() in ("nan", "none", "<na>")
