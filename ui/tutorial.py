import tkinter as tk
import json
import os
import sys
from config import sc
import config


COLORS = {
    "bg": "#ffffff",
    "surface": "#fbfaf8",
    "surface_dim": "#dadada",
    "border": "#c4c7c7",
    "primary": "#000000",
    "secondary": "#3a7d44",
    "text": "#2c302e",
    "text_muted": "#444748",
    "highlight": "#d9480f",
}

COLORS_DARK = {
    "bg": "#181c19",
    "surface": "#24273a",
    "surface_dim": "#1e2030",
    "border": "#363a4f",
    "primary": "#cad3f5",
    "secondary": "#8bd5ca",
    "text": "#cad3f5",
    "text_muted": "#a5adcb",
    "highlight": "#f5a97f",
}


class TutorialManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TutorialManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.tutorials = {}
            self.load_tutorials()
            self.current_tutorial = None
            self.current_step_idx = 0
            self.active_root = None
            self.popup = None
            self.highlight = None
            self.scrim = None
            self.on_complete = None
            self.trigger_bind_id = None
            self.trigger_widget = None
            self.pending_main_tutorial = False

    def load_tutorials(self):
        try:
            from utils import get_resource_path, debug_error
            tut_path = get_resource_path("tutorials.json")
        except (Exception, tk.TclError):
            if getattr(sys, 'frozen', False):
                base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            tut_path = os.path.join(base_dir, "tutorials.json")
            
        if os.path.exists(tut_path):
            try:
                with open(tut_path, "r", encoding="utf-8") as f:
                    self.tutorials = json.load(f)
            except Exception as e:
                try:
                    from utils import debug_error
                    debug_error("Tutorial Load Error", f"Could not parse {tut_path}: {e}")
                except (Exception, tk.TclError):
                    pass
                self.tutorials = {}
        else:
            self.tutorials = {}


    def start_tutorial(self, tutorial_name, root, on_complete=None, force=False):
        import tkinter.messagebox as mb

        # Check if tutorials are disabled globally
        import config
        prefs = config.load_prefs()
        disable_tutorials_pref = prefs.get("disable_tutorials", False)
        enable_tutorials_config = getattr(config, "ENABLE_TUTORIALS", True)

        # Check command line args
        no_tutorial_arg = "--no-tutorial" in sys.argv

        if (disable_tutorials_pref or not enable_tutorials_config or no_tutorial_arg) and not force:
            return

        if not root or not root.winfo_exists():
            return
            
        if tutorial_name not in self.tutorials:
            mb.showerror("Tutorial Error", f"Tutorial {tutorial_name} not found. Loaded: {list(self.tutorials.keys())}")
            return

        self.current_tutorial = tutorial_name
        self.current_step_idx = 0
        self.active_root = root
        self.on_complete = on_complete
        
        self.show_step()

    def set_active_root(self, root):
        self.active_root = root
        
    def continue_pending_tutorial(self, root):
        if self.pending_main_tutorial:
            self.pending_main_tutorial = False
            # Short delay to allow window to render
            if root and root.winfo_exists():
                root.after(1000, lambda: self.start_tutorial("main_tutorial", root))

    def close_tutorial(self):
        self._cleanup()
        self.current_tutorial = None

    def _cleanup(self):
        if self.trigger_bind_id and self.trigger_widget:
            try:
                if self.trigger_widget.winfo_exists():
                    self.trigger_widget.unbind(self._trigger_event, self.trigger_bind_id)
            except (Exception, tk.TclError):
                pass
        self.trigger_bind_id = None
        self.trigger_widget = None
        self._trigger_event = None
        if self.popup:
            try:
                self.popup.destroy()
            except (Exception, tk.TclError):
                pass
            self.popup = None
        if self.highlight:
            try:
                self.highlight.destroy()
            except (Exception, tk.TclError):
                pass
            self.highlight = None
        if self.scrim:
            try:
                self.scrim.destroy()
            except (Exception, tk.TclError):
                pass
            self.scrim = None

    def next_step(self):
        if not self.current_tutorial: return
        steps = self.tutorials[self.current_tutorial]
        if self.current_step_idx < len(steps) - 1:
            self.current_step_idx += 1
            self.show_step()
        else:
            # Reached the end
            if self.current_tutorial == "startup_tutorial":
                # Mark that we should start main_tutorial next
                self.pending_main_tutorial = True
            self.close_tutorial()
            if self.on_complete:
                try:
                    self.on_complete()
                except (Exception, tk.TclError):
                    pass

    def prev_step(self):
        if not self.current_tutorial: return
        if self.current_step_idx > 0:
            self.current_step_idx -= 1
            self.show_step()

    def show_step(self):
        self._cleanup()
        if not self.current_tutorial or not self.active_root or not self.active_root.winfo_exists():
            return

        steps = self.tutorials[self.current_tutorial]
        step = steps[self.current_step_idx]

        target_widget = None
        if step.get("target"):
            target_widget = self._find_widget(self.active_root, step["target"])

        if step.get("target") and not target_widget:
            print(f"Target {step['target']} not found for step {step['id']}")
            
        if target_widget:
            try:
                self.scrim = TutorialScrim(self.active_root, target_widget)
                self.highlight = TutorialHighlight(self.active_root, target_widget)
            except (Exception, tk.TclError):
                self.scrim = None
                self.highlight = None
        else:
            try:
                self.scrim = TutorialScrim(self.active_root, None)
            except (Exception, tk.TclError):
                self.scrim = None
            
        if target_widget and step.get("wait_event"):
            try:
                self._trigger_event = step["wait_event"]
                # We use next_step directly, but wrapped to prevent bubbling issues
                self.trigger_bind_id = target_widget.bind(self._trigger_event, lambda e: self.active_root.after(10, self.next_step), add="+")
                self.trigger_widget = target_widget
            except (Exception, tk.TclError):
                pass

        try:
            self.popup = TutorialPopup(
                self.active_root,
                title=step.get("title", ""),
                text=step.get("text", ""),
                target_widget=target_widget,
                placement=step.get("placement", "center"),
                is_first=(self.current_step_idx == 0),
                is_last=(self.current_step_idx == len(steps) - 1),
                manager=self,
                total_steps=len(steps)
            )
        except Exception as e:
            import tkinter.messagebox as mb
            mb.showerror("Tutorial Error", f"Error creating TutorialPopup: {e}")

    def _find_widget(self, root, target_id):
        try:
            if not root or not root.winfo_exists():
                return None
            if getattr(root, "tutorial_id", None) == target_id:
                return root
            # Iterate over all children
            for child in root.winfo_children():
                res = self._find_widget(child, target_id)
                if res:
                    return res
        except (Exception, tk.TclError):
            pass
        return None


