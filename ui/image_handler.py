"""ui/image_handler.py - Image handler compatibility layer and async pre-caching engine.

Modernized image inspection architecture providing:
- Asynchronous adjacent image pre-caching (N-1, N+1) via thread-safe cachetools.LRUCache(maxsize=10)
- Pre-decoding of high-resolution TIFF, JPEG, and PNG herbarium scans
- Safe zoom presets: Fit Window (Ctrl+1), Fit Width (Ctrl+2), 100% 1:1 Pixel Inspection (Ctrl+3)
- Graceful corrupted/missing image placeholder generator with explanatory badges
- Backward compatibility delegation to ImagePanel when embedded in MainWindow
"""

from __future__ import annotations

import os
import re
import threading
from io import BytesIO
from typing import Optional, Dict, List, Any, Callable
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageFile, ImageDraw
from cachetools import LRUCache

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

_NUMERIC_OID_PATTERN = re.compile(r"(\d+)")
MAX_IMAGE_CACHE = 40
MAX_PIL_CACHE = 10


def create_missing_image_placeholder(
    filename: str,
    width: int = 600,
    height: int = 400,
    is_dark: bool = False,
    reason: str = "Image not found on disk"
) -> Image.Image:
    """
    Renders an attractive, high-contrast visual placeholder PIL image with
    an explanatory badge: 'Image not found on disk: [filename]'
    Adheres strictly to AI_UI_GUIDE.md design tokens and museum trainee clarity.
    """
    w = max(320, width)
    h = max(200, height)

    bg_color = "#1e221f" if is_dark else "#f8fafc"
    card_bg = "#252b27" if is_dark else "#ffffff"
    border_color = "#45475a" if is_dark else "#cfc4c5"
    badge_bg = "#450a0a" if is_dark else "#fee2e2"
    badge_border = "#991b1b" if is_dark else "#fca5a5"
    badge_fg = "#fca5a5" if is_dark else "#991b1b"
    text_sub_color = "#bac2de" if is_dark else "#4c4546"
    icon_color = "#f87171" if is_dark else "#ef4444"

    img = Image.new("RGB", (w, h), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Outer decorative card frame with subtle rounded padding
    pad = 16
    draw.rounded_rectangle(
        [pad, pad, w - pad, h - pad],
        radius=12,
        fill=card_bg,
        outline=border_color,
        width=1
    )

    cx = w // 2
    cy = h // 2

    # Draw camera/image icon glyph
    icon_w = 44
    icon_h = 32
    ix0 = cx - icon_w // 2
    iy0 = cy - 65
    draw.rounded_rectangle([ix0, iy0, ix0 + icon_w, iy0 + icon_h], radius=4, outline=icon_color, width=2)
    draw.ellipse([cx - 8, iy0 + 8, cx + 8, iy0 + 24], outline=icon_color, width=2)
    # Strikethrough diagonal
    draw.line([ix0 - 4, iy0 + icon_h + 4, ix0 + icon_w + 4, iy0 - 4], fill=icon_color, width=2)

    # Explanatory badge text: "Image not found on disk: [filename]"
    short_name = os.path.basename(str(filename)) if filename else "unknown"
    badge_text = f"{reason}: {short_name}"
    # Truncate if filename is excessively long
    if len(badge_text) > 55:
        badge_text = badge_text[:52] + "..."

    # Estimate text width using character heuristic (safe across default PIL fonts)
    char_w = 7
    bw = min(w - 60, max(260, len(badge_text) * char_w + 24))
    bh = 28
    bx0 = cx - bw // 2
    by0 = cy - 10
    draw.rounded_rectangle(
        [bx0, by0, bx0 + bw, by0 + bh],
        radius=6,
        fill=badge_bg,
        outline=badge_border,
        width=1
    )
    # Centered badge text
    text_x = cx - (len(badge_text) * char_w) // 2
    draw.text((max(bx0 + 8, text_x), by0 + 7), badge_text, fill=badge_fg)

    # Trainee guidance helper text
    guide_text = "Check specimen directory or reconnect digital storage."
    gw_approx = len(guide_text) * 6
    draw.text((cx - gw_approx // 2, cy + 30), guide_text, fill=text_sub_color)

    return img


class ImagePreCacher:
    """
    Asynchronous Adjacent Image Pre-Caching Engine with thread-safe LRU eviction.
    Pre-loads and pre-decodes adjacent (N-1, N+1) specimen scans in a background
    daemon thread so navigating cards has zero decompression latency on the UI thread.
    """

    def __init__(self, maxsize: int = 10):
        self.maxsize = maxsize
        self._cache: LRUCache = LRUCache(maxsize=maxsize)
        self._lock = threading.Lock()
        self._active_worker: Optional[threading.Thread] = None

    def get(self, path: str) -> Optional[Image.Image]:
        """Thread-safe lookup of pre-decoded PIL image."""
        if not path:
            return None
        with self._lock:
            img = self._cache.get(path)
            if img is not None:
                try:
                    return img.copy()
                except Exception:
                    return img
            return None

    def put(self, path: str, img: Image.Image) -> None:
        """Thread-safe insertion into LRU cache with automatic eviction."""
        if not path or img is None:
            return
        with self._lock:
            self._cache[path] = img

    def clear(self) -> None:
        """Clear cache contents."""
        with self._lock:
            self._cache.clear()

    def __contains__(self, path: str) -> bool:
        with self._lock:
            return path in self._cache

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    @property
    def cache(self) -> LRUCache:
        return self._cache

    def load_and_decode(self, path: str) -> Optional[Image.Image]:
        """Synchronously reads and fully decodes an image from disk or cache safely."""
        if not path:
            return None
        cached = self.get(path)
        if cached is not None:
            return cached

        # Check existence if local path
        if not path.startswith(("http://", "https://")) and not os.path.exists(path):
            return None

        try:
            if path.startswith(("http://", "https://")):
                import requests
                r = requests.get(path, timeout=(3, 8))
                if r.status_code == 200:
                    pil_img = Image.open(BytesIO(r.content))
                    pil_img.load()
                else:
                    return None
            else:
                with open(path, "rb") as f:
                    file_bytes = f.read()
                if path.lower().endswith((".tif", ".tiff")):
                    try:
                        import tifffile
                        import numpy as np
                        tif_arr = tifffile.imread(BytesIO(file_bytes))
                        if tif_arr.dtype == np.uint16:
                            tif_arr = (tif_arr / 256).astype(np.uint8)
                        pil_img = Image.fromarray(tif_arr)
                    except Exception:
                        pil_img = Image.open(BytesIO(file_bytes))
                else:
                    pil_img = Image.open(BytesIO(file_bytes))
                pil_img.load()

            self.put(path, pil_img)
            return pil_img.copy()
        except Exception:
            return None

    def preload_adjacent(
        self,
        active_ids: list,
        current_id,
        image_index: dict,
        max_adjacent: int = 1,
        on_decoded: Optional[Callable[[str, Image.Image], None]] = None
    ) -> list:
        """
        Dispatches background pre-decoding of N-1 and N+1 adjacent specimen images.
        Returns the list of target paths queued for background caching.
        """
        if not active_ids:
            return []

        # Find current index with string and int tolerance
        idx = -1
        if current_id in active_ids:
            idx = active_ids.index(current_id)
        else:
            str_ids = [str(x) for x in active_ids]
            curr_str = str(current_id)
            if curr_str in str_ids:
                idx = str_ids.index(curr_str)

        if idx == -1:
            return []

        target_oids = []
        # Preload previous N-1
        for i in range(1, max_adjacent + 1):
            if idx - i >= 0:
                target_oids.append(active_ids[idx - i])
        # Preload next N+1
        for i in range(1, max_adjacent + 1):
            if idx + i < len(active_ids):
                target_oids.append(active_ids[idx + i])

        paths_to_load = []
        for oid in target_oids:
            oid_paths = image_index.get(str(oid)) or image_index.get(oid) or []
            if oid_paths:
                first_item = oid_paths[0]
                first_path = first_item[1] if isinstance(first_item, tuple) else first_item
                if first_path and first_path not in self:
                    paths_to_load.append(first_path)

        if not paths_to_load:
            return []

        def _worker():
            for p in paths_to_load:
                try:
                    img = self.load_and_decode(p)
                    if img and on_decoded:
                        on_decoded(p, img)
                except Exception:
                    pass

        t = threading.Thread(target=_worker, daemon=True, name="Arbor-ImagePreCacher")
        self._active_worker = t
        t.start()
        return paths_to_load


class ImageHandlerMixin:
    """Compatibility mixin for image operations, delegating to self.image_panel when available."""

    @property
    def pre_cacher(self) -> ImagePreCacher:
        if hasattr(self, "image_panel") and hasattr(self.image_panel, "pre_cacher"):
            return self.image_panel.pre_cacher
        if not hasattr(self, "_pre_cacher"):
            self._pre_cacher = ImagePreCacher(maxsize=10)
        return self._pre_cacher

    def _preload_adjacent_images(self, oid):
        if hasattr(self, "image_panel") and hasattr(self.image_panel, "_preload_adjacent_images"):
            return self.image_panel._preload_adjacent_images(oid)
        active_ids = getattr(getattr(self, "app", None), "active_object_ids", [])
        image_index = getattr(self, "image_index", {})
        return self.pre_cacher.preload_adjacent(active_ids, oid, image_index)

    def preload_adjacent_images(self, oid):
        return self._preload_adjacent_images(oid)

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
        self.image_zoom_factor = min(8.0, round(factor * 1.25, 3))
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()
        return self.image_zoom_factor

    def zoom_image_out(self):
        if hasattr(self, "image_panel"):
            return self.image_panel.zoom_image_out()
        factor = getattr(self, "image_zoom_factor", 1.0)
        self.image_zoom_factor = max(0.1, round(factor / 1.25, 3))
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()
        return self.image_zoom_factor

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

    def reset_image_view(self, event=None):
        """Reset view to 1.0 zoom and 0 orientation (Ctrl+0)."""
        if hasattr(self, "image_panel"):
            return self.image_panel.reset_image_view()
        self.image_zoom_factor = 1.0
        self.image_rotation_angle = 0
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()
        return self.image_zoom_factor

    def fit_image_view(self, event=None):
        """Fit whole sheet to window (Ctrl+1 / Toolbar Fit)."""
        if hasattr(self, "image_panel"):
            return self.image_panel.fit_image_view()
        return self.zoom_fit_window(event)

    def zoom_fit_window(self, event=None):
        """Fit entire specimen sheet into viewport (Ctrl+1)."""
        if hasattr(self, "image_panel") and hasattr(self.image_panel, "zoom_fit_window"):
            return self.image_panel.zoom_fit_window()
        self.image_zoom_factor = 1.0
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()
        return self.image_zoom_factor

    def zoom_fit_width(self, event=None):
        """Fit specimen width to viewport width for reading bottom label (Ctrl+2)."""
        if hasattr(self, "image_panel") and hasattr(self.image_panel, "zoom_fit_width"):
            return self.image_panel.zoom_fit_width()
        scales = self.calculate_zoom_preset_scales()
        self.image_zoom_factor = scales["fit_width"]
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()
        return self.image_zoom_factor

    def zoom_actual_pixels(self, event=None):
        """100% 1:1 Actual Pixel Inspection for fine botanical structures (Ctrl+3)."""
        if hasattr(self, "image_panel") and hasattr(self.image_panel, "zoom_actual_pixels"):
            return self.image_panel.zoom_actual_pixels()
        scales = self.calculate_zoom_preset_scales()
        self.image_zoom_factor = scales["actual_pixels"]
        if hasattr(self, "_re_render_current_images") and callable(self._re_render_current_images):
            self._re_render_current_images()
        return self.image_zoom_factor

    def calculate_zoom_preset_scales(self, path=None) -> Dict[str, float]:
        """Calculates scale factors for fit_window, fit_width, and actual_pixels presets."""
        if hasattr(self, "image_panel") and hasattr(self.image_panel, "calculate_zoom_preset_scales"):
            return self.image_panel.calculate_zoom_preset_scales(path)
        # Standard fallback portrait ratio (2:3) under default canvas
        avail_w = 760
        avail_h = 340
        img_w = 2000
        img_h = 3000
        default_ratio = min(avail_w / img_w, avail_h / img_h)
        width_ratio = avail_w / img_w
        return {
            "fit_window": 1.0,
            "fit_width": round(width_ratio / default_ratio, 3),
            "actual_pixels": round(1.0 / default_ratio, 3)
        }

    def build_online_image_urls(self, oid):
        if hasattr(self, "image_panel"):
            return self.image_panel.build_online_image_urls(oid)
        from ui.image_panel import ImagePanel
        return ImagePanel.build_online_image_urls(self, oid)
