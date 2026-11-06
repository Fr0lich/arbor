import os
import sys
import time
import json
import struct
import subprocess
from datetime import datetime
import requests
from packaging.version import parse as parse_version
import config


def is_frozen():
    """Return True if running as a compiled standalone executable (PyInstaller), False if source."""
    return getattr(sys, "frozen", False)


def get_install_dir():
    """Return directory containing the running executable (or main.py if in source)."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_staging_dir():
    """Return update staging directory (collocated with executable)."""
    staging = os.path.join(get_install_dir(), ".arbor_update")
    os.makedirs(staging, exist_ok=True)
    return staging


def is_install_dir_writable():
    """Test whether the installation folder is writable (detects C:\\Program Files without admin rights)."""
    install_dir = get_install_dir()
    test_path = os.path.join(install_dir, f".perm_test_{os.getpid()}")
    try:
        with open(test_path, "w") as f:
            f.write("ok")
        if os.path.exists(test_path):
            os.remove(test_path)
        return True
    except (PermissionError, OSError):
        return False


def validate_pe_executable(file_path):
    """
    Validate that a file is a non-empty Windows PE executable by inspecting DOS/PE headers.
    Guards against truncated downloads or HTML error pages saved as .exe.
    """
    if not os.path.isfile(file_path):
        return False

    size = os.path.getsize(file_path)
    if size < 1024:
        return False

    try:
        with open(file_path, "rb") as f:
            header = f.read(1024)

        # 1. Check DOS MZ header signature (0x4D5A)
        if len(header) < 64 or header[:2] != b"MZ":
            return False

        # 2. Extract PE header offset from DOS header offset 0x3C
        pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
        if pe_offset + 4 > size:
            return False

        with open(file_path, "rb") as f:
            f.seek(pe_offset)
            pe_sig = f.read(4)

        # 3. Check PE signature (PE\0\0)
        return pe_sig == b"PE\x00\x00"
    except Exception:
        return False


def check_for_updates(repo=None, timeout=6):
    """
    Query the GitHub REST API for the latest release.
    Handles repository redirects, 404s, rate-limiting, and network timeouts.
    """
    if not repo:
        repo = config.get_update_repo()

    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": f"Arbor-Desktop/{config.APP_VERSION}"
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=timeout, allow_redirects=True)

        # Handle automatic repository migration redirect
        if response.history:
            final_url = response.url
            # Example: https://api.github.com/repos/NewOrg/arbor/releases/latest
            parts = final_url.split("/repos/")
            if len(parts) > 1:
                new_repo = parts[1].replace("/releases/latest", "").strip("/")
                if new_repo and new_repo != repo:
                    config.set_update_repo(new_repo)
                    repo = new_repo

        if response.status_code == 200:
            data = response.json()
            raw_tag = data.get("tag_name", "").strip()
            latest_version_str = raw_tag.lstrip("vV").strip()
            release_name = data.get("name", f"Arbor {raw_tag}")
            release_notes = data.get("body", "No release notes provided.")
            release_url = data.get("html_url", f"https://github.com/{repo}/releases")

            # Find matching Windows executable asset
            assets = data.get("assets", [])
            download_url = None
            asset_name = None
            asset_size = 0

            for asset in assets:
                name = asset.get("name", "")
                if name.lower().endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    asset_name = name
                    asset_size = asset.get("size", 0)
                    break

            current_ver = parse_version(config.APP_VERSION)
            latest_ver = parse_version(latest_version_str) if latest_version_str else current_ver
            has_update = latest_ver > current_ver

            return {
                "status": "ok",
                "has_update": has_update,
                "latest_version": latest_version_str or config.APP_VERSION,
                "current_version": config.APP_VERSION,
                "tag_name": raw_tag,
                "release_name": release_name,
                "release_notes": release_notes,
                "release_url": release_url,
                "download_url": download_url,
                "asset_name": asset_name,
                "asset_size": asset_size,
                "repo": repo,
            }

        elif response.status_code == 404:
            return {
                "status": "404_not_found",
                "repo": repo,
                "message": f"Repository '{repo}' not found on GitHub. It may have been moved, renamed, or made private."
            }
        elif response.status_code == 403:
            return {
                "status": "rate_limited",
                "repo": repo,
                "message": "GitHub API hourly request limit reached. Please try again later or check directly in your browser."
            }
        else:
            return {
                "status": "error",
                "repo": repo,
                "code": response.status_code,
                "message": f"GitHub returned HTTP status {response.status_code}."
            }

    except (requests.ConnectionError, requests.Timeout) as e:
        return {
            "status": "offline_or_error",
            "repo": repo,
            "error": str(e),
            "message": "Unable to connect to GitHub. Please check your network connection."
        }
    except Exception as e:
        return {
            "status": "error",
            "repo": repo,
            "error": str(e),
            "message": f"Unexpected error during update check: {e}"
        }


def download_update_staged(download_url, expected_size=0, progress_callback=None, cancel_event=None):
    """
    Stream download the executable into a staging folder with progress reporting and PE header validation.
    """
    staging_dir = get_staging_dir()
    part_path = os.path.join(staging_dir, "arbor_update.part")
    final_path = os.path.join(staging_dir, "arbor_update.exe")

    if os.path.exists(part_path):
        try:
            os.remove(part_path)
        except Exception:
            pass

    headers = {"User-Agent": f"Arbor-Desktop/{config.APP_VERSION}"}
    response = requests.get(download_url, stream=True, headers=headers, timeout=20)
    response.raise_for_status()

    total_bytes = int(response.headers.get("Content-Length", expected_size or 0))
    downloaded = 0
    chunk_size = 16384

    with open(part_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if cancel_event and cancel_event.is_set():
                f.close()
                if os.path.exists(part_path):
                    os.remove(part_path)
                return None

            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total_bytes > 0:
                    percent = min(100.0, (downloaded / total_bytes) * 100.0)
                    progress_callback(percent, downloaded, total_bytes)

    # Validate binary integrity
    if not validate_pe_executable(part_path):
        if os.path.exists(part_path):
            os.remove(part_path)
        raise ValueError("Downloaded file is not a valid Windows executable. Update aborted.")

    if os.path.exists(final_path):
        try:
            os.remove(final_path)
        except Exception:
            pass

    os.replace(part_path, final_path)
    return final_path


# ============================================================================
# SESSION STATE PRESERVATION & RESTORATION
# ============================================================================

def get_session_restore_path():
    """Return location of the ephemeral session restore JSON file."""
    app_data = os.path.join(os.path.expanduser("~"), ".arbor")
    os.makedirs(app_data, exist_ok=True)
    return os.path.join(app_data, "session_restore.json")


def save_session_state(app):
    """Save active workbook path and selected specimen ID before restarting."""
    try:
        # Flush UI focus to commit in-flight typing
        if hasattr(app, "root") and app.root and hasattr(app.root, "winfo_exists") and app.root.winfo_exists():
            try:
                app.root.focus_set()
            except Exception:
                pass

        # Try to trigger autosave if dirty
        try:
            if hasattr(app, "_autosave_tick") and callable(app._autosave_tick):
                app._autosave_tick(skip_commit=False)
        except Exception:
            pass

        inner_app = getattr(app, "app", None)
        excel_path = getattr(app, "excel_path", "") or (getattr(inner_app, "excel_path", "") if inner_app else "")
        active_oid = getattr(app, "last_object_id", "") or getattr(app, "current_object_id", "") or (getattr(inner_app, "current_object_id", "") if inner_app else "")
        config_name = getattr(app, "config_name", "") or (getattr(inner_app, "config_name", "") if inner_app else "")
        image_mode = getattr(app, "image_mode", "online")
        image_folder = getattr(app, "image_folder", "")

        state = {
            "excel_path": excel_path,
            "active_object_id": str(active_oid) if active_oid is not None else "",
            "config_name": config_name,
            "image_mode": image_mode,
            "image_folder": image_folder,
            "timestamp": datetime.now().isoformat()
        }
        with open(get_session_restore_path(), "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        print(f"Warning: Failed to save session restore state: {e}", file=sys.stderr)
        return False


def load_session_state():
    """Retrieve saved session restore state if present."""
    path = get_session_restore_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return None


def clear_session_state():
    """Remove session restore file."""
    path = get_session_restore_path()
    if os.path.isfile(path):
        try:
            os.remove(path)
        except Exception:
            pass


def cleanup_old_binaries():
    """Clean up leftover .old.*.exe files from previous updates."""
    install_dir = get_install_dir()
    if not os.path.isdir(install_dir):
        return

    try:
        for fname in os.listdir(install_dir):
            if ".old." in fname and fname.lower().endswith(".exe"):
                old_path = os.path.join(install_dir, fname)
                try:
                    os.remove(old_path)
                except Exception:
                    pass
    except Exception:
        pass


def execute_swap_and_restart(app=None):
    """
    Execute NTFS atomic rename and restart into the new executable.
    Renames running arbor.exe -> arbor.old.{timestamp}.exe,
    moves staged update -> arbor.exe, launches new process, and exits old process.
    """
    if not is_frozen():
        raise RuntimeError("In-place executable swap can only be performed on compiled binaries.")

    current_exe = os.path.abspath(sys.executable)
    staged_exe = os.path.join(get_staging_dir(), "arbor_update.exe")

    if not os.path.isfile(staged_exe) or not validate_pe_executable(staged_exe):
        raise FileNotFoundError("Valid staged update executable not found.")

    # Save session state if app instance is provided
    if app:
        save_session_state(app)

    old_exe = f"{current_exe}.old.{int(time.time())}.exe"

    # Step 1: Rename running binary to old binary
    try:
        os.rename(current_exe, old_exe)
    except Exception as e:
        raise OSError(f"Failed to rename running executable: {e}")

    # Step 2: Move new binary to main executable path
    try:
        os.replace(staged_exe, current_exe)
    except Exception as e:
        # Rollback rename if move fails
        try:
            os.rename(old_exe, current_exe)
        except Exception:
            pass
        raise OSError(f"Failed to install new executable into place: {e}")

    # Step 3: Spawn new process
    args = [current_exe, "--restore-session"]
    proc = subprocess.Popen(args, close_fds=True)

    # Step 4: Terminate current process cleanly
    if app and hasattr(app, "root") and app.root.winfo_exists():
        app.root.after(100, lambda: sys.exit(0))
    else:
        sys.exit(0)