class TutorialScrim:
    """A semi-transparent dark overlay consisting of 4 windows that frame a hole over the target widget."""
    def __init__(self, parent, target_widget=None):
        self.parent = parent
        self.target = target_widget
        self.windows = []

        # 4 windows to frame the hole: top, bottom, left, right
        for i in range(4):
            win = tk.Toplevel(parent)
            win.attributes("-alpha", 0.5)
            win.config(bg="black")
            win.overrideredirect(True)
            if parent:
                try:
                    win.transient(parent)
                except (Exception, tk.TclError):
                    pass
            self.windows.append(win)

        self.bind_id = None
        if parent:
            try:
                self.bind_id = parent.bind("<Configure>", lambda e: self.update_position(), add="+")
            except (Exception, tk.TclError):
                pass

        self.update_position()

    def update_position(self):
        try:
            if not self.parent or not self.parent.winfo_exists():
                return

            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()

            # If no target or target invisible, cover the whole parent
            if not self.target or not self.target.winfo_exists() or not self.target.winfo_viewable():
                self._place(self.windows[0], px, py, pw, ph)
                self._hide(self.windows[1])
                self._hide(self.windows[2])
                self._hide(self.windows[3])
                return

            tx = self.target.winfo_rootx()
            ty = self.target.winfo_rooty()
            tw = self.target.winfo_width()
            th = self.target.winfo_height()

            pad = sc(4)
            hx = tx - pad
            hy = ty - pad
            hw = tw + pad * 2
            hh = th + pad * 2

            # Clamp hole to parent bounds
            hx = max(px, min(hx, px + pw))
            hy = max(py, min(hy, py + ph))
            hx2 = max(px, min(hx + hw, px + pw))
            hy2 = max(py, min(hy + hh, py + ph))

            # Top rect
            self._place(self.windows[0], px, py, pw, max(0, hy - py))
            # Bottom rect
            self._place(self.windows[1], px, hy2, pw, max(0, py + ph - hy2))
            # Left rect
            self._place(self.windows[2], px, hy, max(0, hx - px), hy2 - hy)
            # Right rect
            self._place(self.windows[3], hx2, hy, max(0, px + pw - hx2), hy2 - hy)

        except (Exception, tk.TclError):
            pass

    def _place(self, win, x, y, w, h):
        if w > 0 and h > 0:
            win.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
            if not win.winfo_viewable():
                win.deiconify()
            win.lift()
        else:
            self._hide(win)

    def _hide(self, win):
        if win.winfo_viewable():
            win.withdraw()

    def destroy(self):
        if self.bind_id and self.parent:
            try:
                if self.parent.winfo_exists():
                    self.parent.unbind("<Configure>", self.bind_id)
            except (Exception, tk.TclError):
                pass
        for win in self.windows:
            try:
                if win.winfo_exists():
                    win.destroy()
            except (Exception, tk.TclError):
                pass
        self.windows = []

