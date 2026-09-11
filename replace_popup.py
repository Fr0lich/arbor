import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# We need to replace TutorialPopup entirely. Let's do a search and replace for it.
import re

popup_pattern = re.compile(r'class TutorialPopup:.*?def destroy\(self\):.*?(?:\n\s*(?:try|if|except).*)*\n\s*pass\n', re.DOTALL)
if not popup_pattern.search(content):
    print("Could not find TutorialPopup class block to replace")

popup_code = """class TutorialPopup:
    \"\"\"The tutorial message box.\"\"\"
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
            except Exception:
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
            except Exception:
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
                sub_parts = re.split(r'(\*[^\*]+\*)', part)
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

            self.win.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
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
"""

content = popup_pattern.sub(popup_code, content)
with open('ui/tutorial.py', 'w') as f:
    f.write(content)
