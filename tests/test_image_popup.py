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


def test_zoomable_image_popup_linux_zoom():
    root = tk.Tk()
    root.withdraw()
    try:
        img = Image.new("RGB", (20, 20), color="blue")
        tk_img = ImageTk.PhotoImage(img)
        popup = ZoomableImagePopup(root, tk_img, source=None, is_online=False)

        # Verify Linux button bindings exist on the canvas
        canvas_bindings = popup.canvas.bind()
        assert "<Button-4>" in canvas_bindings
        assert "<Button-5>" in canvas_bindings
        assert "<MouseWheel>" in canvas_bindings

        class DummyEvent:
            x = 10
            y = 10

        initial_scale = popup.scale

        # Linux scroll up (Button-4, direction=1) -> zoom in factor 1.1
        popup._on_zoom_linux(DummyEvent(), 1)
        assert popup.scale == pytest.approx(initial_scale * 1.1, rel=1e-4)

        # Linux scroll down (Button-5, direction=-1) -> zoom out factor 0.9
        after_zoom_in = popup.scale
        popup._on_zoom_linux(DummyEvent(), -1)
        assert popup.scale == pytest.approx(after_zoom_in * 0.9, rel=1e-4)

        popup.top.destroy()
    finally:
        root.destroy()


def test_zoomable_image_popup_app_worker_streaming(monkeypatch):
    from backend.task_queue import app_worker
    from unittest.mock import MagicMock

    root = tk.Tk()
    root.withdraw()
    try:
        img = Image.new("RGB", (10, 10), color="red")
        tk_img = ImageTk.PhotoImage(img)

        run_bg_mock = MagicMock()
        monkeypatch.setattr(app_worker, "run_in_background", run_bg_mock)

        popup = ZoomableImagePopup(root, tk_img, source="http://example.com/specimen.jpg", is_online=True)

        # Verify app_worker.run_in_background was invoked with expected callbacks
        run_bg_mock.assert_called_once()
        call_args, call_kwargs = run_bg_mock.call_args

        assert call_args[0] == popup._load_full_res_worker
        assert call_kwargs.get("on_success") == popup._apply_full_res
        assert call_kwargs.get("on_error") == popup._on_full_res_error

        # Verify cancellation halts worker streaming immediately
        popup._stop_event.set()
        res = popup._load_full_res_worker()
        assert res is None

        # Verify applying full resolution updates title and image
        popup._stop_event.clear()
        full_img = Image.new("RGB", (100, 100), color="yellow")
        popup._apply_full_res(full_img)
        assert popup.orig_img == full_img
        assert popup.top.title() == "Image (Full Resolution)"

        # Verify error handling sets fallback title
        popup._on_full_res_error(RuntimeError("Network timeout"))
        assert popup.top.title() == "Image (Failed to load full res)"

        # Verify closing sets stop event
        popup._on_close()
        assert popup._stop_event.is_set()

        popup.top.destroy()
    finally:
        root.destroy()
