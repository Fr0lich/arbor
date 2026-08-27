import threading
import logging
import random
import string
import json
import base64
import os
import io
import mimetypes
import socket
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file
from werkzeug.utils import secure_filename
import pandas as pd
import config
from utils import debug_error

def sanitize_value(val):
    if pd.isna(val) or val is None:
        return ""
    return str(val).strip()

def coerce_type(val, dtype):
    if pd.isna(val) or val is None:
        return ""
    if pd.api.types.is_bool_dtype(dtype):
        return str(val).strip().lower() in ("true", "1", "yes", "t")
    if pd.api.types.is_integer_dtype(dtype):
        try:
            return int(val)
        except Exception:
            return 0
    if pd.api.types.is_float_dtype(dtype):
        try:
            return float(val)
        except Exception:
            return 0.0
    return str(val).strip()

# Reduce Flask logging spam
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


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


class MobileServer:
    def __init__(self, app_state, root_tk=None, port=5055, on_edit_callback=None):
        self.app_state = app_state
        self.root_tk = root_tk
        self.port = port
        self.on_edit_callback = on_edit_callback
        self.flask_app = Flask(__name__)
        self.session_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        self.pin = ''.join(random.choices(string.digits, k=4))
        self.thread = None
        self._is_running = False
        self.recent_edits = []  # list of dicts: {oid, summary, time}
        self._auth_attempts = {}
        self._setup_routes()

    def start(self):
        if self._is_running:
            return
        self._is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.flask_app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)
        except Exception as e:
            debug_error("Mobile Server Crash", str(e))
        finally:
            self._is_running = False

    def stop(self):
        self._is_running = False

    def _check_rate_limit(self, ip):
        if ip not in self._auth_attempts:
            self._auth_attempts[ip] = {"consecutive": 0, "recent": [], "lockout_until": 0}

        state = self._auth_attempts[ip]
        now = time.time()

        if now < state["lockout_until"]:
            remaining = int(state["lockout_until"] - now)
            if remaining <= 0:
                remaining = 1
            return jsonify({"error": f"Too many failed attempts. Please wait {remaining} seconds.", "retry_after_seconds": remaining}), 429, {'Retry-After': str(remaining)}

        # Clean up old failures
        state["recent"] = [t for t in state["recent"] if now - t < 60]

        if len(state["recent"]) >= 5:
            remaining = 60 - int(now - state["recent"][0])
            if remaining <= 0:
                remaining = 60
            return jsonify({"error": f"Too many failed attempts. Please wait {remaining} seconds.", "retry_after_seconds": remaining}), 429, {'Retry-After': str(remaining)}

        return None

    def _record_failure(self, ip):
        if ip not in self._auth_attempts:
            self._auth_attempts[ip] = {"consecutive": 0, "recent": [], "lockout_until": 0}
        state = self._auth_attempts[ip]
        now = time.time()
        state["recent"].append(now)
        state["consecutive"] += 1

        if state["consecutive"] >= 10:
            state["lockout_until"] = now + 15 * 60
            remaining = 15 * 60
            return jsonify({"error": f"Too many failed attempts. Please wait {remaining} seconds.", "retry_after_seconds": remaining}), 429, {'Retry-After': str(remaining)}

        return None

    def _record_success(self, ip):
        if ip in self._auth_attempts:
            self._auth_attempts[ip] = {"consecutive": 0, "recent": [], "lockout_until": 0}

    def _check_auth(self):
        """Verify session token or PIN authentication."""
        # 1. Header token
        auth_header = request.headers.get('X-Session-Token')
        if auth_header and auth_header == self.session_token:
            return True
        # 2. Query param token
        token_param = request.args.get('token')
        if token_param and token_param == self.session_token:
            return True
        # 3. Cookie session
        if session.get('authenticated') is True:
            return True
        return False

    def _setup_routes(self):
        app = self.flask_app
        app.secret_key = self.session_token

        @app.before_request
        def require_auth():
            if request.endpoint in ['login', 'static', 'api_auth', None]:
                return
            if not self._check_auth():
                if request.path.startswith('/api/'):
                    return jsonify({"error": "Unauthorized: Invalid or missing session token"}), 401
                return redirect(url_for('login', next=request.url))

        @app.route('/login', methods=['GET', 'POST'])
        def login():
            error = None
            if request.method == 'POST':
                ip = request.remote_addr
                rate_limit_resp = self._check_rate_limit(ip)
                if rate_limit_resp:
                    return rate_limit_resp

                provided_pin = request.form.get('pin', '').strip()
                if provided_pin == self.pin:
                    self._record_success(ip)
                    session['authenticated'] = True
                    return redirect(url_for('index'))
                else:
                    lockout_resp = self._record_failure(ip)
                    if lockout_resp:
                        return lockout_resp
                    error = 'Invalid PIN'
            return render_template_string(LOGIN_TEMPLATE, error=error)

        @app.route('/logout')
        def logout():
            session.pop('authenticated', None)
            return redirect(url_for('login'))

        @app.route('/api/auth', methods=['POST'])
        def api_auth():
            ip = request.remote_addr
            rate_limit_resp = self._check_rate_limit(ip)
            if rate_limit_resp:
                return rate_limit_resp

            data = request.get_json(silent=True) or {}
            provided_pin = str(data.get('pin', '')).strip()
            provided_token = str(data.get('token', '')).strip()

            if provided_token == self.session_token or provided_pin == self.pin:
                self._record_success(ip)
                session['authenticated'] = True
                return jsonify({
                    "success": True,
                    "token": self.session_token,
                    "message": "Authenticated successfully"
                })

            lockout_resp = self._record_failure(ip)
            if lockout_resp:
                return lockout_resp
            return jsonify({"success": False, "error": "Invalid PIN"}), 401

        @app.route('/')
        def index():
            token_param = request.args.get('token')
            if token_param == self.session_token:
                session['authenticated'] = True
            return render_template_string(INDEX_TEMPLATE, token=self.session_token)

        # -------------------------------------------------------------
        # REST API (Conforming to arbor-mobile-companion / src/api.ts)
        # -------------------------------------------------------------

        @app.route('/api/status', methods=['GET'])
        def get_status():
            with self.app_state.df_lock:
                total = len(self.app_state.df_reg) if self.app_state.df_reg is not None else 0
                reviewed_count = 0
                pending_count = total
                if self.app_state.df_obs is not None and "Reviewed" in self.app_state.df_obs.columns:
                    rev_series = self.app_state.df_obs["Reviewed"].astype(str).str.strip().str.lower()
                    reviewed_count = int(rev_series.isin(["true", "1", "yes"]).sum())
                    pending_count = max(0, total - reviewed_count)

                db_name = os.path.basename(self.app_state.excel_path) if self.app_state.excel_path else "Active Database"

            return jsonify({
                "status": "ok",
                "arbor_version": "1.0.0",
                "database_name": db_name,
                "total_objects": total,
                "reviewed_count": reviewed_count,
                "pending_count": pending_count,
                "dirty": getattr(self.app_state, 'dirty', False),
                "server_time": datetime.now().isoformat()
            })

        @app.route('/api/objects', methods=['GET'])
        def get_objects():
            if self.app_state.df_reg is None:
                return jsonify({"total_matching": 0, "offset": 0, "limit": 0, "objects": []})

            query = request.args.get('q', '').strip().lower()
            status_filter = request.args.get('status', 'all').lower()

            # New query parameters
            cabinet_filter = request.args.get('cabinet', '').strip().lower()
            room_filter = request.args.get('room', '').strip().lower()
            genus_filter = request.args.get('genus', '').strip().lower()
            collector_filter = request.args.get('collector', '').strip().lower()
            has_problems_filter = request.args.get('has_problems', '').strip().lower()

            sort_by = request.args.get('sort_by', '').strip().lower()
            sort_dir = request.args.get('sort_dir', 'asc').strip().lower()

            limit = max(1, min(int(request.args.get('limit', 100)), 500))
            offset = max(0, int(request.args.get('offset', 0)))

            with self.app_state.df_lock:
                df_reg = self.app_state.df_reg
                df_obs = self.app_state.df_obs

                rev_col = "Reviewed" if (df_obs is not None and "Reviewed" in df_obs.columns) else None
                matched_indices = df_reg.index

                # Text search
                if query:
                    mask = pd.Series(False, index=matched_indices)
                    mask |= df_reg.index.astype(str).str.lower().str.contains(query, regex=False)
                    for col in ["Genus", "Species", "Family", "ScientificName", "Locality"]:
                        if col in df_reg.columns:
                            mask |= df_reg[col].fillna("").astype(str).str.lower().str.contains(query, regex=False)
                    matched_indices = matched_indices[mask]

                # Status filter
                if status_filter != 'all' and rev_col and df_obs is not None:
                    rev_series = df_obs.reindex(matched_indices)[rev_col].astype(str).str.strip().str.lower()
                    is_rev = rev_series.isin(["true", "1", "yes"])
                    if status_filter == 'reviewed':
                        matched_indices = matched_indices[is_rev]
                    elif status_filter == 'pending':
                        matched_indices = matched_indices[~is_rev]

                # Cabinet filter
                if cabinet_filter:
                    combined_cabinets = pd.Series(index=matched_indices, dtype=str)
                    if "Cabinet" in df_reg.columns:
                        combined_cabinets = df_reg["Cabinet"].reindex(matched_indices)
                    if df_obs is not None and "Cabinet" in df_obs.columns:
                        combined_cabinets = df_obs["Cabinet"].reindex(matched_indices).combine_first(combined_cabinets)

                    mask = combined_cabinets.fillna("").astype(str).str.lower() == cabinet_filter
                    matched_indices = matched_indices[mask]

                # Room filter
                if room_filter:
                    combined_rooms = pd.Series(index=matched_indices, dtype=str)
                    if "Room" in df_reg.columns:
                        combined_rooms = df_reg["Room"].reindex(matched_indices)
                    if df_obs is not None and "Room" in df_obs.columns:
                        combined_rooms = df_obs["Room"].reindex(matched_indices).combine_first(combined_rooms)

                    mask = combined_rooms.fillna("").astype(str).str.lower() == room_filter
                    matched_indices = matched_indices[mask]

                # Genus filter
                if genus_filter:
                    if "Genus" in df_reg.columns:
                        mask = df_reg["Genus"].reindex(matched_indices).fillna("").astype(str).str.lower() == genus_filter
                        matched_indices = matched_indices[mask]

                # Collector filter
                if collector_filter:
                    if "Collector" in df_reg.columns:
                        mask = df_reg["Collector"].reindex(matched_indices).fillna("").astype(str).str.lower().str.contains(collector_filter, regex=False)
                        matched_indices = matched_indices[mask]

                # Has problems filter
                if has_problems_filter:
                    mask = pd.Series(False, index=matched_indices)
                    problems = []
                    if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                        problems = [p.get("name") for p in self.app_state.config["ui_sections"]["problems"]]

                    for p_col in problems:
                        combined_prob = pd.Series(index=matched_indices, dtype=str)
                        if p_col in df_reg.columns:
                            combined_prob = df_reg[p_col].reindex(matched_indices)
                        if df_obs is not None and p_col in df_obs.columns:
                            combined_prob = df_obs[p_col].reindex(matched_indices).combine_first(combined_prob)

                        mask |= combined_prob.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "t"])

                    if has_problems_filter in ["true", "1", "yes", "t"]:
                        matched_indices = matched_indices[mask]
                    elif has_problems_filter in ["false", "0", "no", "f"]:
                        matched_indices = matched_indices[~mask]

                total_matching = len(matched_indices)

                # Facet computation
                facets = {}

                # 1. Cabinets facet
                cabinet_series = pd.Series(index=matched_indices, dtype=str)
                if "Cabinet" in df_reg.columns:
                    cabinet_series = df_reg["Cabinet"].reindex(matched_indices)
                if df_obs is not None and "Cabinet" in df_obs.columns:
                    cabinet_series = df_obs["Cabinet"].reindex(matched_indices).combine_first(cabinet_series)

                cabinet_series = cabinet_series.fillna("").astype(str).str.strip()
                cabinet_series = cabinet_series[cabinet_series != ""]
                facets["cabinets"] = cabinet_series.value_counts().to_dict()

                # 2. Review counts
                reviewed_count = 0
                pending_count = total_matching
                if rev_col and df_obs is not None:
                    rev_series_facet = df_obs.reindex(matched_indices)[rev_col].astype(str).str.strip().str.lower()
                    reviewed_count = int(rev_series_facet.isin(["true", "1", "yes"]).sum())
                    pending_count = max(0, total_matching - reviewed_count)

                facets["reviewed_count"] = reviewed_count
                facets["pending_count"] = pending_count

                # Sorting logic
                if sort_by in ['id', 'genus', 'cabinet']:
                    ascending = (sort_dir == 'asc')
                    if sort_by == 'id':
                        # Use numeric sorting if possible, otherwise string sorting
                        try:
                            # index might be strings of integers
                            num_index = matched_indices.astype(int)
                            matched_indices = matched_indices[num_index.argsort()]
                            if not ascending:
                                matched_indices = matched_indices[::-1]
                        except Exception:
                            matched_indices = matched_indices.sort_values(ascending=ascending)
                    elif sort_by == 'genus':
                        if "Genus" in df_reg.columns:
                            sort_series = df_reg["Genus"].reindex(matched_indices).fillna("").astype(str)
                            matched_indices = matched_indices[sort_series.argsort()]
                            if not ascending:
                                matched_indices = matched_indices[::-1]
                    elif sort_by == 'cabinet':
                        sort_series = pd.Series(index=matched_indices, dtype=str)
                        if "Cabinet" in df_reg.columns:
                            sort_series = df_reg["Cabinet"].reindex(matched_indices)
                        if df_obs is not None and "Cabinet" in df_obs.columns:
                            sort_series = df_obs["Cabinet"].reindex(matched_indices).combine_first(sort_series)

                        sort_series = sort_series.fillna("").astype(str)
                        matched_indices = matched_indices[sort_series.argsort()]
                        if not ascending:
                            matched_indices = matched_indices[::-1]

                paged_indices = matched_indices[offset:offset + limit]

                objects = []
                for oid in paged_indices:
                    reg_row = df_reg.loc[oid]
                    genus = str(reg_row.get("Genus", "") or "")
                    species = str(reg_row.get("Species", "") or "")
                    family = str(reg_row.get("Family", "") or "")
                    author = str(reg_row.get("Author", "") or "")
                    sci_name = f"{genus} {species} {author}".strip() if (genus or species) else f"Specimen #{oid}"

                    rev_val = False
                    if rev_col and df_obs is not None and oid in df_obs.index:
                        v = str(df_obs.at[oid, rev_col]).strip().lower()
                        rev_val = v in ["true", "1", "yes"]

                    loc = {}
                    for lcol in ["Building", "Room", "Cabinet", "Shelf", "Drawer", "Box"]:
                        if df_obs is not None and lcol in df_obs.columns and oid in df_obs.index:
                            loc[lcol.lower()] = str(df_obs.at[oid, lcol] or "")
                        elif lcol in df_reg.columns:
                            loc[lcol.lower()] = str(reg_row.get(lcol, "") or "")

                    objects.append({
                        "id": str(oid),
                        "accession_number": str(oid),
                        "scientific_name": sci_name,
                        "genus": genus,
                        "species": species,
                        "family": family,
                        "location": loc,
                        "review_status": "reviewed" if rev_val else "pending",
                        "has_flags": False
                    })

            return jsonify({
                "total_matching": total_matching,
                "offset": offset,
                "limit": limit,
                "objects": objects,
                "facets": facets
            })

        @app.route('/api/object/<oid>', methods=['GET'])
        def get_object_detail(oid):
            if self.app_state.df_reg is None:
                return jsonify({"error": "No database loaded"}), 400

            oid = str(oid).strip()

            with self.app_state.df_lock:
                if oid not in self.app_state.df_reg.index:
                    return jsonify({"error": f"Object {oid} not found"}), 404

                reg_row = self.app_state.df_reg.loc[[oid]].copy()
                obs_row = None
                if self.app_state.df_obs is not None and oid in self.app_state.df_obs.index:
                    obs_row = self.app_state.df_obs.loc[[oid]].copy()

                photo_row = None
                if self.app_state.df_photo is not None and oid in self.app_state.df_photo.index:
                    photo_row = self.app_state.df_photo.loc[[oid]].copy()

            reg_dict = {}
            for col in reg_row.columns:
                val = reg_row.iloc[0][col]
                reg_dict[col] = str(val) if pd.notna(val) else ""

            obs_dict = {}
            if obs_row is not None:
                for col in obs_row.columns:
                    val = obs_row.iloc[0][col]
                    obs_dict[col] = str(val) if pd.notna(val) else ""

            genus = reg_dict.get("Genus", "")
            species = reg_dict.get("Species", "")
            author = reg_dict.get("Author", "")
            sci_name = f"{genus} {species} {author}".strip() if (genus or species) else f"Specimen #{oid}"

            rev_val = False
            if "Reviewed" in obs_dict:
                rev_val = str(obs_dict["Reviewed"]).strip().lower() in ["true", "1", "yes"]

            online_urls = []
            if self.app_state.config:
                pattern = self.app_state.config.get("image_url_pattern", "")
                if pattern:
                    online_urls.append(pattern.replace("{id}", oid))

            if not online_urls:
                padded = oid.zfill(4) if oid.isdigit() else oid
                online_urls.append(f"https://www.unimus.no/photos/image/jpeg/O-V-OE-{padded}.jpg")

            flagged_issues = []
            if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                for p_info in self.app_state.config["ui_sections"]["problems"]:
                    p_col = p_info["name"]
                    val = obs_dict.get(p_col, reg_dict.get(p_col, "")).strip().lower()
                    if val in ["true", "1", "yes", "x"]:
                        flagged_issues.append({
                            "id": p_col,
                            "field": p_info.get("label", p_col),
                            "severity": "warning",
                            "reason": p_info.get("label", p_col),
                            "resolved": False
                        })

            return jsonify({
                "id": str(oid),
                "accession_number": str(oid),
                "scientific_name": sci_name,
                "registration": reg_dict,
                "observation": obs_dict,
                "review_status": "reviewed" if rev_val else "pending",
                "flagged_issues": flagged_issues,
                "images": {
                    "preferred_source": "online",
                    "online_urls": online_urls,
                    "local_endpoints": [],
                    "photo_count": len(online_urls)
                }
            })

        @app.route('/api/update', methods=['POST'])
        def update_object():
            data = request.get_json(silent=True) or {}
            oid = str(data.get('id') or data.get('oid') or '').strip()
            if not oid:
                return jsonify({"error": "Missing object ID"}), 400

            reviewed = data.get('reviewed')
            updates = data.get('observation') or data.get('updates') or {}
            reg_updates = data.get('registration') or {}

            with self.app_state.df_lock:
                if self.app_state.df_reg is None or oid not in self.app_state.df_reg.index:
                    return jsonify({"error": f"Object {oid} not found in active database"}), 404

                # 1. Snapshot for Undo Stack
                old_reg = self.app_state.df_reg.loc[oid].to_dict()
                old_obs = self.app_state.df_obs.loc[oid].to_dict() if (self.app_state.df_obs is not None and oid in self.app_state.df_obs.index) else {}
                undo_snapshot = {
                    "oid": oid,
                    "reg": old_reg.copy(),
                    "obs": old_obs.copy(),
                    "timestamp": datetime.now().isoformat()
                }
                self.app_state.undo_stacks.setdefault(oid, []).append(undo_snapshot)
                if len(self.app_state.undo_stacks[oid]) > 20:
                    self.app_state.undo_stacks[oid].pop(0)

                changed_fields = []
                changed_values = []

                # 2. Apply registration updates
                for k, v in reg_updates.items():
                    if k in self.app_state.df_reg.columns:
                        old_v = sanitize_value(self.app_state.df_reg.at[oid, k])
                        new_v = sanitize_value(v)
                        if str(old_v) != str(new_v):
                            coerced = coerce_type(new_v, self.app_state.df_reg[k].dtype)
                            self.app_state.df_reg.at[oid, k] = coerced
                            changed_fields.append(k)
                            changed_values.append(f'{k}: "{old_v}" -> "{new_v}"')
                    else:
                        # Dynamic addition of new fields to df_reg if they don't exist
                        new_v = sanitize_value(v)
                        if new_v:
                            self.app_state.df_reg[k] = pd.Series(dtype="object")
                            self.app_state.df_reg.at[oid, k] = new_v
                            changed_fields.append(k)
                            changed_values.append(f'{k}: "" -> "{new_v}"')

                # 3. Apply observation updates
                if self.app_state.df_obs is not None and oid in self.app_state.df_obs.index:
                    for k, v in updates.items():
                        if k in self.app_state.df_obs.columns:
                            old_v = sanitize_value(self.app_state.df_obs.at[oid, k])
                            new_v = sanitize_value(v)
                            if str(old_v) != str(new_v):
                                coerced = coerce_type(new_v, self.app_state.df_obs[k].dtype)
                                self.app_state.df_obs.at[oid, k] = coerced
                                changed_fields.append(k)
                                changed_values.append(f'{k}: "{old_v}" -> "{new_v}"')
                        elif k in self.app_state.df_reg.columns and k not in reg_updates:
                            old_v = sanitize_value(self.app_state.df_reg.at[oid, k])
                            new_v = sanitize_value(v)
                            if str(old_v) != str(new_v):
                                coerced = coerce_type(new_v, self.app_state.df_reg[k].dtype)
                                self.app_state.df_reg.at[oid, k] = coerced
                                changed_fields.append(k)
                                changed_values.append(f'{k}: "{old_v}" -> "{new_v}"')
                        else:
                            # Dynamic addition of new fields to df_obs if they don't exist
                            new_v = sanitize_value(v)
                            if new_v:
                                # Ensure column exists first in df_obs
                                self.app_state.df_obs[k] = pd.Series(dtype="object")
                                self.app_state.df_obs.at[oid, k] = new_v
                                changed_fields.append(k)
                                changed_values.append(f'{k}: "" -> "{new_v}"')

                # 4. Handle Reviewed Status
                action_name = "EDIT"
                is_rev_str = ""
                if reviewed is not None:
                    is_reviewed_bool = bool(reviewed)
                    is_rev_str = "Yes" if is_reviewed_bool else "No"
                    action_name = "REVIEWED" if is_reviewed_bool else "NOT_REVIEWED"
                    if self.app_state.df_obs is not None and oid in self.app_state.df_obs.index:
                        if "Reviewed" in self.app_state.df_obs.columns:
                            self.app_state.df_obs.at[oid, "Reviewed"] = is_reviewed_bool
                        if "ReviewedAt" in self.app_state.df_obs.columns:
                            self.app_state.df_obs.at[oid, "ReviewedAt"] = datetime.now().isoformat(timespec="seconds")
                        changed_fields.append("Reviewed")

                # 5. Append / Merge Log Record
                if not hasattr(self.app_state, "_log_records") or self.app_state._log_records is None:
                    self.app_state._log_records = []

                now_ts = datetime.now().isoformat(timespec="seconds")
                log_entry = {
                    "Timestamp": now_ts,
                    "Action": action_name,
                    "Reviewed": is_rev_str,
                    "ObjectID": oid,
                    "ChangedFields": ", ".join(changed_fields) if changed_fields else "(no changes)",
                    "ChangedValues": " | ".join(changed_values),
                    "ProblemsChanged": "",
                    "ProblemsChangedValues": "",
                    "LocationChanged": "",
                    "LocationChangedValues": "",
                    "User": "Mobile-Companion",
                    "SourceFile": os.path.basename(self.app_state.excel_path or ""),
                    "OutputFile": os.path.basename(self.app_state.output_path or self.app_state.excel_path or "")
                }
                self.app_state._log_records.append(log_entry)
                self.app_state.df_log = pd.DataFrame(self.app_state._log_records)

                # 6. Flag Application Dirty
                self.app_state.dirty = True

                # 7. Record Recent Edit in Server
                edit_summary = f"#{oid}: {', '.join(changed_fields)}" if changed_fields else f"#{oid} updated"
                self.recent_edits.insert(0, {
                    "oid": oid,
                    "summary": edit_summary,
                    "time": datetime.now().strftime("%H:%M:%S")
                })
                if len(self.recent_edits) > 20:
                    self.recent_edits.pop()

            # 8. Notify desktop UI
            if self.on_edit_callback:
                try:
                    self.on_edit_callback(oid, edit_summary)
                except Exception as e:
                    pass

            if self.root_tk:
                try:
                    self.app_state._mobile_last_edited_oid = oid
                    self.root_tk.event_generate("<<MobileEdit>>", when="tail")
                except Exception as e:
                    pass

            return jsonify({
                "success": True,
                "id": str(oid),
                "review_status": "reviewed" if reviewed else "pending",
                "synced_at": datetime.now().isoformat()
            })

        @app.route('/api/object/<oid>/photo', methods=['POST'])
        def attach_photo(oid):
            if self.app_state.df_reg is None:
                return jsonify({"error": "No database loaded"}), 400

            oid = str(oid).strip()

            if 'image' not in request.files and 'file' not in request.files:
                return jsonify({"error": "No image payload found"}), 400

            file = request.files.get('image') or request.files.get('file')
            if file.filename == '':
                return jsonify({"error": "Empty filename"}), 400

            caption = request.form.get('caption', '').strip()
            category = request.form.get('category', '').strip()

            with self.app_state.df_lock:
                if oid not in self.app_state.df_reg.index:
                    return jsonify({"error": f"Object {oid} not found"}), 404

            if self.app_state.excel_path:
                db_folder = os.path.dirname(self.app_state.excel_path)
            else:
                db_folder = os.getcwd()
            photos_dir = os.path.join(db_folder, "photos")
            os.makedirs(photos_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_filename = secure_filename(file.filename)
            _, ext = os.path.splitext(original_filename)
            if not ext:
                ext = ".jpg"

            new_filename = f"{oid}_{timestamp}{ext}"
            file_path = os.path.join(photos_dir, new_filename)

            try:
                file.save(file_path)
            except Exception as e:
                debug_error("Photo Upload Error", str(e))
                return jsonify({"error": "Failed to save image"}), 500

            with self.app_state.df_lock:
                if getattr(self.app_state, 'df_photo', None) is None:
                    # Depending on how it's structured, standard columns are generic
                    self.app_state.df_photo = pd.DataFrame(columns=["PhotoPath", "FileName", "Caption", "Timestamp"])
                    self.app_state.df_photo.index.name = "ObjectID"

                # Check for what columns exist
                cols = self.app_state.df_photo.columns.tolist()
                new_row = {}
                for c in cols:
                    new_row[c] = ""

                # Use user's requested columns
                if "PhotoPath" in cols or "FileName" in cols or "Caption" in cols or "Timestamp" in cols:
                    # It's an empty schema or already matching our requested schema
                    pass
                else:
                    # Let's add them to columns if they don't exist
                    for c in ["PhotoPath", "FileName", "Caption", "Timestamp"]:
                        if c not in self.app_state.df_photo.columns:
                            self.app_state.df_photo[c] = ""

                new_row["PhotoPath"] = file_path
                new_row["FileName"] = new_filename
                new_row["Caption"] = caption
                new_row["Timestamp"] = timestamp
                if category and "Category" in self.app_state.df_photo.columns:
                    new_row["Category"] = category
                elif category:
                    self.app_state.df_photo["Category"] = ""
                    new_row["Category"] = category

                new_df = pd.DataFrame([new_row], index=[oid])
                new_df.index.name = self.app_state.df_photo.index.name or "ObjectID"

                self.app_state.df_photo = pd.concat([self.app_state.df_photo, new_df])

                if not hasattr(self.app_state, "_log_records") or self.app_state._log_records is None:
                    self.app_state._log_records = []

                now_ts = datetime.now().isoformat(timespec="seconds")
                log_entry = {
                    "Timestamp": now_ts,
                    "Action": "PHOTO_ADDED",
                    "Reviewed": "",
                    "ObjectID": oid,
                    "ChangedFields": "Photo",
                    "ChangedValues": f"Added {new_filename}",
                    "ProblemsChanged": "",
                    "ProblemsChangedValues": "",
                    "LocationChanged": "",
                    "LocationChangedValues": "",
                    "User": "Mobile-Companion",
                    "SourceFile": os.path.basename(self.app_state.excel_path or ""),
                    "OutputFile": os.path.basename(self.app_state.output_path or self.app_state.excel_path or "")
                }
                self.app_state._log_records.append(log_entry)
                self.app_state.df_log = pd.DataFrame(self.app_state._log_records)

                self.app_state.dirty = True

            return jsonify({
                "success": True,
                "photo_id": new_filename,
                "filename": new_filename,
                "url": f"/api/photo/{new_filename}"
            }), 201



        @app.route('/api/batch_update', methods=['POST'])
        def batch_update_objects():
            data = request.get_json(silent=True) or {}
            updates_list = data.get('updates')
            if not updates_list or not isinstance(updates_list, list):
                return jsonify({"error": "Missing or invalid 'updates' array"}), 400

            updated_ids = []

            with self.app_state.df_lock:
                if self.app_state.df_reg is None:
                    return jsonify({"error": "No database loaded"}), 400

                for update in updates_list:
                    oid = str(update.get('id') or update.get('oid') or '').strip()
                    if not oid or oid not in self.app_state.df_reg.index:
                        continue

                    reviewed = update.get('reviewed')
                    obs_updates = update.get('observation') or {}
                    reg_updates = update.get('registration') or {}

                    # 1. Snapshot for Undo Stack
                    old_reg = self.app_state.df_reg.loc[oid].to_dict()
                    old_obs = self.app_state.df_obs.loc[oid].to_dict() if (self.app_state.df_obs is not None and oid in self.app_state.df_obs.index) else {}
                    undo_snapshot = {
                        "oid": oid,
                        "reg": old_reg.copy(),
                        "obs": old_obs.copy(),
                        "timestamp": datetime.now().isoformat()
                    }
                    self.app_state.undo_stacks.setdefault(oid, []).append(undo_snapshot)
                    if len(self.app_state.undo_stacks[oid]) > 20:
                        self.app_state.undo_stacks[oid].pop(0)

                    changed_fields = []
                    changed_values = []

                    # 2. Apply registration updates
                    for k, v in reg_updates.items():
                        if k in self.app_state.df_reg.columns:
                            old_v = sanitize_value(self.app_state.df_reg.at[oid, k])
                            new_v = sanitize_value(v)
                            if str(old_v) != str(new_v):
                                coerced = coerce_type(new_v, self.app_state.df_reg[k].dtype)
                                self.app_state.df_reg.at[oid, k] = coerced
                                changed_fields.append(k)
                                changed_values.append(f'{k}: "{old_v}" -> "{new_v}"')

                    # 3. Apply observation updates
                    if self.app_state.df_obs is not None and oid in self.app_state.df_obs.index:
                        for k, v in obs_updates.items():
                            if k in self.app_state.df_obs.columns:
                                old_v = sanitize_value(self.app_state.df_obs.at[oid, k])
                                new_v = sanitize_value(v)
                                if str(old_v) != str(new_v):
                                    coerced = coerce_type(new_v, self.app_state.df_obs[k].dtype)
                                    self.app_state.df_obs.at[oid, k] = coerced
                                    changed_fields.append(k)
                                    changed_values.append(f'{k}: "{old_v}" -> "{new_v}"')
                            elif k in self.app_state.df_reg.columns and k not in reg_updates:
                                old_v = sanitize_value(self.app_state.df_reg.at[oid, k])
                                new_v = sanitize_value(v)
                                if str(old_v) != str(new_v):
                                    coerced = coerce_type(new_v, self.app_state.df_reg[k].dtype)
                                    self.app_state.df_reg.at[oid, k] = coerced
                                    changed_fields.append(k)
                                    changed_values.append(f'{k}: "{old_v}" -> "{new_v}"')

                    # 4. Handle Reviewed Status
                    action_name = "EDIT"
                    is_rev_str = ""
                    if reviewed is not None:
                        is_reviewed_bool = bool(reviewed)
                        is_rev_str = "Yes" if is_reviewed_bool else "No"
                        action_name = "REVIEWED" if is_reviewed_bool else "NOT_REVIEWED"
                        if self.app_state.df_obs is not None and oid in self.app_state.df_obs.index:
                            if "Reviewed" in self.app_state.df_obs.columns:
                                self.app_state.df_obs.at[oid, "Reviewed"] = is_reviewed_bool
                            if "ReviewedAt" in self.app_state.df_obs.columns:
                                self.app_state.df_obs.at[oid, "ReviewedAt"] = datetime.now().isoformat(timespec="seconds")
                            changed_fields.append("Reviewed")

                    # 5. Append / Merge Log Record
                    if not hasattr(self.app_state, "_log_records") or self.app_state._log_records is None:
                        self.app_state._log_records = []

                    now_ts = datetime.now().isoformat(timespec="seconds")
                    log_entry = {
                        "Timestamp": now_ts,
                        "Action": action_name,
                        "Reviewed": is_rev_str,
                        "ObjectID": oid,
                        "ChangedFields": ", ".join(changed_fields) if changed_fields else "(no changes)",
                        "ChangedValues": " | ".join(changed_values),
                        "ProblemsChanged": "",
                        "ProblemsChangedValues": "",
                        "LocationChanged": "",
                        "LocationChangedValues": "",
                        "User": "Mobile-Companion",
                        "SourceFile": os.path.basename(self.app_state.excel_path or ""),
                        "OutputFile": os.path.basename(self.app_state.output_path or self.app_state.excel_path or "")
                    }
                    self.app_state._log_records.append(log_entry)

                    # 7. Record Recent Edit in Server
                    edit_summary = f"#{oid}: {', '.join(changed_fields)}" if changed_fields else f"#{oid} updated"
                    self.recent_edits.insert(0, {
                        "oid": oid,
                        "summary": edit_summary,
                        "time": datetime.now().strftime("%H:%M:%S")
                    })
                    if len(self.recent_edits) > 20:
                        self.recent_edits.pop()

                    updated_ids.append(oid)

                if updated_ids:
                    self.app_state.df_log = pd.DataFrame(self.app_state._log_records)
                    self.app_state.dirty = True

            if not updated_ids:
                return jsonify({"success": True, "updated_count": 0, "updated_ids": []})

            # 8. Notify desktop UI
            if self.on_edit_callback:
                try:
                    self.on_edit_callback("BATCH", f"Batch updated {len(updated_ids)} records")
                except Exception as e:
                    pass

            if self.root_tk:
                try:
                    self.app_state._mobile_last_edited_oid = updated_ids[-1]
                    self.root_tk.event_generate("<<MobileEdit>>", when="tail")
                except Exception as e:
                    pass

            return jsonify({
                "success": True,
                "updated_count": len(updated_ids),
                "updated_ids": updated_ids
            })


LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Arbor Companion Login</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
</head>
<body class="bg-[#121915] text-[#1c241f] min-h-screen flex items-center justify-center p-4 antialiased">
  <div class="w-full max-w-sm bg-white rounded-2xl p-6 shadow-2xl border border-emerald-900/20 text-center space-y-4">
    <div class="w-12 h-12 rounded-full bg-emerald-100 text-[#2d6a4f] text-2xl mx-auto flex items-center justify-center">🌿</div>
    <div>
      <h1 class="text-lg font-bold text-[#1c241f]">Arbor Mobile Companion</h1>
      <p class="text-xs text-[#5a655e]">Enter the 4-digit PIN displayed on your laptop screen</p>
    </div>
    {% if error %}
    <div class="bg-red-50 text-red-700 text-xs font-semibold py-2 px-3 rounded-md border border-red-200">{{ error }}</div>
    {% endif %}
    <form method="POST" action="/login" class="space-y-3">
      <input type="password" name="pin" maxlength="6" inputmode="numeric" placeholder="• • • •" autofocus required
             class="w-full text-center tracking-widest text-2xl font-mono py-2.5 bg-neutral-50 border border-neutral-300 rounded-lg focus:outline-none focus:border-[#2d6a4f] focus:ring-1 focus:ring-[#2d6a4f]">
      <button type="submit" class="w-full bg-[#2d6a4f] hover:bg-[#1b4332] text-white py-2.5 rounded-lg font-bold text-sm transition">
        Connect to Database
      </button>
    </form>
  </div>
</body>
</html>"""


INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Arbor Mobile Companion</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            fern: {
              DEFAULT: '#3a7d44',
              dark: '#2c6034',
              light: '#eff7f1',
              border: '#a4cca9'
            },
            ember: {
              DEFAULT: '#d95c14',
              dark: '#b84a0c',
              light: '#fff3ec',
              border: '#f8c2a3'
            },
            canvas: '#f3f3f3',
            surface: '#ffffff',
            tonal1: '#f8f9fa',
            tonal2: '#eceeec',
            tonal3: '#dfe3e0',
            bordercol: '#d4d8d5',
            borderdark: '#b3b9b4',
            ink: {
              DEFAULT: '#191e1a',
              muted: '#535d56',
              faint: '#848f87'
            }
          },
          fontFamily: {
            sans: ['Inter', 'sans-serif'],
            serif: ['Lora', 'serif'],
            mono: ['JetBrains Mono', 'monospace'],
          }
        }
      }
    }
  </script>
  <style>
    .touch-min { min-height: 44px; }
    .touch-press:active { transform: scale(0.985); }
    /* Accordion icon rotation */
    .acc-open .acc-icon { transform: rotate(180deg); }
  </style>
</head>
<body class="bg-canvas text-ink min-h-screen antialiased select-none">
  
  <div class="w-full h-screen flex flex-col relative overflow-hidden bg-canvas mx-auto max-w-md border-x border-bordercol shadow-xl">
    
    <!-- Top Status Bar -->
    <div class="bg-fern-dark text-white px-4 py-2 flex items-center justify-between text-xs font-mono">
      <div class="flex items-center gap-1.5 font-bold">
        <span class="inline-block w-2 h-2 rounded-full bg-fern-border animate-pulse"></span>
        <span id="headerDbName">Herbarium Database</span>
      </div>
      <div class="flex items-center gap-2 text-[11px] text-fern-light">
        <span id="syncStatusBadge">⚡ Connected</span>
      </div>
    </div>

    <!-- Header Navigation -->
    <header class="bg-fern text-white px-4 py-3 flex items-center justify-between shadow-md z-10">
      <div class="flex items-center gap-2">
        <div id="backButton" class="hidden mr-2 bg-fern-dark/50 hover:bg-fern-dark px-2 py-1 rounded cursor-pointer touch-press" onclick="showListView()">
          <span class="font-bold text-lg">&lt;</span>
        </div>
        <div class="bg-white text-fern rounded font-bold px-1.5 py-0.5 text-xs">A</div>
        <div>
          <h1 class="font-bold text-sm tracking-tight leading-tight font-sans">Arbor Companion</h1>
          <p class="text-[10px] text-fern-light/80 font-mono" id="headerCount">Vault #04 • Linnaean Botanical</p>
        </div>
      </div>
    </header>

    <!-- Toast Notification Overlay -->
    <div id="toast" class="hidden absolute top-16 left-4 right-4 bg-fern-dark text-white text-xs font-bold py-3 px-4 rounded-lg shadow-lg text-center z-50 transition-all opacity-95">
      Edits saved & synchronized
    </div>

    <!-- VIEW: LIST -->
    <main id="listView" class="flex-1 flex flex-col h-full bg-canvas overflow-hidden">
      <!-- Search Bar -->
      <div class="bg-surface px-4 py-3 border-b border-bordercol shadow-sm z-10">
        <div class="relative flex">
          <span class="absolute inset-y-0 left-0 pl-3 flex items-center text-ink-muted">🔍</span>
          <input id="searchBox" type="text" placeholder="Search botanical name, ID, collector, cabinet..." onkeyup="debounceSearch()"
                 class="w-full bg-surface border border-bordercol rounded-md pl-9 pr-3 py-2 text-sm text-ink focus:outline-none focus:border-fern focus:ring-1 focus:ring-fern font-sans">
        </div>
      </div>

      <!-- List Header -->
      <div class="px-4 py-2 flex items-center justify-between bg-canvas border-b border-bordercol">
        <span id="listSummary" class="text-xs text-ink-muted font-mono">Showing 0 of 0 specimens</span>
        <div class="flex items-center gap-2 text-xs text-ink-muted">
          <span>Sort by:</span>
          <select class="bg-surface border border-bordercol rounded px-2 py-1 focus:outline-none focus:border-fern text-ink">
            <option>Scientific Name (A-Z)</option>
          </select>
        </div>
      </div>

      <!-- Scrollable List -->
      <div id="specimenListContainer" class="flex-1 overflow-y-auto p-3 space-y-3 pb-24">
        <!-- List items populated here -->
      </div>
    </main>

    <!-- VIEW: DETAIL -->
    <main id="detailView" class="hidden flex-1 flex flex-col h-full overflow-hidden bg-canvas relative">
      <!-- Detail Header (Fixed) -->
      <div class="bg-surface border-b border-bordercol p-4 shadow-sm z-10 shrink-0">
        <div class="flex items-center justify-between mb-1">
           <span class="font-mono text-sm font-bold text-ink" id="detailAccession"></span>
           <span class="text-xs text-ink-muted font-sans" id="detailTopLocation"></span>
        </div>
        <h2 id="detailScientificName" class="font-serif italic text-2xl font-bold text-ink mb-1"></h2>
        <div class="text-sm font-sans text-ink-muted">
           <span id="detailAuthor" class="font-bold text-ink"></span> • <span id="detailFamily"></span> • <span id="detailCommonName" class="italic"></span>
        </div>
      </div>

      <!-- Scrollable Detail Content -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4 pb-32">

        <!-- Photo Plate Card -->
        <div class="bg-surface rounded-md border border-bordercol shadow-sm overflow-hidden">
          <div class="p-3 border-b border-bordercol flex items-center justify-between">
            <span class="text-sm font-bold font-sans text-ink">Attached Archival Scans (1)</span>
            <button class="text-xs text-fern font-semibold hover:underline touch-press" onclick="loadImage()">↗ Inspect Scan</button>
          </div>
          <div id="imagePlaceholder" class="p-8 text-center bg-tonal1 flex flex-col items-center justify-center gap-2 cursor-pointer hover:bg-tonal2 transition" onclick="loadImage()">
            <div class="w-12 h-12 rounded-full bg-fern-light text-fern flex items-center justify-center text-xl shadow-sm">📷</div>
            <div>
              <p class="text-sm font-bold text-fern">Tap to Load Specimen Plate</p>
              <p class="text-xs text-ink-muted mt-1">Loads directly from cloud CDN (0 laptop bandwidth)</p>
            </div>
          </div>
          <div id="imageContainer" class="hidden relative bg-ink flex items-center justify-center p-2 min-h-[250px]">
            <img id="specimenImg" src="" alt="Specimen Plate" class="max-h-80 w-auto object-contain mx-auto">
          </div>
        </div>

        <!-- Accordion 1: Taxonomy -->
        <div class="bg-surface rounded-md border border-bordercol shadow-sm overflow-hidden accordion">
          <button class="w-full p-3 flex items-center justify-between bg-tonal1 hover:bg-tonal2 transition focus:outline-none touch-press acc-header" onclick="toggleAcc(this)">
             <div class="flex items-center gap-3">
               <span class="text-lg">🧬</span>
               <div class="text-left">
                 <h3 class="font-bold text-sm text-ink">Taxonomy & Scientific Name</h3>
                 <p class="text-xs text-ink-muted">Linnaean classification, determination author & qualifier</p>
               </div>
             </div>
             <span class="acc-icon text-ink-muted font-bold transition-transform duration-200">^</span>
          </button>
          <div class="p-4 space-y-4 acc-content block border-t border-bordercol">

             <!-- Botanical Binomial -->
             <div>
               <div class="flex items-center justify-between mb-1">
                 <label class="text-xs font-bold text-ink">Botanical / Scientific Binomial *</label>
                 <span class="text-[10px] text-ink-muted font-medium">⚑ Flag discrepancy</span>
               </div>
               <input id="inputBinomial" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink font-serif italic focus:outline-none focus:border-fern" onchange="autoSave()">
             </div>

             <div class="grid grid-cols-2 gap-3">
               <div>
                 <label class="text-xs font-bold text-ink block mb-1">Taxon Author</label>
                 <input id="inputAuthor" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
               </div>
               <div>
                 <label class="text-xs font-bold text-ink block mb-1">Common Name</label>
                 <input id="inputCommonName" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
               </div>
             </div>

             <div>
                <h4 class="text-[10px] font-mono font-bold text-ink-muted uppercase tracking-wider mb-2 mt-4 border-b border-bordercol pb-1">Darwin Core Classification Ranks</h4>
                <div class="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Family</label>
                    <input id="inputFamily" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
                  </div>
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Genus</label>
                    <input id="inputGenus" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink font-serif italic focus:outline-none focus:border-fern" onchange="autoSave()">
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Order</label>
                    <input id="inputOrder" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
                  </div>
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Class / Phylum</label>
                    <input id="inputClass" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
                  </div>
                </div>
             </div>

             <!-- Identification status placeholder block from mock -->
             <div class="border border-ember-border bg-ember-light p-3 rounded mt-4">
                <div class="flex items-center justify-between mb-2">
                   <h4 class="text-xs font-bold text-ember-dark">Identification Qualifier / Status</h4>
                   <span class="text-[10px] text-ember-dark border border-ember-border bg-white px-2 py-0.5 rounded">Flagged for re-examination</span>
                </div>
                <div class="border-l-2 border-ember pl-2 mb-3">
                   <p class="text-sm font-semibold text-ember-dark">Requires re-examination</p>
                </div>
                <div class="bg-white border border-ember-border p-2 rounded flex items-start gap-2 text-xs">
                   <span class="text-ember">⚠</span>
                   <p class="text-ember-dark flex-1">Curator note: Check whether specimen might be Adansonia za var. bozy based on calyx dimensions.</p>
                   <button class="border border-ember-dark text-ember-dark font-bold px-2 py-1 rounded bg-white hover:bg-ember-light touch-press">Resolve</button>
                </div>
             </div>

             <div class="grid grid-cols-2 gap-3">
               <div>
                 <label class="text-xs font-bold text-ink block mb-1">Determined By</label>
                 <input id="inputDeterminedBy" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
               </div>
               <div>
                 <label class="text-xs font-bold text-ink block mb-1">Date Determined</label>
                 <input id="inputDateDetermined" type="text" placeholder="DD.MM.YYYY" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern font-mono" onchange="autoSave()">
               </div>
             </div>

          </div>
        </div>


        <!-- Accordion 2: Collection & Specimen -->
        <div class="bg-surface rounded-md border border-bordercol shadow-sm overflow-hidden accordion acc-open">
          <button class="w-full p-3 flex items-center justify-between bg-tonal1 hover:bg-tonal2 transition focus:outline-none touch-press acc-header border-b border-bordercol" onclick="toggleAcc(this)">
             <div class="flex items-center gap-3">
               <span class="text-lg">📦</span>
               <div class="text-left">
                 <h3 class="font-bold text-sm text-ink">Collection & Specimen Metadata</h3>
                 <p class="text-xs text-ink-muted">Physical vault location, field collector, GPS & preparation</p>
               </div>
             </div>
             <span class="acc-icon text-ink-muted font-bold transition-transform duration-200">^</span>
          </button>
          <div class="p-4 space-y-4 acc-content block">

             <div>
                <div class="flex items-center justify-between mb-2">
                   <h4 class="text-[10px] font-mono font-bold text-ink-muted uppercase tracking-wider">Museum Physical Storage Coordinates</h4>
                   <span class="text-[10px] text-fern-dark border border-fern-border bg-white px-2 py-0.5 rounded font-mono">Tagged Unit</span>
                </div>
                <div class="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Cabinet</label>
                    <input id="inputCabinet" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern font-mono" onchange="autoSave()">
                  </div>
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Drawer / Unit Tray</label>
                    <input id="inputShelf" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern font-mono" onchange="autoSave()">
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Room & Building</label>
                    <input id="inputRoom" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
                  </div>
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Barcode String</label>
                    <input id="inputBarcode" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern font-mono" onchange="autoSave()">
                  </div>
                </div>
             </div>

             <div class="mt-6 border-t border-bordercol pt-4">
                <h4 class="text-[10px] font-mono font-bold text-ink-muted uppercase tracking-wider mb-2">Historical Field Collection Data</h4>
                <div class="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Collector Name</label>
                    <input id="inputCollector" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
                  </div>
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Field Number</label>
                    <input id="inputFieldNumber" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern font-mono" onchange="autoSave()">
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Collection Date</label>
                    <input id="inputCollectionDate" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern font-mono" onchange="autoSave()">
                  </div>
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Country / Province</label>
                    <input id="inputCountry" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
                  </div>
                </div>
                <div class="mb-3">
                  <label class="text-xs font-medium text-ink-muted block mb-1">Specific Locality</label>
                  <textarea id="inputLocality" rows="2" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()"></textarea>
                </div>

                <label class="text-xs font-medium text-ink-muted block mb-1">Decimal GPS Coordinates (Technical Monospace)</label>
                <div class="grid grid-cols-2 gap-3 mb-3">
                  <input id="inputLat" type="text" placeholder="Latitude" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern font-mono" onchange="autoSave()">
                  <input id="inputLon" type="text" placeholder="Longitude" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern font-mono" onchange="autoSave()">
                </div>

                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Elevation</label>
                    <input id="inputElevation" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern font-mono" onchange="autoSave()">
                  </div>
                  <div>
                    <label class="text-xs font-medium text-ink-muted block mb-1">Habitat / Ecology</label>
                    <input id="inputHabitat" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
                  </div>
                </div>
             </div>

             <div class="mt-6 border-t border-bordercol pt-4">
                <h4 class="text-[10px] font-mono font-bold text-ink-muted uppercase tracking-wider mb-2">Preservation & Physical Condition</h4>
                <div class="mb-3">
                  <label class="text-xs font-medium text-ink-muted block mb-1">Preparation Type</label>
                  <input id="inputPreparation" type="text" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
                </div>
                <div class="mb-3">
                  <label class="text-xs font-medium text-ink-muted block mb-1">Condition Grade</label>
                  <select id="inputCondition" class="w-full bg-surface border border-bordercol rounded px-3 py-2 text-sm text-ink focus:outline-none focus:border-fern" onchange="autoSave()">
                     <option value="">Select Condition</option>
                     <option value="Pristine">Pristine (No Damage)</option>
                     <option value="Good">Good (Stable)</option>
                     <option value="Fair">Fair (Minor Degradation)</option>
                     <option value="Fragile">Fragile (Needs Support)</option>
                     <option value="Severe">Severe (Urgent Repair)</option>
                  </select>
                </div>

                <div class="bg-tonal1 border border-bordercol p-3 rounded">
                  <label class="text-xs font-medium text-ink-muted block mb-2">Phenology Traits Visible on Sheet:</label>
                  <div class="flex items-center gap-4">
                    <label class="flex items-center gap-1.5 text-sm text-ink touch-press"><input type="checkbox" id="checkFlower" class="w-4 h-4 text-fern" onchange="autoSave()"> Flower / Inflorescence</label>
                    <label class="flex items-center gap-1.5 text-sm text-ink touch-press"><input type="checkbox" id="checkFruit" class="w-4 h-4 text-fern" onchange="autoSave()"> Fruit / Cone</label>
                    <label class="flex items-center gap-1.5 text-sm text-ink touch-press"><input type="checkbox" id="checkBuds" class="w-4 h-4 text-fern" onchange="autoSave()"> Buds</label>
                  </div>
                </div>
             </div>

          </div>
        </div>

      </div>

      <!-- Detail Sticky Footer (Floating / Fixed to Bottom of Screen) -->
      <footer class="absolute bottom-0 w-full bg-surface/95 backdrop-blur border-t border-bordercol p-3 flex flex-col gap-2 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-20">
         <div class="flex items-center justify-between px-1">
            <div class="flex items-center gap-2">
               <span class="inline-block w-2.5 h-2.5 rounded-full bg-fern"></span>
               <span class="text-xs font-mono text-ink-muted font-bold">Desktop Host Linked (14ms)</span>
            </div>
            <button class="text-xs font-bold text-ember touch-press">⚠ Discrepancy Open</button>
         </div>
         <div class="flex items-center gap-2">
           <button id="btnReviewed" onclick="toggleReviewed()" class="flex-1 bg-surface border-2 border-bordercol text-ink hover:bg-tonal1 px-4 py-3 rounded-md font-bold text-sm flex items-center justify-center gap-2 touch-min touch-press transition">
             <span class="text-fern-dark">✓</span> <span>Mark Reviewed</span>
           </button>
         </div>
      </footer>
    </main>

  </div>

  <script>
    const TOKEN = "{{ token }}";
    let currentOid = null;
    let currentRecord = null;
    let isReviewed = false;
    let objectList = [];

    // Auto-save debounce timer
    let saveTimeout = null;

    async function apiFetch(url, options = {}) {
      options.headers = options.headers || {};
      options.headers['X-Session-Token'] = TOKEN;
      options.headers['Content-Type'] = 'application/json';
      const sep = url.includes('?') ? '&' : '?';
      const res = await fetch(`${url}${sep}token=${encodeURIComponent(TOKEN)}`, options);
      return res.json();
    }

    function showToast(msg) {
      const toast = document.getElementById('toast');
      toast.textContent = msg;
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 2500);
    }

    function toggleAcc(btn) {
       const acc = btn.closest('.accordion');
       acc.classList.toggle('acc-open');
       const content = acc.querySelector('.acc-content');
       if (acc.classList.contains('acc-open')) {
           content.classList.remove('hidden');
       } else {
           content.classList.add('hidden');
       }
    }

    async function init() {
      try {
        const status = await apiFetch('/api/status');
        document.getElementById('headerDbName').textContent = status.database_name || 'Arbor Database';
        document.getElementById('headerCount').textContent = `${status.reviewed_count} / ${status.total_objects} reviewed`;

        await fetchList();
      } catch (err) {
        console.error("Init failed:", err);
      }
    }

    let searchDebounce = null;
    function debounceSearch() {
       clearTimeout(searchDebounce);
       searchDebounce = setTimeout(fetchList, 300);
    }

    async function fetchList() {
      const q = document.getElementById('searchBox').value.trim();
      const objRes = await apiFetch(`/api/objects?limit=50&q=${encodeURIComponent(q)}`);
      objectList = objRes.objects || [];
      document.getElementById('listSummary').textContent = `Showing ${objectList.length} of ${objRes.total_matching} specimens`;
      renderList();
    }

    function renderList() {
      const container = document.getElementById('specimenListContainer');
      if (objectList.length === 0) {
          container.innerHTML = `<div class="p-4 text-center text-ink-muted text-sm border border-dashed border-bordercol rounded bg-surface">No specimens found.</div>`;
          return;
      }

      container.innerHTML = objectList.map(o => {
          let badge = '';
          if (o.review_status === 'reviewed') {
              badge = `<span class="bg-fern-light text-fern-dark border border-fern-border px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1">✓ Reviewed</span>`;
          } else {
              badge = `<span class="bg-surface border border-bordercol text-ink-muted px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1">🕒 Pending</span>`;
          }

          let subtext = [];
          if (o.location.cabinet && o.location.cabinet !== 'nan') subtext.push(`Cab ${o.location.cabinet}`);
          if (o.location.drawer && o.location.drawer !== 'nan') subtext.push(`Drw ${o.location.drawer}`);
          else if (o.location.shelf && o.location.shelf !== 'nan') subtext.push(`Shf ${o.location.shelf}`);

          return `
          <div onclick="loadObject('${o.id}')" class="bg-surface rounded-md border-l-4 border-l-fern border-y border-r border-bordercol shadow-sm p-3 hover:bg-tonal1 cursor-pointer touch-press transition">
             <div class="flex items-start justify-between mb-2">
                 <div class="flex items-center gap-2">
                     <span class="font-mono text-[10px] bg-tonal1 border border-bordercol text-ink px-1.5 py-0.5 rounded font-bold">${o.accession_number}</span>
                 </div>
                 ${badge}
             </div>
             <h3 class="font-serif italic font-bold text-ink text-base mb-1">${o.scientific_name}</h3>
             <p class="text-xs text-ink-muted font-sans">${o.family || 'Unknown Family'}</p>
             <div class="mt-2 pt-2 border-t border-tonal2 flex justify-between items-center text-[10px] text-ink-muted font-mono">
                 <div class="flex items-center gap-1">📍 ${subtext.join(' / ') || 'Location unknown'}</div>
                 <div>📅 --</div>
             </div>
          </div>
          `;
      }).join('');
    }

    function showListView() {
       document.getElementById('detailView').classList.add('hidden');
       document.getElementById('listView').classList.remove('hidden');
       document.getElementById('backButton').classList.add('hidden');
       // Refresh list in case of changes
       fetchList();
    }

    function showDetailView() {
       document.getElementById('listView').classList.add('hidden');
       document.getElementById('detailView').classList.remove('hidden');
       document.getElementById('backButton').classList.remove('hidden');
    }

    function setVal(id, val) {
       const el = document.getElementById(id);
       if(el) el.value = val || '';
    }

    function setCheck(id, val) {
       const el = document.getElementById(id);
       if(el) el.checked = (String(val).toLowerCase() === 'true' || val === true || val === '1' || val === 'yes');
    }

    async function loadObject(oid) {
      currentOid = oid;
      showDetailView();

      document.getElementById('imagePlaceholder').classList.remove('hidden');
      document.getElementById('imageContainer').classList.add('hidden');
      document.getElementById('specimenImg').src = '';

      // Reset scroll position to top
      document.querySelector('#detailView .flex-1.overflow-y-auto').scrollTop = 0;

      try {
        const data = await apiFetch(`/api/object/${encodeURIComponent(oid)}`);
        currentRecord = data;
        
        // Header
        document.getElementById('detailAccession').textContent = data.accession_number;
        document.getElementById('detailScientificName').textContent = data.scientific_name;
        document.getElementById('detailAuthor').textContent = data.registration.Author || '';
        document.getElementById('detailFamily').textContent = data.registration.Family || 'Unknown Family';
        const cab = data.observation.Cabinet || data.registration.Cabinet || '';
        const drw = data.observation.Shelf || data.registration.Shelf || '';
        document.getElementById('detailTopLocation').textContent = cab ? `Cabinet ${cab} / Drawer ${drw}` : '';
        document.getElementById('detailCommonName').textContent = data.observation.CommonName || '';

        // Taxonomy Tab
        setVal('inputBinomial', (data.registration.Genus || '') + ' ' + (data.registration.Species || ''));
        setVal('inputAuthor', data.registration.Author);
        setVal('inputCommonName', data.observation.CommonName || data.registration.CommonName);
        setVal('inputFamily', data.registration.Family);
        setVal('inputGenus', data.registration.Genus);
        setVal('inputOrder', data.observation.Order || data.registration.Order);
        setVal('inputClass', data.observation.Class || data.registration.Class);
        setVal('inputDeterminedBy', data.observation.DeterminedBy || data.registration.DeterminedBy);
        setVal('inputDateDetermined', data.observation.DateDetermined || data.registration.DateDetermined);

        // Collection Tab
        setVal('inputCabinet', data.observation.Cabinet || data.registration.Cabinet);
        setVal('inputShelf', data.observation.Shelf || data.registration.Shelf);
        setVal('inputRoom', data.observation.Room || data.registration.Room);
        setVal('inputBarcode', data.observation.Barcode || data.registration.Barcode);

        setVal('inputCollector', data.observation.Collector || data.registration.Collector);
        setVal('inputFieldNumber', data.observation.FieldNumber || data.registration.FieldNumber);
        setVal('inputCollectionDate', data.observation.CollectionDate || data.registration.CollectionDate);
        setVal('inputCountry', data.observation.Country || data.registration.Country);
        setVal('inputLocality', data.observation.Locality || data.registration.Locality);

        setVal('inputLat', data.observation.Latitude || data.registration.Latitude);
        setVal('inputLon', data.observation.Longitude || data.registration.Longitude);
        setVal('inputElevation', data.observation.Elevation || data.registration.Elevation);
        setVal('inputHabitat', data.observation.Habitat || data.registration.Habitat);
        
        setVal('inputPreparation', data.observation.Preparation || data.registration.Preparation);
        setVal('inputCondition', data.observation.ConditionGrade || data.registration.ConditionGrade);
        
        setCheck('checkFlower', data.observation.PhenologyFlower);
        setCheck('checkFruit', data.observation.PhenologyFruit);
        setCheck('checkBuds', data.observation.PhenologyBuds);

        isReviewed = data.review_status === 'reviewed';
        updateReviewButton();
      } catch (err) {
        console.error("Failed to load object:", err);
      }
    }

    function loadImage() {
      if (currentRecord && currentRecord.images && currentRecord.images.online_urls.length > 0) {
        const url = currentRecord.images.online_urls[0];
        const img = document.getElementById('specimenImg');
        img.src = url;
        document.getElementById('imagePlaceholder').classList.add('hidden');
        document.getElementById('imageContainer').classList.remove('hidden');
      }
    }

    function updateReviewButton() {
      const btn = document.getElementById('btnReviewed');
      if (isReviewed) {
        btn.className = 'flex-1 bg-fern text-white px-4 py-3 rounded-md font-bold text-sm flex items-center justify-center gap-2 touch-min touch-press shadow-md transition border-2 border-fern-dark';
        btn.innerHTML = '<span>✓</span> <span>Reviewed (Tap to undo)</span>';
      } else {
        btn.className = 'flex-1 bg-surface border-2 border-bordercol text-ink hover:bg-tonal1 px-4 py-3 rounded-md font-bold text-sm flex items-center justify-center gap-2 touch-min touch-press transition';
        btn.innerHTML = '<span class="text-fern-dark">✓</span> <span>Mark Reviewed</span>';
      }
    }

    async function toggleReviewed() {
      isReviewed = !isReviewed;
      updateReviewButton();
      await saveCurrentEdits(true);
    }

    function autoSave() {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            saveCurrentEdits(false);
        }, 1000);
    }

    async function saveCurrentEdits(showStatus=false) {
      if (!currentOid) return;

      const binomial = document.getElementById('inputBinomial').value.trim().split(' ');
      const genus = binomial[0] || '';
      const species = binomial.slice(1).join(' ') || '';

      const payload = {
        id: currentOid,
        reviewed: isReviewed,
        registration: {
          Genus: genus || document.getElementById('inputGenus').value,
          Species: species,
          Family: document.getElementById('inputFamily').value,
          Author: document.getElementById('inputAuthor').value
        },
        observation: {
          CommonName: document.getElementById('inputCommonName').value,
          Order: document.getElementById('inputOrder').value,
          Class: document.getElementById('inputClass').value,
          DeterminedBy: document.getElementById('inputDeterminedBy').value,
          DateDetermined: document.getElementById('inputDateDetermined').value,

          Room: document.getElementById('inputRoom').value,
          Cabinet: document.getElementById('inputCabinet').value,
          Shelf: document.getElementById('inputShelf').value,
          Barcode: document.getElementById('inputBarcode').value,

          Collector: document.getElementById('inputCollector').value,
          FieldNumber: document.getElementById('inputFieldNumber').value,
          CollectionDate: document.getElementById('inputCollectionDate').value,
          Country: document.getElementById('inputCountry').value,
          Locality: document.getElementById('inputLocality').value,
          Latitude: document.getElementById('inputLat').value,
          Longitude: document.getElementById('inputLon').value,
          Elevation: document.getElementById('inputElevation').value,
          Habitat: document.getElementById('inputHabitat').value,

          Preparation: document.getElementById('inputPreparation').value,
          ConditionGrade: document.getElementById('inputCondition').value,
          PhenologyFlower: document.getElementById('checkFlower').checked,
          PhenologyFruit: document.getElementById('checkFruit').checked,
          PhenologyBuds: document.getElementById('checkBuds').checked,
        }
      };

      try {
        await apiFetch('/api/update', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        if(showStatus) showToast('✓ Edits synced to desktop database');
      } catch (err) {
        if(showStatus) showToast('⚠ Error syncing edits');
      }
    }

    if ('wakeLock' in navigator) {
      navigator.wakeLock.request('screen').catch(() => {});
    }

    init();
  </script>
</body>
</html>
"""
