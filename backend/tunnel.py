"""
backend/tunnel.py

Zero-install Reverse SSH Tunneling and QR Code Pairing Subsystem for Arbor.
Uses the system's built-in OpenSSH client (ssh.exe on Windows) to establish
reverse port forwarding to public relays (pinggy.io / localhost.run) without
requiring administrative privileges or external tunnel binaries.
"""

from __future__ import annotations

import atexit
import collections
import io
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from typing import Callable, Any

import qrcode
from PIL import Image

_ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

_URL_PATTERNS = {
    "localhost_run": re.compile(r"https://[a-zA-Z0-9-]+\.lhr\.(?:life|rocks)", re.IGNORECASE),
    "serveo": re.compile(r"https?://[a-zA-Z0-9-]+\.serveo\.net", re.IGNORECASE),
    "pinggy": re.compile(r"https://[a-zA-Z0-9.-]+\.(?:a\.)?pinggy\.(?:link|online)", re.IGNORECASE)
}


def find_ssh_executable() -> str | None:
    """Discovers the OpenSSH client binary across PATH and standard Windows locations."""
    # 1. Check standard PATH
    path_ssh = shutil.which("ssh")
    if path_ssh:
        return path_ssh
    # 2. Check standard Windows System32 OpenSSH directory
    if os.name == "nt":
        sys_root = os.environ.get("SystemRoot", r"C:\Windows")
        sys32_ssh = os.path.join(sys_root, "System32", "OpenSSH", "ssh.exe")
        if os.path.isfile(sys32_ssh):
            return sys32_ssh
    return None


def get_subprocess_creation_flags() -> dict:
    """Ensures subprocess spawns silently on Windows without opening a command prompt window."""
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = startupinfo
    return kwargs


def strip_ansi_codes(text: str) -> str:
    """Strips terminal color codes and cursor movements from command output."""
    if not text:
        return ""
    return _ANSI_ESCAPE_PATTERN.sub('', text)


def get_local_ip() -> str:
    """Determines the active LAN IPv4 address without transmitting external network traffic."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def generate_qr_code(url: str, box_size: int = 8, border: int = 2) -> Image.Image:
    """Generates a high-contrast PIL image of the QR code using Arbor's botanical theme."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    # Slate ink (#2c302e) on warm paper (#fbfaf8)
    return qr.make_image(fill_color="#2c302e", back_color="#fbfaf8").convert("RGB")


