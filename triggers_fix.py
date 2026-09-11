import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# We need to add wait_event listener setup in show_step and store the bind_id
init_append = """            self.scrim = None
            self.on_complete = None
            self.trigger_bind_id = None
            self.trigger_widget = None"""

content = content.replace("            self.scrim = None\n            self.on_complete = None", init_append)

cleanup_append = """    def _cleanup(self):
        if self.trigger_bind_id and self.trigger_widget:
            try:
                if self.trigger_widget.winfo_exists():
                    self.trigger_widget.unbind(self._trigger_event, self.trigger_bind_id)
            except Exception:
                pass
        self.trigger_bind_id = None
        self.trigger_widget = None
        self._trigger_event = None"""

content = content.replace("    def _cleanup(self):", cleanup_append)

show_step_append = """        if target_widget and step.get("wait_event"):
            try:
                self._trigger_event = step["wait_event"]
                # We use next_step directly, but wrapped to prevent bubbling issues
                self.trigger_bind_id = target_widget.bind(self._trigger_event, lambda e: self.active_root.after(10, self.next_step), add="+")
                self.trigger_widget = target_widget
            except Exception:
                pass

        try:
            self.popup = TutorialPopup("""

content = content.replace("        try:\n            self.popup = TutorialPopup(", show_step_append)


with open('ui/tutorial.py', 'w') as f:
    f.write(content)
