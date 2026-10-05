import os
import sys
import re
import tkinter as tk
from tkinter import ttk, messagebox


def _render_markdown_to_text(txt_widget, md_text, is_dark=False):
    """Parses markdown text and inserts it into a Tkinter Text widget with rich tags."""
    from config import sc

    fg_text = "#e8ebe9" if is_dark else "#2c302e"
    fg_h1 = "#81c784" if is_dark else "#1b5e20"
    fg_h2 = "#a5d6a7" if is_dark else "#2e7d32"
    fg_h3 = "#c8e6c9" if is_dark else "#388e3c"
    fg_code = "#ff7b72" if is_dark else "#b33939"
    bg_code = "#2d333b" if is_dark else "#ebeff2"
    bg_block = "#1e242c" if is_dark else "#f3f5f4"
    fg_dim = "#8b949e" if is_dark else "#7f8c8d"

    # Define Tags
    txt_widget.tag_configure("h1", font=("Segoe UI", sc(14), "bold"), foreground=fg_h1, spacing1=sc(8), spacing3=sc(6))
    txt_widget.tag_configure("h2", font=("Segoe UI", sc(11), "bold"), foreground=fg_h2, spacing1=sc(12), spacing3=sc(4))
    txt_widget.tag_configure("h3", font=("Segoe UI", sc(10), "bold"), foreground=fg_h3, spacing1=sc(8), spacing3=sc(2))
    txt_widget.tag_configure("body", font=("Segoe UI", sc(9.5)), foreground=fg_text, spacing1=sc(1), spacing3=sc(1))
    txt_widget.tag_configure("bold", font=("Segoe UI", sc(9.5), "bold"), foreground=fg_text)
    txt_widget.tag_configure("italic", font=("Segoe UI", sc(9.5), "italic"), foreground=fg_text)
    txt_widget.tag_configure("bullet", font=("Segoe UI", sc(9.5)), foreground=fg_text, lmargin1=sc(16), lmargin2=sc(28))
    txt_widget.tag_configure("code_inline", font=("Consolas", sc(9), "bold"), foreground=fg_code, background=bg_code)
    txt_widget.tag_configure("code_block", font=("Consolas", sc(8.5)), foreground=fg_text, background=bg_block, lmargin1=sc(12), lmargin2=sc(12))
    txt_widget.tag_configure("table", font=("Consolas", sc(8.5)), foreground=fg_text)
    txt_widget.tag_configure("hr", font=("Segoe UI", sc(3)), foreground=fg_dim)

    in_code_block = False

    def insert_inline(line_text, base_tag=None):
        # Match backticks `code` or bold **bold** or normal
        parts = re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', line_text)
        for part in parts:
            if not part:
                continue
            if part.startswith('`') and part.endswith('`') and len(part) >= 2:
                txt_widget.insert("end", part[1:-1], "code_inline")
            elif part.startswith('**') and part.endswith('**') and len(part) >= 4:
                txt_widget.insert("end", part[2:-2], ("bold", base_tag) if base_tag else "bold")
            else:
                if base_tag:
                    txt_widget.insert("end", part, base_tag)
                else:
                    txt_widget.insert("end", part, "body")

    for raw_line in md_text.splitlines():
        line = raw_line.rstrip()

        # Handle code fences
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            txt_widget.insert("end", raw_line + "\n", "code_block")
            continue

        # Horizontal rule
        if line.strip() in ("---", "***", "___"):
            txt_widget.insert("end", " " * 80 + "\n", "hr")
            continue

        # Headers
        if line.startswith("# "):
            txt_widget.insert("end", line[2:].strip() + "\n", "h1")
        elif line.startswith("## "):
            txt_widget.insert("end", line[3:].strip() + "\n", "h2")
        elif line.startswith("### "):
            txt_widget.insert("end", line[4:].strip() + "\n", "h3")
        elif line.startswith("|") and line.endswith("|"):
            # Table line
            txt_widget.insert("end", raw_line + "\n", "table")
        elif line.startswith("* ") or line.startswith("- "):
            txt_widget.insert("end", "• ", "bullet")
            insert_inline(line[2:], base_tag="bullet")
            txt_widget.insert("end", "\n")
        elif line.startswith("  * ") or line.startswith("  - "):
            txt_widget.insert("end", "    - ", "bullet")
            insert_inline(line[4:], base_tag="bullet")
            txt_widget.insert("end", "\n")
        elif line.strip() == "":
            txt_widget.insert("end", "\n")
        else:
            insert_inline(raw_line)
            txt_widget.insert("end", "\n")


