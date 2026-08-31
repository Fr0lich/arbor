import re

with open("ui/location_panel.py", "r", encoding="utf-8") as f:
    content = f.read()

import_pattern = r"(import config\nfrom config import sc)"
new_import = r"\1\nfrom ui.widgets import ArborTextField, ArborDropdown\nfrom ui.state import app_bus"
if "ArborTextField" not in content:
    content = re.sub(import_pattern, new_import, content)


init_pattern = r"def __init__\(self, parent, mode=\"vertical\", location_vars=None, config_ref=None, live_callbacks=None, dark_mode=False, \*\*kwargs\):"
new_init = """def __init__(self, parent, mode="vertical", location_vars=None, config_ref=None, live_callbacks=None, dark_mode=False, **kwargs):
        self.app_bus = app_bus
        self.app_bus.subscribe("LOCATION_DATA_CHANGED", self._on_bus_data_changed)
"""

if "self.app_bus = app_bus" not in content:
    content = content.replace(
        'def __init__(self, parent, mode="vertical", location_vars=None, config_ref=None, live_callbacks=None, dark_mode=False, **kwargs):',
        new_init
    )


bus_method = """
    def _on_bus_data_changed(self, payload):
        if not self.winfo_exists():
            return
        if "location" in payload:
            self.set_data(payload["location"])

    def destroy(self):
        if hasattr(self, "app_bus"):
            self.app_bus.unsubscribe("LOCATION_DATA_CHANGED", self._on_bus_data_changed)
        super().destroy()

"""

if "def _on_bus_data_changed" not in content:
    content = content.replace(
        "    def get_data(self):",
        bus_method + "    def get_data(self):"
    )

pattern = r"    def _create_field_widget\(self, parent, name, fdef, is_horiz=False\):.*?return container"

new_func = """    def _create_field_widget(self, parent, name, fdef, is_horiz=False):
        var = self.location_vars[name]
        ftype = fdef.get("type", "text")

        # We wrap it in a frame so it matches the expected return signature `row.pack(fill="x")`
        row = tk.Frame(parent, bg=parent.cget("bg"))

        if ftype == "choice":
            choices = fdef.get("choices", [])
            widget = ArborDropdown(
                row, variable=var, label_text=name, choices=choices, colors=self.colors, bg=parent.cget("bg")
            )
        else:
            readonly = fdef.get("readonly", False)
            widget = ArborTextField(
                row, variable=var, label_text=name, colors=self.colors, readonly=readonly, bg=parent.cget("bg")
            )

        widget.pack(fill="x", expand=True)
        return row"""

if re.search(pattern, content, re.DOTALL):
    content = re.sub(pattern, new_func, content, flags=re.DOTALL)

with open("ui/location_panel.py", "w", encoding="utf-8") as f:
    f.write(content)
