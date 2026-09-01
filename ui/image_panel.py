import os
import re
import time
import threading
import webbrowser
from collections import OrderedDict
from io import BytesIO
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageFile

# Allow loading truncated images to prevent broken data stream errors
ImageFile.LOAD_TRUNCATED_IMAGES = True

import config
from config import sc
from ui.image_toolbar import create_image_toolbar

MAX_IMAGE_CACHE = 40
_NUMERIC_OID_PATTERN = re.compile(r"(\d+)")


class ImagePanel(ttk.Frame):
    """
    Decoupled Image Viewer Panel Component for Arbor.
    Manages image rendering, zooming, rotation, panning, async loading,
    local folder indexing, online repository fetching, and keyboard shortcuts.
    """

    def __init__(
        self,
        parent,
        app=None,
        app_bus=None,
        keybindings=None,
        dark_mode=False,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.app = app
        self.app_bus = app_bus
        self.keybindings = keybindings
        self.dark_mode = dark_mode
        self.http = None

        # Image state & cache
        self.image_paths = []
        self._image_paths = []
        self._current_image_index = 0
        self._image_index = 0

        _init_prefs = config.load_prefs() or {}
        self.images_missing_var = tk.StringVar(value="")
        self.show_images_var = tk.BooleanVar(value=_init_prefs.get("show_images", True))
        self.show_image_tools_var = tk.BooleanVar(value=_init_prefs.get("show_image_tools", True))
        self.image_stack_var = tk.BooleanVar(value=_init_prefs.get("image_stack", False))

        self.image_render_cache = OrderedDict()
        self.original_pil_cache = OrderedDict()
        self.image_cache = OrderedDict()

        self.image_zoom_factor = 1.0
        self.image_rotation_angle = 0
        self.image_mode = None  # "folder", "online", or "offline"
        self.image_folder = None
        self.image_index = {}   # ObjectID -> list of file paths
        self.image_status = {}
        self._image_load_token = 0
        self.image_view_mode = "gallery"  # "gallery" or "stack"
        self._is_navigating = False
        self.object_loaded = False
        self._rendered_paths = None
        self._thumb_cards = []
        self._virtual_cards = {}
        self._placeholder_frames = []
        self.image_settings_window = None

        # Build component UI
        self.build_ui()

        # Subscribe to app_bus events
        if self.app_bus:
            self.app_bus.subscribe("OBJECT_LOADED", self._on_bus_object_loaded)

        # Register keybindings if manager provided
        if self.keybindings and hasattr(self.keybindings, "bind_image_shortcuts"):
            self.keybindings.bind_image_shortcuts(self)

    @property
    def root(self):
        """Helper property to retrieve Tk root window safely."""
        if self.app and hasattr(self.app, "root"):
            return self.app.root
        return self.winfo_toplevel()

    def set_dark_mode(self, is_dark):
        self.dark_mode = is_dark
        if hasattr(self, "image_toolbar") and hasattr(self.image_toolbar, "set_dark_mode"):
            self.image_toolbar.set_dark_mode(is_dark)

    def destroy(self):
        """Clean up EventBus subscriptions on destruction."""
        if self.app_bus:
            try:
                self.app_bus.unsubscribe("OBJECT_LOADED", self._on_bus_object_loaded)
            except Exception:
                pass
        super().destroy()

    def _on_bus_object_loaded(self, payload):
        """EventBus handler when an object is selected/loaded in the application."""
        if not self.winfo_exists():
            return
        oid = payload if isinstance(payload, (str, int)) else getattr(payload, "id", None)
        if oid is not None:
            self.load_images(str(oid))

    def _get_http_session(self):
        """Lazy-initialize shared requests.Session to avoid network startup overhead in offline mode."""
        if self.http is None:
            import requests
            self.http = requests.Session()
        return self.http

    # -------------------------------------------------------------------------
    # UI Construction
    # -------------------------------------------------------------------------

    def build_ui(self):
        """Constructs the Image Viewer middle-panel layout."""
        for w in self.winfo_children():
            w.destroy()

        # Header Frame
        header = ttk.Frame(self, padding=(8, 6), style="MiddlePane.TFrame")
        header.pack(fill="x", side="top")
        self.header_frame = header

        self.header_label = ttk.Label(
            header,
            text="SPECIMEN IMAGES",
            font=("Hanken Grotesk", sc(11), "bold"),
            style="MiddlePane.TLabel"
        )
        self.header_label.pack(side="left")

        self.image_count_label = ttk.Label(
            header,
            text="",
            font=("Segoe UI", sc(9)),
            foreground="gray",
            style="MiddlePane.TLabel"
        )
        self.image_count_label.pack(side="left", padx=8)

        self.view_btn = ttk.Button(
            header,
            text="View: gallery",
            style="Nav.TButton",
            command=self.toggle_image_view,
            cursor="hand2"
        )
        self.view_btn.pack(side="right", padx=(4, 0))

        self.images_missing_label = ttk.Label(
            header,
            text="",
            foreground="#c93a40",
            font=("Segoe UI", sc(9), "bold"),
            style="MiddlePane.TLabel"
        )
        self.images_missing_label.pack(side="right", padx=(0, 8))

        # Image Control Overlay Toolbar
        self.image_toolbar = create_image_toolbar(
            parent=self,
            live_callbacks={
                "zoom_in": self.zoom_image_in,
                "zoom_out": self.zoom_image_out,
                "rotate_cw": lambda: self.rotate_image(90),
                "rotate_ccw": lambda: self.rotate_image(-90),
                "reset": self.reset_image_view,
                "fit": self.fit_image_view,
                "design_toggle": lambda mode: getattr(self.app, "save_user_pref", lambda k, v: None)("image_button_style", mode)
            },
            design_mode=getattr(self.app, "image_button_style", "standard") if self.app else "standard",
            dark_mode=self.dark_mode,
            zoom_level=self.image_zoom_factor,
            rotation_angle=self.image_rotation_angle
        )
        self.image_toolbar.pack(fill="x", padx=6, pady=(0, 2))

        # Main Canvas Box
        image_box = ttk.Frame(self, relief="flat", padding=0, style="MiddlePane.TFrame")
        self.image_box = image_box
        image_box.pack(fill="both", expand=True)

        self.image_canvas = tk.Canvas(image_box, highlightthickness=0)
        self.image_scroll = ttk.Scrollbar(
            image_box,
            orient="vertical",
            command=self.image_canvas.yview
        )

        self.image_container = ttk.Frame(self.image_canvas)
        self.image_window = self.image_canvas.create_window(
            (0, 0),
            window=self.image_container,
            anchor="nw"
        )

        self.image_container.bind(
            "<Configure>",
            lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all"))
        )
        self.image_canvas.configure(yscrollcommand=self._on_image_scroll)
        self.image_canvas.pack(side="left", fill="both", expand=True)

        self.image_canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.image_canvas.bind("<B1-Motion>", self._on_pan_drag)
        self.image_scroll.pack(side="right", fill="y")
        self.image_canvas.bind("<Configure>", self._on_canvas_resize)

        self.image_container.columnconfigure(0, weight=1)
        self.image_container.columnconfigure(1, weight=1)

        self.no_image_label = ttk.Label(
            self.image_container,
            text="No images available",
            foreground="gray"
        )
        self.no_image_label.pack(pady=20)

        self.update_image_view_button()

    def ensure_no_image_label(self):
        if not hasattr(self, "no_image_label") or not self.no_image_label.winfo_exists():
            self.no_image_label = ttk.Label(
                self.image_container,
                text="No images available",
                foreground="gray"
            )

    # -------------------------------------------------------------------------
    # Shortcuts & Mode Toggles
    # -------------------------------------------------------------------------

    def _next_image_shortcut(self, event=None):
        if hasattr(self, "root") and isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            return
        if self.image_mode != "folder":
            return
        self._next_image()

    def _prev_image_shortcut(self, event=None):
        if hasattr(self, "root") and isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            return
        if self.image_mode != "folder":
            return
        self._prev_image()

    def toggle_image_view(self):
        if self.image_view_mode == "gallery":
            self.image_view_mode = "stack"
        else:
            self.image_view_mode = "gallery"

        self.view_btn.config(text=f"View: {self.image_view_mode}")

        curr_oid = getattr(self.app, "current_object_id", None) if self.app else None
        if curr_oid:
            self.load_images(curr_oid)

    def update_image_view_button(self):
        if self.image_mode == "folder":
            if not self.view_btn.winfo_ismapped():
                self.view_btn.pack(side="right")
        else:
            self.view_btn.pack_forget()

        # Check panedwindow parent toggling for offline mode
        if self.image_mode == "offline":
            if self.parent and hasattr(self.parent, "panes") and str(self) in self.parent.panes():
                self.parent.forget(self)
        else:
            if self.parent and hasattr(self.parent, "panes") and str(self) not in self.parent.panes():
                try:
                    self.parent.insert(1, self, weight=3)
                except Exception:
                    pass

    def _update_image_controls_visibility(self):
        if hasattr(self, "image_toolbar") and self.image_toolbar.winfo_exists():
            if self.image_mode == "folder" and self.image_view_mode == "stack":
                self.image_toolbar.pack_forget()
                self.image_toolbar.pack(fill="x", padx=6, pady=(0, 2), before=self.image_box)
            else:
                self.image_toolbar.pack_forget()

        if self.image_mode == "online":
            if not hasattr(self, "image_hud") or not self.image_hud.winfo_exists():
                self.image_hud = tk.Frame(
                    self.image_box,
                    bg="#1a1a1a",
                    highlightthickness=1,
                    highlightbackground="#333333"
                )

                def _overlay_btn(text, cmd):
                    btn = tk.Button(
                        self.image_hud,
                        text=text,
                        command=cmd,
                        bg="#1a1a1a",
                        fg="#ffffff",
                        activebackground="#333333",
                        activeforeground="#ffffff",
                        relief="flat",
                        bd=0,
                        font=("Segoe UI", sc(9), "bold"),
                        padx=sc(10),
                        pady=sc(5),
                        cursor="hand2"
                    )
                    btn.pack(side="left", padx=sc(1))
                    btn.bind("<Enter>", lambda e: btn.config(bg="#333333"))
                    btn.bind("<Leave>", lambda e: btn.config(bg="#1a1a1a"))
                    return btn

                _overlay_btn("+", self.zoom_image_in)
                _overlay_btn("-", self.zoom_image_out)
                _overlay_btn("↻", self.rotate_image)
                _overlay_btn("RESET", self.reset_image_view)

            self.image_hud.place(relx=1.0, rely=1.0, anchor="se", x=sc(-24), y=sc(-24))
        else:
            if hasattr(self, "image_hud") and self.image_hud.winfo_exists():
                self.image_hud.place_forget()

    # -------------------------------------------------------------------------
    # Scrolling & Resizing
    # -------------------------------------------------------------------------

    def _bind_image_scroll(self):
        self.image_canvas.bind("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.image_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_resize(self, event):
        self._last_canvas_width = event.width
        now = time.time()
        last_time = getattr(self, "_last_resize_time", 0.0)
        elapsed = (now - last_time) * 1000.0

        if hasattr(self, "_image_resize_job") and self._image_resize_job:
            try:
                self.root.after_cancel(self._image_resize_job)
            except Exception:
                pass
            self._image_resize_job = None

        if elapsed >= 16.6:
            self._last_resize_time = now
            self._refresh_images_on_resize()

        self._image_resize_job = self.root.after(80, self._refresh_images_on_resize)

    def _refresh_images_on_resize(self):
        self._image_resize_job = None
        if not self.root.winfo_exists():
            return
        width = getattr(self, "_last_canvas_width", self.image_canvas.winfo_width())
        try:
            self.image_canvas.itemconfig(self.image_window, width=width)
        except Exception:
            pass
        if self.object_loaded and getattr(self, "_image_paths", None):
            self.image_render_cache.clear()
            if self.image_view_mode == "gallery":
                self._render_image_gallery()
            else:
                self._render_image_stack()

    def _on_image_scroll(self, *args):
        self.image_scroll.set(*args)
        if hasattr(self, "_update_virtual_stack"):
            if hasattr(self, "_virtual_scroll_job") and self._virtual_scroll_job:
                self.root.after_cancel(self._virtual_scroll_job)
            self._virtual_scroll_job = self.root.after(150, self._update_virtual_stack)

    def _update_virtual_stack(self):
        self._virtual_scroll_job = None
        if not hasattr(self, "_placeholder_frames") or not self._placeholder_frames:
            return

        try:
            y0 = self.image_canvas.canvasy(0)
            y1 = self.image_canvas.canvasy(self.image_canvas.winfo_height())
        except tk.TclError:
            return

        buffer = 400
        for i, frame in enumerate(self._placeholder_frames):
            if not frame.winfo_exists():
                continue
            frame_y = frame.winfo_y()
            frame_h = frame.winfo_height()

            is_visible = (frame_y + frame_h >= y0 - buffer) and (frame_y <= y1 + buffer)

            if is_visible and i not in self._virtual_cards:
                path = self._image_paths[i]
                frame.pack_propagate(True)

                lbl = ttk.Label(frame, text="Loading image...")
                lbl.pack(fill="both", expand=True)

                lbl.bind("<ButtonPress-1>", self._on_pan_start)
                lbl.bind("<B1-Motion>", self._on_pan_drag)
                lbl.bind("<Double-Button-1>", lambda e, p=path: self.open_image_web(p))

                self._load_image_async(path, large=True, target_widget=lbl)
                self._virtual_cards[i] = lbl

            elif not is_visible and i in self._virtual_cards:
                for widget in frame.winfo_children():
                    widget.destroy()

                frame.configure(height=getattr(self, "_estimated_card_height", 350))
                frame.pack_propagate(False)
                del self._virtual_cards[i]

    # -------------------------------------------------------------------------
    # Menus & Settings Dialogs
    # -------------------------------------------------------------------------

    def open_image_menu(self):
        if hasattr(self, "image_settings_window") and self.image_settings_window and self.image_settings_window.winfo_exists():
            self.image_settings_window.focus_force()
            self.image_settings_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.image_settings_window = win
        win.title("Image Source Settings")
        win.resizable(True, True)
        win.transient(self.root)

        import utils
        utils.center_and_fit_toplevel(win, sc(340), sc(220))

        frame = ttk.Frame(win, padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="IMAGE SOURCE SETTINGS",
            font=("Segoe UI", sc(11), "bold"),
            foreground="#1a1c1c"
        ).pack(anchor="w", pady=(0, 10))

        mode_text = {
            None: "None / Not Set",
            "folder": "Local Directory",
            "online": "Online Repository",
            "offline": "Offline (No Images)"
        }.get(self.image_mode, "Unknown")

        status_frame = ttk.Frame(frame, padding=5)
        status_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(
            status_frame,
            text="Active Mode:  ",
            font=("Segoe UI", sc(9))
        ).pack(side="left")

        color_fg = "#3b6934" if self.image_mode in ("folder", "online") else "#ba1a1a"
        ttk.Label(
            status_frame,
            text=mode_text,
            font=("Segoe UI", sc(9), "bold"),
            foreground=color_fg
        ).pack(side="left")

        def run_action(cmd):
            win.destroy()
            cmd()

        ttk.Button(
            frame,
            text="Select Local Image Folder...",
            command=lambda: run_action(self.select_image_folder),
            cursor="hand2"
        ).pack(fill="x", pady=2)

        ttk.Button(
            frame,
            text="Load from Online Repository",
            command=lambda: run_action(self.enable_online_images),
            cursor="hand2"
        ).pack(fill="x", pady=2)

        ttk.Button(
            frame,
            text="Disable Images (Offline Mode)",
            command=lambda: run_action(self.enable_offline_mode),
            cursor="hand2"
        ).pack(fill="x", pady=2)

        footer = ttk.Frame(frame)
        footer.pack(fill="x", side="bottom", pady=(10, 0))

        ttk.Button(
            footer,
            text="Close",
            command=win.destroy,
            cursor="hand2"
        ).pack(side="right")

        win.bind("<Escape>", lambda e: win.destroy())

    def enable_online_images(self):
        if self.image_mode == "folder":
            res = messagebox.askyesno(
                "Switch image mode",
                "Images are already loaded from a folder.\n\nSwitch to online images?"
            )
            if not res:
                return

        self.image_mode = "online"
        self.update_image_view_button()
        self.image_index = {}

        if self.app and hasattr(self.app, "system_status"):
            self.app.system_status.config(text="Online image mode enabled")

        curr_oid = getattr(self.app, "current_object_id", None) if self.app else None
        if curr_oid:
            self.load_images(curr_oid)

    def select_image_folder(self):
        folder = filedialog.askdirectory(
            title="Select image folder",
            initialdir=config.get_last_dir("last_image_dir")
        )
        if not folder:
            return
        config.set_last_dir("last_image_dir", folder)
        self.image_folder = folder

        threading.Thread(
            target=self.build_image_index,
            args=(folder,),
            daemon=True
        ).start()

        self.image_mode = "folder"
        self.update_image_view_button()

        if self.app and hasattr(self.app, "reg_entry_list") and self.app.reg_entry_list:
            self.app.reg_entry_list[0].focus_set()

    def enable_offline_mode(self):
        self.image_mode = "offline"
        self.update_image_view_button()
        self.image_cache.clear()
        if self.app and hasattr(self.app, "system_status"):
            self.app.system_status.config(text="Offline image mode enabled")

        curr_oid = getattr(self.app, "current_object_id", None) if self.app else None
        if curr_oid:
            self.load_images(curr_oid)

    # -------------------------------------------------------------------------
    # Indexing & URLs
    # -------------------------------------------------------------------------

    def _extract_numeric_object_id(self, filename):
        name = os.path.splitext(filename)[0]
        m = _NUMERIC_OID_PATTERN.search(name)
        if not m:
            return None
        try:
            return int(m.group(1))
        except ValueError:
            return None

    def build_online_image_urls(self, oid):
        prefs = config.load_prefs() or {}
        pattern_override = prefs.get(
            "image_url_pattern_override",
            prefs.get("advanced", {}).get("image_url_pattern_override", "")
        ).strip()

        if pattern_override:
            pattern = pattern_override
        else:
            pattern = getattr(self.app, "config", {}).get(
                "image_url_pattern",
                "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg"
            ) if self.app else "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg"

        if not pattern:
            return []

        suffixes = ["", "-01", "-02", "-03"]
        urls = []
        is_numeric = str(oid).isdigit()

        for s in suffixes:
            if "{id}" in pattern:
                if "{suffix}" in pattern:
                    url = pattern.replace("{id}", str(oid)).replace("{suffix}", s)
                else:
                    url = pattern.replace("{id}", f"{oid}{s}")
            elif "{num" in pattern and "{suffix}" in pattern:
                if is_numeric:
                    num = int(oid)
                    url = pattern.format(num=num, suffix=s)
                else:
                    url = f"{pattern.rstrip('/')}/{oid}{s}"
            elif "{num" in pattern:
                if is_numeric:
                    num = int(oid)
                    url = pattern.format(num=num)
                    if s:
                        if "." in url.rsplit("/", 1)[-1]:
                            base, ext = url.rsplit(".", 1)
                            url = f"{base}{s}.{ext}"
                        else:
                            url = f"{url}{s}"
                else:
                    url = f"{pattern.rstrip('/')}/{oid}{s}"
            else:
                url = f"{pattern}{oid}{s}"
            urls.append(url)
        return urls

    def build_image_index(self, folder):
        self.image_index = {}
        image_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

        files = []
        for root_dir, _, filenames in os.walk(folder):
            for fname in filenames:
                files.append(os.path.join(root_dir, fname))

        total = len(files)
        if self.app and hasattr(self.app, "_show_progress"):
            self.root.after(0, lambda: self.app._show_progress("Indexing images...", total))

        found_object_ids = set()
        for i, path in enumerate(files):
            fname = os.path.basename(path)
            ext = os.path.splitext(fname)[1].lower()
            if ext not in image_exts:
                continue

            oid_num = self._extract_numeric_object_id(fname)
            if oid_num is None:
                continue

            oid = str(oid_num)
            found_object_ids.add(str(oid_num))

            m = re.search(r"(?:\d+)-(\d+)", fname)
            img_no = int(m.group(1)) if m else 1
            self.image_index.setdefault(oid, []).append((img_no, path))

            if i % 50 == 0 and self.app and hasattr(self.app, "image_scan_progress"):
                self.root.after(
                    0,
                    self.app.image_scan_progress.configure,
                    {"value": i, "maximum": total}
                )

        for oid in self.image_index:
            self.image_index[oid].sort(key=lambda x: x[0])
            self.image_index[oid] = [p for _, p in self.image_index[oid]]

        if self.app and getattr(self.app, "df_obs", None) is not None:
            has_img = self.app.df_obs.index.astype(str).isin(found_object_ids)
            self.app.df_obs["Images_Missing"] = ~has_img
            self.app.dirty = True

        def _notify_ui():
            if self.app:
                if hasattr(self.app, "_invalidate_row_cache"):
                    self.app._invalidate_row_cache()
                if hasattr(self.app, "_problem_cache"):
                    self.app._problem_cache.clear()
                if hasattr(self.app, "refresh_list"):
                    self.app.refresh_list()
                if hasattr(self.app, "_on_startup_ready"):
                    self.app._on_startup_ready()

        self.root.after(0, _notify_ui)

    # -------------------------------------------------------------------------
    # Image Loading & Async Fetching
    # -------------------------------------------------------------------------

    def load_images(self, oid):
        self._update_image_controls_visibility()
        if not self.show_images_var.get():
            return

        self._image_index = 0
        self.image_container.update_idletasks()

        if self.app and self.app.config and not self.app.config.get("has_images", True):
            return

        if self.image_mode == "offline":
            for w in self.image_container.winfo_children():
                if w != getattr(self, "no_image_label", None):
                    w.destroy()

            self.ensure_no_image_label()
            self.no_image_label.pack_forget()
            self.images_missing_label.config(text="Offline mode active (images disabled)")
            return

        self._image_load_token += 1
        token = self._image_load_token

        for w in self.image_container.winfo_children():
            w.destroy()

        if self.image_mode == "online":
            self.images_missing_label.config(text="Loading online images...", foreground="blue")
            urls = self.build_online_image_urls(oid)

            if urls and all(url in self.original_pil_cache for url in urls):
                for url in urls:
                    self._display_online_image(self.original_pil_cache[url], url, token)
                return

            threading.Thread(
                target=self._load_online_images_worker,
                args=(urls, token),
                daemon=True
            ).start()
            return

        paths = self.image_index.get(str(oid), [])
        if self._is_navigating and paths:
            paths = [paths[0]]

        self._image_paths = paths
        self._current_image_index = 0
        self.image_count_label.config(text=f"{len(paths)} images")

        if not paths:
            self.images_missing_label.config(text="No images found")
            self.ensure_no_image_label()
            self.no_image_label.pack(pady=20)
            return

        if self.image_view_mode == "gallery":
            self.root.after(0, self._render_image_gallery)
        else:
            self.root.after(0, self._render_image_stack)

    def _load_image_async(self, path, large, target_widget, token=None):
        if token is None:
            token = getattr(self, "_image_load_token", 0)

        key = (path, large, self.image_zoom_factor if large else 1.0, self.image_rotation_angle if large else 0)

        if key in self.image_render_cache:
            self.image_render_cache.move_to_end(key)
            tk_img = self.image_render_cache[key]
            if target_widget.winfo_exists():
                target_widget.config(image=tk_img, text="")
                target_widget.image = tk_img
            return

        target_widget.loading_path = path

        try:
            width = self.image_canvas.winfo_width()
            height = self.image_canvas.winfo_height()
        except Exception:
            width, height = 800, 350

        if width < 300:
            width = 800
        canvas_h = height if height > 150 else 350

        zoom = self.image_zoom_factor
        rot = self.image_rotation_angle
        dpi_scale = getattr(config, "SCALE_FACTOR", 1.0)

        def worker():
            try:
                if token != getattr(self, "_image_load_token", 0):
                    return

                if path not in self.original_pil_cache:
                    pil_img = Image.open(path)
                    pil_img.load()
                    self.original_pil_cache[path] = pil_img
                    if len(self.original_pil_cache) > 40:
                        self.original_pil_cache.popitem(last=False)

                img = self.original_pil_cache[path].copy()

                prefs = config.load_prefs() or {}
                advanced_prefs = prefs.get("advanced", {})
                algo_name = prefs.get("image_resampling_algorithm", advanced_prefs.get("image_resampling_algorithm", "LANCZOS (High Quality)"))
                if "BILINEAR" in algo_name:
                    resample_filter = Image.BILINEAR
                elif "NEAREST" in algo_name:
                    resample_filter = Image.NEAREST
                else:
                    resample_filter = Image.LANCZOS

                if large and rot != 0:
                    img = img.rotate(rot, expand=True)

                if large:
                    max_width = int(width * 0.95 * zoom)
                    max_height = int(canvas_h * 0.85 * zoom)

                    if max_width > 0 and max_height > 0:
                        img_w, img_h = img.size
                        ratio = min(max_width / img_w, max_height / img_h)
                        new_w = int(img_w * ratio)
                        new_h = int(img_h * ratio)
                        if new_w > 0 and new_h > 0:
                            img = img.resize((new_w, new_h), resample_filter)
                else:
                    size = int(max(1, int(70 * dpi_scale)))
                    img_w, img_h = img.size
                    min_dim = min(img_w, img_h)
                    left = (img_w - min_dim) / 2
                    top = (img_h - min_dim) / 2
                    right = (img_w + min_dim) / 2
                    bottom = (img_h + min_dim) / 2
                    img = img.crop((left, top, right, bottom))
                    img = img.resize((size, size), resample_filter)

                def callback(pil_img=img):
                    if token != getattr(self, "_image_load_token", 0):
                        return
                    if not target_widget.winfo_exists():
                        return
                    if getattr(target_widget, "loading_path", None) != path:
                        return

                    tk_img = ImageTk.PhotoImage(pil_img)
                    self.image_render_cache[key] = tk_img

                    if len(self.image_render_cache) > MAX_IMAGE_CACHE:
                        self.image_render_cache.popitem(last=False)

                    target_widget.config(image=tk_img, text="")
                    target_widget.image = tk_img

                self.root.after(0, callback)
            except Exception as e:
                from utils import debug_error
                debug_error("_load_image_async worker", str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _load_online_images_worker(self, urls, token):
        def try_load(url, attempts=2):
            for _ in range(attempts):
                if token != self._image_load_token:
                    return None
                try:
                    r = self._get_http_session().get(url, timeout=(3, 8))
                    if r.status_code == 200:
                        img = Image.open(BytesIO(r.content))
                        img.load()
                        return img
                    return None
                except Exception:
                    pass
            return None

        loaded_any = False
        for url in urls:
            if token != self._image_load_token:
                return
            img = try_load(url, attempts=2)
            if img is None:
                continue
            self._display_online_image(img, url, token)
            loaded_any = True

        if not loaded_any:
            self.root.after(0, self._show_no_images_online)

    def _show_no_images_online(self):
        self.images_missing_label.config(text="No online images found", foreground="#c93a40")

    def _display_online_image(self, img, url, token):
        if token != self._image_load_token:
            return

        if url not in self.original_pil_cache:
            self.original_pil_cache[url] = img.copy()
            if len(self.original_pil_cache) > 40:
                self.original_pil_cache.popitem(last=False)

        pil_img = self.original_pil_cache[url].copy()
        if self.image_rotation_angle != 0:
            pil_img = pil_img.rotate(self.image_rotation_angle, expand=True)

        self.root.update_idletasks()
        available_width = self.image_canvas.winfo_width()
        if available_width < 300:
            available_width = 800

        max_width = int(available_width * 0.98 * self.image_zoom_factor)
        max_height = int(self.root.winfo_height() * 0.9 * self.image_zoom_factor)
        pil_img.thumbnail((max_width, max_height), Image.LANCZOS)

        self.root.after(
            0,
            lambda im=pil_img, u=url, t=token: self._create_online_image(im, u, t)
        )

    def _create_online_image(self, pil_img, url, token):
        if token != self._image_load_token:
            return

        tk_img = ImageTk.PhotoImage(pil_img)
        container = ttk.Frame(self.image_container)
        container.pack(pady=8)

        ttk.Label(container, text=os.path.basename(url)).pack()

        lbl = ttk.Label(container, image=tk_img)
        lbl.image = tk_img
        lbl.pack()

        lbl.bind("<Enter>", lambda e: container.configure(style="Hover.TFrame"))
        lbl.bind("<Leave>", lambda e: container.configure(style="TFrame"))

        lbl.bind("<ButtonPress-1>", self._on_pan_start)
        lbl.bind("<B1-Motion>", self._on_pan_drag)
        lbl.bind(
            "<ButtonRelease-1>",
            lambda e, im=tk_img, u=url: self._on_pan_release(
                e,
                lambda ev: self.open_image_popup(im, source=u, is_online=True)
            )
        )
        lbl.bind("<Double-Button-1>", lambda e, u=url: webbrowser.open(u))

    # -------------------------------------------------------------------------
    # Renderers (Gallery vs Stack)
    # -------------------------------------------------------------------------

    def _render_image_stack(self):
        self._update_image_controls_visibility()
        for w in self.image_container.winfo_children():
            w.destroy()

        self._virtual_cards = {}
        self._placeholder_frames = []

        if not self._image_paths:
            return

        try:
            available_width = self.image_canvas.winfo_width()
            if available_width < 300:
                available_width = 800
        except Exception:
            available_width = 800

        estimated_height = int(350 * 0.85 * self.image_zoom_factor) + 20
        if estimated_height < 100:
            estimated_height = 100
        self._estimated_card_height = estimated_height

        for path in self._image_paths:
            frame = ttk.Frame(self.image_container, height=estimated_height, width=int(available_width * 0.95))
            frame.pack_propagate(False)
            frame.pack(pady=10)
            self._placeholder_frames.append(frame)

        self.root.update_idletasks()
        self._update_virtual_stack()

    def _render_image_gallery(self):
        self._update_image_controls_visibility()

        can_reuse = (
            getattr(self, "_rendered_paths", None) == self._image_paths
            and self._rendered_paths is not None
            and hasattr(self, "main_image_label")
            and self.main_image_label.winfo_exists()
            and hasattr(self, "thumb_canvas")
            and self.thumb_canvas.winfo_exists()
            and len(getattr(self, "_thumb_cards", [])) == len(self._image_paths)
            and all(c and c.winfo_exists() for c in self._thumb_cards)
        )

        active_border_color = "#3b6934"
        inactive_border_color = "#c4c7c7"

        if can_reuse:
            main_path = self._image_paths[self._current_image_index]
            self.main_image_label.config(image="", text="Loading image...")
            self._load_image_async(main_path, large=True, target_widget=self.main_image_label)
            self.main_image_label.bind("<Double-Button-1>", lambda e, p=main_path: self.open_image_web(p))

            active_card = None
            for i, card in enumerate(self._thumb_cards):
                is_active = (i == self._current_image_index)
                border_size = 2 if is_active else 1
                current_border = active_border_color if is_active else inactive_border_color
                card.config(highlightthickness=border_size, highlightbackground=current_border)
                if is_active:
                    active_card = card

            if active_card:
                self.thumb_canvas.update_idletasks()
                if active_card.winfo_exists() and self.thumb_canvas.winfo_exists():
                    card_x = active_card.winfo_x()
                    card_w = active_card.winfo_width()
                    canvas_w = self.thumb_canvas.winfo_width()
                    scroll_region = self.thumb_canvas.bbox("all")
                    if scroll_region:
                        total_w = scroll_region[2] - scroll_region[0]
                        if total_w > canvas_w:
                            if card_x + card_w > self.thumb_canvas.canvasx(canvas_w):
                                target_x = card_x + card_w - canvas_w + sc(8)
                                self.thumb_canvas.xview_moveto(target_x / total_w)
                            elif card_x < self.thumb_canvas.canvasx(0):
                                target_x = card_x - sc(8)
                                self.thumb_canvas.xview_moveto(target_x / total_w)
            return

        for w in self.image_container.winfo_children():
            w.destroy()

        if not self._image_paths:
            self._rendered_paths = None
            self._thumb_cards = []
            return

        main_path = self._image_paths[self._current_image_index]
        bg_color = "#ffffff"
        strip_bg = "#f3f3f3"
        border_color = "#d1d1d1"

        gallery_container = tk.Frame(
            self.image_container,
            bg=bg_color,
            highlightthickness=1,
            highlightbackground=border_color
        )
        gallery_container.pack(fill="both", expand=True, padx=sc(16), pady=sc(16))

        main_image_container = tk.Frame(gallery_container, bg=bg_color)
        main_image_container.pack(side="top", fill="both", expand=True)

        self.main_image_label = tk.Label(main_image_container, text="Loading image...", bg=bg_color)
        self.main_image_label.pack(fill="both", expand=True)

        self.main_image_label.bind("<ButtonPress-1>", self._on_pan_start)
        self.main_image_label.bind("<B1-Motion>", self._on_pan_drag)
        self.main_image_label.bind("<Double-Button-1>", lambda e, p=main_path: self.open_image_web(p))

        self._load_image_async(main_path, large=True, target_widget=self.main_image_label)

        controls_overlay = tk.Frame(
            main_image_container,
            bg="#1a1a1a",
            highlightthickness=1,
            highlightbackground="#333333"
        )
        controls_overlay.place(relx=1.0, rely=1.0, anchor="se", x=sc(-16), y=sc(-16))

        def _overlay_btn(text, cmd):
            btn = tk.Button(
                controls_overlay,
                text=text,
                command=cmd,
                bg="#1a1a1a",
                fg="#ffffff",
                activebackground="#333333",
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                font=("Segoe UI", sc(9), "bold"),
                padx=sc(10),
                pady=sc(5),
                cursor="hand2"
            )
            btn.pack(side="left", padx=sc(1))
            btn.bind("<Enter>", lambda e: btn.config(bg="#333333"))
            btn.bind("<Leave>", lambda e: btn.config(bg="#1a1a1a"))
            return btn

        _overlay_btn("+", self.zoom_image_in)
        _overlay_btn("-", self.zoom_image_out)
        _overlay_btn("↻", self.rotate_image)
        _overlay_btn("RESET", self.reset_image_view)

        thumbnail_strip = tk.Frame(
            gallery_container,
            bg=strip_bg,
            height=sc(108),
            highlightthickness=1,
            highlightcolor=border_color,
            highlightbackground=border_color
        )
        thumbnail_strip.pack(side="bottom", fill="x")
        thumbnail_strip.pack_propagate(False)

        self.thumb_canvas = tk.Canvas(
            thumbnail_strip,
            bg=strip_bg,
            highlightthickness=0,
            height=sc(90)
        )
        self.thumb_scrollbar = ttk.Scrollbar(
            thumbnail_strip,
            orient="horizontal",
            command=self.thumb_canvas.xview
        )
        self.thumb_canvas.configure(xscrollcommand=self.thumb_scrollbar.set)

        self.thumb_canvas.pack(side="top", fill="x", expand=True)
        self.thumb_scrollbar.pack(side="bottom", fill="x")

        thumb_inner = tk.Frame(self.thumb_canvas, bg=strip_bg)
        self.thumb_canvas.create_window((0, 0), window=thumb_inner, anchor="nw")

        thumb_inner.bind(
            "<Configure>",
            lambda e: self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))
        )

        active_card = None
        self._thumb_cards = []

        for i, path in enumerate(self._image_paths):
            is_active = (i == self._current_image_index)
            border_size = 2 if is_active else 1
            current_border = active_border_color if is_active else inactive_border_color

            card = tk.Frame(
                thumb_inner,
                bg="#ffffff",
                highlightthickness=border_size,
                highlightbackground=current_border
            )
            card.pack(side="left", padx=sc(6), pady=sc(6))
            self._thumb_cards.append(card)

            if is_active:
                active_card = card

            thumb = tk.Label(
                card,
                text="...",
                bg="#ffffff",
                cursor="hand2"
            )
            thumb.pack(padx=2, pady=2)

            thumb.bind("<Button-1>", lambda e, idx=i: self._set_main_image(idx))
            thumb.bind("<Double-Button-1>", lambda e, p=path: self.open_image_web(p))

            if not is_active:
                def _make_hover_handlers(c_card=card, border_c=inactive_border_color):
                    def _on_enter(event):
                        c_card.config(highlightbackground="#000000")
                    def _on_leave(event):
                        c_card.config(highlightbackground=border_c)
                    return _on_enter, _on_leave

                h_enter, h_leave = _make_hover_handlers()
                thumb.bind("<Enter>", h_enter)
                thumb.bind("<Leave>", h_leave)

            self._load_image_async(path, large=False, target_widget=thumb)

        def _on_thumb_scroll(event):
            self.thumb_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        self.thumb_canvas.bind("<MouseWheel>", _on_thumb_scroll)
        if hasattr(self, "thumb_frame") and self.thumb_frame:
            self.thumb_frame.bind("<MouseWheel>", _on_thumb_scroll)

        if active_card:
            self.thumb_canvas.update_idletasks()
            if active_card.winfo_exists() and self.thumb_canvas.winfo_exists():
                card_x = active_card.winfo_x()
                card_w = active_card.winfo_width()
                canvas_w = self.thumb_canvas.winfo_width()
                scroll_region = self.thumb_canvas.bbox("all")
                if scroll_region:
                    total_w = scroll_region[2] - scroll_region[0]
                    if total_w > canvas_w:
                        if card_x + card_w > self.thumb_canvas.canvasx(canvas_w):
                            target_x = card_x + card_w - canvas_w + sc(8)
                            self.thumb_canvas.xview_moveto(target_x / total_w)
                        elif card_x < self.thumb_canvas.canvasx(0):
                            target_x = card_x - sc(8)
                            self.thumb_canvas.xview_moveto(target_x / total_w)

        self._rendered_paths = self._image_paths

    def _set_main_image(self, idx):
        self._current_image_index = idx
        self._render_image_gallery()

    def _next_image(self):
        if not self._image_paths:
            return
        self._current_image_index = (self._current_image_index + 1) % len(self._image_paths)
        self._render_image_gallery()

    def _prev_image(self):
        if not self._image_paths:
            return
        self._current_image_index = (self._current_image_index - 1) % len(self._image_paths)
        self._render_image_gallery()

    # -------------------------------------------------------------------------
    # Zoom, Rotation & Panning Logic
    # -------------------------------------------------------------------------

    def zoom_image_in(self):
        self.image_zoom_factor *= 1.25
        self._re_render_current_images()

    def zoom_image_out(self):
        self.image_zoom_factor /= 1.25
        if self.image_zoom_factor < 0.1:
            self.image_zoom_factor = 0.1
        self._re_render_current_images()

    def rotate_image(self, angle=-90):
        self.image_rotation_angle = (self.image_rotation_angle + angle) % 360
        self._re_render_current_images()

    def reset_image_view(self):
        self.image_zoom_factor = 1.0
        self.image_rotation_angle = 0
        self._re_render_current_images()

    def fit_image_view(self):
        self.reset_image_view()

    def _re_render_current_images(self):
        if hasattr(self, "image_toolbar") and hasattr(self.image_toolbar, "set_status"):
            self.image_toolbar.set_status(self.image_zoom_factor, self.image_rotation_angle)

        curr_oid = getattr(self.app, "current_object_id", None) if self.app else None
        if not curr_oid:
            return

        try:
            old_y = self.image_canvas.yview()[0]
        except Exception:
            old_y = 0.0

        if getattr(self, "_image_paths", None):
            current_paths = set(self._image_paths)
            for k in list(self.image_render_cache):
                if k[0] in current_paths:
                    del self.image_render_cache[k]
        else:
            self.image_render_cache.clear()

        if getattr(self, "_image_paths", None):
            if self.image_view_mode == "gallery":
                self._render_image_gallery()
            else:
                self._render_image_stack()

            def restore_scroll():
                try:
                    self.image_canvas.yview_moveto(old_y)
                except Exception:
                    pass
            self.root.after(50, restore_scroll)
        else:
            self.load_images(curr_oid)

    def refresh_image_view(self):
        curr_oid = getattr(self.app, "current_object_id", None) if self.app else None
        if curr_oid:
            self.load_images(curr_oid)

    def refresh_image_rendering(self):
        if hasattr(self, "image_render_cache"):
            self.image_render_cache.clear()
        self.refresh_image_view()

    def _on_pan_start(self, event):
        canvas_x = event.x_root - self.image_canvas.winfo_rootx()
        canvas_y = event.y_root - self.image_canvas.winfo_rooty()
        self._pan_start_x = event.x_root
        self._pan_start_y = event.y_root
        self._has_dragged = False
        self.image_canvas.scan_mark(canvas_x, canvas_y)

    def _on_pan_drag(self, event):
        dist = ((event.x_root - self._pan_start_x)**2 + (event.y_root - self._pan_start_y)**2)**0.5
        if dist > 5:
            self._has_dragged = True
        canvas_x = event.x_root - self.image_canvas.winfo_rootx()
        canvas_y = event.y_root - self.image_canvas.winfo_rooty()
        self.image_canvas.scan_dragto(canvas_x, canvas_y, gain=1)

    def _on_pan_release(self, event, click_callback=None):
        if not getattr(self, "_has_dragged", False) and click_callback:
            click_callback(event)

    def open_image_popup(self, tk_img, source=None, is_online=False):
        from ui.dialogs import ZoomableImagePopup
        ZoomableImagePopup(self.root, tk_img, source, is_online)

    def open_image_web(self, path_or_url):
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            webbrowser.open(path_or_url)
        else:
            filename = os.path.basename(path_or_url)
            webbrowser.open(f"https://www.unimus.no/photos/image/jpeg/{filename}")



    def _preload_adjacent_images(self, oid):
        if not self.show_images_var.get():
            return
        if self.image_mode != "folder" or not self.app.config or not self.app.config.get("has_images", True):
            return

        if oid not in self.app.active_object_ids:
            return

        idx = self.app.active_object_ids.index(oid)
        adjacent_oids = []
        if idx > 0:
            adjacent_oids.append(self.app.active_object_ids[idx - 1])
        if idx < len(self.app.active_object_ids) - 1:
            adjacent_oids.append(self.app.active_object_ids[idx + 1])

        paths_to_load = []
        for adj_oid in adjacent_oids:
            adj_paths = self.image_index.get(adj_oid, [])
            if adj_paths:
                first_path = adj_paths[0][1] if isinstance(adj_paths[0], tuple) else adj_paths[0]
                if first_path not in self.image_cache:
                    paths_to_load.append(first_path)

        if not paths_to_load:
            return

        def preload_worker():
            try:
                available_width = self.image_canvas.winfo_width()
                if available_width < 300:
                    available_width = 800
                max_width = int((available_width / 2) * 0.95)
                max_height = int(self.root.winfo_height() * 0.85)
            except Exception:
                max_width, max_height = 400, 400

            for path in paths_to_load:
                try:
                    img = Image.open(path)
                    img.load()
                    img.thumbnail((max_width, max_height), Image.LANCZOS)
                    self.root.after(0, lambda p=path, im=img: self._cache_preloaded_image(p, im))
                except Exception:
                    pass

        threading.Thread(target=preload_worker, daemon=True).start()


    def _cache_preloaded_image(self, path, pil_img):
        if path in self.image_cache:
            return
        try:
            tk_img = ImageTk.PhotoImage(pil_img)
            self.image_cache[path] = tk_img
            if len(self.image_cache) > MAX_IMAGE_CACHE:
                self.image_cache.popitem(last=False)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Standalone Test Harness
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Image Panel - Standalone Test Harness")
    root.geometry("900x650")

    ctrl_bar = tk.Frame(root, bg="#eaeaea", pady=8, padx=12)
    ctrl_bar.pack(fill="x", side="top")

    tk.Label(ctrl_bar, text="IMAGE PANEL HARNESS", font=("JetBrains Mono", 10, "bold"), bg="#eaeaea").pack(side="left", padx=(0, 10))

    panel_container = tk.Frame(root, bg="#fbfaf8")
    panel_container.pack(fill="both", expand=True, padx=12, pady=12)

    image_panel = ImagePanel(panel_container)
    image_panel.pack(fill="both", expand=True)

    tk.Button(ctrl_bar, text="Open Source Settings", command=image_panel.open_image_menu).pack(side="right", padx=5)

    root.mainloop()
