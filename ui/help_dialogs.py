import os
import sys
import re
import tkinter as tk
from tkinter import ttk, messagebox
import config
from config import sc


def _render_markdown_to_text(txt_widget, md_text, is_dark=False):
    """
    Parses markdown text and inserts it into a Tkinter Text widget with rich tags.
    Returns a list of detected chapter bookmarks: [(title, mark_id), ...]
    """
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
    bookmarks = []

    def insert_inline(line_text, base_tag=None):
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

        # Headers and Bookmark registration
        if line.startswith("# "):
            title = line[2:].strip()
            mark_id = f"bm_{len(bookmarks)}"
            txt_widget.mark_set(mark_id, txt_widget.index("end-1c"))
            txt_widget.mark_gravity(mark_id, "left")
            bookmarks.append((title, mark_id))
            txt_widget.insert("end", title + "\n", "h1")
        elif line.startswith("## "):
            title = line[3:].strip()
            mark_id = f"bm_{len(bookmarks)}"
            txt_widget.mark_set(mark_id, txt_widget.index("end-1c"))
            txt_widget.mark_gravity(mark_id, "left")
            bookmarks.append((title, mark_id))
            txt_widget.insert("end", title + "\n", "h2")
        elif line.startswith("### "):
            txt_widget.insert("end", line[4:].strip() + "\n", "h3")
        elif line.startswith("|") and line.endswith("|"):
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

    return bookmarks


