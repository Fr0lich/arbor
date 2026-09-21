"""
ui/tutorials/tutorial_runner.py

Action-driven interactive tutorial engine for Arbor.
Provides event-gated step progression, glowing target element highlights,
and persistent skip/exit controls.
"""

import tkinter as tk
from tkinter import ttk
from config import sc
from .sandbox_manager import SandboxManager


class ActionStep:
    def __init__(self, step_id, title, instruction, target_id=None,
                 action_hint=None, on_enter=None, validator=None):
        self.step_id = step_id
        self.title = title
        self.instruction = instruction
        self.target_id = target_id
        self.action_hint = action_hint
        self.on_enter = on_enter
        self.validator = validator


class TutorialHighlight:
    """Animated glowing border frame around a target widget."""
    def __init__(self, parent, target_widget):
        self.target_widget = target_widget
        self.win = tk.Toplevel(parent)
        if parent:
            try:
                self.win.transient(parent)
            except Exception:
                pass
        self.win.overrideredirect(True)

        try:
            self.win.attributes("-transparentcolor", "black")
        except Exception:
            pass
        self.win.config(bg="black")

        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.rect = self.canvas.create_rectangle(0, 0, 10, 10, outline="#00c8ff", width=4)

        self._anim_idx = 0
        self.win.deiconify()
        self.win.lift()
        self.update_position()
        self.animate()

    def update_position(self):
        try:
            if not self.target_widget or not self.target_widget.winfo_exists() or not self.target_widget.winfo_viewable():
                if self.win.winfo_exists():
                    self.win.withdraw()
                return

            x = self.target_widget.winfo_rootx()
            y = self.target_widget.winfo_rooty()
            w = self.target_widget.winfo_width()
            h = self.target_widget.winfo_height()

            pad = 4
            if self.win.winfo_exists():
                self.win.deiconify()
                self.win.geometry(f"{w + pad*2}x{h + pad*2}+{x - pad}+{y - pad}")
                self.canvas.coords(self.rect, pad, pad, w + pad, h + pad)
        except Exception:
            try:
                if self.win.winfo_exists():
                    self.win.withdraw()
            except Exception:
                pass

    def animate(self):
        if not self.win.winfo_exists():
            return
        colors = ["#00c8ff", "#0088ff", "#0055ff", "#0088ff"]
        try:
            self.canvas.itemconfig(self.rect, outline=colors[self._anim_idx])
        except Exception:
            pass
        self._anim_idx = (self._anim_idx + 1) % len(colors)
        self.update_position()
        try:
            self.win.after(250, self.animate)
        except Exception:
            pass

    def destroy(self):
        if self.win.winfo_exists():
            try:
                self.win.destroy()
            except Exception:
                pass


