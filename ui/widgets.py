import tkinter as tk
from tkinter import ttk
import utils

def create_toggle_row(parent, label_text, var, command=None, ui_ref=None, info_text=None):
    from config import sc
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=sc(4))
    lbl = ttk.Label(row, text=label_text)
    lbl.pack(side="left", anchor="w")
    if info_text:
        badge = InfoButton(row, text=info_text, ui_ref=ui_ref)
        badge.pack(side="left", padx=(sc(6), 0))
    sw = ToggleSwitch(row, var, command=command, ui_ref=ui_ref)
    sw.pack(side="right")
    return row

def create_info_badge(parent, text, ui_ref=None, **kwargs):
    """Factory helper to create and return an InfoButton widget."""
    return InfoButton(parent, text=text, ui_ref=ui_ref, **kwargs)

class InfoButton(tk.Canvas):
    """
    Lightweight, accessible Info Badge (ⓘ / ?) widget with floating tooltip.
    Features:
    - Subtle circular badge with muted foreground (#747878 light / #9399b2 dark)
    - Hover & focus micro-interactions with gentle background highlight
    - Non-blocking floating tooltip popover with high-DPI scaling and screen bounds checking
    - Full dark mode theme support
    - Accessible keyboard navigation (Tab focus + Enter/Space trigger)
    - Clean lifecycle cleanup on unbind/destroy
    """
    def __init__(self, parent, text="", ui_ref=None, width=18, height=18, icon="ⓘ", **kwargs):
        from config import sc
        self.ui_ref = ui_ref
        self.text = text
        self.icon = icon
        self.base_width = width
        self.base_height = height
        self._is_hovered = False
        self._is_focused = False
        self.tip_window = None

        scaled_w = sc(width) if ui_ref else width
        scaled_h = sc(height) if ui_ref else height
        kwargs.setdefault('takefocus', 1)

        super().__init__(parent, width=scaled_w, height=scaled_h, highlightthickness=0, bd=0, cursor="hand2", **kwargs)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<space>", self._on_click)
        self.bind("<Return>", self._on_click)
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Destroy>", self._on_destroy)

        self.draw()

    def get_text(self):
        return self.text

    def set_text(self, text):
        self.text = text

    def is_dark_mode(self):
        if self.ui_ref:
            if hasattr(self.ui_ref, "var_dark_mode") and isinstance(self.ui_ref.var_dark_mode, tk.Variable):
                try:
                    return bool(self.ui_ref.var_dark_mode.get())
                except Exception:
                    pass
            if hasattr(self.ui_ref, "dark_mode_active"):
                return bool(self.ui_ref.dark_mode_active)
            if hasattr(self.ui_ref, "app") and self.ui_ref.app and hasattr(self.ui_ref.app, "dark_mode_active"):
                return bool(self.ui_ref.app.dark_mode_active)
        try:
            bg_col = self.master.cget("bg")
            if bg_col and bg_col.startswith("#") and len(bg_col) == 7:
                r, g, b = int(bg_col[1:3], 16), int(bg_col[3:5], 16), int(bg_col[5:7], 16)
                if (r * 0.299 + g * 0.587 + b * 0.114) < 128:
                    return True
        except Exception:
            pass
        try:
            import config
            prefs = config.load_prefs() or {}
            return bool(prefs.get("dark_mode", False))
        except Exception:
            return False

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1:
            w = self.cget("width")
        if h <= 1:
            h = self.cget("height")
        try:
            w = int(w)
            h = int(h)
        except (ValueError, TypeError):
            w, h = 18, 18

        is_dark = self.is_dark_mode()

        try:
            bg_canvas = self.master.cget("bg")
        except Exception:
            bg_canvas = "#181c19" if is_dark else "#ffffff"

        if is_dark:
            fg_icon = "#e8ebe9" if (self._is_hovered or self._is_focused) else "#9399b2"
            circle_fill = "#141715" if (self._is_hovered or self._is_focused) else bg_canvas
            circle_outline = "#89b4fa" if self._is_focused else ("#585b70" if self._is_hovered else "#45475a")
        else:
            fg_icon = "#2c302e" if (self._is_hovered or self._is_focused) else "#747878"
            circle_fill = "#e9ece5" if (self._is_hovered or self._is_focused) else bg_canvas
            circle_outline = "#0058a3" if self._is_focused else ("#747878" if self._is_hovered else "#c4c7c7")

        self.configure(bg=bg_canvas)

        pad = 2
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - pad

        self.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=circle_fill, outline=circle_outline, width=1
        )

        font_size = max(7, int(r * 0.95))
        self.create_text(
            cx, cy,
            text=self.icon,
            fill=fg_icon,
            font=("Segoe UI", font_size, "bold")
        )

    def _on_enter(self, event=None):
        self._is_hovered = True
        self.draw()
        self.show_tip()

    def _on_leave(self, event=None):
        self._is_hovered = False
        self.draw()
        self.hide_tip()

    def _on_focus_in(self, event=None):
        self._is_focused = True
        self.draw()
        self.show_tip()

    def _on_focus_out(self, event=None):
        self._is_focused = False
        self.draw()
        self.hide_tip()

    def _on_click(self, event=None):
        if self.tip_window:
            self.hide_tip()
        else:
            self.show_tip()

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        from config import sc

        try:
            self.update_idletasks()
            x = self.winfo_rootx() + self.winfo_width() + sc(6)
            y = self.winfo_rooty() - sc(2)
        except Exception:
            return

        is_dark = self.is_dark_mode()
        if is_dark:
            bg_color = "#212622"
            fg_color = "#e8ebe9"
            border_color = "#45475a"
        else:
            bg_color = "#2c302e"
            fg_color = "#ffffff"
            border_color = "#4c4546"

        self.tip_window = tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)

        outer = tk.Frame(tw, bg=border_color, padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=bg_color, padx=sc(10), pady=sc(7))
        inner.pack(fill="both", expand=True)

        font_tip = ("Inter", sc(9))
        label = tk.Label(
            inner,
            text=self.text,
            justify=tk.LEFT,
            background=bg_color,
            foreground=fg_color,
            font=font_tip,
            wraplength=sc(340),
            anchor="w"
        )
        label.pack(fill="both", expand=True)

        tw.update_idletasks()
        tip_w = tw.winfo_reqwidth()
        tip_h = tw.winfo_reqheight()
        screen_w = tw.winfo_screenwidth()
        screen_h = tw.winfo_screenheight()

        if x + tip_w > screen_w - 10:
            x = self.winfo_rootx() - tip_w - sc(6)
            if x < 10:
                x = max(10, screen_w - tip_w - 10)

        if y + tip_h > screen_h - 10:
            y = max(10, screen_h - tip_h - 10)

        tw.wm_geometry(f"+{int(x)}+{int(y)}")

    def hide_tip(self, event=None):
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

    def _on_destroy(self, event=None):
        self.hide_tip()

class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable, command=None, width=42, height=22, ui_ref=None, **kwargs):
        from config import sc
        scaled_w = sc(width) if ui_ref else width
        scaled_h = sc(height) if ui_ref else height
        kwargs.setdefault('takefocus', 1)
        super().__init__(parent, width=scaled_w, height=scaled_h, highlightthickness=0, bd=0, **kwargs)
        self.variable = variable
        self.command = command
        self.ui_ref = ui_ref

        self.bind("<Button-1>", self._on_click)
        self.bind("<space>", self._on_click)
        self.bind("<Return>", self._on_click)
        self.bind("<FocusIn>", lambda e: self.draw())
        self.bind("<FocusOut>", lambda e: self.draw())
        self.bind("<Configure>", lambda e: self.draw())
        self._trace_id = self.variable.trace_add("write", lambda *args: self.draw())

        self.draw()

    def _on_click(self, event=None):
        self.variable.set(not self.variable.get())
        if self.command:
            self.command()

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1:
            w = self.cget("width")
        if h <= 1:
            h = self.cget("height")

        try:
            w = int(w)
            h = int(h)
        except (ValueError, TypeError):
            w = 42
            h = 22

        is_dark = False
        if self.ui_ref and hasattr(self.ui_ref, "dark_mode_active"):
            is_dark = self.ui_ref.dark_mode_active

        val = self.variable.get()

        if is_dark:
            bg_canvas = "#181c19"
            bg_active = "#a6e3a1"
            bg_inactive = "#141715"
            fg_knob_active = "#11111b"
            fg_knob_inactive = "#e8ebe9"
        else:
            bg_canvas = "#f2f5f1"
            bg_active = "#3a7d44"
            bg_inactive = "#c4c7c7"
            fg_knob_active = "#ffffff"
            fg_knob_inactive = "#ffffff"

        self.configure(bg=bg_canvas)

        self.create_rectangle(0, 0, w, h, fill=bg_active if val else bg_inactive, outline="")

        pad = 2
        knob_size = h - pad * 2
        if val:
            x = w - pad - knob_size
            knob_color = fg_knob_active
        else:
            x = pad
            knob_color = fg_knob_inactive

        self.create_rectangle(x, pad, x + knob_size, pad + knob_size, fill=knob_color, outline="")

        if self.focus_get() == self:
            focus_color = "#4dabf7" if is_dark else "#0058a3"
            self.create_rectangle(0, 0, w-1, h-1, outline=focus_color, width=2, dash=(2, 2))

    def destroy(self):
        try:
            self.variable.trace_remove("write", self._trace_id)
        except Exception:
            pass