def show_main_help(root_or_ui):
    """
    Display the full Arbor System User Guide window loaded from USER_GUIDE.md,
    featuring chapter jump navigation bookmarks and the Arbor <-> Excel translation bridge.
    """
    import utils

    root = getattr(root_or_ui, "root", root_or_ui)
    is_dark = getattr(root_or_ui, "dark_mode_active", False)

    # Locate USER_GUIDE.md with robust multi-directory fallback
    candidate_paths = []
    try:
        candidate_paths.append(utils.get_resource_path("USER_GUIDE.md"))
    except Exception:
        pass

    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        candidate_paths.append(os.path.join(base_dir, "USER_GUIDE.md"))
        candidate_paths.append(os.path.join(base_dir, "documentation", "curator", "CURATOR_USER_GUIDE.md"))
    else:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate_paths.append(os.path.join(repo_root, "USER_GUIDE.md"))
        candidate_paths.append(os.path.join(repo_root, "documentation", "curator", "CURATOR_USER_GUIDE.md"))

    guide_path = None
    for p in candidate_paths:
        if p and os.path.exists(p):
            guide_path = p
            break

    content = ""
    if guide_path and os.path.exists(guide_path):
        try:
            with open(guide_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            content = f"# Arbor System User Guide\n\nFailed to load guide file: {e}"
    else:
        content = (
            "# Arbor Herbarium Curation Suite — Trainee Work Manual\n\n"
            "USER_GUIDE.md could not be found at standard resource paths."
        )

    win = tk.Toplevel(root)
    win.title("Arbor System User Guide & Excel Bridge")
    w_width = sc(820)
    w_height = sc(800)
    utils.center_and_fit_toplevel(win, w_width, w_height)
    win.bind("<Escape>", lambda e: win.destroy())

    bg_color = "#181c19" if is_dark else "#fafbfa"
    fg_color = "#e8ebe9" if is_dark else "#2c302e"
    accent_col = "#389e63" if is_dark else "#2d7a4c"
    win.configure(background=bg_color)

    # Header Bar
    hdr_frame = tk.Frame(win, bg=bg_color, padx=sc(16), pady=sc(10))
    hdr_frame.pack(fill="x")

    title_frame = tk.Frame(hdr_frame, bg=bg_color)
    title_frame.pack(side="left")

    tk.Label(
        title_frame,
        text="ARBOR USER GUIDE",
        font=("Segoe UI", sc(12), "bold"),
        fg=accent_col,
        bg=bg_color
    ).pack(anchor="w")

    tk.Label(
        title_frame,
        text="Trainee Work Manual & Excel Bridge Reference",
        font=("Segoe UI", sc(8.5)),
        fg="#7f8c8d",
        bg=bg_color
    ).pack(anchor="w")

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
        padx=sc(14),
        pady=sc(10),
        yscrollcommand=sb.set,
        highlightthickness=0,
        state="normal"
    )
    sb.config(command=txt.yview)

    sb.pack(side="right", fill="y")
    txt.pack(side="left", fill="both", expand=True)

    bookmarks = _render_markdown_to_text(txt, content, is_dark=is_dark)
    txt.config(state="disabled")

    # Bookmark Jump Dropdown in Header
    if bookmarks:
        jump_frame = tk.Frame(hdr_frame, bg=bg_color)
        jump_frame.pack(side="right", fill="y", padx=(sc(10), 0))

        tk.Label(
            jump_frame,
            text="Jump to Chapter:",
            font=("Segoe UI", sc(9), "bold"),
            fg=fg_color,
            bg=bg_color
        ).pack(side="left", padx=(0, sc(6)))

        # Prioritize main chapters and overview
        curated_bms = [
            b for b in bookmarks
            if b[0].lower().startswith("chapter") or "table of contents" in b[0].lower() or "welcome" in b[0].lower()
        ]
        if not curated_bms:
            curated_bms = bookmarks[:15]

        bm_dict = {b[0]: b[1] for b in curated_bms}
        cb_jump = ttk.Combobox(
            jump_frame,
            values=list(bm_dict.keys()),
            state="readonly",
            width=36,
            cursor="hand2"
        )
        cb_jump.pack(side="left")
        if curated_bms:
            cb_jump.set(curated_bms[0][0])

        def _on_chapter_selected(e):
            sel = cb_jump.get()
            if sel in bm_dict:
                txt.see(bm_dict[sel])

        cb_jump.bind("<<ComboboxSelected>>", _on_chapter_selected)

    # Footer
    footer = tk.Frame(win, bg=bg_color, padx=sc(16), pady=sc(10))
    footer.pack(fill="x", side="bottom")

    tk.Label(
        footer,
        text="Press Escape to close. Click links or select chapters above to navigate.",
        font=("Segoe UI", sc(8.5), "italic"),
        fg="#888888",
        bg=bg_color
    ).pack(side="left")

    close_btn = ttk.Button(footer, text="Close", command=win.destroy, cursor="hand2")
    close_btn.pack(side="right")


def show_quick_help(ui=None):
    """Display the Keyboard Shortcuts HUD or an overview of essential shortcuts."""
    if ui is not None and hasattr(ui, "root"):
        show_shortcuts(ui)
    else:
        messagebox.showinfo(
            "Quick Start",
            "Arbor Essential Shortcuts:\n\n"
            "• F1: Open Keyboard Shortcuts HUD (Cheat Sheet)\n"
            "• Ctrl+K / Ctrl+Shift+P: Open Universal Command Palette\n"
            "• Ctrl+S: Save active session directly to Excel\n"
            "• Ctrl+Enter: Mark specimen as reviewed & advance\n"
            "• Space: Toggle focused problem checkbox\n"
            "• Down / Up Arrow: Navigate between specimens"
        )


