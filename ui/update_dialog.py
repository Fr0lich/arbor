import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import config
from config import sc
import utils
from backend.updater import (
    is_frozen,
    is_install_dir_writable,
    check_for_updates,
    download_update_staged,
    execute_swap_and_restart,
    save_session_state
)


class UpdateDialog:
    """
    Stitch-styled Release Notes & 1-Click Update Dialog.
    Allows curators to review release notes, download updates in the background,
    and restart seamlessly with active session preservation.
    """
    C_BG          = "#fbfaf8"
    C_CARD        = "#ffffff"
    C_HEADER_BG   = "#fbfaf8"
    C_FOOTER_BG   = "#f2f5f1"
    C_SURFACE_LOW = "#f2f5f1"
    C_OUTLINE     = "#747878"
    C_OUTLINE_VAR = "#c4c7c7"
    C_ON_SURFACE  = "#2c302e"
    C_ON_VARIANT  = "#444748"
    C_PRIMARY     = "#000000"
    C_ON_PRIMARY  = "#ffffff"
    C_HOVER       = "#e9ece5"

    def __init__(self, parent, release_info, app=None):
        self.parent = parent
        self.app = app
        self.release_info = release_info
        self.cancel_download_event = threading.Event()
        self.staged_exe_path = None

        self._scale = getattr(config, "_detected_scale", 1.0)
        s = self._scale

        self.win = tk.Toplevel(parent)
        self.win.title("Arbor Update Available")
        self.win.configure(bg=self.C_BG)
        self.win.transient(parent)
        self.win.grab_set()

        w = int(min(620, self.win.winfo_screenwidth() - 40) * s)
        h = int(min(560, self.win.winfo_screenheight() - 70) * s)
        self.win.geometry(f"{w}x{h}")
        self.win.minsize(int(440 * s), int(380 * s))
        utils.center_and_fit_toplevel(self.win, w, h)

        self._build_ui()

    def _build_ui(self):
        s = self._scale

        # ── HEADER ────────────────────────────────────────────────────────
        header = tk.Frame(self.win, bg=self.C_HEADER_BG, padx=int(16*s), pady=int(12*s))
        header.pack(fill="x", side="top")

        top_row = tk.Frame(header, bg=self.C_HEADER_BG)
        top_row.pack(fill="x")

        tk.Label(
            top_row, text="arbor update", font=("Courier New", sc(9), "bold"),
            bg=self.C_HEADER_BG, fg="#3a7d44"
        ).pack(side="left")

        # Version Badge
        cur_v = self.release_info.get("current_version", config.APP_VERSION)
        lat_v = self.release_info.get("latest_version", "New")
        badge_text = f" v{cur_v} ➔ v{lat_v} "
        tk.Label(
            top_row, text=badge_text, font=("Courier New", sc(8.5), "bold"),
            bg="#2d6a4f", fg="#ffffff", padx=4, pady=1
        ).pack(side="right")

        title = self.release_info.get("release_name", f"Arbor v{lat_v}")
        tk.Label(
            header, text=title, font=("Segoe UI", sc(14), "bold"),
            bg=self.C_HEADER_BG, fg=self.C_ON_SURFACE, anchor="w"
        ).pack(fill="x", pady=(int(3*s), 0))

        tk.Frame(self.win, bg=self.C_OUTLINE_VAR, height=1).pack(fill="x", side="top")

        # ── BODY: RELEASE NOTES ───────────────────────────────────────────
        body = tk.Frame(self.win, bg=self.C_BG, padx=int(16*s), pady=int(10*s))
        body.pack(fill="both", expand=True)

        tk.Label(
            body, text="WHAT'S NEW IN THIS RELEASE:",
            font=("Segoe UI", sc(9), "bold"), bg=self.C_BG, fg=self.C_ON_VARIANT, anchor="w"
        ).pack(fill="x", pady=(0, int(4*s)))

        # Scrollable Text for Notes
        txt_frame = tk.Frame(body, bg=self.C_CARD, highlightthickness=1, highlightbackground=self.C_OUTLINE_VAR)
        txt_frame.pack(fill="both", expand=True)

        sb = ttk.Scrollbar(txt_frame, orient="vertical")
        txt = tk.Text(
            txt_frame, wrap="word", font=("Segoe UI", sc(9.5)), relief="flat",
            bg=self.C_CARD, fg=self.C_ON_SURFACE, padx=int(10*s), pady=int(8*s),
            yscrollcommand=sb.set, highlightthickness=0
        )
        sb.config(command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        notes = self.release_info.get("release_notes", "")
        txt.insert("1.0", notes)
        txt.config(state="disabled")

        # Progress / Status Section
        self.progress_frame = tk.Frame(body, bg=self.C_BG)
        self.progress_frame.pack(fill="x", pady=(int(8*s), 0))

        self.status_lbl = tk.Label(
            self.progress_frame, text="", font=("Segoe UI", sc(9)),
            bg=self.C_BG, fg=self.C_ON_VARIANT, anchor="w"
        )
        self.status_lbl.pack(fill="x")

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progressbar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100.0)

        # ── FOOTER ACTIONS ────────────────────────────────────────────────
        tk.Frame(self.win, bg=self.C_OUTLINE_VAR, height=1).pack(fill="x", side="bottom")

        footer = tk.Frame(self.win, bg=self.C_FOOTER_BG, padx=int(16*s), pady=int(10*s))
        footer.pack(fill="x", side="bottom")

        self.cancel_btn = tk.Button(
            footer, text="Remind Me Later", font=("Segoe UI", sc(9.5)),
            bg=self.C_CARD, fg=self.C_ON_SURFACE, relief="flat", bd=0,
            padx=int(14*s), pady=int(6*s), cursor="hand2",
            highlightthickness=1, highlightbackground=self.C_OUTLINE,
            command=self._on_cancel
        )
        self.cancel_btn.pack(side="left")

        # Determine Primary Action Mode
        download_url = self.release_info.get("download_url")

        if not is_frozen():
            # Source / Developer mode
            self.action_btn = tk.Button(
                footer, text="🌐 View Release on GitHub", font=("Segoe UI", sc(9.5), "bold"),
                bg=self.C_PRIMARY, fg=self.C_ON_PRIMARY, relief="flat", bd=0,
                padx=int(16*s), pady=int(6*s), cursor="hand2",
                command=self._open_web_release
            )
            self.action_btn.pack(side="right")
        elif not is_install_dir_writable() or not download_url:
            # Protected folder or no direct .exe asset
            self.action_btn = tk.Button(
                footer, text="🌐 Open Download Page in Browser", font=("Segoe UI", sc(9.5), "bold"),
                bg=self.C_PRIMARY, fg=self.C_ON_PRIMARY, relief="flat", bd=0,
                padx=int(16*s), pady=int(6*s), cursor="hand2",
                command=self._open_web_release
            )
            self.action_btn.pack(side="right")
        else:
            # Full 1-Click Update Mode
            self.action_btn = tk.Button(
                footer, text="⚡ Update Now (1-Click)", font=("Segoe UI", sc(10), "bold"),
                bg=self.C_PRIMARY, fg=self.C_ON_PRIMARY, relief="flat", bd=0,
                padx=int(18*s), pady=int(7*s), cursor="hand2",
                command=self._start_download
            )
            self.action_btn.pack(side="right")
            self.action_btn.bind("<Enter>", lambda e: self.action_btn.config(bg="#333333"))
            self.action_btn.bind("<Leave>", lambda e: self.action_btn.config(bg=self.C_PRIMARY))

    def _open_web_release(self):
        url = self.release_info.get("release_url", f"https://github.com/{config.get_update_repo()}/releases")
        webbrowser.open(url)
        self.win.destroy()

    def _start_download(self):
        download_url = self.release_info.get("download_url")
        if not download_url:
            self._open_web_release()
            return

        self.action_btn.config(state="disabled", text="Downloading...")
        self.cancel_btn.config(text="Cancel Download")
        self.progressbar.pack(fill="x", pady=(2, 0))
        self.status_lbl.config(text="Connecting to GitHub...")

        def _worker():
            try:
                def _prog(percent, cur, total):
                    cur_mb = cur / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    self.win.after(0, lambda: self._update_progress(percent, cur_mb, tot_mb))

                final_exe = download_update_staged(
                    download_url,
                    expected_size=self.release_info.get("asset_size", 0),
                    progress_callback=_prog,
                    cancel_event=self.cancel_download_event
                )
                if final_exe and self.win.winfo_exists():
                    self.win.after(0, lambda: self._on_download_complete(final_exe))
            except Exception as e:
                if self.win.winfo_exists():
                    self.win.after(0, lambda err=e: self._on_download_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress(self, percent, cur_mb, tot_mb):
        if not self.win.winfo_exists():
            return
        self.progress_var.set(percent)
        self.status_lbl.config(text=f"Downloading update: {cur_mb:.1f} MB / {tot_mb:.1f} MB ({percent:.0f}%)")

    def _on_download_complete(self, final_exe):
        self.staged_exe_path = final_exe
        self.progressbar.pack_forget()
        self.status_lbl.config(text="✓ Update downloaded and verified successfully!", fg="#2d6a4f")

        self.cancel_btn.config(text="Apply on Next Exit", command=self._apply_on_exit)

        self.action_btn.config(
            state="normal", text="🔄 Restart & Restore Session",
            bg="#2d6a4f", command=self._restart_now
        )
        self.action_btn.bind("<Enter>", lambda e: self.action_btn.config(bg="#1b4332"))
        self.action_btn.bind("<Leave>", lambda e: self.action_btn.config(bg="#2d6a4f"))

    def _on_download_error(self, error):
        self.progressbar.pack_forget()
        self.status_lbl.config(text=f"Download failed: {error}", fg="#c93a40")
        self.action_btn.config(state="normal", text="🌐 Download in Browser", command=self._open_web_release)

    def _apply_on_exit(self):
        messagebox.showinfo(
            "Update Queued",
            "The update has been staged. It will be installed automatically the next time you close Arbor.",
            parent=self.win
        )
        self.win.destroy()

    def _restart_now(self):
        # In-flight task check
        if self.app and hasattr(self.app, "mobile_server_running") and self.app.mobile_server_running:
            messagebox.showwarning(
                "Mobile Server Active",
                "The Mobile Companion server is actively running. Please stop the server before restarting, or choose 'Apply on Next Exit'.",
                parent=self.win
            )
            return

        # Prompt unsaved changes if needed
        if self.app and hasattr(self.app, "has_unsaved_changes") and self.app.has_unsaved_changes:
            res = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes in your active catalog.\nWould you like to save before restarting?",
                parent=self.win
            )
            if res is None:  # Cancel
                return
            if res and hasattr(self.app, "save_file"):
                self.app.save_file()

        try:
            execute_swap_and_restart(self.app)
        except Exception as e:
            messagebox.showerror("Restart Failed", f"Could not complete update handoff:\n{e}", parent=self.win)

    def _on_cancel(self):
        self.cancel_download_event.set()
        self.win.destroy()


