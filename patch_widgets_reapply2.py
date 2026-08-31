import re

with open("ui/widgets.py", "r", encoding="utf-8") as f:
    content = f.read()

builder_code = """
class ArborTextField(tk.Frame):
    \"\"\"
    A reusable text field component that manages its own style, variables, and focus lines.
    \"\"\"
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
            state = self.text_widget.cget("state")
            if state == "disabled":
                self.text_widget.configure(state="normal")
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", self.variable.get())
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
    \"\"\"
    A reusable dropdown component that manages its own style and variables.
    \"\"\"
    def __init__(self, parent, variable=None, label_text="", choices=None, colors=None, **kwargs):
        if colors is None:
            raise ValueError("colors dictionary must be provided to ArborDropdown")
        self.colors = colors
        self.choices = choices or []

        if "bg" not in kwargs:
            kwargs["bg"] = colors["surface"]

        super().__init__(parent, **kwargs)

        self.variable = variable if variable else tk.StringVar()

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
    \"\"\"
    A builder class to dynamically generate form layouts based on configuration dictionaries.
    \"\"\"
    def __init__(self, parent_frame, colors, group_defs):
        self.parent = parent_frame
        self.colors = colors
        self.group_defs = group_defs

    def build(self, variables_dict):
        \"\"\"
        Builds the form widgets based on group_defs.
        variables_dict should be a dictionary mapping field names to tk.StringVar objects.
        Returns a dictionary of created widgets mapped by field name.
        \"\"\"
        widgets = {}
        for row_idx, group in enumerate(self.group_defs):
            group_name = group.get("name", "")
            fields = group.get("fields", [])

            # Group Container
            group_frame = tk.Frame(self.parent, bg=self.colors["bg"])
            group_frame.pack(fill="x", pady=(0, sc(16)))

            # Group Header
            if group_name:
                lbl = tk.Label(
                    group_frame, text=group_name.upper(),
                    font=("JetBrains Mono", sc(10), "bold"),
                    bg=self.colors["bg"], fg=self.colors["text_muted"],
                    anchor="w"
                )
                lbl.pack(fill="x", pady=(0, sc(4)))

            # Content grid
            content_frame = tk.Frame(group_frame, bg=self.colors["bg"])
            content_frame.pack(fill="x")

            # For each field, place it in a grid column
            num_cols = max(len(fields), 1)
            for i in range(num_cols):
                content_frame.columnconfigure(i, weight=1, uniform="col")

            for col_idx, field_name in enumerate(fields):
                if field_name not in variables_dict:
                    variables_dict[field_name] = tk.StringVar()

                field_widget = ArborTextField(
                    content_frame,
                    variable=variables_dict[field_name],
                    label_text=field_name,
                    colors=self.colors,
                    bg=self.colors["bg"]
                )
                field_widget.grid(row=0, column=col_idx, sticky="ew", padx=sc(4))
                widgets[field_name] = field_widget

        return widgets
"""

if "class ArborTextField" not in content:
    with open("ui/widgets.py", "a", encoding="utf-8") as f:
        f.write("\n" + builder_code)

print("Appended widgets to existing widgets.py")
