"""
ui/mobile_dialog.py

Desktop controller dialog for Arbor Mobile Web Companion.
Displays live pairing QR code, public relay status, session security PIN,
one-click copy/open actions, and real-time activity log feed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from typing import Any
from PIL import ImageTk

from config import sc
from models import AppState
from backend.mobile_server import MobileServerManager
from backend.tunnel import SSHTunnelManager


class MobileCompanionDialog:
    """Desktop controller window for managing the embedded mobile server and reverse tunnel."""

    def __init__(self, parent_ui: Any, app_state: AppState):
        self.main_ui = parent_ui
        self.app_state = app_state
        self.root = parent_ui.root
        
        # Ensure server and tunnel managers exist on main_ui
        if not hasattr(parent_ui, "mobile_server_mgr") or parent_ui.mobile_server_mgr is None:
            parent_ui.mobile_server_mgr = MobileServerManager(app_state, root_tk=self.root)
        if not hasattr(parent_ui, "mobile_tunnel_mgr") or parent_ui.mobile_tunnel_mgr is None:
            port = parent_ui.mobile_server_mgr.port
            token = parent_ui.mobile_server_mgr.session_token
            parent_ui.mobile_tunnel_mgr = SSHTunnelManager(local_port=port, session_token=token)

        self.server_mgr: MobileServerManager = parent_ui.mobile_server_mgr
        self.tunnel_mgr: SSHTunnelManager = parent_ui.mobile_tunnel_mgr

        self._qr_image_tk: ImageTk.PhotoImage | None = None
        self._is_closing = False

        # Create Toplevel Window
        self.win = tk.Toplevel(self.root)
        self.win.title("Arbor · Mobile Companion")
        self.win.geometry(f"{int(sc(460))}x{int(sc(630))}")
        self.win.configure(bg="#fbfaf8")
        self.win.resizable(False, False)
        self.win.transient(self.root)
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()

        # Start server & tunnel if not running
        if not self.server_mgr.is_running:
            self.server_mgr.start()
            self.tunnel_mgr.local_port = self.server_mgr.port
            self.tunnel_mgr.session_token = self.server_mgr.session_token

        if self.tunnel_mgr.status == "stopped":
            self.tunnel_mgr.start()

        self._attach_tunnel_callback()
        self._refresh_display()

    def _build_ui(self):
        # 1. Header Frame
        header = tk.Frame(self.win, bg="#2c302e", padx=int(sc(16)), pady=int(sc(12)))
        header.pack(fill="x")

        title_row = tk.Frame(header, bg="#2c302e")
        title_row.pack(fill="x")

        tk.Label(
            title_row,
            text="MOBILE WEB COMPANION",
            bg="#2c302e",
            fg="#fbfaf8",
            font=("Segoe UI", int(sc(11)), "bold")
        ).pack(side="left")

        self.btn_toggle_server = tk.Button(
            title_row,
            text="Stop Server",
            bg="#c93a40",
            fg="white",
            activebackground="#a8282e",
            activeforeground="white",
            font=("Segoe UI", int(sc(8)), "bold"),
            relief="flat",
            padx=int(sc(8)),
            pady=int(sc(2)),
            command=self._toggle_server_state,
            cursor="hand2"
        )
        self.btn_toggle_server.pack(side="right")

        db_name = self.app_state.config_name or "Active Collection"
        tk.Label(
            header,
            text=f"Collection: {db_name}",
            bg="#2c302e",
            fg="#a4cca9",
            font=("Segoe UI", int(sc(9)))
        ).pack(anchor="w", pady=(int(sc(2)), 0))

        # Main Body Frame
        body = tk.Frame(self.win, bg="#fbfaf8", padx=int(sc(16)), pady=int(sc(12)))
        body.pack(fill="both", expand=True)

        # 2. QR Code Preview Container
        qr_card = tk.Frame(body, bg="#ffffff", bd=1, relief="solid", highlightthickness=0)
        qr_card.pack(fill="x", pady=(0, int(sc(8))))

        # Connection Mode Switcher
        mode_frame = tk.Frame(qr_card, bg="#ffffff")
        mode_frame.pack(fill="x", padx=int(sc(8)), pady=(int(sc(6)), int(sc(4))))

        self.conn_mode_var = tk.StringVar(value="relay")

        r_relay = tk.Radiobutton(
            mode_frame,
            text="Public Relay (No Login)",
            variable=self.conn_mode_var,
            value="relay",
            bg="#ffffff",
            fg="#191e1a",
            selectcolor="#ffffff",
            activebackground="#ffffff",
            font=("Segoe UI", int(sc(8)), "bold"),
            command=self._on_mode_changed
        )
        r_relay.pack(side="left", padx=(0, int(sc(6))))

        r_local = tk.Radiobutton(
            mode_frame,
            text="Direct Wi-Fi (Fastest)",
            variable=self.conn_mode_var,
            value="local",
            bg="#ffffff",
            fg="#191e1a",
            selectcolor="#ffffff",
            activebackground="#ffffff",
            font=("Segoe UI", int(sc(8)), "bold"),
            command=self._on_mode_changed
        )
        r_local.pack(side="left")

        self.qr_label = tk.Label(qr_card, bg="#ffffff")
        self.qr_label.pack(pady=(0, int(sc(8))))

        # 3. Pairing URL Bar
        url_frame = tk.Frame(body, bg="#fbfaf8")
        url_frame.pack(fill="x", pady=(0, int(sc(10))))

        self.url_var = tk.StringVar(value="Generating pairing URL...")
        url_entry = tk.Entry(
            url_frame,
            textvariable=self.url_var,
            state="readonly",
            bg="#ffffff",
            fg="#191e1a",
            font=("Courier New", int(sc(9))),
            relief="solid",
            bd=1
        )
        url_entry.pack(side="left", fill="x", expand=True, ipady=int(sc(4)), padx=(0, int(sc(6))))

        btn_copy = tk.Button(
            url_frame,
            text="Copy URL",
            bg="#e9ece5",
            fg="#191e1a",
            activebackground="#dfe3e0",
            font=("Segoe UI", int(sc(8)), "bold"),
            relief="flat",
            padx=int(sc(8)),
            command=self._copy_url,
            cursor="hand2"
        )
        btn_copy.pack(side="left", padx=(0, int(sc(4))) )

        btn_open = tk.Button(
            url_frame,
            text="Open",
            bg="#3a7d44",
            fg="white",
            activebackground="#2c6034",
            activeforeground="white",
            font=("Segoe UI", int(sc(8)), "bold"),
            relief="flat",
            padx=int(sc(8)),
            command=self._open_in_browser,
            cursor="hand2"
        )
        btn_open.pack(side="left")

        # 4. Connection Diagnostics Matrix
        diag_card = tk.Frame(body, bg="#ffffff", bd=1, relief="solid", padx=int(sc(10)), pady=int(sc(8)))
        diag_card.pack(fill="x", pady=(0, int(sc(10))))

        def _diag_row(parent, label, default_val):
            r = tk.Frame(parent, bg="#ffffff")
            r.pack(fill="x", pady=1)
            tk.Label(r, text=label, bg="#ffffff", fg="#848f87", font=("Segoe UI", int(sc(8))), width=16, anchor="w").pack(side="left")
            val_lbl = tk.Label(r, text=default_val, bg="#ffffff", fg="#191e1a", font=("Segoe UI", int(sc(8)), "bold"), anchor="w")
            val_lbl.pack(side="left", fill="x", expand=True)
            return val_lbl

        self.lbl_server_status = _diag_row(diag_card, "Local Server:", f"Active (Port {self.server_mgr.port})")
        self.lbl_tunnel_status = _diag_row(diag_card, "Tunnel Relay:", "Connecting...")
        self.lbl_token = _diag_row(diag_card, "Security PIN:", self.server_mgr.session_token)

        # 5. Live Activity Feed
        feed_hdr = tk.Frame(body, bg="#fbfaf8")
        feed_hdr.pack(fill="x", pady=(0, int(sc(4))))
        tk.Label(
            feed_hdr,
            text="LIVE ACTIVITY LOG",
            bg="#fbfaf8",
            fg="#535d56",
            font=("Segoe UI", int(sc(8)), "bold")
        ).pack(side="left")

        self.log_text = tk.Text(
            body,
            height=5,
            bg="#ffffff",
            fg="#191e1a",
            font=("Courier New", int(sc(8))),
            relief="solid",
            bd=1,
            state="disabled",
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True)

        self.log_activity("Mobile Companion controller initialized.")

    def _attach_tunnel_callback(self):
        """Attaches status listener marshaling updates to the Tkinter main thread."""
        def _safe_callback(status):
            if not self._is_closing and self.win.winfo_exists():
                self.root.after(0, lambda: self._on_tunnel_status_update(status))
        self.tunnel_mgr.set_status_callback(_safe_callback)

    def _on_tunnel_status_update(self, status: dict):
        """Updates UI status pills and QR code on the main GUI thread."""
        if not self.win.winfo_exists():
            return
        self._refresh_display()

    def _on_mode_changed(self):
        """Handler when user switches between Public Relay and Direct Wi-Fi."""
        mode = self.conn_mode_var.get()
        if mode == "local":
            self.log_activity(f"Switched to Direct Wi-Fi mode ({self.tunnel_mgr.local_ip}:{self.server_mgr.port})")
        else:
            self.log_activity("Switched to Public Relay mode (No Login required)")
        self._refresh_display()

    def _refresh_display(self):
        """Refreshes all text variables, QR codes, and diagnostics."""
        if not self.win.winfo_exists():
            return

        mode = getattr(self, "conn_mode_var", None)
        prefer_mode = mode.get() if mode else "relay"

        pairing_url = self.tunnel_mgr.get_pairing_url(prefer=prefer_mode)
        self.url_var.set(pairing_url)

        # Update QR Code
        try:
            pil_img = self.tunnel_mgr.generate_pairing_qr_code(box_size=int(sc(5)), prefer=prefer_mode)
            self._qr_image_tk = ImageTk.PhotoImage(pil_img)
            self.qr_label.configure(image=self._qr_image_tk)
        except Exception:
            pass

        # Update Diagnostics
        t_status = self.tunnel_mgr.status
        if t_status == "connected":
            self.lbl_tunnel_status.configure(text=f"● Connected ({self.tunnel_mgr.active_provider})", fg="#3a7d44")
        elif t_status in ("starting", "reconnecting"):
            self.lbl_tunnel_status.configure(text=f"◌ {t_status.capitalize()}...", fg="#d9a036")
        else:
            self.lbl_tunnel_status.configure(text="Local Wi-Fi Only", fg="#535d56")

        if self.server_mgr.is_running:
            self.lbl_server_status.configure(text=f"● Active (Port {self.server_mgr.port})", fg="#3a7d44")
            self.btn_toggle_server.configure(text="Stop Server", bg="#c93a40")
        else:
            self.lbl_server_status.configure(text="● Stopped", fg="#dc2626")
            self.btn_toggle_server.configure(text="Start Server", bg="#3a7d44")

    def _toggle_server_state(self):
        if self.server_mgr.is_running:
            self.server_mgr.stop()
            self.tunnel_mgr.stop()
            self.log_activity("Server and tunnel stopped.")
        else:
            self.server_mgr.start()
            self.tunnel_mgr.local_port = self.server_mgr.port
            self.tunnel_mgr.session_token = self.server_mgr.session_token
            self.tunnel_mgr.start()
            self.log_activity("Server and tunnel started.")
        self._refresh_display()

    def _copy_url(self):
        url = self.url_var.get()
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.log_activity("Pairing URL copied to clipboard.")

    def _open_in_browser(self):
        url = self.url_var.get()
        webbrowser.open(url)
        self.log_activity("Opened Mobile Companion in browser.")

    def log_activity(self, message: str):
        """Appends a line to the real-time activity log feed."""
        if not self.win.winfo_exists():
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def on_close(self):
        """Closes dialog window without stopping background server."""
        self._is_closing = True
        self.tunnel_mgr.set_status_callback(None)
        self.win.destroy()
        if hasattr(self.main_ui, "_mobile_dialog"):
            self.main_ui._mobile_dialog = None
