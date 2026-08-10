import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from PIL import Image, ImageTk, ImageFile
from io import BytesIO

# Allow loading truncated images to prevent broken data stream errors
ImageFile.LOAD_TRUNCATED_IMAGES = True
from config import sc

MAX_IMAGE_CACHE = 40

class ImageHandlerMixin:
    def _next_image_shortcut(self, event=None):
        if self.image_mode != "folder":
            return
        self._next_image()


    def _prev_image_shortcut(self, event=None):
        if self.image_mode != "folder":
            return
        self._prev_image()


    def toggle_image_view(self):
        if self.image_view_mode == "gallery":
            self.image_view_mode = "stack"
        else:
            self.image_view_mode = "gallery"

        self.view_btn.config(text=f"View: {self.image_view_mode}")

        if self.app.current_object_id:
            self.load_images(self.app.current_object_id)


    def update_image_view_button(self):

        if self.image_mode == "folder":
            if not self.view_btn.winfo_ismapped():
                self.view_btn.pack(side="right")
        else:
            self.view_btn.pack_forget()

        if self.image_mode == "offline":
            if str(self.middle_frame) in self.panes.panes():
                self.panes.forget(self.middle_frame)
        else:
            if str(self.middle_frame) not in self.panes.panes():
                self.panes.insert(1, self.middle_frame, weight=3)


    def _bind_image_scroll(self):
        self.image_canvas.bind("<Enter>", lambda e: self.image_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.image_canvas.bind("<Leave>", lambda e: self.image_canvas.unbind_all("<MouseWheel>"))


    def _on_mousewheel(self, event):
        self.image_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


    def _on_canvas_resize(self, event):
        self._last_canvas_width = event.width

        # Debounce image container resizing and image refresh on resize so it doesn't lag while dragging sashes
        if hasattr(self, "_image_resize_job") and self._image_resize_job:
            try:
                self.root.after_cancel(self._image_resize_job)
            except Exception:
                pass
        self._image_resize_job = self.root.after(150, self._refresh_images_on_resize)


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

        # Current Mode Display
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

        # Action buttons
        def run_action(cmd):
            win.destroy()
            cmd()

        ttk.Button(
            frame,
            text="Select Local Image Folder...",
            command=lambda: run_action(self.select_image_folder)
        ).pack(fill="x", pady=2)

        ttk.Button(
            frame,
            text="Load from Online Repository",
            command=lambda: run_action(self.enable_online_images)
        ).pack(fill="x", pady=2)

        ttk.Button(
            frame,
            text="Disable Images (Offline Mode)",
            command=lambda: run_action(self.enable_offline_mode)
        ).pack(fill="x", pady=2)

        # Close button in footer
        footer = ttk.Frame(frame)
        footer.pack(fill="x", side="bottom", pady=(10, 0))

        ttk.Button(
            footer,
            text="Close",
            command=win.destroy
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
        self.image_index = {}  # ikke brukt, men tÃ¸mmes

        self.data_status.config(text="Online image mode enabled")

        # reload current object
        if self.app.current_object_id:
            self.load_images(self.app.current_object_id)


    def select_image_folder(self):
        folder = filedialog.askdirectory(title="Select image folder", initialdir=__import__("config").get_last_dir("last_image_dir"))
        if not folder:
            return
        __import__("config").set_last_dir("last_image_dir", folder)

        self.image_folder = folder

        threading.Thread(
            target=self.build_image_index,
            args=(folder,),
            daemon=True
        ).start()

        self.image_mode = "folder"
        self.update_image_view_button()

        if self.reg_entry_list:
            self.reg_entry_list[0].focus_set()


    def build_online_image_urls(self, oid):
        import config
        advanced_prefs = config.load_prefs().get("advanced", {})
        pattern_override = advanced_prefs.get("image_url_pattern_override", "").strip()
        
        if pattern_override:
            pattern = pattern_override
        else:
            pattern = self.app.config.get(
                "image_url_pattern",
                "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg"
            )
        if not pattern:
            return []

        suffixes = ["", "-01", "-02", "-03"]
        urls = []
        for s in suffixes:
            if "{id}" in pattern:
                url = pattern.replace("{id}", f"{oid}{s}")
            elif "{num" in pattern and "{suffix}" in pattern:
                try:
                    num = int(oid)
                    url = pattern.format(num=num, suffix=s)
                except Exception:
                    url = f"{pattern.rstrip('/')}/{oid}{s}"
            else:
                url = f"{pattern}{oid}{s}"
            urls.append(url)
        return urls


    def build_image_index(self, folder):
        import re

        self.image_index = {}

        image_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}



        files = []
        for root_dir, _, filenames in os.walk(folder):
            for fname in filenames:
                files.append(os.path.join(root_dir, fname))



        total = len(files)

        self.root.after(0, lambda: self._show_progress("Indexing images...", total))


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

            full_path = path

            self.image_index.setdefault(oid, []).append((img_no, full_path))

            # progress
            if i % 50 == 0:
                self.root.after(
                    0,
                    self.image_scan_progress.configure,
                    {"value": i, "maximum": total}
                )


        for oid in self.image_index:
            self.image_index[oid].sort(key=lambda x: x[0])
            self.image_index[oid] = [p for _, p in self.image_index[oid]]


        # PERFORMANCE OPTIMIZATION (Bolt): Vectorized check for 'Images_Missing' on the whole DataFrame index
        # directly in the background thread, eliminating slow main-thread loops of .at/loc assignments.
        if self.app.df_obs is not None:
            has_img = self.app.df_obs.index.astype(str).isin(found_object_ids)
            self.app.df_obs["Images_Missing"] = ~has_img

        self.app.dirty = True

        def _notify_ui():
            self._problem_cache.clear()
            self.refresh_list()
            # Use _on_startup_ready() instead of _hide_progress("Ready") directly.
            # During startup, this ensures the LoadingWindow is dismissed only after
            # both the image scan AND the first load_object() call have completed.
            # Outside startup (no LoadingWindow), _on_startup_ready just calls
            # _hide_progress("Ready") which behaves identically to the old code.
            self._on_startup_ready()

        self.root.after(0, _notify_ui)


    def _apply_image_updates(self, updates):
        for oid, val in updates:
            self.app.df_obs.at[oid, "Images_Missing"] = val


    def load_images(self, oid):
        self._update_image_controls_visibility()
        if not self.show_images_var.get():
            return


        self._image_index = 0
        self.image_container.update_idletasks()
        self.image_container.after(0, lambda: None)  # flush UI queue


        if not self.app.config or not self.app.config.get("has_images", True):
            return

        if self.image_mode == "offline":

            for w in self.image_container.winfo_children():
                if w != self.no_image_label:
                    w.destroy()


            if hasattr(self, "no_image_label") and self.no_image_label.winfo_exists():
                self.no_image_label.pack_forget()



            self.no_image_label.pack_forget()

            self.images_missing_label.config(
                text="Offline mode active (images disabled)"
            )
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



        paths = self.image_index.get(oid, [])


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

        return


    def _load_image_async(self, path, large, target_widget, token=None):
        if token is None:
            token = getattr(self, "_image_load_token", 0)

        # Cache key includes zoom and rotation details for large images
        key = (path, large, self.image_zoom_factor if large else 1.0, self.image_rotation_angle if large else 0)

        if key in self.image_render_cache:
            self.image_render_cache.move_to_end(key)
            tk_img = self.image_render_cache[key]
            if target_widget.winfo_exists():
                target_widget.config(image=tk_img, text="")
                target_widget.image = tk_img
            return

        # Track the active path on the widget to prevent race conditions
        target_widget.loading_path = path

        # Compute sizing arguments on the main thread before starting the background thread
        # because calling winfo methods in worker threads is not thread-safe.
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
        dpi_scale = getattr(self, "_scale", 1.0)

        def worker():
            try:
                # Check token before doing heavy work
                if token != getattr(self, "_image_load_token", 0):
                    return

                # Load original PIL image
                if path not in self.original_pil_cache:
                    self.original_pil_cache[path] = Image.open(path)
                    if len(self.original_pil_cache) > 40:
                        self.original_pil_cache.popitem(last=False)

                img = self.original_pil_cache[path].copy()

                # Get advanced settings resampling algorithm
                import config
                advanced_prefs = config.load_prefs().get("advanced", {})
                algo_name = advanced_prefs.get("image_resampling_algorithm", "LANCZOS (High Quality)")
                if "BILINEAR" in algo_name:
                    resample_filter = Image.BILINEAR
                elif "NEAREST" in algo_name:
                    resample_filter = Image.NEAREST
                else:
                    resample_filter = Image.LANCZOS

                # Apply rotation
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
                    # Modern square thumbnails centered and scaled by DPI scale factor
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

    def _render_image_stack(self):
        self._update_image_controls_visibility()

        for w in self.image_container.winfo_children():
            w.destroy()

        if not self._image_paths:
            return

        for path in self._image_paths:
            frame = ttk.Frame(self.image_container)
            frame.pack(pady=10)

            lbl = ttk.Label(frame, text="Loading image...")
            lbl.pack()

            lbl.bind("<ButtonPress-1>", self._on_pan_start)
            lbl.bind("<B1-Motion>", self._on_pan_drag)

            lbl.bind(
                "<Double-Button-1>",
                lambda e, p=path: self.open_image_web(p)
            )

            self._load_image_async(path, large=True, target_widget=lbl)

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

        active_border_color = "#3b6934" # secondary green
        inactive_border_color = "#c4c7c7"

        if can_reuse:
            # 1. Update main image and bind
            main_path = self._image_paths[self._current_image_index]
            self.main_image_label.config(image="", text="Loading image...")
            self._load_image_async(main_path, large=True, target_widget=self.main_image_label)
            self.main_image_label.bind("<Double-Button-1>", lambda e, p=main_path: self.open_image_web(p))

            # 2. Update border highlight/thickness on the existing thumbnail cards
            active_card = None
            for i, card in enumerate(self._thumb_cards):
                is_active = (i == self._current_image_index)
                border_size = 2 if is_active else 1
                current_border = active_border_color if is_active else inactive_border_color
                card.config(highlightthickness=border_size, highlightbackground=current_border)
                if is_active:
                    active_card = card

            # 3. Handle Auto-Scroll
            if active_card:
                self.thumb_canvas.update_idletasks()
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

        # Stitch-style colors (Light Mode priority, ignore Dark Mode configuration)
        bg_color = "#ffffff"       # surface-container-lowest
        strip_bg = "#f3f3f3"       # surface-container-low
        border_color = "#d1d1d1"   # outline-variant

        # Main Gallery Container Frame with 1px border and margins
        gallery_container = tk.Frame(
            self.image_container,
            bg=bg_color,
            highlightthickness=1,
            highlightbackground=border_color
        )
        gallery_container.pack(fill="both", expand=True, padx=sc(16), pady=sc(16))

        # Main Large Image Container (Top portion)
        main_image_container = tk.Frame(gallery_container, bg=bg_color)
        main_image_container.pack(side="top", fill="both", expand=True)

        # Centered label for the main large image (initially Loading)
        self.main_image_label = tk.Label(main_image_container, text="Loading image...", bg=bg_color)
        self.main_image_label.pack(fill="both", expand=True)

        # Bind zoom/pan and double-click web actions
        self.main_image_label.bind("<ButtonPress-1>", self._on_pan_start)
        self.main_image_label.bind("<B1-Motion>", self._on_pan_drag)
        self.main_image_label.bind("<Double-Button-1>", lambda e, p=main_path: self.open_image_web(p))

        self._load_image_async(main_path, large=True, target_widget=self.main_image_label)

        # Floating Viewer Controls Overlay HUD in the bottom-right corner
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

        # Thumbnail Strip (Bottom portion)
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

        # Horizontal Scrollable Canvas
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

        # Inner frame inside the scrollable canvas
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

            # Card element containing thumbnail
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

            # Hover animations for inactive cards
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

        # Bind horizontal mousewheel scrolling on the thumbnail strip
        def _on_thumb_scroll(event):
            self.thumb_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        self.thumb_canvas.bind("<Enter>", lambda e: self.thumb_canvas.bind_all("<MouseWheel>", _on_thumb_scroll))
        self.thumb_canvas.bind("<Leave>", lambda e: self.thumb_canvas.unbind_all("<MouseWheel>"))

        # Keyboard Navigation Auto-Scroll logic
        if active_card:
            self.thumb_canvas.update_idletasks()
            card_x = active_card.winfo_x()
            card_w = active_card.winfo_width()
            canvas_w = self.thumb_canvas.winfo_width()

            scroll_region = self.thumb_canvas.bbox("all")
            if scroll_region:
                total_w = scroll_region[2] - scroll_region[0]
                if total_w > canvas_w:
                    # If active thumbnail card is scrolled off-screen to the right
                    if card_x + card_w > self.thumb_canvas.canvasx(canvas_w):
                        target_x = card_x + card_w - canvas_w + sc(8)
                        self.thumb_canvas.xview_moveto(target_x / total_w)
                    # If active thumbnail card is scrolled off-screen to the left
                    elif card_x < self.thumb_canvas.canvasx(0):
                        target_x = card_x - sc(8)
                        self.thumb_canvas.xview_moveto(target_x / total_w)

        self._rendered_paths = self._image_paths


    def _update_image_controls_visibility(self):
        # Hide standard top toolbar in Offline and Online modes, or Local Gallery view.
        # It is only shown in Local Stack view.
        if hasattr(self, "image_toolbar") and self.image_toolbar.winfo_exists():
            if self.image_mode == "folder" and self.image_view_mode == "stack":
                # Only show top toolbar in local folder mode when using stack view
                self.image_toolbar.pack_forget()
                self.image_toolbar.pack(fill="x", padx=6, pady=(0, 2), before=self.image_box)
            else:
                self.image_toolbar.pack_forget()

        # Manage floating HUD overlay controls
        if self.image_mode == "online":
            # If in Online Mode, show the floating HUD overlay placed on self.image_box
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

            # Reposition/pack HUD over the scroll view
            self.image_hud.place(relx=1.0, rely=1.0, anchor="se", x=sc(-24), y=sc(-24))
        else:
            # Hide the HUD in Offline Mode and Local Folder Mode
            if hasattr(self, "image_hud") and self.image_hud.winfo_exists():
                self.image_hud.place_forget()


    def _get_image_for_display(self, path, large=False):
        # Cache key includes zoom and rotation details for large images
        key = (path, large, self.image_zoom_factor if large else 1.0, self.image_rotation_angle if large else 0)


        if key in self.image_render_cache:
            self.image_render_cache.move_to_end(key)
            return self.image_render_cache[key]

        # Cache original PIL image
        if path not in self.original_pil_cache:
            self.original_pil_cache[path] = Image.open(path)
            if len(self.original_pil_cache) > 40:
                self.original_pil_cache.popitem(last=False)

        img = self.original_pil_cache[path].copy()

        # Apply rotation (large only)
        if large and self.image_rotation_angle != 0:
            img = img.rotate(self.image_rotation_angle, expand=True)

        self.root.update_idletasks()
        width = self.image_canvas.winfo_width()
        height = self.image_canvas.winfo_height()
        if width < 300:
            width = 800
        canvas_h = height if height > 150 else 350

        import config
        advanced_prefs = config.load_prefs().get("advanced", {})
        algo_name = advanced_prefs.get("image_resampling_algorithm", "LANCZOS (High Quality)")
        if "BILINEAR" in algo_name:
            resample_filter = Image.BILINEAR
        elif "NEAREST" in algo_name:
            resample_filter = Image.NEAREST
        else:
            resample_filter = Image.LANCZOS

        if large:
            max_width = int(width * 0.95 * self.image_zoom_factor)
            max_height = int(canvas_h * 0.85 * self.image_zoom_factor)

            if max_width > 0 and max_height > 0:
                img_w, img_h = img.size
                ratio = min(max_width / img_w, max_height / img_h)
                new_w = int(img_w * ratio)
                new_h = int(img_h * ratio)
                if new_w > 0 and new_h > 0:
                    img = img.resize((new_w, new_h), resample_filter)
        else:
            # Modern square thumbnails centered and scaled by DPI scale factor
            size = int(sc(70))
            img_w, img_h = img.size
            min_dim = min(img_w, img_h)
            left = (img_w - min_dim) / 2
            top = (img_h - min_dim) / 2
            right = (img_w + min_dim) / 2
            bottom = (img_h + min_dim) / 2
            img = img.crop((left, top, right, bottom))
            img = img.resize((size, size), resample_filter)


        tk_img = ImageTk.PhotoImage(img)
        self.image_render_cache[key] = tk_img


        if len(self.image_render_cache) > MAX_IMAGE_CACHE:
            self.image_render_cache.popitem(last=False)

        return tk_img


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


    def _load_online_images_worker(self, urls, token):

        def try_load(url, attempts=2):
            for _ in range(attempts):
                if token != self._image_load_token:
                    return None
                try:
                    r = self._get_http_session().get(url, timeout=5)
                    if r.status_code == 200:
                        return Image.open(BytesIO(r.content))
                except Exception:
                    # Connection errors (e.g. RemoteDisconnected) are expected when
                    # an image URL does not exist — silently skip to the next attempt.
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
            self.root.after(
                0,
                self._show_no_images_online
            )


    def _display_online_image(self, img, url, token):

        if token != self._image_load_token:
            return

        # Cache original online image
        if url not in self.original_pil_cache:
            self.original_pil_cache[url] = img.copy()
            if len(self.original_pil_cache) > 40:
                self.original_pil_cache.popitem(last=False)

        pil_img = self.original_pil_cache[url].copy()

        # Apply rotation
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

        # Click drag release panning & popup integration
        lbl.bind("<ButtonPress-1>", self._on_pan_start)
        lbl.bind("<B1-Motion>", self._on_pan_drag)
        lbl.bind(
            "<ButtonRelease-1>",
            lambda e, im=tk_img, u=url: self._on_pan_release(
                e,
                lambda ev: self.open_image_popup(im, source=u, is_online=True)
            )
        )


        lbl.bind("<Double-Button-1>", lambda e, u=url: __import__('webbrowser').open(u))


    def _load_images_worker(self, paths, token):
        self._image_total = len(paths)
        loaded_any = False

        for path in paths:
            if token != self._image_load_token:
                return

            try:
                if path in self.image_cache:
                    self.image_cache.move_to_end(path)
                    tk_img = self.image_cache[path]

                    self.root.after(
                        0,
                        lambda im=tk_img, p=path, t=token: self._add_image_to_ui(im, p, t)
                    )


                else:
                    img = Image.open(path)


                    self.root.update_idletasks()
                    available_width = self.image_canvas.winfo_width()

                    # fallback hvis UI ikke er klar
                    if available_width < 300:
                        available_width = 800

                    col_width = available_width // 2
                    if hasattr(self, "_image_mode_large_first") and self._image_mode_large_first:
                        if path == paths[0]:

                            max_width = int(available_width * 0.95)
                        else:

                            max_width = int((available_width / 2) * 0.9)
                    else:
                        max_width = int((available_width / 2) * 0.95)

                    max_height = int(self.root.winfo_height() * 0.85)

                    img.thumbnail((max_width, max_height), Image.LANCZOS)

                    self.root.after(
                        0,
                        lambda im=img.copy(), p=path, t=token: self._create_tk_image(im, p, t)
                    )

                loaded_any = True

            except Exception as e:
                self.root.after(0, lambda err=e: messagebox.showerror("Image error", str(err)))

        if not loaded_any and token == self._image_load_token:
            self.root.after(
                0,
                self._show_no_images_local
            )


    def _create_tk_image(self, pil_img, path, token):
        if token != self._image_load_token:
            return

        tk_img = ImageTk.PhotoImage(pil_img)
        self.image_cache[path] = tk_img


        if len(self.image_cache) > MAX_IMAGE_CACHE:
            self.image_cache.popitem(last=False)

        self._add_image_to_ui(tk_img, path, token)


    def _add_image_to_ui(self, tk_img, path, token):

        if token != self._image_load_token:
            return


        if not hasattr(self, "_image_index"):
            self._image_index = 0

        index = self._image_index
        self._image_index += 1

        total = self._image_total


        container = ttk.Frame(self.image_container)


        if total <= 2:
            row = 0
            col = index

            container.grid(
                row=row,
                column=col,
                padx=10,
                pady=10,
                sticky="n"
            )


        else:

            if index == 0:
                container.grid(
                    row=0,
                    column=0,
                    columnspan=2,
                    padx=10,
                    pady=10
                )

            else:

                new_index = index - 1

                row = (new_index // 2) + 1
                col = new_index % 2

                container.grid(
                    row=row,
                    column=col,
                    padx=8,
                    pady=8,
                    sticky="n"
                )

        filename = os.path.basename(path)

        ttk.Label(container, text=filename).pack()

        lbl = ttk.Label(container, image=tk_img)
        lbl.image = tk_img
        lbl.pack()


        lbl.bind(
            "<Double-Button-1>",
            lambda e, f=filename: __import__('webbrowser').open(
                f"https://www.unimus.no/photos/image/jpeg/{f}"
            )
        )

        ttk.Button(
            container,
            text="Open",
            command=lambda im=tk_img, p=path: self.open_image_popup(im, source=p, is_online=False)
        ).pack(pady=(4, 0))


    def open_image_popup(self, tk_img, source=None, is_online=False):
        from ui.dialogs import ZoomableImagePopup
        ZoomableImagePopup(self.root, tk_img, source, is_online)


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


    def zoom_image_in(self):
        self.image_zoom_factor *= 1.25
        self.refresh_image_view()


    def zoom_image_out(self):
        self.image_zoom_factor /= 1.25
        if self.image_zoom_factor < 0.1:
            self.image_zoom_factor = 0.1
        self.refresh_image_view()


    def rotate_image(self):
        self.image_rotation_angle = (self.image_rotation_angle - 90) % 360
        self.refresh_image_view()


    def reset_image_view(self):
        self.image_zoom_factor = 1.0
        self.image_rotation_angle = 0
        self.refresh_image_view()


    def refresh_image_view(self):
        if self.app.current_object_id:
            self.load_images(self.app.current_object_id)


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
