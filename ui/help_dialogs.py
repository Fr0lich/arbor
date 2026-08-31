import tkinter as tk
from tkinter import ttk, messagebox


def show_main_help(root):
    """Display the full Arbor System User Guide window."""
    from config import sc
    import utils

    message = (
        "ARBOR SYSTEM USER GUIDE\n\n"
        "1. WORKSPACE PANELS\n"
        " - Left Panel: Displays the list of objects. Use the search bar to find objects by ID, genus, or species.\n"
        " - Middle Panel: Displays the high-resolution images. Supports zoom/pan (mouse drag & scroll) and rotation.\n"
        " - Right Panel: The registration editor. Re-write or choose fields, flag/clear problem statuses, and save your changes.\n\n"
        "2. PROBLEM WORKFLOW\n"
        " - Fields with errors are flagged in red. Unmapped problems appear below the main fields.\n"
        " - Review historical databases by clicking the 'History' indicator when discrepancies occur.\n"
        " - Once problems are resolved, click 'Mark as Reviewed' at the bottom of the right panel.\n\n"
        "3. FOCUS & LAYOUT SETTINGS\n"
        " - Toggle panels or customize sashes from the View and Layout menus.\n"
        " - Focus mode hides sections or fields that you do not need, making it ideal for small laptop screens."
    )

    win = tk.Toplevel(root)
    win.title("User Guide")
    utils.center_and_fit_toplevel(win, 620, 700)
    win.bind("<Escape>", lambda e: win.destroy())

    canvas = tk.Canvas(win)
    sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
    frame = ttk.Frame(canvas, padding=16)
    frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=frame, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    txt = tk.Text(
        frame,
        wrap="word",
        width=72,
        height=40,
        font=("Consolas", sc(9)),
        relief="flat",
        bg=win.cget("bg"),
        state="normal"
    )
    txt.pack(fill="both", expand=True)
    txt.insert("1.0", message)
    txt.config(state="disabled")

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    win.protocol("WM_DELETE_WINDOW", lambda: (
        canvas.unbind_all("<MouseWheel>"), win.destroy()
    ))

    ttk.Button(win, text="Close", command=lambda: (
        canvas.unbind_all("<MouseWheel>"), win.destroy()
    ), cursor="hand2").pack(side="bottom", pady=8)


def show_quick_help():
    """Display the quick start shortcuts cheat sheet messagebox."""
    message = (
        "ARBOR KEYBOARD SHORTCUTS CHEAT SHEET\n\n"
        "Ctrl + S : Save session\n"
        "Ctrl + Q : Toggle Focus Mode\n"
        "Ctrl + G : Open Filter Menu\n"
        "Ctrl + H : Open Historical suggestions\n"
        "Ctrl + N : Create new blank Object\n"
        "Ctrl + Shift + N : Quick create new Object\n"
        "Ctrl + D : Duplicate current object\n"
        "Ctrl + Shift + P / F3 : Open editable Problem Flags window\n"
        "Ctrl + Shift + L / F4 : Open editable Location window\n"
        "Right Arrow / Left Arrow : Navigate Next / Prev object\n"
        "Down Arrow / Up Arrow : Navigate list rows"
    )
    messagebox.showinfo("Quick Start", message)


def show_about():
    """Display the About dialog."""
    messagebox.showinfo(
        "About arbor",
        "Arbor Botanical Database Management System\nVersion 1.2"
    )


def open_help_window(ui):
    """Display the Help Center dialog."""
    from config import sc
    import utils

    if hasattr(ui, "help_win") and ui.help_win and ui.help_win.winfo_exists():
        ui.help_win.focus_force()
        ui.help_win.focus_set()
        ui.help_win.lift()
        return

    win = tk.Toplevel(ui.root)
    ui.help_win = win
    win.title("Help Center")
    win.resizable(True, True)
    win.transient(ui.root)

    w_width = sc(400)
    w_height = sc(420)
    utils.center_and_fit_toplevel(win, w_width, w_height)

    is_dark = getattr(ui, "dark_mode_active", False)
    bg_color = "#181c19" if is_dark else "#f2f5f1"
    win.configure(background=bg_color)
    win.bind("<Escape>", lambda e: win.destroy())

    frame = ttk.Frame(win, padding=sc(16))
    frame.pack(fill="both", expand=True)

    lbl_header = ttk.Label(
        frame,
        text="HELP CENTER",
        font=("Segoe UI", sc(12), "bold"),
        foreground="#e8ebe9" if is_dark else "#2c302e"
    )
    lbl_header.pack(anchor="w", pady=(0, 10))

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 15))

    def run_help_cmd(cmd):
        win.destroy()
        cmd()

    def start_main_tutorial():
        from ui.tutorial import TutorialManager
        TutorialManager().start_tutorial("main_tutorial", ui.root, force=True)

    def start_startup_tutorial():
        from ui.tutorial import TutorialManager
        TutorialManager().start_tutorial("startup_tutorial", ui.root, force=True)

    def start_hr_tutorial():
        from ui.tutorial import TutorialManager
        TutorialManager().start_tutorial("historical_resolver", ui.root, force=True)

    options = [
        ("Interactive Tutorial", "Guided walkthrough of the main workspace.", start_main_tutorial),
        ("Startup Tutorial", "Guided walkthrough of the welcome screen.", start_startup_tutorial),
        ("Conflict Resolver Tutorial", "Guided walkthrough of the Historical Conflict Resolver.", start_hr_tutorial),
        ("User Guide", "Complete guide and detailed documentation.", lambda: show_main_help(ui.root)),
        ("Keyboard Shortcuts", "HUD cheat sheet for all keys and navigation.", lambda: show_shortcuts(ui)),
        ("Quick Start", "Basic shortcuts and workflow summary.", show_quick_help),
        ("About", "Application version and build details.", show_about)
    ]

    for name, desc, cmd in options:
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=sc(6))

        btn = ttk.Button(
            btn_frame,
            text=name,
            width=18,
            command=lambda c=cmd: run_help_cmd(c),
            style="Primary.TButton",
            cursor="hand2"
        )
        btn.pack(side="left", padx=(0, 10))

        lbl_desc = ttk.Label(
            btn_frame,
            text=desc,
            font=("Segoe UI", sc(8.5)),
            foreground="gray"
        )
        lbl_desc.pack(side="left", fill="x", expand=True)

    close_btn = ttk.Button(
        frame,
        text="Close",
        command=win.destroy,
        style="Tool.TButton",
        width=10,
        cursor="hand2"
    )
    close_btn.pack(side="bottom", pady=(15, 0))


