import subprocess
import threading
import re
import socket
import logging

class PinggyTunnel:
    def __init__(self, port):
        self.port = port
        self.public_url = None
        self.process = None
        self.thread = None
        self._stop_event = threading.Event()

    def start(self, callback):
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run, args=(callback,), daemon=True)
        self.thread.start()

    def _run(self, callback):
        # We use a.pinggy.io on port 443 to bypass university firewall restrictions
        cmd = [
            'ssh', '-p', '443',
            f'-R0:localhost:{self.port}',
            'a.pinggy.io',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ServerAliveInterval=30'
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Robust URL matching pattern for pinggy domains
            url_pattern = re.compile(r'(https://[a-zA-Z0-9.-]+\.pinggy\.[a-z]+)')

            for line in self.process.stdout:
                if self._stop_event.is_set():
                    break

                match = url_pattern.search(line)
                if match and not self.public_url:
                    self.public_url = match.group(1)
                    if callback:
                        callback(self.public_url)

            self.process.wait()
        except Exception as e:
            logging.error(f"Tunnel error: {e}")
        finally:
            self.public_url = None

    def stop(self):
        self._stop_event.set()
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip
