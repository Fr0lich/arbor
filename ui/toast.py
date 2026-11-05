"""ui/toast.py - Sleek, non-blocking floating toast notifications for Arbor.

Replaces disruptive modal dialogs with smooth, auto-dismissing Stitch-styled
feedback pills at the bottom center of the main workstation.
"""

from __future__ import annotations

import tkinter as tk
from config import sc


class ToastManager:
    """Manages creation, display, and auto-dismissal of floating toasts."""

    _active_toast: tk.Toplevel | None = None
    _dismiss_after_id: str | None = None
    _root_ref: tk.Tk | None = None

    @classmethod
    def show(
        cls,
        root: tk.Tk,
        message: str,
        toast_type: str = "success",
        duration_ms: int = 2500,
        action_label: str | None = None,
        action_callback: callable | None = None
    ) -> None:
        """Display a floating toast card anchored to the bottom of the parent window."""
        try:
            # Dismiss any active toast immediately
            cls.dismiss()

            # Colors based on type
            bg_card = "#1e2420"
            fg_text = "#ffffff"
            border_col = "#38453c"

            if toast_type == "success":
                icon = "✓"
                icon_col = "#4caf50"
            elif toast_type == "warning":
                icon = "⚠️"
                icon_col = "#ffb74d"
            elif toast_type == "error":
                icon = "✕"
                icon_col = "#ef5350"
            else:
                icon = "ℹ"
                icon_col = "#64b5f6"

            toast = tk.Toplevel(root)
            toast.wm_overrideredirect(True)
            toast.configure(bg=bg_card)
            toast.attributes("-topmost", True)

            # Container with padding and hairline border
            card = tk.Frame(
                toast,
                bg=bg_card,
                bd=1,
                relief="solid",
                highlightbackground=border_col,
                highlightthickness=1,
                padx=sc(14),
                pady=sc(8)
            )
            card.pack(fill="both", expand=True)

            # Icon
            tk.Label(
                card,
                text=icon,
                font=("Segoe UI", sc(11), "bold"),
                fg=icon_col,
                bg=bg_card
            ).pack(side="left", padx=(0, sc(8)))

            # Message
            tk.Label(
                card,
                text=message,
                font=("Segoe UI", sc(9.5)),
                fg=fg_text,
                bg=bg_card
            ).pack(side="left")

            # Optional action button (e.g. "Undo")
            if action_label and callable(action_callback):
                def _on_action():
                    cls.dismiss()
                    action_callback()

                btn = tk.Label(
                    card,
                    text=action_label,
                    font=("Segoe UI", sc(9.5), "bold", "underline"),
                    fg=icon_col,
                    bg=bg_card,
                    cursor="hand2"
                )
                btn.pack(side="left", padx=(sc(12), 0))
                btn.bind("<Button-1>", lambda e: _on_action())

            # Click to dismiss
            card.bind("<Button-1>", lambda e: cls.dismiss())

            # Position at bottom-center of the root window
            root.update_idletasks()
            toast.update_idletasks()

            rw = root.winfo_width()
            rh = root.winfo_height()
            rx = root.winfo_rootx()
            ry = root.winfo_rooty()

            tw = toast.winfo_reqwidth()
            th = toast.winfo_reqheight()

            x = rx + max(0, (rw - tw) // 2)
            y = ry + max(0, rh - th - sc(36))

            toast.geometry(f"{tw}x{th}+{x}+{y}")

            cls._active_toast = toast
            cls._root_ref = root
            cls._dismiss_after_id = root.after(duration_ms, cls.dismiss)

        except Exception:
            pass

    @classmethod
    def dismiss(cls) -> None:
        """Dismiss and destroy the current floating toast immediately."""
        if cls._dismiss_after_id is not None and cls._root_ref is not None:
            try:
                cls._root_ref.after_cancel(cls._dismiss_after_id)
            except Exception:
                pass
            cls._dismiss_after_id = None

        if cls._active_toast is not None:
            try:
                if cls._active_toast.winfo_exists():
                    cls._active_toast.destroy()
            except Exception:
                pass
            cls._active_toast = None
