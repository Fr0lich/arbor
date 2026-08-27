import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import qrcode
from PIL import ImageTk, Image
from datetime import datetime

from models import AppState
import config
from repository import ExcelRepository, SQLiteRepository
from backend.mobile_server import MobileServer, get_local_ip
from backend.tunnel import PinggyTunnel
from utils import debug_error


class MobileHostApp:
    """Lightweight companion host application for Arbor.
    
    Bypasses building the heavy 9,000+ line Tkinter desktop interface,
    allowing near-instant startup, minimal RAM (< 40MB), and long battery life.
    """

    def __init__(self, file_path=None):
        self.root = tk.Tk()
        self.root.title("Arbor Mobile Host")
        self.root.geometry("460x560")
        self.root.minsize(420, 500)
        self.root.configure(bg="#ffffff")

        self.app = AppState()
        self.server = None
        self.tunnel = None
        self.port = 5055
        self.qr_image_ref = None
        self.autosave_job = None

        self._init_database(file_path)
        self._build_ui()
        self._start_services()
        self._schedule_autosave()

    def _init_database(self, file_path):
        if not file_path or not os.path.exists(file_path):
            # Check recent preferences
            prefs = config.load_prefs()
            last_file = prefs.get("last_opened_file")
            if last_file and os.path.exists(last_file):
                file_path = last_file
            else:
                self.root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Select Database for Mobile Session",
                    filetypes=[("Database Files", "*.xlsx *.xls *.db *.sqlite"), ("All Files", "*.*")]
                )
                self.root.deiconify()

        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("No Database", "No database selected. Exiting mobile host.")
            sys.exit(0)

        self.app.excel_path = os.path.abspath(file_path)
        self.app.output_path = self.app.excel_path
        self.app.config_name = "Botanical Herbarium"
        self.app.config = config.DATABASE_CONFIGS.get(self.app.config_name, next(iter(config.DATABASE_CONFIGS.values())))

        # Load database into memory
        try:
            if file_path.endswith((".db", ".sqlite", ".sqlite3")):
                df_reg, df_obs, df_photo, df_log = SQLiteRepository.load_sqlite(self.app.excel_path, self.app.config)
            else:
                df_reg, df_obs, df_photo, df_log = ExcelRepository.load_excel(self.app.excel_path, self.app.config)

            if "ObjectID" in df_reg.columns:
                df_reg["ObjectID"] = df_reg["ObjectID"].astype(str).str.strip()
                df_reg = df_reg.set_index("ObjectID")
            if "ObjectID" in df_obs.columns:
                df_obs["ObjectID"] = df_obs["ObjectID"].astype(str).str.strip()
                df_obs = df_obs.set_index("ObjectID")
            if "ObjectID" in df_photo.columns:
                df_photo["ObjectID"] = df_photo["ObjectID"].astype(str).str.strip()
                df_photo = df_photo.set_index("ObjectID")

            self.app.df_reg = df_reg
            self.app.df_obs = df_obs
            self.app.df_photo = df_photo
            self.app.df_log = df_log
            self.app._log_records = df_log.to_dict(orient="records") if (df_log is not None and not df_log.empty) else []
            self.app.dirty = False

            # Update preferences
            prefs = config.load_prefs()
            prefs["last_opened_file"] = self.app.excel_path
            config.save_prefs(prefs)
        except Exception as e:
            debug_error("MobileHostApp DB Load Error", str(e))
            messagebox.showerror("Load Error", f"Failed to load database: {e}")
            sys.exit(1)

    def _build_ui(self):
        main = tk.Frame(self.root, bg="#ffffff", padx=16, pady=16)
        main.pack(fill="both", expand=True)

        # Header
        hdr = tk.Frame(main, bg="#ffffff")
        hdr.pack(fill="x", pady=(0, 8))

        title = tk.Label(hdr, text="🌿 Arbor Mobile Host", font=("Segoe UI", 15, "bold"), bg="#ffffff", fg="#1b4332")
        title.pack(anchor="w")

        db_name = os.path.basename(self.app.excel_path)
        sub = tk.Label(hdr, text=f"Active DB: {db_name} ({len(self.app.df_reg)} records)", font=("Segoe UI", 9), bg="#ffffff", fg="#5a655e")
        sub.pack(anchor="w")

        # Status Pill
        self.status_bar = tk.Frame(main, bg="#e8f5e9", bd=1, relief="solid", padx=10, pady=6)
        self.status_bar.pack(fill="x", pady=(0, 10))

        self.status_dot = tk.Label(self.status_bar, text="●", fg="#d97706", bg="#e8f5e9", font=("Segoe UI", 11))
        self.status_dot.pack(side="left", padx=(0, 6))

        self.status_lbl = tk.Label(self.status_bar, text="Starting tunnel & mobile server...", bg="#e8f5e9", fg="#1b4332", font=("Segoe UI", 9, "bold"))
        self.status_lbl.pack(side="left")

        # QR & Info Container
        mid = tk.Frame(main, bg="#fbfbf9", bd=1, relief="solid", padx=10, pady=10)
        mid.pack(fill="x", pady=(0, 10))

        qr_box = tk.Frame(mid, bg="#ffffff", bd=1, relief="solid", padx=4, pady=4)
        qr_box.pack(side="left", padx=(0, 12))

        self.qr_label = tk.Label(qr_box, bg="#ffffff", text="Generating\nQR...", font=("Segoe UI", 8), width=18, height=8)
        self.qr_label.pack()

        info = tk.Frame(mid, bg="#fbfbf9")
        info.pack(side="left", fill="both", expand=True)

        tk.Label(info, text="Scan with Phone Camera:", font=("Segoe UI", 9, "bold"), bg="#fbfbf9", fg="#1b4332").pack(anchor="w")

        self.url_var = tk.StringVar(value="Waiting for tunnel...")
        self.url_entry = ttk.Entry(info, textvariable=self.url_var, font=("Consolas", 8), state="readonly")
        self.url_entry.pack(fill="x", pady=(2, 4))

        pin_row = tk.Frame(info, bg="#fbfbf9")
        pin_row.pack(fill="x", pady=2)
        tk.Label(pin_row, text="PIN: ", font=("Segoe UI", 9, "bold"), bg="#fbfbf9", fg="#1b4332").pack(side="left")
        self.pin_var = tk.StringVar(value="----")
        self.pin_badge = tk.Label(pin_row, textvariable=self.pin_var, font=("Consolas", 11, "bold"), bg="#1b4332", fg="#ffffff", padx=6, pady=1)
        self.pin_badge.pack(side="left")

        self.local_ip_lbl = tk.Label(info, text="Direct Hotspot: detecting...", font=("Segoe UI", 8), bg="#fbfbf9", fg="#5a655e")
        self.local_ip_lbl.pack(anchor="w", pady=(4, 0))

        # Live Feed
        feed_frame = tk.LabelFrame(main, text="Session Activity Log", bg="#ffffff", font=("Segoe UI", 9, "bold"), fg="#1b4332", padx=6, pady=4)
        feed_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.feed_list = tk.Listbox(feed_frame, bg="#fbfbf9", font=("Segoe UI", 9), bd=0, highlightthickness=1, selectmode="none")
        self.feed_list.pack(fill="both", expand=True, side="left")

        feed_scroll = ttk.Scrollbar(feed_frame, orient="vertical", command=self.feed_list.yview)
        feed_scroll.pack(side="right", fill="y")
        self.feed_list.config(yscrollcommand=feed_scroll.set)

        # Bottom Controls
        bottom = tk.Frame(main, bg="#ffffff")
        bottom.pack(fill="x")

        self.save_btn = ttk.Button(bottom, text="💾 Save Changes & Exit", command=self.save_and_exit)
        self.save_btn.pack(fill="x", ipady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _start_services(self):
        self.server = MobileServer(
            self.app,
            root_tk=self.root,
            port=self.port,
            on_edit_callback=self._on_mobile_edit
        )
        self.server.start()
        self.pin_var.set(self.server.pin)
        local_ip = get_local_ip()
        self.local_ip_lbl.config(text=f"Direct Hotspot: http://{local_ip}:{self.port}")

        self.tunnel = PinggyTunnel(self.port)
        self.tunnel.start(self._on_tunnel_ready)

    def _on_tunnel_ready(self, url):
        def update():
            url_with_token = f"{url}?token={self.server.session_token}"
            self.url_var.set(url_with_token)
            self.status_dot.config(fg="#2e7d32")
            self.status_lbl.config(text="🟢 Online & Secure (Pinggy Port 443)", fg="#1b4332")

            try:
                qr = qrcode.QRCode(box_size=3, border=1)
                qr.add_data(url_with_token)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#1b4332", back_color="white")
                self.qr_image_ref = ImageTk.PhotoImage(img)
                self.qr_label.config(image=self.qr_image_ref, text="")
            except Exception:
                self.qr_label.config(text="Scan URL\nin browser")

            self.feed_list.insert(tk.END, f"Public tunnel live: {url}")
            self.feed_list.see(tk.END)
        self.root.after(0, update)

    def _on_mobile_edit(self, oid, summary):
        def log():
            now = datetime.now().strftime("%H:%M:%S")
            self.feed_list.insert(tk.END, f"[{now}] {summary}")
            self.feed_list.see(tk.END)
        self.root.after(0, log)

    def _schedule_autosave(self):
        # Auto-save every 3 minutes if dirty
        def tick():
            if self.app.dirty:
                try:
                    with self.app.df_lock:
                        # Write pickle or direct excel backup
                        backup_path = self.app.excel_path + ".autosave"
                        SQLiteRepository.export_to_excel(
                            sqlite_path=None,
                            excel_path=backup_path,
                            config=self.app.config,
                            df_reg=self.app.df_reg,
                            df_obs=self.app.df_obs,
                            df_log=self.app.df_log,
                            df_photo=self.app.df_photo
                        )
                        self._on_mobile_edit("SYS", "Background autosave completed")
                except Exception as e:
                    debug_error("MobileHost autosave", str(e))

            self.autosave_job = self.root.after(180000, tick)

        self.autosave_job = self.root.after(180000, tick)

    def save_and_exit(self):
        if self.tunnel:
            self.tunnel.stop()

        try:
            with self.app.df_lock:
                if self.app.excel_path.endswith((".db", ".sqlite", ".sqlite3")):
                    SQLiteRepository.save_sqlite(
                        self.app.excel_path,
                        self.app.df_reg,
                        self.app.df_obs,
                        self.app.df_photo,
                        self.app.df_log
                    )
                else:
                    SQLiteRepository.export_to_excel(
                        sqlite_path=None,
                        excel_path=self.app.excel_path,
                        config=self.app.config,
                        df_reg=self.app.df_reg,
                        df_obs=self.app.df_obs,
                        df_log=self.app.df_log,
                        df_photo=self.app.df_photo
                    )
            messagebox.showinfo("Saved", "All changes have been successfully saved to database.")
        except Exception as e:
            debug_error("MobileHost Save Error", str(e))
            messagebox.showerror("Save Error", f"Failed to save changes: {e}")
            return

        self.root.destroy()
        sys.exit(0)

    def on_close(self):
        if self.app.dirty:
            res = messagebox.askyesnocancel("Unsaved Changes", "Save changes to database before closing?")
            if res is None:
                return
            if res:
                self.save_and_exit()
                return

        if self.tunnel:
            self.tunnel.stop()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()
