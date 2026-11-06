import tkinter as tk
import threading
from io import BytesIO
from PIL import Image, ImageTk
import requests
from utils import fade_in_toplevel


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

        # Original PIL-image, starts with thumbnail
        self.orig_img = ImageTk.getimage(tk_img)

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
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._do_pan)

        self._fit_to_window()

        if self.source:
            self.top.title("Loading full resolution...")
            threading.Thread(target=self._load_full_res, daemon=True).start()

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

    def _load_full_res(self):
        try:
            if self.is_online:
                r = requests.get(self.source, stream=True, timeout=10)
                if r.status_code == 200:
                    img_data = bytearray()
                    for chunk in r.iter_content(chunk_size=8192):
                        if self._stop_event.is_set():
                            r.close()
                            return
                        img_data.extend(chunk)
                    full_img = Image.open(BytesIO(img_data))
                    full_img.load()
                else:
                    full_img = None
            else:
                full_img = Image.open(self.source)
                full_img.load()

            if full_img and self.top.winfo_exists():
                self.top.after(0, lambda: self._apply_full_res(full_img))
        except Exception:
            if not getattr(self, "_stop_event", None) or not self._stop_event.is_set():
                if self.top.winfo_exists():
                    self.top.after(0, lambda: self.top.title("Image (Failed to load full res)"))

    def _apply_full_res(self, full_img):
        if not self.top.winfo_exists():
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

            filter_type = Image.NEAREST if fast_filter else Image.LANCZOS
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

    def _on_zoom(self, event):
        factor = 1.1 if event.delta > 0 else 0.9

        old_scale = self.scale
        self.scale *= factor

        mx, my = event.x, event.y
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
