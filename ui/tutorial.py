import tkinter as tk
import json
import os
import sys

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
            self.on_complete = None
            self.pending_main_tutorial = False

    def load_tutorials(self):
        try:
            from utils import get_resource_path, debug_error
            tut_path = get_resource_path("tutorials.json")
        except Exception:
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
                except Exception:
                    pass
                self.tutorials = {}
        else:
            self.tutorials = {}


    def start_tutorial(self, tutorial_name, root, on_complete=None):
        import tkinter.messagebox as mb

        # Check if tutorials are disabled globally
        import config
        prefs = config.load_prefs()
        disable_tutorials_pref = prefs.get("disable_tutorials", False)
        enable_tutorials_config = getattr(config, "ENABLE_TUTORIALS", True)

        # Check command line args
        no_tutorial_arg = "--no-tutorial" in sys.argv

        if disable_tutorials_pref or not enable_tutorials_config or no_tutorial_arg:
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
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None
        if self.highlight:
            try:
                self.highlight.destroy()
            except Exception:
                pass
            self.highlight = None

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
                except Exception:
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
                self.highlight = TutorialHighlight(self.active_root, target_widget)
            except Exception:
                self.highlight = None
            
        try:
            self.popup = TutorialPopup(
                self.active_root,
                title=step.get("title", ""),
                text=step.get("text", ""),
                target_widget=target_widget,
                placement=step.get("placement", "center"),
                is_first=(self.current_step_idx == 0),
                is_last=(self.current_step_idx == len(steps) - 1),
                manager=self
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
        except Exception:
            pass
        return None

class TutorialHighlight:
    """Creates a glowing animated border around a target widget."""
    def __init__(self, parent, target_widget):
        self.target_widget = target_widget
        self.win = tk.Toplevel(parent)
        if parent:
            try:
                self.win.transient(parent)
            except Exception:
                pass
        self.win.overrideredirect(True)
        
        # Windows transparent color trick
        try:
            self.win.attributes("-transparentcolor", "black")
        except Exception:
            pass
        self.win.config(bg="black")

        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.rect = self.canvas.create_rectangle(0, 0, 10, 10, outline="#00c8ff", width=4)
        
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

            pad = 4
            if self.win.winfo_exists():
                self.win.deiconify()
                self.win.geometry(f"{w + pad*2}x{h + pad*2}+{x - pad}+{y - pad}")
                self.canvas.coords(self.rect, pad, pad, w + pad, h + pad)
        except Exception:
            try:
                if self.win.winfo_exists():
                    self.win.withdraw()
            except Exception:
                pass

    def animate(self):
        if not self.win.winfo_exists():
            return
        # Simple animation: change color slightly or width
        colors = ["#00c8ff", "#0088ff", "#0044ff", "#0088ff"]
        current = getattr(self, "_anim_idx", 0)
        try:
            self.canvas.itemconfig(self.rect, outline=colors[current])
        except Exception:
            pass
        self._anim_idx = (current + 1) % len(colors)
        
        self.update_position()
        try:
            self.win.after(200, self.animate)
        except Exception:
            pass

    def destroy(self):
        if self.win.winfo_exists():
            try:
                self.win.destroy()
            except Exception:
                pass

class TutorialPopup:
    """The tutorial message box."""
    def __init__(self, parent, title, text, target_widget, placement, is_first, is_last, manager):
        self.manager = manager
        self.target_widget = target_widget
        self.placement = placement
        self.parent_widget = parent
        self.bind_id = None

        self.win = tk.Toplevel(parent)
        if parent:
            try:
                self.win.transient(parent)
            except Exception:
                pass
        self.win.overrideredirect(True)
        self.win.config(bg="#333333")

        # Inner frame for border
        self.frame = tk.Frame(self.win, bg="#ffffff", highlightthickness=1, highlightbackground="#00c8ff")
        self.frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Title
        lbl_title = tk.Label(self.frame, text=title, font=("Segoe UI", 12, "bold"), bg="#ffffff", fg="#333333")
        lbl_title.pack(anchor="w", padx=15, pady=(15, 5))

        # Text
        lbl_text = tk.Label(self.frame, text=text, font=("Segoe UI", 10), bg="#ffffff", fg="#555555", justify="left")
        lbl_text.pack(anchor="w", padx=15, pady=(0, 15))

        # Buttons frame
        btn_frame = tk.Frame(self.frame, bg="#ffffff")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        if not is_first:
            btn_back = tk.Button(btn_frame, text="Back", command=self.manager.prev_step, relief="flat", bg="#e0e0e0", cursor="hand2")
            btn_back.pack(side="left")

        btn_next_text = "Finish" if is_last else "Next"
        btn_next = tk.Button(btn_frame, text=btn_next_text, command=self.manager.next_step, relief="flat", bg="#00c8ff", fg="white", cursor="hand2", font=("Segoe UI", 9, "bold"))
        btn_next.pack(side="right", padx=(10, 0))

        btn_close = tk.Button(btn_frame, text="Close", command=self.manager.close_tutorial, relief="flat", bg="#ffffff", fg="#888888", cursor="hand2")
        btn_close.pack(side="right")

        # Skip check
        if is_first:
            self.skip_var = tk.BooleanVar()
            chk_skip = tk.Checkbutton(self.frame, text="Don't show this again", variable=self.skip_var, bg="#ffffff", activebackground="#ffffff", selectcolor="#ffffff", command=self.save_skip_pref, cursor="hand2")
            chk_skip.pack(anchor="w", padx=15, pady=(0, 10))

        self.win.update_idletasks()
        self.position_popup()
        
        # Ensure it stays with parent, but guard to only process parent window's config events
        if parent:
            try:
                self.bind_id = parent.bind("<Configure>", lambda e, p=parent: self.position_popup(e, p), add="+")
            except Exception:
                pass

    def save_skip_pref(self):
        import config
        try:
            prefs = config.load_prefs()
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
        except Exception:
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
                except Exception:
                    pass

            if target_coords_found:
                # Optional padding
                pad = 10

                if self.placement == "top":
                    x = tx + (tw // 2) - (w // 2)
                    y = ty - h - pad
                elif self.placement == "bottom":
                    x = tx + (tw // 2) - (w // 2)
                    y = ty + th + pad
                elif self.placement == "left":
                    x = tx - w - pad
                    y = ty + (th // 2) - (h // 2)
                elif self.placement == "right":
                    x = tx + tw + pad
                    y = ty + (th // 2) - (h // 2)
                else:
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
                    except Exception:
                        pass

                if not centered_on_parent:
                    x = self.win.winfo_screenwidth() // 2 - w // 2
                    y = self.win.winfo_screenheight() // 2 - h // 2

            # Screen constraint checks (10px screen margin)
            screen_w = self.win.winfo_screenwidth()
            screen_h = self.win.winfo_screenheight()
            x = max(10, min(x, screen_w - w - 10))
            y = max(10, min(y, screen_h - h - 10))

            self.win.geometry(f"{w}x{h}+{x}+{y}")
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except Exception:
            pass

    def destroy(self):
        try:
            if self.bind_id and self.parent_widget:
                try:
                    if self.parent_widget.winfo_exists():
                        self.parent_widget.unbind("<Configure>", self.bind_id)
                except Exception:
                    pass
            if self.win.winfo_exists():
                try:
                    self.win.destroy()
                except Exception:
                    pass
        except Exception:
            pass
