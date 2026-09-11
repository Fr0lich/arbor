import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# We need to change the animate method in TutorialHighlight to use math.sin
animate_code = """    def animate(self):
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

        except Exception:
            pass

        self.update_position()
        try:
            self.win.after(50, self.animate) # Faster tick for smooth animation
        except Exception:
            pass"""

content = re.sub(r'def animate\(self\):.*?self\.win\.after\(200, self\.animate\)\n\s*except Exception:\n\s*pass', animate_code, content, flags=re.DOTALL)

with open('ui/tutorial.py', 'w') as f:
    f.write(content)
