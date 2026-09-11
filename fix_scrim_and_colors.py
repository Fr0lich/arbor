import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# Fix color in TutorialHighlight
content = content.replace('outline="#00c8ff"', 'outline=self.c["highlight"]')

# We need to add c dictionary to TutorialHighlight as well
highlight_init = """    def __init__(self, parent, target_widget):
        self.target_widget = target_widget
        self.win = tk.Toplevel(parent)

        prefs = config.load_prefs()
        is_dark = prefs.get("appearance", "light") == "dark"
        self.c = COLORS_DARK if is_dark else COLORS"""
content = re.sub(r'    def __init__\(self, parent, target_widget\):\n\s*self\.target_widget = target_widget\n\s*self\.win = tk\.Toplevel\(parent\)', highlight_init, content)

# Fix TutorialScrim updating on window resize
# We can just bind to parent configure event if it's not None
scrim_init = """            self.windows.append(win)

        self.bind_id = None
        if parent:
            try:
                self.bind_id = parent.bind("<Configure>", lambda e: self.update_position(), add="+")
            except (Exception, tk.TclError):
                pass

        self.update_position()"""
content = content.replace("            self.windows.append(win)\n            \n        self.update_position()", scrim_init)

scrim_destroy = """    def destroy(self):
        if self.bind_id and self.parent:
            try:
                if self.parent.winfo_exists():
                    self.parent.unbind("<Configure>", self.bind_id)
            except (Exception, tk.TclError):
                pass
        for win in self.windows:"""
content = content.replace("    def destroy(self):\n        for win in self.windows:", scrim_destroy)

with open('ui/tutorial.py', 'w') as f:
    f.write(content)