def show_shortcuts(ui):
    """Create a searchable HUD dialog displaying all keyboard shortcuts."""
    from config import sc
    import utils

    win = tk.Toplevel(ui.root)
    win.title("Keyboard Shortcuts HUD")
    utils.center_and_fit_toplevel(win, 800, 650)

    is_dark = getattr(ui, "dark_mode_active", False)
    bg_color = "#181c19" if is_dark else "#f2f5f1"
    fg_title = "#e8ebe9" if is_dark else "#2c302e"
    fg_label = "#a6adc8" if is_dark else "#444748"
    fg_nomatch = "#c93a40" if is_dark else "#c93a40"
    fg_cat = "#89b4fa" if is_dark else "#1976d2"
    bg_key = "#11111b" if is_dark else "#e0e0e0"
    fg_key = "#f9e2af" if is_dark else "#000000"
    fg_desc = "#a6adc8" if is_dark else "#444748"
    fg_footer = "#585b70" if is_dark else "#757575"

    win.configure(background=bg_color)
    win.transient(ui.root)
    win.bind("<Escape>", lambda e: win.destroy())

    title_frame = tk.Frame(win, bg=bg_color)
    title_frame.pack(fill="x", padx=20, pady=(15, 10))

    tk.Label(
        title_frame,
        text="Keyboard Shortcuts Cheat Sheet",
        font=("Segoe UI", sc(16), "bold"),
        fg=fg_title,
        bg=bg_color
    ).pack(side="left")

    search_frame = tk.Frame(win, bg=bg_color)
    search_frame.pack(fill="x", padx=20, pady=(0, 15))

    tk.Label(
        search_frame,
        text="Search: ",
        font=("Segoe UI", sc(10), "bold"),
        fg=fg_label,
        bg=bg_color
    ).pack(side="left")

    search_var = tk.StringVar()
    search_ent = ttk.Entry(search_frame, textvariable=search_var, font=("Segoe UI", sc(10)))
    search_ent.pack(side="left", fill="x", expand=True, padx=(5, 0))
    search_ent.focus_set()

    content_outer = tk.Frame(win, bg=bg_color)
    content_outer.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    canvas = tk.Canvas(content_outer, bg=bg_color, highlightthickness=0)
    scrollbar = ttk.Scrollbar(content_outer, orient="vertical", command=canvas.yview)
    scroll_content = tk.Frame(canvas, bg=bg_color)

    scroll_content.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    window_id = canvas.create_window((0, 0), window=scroll_content, anchor="nw")
    canvas.bind(
        "<Configure>",
        lambda e: canvas.itemconfig(window_id, width=e.width) if getattr(canvas, "_last_width", None) != e.width and not setattr(canvas, "_last_width", e.width) else None
    )
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    shortcuts = [
        ("NAVIGATION", "Left / Right", "Previous / Next object"),
        ("NAVIGATION", "Enter", "Load typed ObjectID in search popup"),
        ("NAVIGATION", "Down", "Move to search results"),
        ("NAVIGATION", "Escape", "Close search popup"),
        ("NAVIGATION", "Alt+Left", "Go back in navigation history"),
        ("NAVIGATION", "Alt+Right", "Go forward in navigation history"),
        ("FOCUS", "Ctrl+F", "Jump to Search"),
        ("FOCUS", "Ctrl+O", "Jump to Object list"),
        ("FOCUS", "Ctrl+J", "Open Database Statistics"),
        ("FOCUS", "Ctrl+E / Ctrl+I", "Jump to first Registration field"),
        ("FOCUS", "Ctrl+L", "Jump to first Location field"),
        ("FOCUS", "Ctrl+P", "Jump to first Problem checkbox"),
        ("FOCUS", "Ctrl+Q", "Toggle Focus Mode"),
        ("FOCUS", "Shift+E", "Jump to first empty registration field"),
        ("LAPTOP LAYOUT", "F6", "Toggle Object List (Left Sidebar)"),
        ("LAPTOP LAYOUT", "F7", "Toggle Registration & Taxonomy (Center Panel)"),
        ("LAPTOP LAYOUT", "F8", "Toggle Images & Tools (Right Panel)"),
        ("CHECKBOXES", "Shift+Down", "Next problem checkbox"),
        ("CHECKBOXES", "Shift+Up", "Previous problem checkbox"),
        ("CHECKBOXES", "Space", "Toggle focused problem checkbox"),
        ("CHECKBOXES", "Return", "Toggle focused problem checkbox (in list)"),
        ("EDITING", "Ctrl+Z", "Undo last field or problem change"),
        ("EDITING", "Ctrl+Y", "Redo last change"),
        ("EDITING", "Ctrl+S", "Save session manually"),
        ("EDITING", "Ctrl+R", "Toggle 'Reviewed' status"),
        ("EDITING", "Ctrl+Shift+C", "Copy focused field value"),
        ("EDITING", "Ctrl+Shift+V", "Paste copied value to focused field"),
        ("OBJECT MANAGEMENT", "Ctrl+N", "New object popup"),
        ("OBJECT MANAGEMENT", "Ctrl+Shift+N", "Quick create new object"),
        ("OBJECT MANAGEMENT", "Ctrl+Shift+D", "Duplicate current object"),
        ("OBJECT MANAGEMENT", "Ctrl+Delete", "Delete current object"),
        ("HISTORY & TOOLS", "Ctrl+H", "Open historical suggestions resolver"),
        ("HISTORY & TOOLS", "Ctrl+G", "Open location/problem filter menu"),
        ("HISTORY & RESOLVER", "Ctrl+A", "Apply resolved changes (resolver window only)"),
        ("IMAGE NAVIGATION", "Shift+Left / Shift+Right", "Previous / Next image in gallery"),
        ("IMAGE NAVIGATION", "Double-click", "Open current image in external browser"),
        ("IMAGE NAVIGATION", "Mouse wheel", "Scroll image gallery"),
    ]

    def draw_shortcuts(filter_text=""):
        for w in scroll_content.winfo_children():
            w.destroy()

        categories = {}
        filter_lower = filter_text.lower()

        for cat, keys, desc in shortcuts:
            if filter_lower and filter_lower not in cat.lower() and filter_lower not in keys.lower() and filter_lower not in desc.lower():
                continue
            categories.setdefault(cat, []).append((keys, desc))

        if not categories:
            tk.Label(
                scroll_content,
                text="No shortcuts matched your search.",
                font=("Segoe UI", sc(11), "italic"),
                fg=fg_nomatch,
                bg=bg_color
            ).pack(pady=20)
            return

        for cat, items in categories.items():
            cat_frame = tk.Frame(scroll_content, bg=bg_color)
            cat_frame.pack(fill="x", pady=(10, 5), anchor="w")

            tk.Label(
                cat_frame,
                text=cat,
                font=("Segoe UI", sc(11), "bold"),
                fg=fg_cat,
                bg=bg_color
            ).pack(anchor="w", padx=5)

            grid_frame = tk.Frame(scroll_content, bg=bg_color)
            grid_frame.pack(fill="x", padx=15, pady=2, anchor="w")
            grid_frame.columnconfigure(0, minsize=220)
            grid_frame.columnconfigure(1, weight=1)

            for r, (keys, desc) in enumerate(items):
                key_container = tk.Frame(grid_frame, bg=bg_key, bd=1, relief="ridge", padx=6, pady=3)
                key_container.grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))

                tk.Label(
                    key_container,
                    text=keys,
                    font=("Consolas", sc(10), "bold"),
                    fg=fg_key,
                    bg=bg_key
                ).pack()

                tk.Label(
                    grid_frame,
                    text=desc,
                    font=("Segoe UI", sc(10)),
                    fg=fg_desc,
                    bg=bg_color,
                    wraplength=550,
                    justify="left"
                ).grid(row=r, column=1, sticky="w", pady=3)

    draw_shortcuts()
    search_var.trace_add("write", lambda *args: draw_shortcuts(search_var.get()))

    footer = tk.Frame(win, bg=bg_color)
    footer.pack(fill="x", side="bottom", pady=10, padx=20)

    tk.Label(
        footer,
        text="Press Escape to close this window.",
        font=("Segoe UI", sc(9), "italic"),
        fg=fg_footer,
        bg=bg_color
    ).pack(side="left")

    ttk.Button(
        footer,
        text="Close",
        command=win.destroy,
        cursor="hand2"
    ).pack(side="right")
