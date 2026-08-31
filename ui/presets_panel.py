import tkinter as tk
from tkinter import ttk, simpledialog


class PresetsManager:
    """Manager and UI builder for Field and Location Presets."""

    @staticmethod
    def build_presets_ui(parent_frame, bg_col, bd_col, is_horiz, ui):
        """Build the preset selector and save/apply buttons frame."""
        presets_frame = tk.Frame(parent_frame, bg=bg_col)

        import config
        prefs = config.load_prefs()
        preset_names = list(prefs.get("data_presets", {}).keys())

        if not hasattr(ui, "active_preset_var"):
            ui.active_preset_var = tk.StringVar()
            if "Default" in preset_names:
                ui.active_preset_var.set("Default")
            elif preset_names:
                ui.active_preset_var.set(preset_names[0])

        ui.active_preset_cb = ttk.Combobox(
            presets_frame,
            textvariable=ui.active_preset_var,
            values=preset_names,
            state="normal",
            width=8 if is_horiz else 12,
            cursor="hand2"
        )
        ui.active_preset_cb.pack(side="left", padx=4)
        if hasattr(ui, "add_tooltip"):
            ui.add_tooltip(ui.active_preset_cb, "The preset that will be applied when you press Ctrl+K")

        def save_current_as_preset():
            name = ui.active_preset_var.get().strip()
            if not name:
                name = "Default"
                ui.active_preset_var.set(name)

            cur_prefs = config.load_prefs()
            if "data_presets" not in cur_prefs:
                cur_prefs["data_presets"] = {}

            vals = {}
            if hasattr(ui, "location_vars"):
                for k, var in ui.location_vars.items():
                    v = var.get().strip()
                    if v:
                        vals[k] = v

            cur_prefs["data_presets"][name] = vals
            config.save_prefs(cur_prefs)
            if hasattr(ui, "app") and ui.app:
                ui.app.config_prefs = cur_prefs

            names = list(cur_prefs["data_presets"].keys())
            ui.active_preset_cb["values"] = names
            if hasattr(ui, "system_status") and ui.system_status:
                ui.system_status.config(text=f"Saved preset: {name}")
            PresetsManager.refresh_load_data_preset_menu(ui)

        save_btn = ttk.Button(presets_frame, text="Save", width=5, command=save_current_as_preset, cursor="hand2")
        save_btn.pack(side="left", padx=2)
        if hasattr(ui, "add_tooltip"):
            ui.add_tooltip(save_btn, "Save current Location fields to this preset")

        apply_btn = ttk.Button(
            presets_frame,
            text="Apply",
            width=5,
            command=lambda: PresetsManager.apply_default_data_preset_shortcut(ui),
            cursor="hand2"
        )
        apply_btn.pack(side="left", padx=2)
        if hasattr(ui, "add_tooltip"):
            ui.add_tooltip(apply_btn, "Apply this preset to the fields above (Ctrl+K)")

        return presets_frame

    @staticmethod
    def apply_default_data_preset_shortcut(ui, event=None):
        """Trigger apply_active_preset on the active location panel or apply active data preset."""
        is_center = hasattr(ui, "location_in_center_var") and ui.location_in_center_var.get()
        active_panel = getattr(ui, "location_panel_horiz", None) if is_center else getattr(ui, "location_panel", None)
        if active_panel and hasattr(active_panel, "apply_active_preset"):
            active_panel.apply_active_preset()
            return "break"
        if not hasattr(ui, "active_preset_var"):
            return "break"
        default = ui.active_preset_var.get().strip()
        if default:
            PresetsManager.apply_saved_data_preset(ui, default)
        return "break"

    @staticmethod
    def save_data_preset_dialog(ui):
        """Prompt the user for a preset name and save current registration variables."""
        name = simpledialog.askstring("Save Data Preset", "Enter a name for this preset:")
        if not name:
            return

        import config
        prefs = config.load_prefs()
        if "data_presets" not in prefs:
            prefs["data_presets"] = {}

        preset_data = {}
        if hasattr(ui, "reg_vars"):
            for k, v in ui.reg_vars.items():
                val = v.get().strip()
                if val:
                    preset_data[k] = val

        prefs["data_presets"][name] = preset_data
        config.save_prefs(prefs)

        if hasattr(ui, "active_preset_cb"):
            names = list(prefs["data_presets"].keys())
            ui.active_preset_cb["values"] = names
            ui.active_preset_var.set(name)

        PresetsManager.refresh_load_data_preset_menu(ui)
        if hasattr(ui, "system_status") and ui.system_status:
            ui.system_status.config(text=f"Saved preset '{name}'")

    @staticmethod
    def apply_saved_data_preset(ui, name):
        """Apply a saved data preset by name to registration & location fields with visual highlight."""
        import config
        prefs = config.load_prefs()
        preset = prefs.get("data_presets", {}).get(name)
        if not preset:
            return

        applied_count = 0
        modified_widgets = []
        for k, v in preset.items():
            if hasattr(ui, "reg_vars") and k in ui.reg_vars:
                widget = ui.reg_entries.get(k) if hasattr(ui, "reg_entries") else None
                if isinstance(widget, tk.Text):
                    widget.delete("1.0", tk.END)
                    widget.insert("1.0", v)
                    try:
                        widget.edit_reset()
                    except tk.TclError:
                        pass
                    modified_widgets.append(widget)
                else:
                    ui.reg_vars[k].set(v)
                    if widget:
                        modified_widgets.append(widget)
                applied_count += 1
            elif hasattr(ui, "location_vars") and k in ui.location_vars:
                ui.location_vars[k].set(v)
                if hasattr(ui, "location_entries"):
                    for idx, loc_name in enumerate(ui.location_vars.keys()):
                        if loc_name == k and idx < len(ui.location_entries):
                            modified_widgets.append(ui.location_entries[idx])
                            break
                applied_count += 1

        for w in modified_widgets:
            if isinstance(w, (ttk.Entry, ttk.Combobox)):
                orig_style = w.cget("style")
                w.configure(style="Success.TEntry")
                ui.root.after(500, lambda wid=w, s=orig_style: wid.configure(style=s) if wid.winfo_exists() else None)
            elif isinstance(w, tk.Text):
                orig_bg = w.cget("background")
                w.configure(background="#d4edda")
                ui.root.after(500, lambda wid=w, bg=orig_bg: wid.configure(background=bg) if wid.winfo_exists() else None)

        if hasattr(ui, "commit_current_object"):
            ui.commit_current_object()
        if hasattr(ui, "system_status") and ui.system_status:
            ui.system_status.config(text=f"Applied Data Preset '{name}' ({applied_count} fields)")

    @staticmethod
    def refresh_load_data_preset_menu(ui):
        """Refresh the load presets cascade menu."""
        if not hasattr(ui, "load_data_preset_menu") or not ui.load_data_preset_menu:
            return
        ui.load_data_preset_menu.delete(0, 'end')
        import config
        prefs = config.load_prefs()
        saved = prefs.get("data_presets", {})
        if not saved:
            ui.load_data_preset_menu.add_command(label="(No saved presets)", state="disabled")
            return

        for name in saved.keys():
            ui.load_data_preset_menu.add_command(
                label=name,
                command=lambda n=name: PresetsManager.apply_saved_data_preset(ui, n)
            )

    @staticmethod
    def show_load_data_preset_popup(ui):
        """Display popup context menu with all available presets."""
        popup = tk.Menu(ui.root, tearoff=0)
        import config
        prefs = config.load_prefs()
        saved = prefs.get("data_presets", {})
        if not saved:
            popup.add_command(label="(No saved presets)", state="disabled")
        else:
            for name in sorted(saved.keys()):
                popup.add_command(
                    label=name,
                    command=lambda n=name: PresetsManager.apply_saved_data_preset(ui, n)
                )
        popup.post(ui.root.winfo_pointerx(), ui.root.winfo_pointery())
