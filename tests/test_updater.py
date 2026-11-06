import os
import sys
import json
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from packaging.version import parse as parse_version

import config
from backend.updater import (
    check_for_updates,
    validate_pe_executable,
    is_install_dir_writable,
    get_staging_dir,
    save_session_state,
    load_session_state,
    clear_session_state,
    cleanup_old_binaries,
    get_session_restore_path,
    download_update_staged
)


def create_dummy_pe_bytes():
    """Construct minimal valid DOS + PE header structure (>= 1024 bytes)."""
    header = bytearray(b"MZ" + b"\x00" * 58)
    pe_offset = 128
    header.extend(pe_offset.to_bytes(4, byteorder="little"))
    header.extend(b"\x00" * (pe_offset - len(header)))
    header.extend(b"PE\x00\x00")
    if len(header) < 1024:
        header.extend(b"\x00" * (1024 - len(header)))
    return bytes(header)


class TestUpdater:

    def test_version_comparison_logic(self):
        """Test semantic version parsing and ordering."""
        v_current = parse_version("2.1.0")
        v_newer = parse_version("v2.2.0".lstrip("v"))
        v_same = parse_version("2.1.0")
        v_patch = parse_version("2.1.1")
        v_older = parse_version("2.0.9")

        assert v_newer > v_current
        assert v_patch > v_current
        assert v_same == v_current
        assert v_older < v_current

    def test_pe_validation_success_and_failure(self, tmp_path):
        """Test PE header validation on valid dummy bytes and invalid files."""
        # 1. Non-existent file
        assert validate_pe_executable(str(tmp_path / "non_existent.exe")) is False

        # 2. Too short / empty file
        short_file = tmp_path / "short.exe"
        short_file.write_bytes(b"MZ" + b"\x00" * 10)
        assert validate_pe_executable(str(short_file)) is False

        # 3. Non-MZ header
        invalid_magic = tmp_path / "invalid_magic.exe"
        invalid_magic.write_bytes(b"XX" + b"\x00" * 1024)
        assert validate_pe_executable(str(invalid_magic)) is False

        # 4. Valid DOS + PE header
        valid_pe = tmp_path / "valid.exe"
        valid_pe.write_bytes(create_dummy_pe_bytes())
        assert validate_pe_executable(str(valid_pe)) is True

    def test_check_for_updates_newer_release(self):
        """Mock GitHub API returning a newer release."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.history = []
        mock_response.url = "https://api.github.com/repos/Fr0lich/arbor/releases/latest"
        mock_response.json.return_value = {
            "tag_name": "v2.2.0",
            "body": "### Changes\n- 1-click update added\n- Bug fixes",
            "assets": [
                {
                    "name": "arbor.exe",
                    "browser_download_url": "https://github.com/Fr0lich/arbor/releases/download/v2.2.0/arbor.exe",
                    "size": 52428800
                }
            ]
        }

        with patch("requests.get", return_value=mock_response):
            with patch("config.APP_VERSION", "2.1.0"):
                res = check_for_updates("Fr0lich/arbor")
                assert res["status"] == "ok"
                assert res["has_update"] is True
                assert res["latest_version"] == "2.2.0"
                assert res["current_version"] == "2.1.0"
                assert res["asset_name"] == "arbor.exe"
                assert res["asset_size"] == 52428800
                assert "1-click update added" in res["release_notes"]

    def test_check_for_updates_already_current(self):
        """Mock GitHub API returning current or older version."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.history = []
        mock_response.url = "https://api.github.com/repos/Fr0lich/arbor/releases/latest"
        mock_response.json.return_value = {
            "tag_name": "v2.1.0",
            "body": "Release 2.1.0 notes",
            "assets": [
                {
                    "name": "arbor.exe",
                    "browser_download_url": "https://github.com/Fr0lich/arbor/releases/download/v2.1.0/arbor.exe",
                    "size": 50000000
                }
            ]
        }

        with patch("requests.get", return_value=mock_response):
            with patch("config.APP_VERSION", "2.1.0"):
                res = check_for_updates("Fr0lich/arbor")
                assert res["status"] == "ok"
                assert res["has_update"] is False
                assert res["latest_version"] == "2.1.0"
                assert res["current_version"] == "2.1.0"

    def test_check_for_updates_repo_redirect_detected(self):
        """GitHub repository rename / move returns HTTP 301/307 redirects."""
        mock_redir = MagicMock()
        mock_redir.status_code = 301

        mock_final = MagicMock()
        mock_final.status_code = 200
        mock_final.history = [mock_redir]
        mock_final.url = "https://api.github.com/repos/ArborOrg/arbor-curation/releases/latest"
        mock_final.json.return_value = {
            "tag_name": "v3.0.0",
            "body": "Migrated repo",
            "assets": [{"name": "arbor.exe", "browser_download_url": "http://example.com/arbor.exe", "size": 100}]
        }

        with patch("requests.get", return_value=mock_final):
            with patch("config.set_update_repo") as mock_set_repo:
                res = check_for_updates("Fr0lich/arbor")
                assert res["status"] == "ok"
                assert res["has_update"] is True
                assert res["repo"] == "ArborOrg/arbor-curation"
                mock_set_repo.assert_called_with("ArborOrg/arbor-curation")

    def test_check_for_updates_unreachable_404(self):
        """Mock 404 Not Found when repo was deleted or renamed without redirect."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("requests.get", return_value=mock_response):
            res = check_for_updates("Unknown/broken-repo")
            assert res["status"] == "404_not_found"
            assert "not found" in res["message"].lower()

    def test_session_state_lifecycle(self, tmp_path):
        """Test save_session_state, load_session_state, and clear_session_state."""
        session_file = tmp_path / "session_restore.json"

        with patch("backend.updater.get_session_restore_path", return_value=str(session_file)):
            app = MagicMock()
            app.root = MagicMock()
            app.root.winfo_exists.return_value = True
            app.excel_path = "C:/test/collection.xlsx"
            app.last_object_id = "SPEC-4091"
            app.config_name = "Standard Herbarium"
            app.image_mode = "folder"
            app.image_folder = "C:/test/images"

            # 1. Save
            saved = save_session_state(app)
            assert saved is True
            assert session_file.exists()

            # 2. Load
            loaded = load_session_state()
            assert loaded is not None
            assert loaded["excel_path"] == "C:/test/collection.xlsx"
            assert loaded["active_object_id"] == "SPEC-4091"
            assert loaded["config_name"] == "Standard Herbarium"
            assert loaded["image_mode"] == "folder"
            assert loaded["image_folder"] == "C:/test/images"

            # 3. Clear
            clear_session_state()
            assert not session_file.exists()
            assert load_session_state() is None

    def test_cleanup_old_binaries(self, tmp_path):
        """Test cleanup of leftover .old.*.exe files."""
        normal_exe = tmp_path / "arbor.exe"
        normal_exe.write_bytes(b"normal")
        data_file = tmp_path / "data.db"
        data_file.write_bytes(b"data")
        old_exe_1 = tmp_path / "arbor.old.20261106_120000.exe"
        old_exe_1.write_bytes(b"old binary 1")
        old_exe_2 = tmp_path / "arbor.old.20261106_123000.exe"
        old_exe_2.write_bytes(b"old binary 2")

        with patch("backend.updater.get_install_dir", return_value=str(tmp_path)):
            cleanup_old_binaries()

            assert normal_exe.exists()
            assert data_file.exists()
            assert not old_exe_1.exists()
            assert not old_exe_2.exists()

    def test_repo_config_persistence(self):
        """Test getting and setting custom update repository."""
        original_repo = config.get_update_repo()
        try:
            config.set_update_repo("CustomOrg/custom-arbor")
            assert config.get_update_repo() == "CustomOrg/custom-arbor"

            config.set_update_repo("Fr0lich/arbor")
            assert config.get_update_repo() == "Fr0lich/arbor"
        finally:
            config.set_update_repo(original_repo)

    def test_is_install_dir_writable(self, tmp_path):
        """Test write permission check."""
        with patch("backend.updater.get_install_dir", return_value=str(tmp_path)):
            assert is_install_dir_writable() is True