class SleekScrollbar(tk.Canvas):
    """A sleek, modern capsule-thumb scrollbar styled for Stitch-design principles."""
    def __init__(self, parent, command=None, is_dark=False, width=8, **kwargs):
        self.command = command
        self.is_dark = is_dark
        self._first = 0.0
        self._last = 1.0
        self._dragging = False
        self._hover = False

        bg_color = "#181c19" if is_dark else "#f2f5f1"
        super().__init__(parent, width=width, bg=bg_color, highlightthickness=0, bd=0, **kwargs)

        self._update_colors()
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _update_colors(self):
        self.track_bg = "#181c19" if self.is_dark else "#f2f5f1"
        self.thumb_normal = "#45475a" if self.is_dark else "#cccccc"
        self.thumb_hover = "#585b70" if self.is_dark else "#aaaaaa"
        self.thumb_active = "#89b4fa" if self.is_dark else "#0058a3"
        self.configure(bg=self.track_bg)

    def set_theme(self, is_dark):
        self.is_dark = is_dark
        self._update_colors()
        self._draw()

    def set(self, first, last):
        try:
            self._first = float(first)
            self._last = float(last)
        except (ValueError, TypeError):
            return
        self._draw()

    def _draw(self, event=None):
        self.delete("all")
        h = self.winfo_height()
        w = self.winfo_width()
        if h <= 4 or w <= 4:
            return

        if self._last - self._first >= 0.999:
            return

        y0 = max(2, int(self._first * h))
        y1 = min(h - 2, int(self._last * h))
        if y1 - y0 < 16:
            y1 = min(h - 2, y0 + 16)

        color = self.thumb_active if self._dragging else (self.thumb_hover if self._hover else self.thumb_normal)
        r = max(1, (w - 2) // 2)
        # Draw rounded capsule thumb
        self.create_oval(2, y0, w - 2, y0 + (w - 4), fill=color, outline="")
        if y1 - y0 > (w - 4):
            self.create_rectangle(2, y0 + r, w - 2, y1 - r, fill=color, outline="")
        self.create_oval(2, y1 - (w - 4), w - 2, y1, fill=color, outline="")

    def _on_enter(self, event):
        self._hover = True
        self._draw()

    def _on_leave(self, event):
        self._hover = False
        self._draw()

    def _on_press(self, event):
        self._dragging = True
        self._scroll_to(event.y)

    def _on_drag(self, event):
        self._scroll_to(event.y)

    def _on_release(self, event):
        self._dragging = False
        self._draw()

    def _scroll_to(self, y):
        h = self.winfo_height()
        if h <= 1 or self.command is None:
            return
        fraction = max(0.0, min(1.0, y / float(h)))
        self.command("moveto", fraction)


class TreeviewListboxWrapper(ttk.Frame):
    def __init__(self, parent, main_window, **kwargs):
        super().__init__(parent)
        self.main_window = main_window
        from config import sc

        # State tracking
        self.items_list = []      # list of oids in order
        self.items_set = set()    # fast lookup set
        self._oid_to_index = {}   # O(1) oid -> idx inverted index
        self.item_data = {}       # oid -> {title, genus, species, reviewed, foreground, tags, ...}
        self.selected_iids = []   # list of selected oids
        self.focused_iid = None
        self._resize_job = None

        # Event binding storage
        self.custom_bindings = []

        # Create Treeview for Compact Mode
        self.tree = ttk.Treeview(self, columns=("Rev", "ID", "Genus", "Species"), show="headings", selectmode="extended")
        self.tree.heading("Rev", text="✔")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Genus", text="Genus")
        self.tree.heading("Species", text="Species")

        self.tree.column("Rev", width=sc(28), minwidth=sc(28), stretch=False, anchor="center")
        self.tree.column("ID", width=sc(50), minwidth=sc(35), stretch=True)
        self.tree.column("Genus", width=sc(85), minwidth=sc(60), stretch=True)
        self.tree.column("Species", width=sc(85), minwidth=sc(60), stretch=True)

        # Pre-configure common color and alternating row tags to eliminate Tcl roundtrips during bulk insert
        self._configured_tags = set()
        self._tag_configs = {}
        for c in ("4CAF50", "2E7D32", "BB86FC", "7B1FA2", "f28b82", "C62828", "5ab0e8", "0284C7", "f0ad4e", "0bd45b", "bb6bd9", "d9534f"):
            tname = f"color_{c}"
            self.tree.tag_configure(tname, foreground=f"#{c}")
            self._configured_tags.add(tname)
            self._tag_configs[tname] = {"foreground": f"#{c}"}

        # Bind double-click and selection for Treeview click
        self.tree.bind("<Button-1>", self._on_treeview_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_treeview_select)
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", self._on_tree_leave)
        self._last_hovered_iid = None

        # Create Scrollable Canvas and SleekScrollbar for Detailed Mode
        self.canvas_container = ttk.Frame(self)
        self.scrollbar = SleekScrollbar(self.canvas_container, command=self.canvas_yview_bridge, width=8)
        self.canvas = tk.Canvas(self.canvas_container, highlightthickness=0, yscrollcommand=self._on_canvas_scroll)
        # PERFORMANCE OPTIMIZATION (Bolt): True Virtualization. Removed self.scrollable_frame.

        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Intercept original scrolling methods to trigger virtual viewport updates
        self.original_yview = self.canvas.yview
        self.canvas.yview = self.custom_yview
        self.canvas.yview_scroll = self.custom_yview_scroll
        self.canvas.yview_moveto = self.custom_yview_moveto

        # Mousewheel on canvas
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

        self._card_height = None
        self._active_card_windows = {} # Maps idx -> (window_id, frame_widget)
        self._card_pool = [] # Pool of reusable card widget dictionaries
        self._pending_viewport_update = None

        self._setup_virtual_card_bindtag()

        # Keyboard Navigation bindings for Detailed and Compact Mode
        for target_widget in (self, self.canvas, self.tree):
            target_widget.bind("<Up>", self._on_keypress_up)
            target_widget.bind("<Down>", self._on_keypress_down)
            target_widget.bind("<Prior>", self._on_keypress_page_up)
            target_widget.bind("<Next>", self._on_keypress_page_down)
            target_widget.bind("<Home>", self._on_keypress_home)
            target_widget.bind("<End>", self._on_keypress_end)
            target_widget.bind("<space>", self._on_keypress_space)
            target_widget.bind("<Return>", self._on_keypress_return)

        # Initial active view check
        self._trace_id = None
        self._tree_dirty = False
        if hasattr(self.main_window, "focus_mode_var"):
            self.focus_mode_var = self.main_window.focus_mode_var
            self._trace_id = self.focus_mode_var.trace_add("write", self._on_focus_mode_changed)
        else:
            self.focus_mode_var = None

        self.active_view = "compact"
        self.update_view_visibility()

    def _ensure_tree_synced(self):
        if getattr(self, "_tree_dirty", False):
            self._tree_dirty = False
            children = self.tree.get_children()
            if children:
                self.tree.delete(*children)
            for oid in self.items_list:
                data = self.item_data.get(oid)
                if data:
                    self.tree.insert("", "end", iid=oid, values=tuple(data.get("values", ())), tags=tuple(data.get("tags", ())))

    def _on_keypress_up(self, event):
        if not self.items_list:
            return "break"
        if not self.selected_iids:
            new_idx = 0
        else:
            first_sel = self.selected_iids[0]
            curr_idx = self._oid_to_index.get(first_sel, 0)
            new_idx = max(0, curr_idx - 1)
        self.selection_clear()
        self.selection_set(new_idx)
        self.see(new_idx)
        self.event_generate("<<ListboxSelect>>")
        return "break"

    def _on_keypress_down(self, event):
        if not self.items_list:
            return "break"
        if not self.selected_iids:
            new_idx = 0
        else:
            first_sel = self.selected_iids[0]
            curr_idx = self._oid_to_index.get(first_sel, 0)
            new_idx = min(len(self.items_list) - 1, curr_idx + 1)
        self.selection_clear()
        self.selection_set(new_idx)
        self.see(new_idx)
        self.event_generate("<<ListboxSelect>>")
        return "break"

    def _on_keypress_home(self, event):
        if not self.items_list:
            return "break"
        self.selection_clear()
        self.selection_set(0)
        self.see(0)
        self.event_generate("<<ListboxSelect>>")
        return "break"

    def _on_keypress_end(self, event):
        if not self.items_list:
            return "break"
        last_idx = len(self.items_list) - 1
        self.selection_clear()
        self.selection_set(last_idx)
        self.see(last_idx)
        self.event_generate("<<ListboxSelect>>")
        return "break"

    def _on_keypress_page_up(self, event):
        if not self.items_list:
            return "break"
        first_sel = self.selected_iids[0] if self.selected_iids else self.items_list[0]
        curr_idx = self._oid_to_index.get(first_sel, 0)
        new_idx = max(0, curr_idx - 10)
        self.selection_clear()
        self.selection_set(new_idx)
        self.see(new_idx)
        self.event_generate("<<ListboxSelect>>")
        return "break"

    def _on_keypress_page_down(self, event):
        if not self.items_list:
            return "break"
        first_sel = self.selected_iids[0] if self.selected_iids else self.items_list[0]
        curr_idx = self._oid_to_index.get(first_sel, 0)
        new_idx = min(len(self.items_list) - 1, curr_idx + 10)
        self.selection_clear()
        self.selection_set(new_idx)
        self.see(new_idx)
        self.event_generate("<<ListboxSelect>>")
        return "break"

    def _on_keypress_space(self, event):
        """Toggle reviewed status for the active object directly from keyboard."""
        if not self.selected_iids:
            return "break"
        active_oid = self.selected_iids[0]
        if hasattr(self.main_window, "_toggle_reviewed_for_id"):
            self.main_window._toggle_reviewed_for_id(active_oid)
        return "break"

    def _on_keypress_return(self, event):
        if hasattr(self.main_window, "_on_list_return"):
            self.main_window._on_list_return(event)
        return "break"

    def _on_focus_mode_changed(self, *args):
        self.update_view_visibility()
        if hasattr(self.main_window, "refresh_list"):
            self.main_window.refresh_list()

    def update_view_visibility(self):
        focus_active = self.focus_mode_var.get() if self.focus_mode_var else False
        is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
        canvas_bg = "#181c19" if is_dark else "#f2f5f1"
        self.canvas.configure(bg=canvas_bg)

        if focus_active:
            # Compact view (Treeview)
            self._ensure_tree_synced()
            self.canvas_container.pack_forget()
            self.tree.pack(fill="both", expand=True)
            self.active_view = "compact"
            self._clear_virtual_cards()
        else:
            # Detailed view (Canvas Cards)
            self.tree.pack_forget()
            self.canvas_container.pack(fill="both", expand=True)
            self.scrollbar.set_theme(is_dark)
            self.scrollbar.pack(side="right", fill="y", padx=(0, 2), pady=2)
            self.canvas.pack(side="left", fill="both", expand=True)
            self.active_view = "detailed"

            if self._card_height is None:
                self._measure_card_height()

            # PERFORMANCE OPTIMIZATION (Bolt): True Virtualization.
            self._schedule_viewport_update()

        self._sync_view_selections()

    def canvas_yview_bridge(self, *args):
        return self.canvas.yview(*args)

    def _on_canvas_scroll(self, first, last):
        if hasattr(self, "scrollbar") and self.scrollbar.winfo_exists():
            self.scrollbar.set(first, last)
        if getattr(self, "_external_yscrollcommand", None):
            try:
                self._external_yscrollcommand(first, last)
            except Exception:
                pass

    def _on_canvas_configure(self, event):
        self._last_canvas_width = event.width
        if self._card_height is None and self.active_view == "detailed":
            self._measure_card_height()
        self._schedule_viewport_update()
        # Update widths of all active virtual card windows
        for win_id, _ in self._active_card_windows.values():
            try:
                self.canvas.itemconfig(win_id, width=event.width)
            except Exception:
                pass

    def _on_mousewheel(self, event):
        if hasattr(event, "delta") and event.delta:
            scroll_units = int(-1 * (event.delta / 120))
        elif hasattr(event, "num"):
            if event.num == 4:
                scroll_units = -1
            elif event.num == 5:
                scroll_units = 1
            else:
                return
        else:
            return
        self.canvas.yview_scroll(scroll_units, "units")
        self._schedule_viewport_update()

    def _on_tree_motion(self, event):
        iid = self.tree.identify_row(event.y)
        if iid != getattr(self, "_last_hovered_iid", None):
            if getattr(self, "_last_hovered_iid", None):
                try:
                    tags = list(self.tree.item(self._last_hovered_iid, "tags"))
                    if "hover" in tags:
                        tags.remove("hover")
                        self.tree.item(self._last_hovered_iid, tags=tags)
                except Exception:
                    pass
            
            if iid:
                try:
                    tags = list(self.tree.item(iid, "tags"))
                    if "hover" not in tags:
                        tags.append("hover")
                        self.tree.item(iid, tags=tags)
                except Exception:
                    pass
            
            self._last_hovered_iid = iid
            
        is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
        hover_bg = "#141715" if is_dark else "#e9ece5"
        try:
            self.tree.tag_configure("hover", background=hover_bg)
        except Exception:
            pass

    def _on_tree_leave(self, event):
        if getattr(self, "_last_hovered_iid", None):
            try:
                tags = list(self.tree.item(self._last_hovered_iid, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    self.tree.item(self._last_hovered_iid, tags=tags)
            except Exception:
                pass
            self._last_hovered_iid = None

    def _on_treeview_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            if column == "#1":
                item_id = self.tree.identify_row(event.y)
                if item_id:
                    self.main_window._toggle_reviewed_for_id(item_id)
                    self.selection_clear()
                    self.selection_set(item_id)
                    return "break"

    def _on_treeview_select(self, event):
        tree_sel = self.tree.selection()
        if tree_sel:
            self.selected_iids = list(tree_sel)
            self.focused_iid = tree_sel[0]

    def _sync_view_selections(self):
        if self.active_view == "compact":
            self._ensure_tree_synced()
            tree_sel = self.tree.selection()
            if set(tree_sel) != set(self.selected_iids):
                self.tree.selection_set(self.selected_iids)
        elif self.active_view == "detailed":
            self.redraw_cards_highlights()

    def redraw_cards_highlights(self):
        is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
        bg_selected = "#ffffff" if not is_dark else "#2d3149"
        accent_selected = "#3a7d44" if not is_dark else "#a6e3a1"
        bg_normal = "#f2f5f1" if not is_dark else "#24273a"

        # Only update active virtual cards on screen for instant O(1) response
        for idx in list(self._active_card_windows.keys()):
            if 0 <= idx < len(self.items_list):
                oid = self.items_list[idx]
                if oid in self.item_data:
                    card_body = self.item_data[oid].get("card_body")
                    accent_strip = self.item_data[oid].get("accent_strip")
                    accent_normal = self.item_data[oid].get("accent_color_normal", bg_normal)
                    if card_body and card_body.winfo_exists():
                        is_sel = oid in self.selected_iids
                        bg = bg_selected if is_sel else bg_normal
                        self._set_bg_recursive(card_body, bg)
                    if accent_strip and accent_strip.winfo_exists():
                        is_sel = oid in self.selected_iids
                        accent_strip.configure(bg=accent_selected if is_sel else accent_normal)

    def _set_bg_recursive(self, widget, bg_color):
        if getattr(widget, "is_badge", False):
            return
        if getattr(widget, "is_accent_strip", False):
            return
        try:
            if not widget.winfo_exists():
                return
            widget.configure(bg=bg_color)
        except Exception:
            pass

        try:
            children = widget.winfo_children()
        except Exception:
            return

        for child in children:
            self._set_bg_recursive(child, bg_color)

    def _on_card_click(self, oid, event=None):
        """Single-click: select card and navigate to its object."""
        self.selected_iids = [oid]
        self.focused_iid = oid
        self.redraw_cards_highlights()
        # Sync treeview selection silently — flag tells on_list_select not to
        # double-navigate (it would also block on _is_searching if active).
        self._card_driving_nav = True
        try:
            if set(self.tree.selection()) != set(self.selected_iids):
                self.tree.selection_set(self.selected_iids)
        except Exception:
            pass
        finally:
            self._card_driving_nav = False
        mw = self.main_window
        # Commit unsaved edits on the previously loaded object
        if hasattr(mw, "commit_current_object"):
            mw.commit_current_object()
        # Navigate directly – bypasses the _is_searching guard in on_list_select
        if hasattr(mw, "_list_select_job") and mw._list_select_job:
            try:
                mw.root.after_cancel(mw._list_select_job)
            except Exception:
                pass
        if hasattr(mw, "_deferred_list_select"):
            mw._list_select_job = mw.root.after(
                100, lambda o=oid: mw._deferred_list_select(o)
            )
        elif hasattr(mw, "load_object"):
            mw.root.after(100, lambda o=oid: mw.load_object(o))

    def _on_card_double_click(self, oid, event):
        # Single-click already handles full navigation; just replay it.
        self._on_card_click(oid, event)

    def _on_checkbox_click(self, oid, event):
        self.main_window._toggle_reviewed_for_id(oid)
        self.selection_clear()
        self.selection_set(oid)
        return "break"

    def refresh_object_card(self, oid):
        """Live updates an object's card and/or Treeview row when fields (location, genus, species, etc.) change."""
        if not oid:
            return

        obs_dict = self.main_window._get_obs_dict() if hasattr(self.main_window, "_get_obs_dict") else {}
        reg_dict = self.main_window._get_reg_dict() if hasattr(self.main_window, "_get_reg_dict") else {}

        obs_row = obs_dict.get(oid) or {}
        reg_row = reg_dict.get(oid) or {}

        genus = str(reg_row.get("Genus", "") or "").strip()
        species = str(reg_row.get("Species", "") or "").strip()
        reviewed = bool(obs_row.get("Reviewed", False))
        rev_char = "☑" if reviewed else "☐"

        if oid in self.item_data:
            self.item_data[oid]["genus"] = genus
            self.item_data[oid]["species"] = species
            self.item_data[oid]["reviewed"] = reviewed
            self.item_data[oid]["values"] = [rev_char, oid, genus, species]

            parts = [str(oid)]
            if genus:
                parts.append(genus)
            if species:
                parts.append(species)
            self.item_data[oid]["title"] = " ".join(parts)

        oid_key = oid
        if getattr(self, "_oid_to_index", None):
            if oid_key not in self._oid_to_index and str(oid) in self._oid_to_index:
                oid_key = str(oid)
            elif oid_key not in self._oid_to_index and str(oid).isdigit() and int(oid) in self._oid_to_index:
                oid_key = int(oid)

        if getattr(self, "_oid_to_index", None) and oid_key in self._oid_to_index:
            idx = self._oid_to_index[oid_key]
            if idx in self._active_card_windows:
                win_id, widget_dict = self._active_card_windows[idx]
                self._populate_card_widget(widget_dict, oid)

        if hasattr(self, "tree") and self.tree.exists(oid):
            try:
                current_tags = self.tree.item(oid, "tags") or ()
                self.tree.item(oid, values=(rev_char, oid, genus, species), tags=current_tags)
            except Exception:
                pass

    def _update_card_checkbox(self, oid):
        if oid in self.item_data:
            reviewed = self.item_data[oid].get("reviewed", False)
            rev_char = "☑" if reviewed else "☐"
            cb_lbl = self.item_data[oid].get("cb_label")
            is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
            sec_text_color = "#6c757d" if not is_dark else "#a6adc8"
            cb_color = "#28a745" if reviewed else sec_text_color
            if cb_lbl and cb_lbl.winfo_exists():
                cb_lbl.configure(text=rev_char, fg=cb_color)

    def _refresh_card_accent(self, oid):
        if oid not in self.item_data:
            return
        accent_strip = self.item_data[oid].get("accent_strip")
        if not accent_strip or not accent_strip.winfo_exists():
            return

        is_dark = getattr(self.main_window, "dark_mode_active", False)
        canvas_bg = "#181c19" if is_dark else "#fbfaf8"

        if getattr(self.main_window, "_cached_reviewed_dict", None) is not None:
            reviewed = bool(self.main_window._cached_reviewed_dict.get(oid, self.item_data[oid].get("reviewed", False)))
        elif getattr(self.main_window, "_cached_obs_dict", None) is not None and oid in self.main_window._cached_obs_dict:
            reviewed = bool(self.main_window._cached_obs_dict[oid].get(REVIEWED_COLUMN, False))
        else:
            reviewed = self.item_data[oid].get("reviewed", False)
        self.item_data[oid]["reviewed"] = reviewed

        if hasattr(self.main_window, "_get_cached_problem"):
            has_problem = self.main_window._get_cached_problem(oid)
        else:
            has_problem = getattr(self.main_window, "_problem_cache", {}).get(oid, False)
        problems_have_history = self.main_window._problems_have_history(oid) if hasattr(self.main_window, "_problems_have_history") else False

        has_unknown = False
        if hasattr(self.main_window, "is_unknown"):
            reg_dict = self.main_window._get_reg_dict() if hasattr(self.main_window, "_get_reg_dict") else {}
            reg_row = reg_dict.get(oid) or {}
            for v in reg_row.values():
                if self.main_window.is_unknown(v):
                    has_unknown = True
                    break

        if reviewed and has_problem:
            new_color = "#ffb366" if is_dark else "#f0ad4e"
            badge_label, badge_bg, badge_fg = "REV+ERR", "#F57C00", "#ffffff"
        elif reviewed:
            new_color = "#4CAF50" if is_dark else "#2E7D32"
            badge_label, badge_bg, badge_fg = "OK",      "#2E7D32", "#ffffff"
        elif has_problem and problems_have_history:
            new_color = "#BB86FC" if is_dark else "#7B1FA2"
            badge_label, badge_bg, badge_fg = "ERR+HIS", "#7B1FA2", "#ffffff"
        elif has_problem:
            new_color = "#f28b82" if is_dark else "#C62828"
            badge_label, badge_bg, badge_fg = "ERR",     "#C62828", "#ffffff"
        elif problems_have_history:
            new_color = "#5ab0e8" if is_dark else "#0284C7"
            badge_label, badge_bg, badge_fg = "CFCT",    "#0284C7", "#ffffff"
        elif has_unknown:
            new_color = "#f59e0b" if is_dark else "#FBC02D"
            badge_label, badge_bg, badge_fg = "UKN",     "#FBC02D", "#2c302e"
        else:
            new_color = canvas_bg
            badge_label, badge_bg, badge_fg = "UNREV",   "#6c757d" if not is_dark else "#45475a", "#ffffff"

        accent_strip.configure(bg=new_color)
        self.item_data[oid]["accent_color_normal"] = new_color

        status_badge = self.item_data[oid].get("status_badge")
        if status_badge and status_badge.winfo_exists():
            status_badge.configure(text=badge_label, bg=badge_bg, fg=badge_fg, highlightbackground=badge_bg)

        self._apply_tags_to_card(oid)

        # Update Loaned badge dynamically
        obs_dict = getattr(self.main_window, "_cached_obs_dict", None)
        if obs_dict is None and hasattr(self.main_window, "_get_obs_dict"):
            obs_dict = self.main_window._get_obs_dict()
        obs_row = obs_dict.get(oid) if obs_dict else {}
        if obs_row is None:
            try:
                lookup_key = int(oid) if str(oid).isdigit() else oid
                obs_row = obs_dict.get(lookup_key, {})
            except Exception:
                obs_row = {}

        loaned_raw = obs_row.get("Loaned out", False)
        loaned = utils.parse_bool(loaned_raw)

        row1 = self.item_data[oid].get("row1")
        loaned_badge = self.item_data[oid].get("loaned_badge")

        if loaned and not loaned_badge and row1 and row1.winfo_exists():
            from config import sc
            l_bg = "#203040" if is_dark else "#e3f2fd"
            l_fg = "#64b5f6" if is_dark else "#0d47a1"
            l_bd = "#bbdefb" if is_dark else "#90caf9"

            l_badge = self._create_badge(row1, "Loaned", l_bg, l_fg, l_bd)
            l_badge.pack(side="right", padx=(sc(2), sc(2)))

            # Reapply tags to new child for hover effects
            tags = l_badge.bindtags()
            if "VirtualCard" not in tags:
                l_badge.bindtags((tags[0], "VirtualCard") + tags[1:])
            card_body = self.item_data[oid].get("card_body")
            l_badge._card_oid = oid
            l_badge._card_body = card_body

            self.item_data[oid]["loaned_badge"] = l_badge

        elif not loaned and loaned_badge:
            if loaned_badge.winfo_exists():
                loaned_badge.destroy()
            self.item_data[oid]["loaned_badge"] = None

        has_unval = self.main_window.has_unvalidated_sources(oid) if hasattr(self.main_window, "has_unvalidated_sources") else False
        unval_badge = self.item_data[oid].get("unval_badge")

        if has_unval and not unval_badge and row1 and row1.winfo_exists():
            from config import sc
            u_bg = "#3e2723" if is_dark else "#fff3e0"
            u_fg = "#ffb74d" if is_dark else "#e65100"
            u_bd = "#ffb74d" if is_dark else "#ffe0b2"

            u_badge = self._create_badge(row1, "UNVAL", u_bg, u_fg, u_bd)
            u_badge.pack(side="right", padx=(sc(2), sc(2)))

            tags = u_badge.bindtags()
            if "VirtualCard" not in tags:
                u_badge.bindtags((tags[0], "VirtualCard") + tags[1:])
            card_body = self.item_data[oid].get("card_body")
            u_badge._card_oid = oid
            u_badge._card_body = card_body

            self.item_data[oid]["unval_badge"] = u_badge

        elif not has_unval and unval_badge:
            if unval_badge.winfo_exists():
                unval_badge.destroy()
            self.item_data[oid]["unval_badge"] = None

    def _create_badge(self, parent, text, bg, fg, border_color):
        from config import sc
        badge = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=("Segoe UI", sc(8), "bold"),
            padx=sc(4),
            pady=sc(1),
            highlightthickness=1,
            highlightbackground=border_color,
            bd=0
        )
        badge.is_badge = True
        return badge




    def custom_yview(self, *args):
        res = self.original_yview(*args)
        self._schedule_viewport_update()
        return res

    def custom_yview_scroll(self, *args):
        res = self.canvas.tk.call(self.canvas._w, 'yview', 'scroll', *args)
        self._schedule_viewport_update()
        return res

    def custom_yview_moveto(self, *args):
        res = self.canvas.tk.call(self.canvas._w, 'yview', 'moveto', *args)
        self._schedule_viewport_update()
        return res

    def _measure_card_height(self):
        if not self.items_list:
            return

        # Instantiate a dummy card to measure it
        oid = self.items_list[0]
        # Make sure item data exists
        if oid not in self.item_data:
            self.item_data[oid] = {"tags": [], "values": ["☐", oid, "", ""], "title": "", "genus": "", "species": "", "reviewed": False}

        widget_dict = self._build_empty_card_widget(self.canvas)
        dummy_card = self._populate_card_widget(widget_dict, oid)
        # Update idletasks to ensure geometry is calculated
        self.update_idletasks()

        h = dummy_card.winfo_reqheight()
        # Default fallback if somehow reqheight fails
        self._card_height = h if h > 10 else 78

        dummy_card.destroy()
        if oid in self.item_data:
            for key in ["card_frame", "accent_strip", "card_body", "cb_label", "tax_label", "status_badge", "loaned_badge", "id_label", "row1"]:
                if key in self.item_data[oid]:
                    del self.item_data[oid][key]

    def _clear_virtual_cards(self):
        for win_id, widget_dict in list(self._active_card_windows.values()):
            try:
                self.canvas.coords(win_id, -9999, -9999) # move offscreen
                self._card_pool.append((win_id, widget_dict))
            except Exception:
                pass
        self._active_card_windows.clear()
        for oid in self.item_data:
            if "card_frame" in self.item_data[oid]:
                for key in ["card_frame", "accent_strip", "card_body", "cb_label", "tax_label", "status_badge", "loaned_badge", "id_label", "row1"]:
                    if key in self.item_data[oid]:
                        del self.item_data[oid][key]

    def _schedule_viewport_update(self):
        if self._pending_viewport_update:
            try:
                self.after_cancel(self._pending_viewport_update)
            except Exception:
                pass
        self._pending_viewport_update = self.after(10, self._update_visible_cards)

    def _update_visible_cards(self):
        self._pending_viewport_update = None
        if self.active_view != "detailed" or not self.winfo_exists():
            return

        if self._card_height is None:
            self._measure_card_height()

        if self._card_height is None:
            return # still None, list might be empty

        total_items = len(self.items_list)
        total_height = total_items * self._card_height

        canvas_width = getattr(self, "_last_canvas_width", self.canvas.winfo_width())
        self.canvas.configure(scrollregion=(0, 0, canvas_width, max(total_height, 1)))

        if total_items == 0:
            self._clear_virtual_cards()
            return

        canvas_height = self.canvas.winfo_height()
        if canvas_height <= 1:
            return # Canvas not fully realized yet

        y_top = self.canvas.canvasy(0)
        y_bottom = self.canvas.canvasy(canvas_height)

        start_idx = max(0, int(y_top // self._card_height) - 1)
        end_idx = min(total_items, int(y_bottom // self._card_height) + 2)

        visible_indices = set(range(start_idx, end_idx))
        current_indices = set(self._active_card_windows.keys())

        # Recycle cards scrolled out of view into the pool
        for idx in current_indices - visible_indices:
            win_id, widget_dict = self._active_card_windows.pop(idx)
            try:
                oid = self.items_list[idx]
                if oid in self.item_data and "card_frame" in self.item_data[oid]:
                    for key in ["card_frame", "accent_strip", "card_body", "cb_label", "tax_label", "status_badge", "loaned_badge", "id_label", "row1"]:
                        if key in self.item_data[oid]:
                            del self.item_data[oid][key]
            except IndexError:
                pass
            self.canvas.coords(win_id, -9999, -9999) # Move offscreen
            self._card_pool.append((win_id, widget_dict))

        # Create or reuse cards scrolled into view
        for idx in visible_indices - current_indices:
            oid = self.items_list[idx]

            if self._card_pool:
                win_id, widget_dict = self._card_pool.pop()
                card_frame = self._populate_card_widget(widget_dict, oid)
                y_pos = idx * self._card_height
                self.canvas.coords(win_id, 0, y_pos)
                self.canvas.itemconfig(win_id, window=card_frame, width=canvas_width)
            else:
                widget_dict = self._build_empty_card_widget(self.canvas)
                card_frame = self._populate_card_widget(widget_dict, oid)
                y_pos = idx * self._card_height
                win_id = self.canvas.create_window(0, y_pos, window=card_frame, anchor="nw", width=canvas_width)

            self._active_card_windows[idx] = (win_id, widget_dict)

            # Apply initial selection styling if selected
            self._apply_tags_to_card(oid)
            if oid in self.selected_iids:
                is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
                bg_selected = "#ffffff" if not is_dark else "#2d3149"
                accent_selected = "#3a7d44" if not is_dark else "#a6e3a1"
                card_body = self.item_data[oid].get("card_body")
                accent_strip = self.item_data[oid].get("accent_strip")
                if card_body and card_body.winfo_exists():
                    self._set_bg_recursive(card_body, bg_selected)
                if accent_strip and accent_strip.winfo_exists():
                    accent_strip.configure(bg=accent_selected)

    def _build_empty_card_widget(self, parent):
        from config import sc
        is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
        canvas_bg      = "#181c19" if is_dark else "#fbfaf8"
        card_bg        = "#24273a" if is_dark else "#f2f5f1"
        text_primary   = "#cad3f5" if is_dark else "#2c302e"
        text_secondary = "#a5adcb" if is_dark else "#4c4546"
        family_color   = "#a6e3a1" if is_dark else "#3a7d44"

        outer_frame = tk.Frame(parent, bg=canvas_bg, bd=0, highlightthickness=0, cursor="hand2")
        outer_frame.pack(fill="x", pady=sc(1))

        accent_strip = tk.Frame(outer_frame, bg=canvas_bg, width=sc(4), bd=0, highlightthickness=0)
        accent_strip.pack(side="left", fill="y")
        accent_strip.pack_propagate(False)
        accent_strip.is_accent_strip = True

        card_body = tk.Frame(outer_frame, bg=card_bg, bd=0, highlightthickness=0,
                             padx=sc(8), pady=sc(6), cursor="hand2")
        card_body.pack(side="left", fill="both", expand=True)

        row1 = tk.Frame(card_body, bg=card_bg)
        row1.pack(fill="x", anchor="w")

        cb_lbl = tk.Label(row1, text="☐", bg=card_bg, fg=text_secondary,
                          font=("Segoe UI", sc(10), "bold"), cursor="hand2")
        cb_lbl.pack(side="left", padx=(0, sc(4)))

        tax_lbl = tk.Label(row1, text="", bg=card_bg, fg=text_primary,
                           font=("Georgia", sc(9), "italic bold"), anchor="w")
        tax_lbl.pack(side="left", fill="x", expand=True, padx=(0, sc(4)))

        status_badge = self._create_badge(row1, "UKN", "#FBC02D", "#2c302e", "#FBC02D")
        status_badge.pack(side="right", padx=(sc(2), 0))

        loaned_badge = self._create_badge(row1, "Loaned", "#203040" if is_dark else "#e3f2fd", "#64b5f6" if is_dark else "#0d47a1", "#bbdefb" if is_dark else "#90caf9")
        loaned_badge.pack(side="right", padx=(sc(2), sc(2)))
        loaned_badge.pack_forget() # Initially hidden

        row2 = tk.Frame(card_body, bg=card_bg)
        row2.pack(fill="x", anchor="w", pady=(sc(3), 0))

        fam_lbl = tk.Label(row2, text="", bg=card_bg, fg=family_color,
                           font=("Segoe UI", sc(8), "bold"), anchor="w")
        fam_lbl.pack(side="left", padx=(sc(18), 0))
        fam_lbl.pack_forget()

        sep_lbl = tk.Label(row2, text="•", bg=card_bg, fg=text_secondary,
                           font=("Segoe UI", sc(8)))
        sep_lbl.pack(side="left", padx=sc(3))
        sep_lbl.pack_forget()

        id_lbl = tk.Label(row2, text="", bg=card_bg, fg=text_primary,
                          font=("Consolas", sc(8)))
        id_lbl.pack(side="left", padx=(sc(18), 0))

        photo_lbl = tk.Label(row2, text="📷 0", bg=card_bg, fg=text_secondary,
                             font=("Segoe UI", sc(8)))
        photo_lbl.pack(side="right", padx=(sc(4), 0))

        row3 = tk.Frame(card_body, bg=card_bg)
        row3.pack(fill="x", anchor="w", pady=(sc(2), 0))

        loc_lbl = tk.Label(row3, text="", bg=card_bg, fg=text_secondary,
                           font=("Segoe UI", sc(8)), anchor="w", justify="left")
        loc_lbl.pack(side="left", padx=(sc(18), 0), fill="x", expand=True)

        cb_lbl.is_cb_lbl = True
        def _add_virtual_tag(w):
            if getattr(w, "is_cb_lbl", False):
                return
            tags = w.bindtags()
            if "VirtualCard" not in tags:
                w.bindtags((tags[0], "VirtualCard") + tags[1:])
            for c in w.winfo_children():
                _add_virtual_tag(c)

        _add_virtual_tag(outer_frame)

        return {
            "outer_frame": outer_frame,
            "accent_strip": accent_strip,
            "card_body": card_body,
            "row1": row1,
            "cb_lbl": cb_lbl,
            "tax_lbl": tax_lbl,
            "status_badge": status_badge,
            "loaned_badge": loaned_badge,
            "row2": row2,
            "fam_lbl": fam_lbl,
            "sep_lbl": sep_lbl,
            "id_lbl": id_lbl,
            "photo_lbl": photo_lbl,
            "row3": row3,
            "loc_lbl": loc_lbl
        }

    def _populate_card_widget(self, widgets, oid):
        from config import sc
        import utils
        is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
        canvas_bg      = "#181c19" if is_dark else "#fbfaf8"
        card_bg        = "#24273a" if is_dark else "#f2f5f1"
        text_secondary = "#a5adcb" if is_dark else "#4c4546"

        obs_dict = self.main_window._get_obs_dict() if hasattr(self.main_window, "_get_obs_dict") else {}
        reg_dict = self.main_window._get_reg_dict() if hasattr(self.main_window, "_get_reg_dict") else {}

        obs_row = obs_dict.get(oid)
        if obs_row is None:
            try:
                lookup_key = int(oid) if str(oid).isdigit() else oid
                obs_row = obs_dict.get(lookup_key, {})
            except Exception:
                obs_row = {}

        reg_row = reg_dict.get(oid)
        if reg_row is None:
            try:
                lookup_key = int(oid) if str(oid).isdigit() else oid
                reg_row = reg_dict.get(lookup_key, {})
            except Exception:
                reg_row = {}

        if oid not in self.item_data:
            self.item_data[oid] = {}
        data = self.item_data[oid]

        data["card_frame"] = widgets["outer_frame"]
        data["accent_strip"] = widgets["accent_strip"]
        data["card_body"] = widgets["card_body"]
        data["cb_label"] = widgets["cb_lbl"]
        data["tax_label"] = widgets["tax_lbl"]
        data["status_badge"] = widgets["status_badge"]
        data["loaned_badge"] = widgets["loaned_badge"]
        data["id_label"] = widgets["id_lbl"]
        data["row1"] = widgets["row1"]

        has_problem = self.main_window._get_cached_problem(oid) if hasattr(self.main_window, "_get_cached_problem") else (self.main_window._problem_cache.get(oid, False) if hasattr(self.main_window, "_problem_cache") else False)
        problems_have_history = self.main_window._problems_have_history(oid) if hasattr(self.main_window, "_problems_have_history") else False
        
        if getattr(self.main_window, "_cached_reviewed_dict", None) is not None:
            reviewed = bool(self.main_window._cached_reviewed_dict.get(oid, data.get("reviewed", False)))
        elif getattr(self.main_window, "_cached_obs_dict", None) is not None and oid in self.main_window._cached_obs_dict:
            reviewed = bool(self.main_window._cached_obs_dict[oid].get(REVIEWED_COLUMN, False))
        else:
            reviewed = bool(obs_row.get(REVIEWED_COLUMN, data.get("reviewed", False)))
        data["reviewed"] = reviewed

        loaned_raw = obs_row.get("Loaned out", False)
        loaned = utils.parse_bool(loaned_raw)

        has_unknown = False
        if hasattr(self.main_window, "is_unknown"):
            for v in reg_row.values():
                if self.main_window.is_unknown(v):
                    has_unknown = True
                    break

        if reviewed and has_problem:
            accent_color = "#ffb366" if is_dark else "#f0ad4e"
            badge_label, badge_bg, badge_fg = "REV+ERR", "#F57C00", "#ffffff"
        elif reviewed:
            accent_color = "#4CAF50" if is_dark else "#2E7D32"  # green
            badge_label, badge_bg, badge_fg = "OK",      "#2E7D32", "#ffffff"
        elif has_problem and problems_have_history:
            accent_color = "#BB86FC" if is_dark else "#7B1FA2"  # purple
            badge_label, badge_bg, badge_fg = "ERR+HIS", "#7B1FA2", "#ffffff"
        elif has_problem:
            accent_color = "#f28b82" if is_dark else "#C62828"  # red
            badge_label, badge_bg, badge_fg = "ERR",     "#C62828", "#ffffff"
        elif problems_have_history:
            accent_color = "#5ab0e8" if is_dark else "#0284C7"  # blue
            badge_label, badge_bg, badge_fg = "CFCT",    "#0284C7", "#ffffff"
        elif has_unknown:
            accent_color = "#f59e0b" if is_dark else "#FBC02D"
            badge_label, badge_bg, badge_fg = "UKN",     "#FBC02D", "#2c302e"
        else:
            accent_color = canvas_bg  # visually transparent
            badge_label, badge_bg, badge_fg = "UNREV",   "#6c757d" if not is_dark else "#45475a", "#ffffff"

        widgets["outer_frame"].configure(bg=canvas_bg)
        widgets["card_body"].configure(bg=card_bg)
        widgets["row1"].configure(bg=card_bg)
        widgets["row2"].configure(bg=card_bg)
        widgets["row3"].configure(bg=card_bg)
        widgets["cb_lbl"].configure(bg=card_bg)
        widgets["tax_lbl"].configure(bg=card_bg)
        widgets["fam_lbl"].configure(bg=card_bg)
        widgets["sep_lbl"].configure(bg=card_bg)
        widgets["id_lbl"].configure(bg=card_bg)
        widgets["photo_lbl"].configure(bg=card_bg)
        widgets["loc_lbl"].configure(bg=card_bg)
        widgets["accent_strip"].configure(bg=accent_color)
        data["accent_color_normal"] = accent_color

        rev_char = "☑" if reviewed else "☐"
        cb_color = "#28a745" if reviewed else text_secondary
        widgets["cb_lbl"].configure(text=rev_char, fg=cb_color)
        # Clear previous bindings to avoid buildup if recycled
        widgets["cb_lbl"].unbind("<Button-1>")
        widgets["cb_lbl"].bind("<Button-1>", lambda e, o=oid: self._on_checkbox_click(o, e))

        genus   = str(reg_row.get("Genus",   "") or "").strip()
        species = str(reg_row.get("Species", "") or "").strip()
        tax_text = f"{genus} {species}".strip() or "Unknown Specimen"
        widgets["tax_lbl"].configure(text=tax_text)

        badge_frame = widgets["status_badge"]
        badge_frame.configure(text=badge_label, bg=badge_bg, fg=badge_fg, highlightbackground=badge_bg)

        if loaned:
            if widgets["loaned_badge"].winfo_manager() != 'pack':
                widgets["loaned_badge"].pack(side="right", padx=(sc(2), sc(2)))
        else:
            if widgets["loaned_badge"].winfo_manager() == 'pack':
                widgets["loaned_badge"].pack_forget()

        family = str(reg_row.get("Family", "") or "").strip()
        if family in ("nan", "None"):
            family = ""

        if family:
            widgets["fam_lbl"].configure(text=family.upper())
            if widgets["fam_lbl"].winfo_manager() != 'pack':
                widgets["fam_lbl"].pack(before=widgets["id_lbl"], side="left", padx=(sc(18), 0))
                widgets["sep_lbl"].pack(before=widgets["id_lbl"], side="left", padx=sc(3))
                widgets["id_lbl"].pack_configure(padx=(0, 0))
        else:
            if widgets["fam_lbl"].winfo_manager() == 'pack':
                widgets["fam_lbl"].pack_forget()
                widgets["sep_lbl"].pack_forget()
                widgets["id_lbl"].pack_configure(padx=(sc(18), 0))

        widgets["id_lbl"].configure(text=oid)

        photo_count = 0
        if self.main_window.app.df_photo is not None:
            if not hasattr(self.main_window, "_cached_photo_counts") or self.main_window._cached_photo_counts is None:
                photo_df = self.main_window.app.df_photo
                if photo_df is not None and not photo_df.empty:
                    self.main_window._cached_photo_counts = photo_df.index.value_counts().to_dict()
                else:
                    self.main_window._cached_photo_counts = {}
            photo_count = self.main_window._cached_photo_counts.get(oid)
            if photo_count is None:
                try:
                    lookup_key = int(oid) if str(oid).isdigit() else oid
                    photo_count = self.main_window._cached_photo_counts.get(lookup_key, 0)
                except Exception:
                    photo_count = 0
        if hasattr(self.main_window, "image_index"):
            paths = self.main_window.image_index.get(oid)
            if paths is None:
                try:
                    lookup_key = int(oid) if str(oid).isdigit() else oid
                    paths = self.main_window.image_index.get(lookup_key, [])
                except Exception:
                    paths = []
            photo_count = max(photo_count, len(paths or []))

        widgets["photo_lbl"].configure(text=f"📷 {photo_count}")

        def _clean(v):
            s = str(v).strip()
            return "" if s in ("nan", "None", "") else s

        building  = _clean(obs_row.get("Building",  ""))
        floor     = _clean(obs_row.get("Floor",     ""))
        extra     = _clean(obs_row.get("Extra",     ""))
        stored_as = _clean(obs_row.get("Stored as", ""))
        cabinet   = _clean(obs_row.get("Cabinet",   ""))

        loc_parts = []
        if building: loc_parts.append(building)
        fr = ", ".join(filter(None, [f"Floor {floor}" if floor else "", extra]))
        if fr: loc_parts.append(fr)
        st = " / ".join(filter(None, [stored_as, f"Cab {cabinet}" if cabinet else ""]))
        if st: loc_parts.append(st)
        loc_text = " \u2022 ".join(loc_parts) if loc_parts else "No location info"

        widgets["loc_lbl"].configure(text=loc_text)

        self._bind_card_events(widgets["outer_frame"], widgets["card_body"], oid)
        return widgets["outer_frame"]

    def _setup_virtual_card_bindtag(self):
        """Attach hover, click, and context-menu bindings via a single static bindtag."""
        card_tag = "VirtualCard"

        def _get_target(event):
            w = event.widget
            oid = getattr(w, "_card_oid", None)
            card_body = getattr(w, "_card_body", None)
            return w, oid, card_body

        def _on_enter(event):
            w, oid, card_body = _get_target(event)
            if oid is None or card_body is None:
                return
            is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
            hover_bg = "#30354f" if is_dark else "#e9ece5"
            if oid not in self.selected_iids:
                self._set_bg_recursive(card_body, hover_bg)

        def _on_leave(event):
            w, oid, card_body = _get_target(event)
            if oid is None or card_body is None:
                return
            is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
            card_bg = "#24273a" if is_dark else "#f2f5f1"
            if oid not in self.selected_iids:
                self._set_bg_recursive(card_body, card_bg)

        def _on_card_click(event):
            _, oid, _ = _get_target(event)
            if oid is not None:
                self._on_card_click(oid, event)

        def _on_card_double_click(event):
            _, oid, _ = _get_target(event)
            if oid is not None:
                self._on_card_double_click(oid, event)

        def _on_card_right_click(event):
            _, oid, _ = _get_target(event)
            if oid is not None:
                self._on_card_click(oid, event)
                if hasattr(self.main_window, "_show_context_menu"):
                    self.main_window._show_context_menu(event)

        self.bind_class(card_tag, "<Enter>",           _on_enter)
        self.bind_class(card_tag, "<Leave>",           _on_leave)
        self.bind_class(card_tag, "<Button-1>",        _on_card_click)
        self.bind_class(card_tag, "<Double-Button-1>", _on_card_double_click)
        self.bind_class(card_tag, "<Button-3>",        _on_card_right_click)

        self.bind_class(card_tag, "<MouseWheel>", self._on_mousewheel)
        self.bind_class(card_tag, "<Button-4>", self._on_mousewheel)
        self.bind_class(card_tag, "<Button-5>", self._on_mousewheel)

        _skip = {"<Button-1>", "<Button-2>", "<Button-3>",
                 "<Button-4>", "<Button-5>",
                 "<Double-Button-1>", "<Double-Button-2>", "<Double-Button-3>",
                 "<Control-Button-1>", "<Control-Button-3>",
                 "<MouseWheel>"}
        for seq, func, add in self.custom_bindings:
            if "Select" in seq or seq.startswith("<<"):
                continue
            if seq in _skip or "Button" in seq:
                continue
            self.bind_class(card_tag, seq, lambda e: func(e))

    def _bind_card_events(self, widget, card_body, oid):
        """Assign item context to widget tree so static VirtualCard bindtag works without leaking events."""
        def _attach_card_context(w):
            w._card_oid = oid
            w._card_body = card_body
            for c in w.winfo_children():
                _attach_card_context(c)

        _attach_card_context(widget)

    def _apply_tags_to_card(self, oid):
        if oid in self.item_data:
            tags = self.item_data[oid].get("tags", [])
            card = self.item_data[oid].get("card_frame")
            if not card or not card.winfo_exists():
                return

            fg_color = None
            for t in tags:
                if t.startswith("color_"):
                    fg_color = "#" + t.split("_")[1]
                    break

            is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
            default_color = "#000000" if not is_dark else "#cad3f5"
            target_color = fg_color if fg_color else default_color

            tax_lbl = self.item_data[oid].get("tax_label")
            id_lbl = self.item_data[oid].get("id_label")
            if tax_lbl and tax_lbl.winfo_exists():
                tax_lbl.configure(fg=target_color)
            if id_lbl and id_lbl.winfo_exists():
                id_lbl.configure(fg=target_color)

    def curselection(self):
        res = []
        for oid in self.selected_iids:
            idx = self._oid_to_index.get(oid)
            if idx is not None:
                res.append(idx)
        return res

    def selection_clear(self, first=0, last=None):
        self.selected_iids.clear()
        self.tree.selection_remove(*self.tree.selection())
        self._sync_view_selections()

    def selection_set(self, *args):
        if not args:
            return
        arg = args[0]
        if isinstance(arg, (int, float)):
            idx = int(arg)
            if 0 <= idx < len(self.items_list):
                self.selected_iids = [self.items_list[idx]]
        else:
            if len(args) == 1 and isinstance(args[0], (list, tuple)):
                self.selected_iids = [str(x) for x in args[0]]
            else:
                self.selected_iids = [str(x) for x in args]

        self._sync_view_selections()
        if self.selected_iids:
            self.see(self.selected_iids[0])

    def see(self, index_or_iid):
        if not self.items_list:
            return

        idx = -1
        if isinstance(index_or_iid, (int, float)):
            idx = int(index_or_iid)
            if 0 <= idx < len(self.items_list):
                oid = self.items_list[idx]
            else:
                return
        else:
            oid = str(index_or_iid)
            idx = self._oid_to_index.get(oid, -1)

        if self.active_view == "compact":
            if oid in self._oid_to_index:
                self.tree.see(oid)
        else:
            if idx >= 0 and self._card_height:
                y_target = idx * self._card_height
                canvas_h = self.canvas.winfo_height()
                total_items = len(self.items_list)
                total_height = max(1, total_items * self._card_height)

                # Center the item vertically
                target_offset = max(0, y_target - (canvas_h / 2) + (self._card_height / 2))
                target_fraction = target_offset / total_height

                # Clamp fraction between 0.0 and 1.0
                target_fraction = max(0.0, min(1.0, target_fraction))
                self.canvas.yview_moveto(target_fraction)
                # Ensure viewport updates immediately so card is rendered
                self._update_visible_cards()



    def activate(self, index_or_iid):
        self.see(index_or_iid)
        if isinstance(index_or_iid, (int, float)):
            idx = int(index_or_iid)
            if 0 <= idx < len(self.items_list):
                self.focused_iid = self.items_list[idx]
        else:
            self.focused_iid = str(index_or_iid)

    def delete(self, first=0, last=None):
        self.items_list.clear()
        self.items_set.clear()
        self._oid_to_index.clear()
        self.selected_iids.clear()
        self.focused_iid = None
        self._tree_dirty = False
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)

        self._clear_virtual_cards()
        self.item_data.clear()
        self._schedule_viewport_update()

    def insert(self, index, title, genus=None, species=None, reviewed=None, color=None, bulk=False):
        oid = title.split(" ")[0].strip()
        if not bulk:
            if oid in self.items_set:
                try:
                    self.items_list.remove(oid)
                except ValueError:
                    pass
            else:
                self.items_set.add(oid)
        else:
            self.items_set.add(oid)

        idx = len(self.items_list)
        self.items_list.append(oid)
        self._oid_to_index[oid] = idx

        rev_char = "☑" if reviewed else "☐"
        row_tags = ["even" if idx % 2 == 0 else "odd"]
        
        if color:
            tag_name = f"color_{color.replace('#', '')}"
            if tag_name not in self._configured_tags:
                self.tree.tag_configure(tag_name, foreground=color)
                self._tag_configs[tag_name] = {"foreground": color}
                self._configured_tags.add(tag_name)
            row_tags.append(tag_name)

        if self.active_view == "compact":
            if not bulk and self.tree.exists(oid):
                try:
                    self.tree.delete(oid)
                except Exception:
                    pass
            self.tree.insert("", "end", iid=oid, values=(rev_char, oid, genus or "", species or ""), tags=tuple(row_tags))
        else:
            self._tree_dirty = True

        self.item_data[oid] = {
            "title": title,
            "genus": genus or "",
            "species": species or "",
            "reviewed": bool(reviewed),
            "tags": row_tags,
            "values": [rev_char, oid, genus or "", species or ""]
        }

        if self.active_view == "detailed" and not bulk:
            self._schedule_viewport_update()

    def itemconfig(self, index, **kwargs):
        foreground = kwargs.get("foreground")
        if not foreground:
            return

        tag_name = f"color_{foreground.replace('#', '')}"
        self.tag_configure(tag_name, foreground=foreground)

        if isinstance(index, (int, float)):
            idx = int(index)
            if 0 <= idx < len(self.items_list):
                oid = self.items_list[idx]
                current_tags = list(self.item(oid, "tags") or [])
                if tag_name not in current_tags:
                    current_tags.append(tag_name)
                    self.item(oid, tags=current_tags)
        else:
            # "end" or similar
            if self.items_list:
                oid = self.items_list[-1]
                current_tags = list(self.item(oid, "tags") or [])
                if tag_name not in current_tags:
                    current_tags.append(tag_name)
                    self.item(oid, tags=current_tags)

    def xview_moveto(self, fraction):
        pass

    def bind(self, sequence, func, add=None):
        if sequence == "<<ListboxSelect>>":
            sequence = "<<TreeviewSelect>>"
        bind_id = super().bind(sequence, func, add)
        self.custom_bindings.append((sequence, func, add))
        self.tree.bind(sequence, func, add)
        return bind_id

    def focus(self, item=None):
        if item is None:
            if self.active_view == "compact":
                self._ensure_tree_synced()
                return self.tree.focus()
            else:
                return self.focused_iid or ""
        else:
            oid = str(item)
            if self.active_view == "compact":
                self._ensure_tree_synced()
                self.tree.focus(oid)
            else:
                self.focused_iid = oid

    def item(self, item, option=None, **kwargs):
        oid = str(item)
        if self.active_view == "compact" and not getattr(self, "_tree_dirty", False):
            return self.tree.item(oid, option, **kwargs)

        if oid not in self.item_data:
            self.item_data[oid] = {"tags": [], "values": [], "title": "", "genus": "", "species": "", "reviewed": False}

        if option == "tags":
            return self.item_data[oid].get("tags", [])
        if option == "values":
            return self.item_data[oid].get("values", [])

        if "tags" in kwargs:
            self.item_data[oid]["tags"] = kwargs["tags"]
            self._apply_tags_to_card(oid)
        if "values" in kwargs:
            self.item_data[oid]["values"] = kwargs["values"]
            vals = kwargs["values"]
            if vals:
                self.item_data[oid]["reviewed"] = (vals[0] == "☑")
                self._update_card_checkbox(oid)
                self._refresh_card_accent(oid)

        if self.active_view == "compact" and getattr(self, "_tree_dirty", False):
            self._ensure_tree_synced()
            return self.tree.item(oid, option, **kwargs)

        if option is None and not kwargs:
            reviewed = self.item_data[oid].get("reviewed", False)
            rev_char = "☑" if reviewed else "☐"
            genus = self.item_data[oid].get("genus", "")
            species = self.item_data[oid].get("species", "")
            return {
                "tags": self.item_data[oid].get("tags", []),
                "values": [rev_char, oid, genus, species]
            }

    def identify_row(self, y):
        if self.active_view == "compact":
            return self.tree.identify_row(y)
        else:
            if not self._card_height or not self.items_list:
                return ""
            canvas_y = self.canvas.canvasy(y)
            idx = int(canvas_y // self._card_height)
            if 0 <= idx < len(self.items_list):
                return self.items_list[idx]
            if self.selected_iids:
                return self.selected_iids[0]
            return ""

    def selection(self):
        if self.active_view == "compact":
            return self.tree.selection()
        else:
            return tuple(self.selected_iids)

    def tag_configure(self, tagname, **kwargs):
        self.tree.tag_configure(tagname, **kwargs)
        if not hasattr(self, "_tag_configs"):
            self._tag_configs = {}
        self._tag_configs[tagname] = kwargs
        for oid in self.items_list:
            if tagname in self.item_data.get(oid, {}).get("tags", []):
                self._apply_tags_to_card(oid)

    def yview(self, *args):
        if self.active_view == "compact":
            return self.tree.yview(*args)
        else:
            return self.canvas.yview(*args)

    def configure(self, **kwargs):
        if "yscrollcommand" in kwargs:
            yscroll = kwargs["yscrollcommand"]
            self._external_yscrollcommand = yscroll
            self.tree.configure(yscrollcommand=yscroll)
            self.canvas.configure(yscrollcommand=self._on_canvas_scroll)
            del kwargs["yscrollcommand"]
        if kwargs:
            super().configure(**kwargs)

    def yview_scroll(self, number, what):
        if self.active_view == "compact":
            self.tree.yview_scroll(number, what)
        else:
            self.canvas.yview_scroll(number, what)

    def get_children(self, item=None):
        if item is not None:
            return ()
        return tuple(self.items_list)

    def focus_set(self):
        if self.active_view == "compact":
            self.tree.focus_set()
        else:
            self.canvas.focus_set()

    def destroy(self):
        if hasattr(self, "_resize_job") and self._resize_job:
            try:
                self.canvas.after_cancel(self._resize_job)
            except Exception:
                pass
        if hasattr(self, "_card_build_job") and self._card_build_job:
            try:
                self.canvas.after_cancel(self._card_build_job)
            except Exception:
                pass
        if self._trace_id and self.focus_mode_var:
            try:
                self.focus_mode_var.trace_remove("write", self._trace_id)
            except Exception:
                pass
        super().destroy()


class ArborTextField(tk.Frame):
    """
    A reusable text field component that manages its own style, variables, and focus lines.
    """
    def __init__(self, parent, variable=None, label_text="", colors=None, readonly=False, multiline=False, **kwargs):
        if colors is None:
            raise ValueError("colors dictionary must be provided to ArborTextField")
        self.colors = colors

        if "bg" not in kwargs:
            kwargs["bg"] = colors["surface"]

        super().__init__(parent, **kwargs)

        self.variable = variable if variable else tk.StringVar()
        self.readonly = readonly
        self.multiline = multiline

        from config import sc
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # Label
        if label_text:
            self.lbl = tk.Label(
                self, text=label_text.upper(),
                font=("JetBrains Mono", sc(9), "bold"),
                bg=self.colors["surface"], fg=self.colors["text_muted"],
                anchor="w"
            )
            self.lbl.grid(row=0, column=0, sticky="ew", pady=(0, sc(2)))

        # Container for the input widget
        self.input_container = tk.Frame(self, bg=self.colors["surface"])
        self.input_container.grid(row=1, column=0, sticky="nsew")
        self.input_container.columnconfigure(0, weight=1)
        self.input_container.rowconfigure(0, weight=1)

        # Input widget
        if self.multiline:
            self.text_widget = tk.Text(
                self.input_container,
                font=("Inter", sc(10)),
                bg=self.colors["surface"], fg=self.colors["text"],
                insertbackground=self.colors["text"],
                relief="flat", height=3
            )
            self.text_widget.grid(row=0, column=0, sticky="nsew", padx=sc(2), pady=sc(2))

            # Sync Text widget with string var
            if self.variable.get():
                self.text_widget.insert("1.0", self.variable.get())

            self.text_widget.bind("<KeyRelease>", self._sync_text_to_var)
            self._trace_id = self.variable.trace_add("write", self._sync_var_to_text)

            if self.readonly:
                self.text_widget.configure(state="disabled")

            self.entry = self.text_widget # alias for common access

        else:
            self.entry = tk.Entry(
                self.input_container,
                textvariable=self.variable,
                font=("Inter", sc(10)),
                bg=self.colors["surface"], fg=self.colors["text"],
                insertbackground=self.colors["text"],
                relief="flat"
            )
            self.entry.grid(row=0, column=0, sticky="ew", padx=sc(2), pady=sc(2))

            if self.readonly:
                self.entry.configure(state="readonly", readonlybackground=self.colors["surface"])

        # Focus line
        self.focus_line = tk.Frame(self, bg=self.colors["border"], height=sc(2))
        self.focus_line.grid(row=2, column=0, sticky="ew", pady=(sc(2), 0))

        # Bind focus events for the line color
        if not self.readonly:
            self.entry.bind("<FocusIn>", self._on_focus_in, add="+")
            self.entry.bind("<FocusOut>", self._on_focus_out, add="+")

        self.bind("<Destroy>", self._on_destroy, add="+")

    def _sync_text_to_var(self, event=None):
        if self.multiline and not self.readonly:
            # Need to disable trace temporarily to avoid infinite loop
            if hasattr(self, "_trace_id"):
                self.variable.trace_remove("write", self._trace_id)
            self.variable.set(self.text_widget.get("1.0", "end-1c"))
            self._trace_id = self.variable.trace_add("write", self._sync_var_to_text)

    def _sync_var_to_text(self, *args):
        if self.multiline and self.winfo_exists():
            current_text = self.text_widget.get("1.0", "end-1c")
            new_text = self.variable.get() or ""
            if current_text == new_text:
                return
            state = self.text_widget.cget("state")
            if state == "disabled":
                self.text_widget.configure(state="normal")
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", new_text)
            if state == "disabled":
                self.text_widget.configure(state="disabled")

    def _on_focus_in(self, event=None):
        if self.winfo_exists():
            self.focus_line.configure(bg=self.colors["focus_line"])

    def _on_focus_out(self, event=None):
        if self.winfo_exists():
            self.focus_line.configure(bg=self.colors["border"])

    def _on_destroy(self, event):
        if str(event.widget) == str(self):
            if hasattr(self, "_trace_id") and self._trace_id:
                try:
                    self.variable.trace_remove("write", self._trace_id)
                except Exception:
                    pass

class ArborDropdown(tk.Frame):
    """
    A reusable dropdown component that manages its own style and variables.
    """
    def __init__(self, parent, variable=None, label_text="", choices=None, colors=None, **kwargs):
        if colors is None:
            raise ValueError("colors dictionary must be provided to ArborDropdown")
        self.colors = colors
        self.choices = choices or []

        if "bg" not in kwargs:
            kwargs["bg"] = colors["surface"]

        super().__init__(parent, **kwargs)

        self.variable = variable if variable else tk.StringVar()

        from config import sc
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # Label
        if label_text:
            self.lbl = tk.Label(
                self, text=label_text.upper(),
                font=("JetBrains Mono", sc(9), "bold"),
                bg=self.colors["surface"], fg=self.colors["text_muted"],
                anchor="w"
            )
            self.lbl.grid(row=0, column=0, sticky="ew", pady=(0, sc(2)))

        # Dropdown
        style_name = f"Arbor.{parent.winfo_id()}.TCombobox"
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            style_name,
            fieldbackground=self.colors["surface"],
            background=self.colors["surface"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["surface"],
            darkcolor=self.colors["surface"],
            arrowcolor=self.colors["text"]
        )

        self.cb = ttk.Combobox(
            self,
            textvariable=self.variable,
            values=self.choices,
            font=("Inter", sc(10)),
            style=style_name
        )
        self.cb.grid(row=1, column=0, sticky="ew")

class SchemaFormBuilder:
    """
    A builder class to dynamically generate form layouts based on configuration dictionaries.
    Supports grouped forms, multi-column grids, custom row layouts, and varied field types
    (text, choices/dropdowns, readonly, multiline).
    """
    def __init__(self, parent_frame, colors, group_defs=None):
        self.parent = parent_frame
        self.colors = colors
        self.group_defs = group_defs or []

    def _create_field_widget(self, parent, field_name, fdef, var, bg_color=None):
        from config import sc
        bg = bg_color or self.colors.get("surface", self.parent.cget("bg"))
        ftype = fdef.get("type", "text") if isinstance(fdef, dict) else "text"

        if ftype == "choice":
            choices = fdef.get("choices", []) if isinstance(fdef, dict) else []
            widget = ArborDropdown(
                parent,
                variable=var,
                label_text=field_name,
                choices=choices,
                colors=self.colors,
                bg=bg
            )
        else:
            readonly = fdef.get("readonly", False) if isinstance(fdef, dict) else False
            multiline = fdef.get("multiline", False) if isinstance(fdef, dict) else False
            widget = ArborTextField(
                parent,
                variable=var,
                label_text=field_name,
                colors=self.colors,
                readonly=readonly,
                multiline=multiline,
                bg=bg
            )
        return widget

    def build_grid(self, field_defs, variables_dict, columns=1, layout_rows=None, custom_widgets=None):
        """
        Builds fields in a grid layout.
        - field_defs: list of dicts (or dict mapping name -> fdef)
        - variables_dict: dict mapping field_name -> tk.StringVar
        - columns: number of equal-width columns (if layout_rows is not given)
        - layout_rows: list of lists specifying field names in each row, e.g.
                       [['Stored as', 'Building', 'Floor'], ['Cabinet', 'Extra', 'Loan status']]
        - custom_widgets: dict mapping field_name/placeholder -> callable(parent) or prebuilt widget
        Returns dict of created field widgets.
        """
        from config import sc
        widgets = {}
        custom_widgets = custom_widgets or {}

        # Normalize field_defs to dict name -> def
        if isinstance(field_defs, list):
            fdef_map = {f["name"] if isinstance(f, dict) else str(f): (f if isinstance(f, dict) else {"name": str(f)}) for f in field_defs}
        elif isinstance(field_defs, dict):
            fdef_map = field_defs
        else:
            fdef_map = {}

        if layout_rows:
            # Layout specified by exact row lists
            for r_idx, row_fields in enumerate(layout_rows):
                num_cols = max(len(row_fields), 1)
                for c_idx in range(num_cols):
                    self.parent.columnconfigure(c_idx, weight=1, uniform=f"grid_col_{r_idx}")

                for c_idx, fname in enumerate(row_fields):
                    if fname in custom_widgets:
                        custom_item = custom_widgets[fname]
                        if callable(custom_item):
                            cw = custom_item(self.parent)
                        else:
                            cw = custom_item
                        cw.grid(row=r_idx, column=c_idx, sticky="nsew", padx=sc(4), pady=sc(3))
                        widgets[fname] = cw
                        continue

                    fdef = fdef_map.get(fname, {"name": fname})
                    if fname not in variables_dict:
                        variables_dict[fname] = tk.StringVar(value="")

                    w = self._create_field_widget(self.parent, fname, fdef, variables_dict[fname], bg_color=self.parent.cget("bg"))
                    w.grid(row=r_idx, column=c_idx, sticky="nsew", padx=sc(4), pady=sc(3))
                    widgets[fname] = w
        else:
            # Layout by columns
            field_list = list(fdef_map.keys())
            num_cols = max(columns, 1)
            for c_idx in range(num_cols):
                self.parent.columnconfigure(c_idx, weight=1, uniform="grid_col")

            for idx, fname in enumerate(field_list):
                r_idx = idx // num_cols if num_cols > 1 else idx
                c_idx = idx % num_cols if num_cols > 1 else 0

                if fname in custom_widgets:
                    custom_item = custom_widgets[fname]
                    if callable(custom_item):
                        cw = custom_item(self.parent)
                    else:
                        cw = custom_item
                    cw.grid(row=r_idx, column=c_idx, sticky="nsew", padx=sc(4), pady=sc(3))
                    widgets[fname] = cw
                    continue

                fdef = fdef_map.get(fname, {"name": fname})
                if fname not in variables_dict:
                    variables_dict[fname] = tk.StringVar(value="")

                w = self._create_field_widget(self.parent, fname, fdef, variables_dict[fname], bg_color=self.parent.cget("bg"))
                w.grid(row=r_idx, column=c_idx, sticky="nsew", padx=sc(4), pady=sc(3))
                widgets[fname] = w

    def build_stack(self, field_defs, variables_dict, pady=3):
        """
        Builds fields in a vertical stack using pack().
        """
        from config import sc
        widgets = {}
        if isinstance(field_defs, list):
            fdef_map = {f["name"] if isinstance(f, dict) else str(f): (f if isinstance(f, dict) else {"name": str(f)}) for f in field_defs}
        elif isinstance(field_defs, dict):
            fdef_map = field_defs
        else:
            fdef_map = {}

        for fname, fdef in fdef_map.items():
            if fname not in variables_dict:
                variables_dict[fname] = tk.StringVar(value="")
            w = self._create_field_widget(self.parent, fname, fdef, variables_dict[fname], bg_color=self.parent.cget("bg"))
            w.pack(fill="x", pady=sc(pady))
            widgets[fname] = w
        return widgets

    def build(self, variables_dict):
        """
        Builds the form widgets based on group_defs.
        variables_dict should be a dictionary mapping field names to tk.StringVar objects.
        Returns a dictionary of created widgets mapped by field name.
        """
        from config import sc
        widgets = {}
        for row_idx, group in enumerate(self.group_defs):
            group_name = group.get("name", "")
            fields = group.get("fields", [])

            # Group Container
            group_frame = tk.Frame(self.parent, bg=self.colors.get("bg", self.parent.cget("bg")))
            group_frame.pack(fill="x", pady=(0, sc(16)))

            # Group Header
            if group_name:
                lbl = tk.Label(
                    group_frame, text=group_name.upper(),
                    font=("JetBrains Mono", sc(10), "bold"),
                    bg=self.colors.get("bg", self.parent.cget("bg")),
                    fg=self.colors.get("text_muted", "#444748"),
                    anchor="w"
                )
                lbl.pack(fill="x", pady=(0, sc(4)))

            # Content grid
            content_frame = tk.Frame(group_frame, bg=self.colors.get("bg", self.parent.cget("bg")))
            content_frame.pack(fill="x")

            # For each field, place it in a grid column
            num_cols = max(len(fields), 1)
            for i in range(num_cols):
                content_frame.columnconfigure(i, weight=1, uniform="col")

            for col_idx, field_item in enumerate(fields):
                if isinstance(field_item, dict):
                    field_name = field_item.get("name", "")
                    fdef = field_item
                else:
                    field_name = str(field_item)
                    fdef = {"name": field_name}

                if field_name not in variables_dict:
                    variables_dict[field_name] = tk.StringVar(value="")

                field_widget = self._create_field_widget(
                    content_frame,
                    field_name,
                    fdef,
                    variables_dict[field_name],
                    bg_color=self.colors.get("bg", self.parent.cget("bg"))
                )
                field_widget.grid(row=0, column=col_idx, sticky="ew", padx=sc(4))
                widgets[field_name] = field_widget

        return widgets

