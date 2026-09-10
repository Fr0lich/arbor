import sys
import tkinter as tk
from typing import Callable, List, Dict, Any, Optional


class ContextMenuManager:
    """
    Unified context menu manager for Tkinter widgets.
    Standardizes cross-platform right-click bindings (<Button-3>, <Button-2>, <Control-Button-1>)
    and dynamically generates menus from callback return values.
    """

    @classmethod
    def bind(
        cls,
        widget_or_tag: Any,
        callback: Callable[[tk.Event], Optional[List[Dict[str, Any]]]],
        is_tag: bool = False,
        root: Optional[tk.Misc] = None,
    ) -> None:
        """
        Bind cross-platform right-click context menu triggers to a widget or bindtag.

        Args:
            widget_or_tag: A Tkinter widget instance or string bindtag name.
            callback: A function taking a tk.Event and returning a list of item dictionaries:
                      - {"label": str, "command": callable, "state": "normal"|"disabled"}
                      - {"separator": True}
                      - {"label": str, "submenu": [list of items], "state": "normal"|"disabled"}
            is_tag: True if widget_or_tag is a bindtag string rather than a widget.
            root: Optional root or master widget to resolve Tk context when binding tags or creating menus.
        """
        def _on_context_menu(event: tk.Event) -> Optional[str]:
            items = callback(event)
            if not items:
                return None

            parent = root
            if parent is None:
                if hasattr(event.widget, "winfo_toplevel"):
                    try:
                        parent = event.widget.winfo_toplevel()
                    except Exception:
                        parent = event.widget
                else:
                    parent = event.widget

            menu = cls.create_menu(parent, items)
            try:
                x = getattr(event, "x_root", 0)
                y = getattr(event, "y_root", 0)
                menu.tk_popup(x, y)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass
            return "break"

        sequences = ["<Button-3>", "<Control-Button-1>"]
        if sys.platform == "darwin":
            sequences.append("<Button-2>")
        else:
            sequences.append("<Button-2>")

        if is_tag or isinstance(widget_or_tag, str):
            tag_name = str(widget_or_tag)
            master = root or tk._default_root
            if master is not None:
                for seq in sequences:
                    master.bind_class(tag_name, seq, _on_context_menu)
        else:
            for seq in sequences:
                widget_or_tag.bind(seq, _on_context_menu)

    @classmethod
    def create_menu(cls, parent: tk.Misc, items: List[Dict[str, Any]]) -> tk.Menu:
        """
        Recursively instantiate and populate a tk.Menu with items, separators, and submenus.
        """
        menu = tk.Menu(parent, tearoff=0)
        for item in items:
            if not isinstance(item, dict):
                continue

            if item.get("separator"):
                menu.add_separator()
            elif "submenu" in item and item["submenu"] is not None:
                submenu = cls.create_menu(menu, item["submenu"])
                label = item.get("label", "")
                state = item.get("state", "normal")
                menu.add_cascade(label=label, menu=submenu, state=state)
            else:
                label = item.get("label", "")
                command = item.get("command")
                state = item.get("state", "normal")
                menu.add_command(label=label, command=command, state=state)
        return menu