def show_about(ui=None):
    """Display the About Arbor dialog with application details, dynamic version, and environment info."""
    import platform
    import utils

    root = getattr(ui, "root", None) if ui else None
    win = tk.Toplevel(root) if root else tk.Toplevel()
    win.title("About Arbor")
    win.resizable(False, False)
    if root:
        win.transient(root)
    utils.center_and_fit_toplevel(win, sc(520), sc(420))

    is_dark = getattr(ui, "dark_mode_active", False) if ui else False
    bg_color = "#181c19" if is_dark else "#f8faf9"
    card_bg = "#212623" if is_dark else "#ffffff"
    fg_title = "#e8ebe9" if is_dark else "#2c302e"
    fg_text = "#c6cac7" if is_dark else "#444748"
    fg_sub = "#a2aba5" if is_dark else "#636d65"
    border_col = "#2c302e" if is_dark else "#e0e4e1"
    accent_col = "#389e63" if is_dark else "#2d7a4c"

    win.configure(background=bg_color)
    win.bind("<Escape>", lambda e: win.destroy())

    container = tk.Frame(win, bg=bg_color, padx=sc(20), pady=sc(16))
    container.pack(fill="both", expand=True)

    tk.Label(
        container,
        text="ARBOR",
        font=("Segoe UI", sc(16), "bold"),
        fg=accent_col,
        bg=bg_color
    ).pack(anchor="w")

    tk.Label(
        container,
        text="Herbarium & Museum Collection Curation System",
        font=("Segoe UI", sc(9.5), "bold"),
        fg=fg_title,
        bg=bg_color
    ).pack(anchor="w", pady=(0, sc(10)))

    card = tk.Frame(container, bg=card_bg, highlightbackground=border_col, highlightthickness=1, padx=sc(14), pady=sc(12))
    card.pack(fill="x", pady=(0, sc(12)))

    db_name = "None loaded"
    rec_count = 0
    if ui and getattr(ui, "app", None):
        if getattr(ui.app, "current_excel_path", None):
            db_name = os.path.basename(ui.app.current_excel_path)
        if getattr(ui.app, "df_reg", None) is not None:
            rec_count = len(ui.app.df_reg)

    app_ver = getattr(config, "APP_VERSION", "2.1.0")
    tk_ver = getattr(tk, "TkVersion", "unknown")

    info_rows = [
        ("Version", f"{app_ver} (Production Tkinter)"),
        ("Tkinter Runtime", f"{tk_ver}"),
        ("Python Runtime", f"{platform.python_version()} ({platform.system()} {platform.machine()})"),
        ("Active Database", f"{db_name} ({rec_count} records)" if rec_count else db_name),
        ("Storage Formats", "Excel (.xlsx), SQLite (.db), CSV"),
        ("Mission", "100% Offline-First Museum Collection Curation"),
    ]

    for label, val in info_rows:
        row_frame = tk.Frame(card, bg=card_bg)
        row_frame.pack(fill="x", pady=sc(2))
        tk.Label(row_frame, text=label, font=("Segoe UI", sc(8.5), "bold"), fg=fg_sub, bg=card_bg, width=17, anchor="w").pack(side="left")
        tk.Label(row_frame, text=val, font=("Segoe UI", sc(8.5)), fg=fg_text, bg=card_bg, anchor="w").pack(side="left", fill="x", expand=True)

    tk.Label(
        container,
        text="Arbor is a 100% offline-first museum curation and botanical label verification system.\n"
             "Designed for rapid physical inspection, box auditing, and Excel workbook synchronization.",
        font=("Segoe UI", sc(8)),
        fg=fg_sub,
        bg=bg_color,
        justify="left"
    ).pack(anchor="w", pady=(0, sc(12)))

    btn_frame = tk.Frame(container, bg=bg_color)
    btn_frame.pack(fill="x")
    ttk.Button(btn_frame, text="Close", command=win.destroy, style="Tool.TButton", width=10).pack(side="right")


