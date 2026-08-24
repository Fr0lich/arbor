"""
backend/mobile_server.py

Embedded lightweight Flask REST API server for the Arbor Mobile Web Companion.
Runs in a background daemon thread and provides thread-safe access to AppState
dataframes (df_reg, df_obs, df_photo, df_log) using app_state.df_lock.
"""

from __future__ import annotations

import os
import queue
import socket
import threading
import uuid
import datetime
from typing import Any

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.serving import make_server, BaseWSGIServer

from models import AppState, MAX_UNDO_PER_OBJECT
from repository import REVIEWED_COLUMN, REVIEWED_AT_COLUMN

DIST_DIR = os.path.join(os.path.dirname(__file__), "mobile_app_dist")


def _to_python_value(val: Any) -> Any:
    """Converts numpy types (np.bool_, np.int64, np.float64, etc.) and NaN to JSON-serializable Python types."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (float, np.floating)):
        return float(val)
    if hasattr(val, "item"):
        try:
            return val.item()
        except Exception:
            pass
    return str(val)


def _find_object_index(df: pd.DataFrame | None, oid: str | int) -> Any | None:
    """Safely finds the exact index key in a DataFrame regardless of string/int type.
    
    Handles exact match, string-converted match, integer-converted match, and stripped whitespace.
    """
    if df is None or df.empty:
        return None
    if oid in df.index:
        return oid
    oid_str = str(oid).strip()
    if oid_str in df.index:
        return oid_str
    if oid_str.isdigit():
        oid_int = int(oid_str)
        if oid_int in df.index:
            return oid_int
    return None


def _extract_photo_filenames(df_photo: pd.DataFrame | None, oid: str | int) -> list[str]:
    """Extract photo filenames for an ObjectID defensively handling Series, DataFrame, or missing keys."""
    if df_photo is None or df_photo.empty:
        return []
    idx = _find_object_index(df_photo, oid)
    if idx is None:
        return []
    try:
        match = df_photo.loc[idx]
        if isinstance(match, pd.DataFrame):
            col = "Filename" if "Filename" in match.columns else match.columns[0]
            return [str(v).strip() for v in match[col].dropna() if str(v).strip() and str(v).lower() != "nan"]
        elif isinstance(match, pd.Series):
            col = "Filename" if "Filename" in match.index else match.index[0]
            val = str(match.get(col, "")).strip()
            return [val] if val and val.lower() not in ("nan", "none", "") else []
    except Exception:
        return []
    return []


def _build_dual_image_urls(oid: str, app_state: AppState) -> dict:
    """Constructs dual online and local image endpoints for a given ObjectID."""
    config = app_state.config or {}
    pattern = config.get("image_url_pattern", "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg")
    
    online_urls: list[str] = []
    if pattern:
        suffixes = ["", "-01", "-02", "-03"]
        is_numeric = str(oid).isdigit()
        for s in suffixes:
            if "{id}" in pattern:
                if "{suffix}" in pattern:
                    url = pattern.replace("{id}", str(oid)).replace("{suffix}", s)
                else:
                    url = pattern.replace("{id}", f"{oid}{s}")
            elif "{num" in pattern and "{suffix}" in pattern:
                if is_numeric:
                    num = int(oid)
                    url = pattern.format(num=num, suffix=s)
                else:
                    url = f"{pattern.rstrip('/')}/{oid}{s}"
            elif "{num" in pattern:
                if is_numeric:
                    num = int(oid)
                    url = pattern.format(num=num)
                    if s:
                        if "." in url.rsplit("/", 1)[-1]:
                            base, ext = url.rsplit(".", 1)
                            url = f"{base}{s}.{ext}"
                        else:
                            url = f"{url}{s}"
                else:
                    url = f"{pattern.rstrip('/')}/{oid}{s}"
            else:
                url = f"{pattern}{oid}{s}"
            online_urls.append(url)

    # Local fallback endpoints
    local_filenames = _extract_photo_filenames(app_state.df_photo, oid)
    local_endpoints = [f"/api/image/{oid}/{idx}" for idx in range(len(local_filenames))] if local_filenames else []

    preferred = "online"
    # If app is explicitly configured in local folder mode or has no online pattern
    if config.get("image_mode") == "folder" or not pattern:
        preferred = "local"

    return {
        "preferred_source": preferred,
        "online_urls": online_urls,
        "local_endpoints": local_endpoints,
        "photo_count": len(local_filenames) or len(online_urls)
    }


def _safe_resolve_local_image(oid: str, photo_idx: int, app_state: AppState) -> str | None:
    """Safely resolves the absolute file path for a photo, preventing directory traversal."""
    filenames = _extract_photo_filenames(app_state.df_photo, oid)
    if photo_idx < 0 or photo_idx >= len(filenames):
        return None

    filename = str(filenames[photo_idx]).strip()
    if not filename:
        return None

    # Look up in image_folder from config or AppState
    base_folder = getattr(app_state, "image_folder", None)
    if not base_folder and app_state.config:
        base_folder = app_state.config.get("image_folder")
    if not base_folder and app_state.excel_path:
        base_folder = os.path.dirname(app_state.excel_path)

    if not base_folder or not os.path.exists(base_folder):
        return None

    # Canonical path resolution & LFI traversal verification
    canonical_base = os.path.realpath(base_folder)
    if os.path.isabs(filename):
        canonical_target = os.path.realpath(filename)
    else:
        canonical_target = os.path.realpath(os.path.join(base_folder, filename))

    try:
        if os.path.commonpath([canonical_base, canonical_target]) != canonical_base:
            return None  # Path traversal attempt outside base_folder
    except (ValueError, Exception):
        return None

    if not os.path.isfile(canonical_target):
        return None

    return canonical_target


def create_flask_app(server_mgr: MobileServerManager) -> Flask:
    """Flask application factory configured for thread-safe AppState access."""
    app = Flask(__name__)

    @app.before_request
    def check_auth():
        # Allow preflight OPTIONS
        if request.method == "OPTIONS":
            return "", 204

        # Allow static SPA assets and root index to be delivered without blocking
        # (Session token is parsed client-side by the SPA from query params or localStorage)
        if not request.path.startswith("/api/"):
            return None

        # Token validation: passed via Header 'X-Session-Token' or query param '?token='
        token = request.headers.get("X-Session-Token") or request.args.get("token")
        if server_mgr.session_token and token != server_mgr.session_token:
            return jsonify({"error": "Unauthorized: Invalid or missing session token"}), 401

        # Track client heartbeat
        client_ip = request.remote_addr or "unknown"
        server_mgr.connected_clients[client_ip] = datetime.datetime.now().timestamp()

    @app.after_request
    def add_headers(response):
        # Strict Cache-Control to prevent stale GET responses on mobile browsers
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        # CORS headers for local development and companion pairing
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Session-Token"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.route("/api/status", methods=["GET"])
    def get_status():
        with server_mgr.app_state.df_lock:
            df_reg = server_mgr.app_state.df_reg
            df_obs = server_mgr.app_state.df_obs
            
            total_objects = len(df_reg) if df_reg is not None else 0
            reviewed_count = 0
            if df_obs is not None and REVIEWED_COLUMN in df_obs.columns:
                try:
                    reviewed_count = int(df_obs[REVIEWED_COLUMN].fillna(False).astype(bool).sum())
                except Exception:
                    reviewed_count = 0
            
            pending_count = max(0, total_objects - reviewed_count)
            db_name = (
                server_mgr.app_state.config_name 
                or (os.path.basename(server_mgr.app_state.excel_path) if server_mgr.app_state.excel_path else "Arbor Database")
            )

            # Active clients in last 60 seconds
            now = datetime.datetime.now().timestamp()
            active_sessions = sum(1 for t in server_mgr.connected_clients.values() if now - t < 60)

            return jsonify({
                "status": "online",
                "database_name": db_name,
                "total_objects": total_objects,
                "reviewed_count": reviewed_count,
                "pending_count": pending_count,
                "dirty": bool(server_mgr.app_state.dirty),
                "active_sessions": max(1, active_sessions),
                "server_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })

    @app.route("/api/objects", methods=["GET"])
    def get_objects():
        query = request.args.get("q", "").strip().lower()
        status_filter = request.args.get("status", "all").strip().lower()
        limit = min(int(request.args.get("limit", 100)), 1000)
        offset = max(int(request.args.get("offset", 0)), 0)

        with server_mgr.app_state.df_lock:
            df_reg = server_mgr.app_state.df_reg
            df_obs = server_mgr.app_state.df_obs

            if df_reg is None or df_reg.empty:
                return jsonify({"total_matching": 0, "offset": offset, "limit": limit, "objects": []})

            objects = []
            for oid in df_reg.index:
                oid_str = str(oid)
                reg_row = df_reg.loc[oid]
                obs_row = df_obs.loc[oid] if df_obs is not None and oid in df_obs.index else None

                # Extract standard taxonomy/location fields with fallbacks
                genus = str(reg_row.get("Genus", "") if hasattr(reg_row, "get") else "").strip()
                species = str(reg_row.get("Species", "") if hasattr(reg_row, "get") else "").strip()
                family = str(reg_row.get("Family", "") if hasattr(reg_row, "get") else "").strip()
                scientific_name = f"{genus} {species}".strip() or oid_str

                # Determine review status
                is_reviewed = False
                if obs_row is not None and REVIEWED_COLUMN in obs_row:
                    val = obs_row[REVIEWED_COLUMN]
                    is_reviewed = bool(val) and str(val).lower() not in ("nan", "none", "false", "0", "")

                review_status = "reviewed" if is_reviewed else "pending"

                # Check for problem flags in obs_row
                has_flags = False
                if obs_row is not None:
                    for col, val in obs_row.items():
                        if str(col).endswith("_Problem") and bool(val) and str(val).lower() not in ("nan", "none", "false", "0", ""):
                            has_flags = True
                            break

                # Status filter
                if status_filter == "reviewed" and not is_reviewed:
                    continue
                if status_filter == "pending" and is_reviewed:
                    continue
                if status_filter == "flagged" and not has_flags:
                    continue

                # Query search filter
                if query:
                    searchable = f"{oid_str} {genus} {species} {family}".lower()
                    if query not in searchable:
                        continue

                # Location tags
                location = {}
                for loc_key in ("Cabinet", "Drawer", "Tray", "Box", "Room", "Location"):
                    if hasattr(reg_row, "get") and reg_row.get(loc_key):
                        location[loc_key.lower()] = str(reg_row.get(loc_key)).strip()

                objects.append({
                    "id": oid_str,
                    "accession_number": oid_str,
                    "scientific_name": scientific_name,
                    "genus": genus,
                    "species": species,
                    "family": family,
                    "location": location,
                    "review_status": review_status,
                    "has_flags": has_flags
                })

            total_matching = len(objects)
            paginated = objects[offset:offset + limit]

            return jsonify({
                "total_matching": total_matching,
                "offset": offset,
                "limit": limit,
                "objects": paginated
            })

    @app.route("/api/object/<id>", methods=["GET"])
    def get_object_detail(id: str):
        with server_mgr.app_state.df_lock:
            df_reg = server_mgr.app_state.df_reg
            df_obs = server_mgr.app_state.df_obs

            if df_reg is None or df_reg.empty:
                return jsonify({"error": "No database loaded"}), 404

            reg_idx = _find_object_index(df_reg, id)
            if reg_idx is None:
                return jsonify({"error": f"Object '{id}' not found"}), 404

            reg_row = df_reg.loc[reg_idx]
            obs_idx = _find_object_index(df_obs, id) if df_obs is not None else None
            obs_row = df_obs.loc[obs_idx] if obs_idx is not None else None

            # Dynamic dictionary mapping for registration
            registration = {}
            if hasattr(reg_row, "items"):
                for k, v in reg_row.items():
                    registration[str(k)] = _to_python_value(v)

            # Dynamic dictionary mapping for observation
            observation = {}
            flagged_issues = []
            if obs_row is not None and hasattr(obs_row, "items"):
                for k, v in obs_row.items():
                    py_val = _to_python_value(v)
                    observation[str(k)] = py_val
                    if str(k).endswith("_Problem") and bool(py_val) and str(py_val).lower() not in ("nan", "none", "false", "0", ""):
                        flagged_issues.append({
                            "id": f"flag-{k}",
                            "field": str(k).replace("_Problem", ""),
                            "severity": "warning",
                            "reason": f"Discrepancy flagged on {k}",
                            "resolved": False
                        })

            is_reviewed = False
            if obs_row is not None and REVIEWED_COLUMN in obs_row:
                val = obs_row[REVIEWED_COLUMN]
                is_reviewed = bool(val) and str(val).lower() not in ("nan", "none", "false", "0", "")

            images = _build_dual_image_urls(str(id), server_mgr.app_state)

            genus = str(registration.get("Genus", "") or "").strip()
            species = str(registration.get("Species", "") or "").strip()
            scientific_name = f"{genus} {species}".strip() or str(id)

            return jsonify({
                "id": str(id),
                "accession_number": str(id),
                "scientific_name": scientific_name,
                "registration": registration,
                "observation": observation,
                "review_status": "reviewed" if is_reviewed else "pending",
                "flagged_issues": flagged_issues,
                "images": images
            })

    @app.route("/api/update", methods=["POST"])
    def update_object():
        data = request.get_json()
        if not data or "id" not in data:
            return jsonify({"error": "Missing 'id' in request body"}), 400

        oid = str(data["id"])
        with server_mgr.app_state.df_lock:
            df_obs = server_mgr.app_state.df_obs
            if df_obs is None or df_obs.empty:
                return jsonify({"error": "Observation dataframe not loaded"}), 404

            obs_idx = _find_object_index(df_obs, oid)
            if obs_idx is None:
                return jsonify({"error": f"Object '{oid}' not found in observations"}), 404

            # 1. Snapshot previous state into undo stack for desktop Ctrl+Z support
            current_obs_snapshot = {}
            row = df_obs.loc[obs_idx]
            if hasattr(row, "items"):
                for k, v in row.items():
                    current_obs_snapshot[str(k)] = _to_python_value(v)
            
            stack = server_mgr.app_state.undo_stacks.setdefault(str(oid), [])
            stack.append(current_obs_snapshot)
            if len(stack) > MAX_UNDO_PER_OBJECT:
                server_mgr.app_state.undo_stacks[str(oid)] = stack[-MAX_UNDO_PER_OBJECT:]

            # 2. Update review status if provided
            if "reviewed" in data:
                is_rev = bool(data["reviewed"])
                df_obs.at[obs_idx, REVIEWED_COLUMN] = is_rev
                if is_rev:
                    df_obs.at[obs_idx, REVIEWED_AT_COLUMN] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 3. Update observation field values
            obs_updates = data.get("observation", {})
            for field, val in obs_updates.items():
                if field in df_obs.columns:
                    df_obs.at[obs_idx, field] = val

            # 4. Record in change log
            now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            server_mgr.app_state._log_records.append({
                "Timestamp": now_iso,
                "ObjectID": str(oid),
                "Action": "MOBILE_UPDATE",
                "Details": f"Updated via Mobile Companion: {list(obs_updates.keys())}"
            })

            # 5. Mark application state dirty
            server_mgr.app_state.dirty = True

        # 6. Post event to Tkinter cross-thread queue
        event_payload = {
            "type": "update",
            "oid": str(oid),
            "reviewed": data.get("reviewed"),
            "observation": obs_updates,
            "timestamp": now_iso
        }
        server_mgr.post_mobile_edit_event(event_payload)

        return jsonify({
            "success": True,
            "id": str(oid),
            "review_status": "reviewed" if data.get("reviewed", False) else "pending",
            "synced_at": now_iso
        })

    @app.route("/api/image/<oid>/<int:photo_idx>", methods=["GET"])
    def get_local_image(oid: str, photo_idx: int):
        with server_mgr.app_state.df_lock:
            image_path = _safe_resolve_local_image(oid, photo_idx, server_mgr.app_state)

        if not image_path or not os.path.isfile(image_path):
            return jsonify({"error": "Image not found or access forbidden"}), 404

        return send_file(image_path)

    # ── Static SPA Routes ────────────────────────────────────────────────────────

    @app.route("/", methods=["GET"])
    def serve_index():
        """Delivers the Mobile Companion SPA entry page."""
        index_path = os.path.join(DIST_DIR, "index.html")
        if os.path.isfile(index_path):
            return send_file(index_path)
        return _render_fallback_landing_page(server_mgr), 200

    @app.route("/assets/<path:filename>", methods=["GET"])
    def serve_assets(filename: str):
        """Serves compiled static CSS/JS assets."""
        assets_dir = os.path.join(DIST_DIR, "assets")
        return send_from_directory(assets_dir, filename)

    @app.route("/<path:fallback_path>", methods=["GET"])
    def serve_spa_fallback(fallback_path: str):
        """Fallback handler for SPA routing and static files."""
        if fallback_path.startswith("api/"):
            return jsonify({"error": "Endpoint not found"}), 404

        target_file = os.path.join(DIST_DIR, fallback_path)
        if os.path.isfile(target_file):
            return send_file(target_file)

        index_path = os.path.join(DIST_DIR, "index.html")
        if os.path.isfile(index_path):
            return send_file(index_path)
        return _render_fallback_landing_page(server_mgr), 200

    return app


def _render_fallback_landing_page(server_mgr: MobileServerManager) -> str:
    """Generates an HTML fallback page if the pre-built dist folder is missing."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Arbor · Mobile Companion</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f3f3; color: #191e1a; padding: 2rem 1rem; text-align: center; }}
    .card {{ background: white; border: 1px solid #d4d8d5; border-radius: 8px; max-width: 420px; margin: 0 auto; padding: 1.5rem; }}
    .badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: bold; background: #eff7f1; color: #3a7d44; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">● Server Active</div>
    <h2 style="margin: 0.75rem 0 0.25rem;">Arbor Mobile Companion</h2>
    <p style="font-size: 0.85rem; color: #535d56;">Connected to port {server_mgr.port}</p>
    <p style="font-size: 0.8rem; color: #848f87; margin-top: 1rem;">Session Token: <code>{server_mgr.session_token}</code></p>
  </div>
</body>
</html>"""


class MobileServerManager:
    """Manages the background Flask server daemon and Tkinter event dispatching."""

    def __init__(self, app_state: AppState, root_tk: Any | None = None, host: str = "127.0.0.1", port: int = 8765):
        self.app_state = app_state
        self.root_tk = root_tk
        self.host = host
        self.port = port
        self.server_thread: threading.Thread | None = None
        self.http_server: BaseWSGIServer | None = None
        self.is_running: bool = False
        self.session_token: str = uuid.uuid4().hex[:8]
        self.event_queue: queue.Queue = queue.Queue()
        self.connected_clients: dict[str, float] = {}
        self.app = create_flask_app(self)

    def _find_available_port(self, preferred_port: int) -> int:
        """Attempts preferred port; falls back to an available dynamic OS port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((self.host, preferred_port)) != 0:
                return preferred_port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, 0))
            return s.getsockname()[1]

    def start(self, port: int | None = None) -> int:
        """Starts the Flask server in a background daemon thread and returns the active port."""
        if self.is_running and self.http_server:
            return self.port

        target_port = port or self.port
        self.port = self._find_available_port(target_port)
        self.http_server = make_server(self.host, self.port, self.app, threaded=True)

        def _serve():
            try:
                self.is_running = True
                if self.http_server:
                    self.http_server.serve_forever()
            except Exception:
                pass
            finally:
                self.is_running = False

        self.server_thread = threading.Thread(target=_serve, daemon=True, name="ArborMobileServerDaemon")
        self.server_thread.start()
        return self.port

    def stop(self) -> None:
        """Gracefully shuts down the background WSGI server."""
        if self.http_server and self.is_running:
            self.http_server.shutdown()
            self.http_server = None
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1.0)
            self.server_thread = None
        self.is_running = False

    def post_mobile_edit_event(self, edit_payload: dict) -> None:
        """Enqueues an edit payload and notifies the Tkinter mainloop safely."""
        self.event_queue.put(edit_payload)
        if self.root_tk is not None and hasattr(self.root_tk, "winfo_exists"):
            try:
                if self.root_tk.winfo_exists():
                    self.root_tk.event_generate("<<MobileEditReceived>>", when="tail")
            except Exception:
                pass

    def get_status(self) -> dict:
        """Returns runtime server status dictionary."""
        return {
            "is_running": self.is_running,
            "host": self.host,
            "port": self.port,
            "session_token": self.session_token,
            "active_clients": len(self.connected_clients),
            "pending_events": self.event_queue.qsize()
        }
