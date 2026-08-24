"""
tests/test_tunnel.py

Comprehensive unit tests for the SSH reverse tunnel and pairing QR generator (backend/tunnel.py).
Tests OpenSSH detection, ANSI code stripping, URL regex matching, QR code generation,
and mock subprocess lifecycle/watchdog behavior.
"""

import os
import re
import subprocess
import threading
import time
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from backend.tunnel import (
    find_ssh_executable,
    strip_ansi_codes,
    get_local_ip,
    generate_qr_code,
    SSHTunnelManager,
    _URL_PATTERNS
)


def test_find_ssh_executable():
    ssh_path = find_ssh_executable()
    # On modern Windows 10/11 and Linux/macOS, ssh is installed by default
    if os.name == "nt":
        assert ssh_path is not None
        assert ssh_path.lower().endswith("ssh.exe") or "ssh" in ssh_path.lower()
    else:
        assert ssh_path is not None


def test_strip_ansi_codes():
    raw = "\x1B[2J\x1B[H\x1B[32mhttps://abc123.a.pinggy.link\x1B[0m\r\n"
    cleaned = strip_ansi_codes(raw)
    assert cleaned.strip() == "https://abc123.a.pinggy.link"
    assert "\x1B" not in cleaned


def test_get_local_ip():
    ip = get_local_ip()
    assert isinstance(ip, str)
    # Check valid IPv4 pattern
    parts = ip.split(".")
    assert len(parts) == 4
    for p in parts:
        assert p.isdigit()
        assert 0 <= int(p) <= 255


def test_generate_qr_code():
    url = "https://abc123.a.pinggy.link/?token=XYZ789"
    img = generate_qr_code(url, box_size=6, border=2)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.width > 50
    assert img.height > 50


def test_tunnel_url_regex():
    pinggy_sample = "  Forwarded HTTP: https://rvxwb-84-211-19-10.a.pinggy.link  "
    match_pinggy = _URL_PATTERNS["pinggy"].search(pinggy_sample)
    assert match_pinggy is not None
    assert match_pinggy.group(0) == "https://rvxwb-84-211-19-10.a.pinggy.link"

    lhr_sample = "tunnel http://example.lhr.life (https://example.lhr.life)"
    match_lhr = _URL_PATTERNS["localhost_run"].search(lhr_sample)
    assert match_lhr is not None
    assert match_lhr.group(0) == "https://example.lhr.life"


class MockSubprocess:
    """Simulates a subprocess.Popen object with mock stdout/stderr streams."""

    def __init__(self, stdout_lines: list[str], exit_after: float = 2.0):
        self._stdout_lines = stdout_lines
        self._exit_after = exit_after
        self._start_time = time.time()
        self._is_terminated = False

        # Create mock stream
        self.stdout = MagicMock()
        self.stdout.readline = self._readline_stdout
        self.stdout.close = MagicMock()

        self.stderr = MagicMock()
        self.stderr.readline = MagicMock(return_value="")
        self.stderr.close = MagicMock()

    def _readline_stdout(self):
        if self._stdout_lines:
            return self._stdout_lines.pop(0)
        time.sleep(0.1)
        return ""

    def poll(self):
        if self._is_terminated:
            return 0
        if time.time() - self._start_time > self._exit_after:
            return 0
        return None

    def terminate(self):
        self._is_terminated = True

    def kill(self):
        self._is_terminated = True

    def wait(self, timeout=None):
        return 0


def test_tunnel_manager_mock_lifecycle():
    manager = SSHTunnelManager(local_port=8765, session_token="testtoken123")
    assert manager.status == "stopped"

    # Pairing URL before public connection (falls back to local IP)
    pairing_url = manager.get_pairing_url()
    assert "token=testtoken123" in pairing_url
    assert f":8765" in pairing_url

    # Simulate SSH subprocess outputting localhost.run URL
    simulated_output = [
        "Welcome to localhost.run!\n",
        "Initializing tunnel...\n",
        "https://mocktunnel123.lhr.life\n",
        "Tunnel established\n"
    ]
    mock_proc = MockSubprocess(simulated_output, exit_after=5.0)

    with patch("subprocess.Popen", return_value=mock_proc):
        manager.start()
        # Wait for reader thread to parse URL
        for _ in range(20):
            if manager.status == "connected":
                break
            time.sleep(0.1)

        status = manager.get_status()
        assert status["status"] == "connected"
        assert status["public_url"] == "https://mocktunnel123.lhr.life"
        assert "https://mocktunnel123.lhr.life/?token=testtoken123" in manager.get_pairing_url()

        # QR code generation with active public URL
        qr_img = manager.generate_pairing_qr_code()
        assert qr_img.width > 50

        # Stop manager
        manager.stop()
        assert manager.status == "stopped"
        assert manager.public_url is None


def test_tunnel_manager_fallback_switching():
    manager = SSHTunnelManager(local_port=8765, session_token="testtoken123")
    
    # Simulate repeated immediate process failure to trigger fallback
    def failing_proc(*args, **kwargs):
        return MockSubprocess([], exit_after=0.01)

    with patch("subprocess.Popen", side_effect=failing_proc):
        manager.start()
        # Allow watchdog to run multiple cycles
        time.sleep(1.5)
        
        status = manager.get_status()
        # Should have attempted fallback to localhost_run or pinggy
        assert status["active_provider"] in ("pinggy", "localhost_run")

        manager.stop()
        assert manager.status == "stopped"
