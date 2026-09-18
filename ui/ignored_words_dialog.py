import os
import re
import json
import tkinter as tk
from tkinter import ttk
from utils import debug_error

_NORMALIZE_NON_WORD_PATTERN = re.compile(r'[^\w\s]')
_NORMALIZE_SPACE_PATTERN = re.compile(r'\s+')


def normalize_word(text, variations):
    """Normalize text by stripping and optionally lowercasing and removing punctuation."""
    if not text:
        return ""
    text = text.strip()
    if variations:
        text = text.lower()
        text = _NORMALIZE_NON_WORD_PATTERN.sub('', text)
        text = _NORMALIZE_SPACE_PATTERN.sub(' ', text)
        text = text.strip()
    return text


def is_word_ignored(val, ignored_words, variations):
    """Check if a word/phrase matches any entry in the ignored words list."""
    if not val or not ignored_words:
        return False

    val_norm = normalize_word(val, variations)

    for word in ignored_words:
        word_norm = normalize_word(word, variations)
        if variations:
            if val_norm == word_norm:
                return True
        else:
            if val == word:
                return True
    return False


def load_ignored_words(file_path):
    """Load ignored words and variations flag from disk or default bundled file."""
    read_path = file_path
    if not os.path.exists(read_path):
        try:
            from utils import get_resource_path
            bundled = get_resource_path("ignored_words.json")
            if os.path.exists(bundled):
                read_path = bundled
        except Exception:
            pass

    if os.path.exists(read_path):
        try:
            with open(read_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("words", []), data.get("variations", True)
        except Exception as e:
            debug_error("Load ignored words failed", str(e))
            return [], True
    else:
        return [], True


def save_ignored_words(file_path, words, variations):
    """Save ignored words and variations flag to disk."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({
                "words": words,
                "variations": variations
            }, f, indent=4, ensure_ascii=False)
    except Exception as e:
        debug_error("Save ignored words failed", str(e))


def open_ignored_words_editor(ui):
    """Open the Ignored Words configuration dialog."""
    from config import sc
    import utils

    win = tk.Toplevel(ui.root)
    win.transient(ui.root)
    win.grab_set()
    win.bind("<Escape>", lambda e: win.destroy())

    is_dark = getattr(ui, "dark_mode_active", False)
    bg_color = "#181c19" if is_dark else "#fbfaf8"
    header_bg = "#212622" if is_dark else "#f2f5f1"
    fg_color = "#e8ebe9" if is_dark else "#2c302e"
    muted_fg = "#bac2de" if is_dark else "#444748"
    field_bg = "#212622" if is_dark else "#ffffff"
    border_color = "#45475a" if is_dark else "#d1d1d1"
    primary_btn_bg = "#a6e3a1" if is_dark else "#2c302e"
    primary_btn_fg = "#181c19" if is_dark else "#ffffff"

    win.configure(background=bg_color)
    win.title("Configure Ignored Words")
    utils.center_and_fit_toplevel(win, sc(520), sc(560))

    # Header
    header = tk.Frame(win, bg=header_bg, height=sc(56))
    header.pack(fill="x", side="top")
    header.pack_propagate(False)
    tk.Frame(header, bg=border_color, height=1).pack(fill="x", side="bottom")

    tk.Label(
        header, text="Suggestions Filter: Ignored Words",
        font=("Hanken Grotesk", sc(12), "bold"), bg=header_bg, fg=fg_color
    ).pack(anchor="w", padx=sc(16), pady=(sc(8), 0))

    tk.Label(
        header,
        text="Suggestions matching these words/phrases will be omitted in comparison.",
        font=("Inter", sc(8.5)), bg=header_bg, fg=muted_fg
    ).pack(anchor="w", padx=sc(16))

    # Footer (packed first to guarantee visibility at bottom)
    btn_frame = tk.Frame(win, bg=header_bg, height=sc(52))
    btn_frame.pack(fill="x", side="bottom")
    btn_frame.pack_propagate(False)
    tk.Frame(btn_frame, bg=border_color, height=1).pack(fill="x", side="top")

    local_vars_var = tk.BooleanVar(value=ui.ignored_words_variations.get())

    def on_save():
        content = text_area.get("1.0", tk.END).strip()
        words = [line.strip() for line in content.split("\n") if line.strip()]
        ui.ignored_words = words
        ui.ignored_words_variations.set(local_vars_var.get())
        ui.save_ignored_words()

        if hasattr(ui, "_history_cache"):
            ui._history_cache.clear()

        if hasattr(ui, "history_window") and ui.history_window and ui.history_window.winfo_exists():
            show_all = getattr(ui.history_window, "local_show_all", False)
            ui.history_window.destroy()
            ui.open_historical_suggestions(show_all_override=show_all)

        win.destroy()

    tk.Button(
        btn_frame, text="Cancel", command=win.destroy,
        font=("Hanken Grotesk", sc(9.5)), bg=field_bg, fg=fg_color,
        relief="solid", bd=1, cursor="hand2", padx=sc(14), pady=sc(4)
    ).pack(side="left", padx=sc(16), pady=sc(8))

    tk.Button(
        btn_frame, text="Save Settings", command=on_save,
        font=("Hanken Grotesk", sc(9.5), "bold"), bg=primary_btn_bg, fg=primary_btn_fg,
        relief="flat", bd=0, cursor="hand2", padx=sc(16), pady=sc(5)
    ).pack(side="right", padx=sc(16), pady=sc(8))

    # Variations Checkbox Row (above footer)
    vars_frame = tk.Frame(win, bg=bg_color)
    vars_frame.pack(fill="x", side="bottom", padx=sc(16), pady=sc(8))

    cb = tk.Checkbutton(
        vars_frame, cursor="hand2",
        text="Include variations (ignore capitalization, punctuation, extra spacing)",
        variable=local_vars_var, font=("Inter", sc(9)),
        bg=bg_color, fg=fg_color, activebackground=bg_color, selectcolor=field_bg
    )
    cb.pack(anchor="w")

    # Scrollable Text Area
    text_frame = tk.Frame(win, bg=bg_color)
    text_frame.pack(fill="both", expand=True, padx=sc(16), pady=(sc(10), 0))

    text_scroll = ttk.Scrollbar(text_frame)
    text_scroll.pack(side="right", fill="y")

    text_area = tk.Text(
        text_frame,
        yscrollcommand=text_scroll.set,
        font=("JetBrains Mono", sc(10)),
        background=field_bg,
        foreground=fg_color,
        insertbackground=fg_color,
        highlightbackground=border_color,
        highlightcolor=primary_btn_bg,
        highlightthickness=1,
        bd=0
    )
    text_area.pack(side="left", fill="both", expand=True)
    text_scroll.config(command=text_area.yview)

    text_area.insert("1.0", "\n".join(ui.ignored_words))
