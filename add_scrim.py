import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

scrim_class = """
class TutorialScrim:
    \"\"\"A semi-transparent dark overlay consisting of 4 windows that frame a hole over the target widget.\"\"\"
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
                except Exception:
                    pass
            self.windows.append(win)

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

        except Exception:
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
        for win in self.windows:
            try:
                if win.winfo_exists():
                    win.destroy()
            except Exception:
                pass
        self.windows = []
"""

if "class TutorialScrim:" not in content:
    # Insert it right before TutorialHighlight
    content = content.replace("class TutorialHighlight:", scrim_class + "\nclass TutorialHighlight:")

# Now we need to update TutorialManager to use the scrim
manager_init = """            self.active_root = None
            self.popup = None
            self.highlight = None
            self.scrim = None
            self.on_complete = None"""

if "self.scrim = None" not in content:
    content = re.sub(r'self\.active_root = None\n\s*self\.popup = None\n\s*self\.highlight = None\n\s*self\.on_complete = None', manager_init, content)

cleanup_func = """    def _cleanup(self):
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
        if self.scrim:
            try:
                self.scrim.destroy()
            except Exception:
                pass
            self.scrim = None"""

content = re.sub(r'def _cleanup\(self\):.*?self\.highlight = None', cleanup_func, content, flags=re.DOTALL)

show_step_func = """        if target_widget:
            try:
                self.scrim = TutorialScrim(self.active_root, target_widget)
                self.highlight = TutorialHighlight(self.active_root, target_widget)
            except Exception:
                self.scrim = None
                self.highlight = None
        else:
            try:
                self.scrim = TutorialScrim(self.active_root, None)
            except Exception:
                self.scrim = None"""

content = re.sub(r'if target_widget:\n\s*try:\n\s*self\.highlight = TutorialHighlight\(self\.active_root, target_widget\)\n\s*except Exception:\n\s*self\.highlight = None', show_step_func, content)


with open('ui/tutorial.py', 'w') as f:
    f.write(content)
