import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

replacement = """            self.popup = TutorialPopup(
                self.active_root,
                title=step.get("title", ""),
                text=step.get("text", ""),
                target_widget=target_widget,
                placement=step.get("placement", "center"),
                is_first=(self.current_step_idx == 0),
                is_last=(self.current_step_idx == len(steps) - 1),
                manager=self,
                total_steps=len(steps)
            )"""

# The regex didn't work because of indentation or something. Let's do a literal replace
original = """            self.popup = TutorialPopup(
                self.active_root,
                title=step.get("title", ""),
                text=step.get("text", ""),
                target_widget=target_widget,
                placement=step.get("placement", "center"),
                is_first=(self.current_step_idx == 0),
                is_last=(self.current_step_idx == len(steps) - 1),
                manager=self
            )"""

content = content.replace(original, replacement)

with open('ui/tutorial.py', 'w') as f:
    f.write(content)