class TutorialHighlight:
    """Creates a glowing animated border around a target widget."""
    def __init__(self, parent, target_widget):
        self.target_widget = target_widget
        self.win = tk.Toplevel(parent)

        prefs = config.load_prefs()
        is_dark = prefs.get("appearance", "light") == "dark"
        self.c = COLORS_DARK if is_dark else COLORS
        if parent:
            try:
                self.win.transient(parent)
            except (Exception, tk.TclError):
                pass
        self.win.overrideredirect(True)
        
        # Windows transparent color trick
        try:
            self.win.attributes("-transparentcolor", "black")
        except (Exception, tk.TclError):
            pass
        self.win.config(bg="black")

        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.rect = self.canvas.create_rectangle(0, 0, sc(10), sc(10), outline=self.c["highlight"], width=sc(4))
        
        self.win.deiconify()
        self.win.lift()
        self.update_position()
        self.animate()

    def update_position(self):
        try:
            if not self.target_widget or not self.target_widget.winfo_exists() or not self.target_widget.winfo_viewable():
                if self.win.winfo_exists():
                    self.win.withdraw()
                return

            x = self.target_widget.winfo_rootx()
            y = self.target_widget.winfo_rooty()
            w = self.target_widget.winfo_width()
            h = self.target_widget.winfo_height()

            pad = sc(4)
            if self.win.winfo_exists():
                self.win.deiconify()
                self.win.geometry(f"{w + pad*2}x{h + pad*2}+{x - pad}+{y - pad}")
                self.canvas.coords(self.rect, pad, pad, w + pad, h + pad)
        except (Exception, tk.TclError):
            try:
                if self.win.winfo_exists():
                    self.win.withdraw()
            except (Exception, tk.TclError):
                pass

    def animate(self):
        if not self.win.winfo_exists():
            return

        import time
        import math

        try:
            # Sine wave based breathing (0.0 to 1.0)
            t = time.time()
            pulse = (math.sin(t * 3.0) + 1) / 2.0  # Speed factor 3.0

            # Smoothly pulse width between 2 and 6
            new_width = sc(2) + (sc(4) * pulse)
            self.canvas.itemconfig(self.rect, width=new_width)

        except (Exception, tk.TclError):
            pass

        self.update_position()
        try:
            self.win.after(50, self.animate) # Faster tick for smooth animation
        except (Exception, tk.TclError):
            pass

    def destroy(self):
        if self.win.winfo_exists():
            try:
                self.win.destroy()
            except (Exception, tk.TclError):
                pass

