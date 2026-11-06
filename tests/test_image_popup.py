import pytest
import tkinter as tk
from PIL import Image, ImageTk
from ui.image_popup import ZoomableImagePopup
from ui.dialogs import ZoomableImagePopup as ReexportedPopup

def test_image_popup_reexport_parity():
    assert ReexportedPopup is ZoomableImagePopup

def test_zoomable_image_popup_lifecycle():
    root = tk.Tk()
    root.withdraw()
    try:
        # Create a tiny 10x10 PIL image
        img = Image.new("RGB", (10, 10), color="green")
        tk_img = ImageTk.PhotoImage(img)

        popup = ZoomableImagePopup(root, tk_img, source=None, is_online=False)

        assert popup.top.winfo_exists()
        assert popup.scale > 0
        assert popup.orig_img is not None

        # Test zoom and pan
        class DummyEvent:
            delta = 120
            x = 5
            y = 5

        popup._on_zoom(DummyEvent())
        popup._start_pan(DummyEvent())

        class DummyDragEvent:
            x = 15
            y = 15
        popup._do_pan(DummyDragEvent())

        # Close and verify cleanup
        popup._on_close()
        assert popup.orig_img is None
        assert popup.tk_img is None
        assert popup._stop_event.is_set()

        popup.top.destroy()
    finally:
        root.destroy()
