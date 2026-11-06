"""ui/image_handler.py - Lightweight image handler compatibility layer.

Historically, Arbor contained a monolithic ImageHandlerMixin in this file.
The image viewing architecture has been fully modernized and decoupled into
ui.image_panel.ImagePanel. This module is retained for backward compatibility,
delegating all operations to self.image_panel when available.
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

from ui.image_panel import ImagePanel, MAX_IMAGE_CACHE, MAX_PIL_CACHE

_NUMERIC_OID_PATTERN = re.compile(r"(\d+)")


class ImageHandlerMixin:
    """Compatibility mixin for image operations, delegating to self.image_panel."""

    def _next_image_shortcut(self, event=None):
        if hasattr(self, "image_panel"):
            return self.image_panel._next_image_shortcut(event)
        if hasattr(self, "root") and isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            return
        if getattr(self, "image_mode", "") != "folder":
            return
        self._next_image()

    def _prev_image_shortcut(self, event=None):
        if hasattr(self, "image_panel"):
            return self.image_panel._prev_image_shortcut(event)
        if hasattr(self, "root") and isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            return
        if getattr(self, "image_mode", "") != "folder":
            return
        self._prev_image()

    def _next_image(self):
        if hasattr(self, "image_panel"):
            return self.image_panel._next_image()
        paths = getattr(self, "_image_paths", [])
        if not paths:
            return
        idx = getattr(self, "_current_image_index", 0)
        self._current_image_index = (idx + 1) % len(paths)
        if hasattr(self, "_render_image_gallery") and callable(self._render_image_gallery):
            self._render_image_gallery()

    def _prev_image(self):
        if hasattr(self, "image_panel"):
            return self.image_panel._prev_image()
        paths = getattr(self, "_image_paths", [])
        if not paths:
            return
        idx = getattr(self, "_current_image_index", 0)
        self._current_image_index = (idx - 1) % len(paths)
        if hasattr(self, "_render_image_gallery") and callable(self._render_image_gallery):
            self._render_image_gallery()

    def toggle_image_view(self):
        if hasattr(self, "image_panel"):
            return self.image_panel.toggle_image_view()
        mode = getattr(self, "image_view_mode", "gallery")
        self.image_view_mode = "stack" if mode == "gallery" else "gallery"
        if hasattr(self, "view_btn") and hasattr(self.view_btn, "config"):
            self.view_btn.config(text=f"View: {self.image_view_mode}")
        if getattr(self, "app", None) and getattr(self.app, "current_object_id", None):
            if hasattr(self, "load_images") and callable(self.load_images):
                self.load_images(self.app.current_object_id)

    def update_image_view_button(self):
        if hasattr(self, "image_panel"):
            return self.image_panel.update_image_view_button()
        if getattr(self, "image_mode", "") == "folder":
            if hasattr(self, "view_btn") and hasattr(self.view_btn, "winfo_ismapped") and not self.view_btn.winfo_ismapped():
                self.view_btn.pack(side="right")
        elif hasattr(self, "view_btn") and hasattr(self.view_btn, "pack_forget"):
            self.view_btn.pack_forget()

    def zoom_image_in(self):
        if hasattr(self, "image_panel"):
            return self.image_panel.zoom_image_in()
        factor = getattr(self, "image_zoom_factor", 1.0)
        self.image_zoom_factor = min(4.0, round(factor + 0.25, 2))
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()

    def zoom_image_out(self):
        if hasattr(self, "image_panel"):
            return self.image_panel.zoom_image_out()
        factor = getattr(self, "image_zoom_factor", 1.0)
        self.image_zoom_factor = max(0.1, round(factor - 0.25, 2))
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()

    def rotate_image(self, angle=None):
        if hasattr(self, "image_panel"):
            return self.image_panel.rotate_image(angle)
        if angle is not None:
            self.image_rotation_angle = angle % 360
        else:
            curr = getattr(self, "image_rotation_angle", 0)
            self.image_rotation_angle = (curr - 90) % 360
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()

    def reset_image_view(self):
        if hasattr(self, "image_panel"):
            return self.image_panel.reset_image_view()
        self.image_zoom_factor = 1.0
        self.image_rotation_angle = 0
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()

    def fit_image_view(self):
        if hasattr(self, "image_panel"):
            return self.image_panel.fit_image_view()
        self.reset_image_view()

    def build_online_image_urls(self, oid):
        if hasattr(self, "image_panel"):
            return self.image_panel.build_online_image_urls(oid)
        return ImagePanel.build_online_image_urls(self, oid)