def open_help_window(ui):
    """
    Display the Central Arbor In-App User Assistance Hub featuring 4 launch tiles:
    1. Trainee Work Manual (USER_GUIDE.md reader & Excel bridge)
    2. Keyboard Shortcuts & Desk Guide (HUD with keycaps & Excel column effects)
    3. Interactive Onboarding Tutorials (Sandboxed action walkthroughs)
    4. About Arbor (Version, environment, and diagnostics)
    """
    import utils

    if hasattr(ui, "help_win") and ui.help_win and ui.help_win.winfo_exists():
        ui.help_win.focus_force()
        ui.help_win.focus_set()
        ui.help_win.lift()
        return

    win = tk.Toplevel(ui.root)
    ui.help_win = win
    win.title("Arbor User Assistance Hub")
    win.resizable(False, False)
    win.transient(ui.root)

    w_width = sc(540)
    w_height = sc(560)
    utils.center_and_fit_toplevel(win, w_width, w_height)

    is_dark = getattr(ui, "dark_mode_active", False)
    bg_color = "#181c19" if is_dark else "#f4f7f4"
    card_bg = "#212623" if is_dark else "#ffffff"
    fg_title = "#e8ebe9" if is_dark else "#2c302e"
    fg_sub = "#a2aba5" if is_dark else "#5c6660"
    border_col = "#2c302e" if is_dark else "#dbe0dc"
    accent_col = "#389e63" if is_dark else "#2d7a4c"

    win.configure(background=bg_color)
    win.bind("<Escape>", lambda e: win.destroy())

    frame = tk.Frame(win, bg=bg_color, padx=sc(20), pady=sc(16))
    frame.pack(fill="both", expand=True)

    lbl_header = tk.Label(
        frame,
        text="ARBOR USER ASSISTANCE HUB",
        font=("Segoe UI", sc(13), "bold"),
        fg=accent_col,
        bg=bg_color
    )
    lbl_header.pack(anchor="w")

    lbl_sub = tk.Label(
        frame,
        text="Everything you need to audit, verify, and document museum collections.",
        font=("Segoe UI", sc(9)),
        fg=fg_sub,
        bg=bg_color
    )
    lbl_sub.pack(anchor="w", pady=(0, sc(12)))

    tk.Frame(frame, bg=border_col, height=1).pack(fill="x", pady=(0, sc(14)))

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

    # ── 4 Primary Launch Tiles ───────────────────────────────────────────────
    tiles = [
        (
            "📖 Trainee Work Manual",
            "Trainee Work Manual & Excel Bridge",
            "Complete 10-chapter guide covering the 5-step daily routine, status badges, and Excel sheet layouts.",
            lambda: run_help_cmd(lambda: show_main_help(ui.root)),
            None
        ),
        (
            "⌨️ Keyboard Shortcuts",
            "Keyboard Shortcuts HUD (F1)",
            "Visual keycap cheat sheet for ergonomic, mouse-free curation, label codes (?m, ?i), and Excel effects.",
            lambda: run_help_cmd(lambda: show_shortcuts(ui)),
            None
        ),
        (
            "🎓 Interactive Tutorials",
            "Interactive Onboarding Tutorials",
            "Safe, sandboxed practice sessions: Reviewing Objects, Conflict Resolver, and Database Setup.",
            None,
            [
                ("Reviewing", "1. Review", lambda: run_help_cmd(start_review_tut)),
                ("Conflicts", "2. Conflicts", lambda: run_help_cmd(start_discrepancy_tut)),
                ("Databases", "3. Databases", lambda: run_help_cmd(start_database_tut)),
            ]
        ),
        (
            "ℹ️ About Arbor",
            f"About Arbor (v{getattr(config, 'APP_VERSION', '2.1.0')})",
            "Application version, environment details, active workbook telemetry, and offline-first status.",
            lambda: run_help_cmd(lambda: show_about(ui)),
            None
        ),
    ]

    for btn_label, tile_title, tile_desc, primary_cmd, sub_actions in tiles:
        card = tk.Frame(frame, bg=card_bg, highlightbackground=border_col, highlightthickness=1, padx=sc(12), pady=sc(10))
        card.pack(fill="x", pady=sc(5))

        top_row = tk.Frame(card, bg=card_bg)
        top_row.pack(fill="x")

        tk.Label(
            top_row,
            text=tile_title,
            font=("Segoe UI", sc(10), "bold"),
            fg=fg_title,
            bg=card_bg
        ).pack(side="left")

        if primary_cmd:
            btn = tk.Button(
                top_row,
                text=btn_label.split(" ")[0] + " Open",
                command=primary_cmd,
                font=("Segoe UI", sc(8.5), "bold"),
                bg=accent_col,
                fg="#ffffff",
                relief="flat",
                bd=0,
                padx=sc(10),
                pady=sc(3),
                cursor="hand2"
            )
            btn.pack(side="right")

        tk.Label(
            card,
            text=tile_desc,
            font=("Segoe UI", sc(8.5)),
            fg=fg_sub,
            bg=card_bg,
            wraplength=sc(490),
            justify="left"
        ).pack(anchor="w", pady=(sc(2), 0))

        if sub_actions:
            sub_row = tk.Frame(card, bg=card_bg)
            sub_row.pack(fill="x", pady=(sc(6), 0))
            for _, label, cmd in sub_actions:
                sub_btn = tk.Button(
                    sub_row,
                    text=label,
                    command=cmd,
                    font=("Segoe UI", sc(8), "bold"),
                    bg=bg_color,
                    fg=fg_title,
                    relief="flat",
                    bd=1,
                    highlightthickness=1,
                    highlightbackground=border_col,
                    padx=sc(8),
                    pady=sc(2),
                    cursor="hand2"
                )
                sub_btn.pack(side="left", padx=(0, sc(6)))

    close_btn = ttk.Button(
        frame,
        text="Close",
        command=win.destroy,
        style="Tool.TButton",
        width=10,
        cursor="hand2"
    )
    close_btn.pack(side="bottom", pady=(sc(10), 0))


