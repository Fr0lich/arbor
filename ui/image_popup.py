import os
import tkinter as tk
import threading
from io import BytesIO
from PIL import Image, ImageTk
import requests
from utils import fade_in_toplevel
from backend.task_queue import app_worker
from ui.image_handler import create_missing_image_placeholder

# Allow on_success and on_error aliases for app_worker.run_in_background
if not getattr(app_worker.__class__, "_has_success_kwarg_shim", False):
    _orig_run_in_background = app_worker.__class__.run_in_background

    def _shimmed_run_in_background(self, func, callback=None, error_callback=None, **kwargs):
        cb = kwargs.pop("on_success", callback)
        err_cb = kwargs.pop("on_error", error_callback)
        return _orig_run_in_background(self, func, callback=cb, error_callback=err_cb, **kwargs)

    app_worker.__class__.run_in_background = _shimmed_run_in_background
    app_worker.__class__._has_success_kwarg_shim = True


class ZoomableImagePopup:
    """
    Detached full-resolution zoomable and pannable image viewport.
    Supports asynchronous streaming HTTP fetch for remote photo URLs,
    mouse-wheel zoom tracking with mouse coordinates, and debounced Lanczos filtering.
    """
    def __init__(self, parent, tk_img, source=None, is_online=False):
        self.top = tk.Toplevel(parent)
        self.top.title("Image")

        self._scale = getattr(parent, "_scale", 1.0)
        self._compact = False
        self._last_scale = self._scale
        self._zoom_job = None
        self._resize_job = None

        self.canvas = tk.Canvas(self.top, bg="black")
        self.canvas.pack(fill="both", expand=True)

        # Original PIL-image, starts with thumbnail or placeholder
        try:
            self.orig_img = ImageTk.getimage(tk_img) if tk_img else None
        except Exception:
            self.orig_img = None

        if not self.orig_img:
            short_name = os.path.basename(str(self.source)) if self.source else "photo"
            self.orig_img = create_missing_image_placeholder(short_name, width=600, height=400)

        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self._drag_start = None
        self.tk_img = None
        self.img_id = None
        self.source = source
        self.is_online = is_online
        self._stop_event = threading.Event()

        # Clean up references when window closes to avoid memory leaks
        self.top.bind("<Destroy>", self._on_close)
        self.top.bind("<Configure>", self._fit_to_window)
        self.canvas.bind("<MouseWheel>", self._on_zoom)
        self.canvas.bind("<Button-4>", lambda e: self._on_zoom_linux(e, 1))
        self.canvas.bind("<Button-5>", lambda e: self._on_zoom_linux(e, -1))
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._do_pan)

        self._fit_to_window()

        if self.source:
            self.top.title("Loading full resolution...")
            from backend.task_queue import app_worker
            app_worker.run_in_background(
                self._load_full_res_worker,
                on_success=self._apply_full_res,
                on_error=self._on_full_res_error
            )

        fade_in_toplevel(self.top)

    def _on_close(self, event=None):
        if hasattr(self, "_zoom_job") and self._zoom_job:
            try:
                self.top.after_cancel(self._zoom_job)
            except Exception:
                pass
        if hasattr(self, "_resize_job") and self._resize_job:
            try:
                self.top.after_cancel(self._resize_job)
            except Exception:
                pass
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
        self.orig_img = None
        self.tk_img = None

    def _load_full_res_worker(self):
        if getattr(self, "_stop_event", None) and self._stop_event.is_set():
            return None

        if self.is_online:
            r = requests.get(self.source, stream=True, timeout=10)
            if r.status_code == 200:
                img_data = bytearray()
                for chunk in r.iter_content(chunk_size=8192):
                    if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                        r.close()
                        return None
                    img_data.extend(chunk)
                if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                    return None
                full_img = Image.open(BytesIO(img_data))
                full_img.load()
                return full_img
            else:
                raise RuntimeError(f"HTTP {r.status_code} fetching image")
        else:
            if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                return None
            if not os.path.exists(self.source):
                raise FileNotFoundError(f"Image not found on disk: {self.source}")
            full_img = Image.open(self.source)
            full_img.load()
            if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                return None
            return full_img

    def _on_full_res_error(self, err=None):
        if getattr(self, "_stop_event", None) and self._stop_event.is_set():
            return
        try:
            if self.top.winfo_exists():
                self.top.title("Image (Failed to load full res)")
                short_name = os.path.basename(str(self.source)) if self.source else "photo"
                placeholder = create_missing_image_placeholder(short_name, width=600, height=400, reason="Image not found on disk")
                self.orig_img = placeholder
                self._fit_to_window()
        except Exception:
            pass

    def _load_full_res(self):
        try:
            full_img = self._load_full_res_worker()
            if full_img:
                self._apply_full_res(full_img)
        except Exception as e:
            self._on_full_res_error(e)

    def _apply_full_res(self, full_img):
        if getattr(self, "_stop_event", None) and self._stop_event.is_set():
            return
        if not full_img:
            return
        try:
            if not self.top.winfo_exists():
                return
        except Exception:
            return
        self.orig_img = full_img
        self.top.title("Image (Full Resolution)")
        self._fit_to_window()

    def _fit_to_window(self, event=None):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        iw, ih = self.orig_img.size
        self.scale = min(cw / iw, ch / ih)
        self.offset_x = (cw - iw * self.scale) / 2
        self.offset_y = (ch - ih * self.scale) / 2

        # Debounce the high quality configure/resize events
        if hasattr(self, "_resize_job") and self._resize_job:
            try:
                self.top.after_cancel(self._resize_job)
            except Exception:
                pass
            self._resize_job = None

        self._redraw(scale_changed=True, fast_filter=True)
        self._resize_job = self.top.after(200, self._high_quality_resize)

    def _high_quality_resize(self):
        self._resize_job = None
        self._redraw(scale_changed=True, fast_filter=False)

    def _redraw(self, scale_changed=True, fast_filter=False):
        if scale_changed or not self.tk_img or not self.img_id:
            w = int(self.orig_img.width * self.scale)
            h = int(self.orig_img.height * self.scale)

            if w < 1 or h < 1:
                return

            resample_enum = getattr(Image, "Resampling", Image)
            filter_type = resample_enum.NEAREST if fast_filter else resample_enum.LANCZOS
            resized = self.orig_img.resize((w, h), filter_type)
            self.tk_img = ImageTk.PhotoImage(resized)

            self.canvas.delete("all")
            self.img_id = self.canvas.create_image(
                self.offset_x,
                self.offset_y,
                anchor="nw",
                image=self.tk_img
            )
        else:
            if self.img_id:
                self.canvas.coords(self.img_id, self.offset_x, self.offset_y)

    def _zoom_at(self, x, y, factor):
        old_scale = self.scale
        if old_scale <= 0:
            old_scale = 1.0
        self.scale *= factor

        mx, my = x, y
        self.offset_x = mx - (mx - self.offset_x) * (self.scale / old_scale)
        self.offset_y = my - (my - self.offset_y) * (self.scale / old_scale)

        if hasattr(self, "_zoom_job") and self._zoom_job:
            try:
                self.top.after_cancel(self._zoom_job)
            except Exception:
                pass
            self._zoom_job = None

        self._redraw(scale_changed=True, fast_filter=True)
        self._zoom_job = self.top.after(200, self._high_quality_redraw)

    def _on_zoom(self, event):
        factor = 1.1 if getattr(event, "delta", 0) > 0 else 0.9
        self._zoom_at(event.x, event.y, factor)

    def _on_zoom_linux(self, event, direction):
        factor = 1.1 if direction > 0 else 0.9
        self._zoom_at(event.x, event.y, factor)

    def _high_quality_redraw(self):
        self._zoom_job = None
        self._redraw(scale_changed=True, fast_filter=False)

    def _start_pan(self, event):
        self._drag_start = (event.x, event.y)

    def _do_pan(self, event):
        if not self._drag_start:
            return

        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]

        self.offset_x += dx
        self.offset_y += dy
        self._drag_start = (event.x, event.y)

        self._redraw(scale_changed=False)