class TutorialRunner:
    """Drives step progression and UI synchronization for an action-driven tutorial."""
    def __init__(self, ui, steps, tutorial_name="Interactive Tutorial", on_complete=None):
        self.ui = ui
        self.steps = steps
        self.tutorial_name = tutorial_name
        self.on_complete = on_complete
        self.current_idx = 0

        self.hud_win = None
        self.highlight = None
        self._poll_job = None
        self.root = ui.root if hasattr(ui, "root") else ui

        self._build_hud()
        self.show_step()

    def _build_hud(self):
        self.hud_win = tk.Toplevel(self.root)
        self.hud_win.title(f"Arbor Tutorial - {self.tutorial_name}")
        self.hud_win.attributes("-topmost", True)
        self.hud_win.resizable(False, False)
        self.hud_win.config(bg="#1e1e2d")

        # Main HUD container
        frame = tk.Frame(self.hud_win, bg="#1e1e2d", padx=sc(16), pady=sc(14))
        frame.pack(fill="both", expand=True)

        # Header Row: Badge & Progress
        hdr_row = tk.Frame(frame, bg="#1e1e2d")
        hdr_row.pack(fill="x", pady=(0, sc(6)))

        self.badge_lbl = tk.Label(
            hdr_row,
            text="TUTORIAL MODE (SANDBOX)",
            font=("Segoe UI", sc(8), "bold"),
            bg="#2e384d",
            fg="#00c8ff",
            padx=sc(6),
            pady=sc(2)
        )
        self.badge_lbl.pack(side="left")

        self.step_counter_lbl = tk.Label(
            hdr_row,
            text=f"STEP 1 OF {len(self.steps)}",
            font=("Segoe UI", sc(8), "bold"),
            bg="#1e1e2d",
            fg="#a0a5b5"
        )
        self.step_counter_lbl.pack(side="right")

        # Step Title
        self.title_lbl = tk.Label(
            frame,
            text="",
            font=("Segoe UI", sc(12), "bold"),
            bg="#1e1e2d",
            fg="#ffffff",
            anchor="w",
            justify="left"
        )
        self.title_lbl.pack(fill="x", pady=(0, sc(6)))

        # Instruction Text
        self.instruction_lbl = tk.Label(
            frame,
            text="",
            font=("Segoe UI", sc(10)),
            bg="#1e1e2d",
            fg="#e0e0e0",
            anchor="w",
            justify="left",
            wraplength=sc(380)
        )
        self.instruction_lbl.pack(fill="x", pady=(0, sc(12)))

        # Action hint bar
        self.hint_frame = tk.Frame(frame, bg="#141420", padx=sc(8), pady=sc(6))
        self.hint_frame.pack(fill="x", pady=(0, sc(14)))

        self.hint_lbl = tk.Label(
            self.hint_frame,
            text="",
            font=("Segoe UI", sc(9), "italic"),
            bg="#141420",
            fg="#00e5ff",
            anchor="w",
            justify="left"
        )
        self.hint_lbl.pack(fill="x")

        # Footer Button Bar
        btn_bar = tk.Frame(frame, bg="#1e1e2d")
        btn_bar.pack(fill="x")

        self.exit_btn = tk.Button(
            btn_bar,
            text="Exit Tutorial",
            font=("Segoe UI", sc(9)),
            bg="#2c2c3e",
            fg="#ff7b72",
            relief="flat",
            cursor="hand2",
            padx=sc(8),
            pady=sc(4),
            command=self.exit_tutorial
        )
        self.exit_btn.pack(side="left")

        self.next_btn = tk.Button(
            btn_bar,
            text="Skip Step →",
            font=("Segoe UI", sc(9)),
            bg="#00c8ff",
            fg="#000000",
            relief="flat",
            cursor="hand2",
            padx=sc(10),
            pady=sc(4),
            command=self.next_step
        )
        self.next_btn.pack(side="right", padx=(sc(6), 0))

        self.prev_btn = tk.Button(
            btn_bar,
            text="← Back",
            font=("Segoe UI", sc(9)),
            bg="#2c2c3e",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=sc(8),
            pady=sc(4),
            command=self.prev_step
        )
        self.prev_btn.pack(side="right")

        # Position HUD in top-right corner of parent or screen
        self._position_hud()

    def _position_hud(self):
        try:
            self.hud_win.update_idletasks()
            w = self.hud_win.winfo_reqwidth()
            h = self.hud_win.winfo_reqheight()
            
            if hasattr(self.ui, "root") and self.ui.root.winfo_exists():
                rx = self.ui.root.winfo_rootx()
                ry = self.ui.root.winfo_rooty()
                rw = self.ui.root.winfo_width()
                x = rx + rw - w - sc(24)
                y = ry + sc(50)
            else:
                sw = self.hud_win.winfo_screenwidth()
                x = sw - w - sc(24)
                y = sc(50)

            x = max(10, x)
            y = max(10, y)
            self.hud_win.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def show_step(self):
        self._cleanup_highlight()
        if self._poll_job:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None

        if self.current_idx >= len(self.steps):
            self.finish_tutorial()
            return

        step = self.steps[self.current_idx]
        self.step_counter_lbl.config(text=f"STEP {self.current_idx + 1} OF {len(self.steps)}")
        self.title_lbl.config(text=step.title)
        self.instruction_lbl.config(text=step.instruction)

        if step.action_hint:
            self.hint_frame.pack(fill="x", pady=(0, sc(14)))
            self.hint_lbl.config(text=f"Action: {step.action_hint}")
        else:
            self.hint_frame.pack_forget()

        self.prev_btn.config(state="normal" if self.current_idx > 0 else "disabled")
        is_last = (self.current_idx == len(self.steps) - 1)
        self.next_btn.config(text="Finish ✓" if is_last else "Skip Step →")

        # Trigger on_enter callback if specified
        if step.on_enter:
            try:
                step.on_enter(self.ui)
            except Exception:
                pass

        # Highlight target widget
        target_widget = self._find_target(step.target_id)
        if target_widget:
            try:
                self.highlight = TutorialHighlight(self.root, target_widget)
            except Exception:
                self.highlight = None

        # Start validator polling if a validator condition is provided
        if step.validator:
            self._poll_validator(step.validator)

    def _poll_validator(self, validator_fn):
        try:
            if validator_fn(self.ui):
                self.next_step()
                return
        except Exception:
            pass
        self._poll_job = self.root.after(300, lambda: self._poll_validator(validator_fn))

    def _find_target(self, target_id):
        if not target_id:
            return None
        if isinstance(target_id, tk.Widget):
            return target_id
        if hasattr(self.ui, target_id):
            attr = getattr(self.ui, target_id)
            if isinstance(attr, tk.Widget):
                return attr
        # Search widget tree by tutorial_id
        return self._search_by_tutorial_id(self.root, target_id)

    def _search_by_tutorial_id(self, root, target_id):
        try:
            if not root or not root.winfo_exists():
                return None
            if getattr(root, "tutorial_id", None) == target_id:
                return root
            for child in root.winfo_children():
                res = self._search_by_tutorial_id(child, target_id)
                if res:
                    return res
        except Exception:
            pass
        return None

    def _cleanup_highlight(self):
        if self.highlight:
            try:
                self.highlight.destroy()
            except Exception:
                pass
            self.highlight = None

    def next_step(self):
        self.current_idx += 1
        self.show_step()

    def prev_step(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.show_step()

    def finish_tutorial(self):
        self._cleanup()
        SandboxManager().exit_sandbox(self.ui)
        if self.on_complete:
            try:
                self.on_complete()
            except Exception:
                pass

    def exit_tutorial(self):
        self._cleanup()
        SandboxManager().exit_sandbox(self.ui)

    def _cleanup(self):
        self._cleanup_highlight()
        if self._poll_job:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        if self.hud_win:
            try:
                self.hud_win.destroy()
            except Exception:
                pass
            self.hud_win = None
