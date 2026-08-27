import tkinter as tk
from tkinter import ttk
import threading
import qrcode
from PIL import ImageTk, Image
from backend.mobile_server import MobileServer, get_local_ip
from backend.tunnel import PinggyTunnel

class MobileDialog:
    def __init__(self, parent_ui, root, app_state):
        self.parent_ui = parent_ui
        self.root = root
        self.app_state = app_state

        self.win = tk.Toplevel(root)
        self.win.title("Arbor Mobile Companion")
        self.win.geometry("540x620")
        self.win.minsize(500, 580)
        self.win.transient(root)
        self.win.grab_set()

        # Center on screen
        self.win.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() // 2) - (540 // 2)
        y = root.winfo_y() + (root.winfo_height() // 2) - (620 // 2)
        self.win.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.server = getattr(self.parent_ui, '_mobile_server_instance', None)
        self.tunnel = None
        self.port = 5055
        self.qr_image_ref = None

        self.build_ui()
        self.start_session()

    def build_ui(self):
        main = tk.Frame(self.win, bg="#ffffff", padx=20, pady=16)
        main.pack(fill="both", expand=True)

        # Header Title
        hdr_frame = tk.Frame(main, bg="#ffffff")
        hdr_frame.pack(fill="x", pady=(0, 10))

        title = tk.Label(hdr_frame, text="📱 Arbor Mobile Companion", font=("Segoe UI", 15, "bold"), bg="#ffffff", fg="#1b4332")
        title.pack(anchor="w")

        subtitle = tk.Label(hdr_frame, text="Inspect physical specimens and record data on your phone in real-time.", bg="#ffffff", fg="#5a655e", font=("Segoe UI", 9))
        subtitle.pack(anchor="w")

        # Status Bar Pill
        self.status_bar = tk.Frame(main, bg="#e8f5e9", bd=1, relief="solid", padx=10, pady=6)
        self.status_bar.pack(fill="x", pady=(0, 10))

        self.status_dot = tk.Label(self.status_bar, text="●", fg="#d97706", bg="#e8f5e9", font=("Segoe UI", 12))
        self.status_dot.pack(side="left", padx=(0, 6))

        self.status_lbl = tk.Label(self.status_bar, text="Starting secure tunnel & local server...", bg="#e8f5e9", fg="#1b4332", font=("Segoe UI", 9, "bold"))
        self.status_lbl.pack(side="left")

        # Middle Content Frame (QR Code + Connection Details)
        mid_frame = tk.Frame(main, bg="#fbfbf9", bd=1, relief="solid", padx=12, pady=12)
        mid_frame.pack(fill="x", pady=(0, 10))

        # QR Code Container
        qr_container = tk.Frame(mid_frame, bg="#ffffff", bd=1, relief="solid", padx=6, pady=6)
        qr_container.pack(side="left", padx=(0, 14))

        self.qr_label = tk.Label(qr_container, bg="#ffffff", text="Generating\nQR Code...", font=("Segoe UI", 9), width=22, height=10)
        self.qr_label.pack()

        # Connection Info Grid
        info_grid = tk.Frame(mid_frame, bg="#fbfbf9")
        info_grid.pack(side="left", fill="both", expand=True)

        tk.Label(info_grid, text="1. Scan QR with phone camera", font=("Segoe UI", 9, "bold"), bg="#fbfbf9", fg="#1b4332").pack(anchor="w", pady=(0, 4))
        tk.Label(info_grid, text="Or open this link on your phone:", font=("Segoe UI", 8), bg="#fbfbf9", fg="#5a655e").pack(anchor="w")

        self.url_var = tk.StringVar(value="Waiting for tunnel...")
        self.url_entry = ttk.Entry(info_grid, textvariable=self.url_var, font=("Consolas", 8), state="readonly")
        self.url_entry.pack(fill="x", pady=(2, 6))

        pin_frame = tk.Frame(info_grid, bg="#fbfbf9")
        pin_frame.pack(fill="x", pady=2)
        tk.Label(pin_frame, text="Access PIN: ", font=("Segoe UI", 9, "bold"), bg="#fbfbf9", fg="#1b4332").pack(side="left")
        self.pin_var = tk.StringVar(value="----")
        self.pin_badge = tk.Label(pin_frame, textvariable=self.pin_var, font=("Consolas", 11, "bold"), bg="#1b4332", fg="#ffffff", padx=8, pady=1)
        self.pin_badge.pack(side="left")

        self.local_ip_lbl = tk.Label(info_grid, text="Local LAN IP: detecting...", font=("Segoe UI", 8), bg="#fbfbf9", fg="#5a655e")
        self.local_ip_lbl.pack(anchor="w", pady=(6, 0))

        # Desktop Lock Notice
        lock_notice = tk.Frame(main, bg="#fffbeb", bd=1, relief="solid", padx=10, pady=6)
        lock_notice.pack(fill="x", pady=(0, 10))
        tk.Label(lock_notice, text="🔒 Desktop editing is locked during mobile session to prevent data collisions.\nAll edits from your phone are safely synced into memory and autosaved.",
                 bg="#fffbeb", fg="#92400e", font=("Segoe UI", 8), justify="left").pack(anchor="w")

        # Live Activity Feed Frame
        feed_frame = tk.LabelFrame(main, text="Recent Mobile Activity", bg="#ffffff", font=("Segoe UI", 9, "bold"), fg="#1b4332", padx=8, pady=6)
        feed_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.feed_list = tk.Listbox(feed_frame, bg="#fbfbf9", font=("Segoe UI", 9), bd=0, highlightthickness=1, selectmode="none")
        self.feed_list.pack(fill="both", expand=True, side="left")

        feed_scroll = ttk.Scrollbar(feed_frame, orient="vertical", command=self.feed_list.yview)
        feed_scroll.pack(side="right", fill="y")
        self.feed_list.config(yscrollcommand=feed_scroll.set)

        self.feed_list.insert(tk.END, "Session initialized. Ready for mobile connections.")

        # Bottom Action Bar
        bottom_bar = tk.Frame(main, bg="#ffffff")
        bottom_bar.pack(fill="x")

        self.stop_btn = ttk.Button(bottom_bar, text="🔴 Disconnect & Resume Desktop Editing", command=self.stop_session)
        self.stop_btn.pack(fill="x", ipady=4)

        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_session(self):
        # 1. Commit active desktop typing before locking
        if hasattr(self.parent_ui, "commit_current_object"):
            try:
                self.parent_ui.commit_current_object()
            except Exception:
                pass

        # 2. Start or reuse MobileServer
        if self.server is None:
            self.server = MobileServer(
                self.app_state,
                root_tk=self.root,
                port=self.port,
                on_edit_callback=self.on_mobile_edit_received
            )
            self.server.start()
            self.parent_ui._mobile_server_instance = self.server
        else:
            self.server.on_edit_callback = self.on_mobile_edit_received

        self.pin_var.set(self.server.pin)
        local_ip = get_local_ip()
        self.local_ip_lbl.config(text=f"Direct Hotspot / Local IP: http://{local_ip}:{self.port}")

        # 3. Start Pinggy SSH Tunnel
        self.status_lbl.config(text="Establishing secure Eduroam bypass tunnel (Pinggy)...")
        self.tunnel = PinggyTunnel(self.port)
        self.tunnel.start(self.on_tunnel_ready)

    def on_tunnel_ready(self, url):
        def update_ui():
            url_with_token = f"{url}?token={self.server.session_token}"
            self.url_var.set(url_with_token)
            self.status_dot.config(fg="#2e7d32")
            self.status_lbl.config(text="🟢 Online & Secure — Ready to inspect", fg="#1b4332")
            
            # Generate QR Code
            try:
                qr = qrcode.QRCode(box_size=3, border=1)
                qr.add_data(url_with_token)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#1b4332", back_color="white")
                self.qr_image_ref = ImageTk.PhotoImage(img)
                self.qr_label.config(image=self.qr_image_ref, text="")
            except Exception as e:
                self.qr_label.config(text="Scan URL\nin phone browser")

            self.feed_list.insert(tk.END, f"Public tunnel ready at {url}")
            self.feed_list.see(tk.END)

        self.root.after(0, update_ui)

    def on_mobile_edit_received(self, oid, summary):
        def log_item():
            ts = threading.current_thread().name
            self.feed_list.insert(tk.END, f"[{ts}] {summary}")
            self.feed_list.see(tk.END)
        self.root.after(0, log_item)

    def stop_session(self):
        if self.tunnel:
            self.tunnel.stop()
            self.tunnel = None

        # Reload active desktop record from DataFrame
        if hasattr(self.parent_ui, "load_object") and self.app_state.current_object_id:
            try:
                self.parent_ui.load_object(self.app_state.current_object_id)
            except Exception:
                pass

        if hasattr(self.parent_ui, "update_dirty_ui"):
            self.parent_ui.update_dirty_ui()
        if hasattr(self.parent_ui, "update_review_progress"):
            self.parent_ui.update_review_progress()

        self.win.destroy()

    def on_close(self):
        self.stop_session()