# ============================================================================
# REPOSITORY UNREACHABLE OR 404 FALLBACK DIALOG
# ============================================================================

class RepoUnreachableDialog:
    """
    Intuitive fallback dialog shown when GitHub is unreachable, repository was renamed, or returns 404.
    Empowers users and curators to easily configure a new repository URL or inspect in browser.
    """
    C_BG          = "#fbfaf8"
    C_CARD        = "#ffffff"
    C_HEADER_BG   = "#fbfaf8"
    C_FOOTER_BG   = "#f2f5f1"
    C_SURFACE_LOW = "#f2f5f1"
    C_OUTLINE     = "#747878"
    C_OUTLINE_VAR = "#c4c7c7"
    C_ON_SURFACE  = "#2c302e"
    C_ON_VARIANT  = "#444748"
    C_PRIMARY     = "#000000"
    C_ON_PRIMARY  = "#ffffff"

    def __init__(self, parent, repo_result, on_retry=None):
        self.parent = parent
        self.repo_result = repo_result
        self.on_retry = on_retry
        self.repo = repo_result.get("repo", config.get_update_repo())

        self._scale = getattr(config, "_detected_scale", 1.0)
        s = self._scale

        self.win = tk.Toplevel(parent)
        self.win.title("Unable to Check for Updates")
        self.win.configure(bg=self.C_BG)
        self.win.transient(parent)
        self.win.grab_set()

        w = int(min(520, self.win.winfo_screenwidth() - 40) * s)
        h = int(min(360, self.win.winfo_screenheight() - 70) * s)
        self.win.geometry(f"{w}x{h}")
        utils.center_and_fit_toplevel(self.win, w, h)

        self._build_ui()

    def _build_ui(self):
        s = self._scale

        # Header
        hdr = tk.Frame(self.win, bg=self.C_HEADER_BG, padx=int(16*s), pady=int(12*s))
        hdr.pack(fill="x", side="top")

        tk.Label(
            hdr, text="Unable to Check for Updates", font=("Segoe UI", sc(12), "bold"),
            bg=self.C_HEADER_BG, fg=self.C_ON_SURFACE
        ).pack(anchor="w")

        tk.Label(
            hdr, text=f"Update Source: github.com/{self.repo}", font=("Courier New", sc(9)),
            bg=self.C_HEADER_BG, fg="#c93a40"
        ).pack(anchor="w", pady=(2, 0))

        tk.Frame(self.win, bg=self.C_OUTLINE_VAR, height=1).pack(fill="x", side="top")

        # Body
        body = tk.Frame(self.win, bg=self.C_BG, padx=int(16*s), pady=int(14*s))
        body.pack(fill="both", expand=True)

        msg = (
            "Arbor could not connect to the specified update repository.\n\n"
            "Possible causes:\n"
            "  • The repository was moved, renamed, or transferred to an organization.\n"
            "  • GitHub is temporarily undergoing maintenance or rate-limiting.\n"
            "  • Your workstation is currently offline.\n\n"
            "Your existing database and Arbor installation are functioning normally."
        )
        tk.Label(
            body, text=msg, font=("Segoe UI", sc(9)),
            bg=self.C_BG, fg=self.C_ON_SURFACE, justify="left", anchor="w"
        ).pack(fill="x")

        # Footer Actions
        tk.Frame(self.win, bg=self.C_OUTLINE_VAR, height=1).pack(fill="x", side="bottom")

        footer = tk.Frame(self.win, bg=self.C_FOOTER_BG, padx=int(16*s), pady=int(10*s))
        footer.pack(fill="x", side="bottom")

        tk.Button(
            footer, text="Close", font=("Segoe UI", sc(9)),
            bg=self.C_CARD, fg=self.C_ON_SURFACE, relief="flat", bd=0,
            padx=int(12*s), pady=int(5*s), cursor="hand2",
            highlightthickness=1, highlightbackground=self.C_OUTLINE,
            command=self.win.destroy
        ).pack(side="left")

        tk.Button(
            footer, text="🌐 Open in Browser", font=("Segoe UI", sc(9)),
            bg=self.C_CARD, fg=self.C_ON_SURFACE, relief="flat", bd=0,
            padx=int(12*s), pady=int(5*s), cursor="hand2",
            highlightthickness=1, highlightbackground=self.C_OUTLINE,
            command=lambda: webbrowser.open(f"https://github.com/{self.repo}")
        ).pack(side="left", padx=int(8*s))

        tk.Button(
            footer, text="⚙ Change Repository URL...", font=("Segoe UI", sc(9), "bold"),
            bg=self.C_PRIMARY, fg=self.C_ON_PRIMARY, relief="flat", bd=0,
            padx=int(14*s), pady=int(5*s), cursor="hand2",
            command=self._change_repo
        ).pack(side="right")

    def _change_repo(self):
        new_repo = simpledialog.askstring(
            "Change Update Repository",
            "Enter the GitHub repository (e.g. 'Fr0lich/arbor' or 'Organization/arbor'):",
            initialvalue=self.repo,
            parent=self.win
        )
        if new_repo:
            cleaned = config.set_update_repo(new_repo)
            self.win.destroy()
            if self.on_retry:
                self.on_retry(cleaned)


