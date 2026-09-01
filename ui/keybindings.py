import tkinter as tk

class KeybindingManager:
    """
    Centralizes all keyboard shortcuts and event bindings for the application.
    """
    def __init__(self, main_ui, root):
        self.ui = main_ui
        self.root = root

    def bind_global_shortcuts(self):
        """Binds all global shortcuts to the root window."""
        self.root.bind("<Left>", self.ui._safe_nav_left)
        self.root.bind("<Right>", self.ui._safe_nav_right)

        self.root.bind("<Control-n>", lambda e: self.ui.add_new_object())
        self.root.bind("<Control-N>", lambda e: self.ui._quick_new_object())
        self.root.bind("<Control-D>", lambda e: self.ui._duplicate_current_object())
        self.root.bind("<Control-Delete>", lambda e: self.ui.delete_current_object())

        # Database Statistics shortcut
        self.root.bind("<Control-j>", lambda e: self.ui.show_statistics())
        self.root.bind("<Control-s>", lambda e: self.ui.save_session("SAVE"))
        self.root.bind("<Control-g>", lambda e: self.ui.open_filter_menu())
        self.root.bind("<Control-z>", self.ui._smart_undo)
        self.root.bind("<Control-y>", self.ui.redo)
        self.root.bind("<Control-n>", self.ui._shortcut_new_object)
        self.root.bind("<F1>", lambda e: self.ui.show_shortcuts())
        self.root.bind("<Control-r>", lambda e: self.ui.mark_current_as_reviewed())
        self.root.bind("<Control-Return>", lambda e: self.ui.mark_current_as_reviewed())
        self.root.bind("<Control-KP_Enter>", lambda e: self.ui.mark_current_as_reviewed())

        self.root.bind("<space>", self.ui._toggle_problem_checkbox)

        self.root.bind("<Control-q>", self.ui.toggle_focus_mode_shortcut)
        self.root.bind("<Control-h>", self.ui.open_history_shortcut)

        self.root.bind("<Control-e>", self.ui._focus_first_reg)
        self.root.bind("<Control-Prior>", lambda e: self.ui._switch_reg_tab(-1))
        self.root.bind("<Control-Next>", lambda e: self.ui._switch_reg_tab(1))




        self.root.bind("<Control-l>", self.ui._focus_first_location)
        self.root.bind("<Control-p>", self.ui._focus_first_problem)
        self.root.bind("<Control-i>", self.ui._focus_first_reg)
        self.root.bind("<Control-Shift-P>", self.ui._focus_first_problem)
        self.root.bind("<F3>", self.ui._focus_first_problem)
        self.root.bind("<Control-Shift-L>", self.ui._focus_first_location)
        self.root.bind("<F4>", self.ui._focus_first_location)

        self.root.bind("<Alt-Left>", lambda e: self.ui.go_back())
        self.root.bind("<Alt-Right>", lambda e: self.ui.go_forward())


        self.root.bind("<Control-b>", self.ui._next_image_shortcut)
        self.root.bind("<Shift-Left>", self.ui._prev_image_shortcut)
        self.root.bind("<Shift-Right>", self.ui._next_image_shortcut)
        self.root.bind("<Control-plus>", lambda e: self.ui.zoom_image_in())
        self.root.bind("<Control-equal>", lambda e: self.ui.zoom_image_in())
        self.root.bind("<Control-minus>", lambda e: self.ui.zoom_image_out())
        self.root.bind("<Alt-r>", lambda e: self.ui.rotate_image())
        self.root.bind("<Control-R>", lambda e: self.ui.rotate_image())
        self.root.bind("<Control-Key-0>", lambda e: self.ui.reset_image_view())


        self.root.bind("<Control-Delete>", self.ui._shortcut_delete_object)
        self.root.bind("<Control-Shift-N>", self.ui._shortcut_quick_new_object)
        self.root.bind("<Control-Shift-D>", self.ui._shortcut_duplicate_object)
        self.root.bind("<Control-Shift-C>", self.ui._copy_field_value)
        self.root.bind("<Control-Shift-V>", self.ui._paste_field_value)

        self.root.bind("<Control-k>", self.ui._apply_default_data_preset_shortcut)
        self.root.bind("<Control-K>", self.ui._apply_default_data_preset_shortcut)

        self.root.bind("<Control-o>", self.ui.handle_ctrl_o)
        self.root.bind("<Control-O>", self.ui.handle_ctrl_o)

        self.root.bind("<Control-f>", self.ui.handle_ctrl_f)
        self.root.bind("<Control-F>", self.ui.handle_ctrl_f)

        # Collapsible Panel Toggles for Laptop Views
        self.root.bind("<F6>", self.ui.toggle_list_panel_shortcut)
        self.root.bind("<F7>", self.ui.toggle_reg_panel_shortcut)
        self.root.bind("<F8>", self.ui.toggle_images_panel_shortcut)
        pass

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
        self.root.bind("<Control-R>", lambda e: t.rotate_image())
        self.root.bind("<Control-Key-0>", lambda e: t.reset_image_view())

