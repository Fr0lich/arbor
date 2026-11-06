"""ui/scroll_helper.py - Centralized, non-destructive mousewheel scroll routing for Arbor."""

from __future__ import annotations
import tkinter as tk


def bind_mousewheel(canvas: tk.Canvas, frame: tk.Widget | None = None) -> None:
    """Safely bind cross-platform mousewheel events to a Canvas and its contained child widgets.

    Uses a dedicated bindtag instead of destructive global bind_all/unbind_all hooks.
    This guarantees:
    1. Zero unbinding collisions when opening/closing child popups, dropdowns, or tooltips.
    2. Proper delta normalization for Windows/macOS and Button-4/5 for Linux.
    3. Seamless scrolling when cursor is over labels, entries, or inner containers.
    """
    tag = f"ScrollTag_{id(canvas)}"

    def _on_mousewheel(event):
        try:
            if not canvas.winfo_exists():
                return
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            elif event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    # Canvas direct bindings
    canvas.bind("<MouseWheel>", _on_mousewheel, add="+")
    canvas.bind("<Button-4>", _on_mousewheel, add="+")
    canvas.bind("<Button-5>", _on_mousewheel, add="+")

    # Bind class tag for recursive child widgets
    canvas.bind_class(tag, "<MouseWheel>", _on_mousewheel)
    canvas.bind_class(tag, "<Button-4>", _on_mousewheel)
    canvas.bind_class(tag, "<Button-5>", _on_mousewheel)

    def apply_tag(w):
        try:
            current_tags = list(w.bindtags())
            if tag not in current_tags:
                w.bindtags((tag,) + tuple(current_tags))
            for child in w.winfo_children():
                apply_tag(child)
        except Exception:
            pass

    if frame:
        apply_tag(frame)
        # Re-apply tag whenever new children are added to the container frame
        frame.bind("<Configure>", lambda e: apply_tag(frame), add="+")
