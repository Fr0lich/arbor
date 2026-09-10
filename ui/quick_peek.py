import tkinter as tk
from tkinter import ttk, messagebox
import config
from config import sc
from utils import debug_error
import pandas as pd
from backend.search import SearchEngine

class QuickPeekController:
    """Controller and UI builder for the Quick Peek dialog."""

    @staticmethod
    def open_quick_peek_menu(ui):
        """Open or lift the main Quick Peek dialog."""
        if hasattr(ui, "quick_peek_window") and ui.quick_peek_window and ui.quick_peek_window.winfo_exists():
            ui.quick_peek_window.lift()
            ui.quick_peek_window.focus_force()
            return

        COLORS = {
            "surface": "#fbfaf8",
            "surface_dim": "#dadada",
            "surface_container_low": "#f2f5f1",
            "surface_container_highest": "#e2e2e2",
            "on_surface": "#2c302e",
            "on_surface_variant": "#444748",
            "outline": "#747878",
            "outline_variant": "#c4c7c7",
            "primary": "#000000",
            "on_primary": "#ffffff",
            "secondary": "#3a7d44",
            "error": "#c93a40",
            "botanical_green": "#3e7b3e",
            "search_orange": "#d9480f",
            "surface_tint": "#5f5e5e"
        }

        FONT_HEADLINE = ("Hanken Grotesk", sc(14), "bold")
        FONT_LABEL = ("JetBrains Mono", sc(10), "bold")
        FONT_DATA = ("JetBrains Mono", sc(11))

        # Main window setup
        is_dark = getattr(ui, "dark_mode_active", False)
        if is_dark:
            COLORS.update({
                "surface": "#1e1e2d",
                "surface_dim": "#181825",
                "surface_container_low": "#11111b",
                "surface_container_highest": "#313244",
                "on_surface": "#cdd6f4",
                "on_surface_variant": "#a6adc8",
                "outline": "#6c7086",
                "outline_variant": "#585b70",
                "primary": "#cdd6f4",
                "on_primary": "#1e1e2d",
            })

        win = tk.Toplevel(ui.root)
        ui.quick_peek_window = win
        win.title("Quick Peek")
        win.geometry(f"{sc(1000)}x{sc(700)}")
        win.configure(bg=COLORS["surface"])
        win.transient(ui.root)  # Start modal-ish

        # Cleanup on close
        win.bind("<Destroy>", lambda e: setattr(ui, "quick_peek_window", None) if e.widget == win else None)

        # Header Frame
        header = tk.Frame(win, bg=COLORS["surface_container_low"], highlightthickness=1, highlightbackground=COLORS["outline_variant"])
        header.pack(fill="x", side="top")

        left_header = tk.Frame(header, bg=COLORS["surface_container_low"])
        left_header.pack(side="left", padx=sc(16), pady=sc(12))
        tk.Label(left_header, text="🔍 Quick Peek", font=FONT_HEADLINE, fg=COLORS["primary"], bg=COLORS["surface_container_low"]).pack(side="left")

        right_header = tk.Frame(header, bg=COLORS["surface_container_low"])
        right_header.pack(side="right", padx=sc(16), pady=sc(12))

        # Show image checkbox
        show_img_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            right_header, text="Show Image", variable=show_img_var,
            font=FONT_LABEL, bg=COLORS["surface_container_low"],
            fg=COLORS["on_surface"], selectcolor=COLORS["surface_container_low"],
            activebackground=COLORS["surface_container_low"],
            command=lambda: QuickPeekController._update_layout(ui, win, show_img_var)
        ).pack(side="left", padx=(0, sc(16)))

        # Popout Button
        is_popped_out = tk.BooleanVar(value=False)
        popout_btn = tk.Button(
            right_header, text="⇱ Pop-out", font=FONT_LABEL,
            fg=COLORS["on_surface"], bg=COLORS["surface_container_highest"],
            bd=0, relief="flat", cursor="hand2", padx=sc(8), pady=sc(4),
            command=lambda: QuickPeekController._toggle_popout(ui, win, is_popped_out, popout_btn, COLORS)
        )
        popout_btn.pack(side="left")

        # Main Layout: PanedWindow
        panes = ttk.Panedwindow(win, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=sc(8), pady=sc(8))

        # Left Pane: Search & Results
        left_pane = tk.Frame(panes, bg=COLORS["surface"])
        panes.add(left_pane, weight=1)

        search_frame = tk.Frame(left_pane, bg=COLORS["surface"], highlightthickness=1, highlightbackground=COLORS["outline_variant"])
        search_frame.pack(fill="x", pady=(0, sc(8)))

        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], bd=0, insertbackground=COLORS["primary"])
        search_entry.pack(side="left", fill="x", expand=True, padx=sc(8), pady=sc(6))
        search_entry.insert(0, "Search ID, Genus, Species...")
        search_entry.config(fg="gray")

        def _on_search_focus(e):
            if search_entry.get() == "Search ID, Genus, Species...":
                search_entry.delete(0, tk.END)
                search_entry.config(fg=COLORS["on_surface"])

        def _on_search_blur(e):
            if not search_entry.get().strip():
                search_entry.insert(0, "Search ID, Genus, Species...")
                search_entry.config(fg="gray")

        search_entry.bind("<FocusIn>", _on_search_focus)
        search_entry.bind("<FocusOut>", _on_search_blur)

        # Result listbox
        list_frame = tk.Frame(left_pane, bg=COLORS["surface"])
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        results_listbox = tk.Listbox(
            list_frame, font=FONT_DATA, bg=COLORS["surface_dim"], fg=COLORS["on_surface"],
            selectbackground=COLORS["secondary"], selectforeground=COLORS["on_primary"],
            yscrollcommand=scrollbar.set, bd=0, highlightthickness=0
        )
        results_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=results_listbox.yview)

        # Advanced Filters Frame (hidden by default)
        adv_filters_frame = tk.Frame(left_pane, bg=COLORS["surface_container_low"], highlightthickness=1, highlightbackground=COLORS["outline_variant"])
        # Do not pack initially

        # Add basic advanced filter entries (similar to main search)
        filter_vars = {}
        for f in ["Genus", "Species", "Collection"]:
            f_frame = tk.Frame(adv_filters_frame, bg=COLORS["surface_container_low"])
            f_frame.pack(fill="x", padx=sc(8), pady=sc(4))
            tk.Label(f_frame, text=f"{f}:", font=FONT_LABEL, bg=COLORS["surface_container_low"], fg=COLORS["on_surface"], width=10, anchor="w").pack(side="left")
            var = tk.StringVar()
            filter_vars[f] = var
            ent = tk.Entry(f_frame, textvariable=var, font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], bd=0, insertbackground=COLORS["primary"])
            ent.pack(side="left", fill="x", expand=True, padx=sc(4))

        ui.quick_peek_adv_filters = adv_filters_frame
        ui.quick_peek_filter_vars = filter_vars

        # Right Pane: Content (Data + Image)
        content_pane = ttk.Panedwindow(panes, orient="vertical")
        panes.add(content_pane, weight=3)

        # Data Container (Read-Only Fields)
        data_frame = tk.Frame(content_pane, bg=COLORS["surface_dim"])
        content_pane.add(data_frame, weight=1)

        data_scroll_canvas = tk.Canvas(data_frame, bg=COLORS["surface_dim"], highlightthickness=0)
        data_scrollbar = ttk.Scrollbar(data_frame, orient="vertical", command=data_scroll_canvas.yview)
        data_scroll_frame = tk.Frame(data_scroll_canvas, bg=COLORS["surface_dim"])

        data_scroll_frame.bind(
            "<Configure>",
            lambda e: data_scroll_canvas.configure(scrollregion=data_scroll_canvas.bbox("all"))
        )
        data_scroll_canvas.create_window((0, 0), window=data_scroll_frame, anchor="nw")
        data_scroll_canvas.configure(yscrollcommand=data_scrollbar.set)

        data_scrollbar.pack(side="right", fill="y")
        data_scroll_canvas.pack(side="left", fill="both", expand=True)

        # Image Container (Hidden by default)
        img_frame = tk.Frame(content_pane, bg=COLORS["surface_container_low"])
        ui.quick_peek_img_frame = img_frame
        ui.quick_peek_content_pane = content_pane

        # Bottom Footer
        footer = tk.Frame(win, bg=COLORS["surface_container_low"], highlightthickness=1, highlightbackground=COLORS["outline_variant"])
        footer.pack(fill="x", side="bottom")

        go_btn = tk.Button(
            footer, text="Go to Object ➔", font=FONT_LABEL,
            fg=COLORS["on_primary"], bg=COLORS["botanical_green"],
            bd=0, relief="flat", padx=sc(16), pady=sc(8), cursor="hand2",
            state="disabled",
            command=lambda: QuickPeekController._go_to_object(ui, win, results_listbox)
        )
        go_btn.pack(side="right", padx=sc(16), pady=sc(12))

        # Attach state to UI for callbacks
        ui.quick_peek_search_var = search_var
        ui.quick_peek_listbox = results_listbox
        ui.quick_peek_data_frame = data_scroll_frame
        ui.quick_peek_go_btn = go_btn
        ui.quick_peek_colors = COLORS
        ui.quick_peek_show_img_var = show_img_var

        # Setup search bindings
        def _debounce_search(*args):
            if hasattr(ui, "_qp_search_job") and ui._qp_search_job:
                ui.root.after_cancel(ui._qp_search_job)
            ui._qp_search_job = ui.root.after(250, lambda: QuickPeekController._perform_search(ui))

        search_var.trace_add("write", _debounce_search)
        for var in filter_vars.values():
            var.trace_add("write", _debounce_search)

        results_listbox.bind("<<ListboxSelect>>", lambda e: QuickPeekController._on_select(ui))

        # Initial search to populate list
        QuickPeekController._perform_search(ui)

    @staticmethod
    def _toggle_popout(ui, win, is_popped_out, btn, colors):
        if is_popped_out.get():
            # Revert to modal
            is_popped_out.set(False)
            win.transient(ui.root)
            btn.config(text="⇱ Pop-out", bg=colors["surface_container_highest"])
            ui.quick_peek_adv_filters.pack_forget()
        else:
            # Pop out
            is_popped_out.set(True)
            win.transient("") # Remove transient parent
            btn.config(text="⇲ Dock", bg=colors["outline_variant"])
            # Show advanced filters
            ui.quick_peek_adv_filters.pack(fill="x", side="top", before=ui.quick_peek_listbox.master)

        QuickPeekController._perform_search(ui)


    @staticmethod
    def _update_layout(ui, win, show_img_var):
        if not hasattr(ui, "quick_peek_content_pane") or not hasattr(ui, "quick_peek_img_frame"):
            return

        if show_img_var.get():
            ui.quick_peek_content_pane.add(ui.quick_peek_img_frame, weight=2)

            # Lazy load image panel
            if not hasattr(ui, "qp_image_panel"):
                from ui.image_panel import ImagePanel
                # Pass app and main_ui. It reads active object from app, so we might need a custom approach
                # Actually, ImagePanel relies heavily on main_ui state and app.current_object_id.
                # To make it truly independent, we would need to mock or isolate it.
                # For Quick Peek, a simpler image loader is safer to avoid breaking main_ui state.

                # Setup custom lightweight image viewer inside qp_img_frame
                lbl = tk.Label(ui.quick_peek_img_frame, text="Image loading...", bg=ui.quick_peek_colors["surface_container_low"])
                lbl.pack(fill="both", expand=True)
                ui.qp_image_label = lbl

            # Trigger load if something is selected
            QuickPeekController._on_select(ui)
        else:
            ui.quick_peek_content_pane.forget(ui.quick_peek_img_frame)

    @staticmethod
    def _perform_search(ui):
        if not hasattr(ui.app, "df_reg") or ui.app.df_reg is None or ui.app.df_reg.empty:
            return

        query = ui.quick_peek_search_var.get().strip().lower()
        if query == "search id, genus, species...":
            query = ""

        df = ui.app.df_reg

        # Apply advanced filters if visible
        if hasattr(ui, "quick_peek_adv_filters") and ui.quick_peek_adv_filters.winfo_ismapped():
            for f, var in ui.quick_peek_filter_vars.items():
                val = var.get().strip().lower()
                if val and f in df.columns:
                    mask = df[f].fillna("").astype(str).str.lower().str.contains(val, na=False, regex=False)
                    df = df[mask]

        if query:
            # Use search engine for universal query
            se = SearchEngine()
            idx = se.get_search_index(df, ui.app.config.get("reg_dict", {}))

            matched_oids = set()
            query_parts = query.split()
            for oid, tokens in idx.items():
                if all(any(q in t for t in tokens) for q in query_parts):
                    matched_oids.add(str(oid))

            mask = df.index.astype(str).isin(matched_oids)
            df = df[mask]

        # Limit to 500 for performance
        df = df.head(500)

        ui.quick_peek_listbox.delete(0, tk.END)
        ui.qp_results_oids = []

        for oid, row in df.iterrows():
            genus = str(row.get("Genus", "")).strip()
            species = str(row.get("Species", "")).strip()
            name = f"{genus} {species}".strip()
            if not name or name == "nan":
                name = "Unidentified Specimen"

            display_text = f"{oid} - {name}"
            ui.quick_peek_listbox.insert(tk.END, display_text)
            ui.qp_results_oids.append(oid)

        ui.quick_peek_go_btn.config(state="disabled")

    @staticmethod
    def _on_select(ui):
        sel = ui.quick_peek_listbox.curselection()
        if not sel:
            ui.quick_peek_go_btn.config(state="disabled")
            return

        idx = sel[0]
        oid = ui.qp_results_oids[idx]
        ui.qp_selected_oid = oid
        ui.quick_peek_go_btn.config(state="normal")

        # Render Data
        QuickPeekController._render_data(ui, oid)

        # Render Image if visible
        if ui.quick_peek_show_img_var.get():
            QuickPeekController._render_image(ui, oid)

    @staticmethod
    def _render_data(ui, oid):
        data_frame = ui.quick_peek_data_frame
        for w in data_frame.winfo_children():
            w.destroy()

        if not hasattr(ui.app, "df_reg") or oid not in ui.app.df_reg.index:
            return

        row = ui.app.df_reg.loc[oid]
        colors = ui.quick_peek_colors

        tk.Label(data_frame, text=f"Object ID: {oid}", font=("JetBrains Mono", sc(12), "bold"), bg=colors["surface_dim"], fg=colors["primary"]).grid(row=0, column=0, columnspan=2, sticky="w", padx=sc(8), pady=(sc(8), sc(16)))

        # Important fields to show in Quick Peek
        fields_to_show = [
            "Genus", "Species", "Subspecies", "Author", "Type_Status",
            "Collector", "Date", "Number",
            "Country", "State_Province", "County", "Locality",
            "Collection", "Geography", "Project", "Sex", "Stage", "Preparation_Type",
            "Building", "Floor", "Room", "Cabinet", "Shelf", "Box"
        ]

        r = 1
        for f in fields_to_show:
            if f in row:
                val = row[f]
                if pd.isna(val):
                    val = ""
                else:
                    val = str(val).strip()

                if val:
                    lbl_field = tk.Label(data_frame, text=f"{f}:", font=("JetBrains Mono", sc(10), "bold"), bg=colors["surface_dim"], fg=colors["on_surface_variant"], anchor="e", width=16)
                    lbl_field.grid(row=r, column=0, sticky="e", padx=(sc(8), sc(4)), pady=sc(2))

                    lbl_val = tk.Label(data_frame, text=val, font=("JetBrains Mono", sc(10)), bg=colors["surface_dim"], fg=colors["on_surface"], anchor="w", wraplength=sc(300), justify="left")
                    lbl_val.grid(row=r, column=1, sticky="w", padx=(0, sc(8)), pady=sc(2))
                    r += 1

    @staticmethod
    def _render_image(ui, oid):
        # Extremely simplified image loader for Quick Peek
        # Using PIL directly to avoid breaking ImagePanel state
        if not hasattr(ui, "qp_image_label") or not ui.qp_image_label.winfo_exists():
            return

        ui.qp_image_label.config(text="Loading...", image="")
        ui.qp_image_label.image = None

        def _load_bg():
            try:
                from PIL import Image, ImageTk
                import os, io, requests

                # Check local offline cache first
                local_path = None
                img_dir = getattr(ui.app.config, "offline_image_dir", None)
                if img_dir and os.path.exists(img_dir):
                    cache_dir = os.path.join(img_dir, str(oid))
                    if os.path.exists(cache_dir):
                        files = [f for f in os.listdir(cache_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                        if files:
                            local_path = os.path.join(cache_dir, files[0])

                # Check folder mode
                if not local_path and ui.image_mode == "folder":
                    if hasattr(ui, "image_index") and str(oid) in ui.image_index:
                        local_path = ui.image_index[str(oid)][0][1]

                img = None
                if local_path and os.path.exists(local_path):
                    img = Image.open(local_path)
                elif ui.image_mode in ("online", "offline"): # fallback to online
                    # Try to fetch
                    from ui.image_panel import ImagePanel
                    # Hacky way to get urls without instantiating ImagePanel fully
                    urls = ImagePanel.build_online_image_urls(ui, oid) # Passing ui as 'self' might fail if it uses self.app, but it does. Let's provide a mock
                    if not urls:
                        class MockApp: pass
                        mock = MockApp()
                        mock.app = ui.app
                        urls = ImagePanel.build_online_image_urls(mock, oid)

                    if urls:
                        try:
                            resp = requests.get(urls[0], stream=True, timeout=5)
                            if resp.status_code == 200:
                                img = Image.open(io.BytesIO(resp.content))
                        except:
                            pass

                if img:
                    img.thumbnail((400, 400), Image.Resampling.LANCZOS)

                    def _update_ui(image_to_load=img):
                        photo = ImageTk.PhotoImage(image_to_load)
                        ui.qp_image_label.config(image=photo, text="")
                        ui.qp_image_label.image = photo

                    ui.root.after(0, _update_ui)
                else:
                    ui.root.after(0, lambda: ui.qp_image_label.config(text="No Image Available"))
            except Exception as e:
                print(f"QuickPeek image err: {e}")
                ui.root.after(0, lambda: ui.qp_image_label.config(text="Error loading image"))

        import threading
        threading.Thread(target=_load_bg, daemon=True).start()

    @staticmethod
    def _go_to_object(ui, win, listbox):
        if not hasattr(ui, "qp_selected_oid"):
            return

        oid = ui.qp_selected_oid

        # Warn user
        resp = messagebox.askyesno(
            "Go to Object",
            f"Loading Object {oid} will clear your current search and filter in the main window.\n\nAre you sure?",
            parent=win
        )

        if resp:
            # Clear filters
            if hasattr(ui, "_clear_inline_search"):
                ui._clear_inline_search()
            if hasattr(ui, "_clear_filter_quick"):
                ui._clear_filter_quick()

            # Load object
            ui.load_object(oid)

            # Close Quick Peek
            win.destroy()
