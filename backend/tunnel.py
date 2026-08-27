import subprocess
import threading
import re
import socket
import logging
import sys
import time

import os


def ensure_ssh_key():
    """Ensure an SSH key exists in ~/.ssh, generating one automatically if missing.

    Reverse tunnel services (Serveo, Pinggy, etc.) require an SSH client key pair
    for cryptographic session negotiation.
    """
    try:
        ssh_dir = os.path.expanduser('~/.ssh')
        os.makedirs(ssh_dir, exist_ok=True)
        key_path = os.path.join(ssh_dir, 'id_ed25519')
        rsa_path = os.path.join(ssh_dir, 'id_rsa')
        if not os.path.exists(key_path) and not os.path.exists(rsa_path):
            flags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
            subprocess.run(
                ['ssh-keygen', '-t', 'ed25519', '-N', '', '-f', key_path, '-q'],
                capture_output=True,
                creationflags=flags,
                timeout=5
            )
        return key_path if os.path.exists(key_path) else rsa_path
    except Exception as e:
        logging.warning(f"Could not auto-generate SSH key: {e}")
        return None


class ResilientSSHTunnel:
    """Resilient SSH reverse tunnel.

    Primary provider: Serveo (serveo.net, port 22), which delivers public HTTPS
    URLs in ~1.5s without registration, accounts, or auth requirements.
    Fallback providers are tried if Serveo is unreachable.
    """

    def __init__(self, port):
        self.port = port
        self.public_url = None
        self.process = None
        self.thread = None
        self._stop_event = threading.Event()

    def start(self, url_callback, status_callback=None):
        self._stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            args=(url_callback, status_callback),
            daemon=True
        )
        self.thread.start()

    def _run(self, url_callback, status_callback):
        ensure_ssh_key()

        # Multi-provider configurations in priority order:
        # (host, port, remote_forward, pattern)
        providers = [
            (
                'serveo.net',
                '22',
                f'80:127.0.0.1:{self.port}',
                re.compile(r'(https://[a-zA-Z0-9.-]+\.(?:serveousercontent\.com|serveo\.net))')
            ),
            (
                'a.pinggy.io',
                '443',
                f'0:127.0.0.1:{self.port}',
                re.compile(r'(https://[a-zA-Z0-9.-]+\.(?:pinggy\.io|pinggy\.net|pinggy-free\.link|pinggy\.link))')
            ),
            (
                'nokey@localhost.run',
                '22',
                f'80:127.0.0.1:{self.port}',
                re.compile(r'(https://[a-zA-Z0-9]+\.lhr\.life)')
            )
        ]

        flags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
        known_hosts_null = 'NUL' if sys.platform.startswith('win') else '/dev/null'

        attempt = 0
        backoff = 2

        try:
            while not self._stop_event.is_set():
                provider_idx = attempt % len(providers)
                target_host, target_port, forward_rule, url_pattern = providers[provider_idx]

                cmd = [
                    'ssh',
                    '-p', target_port,
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', f'UserKnownHostsFile={known_hosts_null}',
                    '-o', 'ServerAliveInterval=30',
                    '-o', 'ConnectTimeout=10',
                    '-R', forward_rule,
                    target_host
                ]

                try:
                    self.process = subprocess.Popen(
                        cmd,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        bufsize=1,
                        creationflags=flags
                    )

                    connected = False
                    url_deadline = time.time() + 12  # 12s per provider attempt

                    while not self._stop_event.is_set():
                        line = self.process.stdout.readline()
                        if not line:
                            if self.process.poll() is not None:
                                break
                            if not connected and time.time() > url_deadline:
                                logging.warning(f"Tunnel {target_host}: no URL received within 12s")
                                if status_callback and attempt >= len(providers):
                                    status_callback("🟡 Tunnel timeout — check network / firewall")
                                self.process.terminate()
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

                        if not connected and time.time() > url_deadline:
                            logging.warning(f"Tunnel {target_host}: no URL received within 12s")
                            if status_callback and attempt >= len(providers):
                                status_callback("🟡 Tunnel timeout — check network / firewall")
                            self.process.terminate()
                            break

                    if self.process and not self._stop_event.is_set():
                        self.process.wait()

                    if self._stop_event.is_set():
                        break

                except Exception as e:
                    logging.error(f"Tunnel error with {target_host}: {e}")

                finally:
                    self.public_url = None

                if self._stop_event.is_set():
                    break

                attempt += 1
                if attempt >= len(providers) * 2:
                    if status_callback:
                        status_callback("🟡 Tunnel disconnected (Local Wi-Fi still active)")
                    break

                self._stop_event.wait(timeout=backoff)
                backoff = min(backoff * 1.5, 15)

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


# Backwards-compatible aliases — callers import without changes
LocalhostRunTunnel = ResilientSSHTunnel
PinggyTunnel = ResilientSSHTunnel


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
