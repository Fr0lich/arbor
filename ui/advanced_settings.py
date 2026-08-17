import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import config
from config import sc
from ui.widgets import ToggleSwitch
import utils

# Central registry of advanced features.
# Add new items here to dynamically expose them in the UI.
ADVANCED_SETTINGS_SCHEMA = [
    # SYSTEM & BACKUPS
    {
        "id": "enable_excel_import_backup",
        "type": "toggle",
        "tab": "System & Backups",
        "group": "Backup & Intervals",
        "label": "Enable Backup on Excel Import",
        "description": "Creates a timestamped backup copy inside a 'backups' folder whenever importing an Excel file.",
        "default": True,
        "refresh_type": "none"
    },
    {
        "id": "autosave_archive_limit",
        "type": "choice",
        "tab": "System & Backups",
        "group": "Backup & Intervals",
        "label": "Autosave Archive Warning Limit",
        "description": "Number of archived autosaves kept before prompting the user to clean them up.",
        "choices": ["5", "10", "20", "50"],
        "default": "10",
        "refresh_type": "none"
    },
    {
        "id": "log_verbosity",
        "type": "choice",
        "tab": "System & Backups",
        "group": "Logging",
        "label": "System Logging Verbosity",
        "description": "Set level of diagnostic logging stored in the session logs folder.",
        "choices": ["ERROR", "WARNING", "INFO", "DEBUG"],
        "default": "ERROR",
        "refresh_type": "none"
    },
    
    # GRAPHICS & IMAGES
    {
        "id": "image_resampling_algorithm",
        "type": "choice",
        "tab": "Graphics & Images",
        "group": "Image Rendering Engine",
        "label": "Image Resampling Algorithm",
        "description": "Choose filter quality for image zoom. Lanczos is high-quality but slower.",
        "choices": ["LANCZOS (High Quality)", "BILINEAR (Balanced)", "NEAREST (Fast draft / Pixelated)"],
        "default": "LANCZOS (High Quality)",
        "refresh_type": "immediate",
        "callback": "refresh_image_rendering"
    },
    {
        "id": "image_url_pattern_override",
        "type": "text",
        "tab": "Graphics & Images",
        "group": "Online Image Fetcher",
        "label": "Image URL Pattern Override",
        "description": "Override database image pattern. Leave empty to use database default.",
        "default": "",
        "refresh_type": "none"
    },

    # UX & THEMES
    {
        "id": "enable_bulk_editor",
        "type": "toggle",
        "tab": "UX & Themes",
        "group": "Unfinished Features",
        "label": "Enable Bulk Editor",
        "description": "Allows mass updates to selected rows. Requires application restart.",
        "default": False,
        "refresh_type": "restart"
    },
    {
        "id": "enable_focus_mode_toggle",
        "type": "toggle",
        "tab": "UX & Themes",
        "group": "Unfinished Features",
        "label": "Show Focus Mode Toggle",
        "description": "Shows the Focus Mode switch in the top-right header of the main window.",
        "default": False,
        "refresh_type": "immediate",
        "callback": "update_focus_toggle_visibility"
    },
    {
        "id": "enable_problem_highlights",
        "type": "toggle",
        "tab": "UX & Themes",
        "group": "Problem Highlights",
        "label": "Enable Problem Highlights",
        "description": "If disabled, problem fields will not highlight their background colors.",
        "default": True,
        "refresh_type": "immediate",
        "callback": "refresh_styles_and_highlights"
    },
    {
        "id": "problem_highlight_color",
        "type": "choice",
        "tab": "UX & Themes",
        "group": "Problem Highlights",
        "label": "Highlight Color Style",
        "description": "Choose the color to highlight problematic fields with.",
        "choices": ["Default (Red)", "Yellow", "Orange", "Blue"],
        "default": "Default (Red)",
        "refresh_type": "immediate",
        "callback": "refresh_styles_and_highlights"
    },
    {
        "id": "action_dark_mode",
        "type": "button",
        "tab": "UX & Themes",
        "group": "Interface",
        "label": "Toggle Dark Mode",
        "description": "Switch the interface theme between light and dark mode.",
        "button_text": "Toggle Theme",
        "callback": "toggle_dark_mode"
    },
    {
        "id": "action_dashboard",
        "type": "button",
        "tab": "UX & Themes",
        "group": "Interface",
        "label": "Session Dashboard",
        "description": "Open the session statistics and logs dashboard.",
        "button_text": "Open Dashboard",
        "callback": "open_session_dashboard_window"
    },
    {
        "id": "action_statistics",
        "type": "button",
        "tab": "UX & Themes",
        "group": "Interface",
        "label": "Database Statistics",
        "description": "Examine overall counts and checklists of registered records.",
        "button_text": "View Statistics",
        "callback": "show_statistics"
    },
    {
        "id": "action_reg_tabs",
        "type": "button",
        "tab": "Tools & Editors",
        "group": "Layout & Tabs",
        "label": "Configure Registration Tabs",
        "description": "Configure the metadata accordions and panels layout.",
        "button_text": "Configure Tabs",
        "callback": "open_tab_config_editor"
    },
    {
        "id": "action_field_groups",
        "type": "button",
        "tab": "Tools & Editors",
        "group": "Layout & Tabs",
        "label": "Edit Field Groups",
        "description": "Add, remove, or customize grouping of text input fields.",
        "button_text": "Edit Groups",
        "callback": "open_group_editor"
    },
    {
        "id": "action_ignored_words",
        "type": "button",
        "tab": "Tools & Editors",
        "group": "Presets & Dictionaries",
        "label": "Configure Ignored Words",
        "description": "Add or remove terms ignored by spelling checkbooks.",
        "button_text": "Configure Words",
        "callback": "open_ignored_words_editor"
    },
    {
        "id": "action_save_preset",
        "type": "button",
        "tab": "Tools & Editors",
        "group": "Presets & Dictionaries",
        "label": "Save Data Preset",
        "description": "Save current input fields configuration as a profile preset.",
        "button_text": "Save Preset...",
        "callback": "save_data_preset_dialog"
    },
    {
        "id": "action_load_preset",
        "type": "button",
        "tab": "Tools & Editors",
        "group": "Presets & Dictionaries",
        "label": "Load Data Preset",
        "description": "Apply a previously saved input fields profile configuration.",
        "button_text": "Load Preset...",
        "callback": "show_load_data_preset_popup"
    },
    {
        "id": "action_focus_settings",
        "type": "button",
        "tab": "Tools & Editors",
        "group": "Layout & Tabs",
        "label": "Focus Settings",
        "description": "Configure field visibility and behaviors when focusing problems.",
        "button_text": "Focus Settings...",
        "callback": "open_focus_settings"
    },
    {
        "id": "action_layout_settings",
        "type": "button",
        "tab": "Tools & Editors",
        "group": "Layout & Tabs",
        "label": "Layout Settings",
        "description": "Customize panels visibility, default behaviors, and toolbar buttons.",
        "button_text": "Layout Settings...",
        "callback": "open_layout_settings"
    },
    {
        "id": "action_mark_reviewed",
        "type": "button",
        "tab": "Tools & Editors",
        "group": "Presets & Dictionaries",
        "label": "Mark Filtered as Reviewed",
        "description": "Mark all currently filtered objects as reviewed.",
        "button_text": "Mark Reviewed",
        "callback": "batch_set_reviewed_true"
    },
    {
        "id": "action_unmark_reviewed",
        "type": "button",
        "tab": "Tools & Editors",
        "group": "Presets & Dictionaries",
        "label": "Unmark Filtered as Reviewed",
        "description": "Unmark all currently filtered objects as reviewed.",
        "button_text": "Unmark Reviewed",
        "callback": "batch_set_reviewed_false"
    }
]

