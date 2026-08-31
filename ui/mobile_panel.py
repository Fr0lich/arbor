import os
import tkinter as tk
from tkinter import ttk
import threading
from datetime import datetime
import qrcode
from PIL import ImageTk

from backend.mobile_server import MobileServer, get_local_ip
from backend.tunnel import PinggyTunnel


class MobilePanel:
    """Shared mobile companion panel.

    Renders the full mobile-session UI — QR code, status pill, URL/PIN,
    tunnel status, lock notice, and activity feed.  Both MobileHostApp
    (standalone window) and MobileDialog (in-app Toplevel) embed this
    panel and supply context-specific callbacks for session lifecycle
    actions that differ between the two entry points.

    Parameters
    ----------
    parent : tk widget
        Frame or window to pack the panel into.
    app_state : AppState
        Shared application state (df_reg, excel_path, …).
    root_tk : tk.Tk
        The root Tk window used for after() scheduling.
    port : int
        Port the MobileServer listens on (default 5055).
    on_end_session : callable, optional
        Called when the user clicks "🔴 End Mobile Session".
        The wrapper is responsible for any saving / cleanup beyond
        stopping the tunnel (which the panel always does first).
    on_edit : callable(oid, summary), optional
        Extra hook fired on every incoming mobile edit — used by the
        in-app dialog to notify the main desktop UI.
    reuse_server : MobileServer or None
        Pass a live MobileServer instance to reuse across re-opens
        (in-app dialog mode).  If None a fresh server is started.
    """

    def __init__(
        self,
        parent,
        app_state,
        root_tk,
        port=5055,
        on_end_session=None,
        on_edit=None,
        reuse_server=None,
    ):
        self.parent = parent
        self.app_state = app_state
        self.root = root_tk
        self.port = port
        self.on_end_session = on_end_session
        self.on_edit = on_edit

        self.server = reuse_server
        self.tunnel = None
        self.qr_image_ref = None
        self.local_url_with_token = ""
        self.public_url_with_token = ""
        self.current_qr_mode = "public"  # public tunnel is the default

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        main = tk.Frame(self.parent, bg="#ffffff", padx=20, pady=16)
        main.pack(fill="both", expand=True)
        self._main = main

        # ── Header ────────────────────────────────────────────────────
        hdr = tk.Frame(main, bg="#ffffff")
        hdr.pack(fill="x", pady=(0, 10))

        tk.Label(
            hdr,
            text="📱 Arbor Mobile Companion",
            font=("Segoe UI", 15, "bold"),
            bg="#ffffff",
            fg="#1b4332",
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text="Scan the QR code to inspect & edit records on your phone.",
            bg="#ffffff",
            fg="#5a655e",
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        # DB info line (filled in after server start when we know the path)
        self._db_info_lbl = tk.Label(
            hdr, text="", bg="#ffffff", fg="#5a655e", font=("Segoe UI", 8, "italic")
        )
        self._db_info_lbl.pack(anchor="w")

        # ── Setup Screen ──────────────────────────────────────────────
        self.setup_frame = tk.Frame(main, bg="#ffffff")
        self.setup_frame.pack(fill="both", expand=True, pady=(10, 0))

        tk.Label(
            self.setup_frame,
            text="Choose Network Mode:",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#1b4332",
        ).pack(anchor="w", pady=(0, 5))

        self.network_choice = tk.StringVar(value="public")

        tk.Radiobutton(
            self.setup_frame,
            text="Public (Internet) - Generates a secure link accessible anywhere.",
            variable=self.network_choice,
            value="public",
            bg="#ffffff",
            font=("Segoe UI", 9),
            cursor="hand2"
        ).pack(anchor="w")

        tk.Radiobutton(
            self.setup_frame,
            text="LAN Only - Connect devices on the same Wi-Fi network.",
            variable=self.network_choice,
            value="local",
            bg="#ffffff",
            font=("Segoe UI", 9),
            cursor="hand2"
        ).pack(anchor="w", pady=(0, 15))

        self.start_btn = ttk.Button(
            self.setup_frame,
            text="▶ Start Mobile Session",
            command=self._on_start_btn_clicked,
            cursor="hand2",
        )
        self.start_btn.pack(fill="x", ipady=4)

        # ── Active Frame (Hidden initially) ───────────────────────────
        self.active_frame = tk.Frame(main, bg="#ffffff")
        # Do not pack active_frame yet

        # ── Status pill ───────────────────────────────────────────────
        self.status_bar = tk.Frame(
            self.active_frame, bg="#e8f5e9", bd=1, relief="solid", padx=10, pady=6)
        self.status_bar.pack(fill="x", pady=(0, 10))

        self.status_dot = tk.Label(
            self.status_bar, text="●", fg="#2e7d32", bg="#e8f5e9", font=("Segoe UI", 12)
        )
        self.status_dot.pack(side="left", padx=(0, 6))

        self.status_lbl = tk.Label(
            self.status_bar,
            text="🟢 Local Server Ready — Connecting public tunnel...",
            bg="#e8f5e9",
            fg="#1b4332",
            font=("Segoe UI", 9, "bold"),
        )
        self.status_lbl.pack(side="left")

        self.client_badge = tk.Label(
            self.status_bar, text="📱 Offline", bg="#e8f5e9", fg="#5a655e", font=("Segoe UI", 9)
        )
        self.client_badge.pack(side="right", padx=(0, 6))

        # ── QR + connection info ──────────────────────────────────────
        mid = tk.Frame(self.active_frame, bg="#fbfbf9", bd=1,
                       relief="solid", padx=12, pady=12)
        mid.pack(fill="x", pady=(0, 10))

        # QR box
        qr_box = tk.Frame(mid, bg="#ffffff", bd=1,
                          relief="solid", padx=6, pady=6)
        qr_box.pack(side="left", padx=(0, 14))

        self.qr_label = tk.Label(qr_box, bg="#ffffff")
        self.qr_label.pack()

        mode_btn_frame = tk.Frame(qr_box, bg="#ffffff")
        mode_btn_frame.pack(fill="x", pady=(4, 0))

        self.btn_qr_public = tk.Button(
            mode_btn_frame,
            text="🌐 Public (Internet)",
            font=("Segoe UI", 7, "bold"),
            bg="#1b4332",
            fg="white",
            relief="flat",
            padx=4,
            pady=1,
            command=lambda: self.switch_qr("public"),
            cursor="hand2",
        )
        self.btn_qr_public.pack(side="left", expand=True, fill="x", padx=1)

        self.btn_qr_local = tk.Button(
            mode_btn_frame,
            text="📶 LAN only",
            font=("Segoe UI", 7),
            bg="#e0e3df",
            fg="#333",
            relief="flat",
            padx=4,
            pady=1,
            command=lambda: self.switch_qr("local"),
            cursor="hand2",
        )
        self.btn_qr_local.pack(side="right", expand=True, fill="x", padx=1)

        # Connection info
        info = tk.Frame(mid, bg="#fbfbf9")
        info.pack(side="left", fill="both", expand=True)

        tk.Label(
            info,
            text="1. Scan QR with phone camera",
            font=("Segoe UI", 9, "bold"),
            bg="#fbfbf9",
            fg="#1b4332",
        ).pack(anchor="w", pady=(0, 2))

        tk.Label(
            info,
            text="Or open this link on your phone:",
            font=("Segoe UI", 8),
            bg="#fbfbf9",
            fg="#5a655e",
        ).pack(anchor="w")

        self.url_var = tk.StringVar(value="Initializing...")
        self.url_entry = ttk.Entry(
            info, textvariable=self.url_var, font=("Consolas", 8), state="readonly"
        )
        self.url_entry.pack(fill="x", pady=(2, 4))

        pin_row = tk.Frame(info, bg="#fbfbf9")
        pin_row.pack(fill="x", pady=2)
        tk.Label(
            pin_row, text="PIN: ", font=("Segoe UI", 9, "bold"), bg="#fbfbf9", fg="#1b4332"
        ).pack(side="left")
        self.pin_var = tk.StringVar(value="----")
        self.pin_badge = tk.Label(
            pin_row,
            textvariable=self.pin_var,
            font=("Consolas", 11, "bold"),
            bg="#1b4332",
            fg="#ffffff",
            padx=8,
            pady=1,
        )
        self.pin_badge.pack(side="left")

        self.tunnel_lbl = tk.Label(
            info,
            text="Tunnel: Establishing...",
            font=("Segoe UI", 8, "italic"),
            bg="#fbfbf9",
            fg="#d97706",
        )
        self.tunnel_lbl.pack(anchor="w", pady=(4, 0))

        # Link to main window's simultaneous edit toggle if it exists
        if hasattr(self.parent.master, "parent_ui") and hasattr(self.parent.master.parent_ui, "simultaneous_edit_var"):
            simul_cb = ttk.Checkbutton(
                info,
                text="Enable simultaneous edit",
                variable=self.parent.master.parent_ui.simultaneous_edit_var,
                command=self.parent.master.parent_ui.toggle_simultaneous_edit,
                cursor="hand2"
            )
            simul_cb.pack(anchor="w", pady=(8, 0))

        # ── Session notice ────────────────────────────────────────────
        notice = tk.Frame(self.active_frame, bg="#fffbeb",
                          bd=1, relief="solid", padx=10, pady=6)
        notice.pack(fill="x", pady=(0, 10))
        tk.Label(
            notice,
            text=(
                "📱 Mobile session active. All edits from your phone are synced into memory.\n"
                "Save your database before closing this window to persist changes."
            ),
            bg="#fffbeb",
            fg="#92400e",
            font=("Segoe UI", 8),
            justify="left",
        ).pack(anchor="w")

        # ── Activity feed ─────────────────────────────────────────────
        feed_frame = tk.LabelFrame(
            self.active_frame,
            text="Recent Mobile Activity",
            bg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            fg="#1b4332",
            padx=8,
            pady=6,
        )
        feed_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.feed_list = tk.Listbox(
            feed_frame,
            bg="#fbfbf9",
            font=("Segoe UI", 9),
            bd=0,
            highlightthickness=1,
            selectmode="none",
        )
        self.feed_list.pack(fill="both", expand=True, side="left")

        feed_scroll = ttk.Scrollbar(
            feed_frame, orient="vertical", command=self.feed_list.yview)
        feed_scroll.pack(side="right", fill="y")
        self.feed_list.config(yscrollcommand=feed_scroll.set)

        self.feed_list.insert(
            tk.END, "Session initialized. Ready for mobile connections.")

        # ── Bottom button ─────────────────────────────────────────────
        bottom = tk.Frame(self.active_frame, bg="#ffffff")
        bottom.pack(fill="x")

        self._end_btn = ttk.Button(
            bottom,
            text="🔴 End Mobile Session",
            command=self._on_end_btn,
            cursor="hand2",
        )
        self._end_btn.pack(fill="x", ipady=4)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _on_start_btn_clicked(self):
        self.setup_frame.pack_forget()
        self.active_frame.pack(fill="both", expand=True)
        self._start_services()

    def start(self):
        """Dummy method to not break existing caller assumptions.
        Server now actually starts upon user interacting with UI.
        """
        pass

    def _start_services(self):
        """Start (or reuse) MobileServer and conditionally launch tunnel."""
        # Start or reuse MobileServer
        if self.server is None:
            self.server = MobileServer(
                self.app_state,
                root_tk=self.root,
                port=self.port,
                on_edit_callback=self._on_mobile_edit,
            )
            self.server.start()
        else:
            self.server.app_state = self.app_state
            self.server.root_tk = self.root
            self.server.on_edit_callback = self._on_mobile_edit

        self.server.on_client_connect_callback = self._on_client_connect
        self._on_client_connect(len(self.server.clients))

        # Populate PIN and local URL (kept as LAN fallback)
        self.pin_var.set(self.server.pin)
        local_ip = get_local_ip()
        self.local_url_with_token = (
            f"http://{local_ip}:{self.port}/?token={self.server.session_token}"
        )

        # Update DB info label
        try:
            db_name = os.path.basename(self.app_state.excel_path or "")
            record_count = len(
                self.app_state.df_reg) if self.app_state.df_reg is not None else 0
            self._db_info_lbl.config(
                text=f"DB: {db_name}  ({record_count} records)")
        except Exception:
            pass

        choice = self.network_choice.get()
        if choice == "public":
            # Show connecting placeholder — public QR renders in _on_tunnel_ready()
            self.url_var.set("🔄 Connecting public tunnel…")
            self.qr_label.config(
                image="",
                text="🔄 Connecting\npublic tunnel…",
                font=("Segoe UI", 9, "italic"),
                fg="#d97706",
            )
            self.log(f"Local LAN fallback: http://{local_ip}:{self.port}")

            # Start localhost.run tunnel in background
            self.tunnel = PinggyTunnel(self.port)
            self.tunnel.start(self._on_tunnel_ready, self._on_tunnel_status)
        else:
            # Local only mode
            self.tunnel_lbl.config(
                text="Tunnel: Disabled (LAN Only)", fg="#5a655e")
            self.status_lbl.config(text="🟢 Local Server Ready", fg="#1b4332")
            self.switch_qr("local")
            self.log(
                f"Server started in LAN-only mode: http://{local_ip}:{self.port}")

    def _is_alive(self):
        """Check if widget hierarchy is still valid and not destroyed."""
        try:
            return (
                hasattr(self, "_main")
                and self._main is not None
                and bool(self._main.winfo_exists())
                and hasattr(self, "client_badge")
                and self.client_badge is not None
                and bool(self.client_badge.winfo_exists())
            )
        except Exception:
            return False


    def stop(self):
        """Stop the tunnel (does not save data — wrapper handles that)."""
        if self.server:
            try:
                self.server.broadcast_event('session_ended', {})
            except Exception:
                pass
            if getattr(self.server, 'on_client_connect_callback', None) == self._on_client_connect:
                self.server.on_client_connect_callback = None
            if getattr(self.server, 'on_edit_callback', None) == self._on_mobile_edit:
                self.server.on_edit_callback = None

        if self.tunnel:
            self.tunnel.stop()
            self.tunnel = None

    def log(self, message: str):
        """Append a timestamped line to the activity feed."""
        def _append():
            if not self._is_alive():
                return
            try:
                ts = datetime.now().strftime("%H:%M:%S")
                self.feed_list.insert(tk.END, f"[{ts}] {message}")
                self.feed_list.see(tk.END)
            except Exception:
                pass
        try:
            if self._is_alive():
                self.root.after(0, _append)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _render_qr(self, url_to_encode):
        """Generate and display a QR code for the given URL."""
        if not self._is_alive():
            return
        try:
            qr = qrcode.QRCode(box_size=3, border=1)
            qr.add_data(url_to_encode)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#1b4332", back_color="white")
            self.qr_image_ref = ImageTk.PhotoImage(img)
            self.qr_label.config(image=self.qr_image_ref, text="")
        except Exception:
            try:
                self.qr_label.config(text=f"Scan URL:\n{url_to_encode[:25]}...")
            except Exception:
                pass

    def switch_qr(self, mode):
        """Toggle the QR code between local and public URL."""
        if not self._is_alive():
            return
        self.current_qr_mode = mode
        try:
            if mode == "local":
                self.btn_qr_local.config(
                    bg="#1b4332", fg="white", font=("Segoe UI", 7, "bold"))
                self.btn_qr_public.config(
                    bg="#e0e3df", fg="#333", font=("Segoe UI", 7))
                self.url_var.set(self.local_url_with_token)
                self._render_qr(self.local_url_with_token)
            else:
                self.btn_qr_public.config(
                    bg="#1b4332", fg="white", font=("Segoe UI", 7, "bold"))
                self.btn_qr_local.config(
                    bg="#e0e3df", fg="#333", font=("Segoe UI", 7))
                url = self.public_url_with_token or self.local_url_with_token
                self.url_var.set(url)
                self._render_qr(url)
        except Exception:
            pass

    def _on_tunnel_status(self, status):
        def _update():
            if not self._is_alive():
                return
            try:
                self.status_lbl.config(text=status, fg="#d95c14")
                self.status_dot.config(fg="#d95c14")
                self.tunnel_lbl.config(text="Tunnel: Disconnected", fg="#d95c14")
                self.feed_list.insert(tk.END, status)
                self.feed_list.see(tk.END)
            except Exception:
                pass
        try:
            if self._is_alive():
                self.root.after(0, _update)
        except Exception:
            pass

    def _on_tunnel_ready(self, url):
        def _update():
            if not self._is_alive():
                return
            try:
                self.public_url_with_token = f"{url}?token={self.server.session_token}"
                self.status_dot.config(fg="#2e7d32")
                self.status_lbl.config(
                    text="🟢 Public Tunnel Live & Secure", fg="#1b4332")
                self.tunnel_lbl.config(
                    text=f"Public: {url}", fg="#2e7d32", font=("Segoe UI", 8))
                self.btn_qr_public.config(text="🌐 Public (Internet) ✓")
                # Always switch to the public QR as soon as the tunnel is ready
                self.switch_qr("public")
                self.feed_list.insert(
                    tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Public tunnel ready: {url}")
                self.feed_list.see(tk.END)
            except Exception:
                pass
        try:
            if self._is_alive():
                self.root.after(0, _update)
        except Exception:
            pass

    def _on_client_connect(self, active_count):
        def _update():
            if not self._is_alive():
                return
            try:
                if active_count > 0:
                    self.client_badge.config(
                        text=f"📱 Phone Connected ({active_count} Online)",
                        fg="#2e7d32",
                        font=("Segoe UI", 9, "bold"),
                    )
                else:
                    self.client_badge.config(
                        text="📱 Offline", fg="#5a655e", font=("Segoe UI", 9)
                    )
            except Exception:
                pass
        try:
            if self._is_alive():
                self.root.after(0, _update)
        except Exception:
            pass

    def _on_mobile_edit(self, oid, summary):
        # Log to feed
        self.log(summary)
        # Notify the wrapper (e.g. desktop UI sync)
        if self.on_edit:
            try:
                self.on_edit(oid, summary)
            except Exception:
                pass

    def _on_end_btn(self):
        """Stop tunnel, then hand off to the wrapper's on_end_session."""
        self.stop()
        if self.on_end_session:
            try:
                self.on_end_session()
            except Exception:
                pass
