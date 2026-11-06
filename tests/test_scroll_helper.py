import tkinter as tk
import pytest
from ui.scroll_helper import bind_mousewheel


def test_bind_mousewheel_tag_routing():
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, height=200, width=200)
        canvas.pack()

        frame = tk.Frame(canvas)
        label = tk.Label(frame, text="Inside scroll frame")
        label.pack()

        # Bind using scroll helper
        bind_mousewheel(canvas, frame)

        # Check tag is applied to frame and child label
        tag = f"ScrollTag_{id(canvas)}"
        assert tag in frame.bindtags()
        assert tag in label.bindtags()

        # Check global root does not have custom mousewheel override
        assert "<MouseWheel>" not in root.bind()
    finally:
        root.destroy()
