import subprocess
import threading
import re
import socket
import logging
import sys
import time

class PinggyTunnel:
    def __init__(self, port):
        self.port = port
        self.public_url = None
        self.process = None
        self.thread = None
        self._stop_event = threading.Event()

    def start(self, url_callback, status_callback=None):
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run, args=(url_callback, status_callback), daemon=True)
        self.thread.start()

    def _run(self, url_callback, status_callback):
        # We use a.pinggy.io on port 443 with -T (disable pseudo-terminal) for clean non-blocking IO
        cmd = [
            'ssh',
            '-p', '443',
            '-T',
            f'-R0:localhost:{self.port}',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=NUL' if sys.platform.startswith('win') else '/dev/null',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ConnectTimeout=10',
            'a.pinggy.io'
        ]

        flags = 0
        if sys.platform.startswith('win'):
            # CREATE_NO_WINDOW prevents console allocation hangs on Windows
            flags = subprocess.CREATE_NO_WINDOW

        attempt = 0
        backoff = 2

        try:
            while not self._stop_event.is_set():
                try:
                    self.process = subprocess.Popen(
                        cmd,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        creationflags=flags
                    )

                    # Robust URL matching pattern
                    url_pattern = re.compile(r'(https://[a-zA-Z0-9.-]+\.pinggy\.[a-z]+)')
                    connected = False

                    # Read with non-blocking check
                    while not self._stop_event.is_set():
                        line = self.process.stdout.readline()
                        if not line:
                            if self.process.poll() is not None:
                                break
                            time.sleep(0.1)
                            continue

                        match = url_pattern.search(line)
                        if match and not connected:
                            self.public_url = match.group(1)
                            connected = True
                            attempt = 0
                            backoff = 2
                            if url_callback:
                                url_callback(self.public_url)

                    if self.process and not self._stop_event.is_set():
                        self.process.wait()

                    if self._stop_event.is_set():
                        break

                except Exception as e:
                    logging.error(f"Tunnel error: {e}")

                finally:
                    self.public_url = None

                if self._stop_event.is_set():
                    break

                attempt += 1
                if attempt > 3:
                    if status_callback:
                        status_callback("🟡 Tunnel disconnected (Local Wi-Fi still active)")
                    break

                self._stop_event.wait(timeout=backoff)
                backoff = min(backoff * 2, 30)

        finally:
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=1.0)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None

    def stop(self):
        self._stop_event.set()
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None


def get_local_ip():
    # 1. Direct UDP gateway probe
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass

    # 2. Enumerate host IP list prioritizing private LAN / Wi-Fi ranges
    try:
        host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        for ip in host_ips:
            if ip.startswith(('192.168.', '172.', '10.')) and not ip.startswith('127.'):
                return ip
        for ip in host_ips:
            if not ip.startswith('127.'):
                return ip
    except Exception:
        pass

    return '127.0.0.1'