class SSHTunnelManager:
    """Manages the zero-install reverse SSH tunnel lifecycle with auto-reconnect and fallback."""

    PROVIDERS = {
        "localhost_run": {
            "name": "Localhost.run (HTTPS, No Login)",
            "args": lambda port: [
                "-R", f"80:localhost:{port}",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "BatchMode=yes",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "ExitOnForwardFailure=yes",
                "nokey@localhost.run"
            ],
            "pattern": _URL_PATTERNS["localhost_run"]
        },
        "serveo": {
            "name": "Serveo (HTTPS, No Login)",
            "args": lambda port: [
                "-R", f"80:localhost:{port}",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "BatchMode=yes",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "ExitOnForwardFailure=yes",
                "serveo.net"
            ],
            "pattern": _URL_PATTERNS["serveo"]
        },
        "pinggy": {
            "name": "Pinggy Relay",
            "args": lambda port: [
                "-p", "443",
                f"-R0:localhost:{port}",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "BatchMode=yes",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "ExitOnForwardFailure=yes",
                "a.pinggy.io"
            ],
            "pattern": _URL_PATTERNS["pinggy"]
        }
    }

    def __init__(self, local_port: int, session_token: str = ""):
        self.local_port = local_port
        self.session_token = session_token
        self.ssh_path = find_ssh_executable()
        self.process: subprocess.Popen | None = None
        self.public_url: str | None = None
        self.local_ip: str = get_local_ip()
        self.status: str = "stopped"  # stopped, starting, connected, reconnecting, failed
        self.active_provider: str = "localhost_run"
        self.recent_logs: collections.deque[str] = collections.deque(maxlen=50)
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._watchdog_thread: threading.Thread | None = None
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._on_status_change_callback: Callable[[dict], None] | None = None

        # Register cleanup at Python process exit
        atexit.register(self.stop)

    def set_status_callback(self, callback: Callable[[dict], None]) -> None:
        """Sets a callback to be notified on tunnel status/URL changes."""
        self._on_status_change_callback = callback

    def _notify_status(self) -> None:
        """Dispatches status updates to the registered callback safely."""
        if self._on_status_change_callback:
            try:
                self._on_status_change_callback(self.get_status())
            except Exception:
                pass

    def get_pairing_url(self) -> str:
        """Returns the active pairing URL with session token (Public URL if connected, LAN IP fallback)."""
        base = self.public_url or f"http://{self.local_ip}:{self.local_port}"
        if not base.endswith("/"):
            base = f"{base}/"
        if self.session_token:
            return f"{base}?token={self.session_token}"
        return base

    def generate_pairing_qr_code(self, box_size: int = 8) -> Image.Image:
        """Generates an Arbor-styled QR code image for the active pairing URL."""
        return generate_qr_code(self.get_pairing_url(), box_size=box_size)

    def _drain_stream(self, stream, is_stderr: bool = False) -> None:
        """Continuously drains a process output stream line by line to prevent buffer deadlock."""
        provider_info = self.PROVIDERS.get(self.active_provider, self.PROVIDERS["pinggy"])
        url_pattern = provider_info["pattern"]

        try:
            for raw_line in iter(stream.readline, ''):
                if self._stop_event.is_set():
                    break
                line = strip_ansi_codes(raw_line.strip())
                if line:
                    prefix = "[stderr] " if is_stderr else ""
                    self.recent_logs.append(f"{prefix}{line}")

                    # Scan for public HTTPS URL if not yet captured
                    if not self.public_url:
                        match = url_pattern.search(line)
                        if match:
                            candidate_url = match.group(0).rstrip('/')
                            # Exclude informational URLs from banner
                            if not any(x in candidate_url.lower() for x in ["admin.", "docs", "dashboard", "github."]):
                                with self._lock:
                                    self.public_url = candidate_url
                                    self.status = "connected"
                                self._notify_status()
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _run_tunnel_process(self) -> None:
        """Spawns the SSH process and starts stream reading threads."""
        if not self.ssh_path:
            with self._lock:
                self.status = "failed"
                self.recent_logs.append("OpenSSH client (ssh.exe) not found on system. Running in Local LAN mode.")
            self._notify_status()
            return

        provider_info = self.PROVIDERS.get(self.active_provider, self.PROVIDERS["pinggy"])
        cmd = [self.ssh_path] + provider_info["args"](self.local_port)
        creation_kwargs = get_subprocess_creation_flags()

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                **creation_kwargs
            )

            # Start background reader threads
            self._stdout_thread = threading.Thread(
                target=self._drain_stream,
                args=(self.process.stdout, False),
                daemon=True,
                name="SSHTunnelStdoutReader"
            )
            self._stderr_thread = threading.Thread(
                target=self._drain_stream,
                args=(self.process.stderr, True),
                daemon=True,
                name="SSHTunnelStderrReader"
            )
            self._stdout_thread.start()
            self._stderr_thread.start()

        except Exception as e:
            with self._lock:
                self.status = "failed"
                self.recent_logs.append(f"Failed to spawn SSH process: {e}")
            self._notify_status()

    def _terminate_process(self) -> None:
        """Safely terminates the active SSH subprocess with timeout and fallback kill."""
        proc = self.process
        self.process = None
        if proc:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1.0)
            except Exception:
                pass

    def _watchdog_loop(self) -> None:
        """Monitors the tunnel process and automatically attempts reconnects with fallback."""
        consecutive_failures = 0

        while not self._stop_event.is_set():
            with self._lock:
                self.status = "starting" if consecutive_failures == 0 else "reconnecting"
                self.public_url = None
            self._notify_status()

            self._run_tunnel_process()

            if not self.process:
                # Spawn failed (e.g. no SSH executable)
                break

            # Wait for process exit or stop signal
            while not self._stop_event.is_set():
                if self.process.poll() is not None:
                    # Subprocess terminated prematurely
                    break
                time.sleep(0.5)

            if self._stop_event.is_set():
                break

            # Process died unexpectedly
            consecutive_failures += 1
            with self._lock:
                self.status = "reconnecting"
                self.public_url = None
            self._terminate_process()

            # Switch provider fallback if primary fails repeatedly
            if consecutive_failures >= 2 and self.active_provider == "pinggy":
                self.active_provider = "localhost_run"
                self.recent_logs.append("Switching tunnel provider fallback to localhost.run")
            elif consecutive_failures >= 4 and self.active_provider == "localhost_run":
                self.active_provider = "pinggy"

            self._notify_status()

            # Backoff before reconnecting
            backoff = min(2 * consecutive_failures, 10)
            for _ in range(backoff * 2):
                if self._stop_event.is_set():
                    break
                time.sleep(0.5)

        # Cleanup on loop exit
        self._terminate_process()
        with self._lock:
            self.status = "stopped"
            self.public_url = None
        self._notify_status()

    def start(self) -> None:
        """Starts the tunnel manager watchdog in a background thread."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return

        self._stop_event.clear()
        if not self.active_provider:
            self.active_provider = "localhost_run"
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="SSHTunnelWatchdog"
        )
        self._watchdog_thread.start()

    def stop(self) -> None:
        """Stops the tunnel manager and cleanly terminates the SSH subprocess."""
        self._stop_event.set()
        self._terminate_process()
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=2.0)
            self._watchdog_thread = None
        with self._lock:
            self.status = "stopped"
            self.public_url = None

    def get_pairing_url(self, prefer: str = "relay") -> str:
        """Constructs the canonical pairing URL with trailing slash and session token."""
        token_suffix = f"?token={self.session_token}" if self.session_token else ""
        if prefer == "local":
            return f"http://{self.local_ip}:{self.local_port}/{token_suffix}"
        if self.public_url:
            base = self.public_url.rstrip("/")
            return f"{base}/{token_suffix}"
        return f"http://{self.local_ip}:{self.local_port}/{token_suffix}"

    def generate_pairing_qr_code(self, box_size: int = 8, border: int = 2, prefer: str = "relay") -> Image.Image:
        """Generates a high-contrast PIL image of the QR code for pairing."""
        url = self.get_pairing_url(prefer=prefer)
        return generate_qr_code(url, box_size=box_size, border=border)

    def get_status(self) -> dict:
        """Returns the current tunnel status dictionary."""
        with self._lock:
            return {
                "status": self.status,
                "is_connected": self.status == "connected",
                "public_url": self.public_url,
                "pairing_url": self.get_pairing_url(),
                "local_ip": self.local_ip,
                "local_port": self.local_port,
                "active_provider": self.active_provider,
                "provider_name": self.PROVIDERS.get(self.active_provider, {}).get("name", "Unknown"),
                "ssh_available": bool(self.ssh_path),
                "recent_logs": list(self.recent_logs)[-10:]
            }
