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
    bg_color = "#181c19" if is_dark else "#f0f0f0"
    fg_color = "#e8ebe9" if is_dark else "black"
    field_bg = "#212622" if is_dark else "white"
    border_color = "#313244" if is_dark else "#d0d0d0"

    win.configure(background=bg_color)
    win.title("Configure Ignored Words")
    utils.center_and_fit_toplevel(win, 500, 550)

    title_lbl = ttk.Label(win, text="Suggestions Filter: Ignored Words", font=("Segoe UI", sc(12), "bold"))
    title_lbl.pack(anchor="w", padx=15, pady=(15, 5))

    desc_lbl = ttk.Label(
        win,
        text="Suggestions matching these words/phrases will be omitted in comparison.\nEnter one word or phrase per line.",
        font=("Segoe UI", sc(9))
    )
    desc_lbl.pack(anchor="w", padx=15, pady=(0, 10))

    text_frame = ttk.Frame(win)
    text_frame.pack(fill="both", expand=True, padx=15, pady=5)

    text_scroll = ttk.Scrollbar(text_frame)
    text_scroll.pack(side="right", fill="y")

    text_area = tk.Text(
        text_frame,
        yscrollcommand=text_scroll.set,
        font=("Segoe UI", sc(10)),
        background=field_bg,
        foreground=fg_color,
        insertbackground=fg_color,
        highlightbackground=border_color,
        bd=1,
        relief="solid"
    )
    text_area.pack(side="left", fill="both", expand=True)
    text_scroll.config(command=text_area.yview)

    text_area.insert("1.0", "\n".join(ui.ignored_words))

    vars_frame = ttk.Frame(win)
    vars_frame.pack(fill="x", padx=15, pady=10)

    local_vars_var = tk.BooleanVar(value=ui.ignored_words_variations.get())
    cb = ttk.Checkbutton(
        vars_frame, cursor="hand2",
        text="Include variations (ignore capitalization, punctuation, extra spacing)",
        variable=local_vars_var
    )
    cb.pack(anchor="w")

    btn_frame = ttk.Frame(win, padding=10)
    btn_frame.pack(fill="x", side="bottom")

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

    ttk.Button(btn_frame, text="Save", command=on_save, cursor="hand2").pack(side="right", padx=5)
    ttk.Button(btn_frame, text="Cancel", command=win.destroy, cursor="hand2").pack(side="left", padx=5)
