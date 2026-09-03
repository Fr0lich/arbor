import subprocess
import threading
import re
import socket
import logging
import sys
import time

import os
import urllib.request
import platform
import stat


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


_ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


class ResilientSSHTunnel:
    """Resilient SSH reverse tunnel.

    Primary provider: Serveo (serveo.net, port 22), which delivers public HTTPS
    URLs in ~1.5s without registration, accounts, or auth requirements.
    Fallback providers (Pinggy, Localhost.run) are tried if Serveo is unreachable.
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
                re.compile(r'(https://[a-zA-Z0-9.-]+?\.(?:free\.pinggy\.net|run\.pinggy-free\.link|a\.pinggy\.link|pinggy\.link))')
            ),
            (
                'nokey@localhost.run',
                '22',
                f'80:127.0.0.1:{self.port}',
                re.compile(r'(https://[a-zA-Z0-9-]+\.lhr\.(?:life|rocks))')
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

                if status_callback and attempt > 0:
                    status_callback(f"🔄 Connecting via {target_host.split('@')[-1]}...")

                cmd = [
                    'ssh',
                    '-T',
                    '-p', target_port,
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', f'UserKnownHostsFile={known_hosts_null}',
                    '-o', 'LogLevel=ERROR',
                    '-o', 'ServerAliveInterval=15',
                    '-o', 'ServerAliveCountMax=3',
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
                        if self.process.poll() is not None:
                            break

                        line = self.process.stdout.readline()
                        if not line:
                            if self.process.poll() is not None:
                                break
                            if not connected and time.time() > url_deadline:
                                logging.warning(f"Tunnel {target_host}: no URL received within 12s")
                                if status_callback and attempt >= len(providers):
                                    status_callback("🟡 Tunnel timeout — trying next provider...")
                                try:
                                    self.process.terminate()
                                    self.process.wait(timeout=1.0)
                                except Exception:
                                    try:
                                        self.process.kill()
                                    except Exception:
                                        pass
                                break
                            time.sleep(0.05)
                            continue

                        clean_line = _ANSI_ESCAPE_RE.sub('', line).strip()
                        if not clean_line:
                            continue

                        # Explicitly skip promo links
                        if "dashboard.pinggy.io" in clean_line or "admin.localhost.run" in clean_line or "admin.pinggy.io" in clean_line:
                            continue

                        match = url_pattern.search(clean_line)
                        if match and not connected:
                            url = match.group(1).rstrip('/')
                            self.public_url = url
                            connected = True
                            attempt = 0
                            backoff = 2
                            if url_callback:
                                url_callback(self.public_url)

                        if not connected and time.time() > url_deadline:
                            logging.warning(f"Tunnel {target_host}: no URL received within 12s")
                            if status_callback and attempt >= len(providers):
                                status_callback("🟡 Tunnel timeout — trying next provider...")
                            try:
                                self.process.terminate()
                                self.process.wait(timeout=1.0)
                            except Exception:
                                try:
                                    self.process.kill()
                                except Exception:
                                    pass
                            break

                    if self.process and not self._stop_event.is_set():
                        try:
                            self.process.wait(timeout=0.5)
                        except Exception:
                            pass

                    if self._stop_event.is_set():
                        break


                except Exception as e:
                    logging.error(f"Tunnel error with {target_host}: {e}")

                finally:
                    if self.process and self._stop_event.is_set():
                        try:
                            self.process.terminate()
                            self.process.wait(timeout=1.0)
                        except Exception:
                            try:
                                self.process.kill()
                            except Exception:
                                pass
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


def ensure_cloudflared():
    """Ensure the cloudflared binary exists locally, downloading it if necessary."""
    try:
        cf_dir = os.path.expanduser('~/.cloudflared')
        os.makedirs(cf_dir, exist_ok=True)

        is_windows = sys.platform.startswith('win')
        binary_name = 'cloudflared.exe' if is_windows else 'cloudflared'
        binary_path = os.path.join(cf_dir, binary_name)

        if not os.path.exists(binary_path):
            system = platform.system().lower()
            machine = platform.machine().lower()

            # Map architecture
            if machine in ['x86_64', 'amd64']:
                arch = 'amd64'
            elif machine in ['arm64', 'aarch64']:
                arch = 'arm64'
            elif machine in ['i386', 'x86']:
                arch = '386'
            elif machine in ['arm']:
                arch = 'arm'
            else:
                arch = 'amd64' # fallback

            # Map OS and build URL
            base_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/"
            if system == 'windows':
                url = f"{base_url}cloudflared-windows-{arch}.exe"
            elif system == 'darwin':
                url = f"{base_url}cloudflared-darwin-{arch}" # macOS uses a single binary or tgz depending on version, let's try direct binary
            else: # linux
                url = f"{base_url}cloudflared-linux-{arch}"

            logging.info(f"Downloading cloudflared from {url}...")
            urllib.request.urlretrieve(url, binary_path)

            # Make executable
            if not is_windows:
                st = os.stat(binary_path)
                os.chmod(binary_path, st.st_mode | stat.S_IEXEC)

        return binary_path
    except Exception as e:
        logging.error(f"Failed to ensure cloudflared: {e}")
        return None

class CloudflareTunnel:
    """Cloudflare Quick Tunnels (trycloudflare.com)."""

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
        binary_path = ensure_cloudflared()
        if not binary_path:
            if status_callback:
                status_callback("🔴 Failed to download cloudflared")
            return

        cmd = [binary_path, 'tunnel', '--url', f'http://127.0.0.1:{self.port}']
        flags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0

        if status_callback:
            status_callback("🔄 Starting Cloudflare tunnel...")

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=flags
            )

            url_pattern = re.compile(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)')
            connected = False
            url_deadline = time.time() + 15  # 15s deadline for tunnel handshake

            while not self._stop_event.is_set():
                if self.process.poll() is not None:
                    break

                line = self.process.stderr.readline()
                if not line:
                    if not connected and time.time() > url_deadline:
                        logging.warning("Cloudflare tunnel: no URL received within 15s")
                        if status_callback:
                            status_callback("🟡 Cloudflare tunnel timeout")
                        break
                    time.sleep(0.05)
                    continue

                clean_line = _ANSI_ESCAPE_RE.sub('', line).strip()
                match = url_pattern.search(clean_line)
                if match and not connected:
                    url = match.group(1)
                    self.public_url = url
                    connected = True
                    if url_callback:
                        url_callback(url)

                if not connected and time.time() > url_deadline:
                    logging.warning("Cloudflare tunnel: no URL received within 15s")
                    if status_callback:
                        status_callback("🟡 Cloudflare tunnel timeout")
                    break

            if self._stop_event.is_set() and self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=1.0)
                except Exception:
                    pass

        except Exception as e:
            logging.error(f"Cloudflare tunnel error: {e}")
            if status_callback:
                status_callback(f"🔴 Tunnel error: {e}")
        finally:
            self.stop()

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
        self.public_url = None


# Backwards-compatible aliases — callers import without changes
LocalhostRunTunnel = ResilientSSHTunnel
PinggyTunnel = ResilientSSHTunnel


def get_local_ip():
    """Discover the most suitable local LAN / Wi-Fi IP address for the mobile companion."""
    # 1. Direct UDP gateway probe using public/local DNS targets
    for target in [('8.8.8.8', 80), ('1.1.1.1', 80), ('10.255.255.255', 1)]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(target)
            ip = s.getsockname()[0]
            s.close()
            # Ignore loopback, VirtualBox host-only, and APIPA autoconfig addresses
            if ip and not ip.startswith('127.') and not ip.startswith('192.168.56.') and not ip.startswith('169.254.'):
                return ip
        except Exception:
            pass

    # 2. Enumerate host IP list prioritizing physical private LAN / Wi-Fi ranges
    try:
        host_ips = socket.gethostbyname_ex(socket.gethostname())[2]

        # Priority 2a: Standard home/office Wi-Fi (192.168.x.x excluding VirtualBox 192.168.56.x)
        for ip in host_ips:
            if ip.startswith('192.168.') and not ip.startswith('192.168.56.') and not ip.startswith('127.'):
                return ip

        # Priority 2b: Standard 10.x private LAN
        for ip in host_ips:
            if ip.startswith('10.') and not ip.startswith('127.'):
                return ip

        # Priority 2c: 172.16 - 172.31 private LAN (deprioritizing default Docker bridge 172.17.x.x)
        for ip in host_ips:
            if ip.startswith('172.') and not ip.startswith('172.17.') and not ip.startswith('127.'):
                return ip

        for ip in host_ips:
            if ip.startswith('172.') and not ip.startswith('127.'):
                return ip

        # Priority 2d: Any remaining 192.168.x.x (including host-only if nothing else)
        for ip in host_ips:
            if ip.startswith('192.168.') and not ip.startswith('127.'):
                return ip

        # Priority 2e: Any non-loopback, non-APIPA IP
        for ip in host_ips:
            if not ip.startswith('127.') and not ip.startswith('169.254.'):
                return ip
    except Exception:
        pass

    return '127.0.0.1'