# ============================================================================
# HIGH-LEVEL CHECK FUNCTION (Called from menus and settings)
# ============================================================================

def check_for_updates_ui(parent_root, app=None, manual=True):
    """
    Non-blocking update check with user-facing dialogs and toast feedback.
    """
    def _worker():
        result = check_for_updates()
        if parent_root.winfo_exists():
            parent_root.after(0, lambda: _handle_result(result))

    def _handle_result(result):
        status = result.get("status")

        if status == "ok":
            if result.get("has_update"):
                UpdateDialog(parent_root, result, app=app)
            elif manual:
                messagebox.showinfo(
                    "Arbor is Up to Date",
                    f"You are running the latest version of Arbor (v{config.APP_VERSION}).\n\nRepository: github.com/{result.get('repo')}",
                    parent=parent_root
                )
        elif status == "404_not_found" or status == "offline_or_error":
            if manual:
                RepoUnreachableDialog(
                    parent_root, result,
                    on_retry=lambda new_r: check_for_updates_ui(parent_root, app=app, manual=True)
                )
        elif status == "rate_limited":
            if manual:
                messagebox.showwarning(
                    "GitHub Rate Limit Reached",
                    "GitHub API request limit reached. Please check releases directly in your browser or try again later.",
                    parent=parent_root
                )
        elif manual:
            messagebox.showerror(
                "Update Check Error",
                result.get("message", "An unexpected error occurred during update check."),
                parent=parent_root
            )

    threading.Thread(target=_worker, daemon=True).start()