class AdvancedSettingsWindow:
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window

        # Get color scheme matching open_filter_menu and open_settings_window
        self.COLORS = {
            "surface": "#f9f9f9",
            "surface_dim": "#dadada",
            "surface_container_low": "#f3f3f3",
            "surface_container_highest": "#e2e2e2",
            "on_surface": "#1a1c1c",
            "on_surface_variant": "#444748",
            "outline": "#747878",
            "outline_variant": "#c4c7c7",
            "primary": "#000000",
            "on_primary": "#ffffff",
            "secondary": "#3b6934",
            "error": "#ba1a1a",
            "botanical_green": "#3e7b3e",
            "search_orange": "#d9480f",
            "surface_tint": "#5f5e5e"
        }

        self.FONT_HEADLINE = ("Hanken Grotesk", sc(14), "bold")
        self.FONT_LABEL = ("JetBrains Mono", sc(10), "bold")
        self.FONT_DATA = ("JetBrains Mono", sc(11))

        # Create Toplevel
        self.win = tk.Toplevel(self.parent)
        self.win.title("Advanced Settings")
        self.win.geometry(f"{sc(700)}x{sc(500)}")
        self.win.configure(bg=self.COLORS["surface"])
        self.win.resizable(True, True)
        self.win.transient(self.parent)
        self.win.grab_set()

        # Bind closing behaviors
        self.win.bind("<Escape>", lambda e: self.win.destroy())

        # Load current advanced settings from user_prefs
        prefs = config.load_prefs()
        self.advanced_prefs = prefs.get("advanced", {})

        # Build Tkinter variables mapping to setting IDs
        self.vars = {}
        for item in ADVANCED_SETTINGS_SCHEMA:
            current_val = self.advanced_prefs.get(item["id"], item.get("default", ""))
            
            if item["type"] == "toggle":
                # Ensure it resolves to a boolean
                current_val = utils.parse_bool(current_val)
                self.vars[item["id"]] = tk.BooleanVar(value=bool(current_val))
            elif item["type"] in ("choice", "text"):
                self.vars[item["id"]] = tk.StringVar(value=str(current_val))

        # Build Main Layout Containers
        self.main_container = tk.Frame(self.win, bg=self.COLORS["surface"], bd=0, highlightthickness=0)
        self.main_container.pack(fill="both", expand=True)

        # Header Block
        self.header = tk.Frame(self.main_container, bg=self.COLORS["surface_container_low"], height=sc(56))
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)
        tk.Frame(self.header, bg=self.COLORS["outline"], height=1).pack(fill="x", side="bottom")

        left_header = tk.Frame(self.header, bg=self.COLORS["surface_container_low"])
        left_header.pack(side="left", fill="y", padx=sc(16))
        tk.Label(left_header, text="Advanced Settings & Features", font=self.FONT_HEADLINE, 
                 fg=self.COLORS["primary"], bg=self.COLORS["surface_container_low"]).pack(side="left", pady=sc(12))

        # Tab Navigation Header
        self.tab_nav = tk.Frame(self.main_container, bg=self.COLORS["surface_container_highest"], height=sc(40))
        self.tab_nav.pack(fill="x", side="top")
        tk.Frame(self.tab_nav, bg=self.COLORS["outline"], height=1).pack(fill="x", side="bottom")

        # Tab Content Area
        self.tab_content_area = tk.Frame(self.main_container, bg=self.COLORS["surface"])
        self.tab_content_area.pack(fill="both", expand=True)

        self.tabs = {}
        self.tab_buttons = {}

        # Footer Action Bar
        self.footer = tk.Frame(self.main_container, bg=self.COLORS["surface_container_low"], height=sc(56))
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)
        tk.Frame(self.footer, bg=self.COLORS["outline"], height=1).pack(fill="x", side="top")

        right_footer = tk.Frame(self.footer, bg=self.COLORS["surface_container_low"])
        right_footer.pack(side="right", fill="y", padx=sc(16))

        tk.Button(right_footer, text="Save", font=self.FONT_LABEL, fg=self.COLORS["on_primary"], 
                  bg=self.COLORS["primary"], bd=1, relief="solid", padx=sc(16), pady=sc(4), 
                  cursor="hand2", command=self.save_settings).pack(side="left", padx=sc(8), pady=sc(12))

        tk.Button(right_footer, text="Cancel", font=self.FONT_LABEL, fg=self.COLORS["on_surface"], 
                  bg=self.COLORS["surface"], bd=1, relief="solid", padx=sc(16), pady=sc(4), 
                  cursor="hand2", command=self.win.destroy).pack(side="left", padx=sc(8), pady=sc(12))

        # Dynamically build tabs and content from schema
        self.build_tabs()

    def show_tab(self, tab_name):
        for name, frame in self.tabs.items():
            frame.pack_forget()
        self.tabs[tab_name].pack(fill="both", expand=True)

        for name, btn_tuple in self.tab_buttons.items():
            btn, border = btn_tuple
            if name == tab_name:
                btn.config(fg=self.COLORS["primary"], bg=self.COLORS["surface"])
                border.config(bg=self.COLORS["primary"])
            else:
                btn.config(fg=self.COLORS["on_surface_variant"], bg=self.COLORS["surface_container_highest"])
                border.config(bg=self.COLORS["outline"])

    def create_tab_btn(self, name, label):
        btn_frame = tk.Frame(self.tab_nav, bg=self.COLORS["surface_container_highest"])
        btn_frame.pack(side="left", fill="y")

        tk.Frame(btn_frame, bg=self.COLORS["outline"], width=1).pack(side="right", fill="y")
        bottom_border = tk.Frame(btn_frame, bg=self.COLORS["outline"], height=2)
        bottom_border.pack(side="bottom", fill="x")

        btn = tk.Button(btn_frame, text=label, font=self.FONT_LABEL, fg=self.COLORS["on_surface_variant"], 
                        bg=self.COLORS["surface_container_highest"], bd=0, relief="flat", padx=sc(16), 
                        cursor="hand2", command=lambda n=name: self.show_tab(n))
        btn.pack(side="top", fill="both", expand=True)
        self.tab_buttons[name] = (btn, bottom_border)

    def build_tabs(self):
        # Extract unique tabs in order
        tab_order = ["System & Backups", "Graphics & Images", "UX & Themes"]
        tab_names = [t for t in tab_order if any(item["tab"] == t for item in ADVANCED_SETTINGS_SCHEMA)]
        
        # Fallback for any tab names not in explicit order
        all_tabs = set(item["tab"] for item in ADVANCED_SETTINGS_SCHEMA)
        for t in all_tabs:
            if t not in tab_names:
                tab_names.append(t)

        if not tab_names:
            tab_names = ["General"]

        for tab_name in tab_names:
            # Container tab frame
            tab_frame = tk.Frame(self.tab_content_area, bg=self.COLORS["surface"])
            self.tabs[tab_name] = tab_frame
            self.create_tab_btn(tab_name, tab_name)

            # Scrollable structure (matches _build_layout_options_section style)
            scroll_container = tk.Frame(tab_frame, bg=self.COLORS["surface"])
            scroll_container.pack(fill="both", expand=True, padx=sc(16), pady=sc(16))

            canvas = tk.Canvas(scroll_container, highlightthickness=0, bd=0, bg=self.COLORS["surface"])
            scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg=self.COLORS["surface"])

            scrollable_frame.bind(
                "<Configure>",
                lambda e, cv=canvas: cv.configure(scrollregion=cv.bbox("all"))
            )

            win_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.bind("<Configure>", lambda e, cv=canvas, wid=win_id: cv.itemconfig(wid, width=e.width))

            def _on_mousewheel(e, cv=canvas):
                if cv.winfo_exists():
                    cv.yview_scroll(int(-1 * (e.delta / 120)), "units")

            self.win.bind_all("<MouseWheel>", _on_mousewheel)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Extract group names for this tab
            tab_items = [item for item in ADVANCED_SETTINGS_SCHEMA if item["tab"] == tab_name]
            group_names = sorted(list(set(item["group"] for item in tab_items)))

            for group_name in group_names:
                group_content = self.create_group(scrollable_frame, group_name)
                group_items = [item for item in tab_items if item["group"] == group_name]

                for item in group_items:
                    if item["type"] == "toggle":
                        self.create_toggle_row(group_content, item["label"], item.get("description", ""), self.vars[item["id"]])
                    elif item["type"] == "choice":
                        self.create_choice_row(group_content, item["label"], item.get("description", ""), 
                                               self.vars[item["id"]], item.get("choices", []))
                    elif item["type"] == "text":
                        self.create_text_row(group_content, item["label"], item.get("description", ""), self.vars[item["id"]])
                    elif item.get("type") == "button":
                        # Support trigger buttons
                        callback_name = item.get("callback")
                        cmd = lambda cb=callback_name: self.execute_button_callback(cb)
                        self.create_button_row(group_content, item["label"], item.get("description", ""), 
                                                item.get("button_text", "Open"), cmd)

        # Show first tab by default
        if tab_names:
            self.show_tab(tab_names[0])

    def create_group(self, parent, title):
        group = tk.Frame(parent, bg=self.COLORS["surface"], highlightbackground=self.COLORS["outline"], highlightthickness=1)
        group.pack(fill="x", pady=(0, sc(16)))
        
        tk.Label(group, text=title.upper(), font=self.FONT_LABEL, fg=self.COLORS["on_surface_variant"], 
                 bg=self.COLORS["surface"]).pack(anchor="w", padx=sc(12), pady=(sc(12), sc(6)))
        
        content = tk.Frame(group, bg=self.COLORS["surface"])
        content.pack(fill="x", padx=sc(12), pady=(0, sc(12)))
        return content

    def create_toggle_row(self, parent, label_text, desc_text, var):
        row = tk.Frame(parent, bg=self.COLORS["surface"])
        row.pack(fill="x", pady=sc(6))

        left_pane = tk.Frame(row, bg=self.COLORS["surface"])
        left_pane.pack(side="left", fill="both", expand=True)

        lbl = tk.Label(left_pane, text=label_text, font=self.FONT_LABEL, fg=self.COLORS["on_surface"], bg=self.COLORS["surface"])
        lbl.pack(anchor="w")

        if desc_text:
            desc = tk.Label(left_pane, text=desc_text, font=("Segoe UI", sc(9)), fg=self.COLORS["on_surface_variant"], bg=self.COLORS["surface"])
            desc.pack(anchor="w", pady=(sc(2), 0))

        sw = ToggleSwitch(row, var, ui_ref=self.main_window)
        sw.pack(side="right", padx=sc(8), pady=sc(4), anchor="center")
        return row

    def create_choice_row(self, parent, label_text, desc_text, var, choices):
        row = tk.Frame(parent, bg=self.COLORS["surface"])
        row.pack(fill="x", pady=sc(6))

        left_pane = tk.Frame(row, bg=self.COLORS["surface"])
        left_pane.pack(side="left", fill="both", expand=True)

        lbl = tk.Label(left_pane, text=label_text, font=self.FONT_LABEL, fg=self.COLORS["on_surface"], bg=self.COLORS["surface"])
        lbl.pack(anchor="w")

        if desc_text:
            desc = tk.Label(left_pane, text=desc_text, font=("Segoe UI", sc(9)), fg=self.COLORS["on_surface_variant"], bg=self.COLORS["surface"])
            desc.pack(anchor="w", pady=(sc(2), 0))

        cb = ttk.Combobox(row, textvariable=var, values=choices, state="readonly", width=25, font=self.FONT_DATA)
        cb.pack(side="right", padx=sc(8), pady=sc(4), anchor="center")
        return row

    def create_text_row(self, parent, label_text, desc_text, var):
        row = tk.Frame(parent, bg=self.COLORS["surface"])
        row.pack(fill="x", pady=sc(6))

        left_pane = tk.Frame(row, bg=self.COLORS["surface"])
        left_pane.pack(side="left", fill="both", expand=True)

        lbl = tk.Label(left_pane, text=label_text, font=self.FONT_LABEL, fg=self.COLORS["on_surface"], bg=self.COLORS["surface"])
        lbl.pack(anchor="w")

        if desc_text:
            desc = tk.Label(left_pane, text=desc_text, font=("Segoe UI", sc(9)), fg=self.COLORS["on_surface_variant"], bg=self.COLORS["surface"])
            desc.pack(anchor="w", pady=(sc(2), 0))

        entry_frame = tk.Frame(row, bg=self.COLORS["surface"], highlightbackground=self.COLORS["outline"], highlightthickness=1)
        entry_frame.pack(side="right", padx=sc(8), pady=sc(4), anchor="center")

        entry = tk.Entry(entry_frame, textvariable=var, font=self.FONT_DATA, fg=self.COLORS["on_surface"], bg=self.COLORS["surface"], bd=0, width=25)
        entry.pack(padx=sc(4), pady=sc(2))
        return row

    def create_button_row(self, parent, label_text, desc_text, button_text, command):
        row = tk.Frame(parent, bg=self.COLORS["surface"])
        row.pack(fill="x", pady=sc(6))

        left_pane = tk.Frame(row, bg=self.COLORS["surface"])
        left_pane.pack(side="left", fill="both", expand=True)

        lbl = tk.Label(left_pane, text=label_text, font=self.FONT_LABEL, fg=self.COLORS["on_surface"], bg=self.COLORS["surface"])
        lbl.pack(anchor="w")

        if desc_text:
            desc = tk.Label(left_pane, text=desc_text, font=("Segoe UI", sc(9)), fg=self.COLORS["on_surface_variant"], bg=self.COLORS["surface"])
            desc.pack(anchor="w", pady=(sc(2), 0))

        btn = tk.Button(row, text=button_text, font=self.FONT_LABEL, fg=self.COLORS["on_surface"], 
                        bg=self.COLORS["surface"], bd=1, relief="solid", padx=sc(12), pady=sc(4), 
                        cursor="hand2", command=command)
        btn.pack(side="right", padx=sc(8), pady=sc(4), anchor="center")
        return row

    def execute_button_callback(self, callback_name):
        if not callback_name:
            return
        method = getattr(self.main_window, callback_name, None)
        if method and callable(method):
            method()
        else:
            messagebox.showerror("Error", f"Callback '{callback_name}' not implemented in MainWindow.", parent=self.win)

    def save_settings(self):
        prefs = config.load_prefs() or {}
        if "advanced" not in prefs:
            prefs["advanced"] = {}

        restart_needed = False
        immediate_callbacks = []

        for item in ADVANCED_SETTINGS_SCHEMA:
            if item.get("type") == "button":
                continue

            item_id = item["id"]
            old_val = self.advanced_prefs.get(item_id, item.get("default", ""))
            
            # Resolve old val types to prevent unnecessary string vs boolean changes
            if item["type"] == "toggle":
                old_val = utils.parse_bool(old_val)
                new_val = bool(self.vars[item_id].get())
            else:
                old_val = str(old_val)
                new_val = str(self.vars[item_id].get()).strip()

            if new_val != old_val:
                prefs["advanced"][item_id] = new_val
                
                # Check refresh/restart action type
                refresh_type = item.get("refresh_type", "none")
                if refresh_type == "restart":
                    restart_needed = True
                elif refresh_type == "immediate" and "callback" in item:
                    immediate_callbacks.append(item["callback"])

        # Save to disk
        config.save_prefs(prefs)
        try:
            utils.reload_log_level()
        except Exception:
            pass

        # Close settings window
        self.win.destroy()

        # Execute immediate callbacks
        for cb_name in immediate_callbacks:
            method = getattr(self.main_window, cb_name, None)
            if method and callable(method):
                try:
                    method()
                except Exception as e:
                    print(f"Error executing callback '{cb_name}': {e}")

        # Warn if restart is required
        if restart_needed:
            messagebox.showinfo(
                "Restart Required", 
                "Some advanced settings have changed and will take full effect after restarting Arbor.", 
                parent=self.main_window.root
            )
