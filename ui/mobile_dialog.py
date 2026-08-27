import tkinter as tk
from tkinter import ttk
import threading
from backend.mobile_server import MobileServer
from backend.tunnel import PinggyTunnel, get_local_ip

class MobileDialog:
    def __init__(self, parent_ui, root, app_state):
        self.parent_ui = parent_ui
        self.root = root
        self.app_state = app_state

        self.win = tk.Toplevel(root)
        self.win.title("Mobile Companion")
        self.win.geometry("450x350")
        self.win.transient(root)
        self.win.grab_set()

        # Center
        self.win.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() // 2) - (450 // 2)
        y = root.winfo_y() + (root.winfo_height() // 2) - (350 // 2)
        self.win.geometry(f"+{x}+{y}")

        self.server = None
        self.tunnel = None
        self.port = 5055

        self.build_ui()

    def build_ui(self):
        main = tk.Frame(self.win, bg="white", padx=20, pady=20)
        main.pack(fill="both", expand=True)

        title = tk.Label(main, text="Arbor Mobile App", font=("Segoe UI", 16, "bold"), bg="white", fg="#2e7d32")
        title.pack(pady=(0, 10))

        desc = tk.Label(main, text="Edit the active database directly from your phone.\nMake sure you have an active internet connection.", bg="white", font=("Segoe UI", 10), justify="center")
        desc.pack(pady=(0, 20))

        self.status_lbl = tk.Label(main, text="Server Stopped", bg="white", fg="#666", font=("Segoe UI", 11, "italic"))
        self.status_lbl.pack(pady=(0, 10))

        self.btn_frame = tk.Frame(main, bg="white")
        self.btn_frame.pack(fill="x", pady=10)

        self.start_btn = ttk.Button(self.btn_frame, text="Start Mobile Server", command=self.start_server)
        self.start_btn.pack(ipadx=10, ipady=5)

        self.info_frame = tk.Frame(main, bg="#f5f5f5", bd=1, relief="solid", padx=10, pady=10)

        # URL
        tk.Label(self.info_frame, text="Phone URL:", bg="#f5f5f5", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=2)
        self.url_var = tk.StringVar(value="Waiting for Pinggy tunnel...")
        self.url_entry = ttk.Entry(self.info_frame, textvariable=self.url_var, state="readonly", width=35)
        self.url_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        # PIN
        tk.Label(self.info_frame, text="Access PIN:", bg="#f5f5f5", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", pady=2)
        self.pin_var = tk.StringVar()
        self.pin_entry = ttk.Entry(self.info_frame, textvariable=self.pin_var, state="readonly", width=15)
        self.pin_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # Local IP Fallback
        tk.Label(self.info_frame, text="Local Wi-Fi IP:", bg="#f5f5f5", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", pady=2)
        self.local_var = tk.StringVar()
        self.local_entry = ttk.Entry(self.info_frame, textvariable=self.local_var, state="readonly", width=35)
        self.local_entry.grid(row=2, column=1, sticky="w", padx=5, pady=2)

        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_server(self):
        self.start_btn.config(state="disabled")
        self.status_lbl.config(text="Starting server...", fg="#d97706")

        # 1. Start Flask (Singleton to avoid port issues on restart)
        if self.server is None:
            self.server = MobileServer(self.app_state, self.root, self.port)
            self.server.start()
        else:
             # Just generate a new PIN for security
             import random
             import string
             self.server.pin = ''.join(random.choices(string.digits, k=4))

        self.pin_var.set(self.server.pin)
        self.local_var.set(f"http://{get_local_ip()}:{self.port}")

        # 2. Start Tunnel
        self.status_lbl.config(text="Establishing secure tunnel (may take a moment)...")
        self.tunnel = PinggyTunnel(self.port)
        self.tunnel.start(self.on_tunnel_ready)

        self.info_frame.pack(fill="x", pady=10)
        self.start_btn.config(text="Stop Mobile Server", command=self.stop_server, state="normal")

    def on_tunnel_ready(self, url):
        # Called from background thread
        def update_ui():
            self.url_var.set(url)
            self.status_lbl.config(text="Server Online and Ready", fg="#2e7d32", font=("Segoe UI", 11, "bold"))
            self.parent_ui.show_banner(f"Mobile Server online at {url} (PIN: {self.pin_var.get()})", "success")
        self.root.after(0, update_ui)

    def stop_server(self):
        if self.tunnel:
            self.tunnel.stop()
        # Note: We do not stop Flask so it can safely be restarted without Werkzeug context issues

        self.info_frame.pack_forget()
        self.status_lbl.config(text="Server Stopped (Background running)", fg="#666", font=("Segoe UI", 11, "italic"))
        self.start_btn.config(text="Start Mobile Server", command=self.start_server)

    def on_close(self):
        if self.tunnel:
             # Stop tunnel to avoid hanging processes
             self.tunnel.stop()

        # Optional: could kill server, but let's just hide the window so it keeps running if they want
        # Actually, it's safer to just hide the window and let it run
        self.win.destroy()