def show_main_help(root_or_ui):
    """Display the full Arbor System User Guide window loaded from USER_GUIDE.md."""
    from config import sc
    import utils

    root = getattr(root_or_ui, "root", root_or_ui)
    is_dark = getattr(root_or_ui, "dark_mode_active", False)

    # Locate USER_GUIDE.md
    guide_path = None
    try:
        from utils import get_resource_path
        guide_path = get_resource_path("USER_GUIDE.md")
    except Exception:
        pass

    if not guide_path or not os.path.exists(guide_path):
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        guide_path = os.path.join(base_dir, "USER_GUIDE.md")

    content = ""
    if os.path.exists(guide_path):
        try:
            with open(guide_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            content = f"# Arbor System User Guide\n\nFailed to load guide file: {e}"
    else:
        content = "# Arbor System User Guide\n\nUSER_GUIDE.md could not be found."

    win = tk.Toplevel(root)
    win.title("Arbor System User Guide")
    w_width = sc(760)
    w_height = sc(780)
    utils.center_and_fit_toplevel(win, w_width, w_height)
    win.bind("<Escape>", lambda e: win.destroy())

    bg_color = "#181c19" if is_dark else "#fafbfa"
    fg_color = "#e8ebe9" if is_dark else "#2c302e"
    win.configure(background=bg_color)

    # Header Bar
    hdr_frame = tk.Frame(win, bg=bg_color, padx=sc(16), pady=sc(10))
    hdr_frame.pack(fill="x")

    tk.Label(
        hdr_frame,
        text="ARBOR USER GUIDE",
        font=("Segoe UI", sc(13), "bold"),
        fg=fg_color,
        bg=bg_color
    ).pack(side="left")

    # Content Frame with Text & Scrollbar
    content_frame = tk.Frame(win, bg=bg_color, padx=sc(16), pady=sc(4))
    content_frame.pack(fill="both", expand=True)

    sb = ttk.Scrollbar(content_frame, orient="vertical")
    txt = tk.Text(
        content_frame,
        wrap="word",
        font=("Segoe UI", sc(9.5)),
        relief="flat",
        bg=bg_color,
        fg=fg_color,
        padx=sc(12),
        pady=sc(8),
        yscrollcommand=sb.set,
        highlightthickness=0,
        state="normal"
    )
    sb.config(command=txt.yview)

    sb.pack(side="right", fill="y")
    txt.pack(side="left", fill="both", expand=True)

    _render_markdown_to_text(txt, content, is_dark=is_dark)
    txt.config(state="disabled")

    # Footer
    footer = tk.Frame(win, bg=bg_color, padx=sc(16), pady=sc(10))
    footer.pack(fill="x", side="bottom")

    tk.Label(
        footer,
        text="Press Escape to close.",
        font=("Segoe UI", sc(8.5), "italic"),
        fg="#888888",
        bg=bg_color
    ).pack(side="left")

    close_btn = ttk.Button(footer, text="Close", command=win.destroy, cursor="hand2")
    close_btn.pack(side="right")


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

    def start_review_tut():
        from ui.tutorials import start_review_tutorial
        start_review_tutorial(ui)

    def start_discrepancy_tut():
        from ui.tutorials import start_discrepancy_tutorial
        start_discrepancy_tutorial(ui)

    def start_database_tut():
        from ui.tutorials import start_database_tutorial
        start_database_tutorial(ui)

    options = [
        ("Tutorial: Reviewing", "Interactive walkthrough: inspecting and verifying objects.", start_review_tut),
        ("Tutorial: Conflicts", "Interactive walkthrough: historical & GBIF discrepancies.", start_discrepancy_tut),
        ("Tutorial: Databases", "Interactive walkthrough: creating databases & new objects.", start_database_tut),
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
    utils.center_and_fit_toplevel(win, sc(840), sc(680))

    is_dark = getattr(ui, "dark_mode_active", False)
    bg_color = "#181c19" if is_dark else "#fbfaf8"
    fg_title = "#e8ebe9" if is_dark else "#2c302e"
    fg_label = "#a6adc8" if is_dark else "#757d77"
    fg_nomatch = "#c93a40"
    fg_cat = "#3a7d44"
    bg_key = "#111412" if is_dark else "#f2f5f1"
    fg_key = "#e8ebe9" if is_dark else "#2c302e"
    key_border = "#2c302e" if is_dark else "#dadada"
    fg_desc = "#c6cac7" if is_dark else "#444748"
    fg_footer = "#757d77"
    border_color = "#2c302e" if is_dark else "#dadada"
    btn_primary_bg = "#3a7d44" if is_dark else "#2c302e"
    btn_primary_hover = "#4b9e57" if is_dark else "#3d4240"

    win.configure(background=bg_color)
    win.transient(ui.root)
    win.bind("<Escape>", lambda e: win.destroy())

    title_frame = tk.Frame(win, bg=bg_color)
    title_frame.pack(fill="x", padx=sc(24), pady=(sc(16), sc(8)))

    tk.Label(
        title_frame,
        text="KEYBOARD SHORTCUTS",
        font=("Segoe UI", sc(13), "bold"),
        fg=fg_title,
        bg=bg_color
    ).pack(anchor="w")

    tk.Label(
        title_frame,
        text="Comprehensive navigation, focus, and curation shortcut cheat sheet.",
        font=("Segoe UI", sc(9)),
        fg=fg_label,
        bg=bg_color
    ).pack(anchor="w", pady=(sc(2), 0))

    search_frame = tk.Frame(win, bg=bg_color, padx=sc(24))
    search_frame.pack(fill="x", pady=(0, sc(12)))

    search_card = tk.Frame(search_frame, bg=bg_key, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1, padx=sc(10), pady=sc(6))
    search_card.pack(fill="x")

    tk.Label(
        search_card,
        text="🔍",
        font=("Segoe UI", sc(9.5)),
        fg=fg_label,
        bg=bg_key
    ).pack(side="left", padx=(0, sc(6)))

    search_var = tk.StringVar()
    search_ent = tk.Entry(
        search_card, textvariable=search_var,
        font=("Segoe UI", sc(9.5)),
        bg=bg_key, fg=fg_key,
        insertbackground=fg_key,
        bd=0, highlightthickness=0
    )
    search_ent.pack(side="left", fill="x", expand=True)
    search_ent.focus_set()

    content_outer = tk.Frame(win, bg=bg_color)
    content_outer.pack(fill="both", expand=True, padx=sc(24), pady=(0, sc(10)))

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
        ("ICEDIG & MISSING DATA", "Ctrl+Shift+M / ?m", "Set field to unknown:missing (Blank on label)"),
        ("ICEDIG & MISSING DATA", "Ctrl+Shift+I / ?i", "Set field to unknown:indecipherable (Illegible)"),
        ("ICEDIG & MISSING DATA", "Ctrl+Shift+U / ?u", "Set field to unknown:undigitized (Skipped)"),
        ("ICEDIG & MISSING DATA", "Ctrl+Shift+W / ?w", "Set field to withheld (Restricted)"),
        ("ICEDIG & MISSING DATA", "Ctrl+Shift+Backspace", "Clear field value"),
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
            ).pack(pady=sc(20))
            return

        for cat, items in categories.items():
            cat_frame = tk.Frame(scroll_content, bg=bg_color)
            cat_frame.pack(fill="x", pady=(sc(12), sc(4)), anchor="w")

            tk.Label(
                cat_frame,
                text=cat,
                font=("JetBrains Mono", sc(10), "bold"),
                fg=fg_cat,
                bg=bg_color
            ).pack(side="left")

            tk.Frame(cat_frame, bg=border_color, height=1).pack(side="left", fill="x", expand=True, padx=(sc(10), 0))

            grid_frame = tk.Frame(scroll_content, bg=bg_color)
            grid_frame.pack(fill="x", padx=sc(4), pady=sc(2), anchor="w")
            grid_frame.columnconfigure(0, minsize=sc(240))
            grid_frame.columnconfigure(1, weight=1)

            for r, (keys, desc) in enumerate(items):
                key_container = tk.Frame(
                    grid_frame, bg=bg_key,
                    bd=1, relief="solid",
                    highlightbackground=key_border,
                    highlightthickness=1,
                    padx=sc(8), pady=sc(3)
                )
                key_container.grid(row=r, column=0, sticky="w", pady=sc(3), padx=(0, sc(12)))

                tk.Label(
                    key_container,
                    text=keys,
                    font=("JetBrains Mono", sc(9.5), "bold"),
                    fg=fg_key,
                    bg=bg_key
                ).pack()

                tk.Label(
                    grid_frame,
                    text=desc,
                    font=("Segoe UI", sc(9.5)),
                    fg=fg_desc,
                    bg=bg_color,
                    wraplength=sc(520),
                    justify="left"
                ).grid(row=r, column=1, sticky="w", pady=sc(3))

    draw_shortcuts()
    search_var.trace_add("write", lambda *args: draw_shortcuts(search_var.get()))

    footer = tk.Frame(win, bg=bg_color)
    footer.pack(fill="x", side="bottom", pady=sc(10), padx=sc(24))

    tk.Label(
        footer,
        text="Press Escape to close this window.",
        font=("Segoe UI", sc(9), "italic"),
        fg=fg_footer,
        bg=bg_color
    ).pack(side="left")

    close_btn = tk.Button(
        footer,
        text="CLOSE",
        command=win.destroy,
        font=("Segoe UI", sc(9.5), "bold"),
        bg=btn_primary_bg,
        fg="#ffffff",
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=sc(16),
        pady=sc(5)
    )
    close_btn.pack(side="right")
    close_btn.bind("<Enter>", lambda e: close_btn.config(bg=btn_primary_hover))
    close_btn.bind("<Leave>", lambda e: close_btn.config(bg=btn_primary_bg))
