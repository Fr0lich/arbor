import tkinter as tk


class KeybindingManager:
    """
    Centralizes all keyboard shortcuts and event bindings for the application.
    Organized into logical functional categories with deduplicated, conflict-free hotkeys.
    """
    def __init__(self, main_ui, root):
        self.ui = main_ui
        self.root = root

    def bind_global_shortcuts(self):
        """Binds all global shortcuts to the root window."""
        ui = self.ui
        r = self.root

        # ── 1. Record & Specimen Navigation ──────────────────────────────────
        r.bind("<Left>", ui._safe_nav_left)
        r.bind("<Right>", ui._safe_nav_right)
        r.bind("<Alt-Left>", lambda e: ui.go_back())
        r.bind("<Alt-Right>", lambda e: ui.go_forward())
        r.bind("<Control-Up>", lambda e: ui._jump_to_next_problem_specimen(-1))
        r.bind("<Control-Down>", lambda e: ui._jump_to_next_problem_specimen(1))

        # ── 2. Specimen Actions & Curation Verification ───────────────────────
        r.bind("<Control-n>", ui._shortcut_new_object)
        r.bind("<Control-N>", ui._shortcut_quick_new_object)
        r.bind("<Control-Shift-n>", ui._shortcut_quick_new_object)
        r.bind("<Control-Shift-N>", ui._shortcut_quick_new_object)
        r.bind("<Control-d>", ui._shortcut_duplicate_object)
        r.bind("<Control-D>", ui._shortcut_duplicate_object)
        r.bind("<Control-Shift-d>", ui._shortcut_duplicate_object)
        r.bind("<Control-Shift-D>", ui._shortcut_duplicate_object)
        r.bind("<Control-Delete>", ui._shortcut_delete_object)

        # Mark as Reviewed
        r.bind("<Control-r>", lambda e: ui.mark_current_as_reviewed())
        r.bind("<Control-Return>", lambda e: ui.mark_current_as_reviewed())
        r.bind("<Control-KP_Enter>", lambda e: ui.mark_current_as_reviewed())

        # Problem indicator check/uncheck
        r.bind("<space>", ui._toggle_problem_checkbox)

        # Undo / Redo
        r.bind("<Control-z>", ui._smart_undo)
        r.bind("<Control-y>", ui.redo)

        # Field Value Copy / Paste
        r.bind("<Control-Shift-c>", ui._copy_field_value)
        r.bind("<Control-Shift-C>", ui._copy_field_value)
        r.bind("<Control-Shift-v>", ui._paste_field_value)
        r.bind("<Control-Shift-V>", ui._paste_field_value)

        # ── 3. Search, Command Palette & Filtering ───────────────────────────
        # Universal Command Palette & Quick Switcher (Ctrl+K)
        r.bind("<Control-k>", lambda e: ui.open_command_palette())
        r.bind("<Control-K>", lambda e: ui.open_command_palette())

        # Instant Search Bar Focus (Ctrl+F)
        r.bind("<Control-f>", ui.handle_ctrl_f)
        r.bind("<Control-F>", ui.handle_ctrl_f)

        # Advanced Filter Menu (Ctrl+G) & Historical Filter Tab (Ctrl+Shift+F)
        r.bind("<Control-g>", lambda e: ui.open_filter_menu())
        r.bind("<Control-G>", lambda e: ui.open_filter_menu())
        r.bind("<Control-Shift-f>", lambda e: ui.open_advanced_search())
        r.bind("<Control-Shift-F>", lambda e: ui.open_advanced_search())

        # ── 4. Curatorial Tools & Workspace Modes ─────────────────────────────
        # Historical Conflict Resolver (Ctrl+H)
        r.bind("<Control-h>", ui.open_history_shortcut)
        r.bind("<Control-H>", ui.open_history_shortcut)

        # Database Statistics Dashboard (Ctrl+J)
        r.bind("<Control-j>", lambda e: ui.show_statistics())
        r.bind("<Control-J>", lambda e: ui.show_statistics())

        # Save Active Session (Ctrl+S)
        r.bind("<Control-s>", lambda e: ui.save_session("SAVE"))
        r.bind("<Control-S>", lambda e: ui.save_session("SAVE"))

        # Sidebar Expand / Collapse (Ctrl+O)
        r.bind("<Control-o>", ui.handle_ctrl_o)
        r.bind("<Control-O>", ui.handle_ctrl_o)

        # Quick Peek Specimen Inspector (Ctrl+P)
        r.bind("<Control-p>", lambda e: ui.open_quick_peek())
        r.bind("<Control-P>", lambda e: ui.open_quick_peek())

        # Toggle Focus Mode (Ctrl+Q)
        r.bind("<Control-q>", ui.toggle_focus_mode_shortcut)
        r.bind("<Control-Q>", ui.toggle_focus_mode_shortcut)

        # Apply Default Data Preset (Ctrl+Alt+K)
        r.bind("<Control-Alt-k>", ui._apply_default_data_preset_shortcut)
        r.bind("<Control-Alt-K>", ui._apply_default_data_preset_shortcut)

        # ── 5. Input Field Focus Navigation ───────────────────────────────────
        # Focus Registration / Taxonomy inputs (Ctrl+E or Ctrl+I)
        r.bind("<Control-e>", ui._focus_first_reg)
        r.bind("<Control-E>", ui._focus_first_reg)
        r.bind("<Control-i>", ui._focus_first_reg)
        r.bind("<Control-I>", ui._focus_first_reg)

        # Cycle Taxonomy Tabs (Ctrl+PageUp / Ctrl+PageDown)
        r.bind("<Control-Prior>", lambda e: ui._switch_reg_tab(-1))
        r.bind("<Control-Next>", lambda e: ui._switch_reg_tab(1))

        # Focus Location Inputs (Ctrl+L, Ctrl+Shift+L, F4)
        r.bind("<Control-l>", ui._focus_first_location)
        r.bind("<Control-L>", ui._focus_first_location)
        r.bind("<Control-Shift-l>", ui._focus_first_location)
        r.bind("<Control-Shift-L>", ui._focus_first_location)
        r.bind("<F4>", ui._focus_first_location)

        # Focus Problem Checkboxes (Ctrl+Shift+P, F3)
        r.bind("<Control-Shift-p>", ui._focus_first_problem)
        r.bind("<Control-Shift-P>", ui._focus_first_problem)
        r.bind("<F3>", ui._focus_first_problem)

        # ── 6. Image Viewport Controls ────────────────────────────────────────
        r.bind("<Control-plus>", lambda e: ui.zoom_image_in())
        r.bind("<Control-equal>", lambda e: ui.zoom_image_in())
        r.bind("<Control-minus>", lambda e: ui.zoom_image_out())
        r.bind("<Control-Key-0>", lambda e: ui.reset_image_view())
        r.bind("<Alt-r>", lambda e: ui.rotate_image())
        r.bind("<Alt-R>", lambda e: ui.rotate_image())
        r.bind("<Control-b>", ui._next_image_shortcut)
        r.bind("<Shift-Left>", ui._prev_image_shortcut)
        r.bind("<Shift-Right>", ui._next_image_shortcut)

        # ── 7. Workspace Panels & Help ────────────────────────────────────────
        # Keyboard Shortcuts HUD (F1)
        r.bind("<F1>", lambda e: ui.show_shortcuts())

        # Collapsible Panel Toggles (F6: Directory, F7: Registration, F8: Image)
        r.bind("<F6>", ui.toggle_list_panel_shortcut)
        r.bind("<F7>", ui.toggle_reg_panel_shortcut)
        r.bind("<F8>", ui.toggle_images_panel_shortcut)

    def bind_search_shortcuts(self, search_entry):
        """Binds shortcuts specific to the inline search bar."""
        search_entry.bind("<KeyRelease>",  self.ui._on_inline_search_key)
        search_entry.bind("<Escape>",      self.ui._clear_inline_search)
        search_entry.bind("<FocusIn>",     self.ui._search_focus_in)
        search_entry.bind("<FocusOut>",    self.ui._search_focus_out)
        search_entry.bind("<Button-1>",    self.ui._search_focus_in)
        search_entry.bind("<Return>",      self.ui._on_search_bar_enter)
        search_entry.bind("<Down>",        self.ui._on_search_arrow_down)
        search_entry.bind("<Up>",          self.ui._on_search_arrow_up)

        def _focus_list(event):
            self.ui.object_list.focus_set()
            if not self.ui.object_list.selection():
                children = self.ui.object_list.get_children()
                if children:
                    self.ui.object_list.selection_set(children[0])
            return "break"
        search_entry.bind("<Tab>", _focus_list)

    def bind_location_shortcuts(self, widget):
        """Binds navigation shortcuts for location input fields."""
        widget.bind("<Shift-Up>", self.ui._location_nav_up)
        widget.bind("<Shift-Down>", self.ui._location_nav_down)
        widget.bind("<Control-Up>", self.ui._location_nav_up)
        widget.bind("<Control-Down>", self.ui._location_nav_down)
        widget.bind("<Return>", self.ui._location_nav_down)

    def bind_problem_shortcuts(self, widget):
        """Binds navigation shortcuts for problem checkbox fields."""
        widget.bind("<Shift-Up>", self.ui._problem_nav_up)
        widget.bind("<Shift-Down>", self.ui._problem_nav_down)
        widget.bind("<Control-Up>", self.ui._problem_nav_up)
        widget.bind("<Control-Down>", self.ui._problem_nav_down)
        widget.bind("<Return>", lambda e, c=widget: self.ui._toggle_specific_checkbox(c))

    def bind_image_shortcuts(self, target=None):
        """Binds keyboard shortcuts specific to the Image Panel."""
        t = target if target is not None else self.ui
        self.root.bind("<Control-b>", getattr(t, "_next_image_shortcut", self.ui._next_image_shortcut))
        self.root.bind("<Shift-Left>", getattr(t, "_prev_image_shortcut", self.ui._prev_image_shortcut))
        self.root.bind("<Shift-Right>", getattr(t, "_next_image_shortcut", self.ui._next_image_shortcut))
        self.root.bind("<Control-plus>", lambda e: t.zoom_image_in())
        self.root.bind("<Control-equal>", lambda e: t.zoom_image_in())
        self.root.bind("<Control-minus>", lambda e: t.zoom_image_out())
        self.root.bind("<Alt-r>", lambda e: t.rotate_image())
        self.root.bind("<Alt-R>", lambda e: t.rotate_image())
        self.root.bind("<Control-Key-0>", lambda e: t.reset_image_view())