class TutorialPopup:
    """The tutorial message box."""
    def __init__(self, parent, title, text, target_widget, placement, is_first, is_last, manager, total_steps=0):
        self.manager = manager
        self.target_widget = target_widget
        self.placement = placement
        self.parent_widget = parent
        self.bind_id = None

        prefs = config.load_prefs()
        is_dark = prefs.get("appearance", "light") == "dark"
        self.c = COLORS_DARK if is_dark else COLORS

        self.win = tk.Toplevel(parent)
        if parent:
            try:
                self.win.transient(parent)
            except (Exception, tk.TclError):
                pass
        self.win.overrideredirect(True)
        self.win.config(bg=self.c["border"])

        # Inner frame for border
        self.frame = tk.Frame(self.win, bg=self.c["surface"], highlightthickness=sc(1), highlightbackground=self.c["highlight"])
        self.frame.pack(fill="both", expand=True, padx=sc(2), pady=sc(2))

        font_title = ("Segoe UI", sc(12), "bold")
        font_text = ("Segoe UI", sc(10))
        font_text_bold = ("Segoe UI", sc(10), "bold")
        font_text_italic = ("Segoe UI", sc(10), "italic")
        font_btn = ("Segoe UI", sc(9), "bold")
        font_progress = ("Segoe UI", sc(8), "bold")

        # Title
        lbl_title = tk.Label(self.frame, text=title, font=font_title, bg=self.c["surface"], fg=self.c["primary"])
        lbl_title.pack(anchor="w", padx=sc(15), pady=(sc(15), sc(5)))

        # Text - using Rich Text tk.Text
        self.text_widget = tk.Text(self.frame, font=font_text, bg=self.c["surface"], fg=self.c["text_muted"],
                                   wrap="word", height=4, width=40, bd=0, highlightthickness=0,
                                   insertbackground=self.c["surface"])
        self.text_widget.pack(anchor="w", padx=sc(15), pady=(0, sc(15)), fill="both", expand=True)

        self.text_widget.tag_configure("bold", font=font_text_bold)
        self.text_widget.tag_configure("italic", font=font_text_italic)

        self._insert_rich_text(text)
        self.text_widget.config(state="disabled")

        # Progress Indicator and Buttons frame
        bottom_frame = tk.Frame(self.frame, bg=self.c["surface"])
        bottom_frame.pack(fill="x", padx=sc(15), pady=(0, sc(15)))

        # Progress indicator
        step_text = f"Step {self.manager.current_step_idx + 1} of {total_steps}"
        lbl_progress = tk.Label(bottom_frame, text=step_text, font=font_progress, bg=self.c["surface"], fg=self.c["text_muted"])
        lbl_progress.pack(side="left", pady=sc(5))

        btn_frame = tk.Frame(bottom_frame, bg=self.c["surface"])
        btn_frame.pack(side="right")

        if not is_first:
            btn_back = tk.Button(btn_frame, text="Back", command=self.prev_step, relief="flat",
                                 bg=self.c["surface_dim"], fg=self.c["text"], cursor="hand2", font=font_btn, padx=sc(8), pady=sc(4))
            btn_back.pack(side="left", padx=(0, sc(10)))

        btn_next_text = "Finish" if is_last else "Next"
        btn_next = tk.Button(btn_frame, text=btn_next_text, command=self.next_step, relief="flat",
                             bg=self.c["highlight"], fg="#ffffff", cursor="hand2", font=font_btn, padx=sc(8), pady=sc(4))
        btn_next.pack(side="right")

        btn_close = tk.Button(btn_frame, text="Close", command=self.close, relief="flat",
                              bg=self.c["surface"], fg=self.c["text_muted"], cursor="hand2", font=font_btn, padx=sc(8), pady=sc(4))
        btn_close.pack(side="right", padx=(0, sc(10)))

        # Skip check
        if is_first:
            self.skip_var = tk.BooleanVar()
            chk_skip = tk.Checkbutton(self.frame, text="Don't show this, or other tutorial popups again",
                                      variable=self.skip_var, bg=self.c["surface"], fg=self.c["text_muted"],
                                      activebackground=self.c["surface"], selectcolor=self.c["surface_dim"],
                                      command=self.save_skip_pref, cursor="hand2", font=font_text)
            chk_skip.pack(anchor="w", padx=sc(15), pady=(0, sc(10)))

        # Keyboard accessibility
        self.win.bind("<Right>", lambda e: self.next_step())
        self.win.bind("<Left>", lambda e: self.prev_step() if not is_first else None)
        self.win.bind("<Escape>", lambda e: self.close())

        self.win.update_idletasks()

        # Adjust text widget height dynamically based on content
        num_lines = int(self.text_widget.index('end-1c').split('.')[0])
        self.text_widget.config(height=min(10, max(2, num_lines)))

        self.win.update_idletasks()
        self.position_popup()
        
        # Ensure it stays with parent, but guard to only process parent window's config events
        if parent:
            try:
                self.bind_id = parent.bind("<Configure>", lambda e, p=parent: self.position_popup(e, p), add="+")
            except (Exception, tk.TclError):
                pass

    def _insert_rich_text(self, text):
        import re

        # We need to split by both **bold** and *italic*
        # Use regex to find tokens.
        # A simple approach: replace with placeholders or parse sequentially.

        # Split by **...** first
        parts = re.split(r'(\*\*.*?\*\*)', text)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                self.text_widget.insert("end", part[2:-2], "bold")
            else:
                # Now split by *...*
                sub_parts = re.split(r'(\*[^*]+\*)', part)
                for sub_part in sub_parts:
                    if sub_part.startswith('*') and sub_part.endswith('*'):
                        self.text_widget.insert("end", sub_part[1:-1], "italic")
                    else:
                        self.text_widget.insert("end", sub_part)

    def prev_step(self):
        try:
            self.manager.prev_step()
        except Exception as e:
            pass

    def save_skip_pref(self):
        import config
        try:
            prefs = config.load_prefs()
            if self.skip_var.get():
                prefs["disable_tutorials"] = True
            else:
                prefs["disable_tutorials"] = False

            completed = prefs.get("completed_tutorials", [])
            if self.skip_var.get():
                if self.manager.current_tutorial not in completed:
                    completed.append(self.manager.current_tutorial)
            else:
                if self.manager.current_tutorial in completed:
                    completed.remove(self.manager.current_tutorial)
            prefs["completed_tutorials"] = completed

            # Also maintain legacy flag for startup_tutorial if needed
            if self.manager.current_tutorial == "startup_tutorial":
                prefs["tutorial_skipped"] = self.skip_var.get()

            config.save_prefs(prefs)
        except (Exception, tk.TclError):
            pass

    def close(self):
        try:
            self.manager.end_tutorial()
        except Exception as e:
            import tkinter.messagebox as mb
            mb.showerror("Tutorial Error", f"Error closing tutorial: {e}")

    def next_step(self):
        try:
            self.manager.next_step()
        except Exception as e:
            import tkinter.messagebox as mb
            mb.showerror("Tutorial Error", f"Error in next step: {e}")

    def position_popup(self, event=None, parent_widget=None):
        try:
            if not self.win.winfo_exists():
                return

            # Avoid processing configure events propagated from child widgets.
            # Only process configurations of the parent window itself.
            if event and parent_widget and event.widget != parent_widget:
                return

            w = self.win.winfo_reqwidth()
            h = self.win.winfo_reqheight()

            target_coords_found = False
            if self.target_widget and self.target_widget.winfo_exists() and self.placement != "center":
                try:
                    if self.target_widget.winfo_viewable():
                        tx = self.target_widget.winfo_rootx()
                        ty = self.target_widget.winfo_rooty()
                        tw = self.target_widget.winfo_width()
                        th = self.target_widget.winfo_height()
                        target_coords_found = True
                except (Exception, tk.TclError):
                    pass

            if target_coords_found:
                # Optional padding
                pad = sc(10)

                placement = self.placement

                if placement == "top":
                    x = tx + (tw // 2) - (w // 2)
                    y = ty - h - pad
                    if y < 10:
                        placement = "bottom"
                        y = ty + th + pad
                elif placement == "bottom":
                    x = tx + (tw // 2) - (w // 2)
                    y = ty + th + pad
                    screen_h = self.win.winfo_screenheight()
                    if y + h > screen_h - 10:
                        placement = "top"
                        y = ty - h - pad
                elif placement == "left":
                    x = tx - w - pad
                    y = ty + (th // 2) - (h // 2)
                    if x < 10:
                        placement = "right"
                        x = tx + tw + pad
                elif placement == "right":
                    x = tx + tw + pad
                    y = ty + (th // 2) - (h // 2)
                    screen_w = self.win.winfo_screenwidth()
                    if x + w > screen_w - 10:
                        placement = "left"
                        x = tx - w - pad

                # Re-calculate in case placement changed and wasn't handled properly above,
                # but the above handles basic auto-flip.
                if placement not in ["top", "bottom", "left", "right"]:
                    x = tx
                    y = ty
            else:
                # Center on parent if possible, otherwise center on screen
                centered_on_parent = False
                if parent_widget and parent_widget.winfo_exists():
                    try:
                        if parent_widget.winfo_viewable():
                            px = parent_widget.winfo_rootx()
                            py = parent_widget.winfo_rooty()
                            pw = parent_widget.winfo_width()
                            ph = parent_widget.winfo_height()
                            x = px + (pw // 2) - (w // 2)
                            y = py + (ph // 2) - (h // 2)
                            centered_on_parent = True
                    except (Exception, tk.TclError):
                        pass

                if not centered_on_parent:
                    x = self.win.winfo_screenwidth() // 2 - w // 2
                    y = self.win.winfo_screenheight() // 2 - h // 2

            # Screen constraint checks (10px screen margin)
            screen_w = self.win.winfo_screenwidth()
            screen_h = self.win.winfo_screenheight()
            x = max(10, min(x, screen_w - w - 10))
            y = max(10, min(y, screen_h - h - 10))

            self.win.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except (Exception, tk.TclError):
            pass

    def destroy(self):
        try:
            if self.bind_id and self.parent_widget:
                try:
                    if self.parent_widget.winfo_exists():
                        self.parent_widget.unbind("<Configure>", self.bind_id)
                except (Exception, tk.TclError):
                    pass
            if self.win.winfo_exists():
                try:
                    self.win.destroy()
                except (Exception, tk.TclError):
                    pass
        except (Exception, tk.TclError):
            pass