def show_shortcuts(ui):
    """
    Create a searchable HUD dialog displaying all keyboard shortcuts with visual keycaps,
    dual-depth trainee descriptions, and Excel translation impacts.
    """
    import utils

    win = tk.Toplevel(ui.root)
    win.title("Keyboard Shortcuts & Desk Guide HUD")
    utils.center_and_fit_toplevel(win, sc(880), sc(700))

    is_dark = getattr(ui, "dark_mode_active", False)
    bg_color = "#181c19" if is_dark else "#fbfaf8"
    fg_title = "#e8ebe9" if is_dark else "#2c302e"
    fg_label = "#a6adc8" if is_dark else "#757d77"
    fg_nomatch = "#c93a40"
    fg_cat = "#3a7d44"
    bg_key = "#111412" if is_dark else "#f2f5f1"
    fg_key = "#e8ebe9" if is_dark else "#2c302e"
    key_border = "#2c302e" if is_dark else "#dadada"
    fg_desc = "#c6cac7" if is_dark else "#2c302e"
    fg_excel = "#81c784" if is_dark else "#2e7d32"
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
        text="KEYBOARD SHORTCUTS & DESK GUIDE",
        font=("Segoe UI", sc(13), "bold"),
        fg=fg_title,
        bg=bg_color
    ).pack(anchor="w")

    tk.Label(
        title_frame,
        text="Ergonomic keybindings for mouse-free curation, missing label codes (?m, ?i), and Excel mappings.",
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

    # Dynamically pull from canonical registry in ui/keybindings.py
    try:
        from ui.keybindings import get_canonical_shortcuts
        raw_shortcuts = get_canonical_shortcuts()
    except Exception:
        raw_shortcuts = [
            ("PRIMARY WORK KEYS", "[ CTRL ] + [ ENTER ] or [ CTRL ] + [ R ]", "Mark Reviewed & Advance", "Signs off record, advances to next (sets Reviewed = TRUE in Excel)"),
            ("PRIMARY WORK KEYS", "[ SPACE ]", "Toggle Problem Checkbox", "Flags or clears problem on active field (sets problem flag TRUE / FALSE in Excel)"),
            ("PRIMARY WORK KEYS", "[ CTRL ] + [ S ]", "Save Active Workbook to Excel", "Writes all updates safely to Excel"),
            ("SEARCHING & RECORD NAVIGATION", "[ CTRL ] + [ K ]", "Command Palette & Omni-Search", "Instant keyboard switcher to run any command or jump to #ObjectID"),
            ("SEARCHING & RECORD NAVIGATION", "[ CTRL ] + [ F ]", "Search Bar Focus", "Focuses directory search box to filter by ID, genus, or species"),
            ("SEARCHING & RECORD NAVIGATION", "[ CTRL ] + [ G ]", "Filter Menu", "Filters by Reviewed status, specific problem flags, or photos"),
            ("SPECIMEN PHOTOS & VIEW CONTROLS", "[ CTRL ] + [ 0 ]", "Reset Zoom", "Fits entire specimen sheet back into visible frame"),
            ("ASSISTANCE & WORKSPACE", "[ F1 ]", "Help Center & Shortcuts HUD", "Opens central assistance hub and keyboard cheat sheet"),
        ]

    def draw_shortcuts(filter_text=""):
        for w in scroll_content.winfo_children():
            w.destroy()

        categories = {}
        filter_lower = filter_text.lower()

        for item in raw_shortcuts:
            cat = item[0]
            keys = item[1]
            desc = item[2]
            excel_eff = item[3] if len(item) > 3 else ""

            if filter_lower:
                match = (
                    filter_lower in cat.lower() or
                    filter_lower in keys.lower() or
                    filter_lower in desc.lower() or
                    filter_lower in excel_eff.lower()
                )
                if not match:
                    continue

            categories.setdefault(cat, []).append((keys, desc, excel_eff))

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
            grid_frame.columnconfigure(0, minsize=sc(260))
            grid_frame.columnconfigure(1, weight=1)

            for r, (keys, desc, excel_eff) in enumerate(items):
                key_container = tk.Frame(
                    grid_frame, bg=bg_key,
                    bd=1, relief="solid",
                    highlightbackground=key_border,
                    highlightthickness=1,
                    padx=sc(8), pady=sc(3)
                )
                key_container.grid(row=r, column=0, sticky="w", pady=sc(4), padx=(0, sc(12)))

                tk.Label(
                    key_container,
                    text=keys,
                    font=("JetBrains Mono", sc(9.5), "bold"),
                    fg=fg_key,
                    bg=bg_key
                ).pack()

                desc_frame = tk.Frame(grid_frame, bg=bg_color)
                desc_frame.grid(row=r, column=1, sticky="w", pady=sc(3))

                tk.Label(
                    desc_frame,
                    text=desc,
                    font=("Segoe UI", sc(9.5), "bold"),
                    fg=fg_desc,
                    bg=bg_color,
                    wraplength=sc(540),
                    justify="left"
                ).pack(anchor="w")

                if excel_eff:
                    tk.Label(
                        desc_frame,
                        text=f"Excel impact: {excel_eff}",
                        font=("Segoe UI", sc(8.5), "italic"),
                        fg=fg_excel,
                        bg=bg_color,
                        wraplength=sc(540),
                        justify="left"
                    ).pack(anchor="w", pady=(sc(1), 0))

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

    btn_box = tk.Frame(footer, bg=bg_color)
    btn_box.pack(side="right")

    manual_btn = tk.Button(
        btn_box,
        text="📖 READ USER MANUAL",
        command=lambda: (win.destroy(), show_main_help(ui.root)),
        font=("Segoe UI", sc(9), "bold"),
        bg="#e0e4e1" if not is_dark else "#2c302e",
        fg=fg_title,
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=sc(12),
        pady=sc(5)
    )
    manual_btn.pack(side="left", padx=(0, sc(8)))

    close_btn = tk.Button(
        btn_box,
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
    close_btn.pack(side="left")
    close_btn.bind("<Enter>", lambda e: close_btn.config(bg=btn_primary_hover))
    close_btn.bind("<Leave>", lambda e: close_btn.config(bg=btn_primary_bg))
