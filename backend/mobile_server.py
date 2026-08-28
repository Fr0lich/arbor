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
import subprocess
import sys
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file, Response
import queue
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

def _apply_dataframe_updates(target_df, updates, changed_fields, changed_values, oid, fallback_df=None, allowed_columns=None):
    if target_df is None or oid not in target_df.index or not updates:
        return
    for k, v in updates.items():
        if k in target_df.columns:
            old_v = sanitize_value(target_df.at[oid, k])
            new_v = sanitize_value(v)
            if str(old_v) != str(new_v):
                coerced = coerce_type(new_v, target_df[k].dtype)
                target_df.at[oid, k] = coerced
                changed_fields.append(k)
                changed_values.append(f'{k}: "{old_v}" -> "{new_v}"')
        elif fallback_df is not None and k in fallback_df.columns:
            old_v = sanitize_value(fallback_df.at[oid, k])
            new_v = sanitize_value(v)
            if str(old_v) != str(new_v):
                coerced = coerce_type(new_v, fallback_df[k].dtype)
                fallback_df.at[oid, k] = coerced
                changed_fields.append(k)
                changed_values.append(f'{k}: "{old_v}" -> "{new_v}"')
        elif allowed_columns is not None and k in allowed_columns:
            new_v = sanitize_value(v)
            if new_v:
                # Initialize new column across all rows with empty string to avoid NaN corruption
                target_df[k] = ""
                target_df.at[oid, k] = new_v
                changed_fields.append(k)
                changed_values.append(f'{k}: "" -> "{new_v}"')

def _build_audit_log_entry(app_state, oid, action_name, is_rev_str, changed_fields, changed_values):
    # Lazy-build and cache the name sets — config is immutable per session so this is safe.
    # Avoids rebuilding the sets from config on every single audit log write.
    if not getattr(app_state, '_audit_set_cache', None):
        _loc = {"building", "room", "cabinet", "shelf", "drawer", "box", "location", "aisle", "unittray", "tray", "barcode"}
        _prob = set()
        if getattr(app_state, "config", None) and isinstance(app_state.config, dict) and "ui_sections" in app_state.config:
            ui_sec = app_state.config["ui_sections"]
            if "location" in ui_sec and isinstance(ui_sec["location"], list):
                for l_item in ui_sec["location"]:
                    if isinstance(l_item, dict) and "name" in l_item:
                        _loc.add(l_item["name"].lower())
            if "problems" in ui_sec and isinstance(ui_sec["problems"], list):
                for p_item in ui_sec["problems"]:
                    if isinstance(p_item, dict) and "name" in p_item:
                        _prob.add(p_item["name"].lower())
        app_state._audit_set_cache = (_loc, _prob)
    location_names, problem_names = app_state._audit_set_cache

    loc_fields = []
    loc_values = []
    prob_fields = []
    prob_values = []
    gen_fields = []
    gen_values = []

    for f, v in zip(changed_fields, changed_values):
        f_lower = f.lower()
        if f_lower in problem_names:
            prob_fields.append(f)
            prob_values.append(v)
        elif f_lower in location_names:
            loc_fields.append(f)
            loc_values.append(v)
        else:
            gen_fields.append(f)
            gen_values.append(v)

    now_ts = datetime.now().isoformat(timespec="seconds")
    return {
        "Timestamp": now_ts,
        "Action": action_name,
        "Reviewed": is_rev_str,
        "ObjectID": str(oid),
        "ChangedFields": ", ".join(gen_fields) if gen_fields else ("(no changes)" if not (loc_fields or prob_fields) else ""),
        "ChangedValues": " | ".join(gen_values),
        "ProblemsChanged": ", ".join(prob_fields),
        "ProblemsChangedValues": " | ".join(prob_values),
        "LocationChanged": ", ".join(loc_fields),
        "LocationChangedValues": " | ".join(loc_values),
        "User": "Mobile-Companion",
        "SourceFile": os.path.basename(app_state.excel_path or ""),
        "OutputFile": os.path.basename(app_state.output_path or app_state.excel_path or "")
    }

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
        self.clients = []
        self.clients_lock = threading.Lock()
        self.on_client_connect_callback = None
        self._setup_routes()

    def _add_firewall_rule(self):
        """Add a Windows Firewall inbound rule for the mobile server port.
        Silently skips on non-Windows or if netsh fails (e.g. no admin rights)."""
        if not sys.platform.startswith('win'):
            return
        try:
            subprocess.run([
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                f'name=Arbor Mobile Server (port {self.port})',
                'dir=in', 'action=allow', 'protocol=TCP',
                f'localport={self.port}'
            ], capture_output=True, timeout=5)
        except Exception:
            pass  # No admin rights or netsh unavailable — safe to ignore

    def _remove_firewall_rule(self):
        """Remove the Windows Firewall inbound rule added by _add_firewall_rule."""
        if not sys.platform.startswith('win'):
            return
        try:
            subprocess.run([
                'netsh', 'advfirewall', 'firewall', 'delete', 'rule',
                f'name=Arbor Mobile Server (port {self.port})'
            ], capture_output=True, timeout=5)
        except Exception:
            pass

    def start(self):
        if self._is_running:
            return
        self._add_firewall_rule()
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
        # Flask server intentionally kept alive as a persistent singleton.
        # Only clean up the firewall rule; the server thread keeps running
        # so subsequent MobilePanel re-opens can reuse it without a port conflict.
        self._remove_firewall_rule()


    def broadcast_event(self, event_type, data=None):
        if data is None:
            data = {}
        payload = {"type": event_type, "data": data}
        with self.clients_lock:
            for q in self.clients:
                try:
                    q.put(payload)
                except Exception:
                    pass

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

        @app.route('/api/schema', methods=['GET'])
        def get_schema():
            ui_sections = {}
            image_url_pattern = ""
            db_name = os.path.basename(self.app_state.excel_path) if self.app_state.excel_path else (self.app_state.config_name or "Active Database")
            if getattr(self.app_state, "config", None) and isinstance(self.app_state.config, dict):
                ui_sections = self.app_state.config.get("ui_sections", {})
                image_url_pattern = self.app_state.config.get("image_url_pattern", "")

            return jsonify({
                "database_name": db_name,
                "config_name": self.app_state.config_name or "",
                "ui_sections": ui_sections,
                "image_url_pattern": image_url_pattern
            })


        @app.route('/api/events', methods=['GET'])
        def sse_events():
            if not self._check_auth():
                return jsonify({"error": "Unauthorized"}), 401

            client_queue = queue.Queue()

            with self.clients_lock:
                self.clients.append(client_queue)
                active_count = len(self.clients)

            if self.on_client_connect_callback:
                try:
                    self.on_client_connect_callback(active_count)
                except Exception:
                    pass

            def generate():
                try:
                    while True:
                        try:
                            # 15s heartbeat timeout
                            msg = client_queue.get(timeout=15)
                            yield f"data: {json.dumps(msg)}\n\n"
                        except queue.Empty:
                            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                finally:
                    with self.clients_lock:
                        if client_queue in self.clients:
                            self.clients.remove(client_queue)
                        active_count = len(self.clients)
                    if self.on_client_connect_callback:
                        try:
                            self.on_client_connect_callback(active_count)
                        except Exception:
                            pass

            return Response(generate(), mimetype="text/event-stream")

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
                return jsonify({
                    "total_matching": 0,
                    "offset": 0,
                    "limit": 0,
                    "objects": [],
                    "facets": {"reviewed_count": 0, "pending_count": 0, "cabinets": {}}
                })

            query = request.args.get('q', '').strip().lower()
            status_filter = request.args.get('status', 'all').lower()

            # New query parameters
            cabinet_filter = request.args.get('cabinet', '').strip().lower()
            room_filter = request.args.get('room', '').strip().lower()
            genus_filter = request.args.get('genus', '').strip().lower()
            collector_filter = request.args.get('collector', '').strip().lower()
            has_problems_filter = request.args.get('has_problems', '').strip().lower()

            # Dynamic Advanced Filters
            specific_problems_param = request.args.get('specific_problems', '').strip()
            specific_problems = [p.strip() for p in specific_problems_param.split(',')] if specific_problems_param else []

            loc_filters = {}
            for k, v in request.args.items():
                if k.startswith('loc_') and v.strip():
                    loc_filters[k[4:]] = v.strip().lower()

            sort_by = request.args.get('sort_by', '').strip().lower()
            sort_dir = request.args.get('sort_dir', 'asc').strip().lower()

            limit = max(1, min(int(request.args.get('limit', 100)), 500))
            offset = max(0, int(request.args.get('offset', 0)))

            with self.app_state.df_lock:
                df_reg = self.app_state.df_reg
                df_obs = self.app_state.df_obs

                def _clean_val(val):
                    if val is None or pd.isna(val):
                        return ""
                    if isinstance(val, float) and val.is_integer():
                        return str(int(val))
                    s = str(val).strip()
                    return "" if s.lower() in ("nan", "none", "<na>") else s

                def _get_combined(col_name, indices):
                    """Helper to efficiently combine columns across registration and observation data safely."""
                    has_reg = col_name in df_reg.columns
                    has_obs = df_obs is not None and col_name in df_obs.columns

                    if not has_reg and not has_obs:
                        return pd.Series("", index=indices, dtype=object)

                    if has_reg and not has_obs:
                        return df_reg[col_name].reindex(indices)

                    if has_obs and not has_reg:
                        return df_obs[col_name].reindex(indices)

                    # Both exist: overlay non-null/non-empty observation values onto registration values
                    reg_col = df_reg[col_name].reindex(indices).astype(object)
                    obs_col = df_obs[col_name].reindex(indices).astype(object)
                    obs_str = obs_col.map(_clean_val)
                    valid_mask = obs_str != ""
                    reg_col[valid_mask] = obs_col[valid_mask]
                    return reg_col

                rev_col = "Reviewed" if (df_obs is not None and "Reviewed" in df_obs.columns) else None
                matched_indices = df_reg.index

                # Text search across config-defined registration columns
                is_search_active = bool(query)
                if is_search_active:
                    idx_str = df_reg.index.astype(str).str.lower()

                    # p1: exact ID match
                    p1_mask = idx_str == query

                    # p2: partial ID match
                    p2_mask = idx_str.str.contains(query, regex=False) & ~p1_mask

                    # p3: genus/species match
                    genus_col = df_reg["Genus"].fillna("").astype(str).str.lower() if "Genus" in df_reg.columns else pd.Series("", index=df_reg.index)
                    species_col = df_reg["Species"].fillna("").astype(str).str.lower() if "Species" in df_reg.columns else pd.Series("", index=df_reg.index)
                    gen_spec = genus_col + " " + species_col
                    p3_mask = gen_spec.str.contains(query, regex=False) & ~(p1_mask | p2_mask)

                    # p4: family match
                    family_col = df_reg["Family"].fillna("").astype(str).str.lower() if "Family" in df_reg.columns else pd.Series("", index=df_reg.index)
                    p4_mask = family_col.str.contains(query, regex=False) & ~(p1_mask | p2_mask | p3_mask)

                    # p5: other columns match
                    p5_mask = pd.Series(False, index=df_reg.index)
                    search_cols = ["Genus", "Species", "Family", "Author", "Collector", "Box Label", "Cabinet", "Variant"]
                    if self.app_state.config and "registration" in self.app_state.config.get("ui_sections", {}):
                        search_cols = [f["name"] for f in self.app_state.config["ui_sections"]["registration"] if isinstance(f, dict) and f.get("name")]

                    for col in search_cols:
                        if col in df_reg.columns and col not in ["Genus", "Species", "Family"]:
                            p5_mask |= df_reg[col].fillna("").astype(str).str.lower().str.contains(query, regex=False)
                    p5_mask = p5_mask & ~(p1_mask | p2_mask | p3_mask | p4_mask)

                    all_matched_list = df_reg.index[p1_mask].tolist() + df_reg.index[p2_mask].tolist() + df_reg.index[p3_mask].tolist() + df_reg.index[p4_mask].tolist() + df_reg.index[p5_mask].tolist()
                    matched_indices = pd.Index(all_matched_list)

                # Status filter
                if status_filter != 'all':
                    if rev_col and df_obs is not None:
                        rev_series = df_obs.reindex(matched_indices)[rev_col].astype(str).str.strip().str.lower()
                        is_rev = rev_series.isin(["true", "1", "yes"])
                        if status_filter == 'reviewed':
                            matched_indices = matched_indices[is_rev]
                        elif status_filter == 'pending':
                            matched_indices = matched_indices[~is_rev]
                    if status_filter == 'flagged':
                        prob_cols = []
                        if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                            prob_cols = [p.get("name") for p in self.app_state.config["ui_sections"]["problems"] if p.get("name")]
                        flagged_mask = pd.Series(False, index=matched_indices)
                        for p_col in prob_cols:
                            combined_prob = _get_combined(p_col, matched_indices)
                            flagged_mask |= combined_prob.map(_clean_val).str.lower().isin(["true", "1", "yes", "t"])
                        matched_indices = matched_indices[flagged_mask]

                # Cabinet filter
                if cabinet_filter:
                    combined_cabinets = _get_combined("Cabinet", matched_indices).map(_clean_val).str.lower()
                    mask = combined_cabinets == cabinet_filter
                    matched_indices = matched_indices[mask]

                # Room filter
                if room_filter:
                    combined_rooms = _get_combined("Room", matched_indices).map(_clean_val).str.lower()
                    mask = combined_rooms == room_filter
                    matched_indices = matched_indices[mask]

                # Genus filter
                if genus_filter:
                    if "Genus" in df_reg.columns:
                        mask = df_reg["Genus"].reindex(matched_indices).map(_clean_val).str.lower() == genus_filter
                        matched_indices = matched_indices[mask]

                # Collector filter
                if collector_filter:
                    if "Collector" in df_reg.columns:
                        mask = df_reg["Collector"].reindex(matched_indices).map(_clean_val).str.lower().str.contains(collector_filter, regex=False)
                        matched_indices = matched_indices[mask]

                # Has problems filter
                if has_problems_filter:
                    mask = pd.Series(False, index=matched_indices)
                    problems = []
                    if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                        problems = [p.get("name") for p in self.app_state.config["ui_sections"]["problems"]]

                    for p_col in problems:
                        combined_prob = _get_combined(p_col, matched_indices)
                        mask |= combined_prob.map(_clean_val).str.lower().isin(["true", "1", "yes", "t"])

                    if has_problems_filter in ["true", "1", "yes", "t"]:
                        matched_indices = matched_indices[mask]
                    elif has_problems_filter in ["false", "0", "no", "f"]:
                        matched_indices = matched_indices[~mask]

                # Dynamic Location Filters
                for loc_col, loc_val in loc_filters.items():
                    combined_loc = _get_combined(loc_col, matched_indices).map(_clean_val).str.lower()
                    matched_indices = matched_indices[combined_loc == loc_val]

                # Specific Problems Filters (from Advanced Filter Modal)
                if specific_problems:
                    # Collect schema-defined problems and mapping
                    schema_problems = []
                    problem_to_field = {}
                    if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                        for p in self.app_state.config["ui_sections"]["problems"]:
                            name = p.get("name")
                            if name:
                                schema_problems.append(name)
                                if "maps_to" in p:
                                    problem_to_field[name] = p["maps_to"]
                                elif "target" in p:
                                    problem_to_field[name] = p["target"]

                    def get_problem_mask(prob_col, indices):
                        if prob_col == "Images_Missing":
                            if "Images_Missing" in df_obs.columns if df_obs is not None else False:
                                return _get_combined("Images_Missing", indices).map(_clean_val).str.lower().isin(["true", "1", "yes", "t"])
                            return pd.Series(False, index=indices)

                        obs_mask = _get_combined(prob_col, indices).map(_clean_val).str.lower().isin(["true", "1", "yes", "t"])

                        if prob_col in problem_to_field:
                            field = problem_to_field[prob_col]
                            if field in df_reg.columns:
                                raw_vals = df_reg[field].reindex(indices)
                                is_missing = raw_vals.isna() | (raw_vals.map(_clean_val) == "")
                                # Check for unknown strings
                                is_unknown = raw_vals.isna() | raw_vals.map(lambda x: str(x).strip().lower() in ("", "unknown", "?", "ukjent"))
                                auto_mask = is_missing & ~is_unknown
                                return obs_mask | auto_mask

                        return obs_mask

                    combined_problem_mask = pd.Series(False, index=matched_indices)

                    for sp in specific_problems:
                        if sp == "Any_Problem":
                            for sp_schema in schema_problems:
                                if "Image" not in sp_schema:
                                    combined_problem_mask |= get_problem_mask(sp_schema, matched_indices)
                        else:
                            combined_problem_mask |= get_problem_mask(sp, matched_indices)

                    matched_indices = matched_indices[combined_problem_mask]

                total_matching = len(matched_indices)

                # Facet computation
                facets = {}

                # 1. Cabinets facet
                cabinet_series = _get_combined("Cabinet", matched_indices).map(_clean_val)
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
                if sort_by in ['id', 'genus', 'cabinet'] and not is_search_active:
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
                            sort_series = df_reg["Genus"].reindex(matched_indices).map(_clean_val)
                            matched_indices = matched_indices[sort_series.argsort()]
                            if not ascending:
                                matched_indices = matched_indices[::-1]
                    elif sort_by == 'cabinet':
                        sort_series = _get_combined("Cabinet", matched_indices).map(_clean_val)
                        matched_indices = matched_indices[sort_series.argsort()]
                        if not ascending:
                            matched_indices = matched_indices[::-1]

                paged_indices = matched_indices[offset:offset + limit]

                # Dynamically resolve location fields from config
                location_fields = ["Building", "Floor", "Cabinet", "Stored as", "Extra", "Room", "Shelf", "Drawer", "Box"]
                if self.app_state.config and "location" in self.app_state.config.get("ui_sections", {}):
                    location_fields = [f["name"] for f in self.app_state.config["ui_sections"]["location"] if isinstance(f, dict) and f.get("name")]

                objects = []
                paged_indices_list = paged_indices.tolist()
                paged_reg_dict = df_reg.loc[paged_indices_list].to_dict('index')

                obs_cols = set(df_obs.columns) if df_obs is not None else set()
                reg_cols = set(df_reg.columns)

                paged_obs_dict = {}
                if df_obs is not None:
                    intersect = df_obs.index.intersection(paged_indices_list)
                    if len(intersect) > 0:
                        paged_obs_dict = df_obs.loc[intersect].to_dict('index')

                loc_keys = {lcol: lcol.lower().replace(" ", "_") for lcol in location_fields}

                for oid in paged_indices_list:
                    reg_row = paged_reg_dict.get(oid, {})
                    obs_row = paged_obs_dict.get(oid)

                    genus = _clean_val(reg_row.get("Genus"))
                    species = _clean_val(reg_row.get("Species"))
                    family = _clean_val(reg_row.get("Family"))
                    author = _clean_val(reg_row.get("Author"))
                    collector = _clean_val(reg_row.get("Collector"))
                    collection_date = _clean_val(reg_row.get("Collection Date"))
                    sci_name = f"{genus} {species} {author}".strip() if (genus or species) else f"Specimen #{oid}"

                    rev_val = False
                    if rev_col and obs_row is not None:
                        v = _clean_val(obs_row.get(rev_col)).lower()
                        rev_val = v in ["true", "1", "yes"]

                    loc = {}
                    for lcol, key_name in loc_keys.items():
                        if obs_row is not None and lcol in obs_cols and _clean_val(obs_row.get(lcol)):
                            loc[key_name] = _clean_val(obs_row.get(lcol))
                        elif lcol in reg_cols and _clean_val(reg_row.get(lcol)):
                            loc[key_name] = _clean_val(reg_row.get(lcol))
                        else:
                            loc[key_name] = ""

                    objects.append({
                        "id": str(oid),
                        "accession_number": str(oid),
                        "scientific_name": sci_name,
                        "genus": genus,
                        "species": species,
                        "family": family,
                        "author": author,
                        "collector": collector,
                        "collection_date": collection_date,
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


        @app.route('/api/object/<oid>/history', methods=['GET'])
        def get_object_history(oid):
            if not getattr(self.app_state, 'historical_dbs', None):
                return jsonify({"historical_data": {}})

            oid = str(oid).strip()
            suggestions = {}

            with self.app_state.df_lock:
                for db in self.app_state.historical_dbs:
                    db_name = db.get("name", "Unknown DB")
                    reg_by_id = db.get("reg_by_id")

                    if reg_by_id is not None:
                        # Try exact match first
                        if oid in reg_by_id.index:
                            row = reg_by_id.loc[oid]
                        else:
                            # Try int match if numeric
                            try:
                                if oid.isdigit() and int(oid) in reg_by_id.index:
                                    row = reg_by_id.loc[int(oid)]
                                else:
                                    continue
                            except Exception:
                                continue

                        if isinstance(row, pd.DataFrame):
                            row = row.iloc[0]

                        for col in row.index:
                            val = row[col]
                            if pd.isna(val):
                                continue
                            val_str = str(val).strip()
                            if not val_str or val_str.lower() == "nan":
                                continue

                            if col not in suggestions:
                                suggestions[col] = {}

                            if val_str not in suggestions[col]:
                                suggestions[col][val_str] = []

                            if db_name not in suggestions[col][val_str]:
                                suggestions[col][val_str].append(db_name)

            return jsonify({
                "id": str(oid),
                "historical_data": suggestions
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

                # Compute allowed columns from active config
                allowed_reg_cols = set()
                allowed_obs_cols = {"Reviewed", "ReviewedAt", "Images_Missing", "Images_Problem", "Online_Images_Exist"}
                if getattr(self.app_state, "config", None) and isinstance(self.app_state.config, dict):
                    ui_sec = self.app_state.config.get("ui_sections", {})
                    for item in ui_sec.get("registration", []):
                        if isinstance(item, dict) and "name" in item:
                            allowed_reg_cols.add(item["name"])
                    for item in ui_sec.get("location", []):
                        if isinstance(item, dict) and "name" in item:
                            allowed_obs_cols.add(item["name"])
                    for item in ui_sec.get("problems", []):
                        if isinstance(item, dict) and "name" in item:
                            allowed_obs_cols.add(item["name"])
                    for item in ui_sec.get("unknown_fields", []):
                        if isinstance(item, dict) and "name" in item:
                            allowed_obs_cols.add(item["name"])

                # 2. Apply registration updates
                _apply_dataframe_updates(self.app_state.df_reg, reg_updates, changed_fields, changed_values, oid, allowed_columns=allowed_reg_cols if allowed_reg_cols else None)

                # 3. Ensure df_obs has a row for this OID before applying observation updates.
                # Use dtype-matched defaults (False for bool cols, "" for all others) to prevent
                # pandas from coercing bool columns to object dtype on pd.concat.
                if self.app_state.df_obs is not None and oid not in self.app_state.df_obs.index:
                    empty_vals = {}
                    for col in self.app_state.df_obs.columns:
                        dtype = self.app_state.df_obs[col].dtype
                        empty_vals[col] = False if pd.api.types.is_bool_dtype(dtype) else ""
                    new_obs_row = pd.DataFrame([empty_vals], index=[oid])
                    new_obs_row.index.name = self.app_state.df_obs.index.name or "ObjectID"
                    self.app_state.df_obs = pd.concat([self.app_state.df_obs, new_obs_row])

                # 4. Apply observation updates
                _apply_dataframe_updates(self.app_state.df_obs, updates, changed_fields, changed_values, oid, fallback_df=self.app_state.df_reg, allowed_columns=allowed_obs_cols if allowed_obs_cols else None)

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
                        changed_values.append(f'Reviewed: "{old_obs.get("Reviewed", "")}" -> "{is_reviewed_bool}"')

                # 5. Append / Merge Log Record
                if not hasattr(self.app_state, "_log_records") or self.app_state._log_records is None:
                    self.app_state._log_records = []

                log_entry = _build_audit_log_entry(self.app_state, oid, action_name, is_rev_str, changed_fields, changed_values)
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

                # Write under lock so rapid sequential edits don't race with the Tkinter event handler
                self.app_state._mobile_last_edited_oid = oid

            self.broadcast_event("record_updated", {"id": oid})

            # 8. Notify desktop UI
            if self.on_edit_callback:
                try:
                    self.on_edit_callback(oid, edit_summary)
                except Exception as e:
                    pass

            if self.root_tk:
                try:
                    self.root_tk.event_generate("<<MobileEdit>>", when="tail")
                except Exception:
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

                # Compute allowed columns from active config outside the loop
                allowed_reg_cols = set()
                allowed_obs_cols = {"Reviewed", "ReviewedAt", "Images_Missing", "Images_Problem", "Online_Images_Exist"}
                if getattr(self.app_state, "config", None) and isinstance(self.app_state.config, dict):
                    ui_sec = self.app_state.config.get("ui_sections", {})
                    for item in ui_sec.get("registration", []):
                        if isinstance(item, dict) and "name" in item:
                            allowed_reg_cols.add(item["name"])
                    for item in ui_sec.get("location", []):
                        if isinstance(item, dict) and "name" in item:
                            allowed_obs_cols.add(item["name"])
                    for item in ui_sec.get("problems", []):
                        if isinstance(item, dict) and "name" in item:
                            allowed_obs_cols.add(item["name"])
                    for item in ui_sec.get("unknown_fields", []):
                        if isinstance(item, dict) and "name" in item:
                            allowed_obs_cols.add(item["name"])

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
                    _apply_dataframe_updates(self.app_state.df_reg, reg_updates, changed_fields, changed_values, oid, allowed_columns=allowed_reg_cols if allowed_reg_cols else None)

                    # 3. Ensure df_obs has a row for this OID before applying observation updates.
                    # Use dtype-matched defaults (False for bool cols, "" for all others) to prevent
                    # pandas from coercing bool columns to object dtype on pd.concat.
                    if self.app_state.df_obs is not None and oid not in self.app_state.df_obs.index:
                        empty_vals = {}
                        for col in self.app_state.df_obs.columns:
                            dtype = self.app_state.df_obs[col].dtype
                            empty_vals[col] = False if pd.api.types.is_bool_dtype(dtype) else ""
                        new_obs_row = pd.DataFrame([empty_vals], index=[oid])
                        new_obs_row.index.name = self.app_state.df_obs.index.name or "ObjectID"
                        self.app_state.df_obs = pd.concat([self.app_state.df_obs, new_obs_row])

                    # 4. Apply observation updates
                    _apply_dataframe_updates(self.app_state.df_obs, obs_updates, changed_fields, changed_values, oid, fallback_df=self.app_state.df_reg, allowed_columns=allowed_obs_cols if allowed_obs_cols else None)

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
                            changed_values.append(f'Reviewed: "{old_obs.get("Reviewed", "")}" -> "{is_reviewed_bool}"')

                    # 5. Append / Merge Log Record
                    if not hasattr(self.app_state, "_log_records") or self.app_state._log_records is None:
                        self.app_state._log_records = []

                    log_entry = _build_audit_log_entry(self.app_state, oid, action_name, is_rev_str, changed_fields, changed_values)
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

                    self.broadcast_event("record_updated", {"id": oid})

                if updated_ids:
                    self.app_state.df_log = pd.DataFrame(self.app_state._log_records)
                    self.app_state.dirty = True
                    # Write under lock so rapid sequential edits don't race with the Tkinter event handler
                    self.app_state._mobile_last_edited_oid = updated_ids[-1]

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
                    self.root_tk.event_generate("<<MobileEdit>>", when="tail")
                except Exception:
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


# WARNING TO AI AGENTS: DO NOT CREATE OR MODIFY AN EXTERNAL `mobile_frontend.html` FILE.
# The user explicitly prefers maintaining a Vanilla HTML/JS frontend directly within this
# INDEX_TEMPLATE string to ensure the Python server remains self-contained without
# external build dependencies or file resolution issues. All frontend modifications for
# the mobile application MUST be done inside this string below.
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
            sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
            serif: ['Lora', 'Georgia', 'serif'],
            mono: ['JetBrains Mono', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
          }
        }
      }
    }
  </script>
  <style>
    .touch-target-min { min-height: 44px; min-width: 44px; }
    .touch-press:active { transform: scale(0.985); filter: brightness(0.97); }
    .search-active:focus-within {
      border-color: #d95c14 !important;
      box-shadow: 0 0 0 2px rgba(217, 92, 20, 0.2) !important;
    }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: #f3f3f3; }
    ::-webkit-scrollbar-thumb { background: #c8ccc9; border-radius: 2px; }
    .acc-open .acc-icon { transform: rotate(180deg); }
    @keyframes spinSlow { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    .animate-spin-slow { animation: spinSlow 8s linear infinite; }
  </style>
</head>
<body class="bg-canvas text-ink min-h-screen antialiased select-none font-sans">

  <div class="w-full h-screen flex flex-col relative overflow-hidden bg-canvas mx-auto max-w-md border-x border-bordercol shadow-xl">

    <!-- Persistent Offline / Disconnected Warning Banner -->
    <div id="offlineBanner" class="hidden bg-ember-light border-b border-ember-border px-4 py-2 flex items-center justify-between gap-2 text-xs font-sans font-medium text-ember-dark shrink-0 transition-all shadow-xs" role="alert" aria-live="assertive">
      <div class="flex items-center gap-2">
        <span class="text-sm">⚠</span>
        <span>Connection to host lost. Reconnecting...</span>
      </div>
      <button
        type="button"
        onclick="setupEventSource()"
        class="min-h-[32px] px-2.5 py-1 bg-ember text-white rounded-[2px] font-bold text-[11px] touch-press shrink-0"
      >
        Retry
      </button>
    </div>

    <!-- ========================================== -->
    <!-- VIEW: SPECIMEN LIST                        -->
    <!-- ========================================== -->
    <div id="listView" class="flex-1 flex flex-col h-full bg-canvas overflow-hidden">
      <!-- Sticky Header -->
      <header class="sticky top-0 z-30 bg-surface border-b border-bordercol px-4 pt-3 pb-2.5 shadow-xs shrink-0">
        <div class="flex items-center justify-between mb-2.5">
          <div class="flex items-center gap-2">
            <div class="w-7 h-7 rounded-[2px] bg-fern text-white flex items-center justify-center font-serif font-bold text-sm">
              A
            </div>
            <div>
              <h1 class="font-serif font-bold text-base text-ink leading-tight">
                Arbor Companion
              </h1>
              <div class="font-mono text-[10px] text-ink-muted truncate max-w-[170px]" id="headerDbName">
                Connecting to database...
              </div>
            </div>
          </div>

          <div class="flex items-center gap-1.5">
            <!-- Screen Wake Lock / Walk Mode Toggle -->
            <button
              type="button"
              id="btnWakeLock"
              onclick="toggleWakeLock()"
              class="p-2 rounded-[2px] border transition-colors touch-target-min bg-ink text-surface border-ink hover:bg-ink-muted flex items-center justify-center"
              title="Toggle Walk Mode (Prevent Screen Sleep)"
            >
              <span id="wakeLockIcon" class="text-sm leading-none">🌙</span>
            </button>

            <!-- Desktop Connection Pill Button -->
            <button
              type="button"
              onclick="openModal('connectionModal')"
              id="connStatusBtn"
              class="flex items-center gap-1.5 px-2.5 py-1.5 bg-surface hover:bg-tonal1 border border-bordercol rounded-[2px] text-xs transition-colors touch-target-min"
              title="Desktop Connection Status"
              aria-live="polite"
            >
              <span class="relative flex h-2 w-2">
                <span id="connPingDotAnimate" class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-fern"></span>
                <span id="connPingDot" class="relative inline-flex rounded-full h-2 w-2 bg-fern"></span>
              </span>
              <span class="font-mono text-[11px] font-medium text-ink" id="pingBadge">
                Live
              </span>
            </button>
          </div>
        </div>

        <!-- Search Input Box -->
        <div class="relative flex items-center gap-2">
          <div class="relative flex-1 flex items-center bg-tonal1 border border-bordercol rounded-[2px] transition-all search-active">
            <span class="text-ink-faint ml-2.5 shrink-0 text-xs">🔍</span>
            <input
              type="text"
              id="searchBox"
              oninput="debounceSearch()"
              placeholder="Search taxonomy, accession, collector, cabinet..."
              class="w-full bg-transparent px-2.5 py-2 font-sans text-xs text-ink placeholder:text-ink-faint outline-none"
            />
            <button
              type="button"
              id="searchClearBtn"
              onclick="clearSearch()"
              class="hidden p-1 mr-1.5 text-ink-faint hover:text-ink text-xs font-bold"
            >
              ✕
            </button>
          </div>

          <!-- Advanced Filter Modal Trigger -->
          <button
            type="button"
            onclick="openFilterModal()"
            class="p-2 bg-surface hover:bg-tonal1 border border-bordercol rounded-[2px] text-ink transition-colors touch-target-min flex items-center justify-center shrink-0"
            title="Advanced Filter"
          >
            <span class="text-ink text-sm font-mono">⚙</span>
          </button>
        </div>

        <!-- Filter Pill Tabs -->
        <div class="flex items-center gap-2 mt-2.5 overflow-x-auto no-scrollbar pb-1" id="filterPills">
          <button
            type="button"
            onclick="setStatusFilter('all')"
            id="pill-all"
            class="min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border transition-colors touch-press flex items-center justify-center bg-ink text-white border-ink"
          >
            All (0)
          </button>

          <button
            type="button"
            onclick="setStatusFilter('pending')"
            id="pill-pending"
            class="min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border transition-colors touch-press flex items-center gap-1.5 bg-surface text-ink-muted border-bordercol hover:bg-tonal1"
          >
            <span>🕒</span>
            <span>Unreviewed (0)</span>
          </button>

          <button
            type="button"
            onclick="setStatusFilter('flagged')"
            id="pill-flagged"
            class="min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border transition-colors touch-press flex items-center gap-1.5 bg-ember-light text-ember-dark border-ember-border hover:bg-ember-light/80"
          >
            <span>⚠</span>
            <span>Flagged (0)</span>
          </button>

          <button
            type="button"
            onclick="setStatusFilter('reviewed')"
            id="pill-reviewed"
            class="min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border transition-colors touch-press flex items-center gap-1.5 bg-fern-light text-fern-dark border-fern-border hover:bg-fern-light/80"
          >
            <span>✓</span>
            <span>Reviewed (0)</span>
          </button>

          <div class="w-px h-6 bg-bordercol mx-0.5 shrink-0"></div>

          <button
            type="button"
            onclick="toggleNoImageFilter()"
            id="pill-no-image"
            class="min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border transition-colors touch-press flex items-center gap-1.5 bg-surface text-ink-muted border-bordercol hover:bg-tonal1"
          >
            <span>📷</span>
            <span>No Image</span>
          </button>
        </div>

        <!-- Results Counter & Sort Dropdown -->
        <div class="flex items-center justify-between mt-2 pt-2 border-t border-tonal2 text-[11px]">
          <span class="font-mono text-ink-muted" id="listSummaryText">
            Showing <strong class="text-ink" id="matchingCount">0</strong> records
          </span>

          <div class="flex items-center gap-1 text-ink-muted">
            <span class="text-xs">⇅</span>
            <select
              id="sortBySelect"
              onchange="handleSortChange()"
              class="bg-transparent font-sans text-[11px] font-medium text-ink outline-none cursor-pointer"
            >
              <option value="location">Sort by Physical Location</option>
              <option value="name-asc">Scientific Name (A-Z)</option>
              <option value="name-desc">Scientific Name (Z-A)</option>
              <option value="id-asc">Accession / ID Number</option>
            </select>
          </div>
        </div>
      </header>

      <!-- Scrollable List -->
      <main id="specimenListContainer" class="flex-1 overflow-y-auto p-3 space-y-2.5 pb-24">
        <!-- Specimen cards injected dynamically -->
      </main>
    </div>


    <!-- ========================================== -->
    <!-- VIEW: SPECIMEN DETAIL                      -->
    <!-- ========================================== -->
    <div id="detailView" class="hidden flex-1 flex flex-col h-full bg-canvas overflow-hidden relative">
      <!-- Sticky Top Header -->
      <header class="sticky top-0 z-30 bg-surface border-b border-bordercol px-4 py-2.5 shadow-xs shrink-0 flex items-center justify-between">
        <button
          type="button"
          onclick="showListView()"
          class="flex items-center gap-1.5 text-xs font-sans font-medium text-ink hover:text-fern py-1 px-1.5 -ml-1 rounded-[2px] transition-colors touch-target-min"
        >
          <span class="font-bold text-sm">&lt;</span>
          <span>Vault List</span>
        </button>

        <div class="flex items-center gap-2">
          <span class="font-mono text-xs text-ink-muted" id="detailNavIndex">
            1 of 1
          </span>
          <div class="flex items-center border border-bordercol rounded-[2px] bg-tonal1 overflow-hidden">
            <button
              type="button"
              id="btnPrevSpecimen"
              onclick="navSpecimen(-1)"
              class="p-1.5 hover:bg-tonal2 disabled:opacity-30 text-ink transition-colors touch-target-min"
              title="Previous specimen"
            >
              <span class="font-bold text-xs">&lt;</span>
            </button>
            <div class="w-[1px] h-4 bg-bordercol"></div>
            <button
              type="button"
              id="btnNextSpecimen"
              onclick="navSpecimen(1)"
              class="p-1.5 hover:bg-tonal2 disabled:opacity-30 text-ink transition-colors touch-target-min"
              title="Next specimen"
            >
              <span class="font-bold text-xs">&gt;</span>
            </button>
          </div>
        </div>
      </header>

      <!-- Scrollable Specimen Form Content -->
      <main class="flex-1 overflow-y-auto p-3.5 space-y-3.5 pb-36">

        <!-- Top Specimen Summary Card -->
        <div class="bg-surface border border-bordercol rounded-[2px] p-4 shadow-xs">
          <div class="flex items-start justify-between gap-2 mb-2">
            <div>
              <div class="font-mono text-xs font-bold text-ink-muted tracking-wider" id="detailAccession">
                #---
              </div>
              <div class="font-mono text-[11px] text-ink-faint" id="detailTopLocation">
                Location: ---
              </div>
            </div>

            <div id="detailReviewStatusBadge">
              <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[10px] font-sans font-medium bg-tonal1 text-ink-muted border border-bordercol">
                🕒 UNREVIEWED
              </span>
            </div>
          </div>

          <h2 id="detailScientificName" class="font-serif italic font-bold text-xl text-ink leading-snug mb-1">
            Loading specimen...
          </h2>

          <div class="flex items-center gap-2 text-xs font-sans text-ink-muted" id="detailTaxonSubline">
            <span id="detailAuthor" class="font-medium text-ink"></span>
            <span>•</span>
            <span id="detailFamily"></span>
          </div>
        </div>


        <!-- Archival Scans / Photo Gallery Card -->
        <div class="bg-surface border border-bordercol rounded-[2px] p-3 space-y-2.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5 text-xs font-sans font-semibold text-ink">
              <span>📷</span>
              <span>Attached Archival Scans</span>
              <span id="photoCountBadge" class="font-mono text-[10px] text-ink-muted bg-tonal1 border border-tonal3 px-1.5 py-0.2 rounded-[2px]">
                0 available
              </span>
            </div>

            <button
              type="button"
              onclick="openFullscreenPhoto()"
              class="text-[11px] font-sans font-medium text-fern hover:text-fern-dark flex items-center gap-1 transition-colors touch-target-min py-1 px-1"
            >
              <span>↗</span>
              <span>Fullscreen</span>
            </button>
          </div>

          <!-- Photo Container -->
          <div
            id="photoMainContainer"
            onclick="openFullscreenPhoto()"
            class="relative w-full h-52 bg-ink/5 rounded-[2px] border border-bordercol overflow-hidden cursor-pointer group flex items-center justify-center"
          >
            <div id="photoPlaceholder" class="p-6 text-center text-xs text-ink-muted flex flex-col items-center gap-1.5">
              <span class="text-2xl">📷</span>
              <p class="font-semibold text-fern">Tap to Load Specimen Plate</p>
              <p class="text-[10px] text-ink-faint">Direct CDN stream</p>
            </div>
            <img
              id="specimenImg"
              src=""
              alt="Archival Specimen Plate"
              class="hidden w-full h-full object-contain group-hover:scale-[1.02] transition-transform duration-200"
              onload="onPhotoLoaded()"
              onerror="onPhotoError()"
            />
            <div id="photoWatermark" class="hidden absolute bottom-1.5 left-1.5 bg-white/90 backdrop-blur-xs font-mono text-[9px] text-ink-muted px-1.5 py-0.5 rounded-[1px] border border-bordercol">
              Archival Scan
            </div>
          </div>

          <!-- Thumbnail Strip -->
          <div id="photoThumbStrip" class="hidden flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
            <!-- Thumbnails injected dynamically -->
          </div>
        </div>

        <!-- Dynamic Form Groups Container (Injected from config.py) -->
        <div id="detailAccordionsContainer" class="space-y-3.5">
          <!-- Rendered dynamically by renderDynamicForm() -->
        </div>

        <!-- Problem Discrepancies Card -->
        <div class="bg-surface border border-bordercol rounded-[2px] p-3.5 space-y-3">
          <div class="flex items-center justify-between border-b border-tonal2 pb-2">
            <div class="flex items-center gap-2">
              <span class="text-ember font-bold text-sm">⚑</span>
              <h3 class="font-sans font-bold text-xs text-ink uppercase tracking-wider">
                Flagged Problems & Issues
              </h3>
            </div>
            <button
              type="button"
              onclick="openAddDiscrepancyModal()"
              class="text-xs font-medium text-ember hover:text-ember-dark flex items-center gap-1 border border-ember-border bg-ember-light px-2 py-0.5 rounded-[2px] transition-colors touch-target-min"
            >
              <span>+</span>
              <span>Flag Issue</span>
            </button>
          </div>

          <!-- Active Discrepancies List -->
          <div id="activeDiscrepanciesList" class="space-y-2">
            <!-- Discrepancy items injected dynamically -->
          </div>

          <!-- Problem Flags Quick-Toggle Grid -->
          <div id="problemFlagsGrid" class="pt-2 border-t border-tonal2 space-y-2">
            <p class="font-mono text-[10px] uppercase font-bold text-ink-muted">Quick Problem Toggles:</p>
            <div id="problemTogglesContainer" class="grid grid-cols-2 gap-2 text-xs">
              <!-- Checkboxes dynamically generated from ui_sections.problems -->
            </div>
          </div>
        </div>

      </main>

      <!-- Sticky Action Bar (Fixed to Screen Bottom) -->
      <footer class="fixed bottom-0 left-0 right-0 z-40 bg-surface border-t border-bordercol shadow-[0_-4px_16px_rgba(0,0,0,0.08)] max-w-md mx-auto">
        <div class="px-4 py-2.5">
          <!-- Mini Status Ticker Bar -->
          <div class="flex items-center justify-between text-[11px] mb-2 pb-1.5 border-b border-tonal2">
            <div class="flex items-center gap-1.5" aria-live="polite">
              <span class="relative flex h-2 w-2">
                <span id="footerConnDotAnimate" class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-fern"></span>
                <span id="footerConnDot" class="relative inline-flex rounded-full h-2 w-2 bg-fern"></span>
              </span>
              <span class="font-mono text-ink-muted" id="footerTickerHost">
                Host Connected
              </span>
            </div>

            <div class="flex items-center gap-1" id="footerSyncStatus">
              <span class="font-mono text-fern-dark font-medium">✓ Synced to host</span>
            </div>
          </div>

          <!-- Primary Action Button: Full-Width Mark Reviewed -->
          <button
            type="button"
            id="btnMarkReviewed"
            onclick="toggleReviewed()"
            class="w-full py-3.5 px-4 rounded-[2px] font-sans font-bold text-sm flex items-center justify-center gap-2 border-2 transition-all touch-target-min touch-press bg-surface text-ink border-bordercol hover:bg-tonal1 shadow-xs"
          >
            <span class="text-fern-dark text-base">✓</span>
            <span id="btnReviewedLabel">Mark Reviewed</span>
          </button>
        </div>
      </footer>
    </div>


    <!-- ========================================== -->
    <!-- MODAL: FULLSCREEN PHOTO VIEWER             -->
    <!-- ========================================== -->
    <div id="photoViewerModal" class="hidden fixed inset-0 z-50 bg-black/95 backdrop-blur-md flex flex-col">
      <!-- Modal Header -->
      <header class="p-3 bg-black/40 text-white flex items-center justify-between border-b border-white/10 shrink-0">
        <div class="flex items-center gap-2 text-xs font-mono">
          <span class="text-fern-light font-bold" id="photoViewerTitle">Specimen Plate</span>
          <span class="text-white/60" id="photoViewerCounter">(1/1)</span>
        </div>
        <button
          type="button"
          onclick="closeModal('photoViewerModal')"
          class="p-2 text-white/80 hover:text-white rounded-[2px] text-lg font-bold touch-target-min"
        >
          ✕
        </button>
      </header>

      <!-- Viewport -->
      <div
        id="photoViewport"
        class="flex-1 relative overflow-hidden flex items-center justify-center p-2 cursor-grab active:cursor-grabbing select-none"
        onmousedown="startPhotoDrag(event)"
        ontouchstart="startPhotoTouch(event)"
      >
        <img
          id="photoViewerImg"
          src=""
          alt="High Resolution Scan"
          class="max-w-full max-h-full object-contain transition-transform duration-75 origin-center"
          style="transform: scale(1) rotate(0deg) translate(0px, 0px);"
        />
      </div>

      <!-- Controls Footer -->
      <footer class="p-3 bg-black/60 text-white flex items-center justify-between border-t border-white/10 shrink-0 text-xs font-mono">
        <div class="flex items-center gap-2">
          <button type="button" onclick="zoomPhoto(-0.5)" class="px-3 py-2 bg-white/10 hover:bg-white/20 rounded-[2px] touch-target-min">− Zoom</button>
          <span id="zoomLevelDisplay" class="text-white/80 min-w-[40px] text-center">1.0x</span>
          <button type="button" onclick="zoomPhoto(0.5)" class="px-3 py-2 bg-white/10 hover:bg-white/20 rounded-[2px] touch-target-min">+ Zoom</button>
        </div>

        <div class="flex items-center gap-2">
          <button type="button" onclick="rotatePhoto()" class="px-3 py-2 bg-white/10 hover:bg-white/20 rounded-[2px] touch-target-min" title="Rotate 90°">↻ Rotate</button>
          <button type="button" onclick="resetPhotoTransform()" class="px-3 py-2 bg-white/10 hover:bg-white/20 rounded-[2px] touch-target-min">Reset</button>
        </div>
      </footer>
    </div>


    <!-- ========================================== -->
    <!-- MODAL: ADVANCED FILTER                     -->
    <!-- ========================================== -->
    <div id="filterModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded-[2px] w-full max-w-md shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-2">
            <span class="text-sm">⚙</span>
            <h2 class="font-serif font-bold text-sm text-ink">
              Advanced Filter
            </h2>
          </div>
          <button
            type="button"
            onclick="closeFilterModal()"
            class="p-1 text-ink-faint hover:text-ink rounded-[2px] text-sm font-bold"
          >
            ✕
          </button>
        </header>

        <div class="p-4 overflow-y-auto space-y-6 flex-1">
          <!-- Locations -->
          <div>
            <h3 class="font-sans text-xs font-bold text-ink mb-3 uppercase tracking-wider">Location Filters</h3>
            <div id="filterModalLocations" class="space-y-3">
              <!-- Dynamically populated -->
            </div>
          </div>

          <hr class="border-t border-tonal2" />

          <!-- Specific Problems -->
          <div>
            <h3 class="font-sans text-xs font-bold text-ink mb-3 uppercase tracking-wider">Specific Problems</h3>
            <div id="filterModalProblems" class="space-y-2">
              <!-- Dynamically populated -->
            </div>
          </div>
        </div>

        <footer class="p-3.5 bg-tonal1 border-t border-tonal2 flex gap-3 justify-end shrink-0">
          <button
            type="button"
            onclick="clearAdvancedFilters()"
            class="px-4 py-2 font-sans font-medium text-xs text-ink-muted hover:text-ink transition-colors rounded-[2px]"
          >
            Clear All
          </button>
          <button
            type="button"
            onclick="applyAdvancedFilters()"
            class="px-5 py-2 bg-fern hover:bg-fern-dark text-white font-sans font-bold text-xs transition-colors rounded-[2px]"
          >
            Apply Filters
          </button>
        </footer>
      </div>
    </div>


    <!-- ========================================== -->
    <!-- MODAL: ADD DISCREPANCY                     -->
    <!-- ========================================== -->
    <div id="addDiscrepancyModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded-[2px] w-full max-w-md shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between">
          <div class="flex items-center gap-2 text-ember">
            <span class="text-sm">⚑</span>
            <h2 class="font-serif font-bold text-sm text-ink">
              Flag Specimen Discrepancy
            </h2>
          </div>
          <button
            type="button"
            onclick="closeModal('addDiscrepancyModal')"
            class="p-1 text-ink-faint hover:text-ink rounded-[2px] text-sm font-bold"
          >
            ✕
          </button>
        </header>

        <form onsubmit="submitDiscrepancy(event)" class="p-4 space-y-3.5">
          <div>
            <label class="block font-sans text-xs font-medium text-ink mb-1">
              Target Field
            </label>
            <select
              id="discrepancyFieldSelect"
              class="w-full bg-surface border border-bordercol rounded-[2px] px-3 py-2 text-xs text-ink outline-none focus:border-fern"
            >
              <!-- Populated dynamically from schema -->
            </select>
          </div>

          <div>
            <label class="block font-sans text-xs font-medium text-ink mb-1">
              Severity Level
            </label>
            <div class="grid grid-cols-3 gap-2">
              <label class="border border-bordercol rounded-[2px] p-2 flex items-center gap-1.5 text-xs cursor-pointer hover:bg-tonal1">
                <input type="radio" name="severity" value="warning" checked class="text-ember">
                <span class="text-ember-dark font-medium">Warning</span>
              </label>
              <label class="border border-bordercol rounded-[2px] p-2 flex items-center gap-1.5 text-xs cursor-pointer hover:bg-tonal1">
                <input type="radio" name="severity" value="critical" class="text-red-600">
                <span class="text-red-700 font-medium">Critical</span>
              </label>
              <label class="border border-bordercol rounded-[2px] p-2 flex items-center gap-1.5 text-xs cursor-pointer hover:bg-tonal1">
                <input type="radio" name="severity" value="inquiry" class="text-blue-600">
                <span class="text-blue-700 font-medium">Inquiry</span>
              </label>
            </div>
          </div>

          <div>
            <label class="block font-sans text-xs font-medium text-ink mb-1">
              Discrepancy Reason / Note *
            </label>
            <textarea
              id="discrepancyReasonInput"
              rows="3"
              required
              placeholder="e.g. Inscription handwriting does not match genus determination..."
              class="w-full bg-surface border border-bordercol rounded-[2px] px-3 py-2 text-xs text-ink outline-none focus:border-fern"
            ></textarea>
          </div>

          <div class="flex items-center justify-end gap-2 pt-2 border-t border-tonal2">
            <button
              type="button"
              onclick="closeModal('addDiscrepancyModal')"
              class="px-3 py-2 border border-bordercol text-ink-muted hover:bg-tonal1 rounded-[2px] text-xs font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="px-4 py-2 bg-ember hover:bg-ember-dark text-white rounded-[2px] text-xs font-bold transition"
            >
              Flag Issue
            </button>
          </div>
        </form>
      </div>
    </div>


    <!-- ========================================== -->
    <!-- MODAL: CONNECTION STATUS                   -->
    <!-- ========================================== -->
    <div id="connectionModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded-[2px] w-full max-w-sm p-4 shadow-xl space-y-3">
        <div class="flex items-center justify-between border-b border-tonal2 pb-2">
          <h3 class="font-serif font-bold text-sm text-ink">⚡ Desktop Host Linked</h3>
          <button type="button" onclick="closeModal('connectionModal')" class="text-ink-muted font-bold text-sm">✕</button>
        </div>

        <div class="space-y-1.5 text-xs font-mono">
          <div class="flex justify-between py-1 border-b border-tonal2">
            <span class="text-ink-muted">Host Status:</span>
            <span class="text-fern-dark font-bold">Online (Active)</span>
          </div>
          <div class="flex justify-between py-1 border-b border-tonal2">
            <span class="text-ink-muted">Database:</span>
            <span class="text-ink font-bold" id="connModalDbName">---</span>
          </div>
          <div class="flex justify-between py-1 border-b border-tonal2">
            <span class="text-ink-muted">Reviewed Total:</span>
            <span class="text-ink" id="connModalReviewed">---</span>
          </div>
          <div class="flex justify-between py-1">
            <span class="text-ink-muted">Latency / Ping:</span>
            <span class="text-fern-dark font-bold" id="connModalPing">12ms</span>
          </div>
        </div>

        <button
          type="button"
          onclick="closeModal('connectionModal')"
          class="w-full py-2 bg-fern hover:bg-fern-dark text-white rounded-[2px] text-xs font-bold"
        >
          Done
        </button>
      </div>
    </div>

    <!-- Floating Toast Notification -->
    <div id="toast" class="hidden fixed top-4 left-4 right-4 max-w-sm mx-auto bg-fern-dark text-white text-xs font-bold py-2.5 px-4 rounded-[2px] shadow-lg text-center z-50 transition-opacity">
      Edits saved & synchronized
    </div>

  </div>

  <!-- ========================================== -->
  <!-- CLIENT APPLICATION SCRIPT                  -->
  <!-- ========================================== -->
  <script>
    const TOKEN = "{{ token }}";
    let activeSchema = null;
    let objectList = [];
    let currentOid = null;
    let currentRecord = null;
    let isReviewed = false;
    let activeStatusFilter = 'all';
    let noImageFilterActive = false;
    let activeAdvancedFilters = { locations: {}, problems: [] };
    let activeSortBy = 'location';
    let searchQuery = '';
    let searchDebounceTimer = null;
    let autoSaveTimer = null;
    let wakeLockSentinel = null;

    let historicalData = {};
    let revertState = {}; // field: originalValue

    async function fetchHistoricalData(oid) {
      try {
        const data = await apiFetch(`/api/object/${encodeURIComponent(oid)}/history`);
        historicalData = data.historical_data || {};
        injectHistoricalData();
      } catch (err) {
        console.error("Failed to fetch historical data:", err);
      }
    }

    function injectHistoricalData() {
        if (!historicalData || Object.keys(historicalData).length === 0) {
            return;
        }

        for (const [field, valuesMap] of Object.entries(historicalData)) {
            if (Object.keys(valuesMap).length === 0) continue;

            const fNameClean = field.replace(/[^a-zA-Z0-9_]/g, '_');
            const toggleBtn = document.getElementById(`history_toggle_${fNameClean}`);
            const container = document.getElementById(`history_container_${fNameClean}`);

            if (!toggleBtn || !container) continue;

            let currentVal = '';
            if (currentRecord.registration && currentRecord.registration[field] !== undefined) {
               currentVal = currentRecord.registration[field];
            } else if (currentRecord.observation && currentRecord.observation[field] !== undefined) {
               currentVal = currentRecord.observation[field];
            }
            let currentValDisp = currentVal ? String(currentVal) : "[BLANK]";

            let suggestionsHtml = '';
            for (const [val, sources] of Object.entries(valuesMap)) {
                const encodedVal = val.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                const sourceStr = sources.join(', ');
                suggestionsHtml += `
                    <div id="hist_sug_${fNameClean}_${encodedVal}" class="p-2.5 mt-1.5 bg-surface border border-bordercol rounded-[2px] cursor-pointer touch-target-min touch-press transition group" onclick="stageHistoricalValue('${field}', '${encodedVal}')">
                        <div class="flex items-center justify-between gap-2">
                            <div class="font-mono text-xs text-ink group-[.staged]:font-bold group-[.staged]:text-ember truncate">${encodedVal}</div>
                            <button type="button" class="hidden group-[.staged]:inline-flex min-h-[36px] bg-ember text-white px-3 py-1.5 text-xs rounded-[2px] font-bold shadow-xs items-center justify-center shrink-0" onclick="event.stopPropagation(); applyHistoricalValue('${field}', '${encodedVal}')">Apply</button>
                        </div>
                        <div class="font-sans text-[10px] text-ink-muted mt-1">Sources: <span class="font-mono">${sourceStr}</span></div>
                    </div>
                `;
            }

            let undoBtn = '';
            if (revertState.hasOwnProperty(field)) {
                 const orig = revertState[field].replace(/'/g, "\\'").replace(/"/g, '&quot;');
                 undoBtn = `<button type="button" onclick="undoHistoricalValue('${field}', '${orig}')" class="text-[11px] text-ember hover:underline font-bold bg-ember-light px-2 py-1 border border-ember-border rounded-[2px] touch-press">Undo Change</button>`;
            }

            container.innerHTML = `
                <div class="flex items-center justify-between mb-1.5">
                    <span class="text-[10px] font-sans font-bold text-ink-muted uppercase tracking-wider">History Suggestions</span>
                    ${undoBtn}
                </div>
                <div class="text-xs font-mono text-ink-muted mb-2">Current: <span class="text-ink font-semibold">${currentValDisp}</span></div>
                ${suggestionsHtml}
            `;

            // Unhide the toggle button since there is history available
            toggleBtn.classList.remove('hidden');
        }
    }

    function toggleHistoryContainer(field) {
        const fNameClean = field.replace(/[^a-zA-Z0-9_]/g, '_');
        const container = document.getElementById(`history_container_${fNameClean}`);
        if (container) {
            container.classList.toggle('hidden');
        }
    }

    function stageHistoricalValue(field, value) {
        const fNameClean = field.replace(/[^a-zA-Z0-9_]/g, '_');
        const container = document.getElementById(`history_container_${fNameClean}`);
        if (!container) return;

        // Reset all suggestion cards in this container
        const suggestions = container.querySelectorAll('[id^="hist_sug_"]');
        suggestions.forEach(sug => {
            sug.classList.remove('staged', 'bg-ember-light', 'border-ember', 'ring-1', 'ring-ember');
            sug.classList.add('bg-surface', 'border-bordercol');
        });

        // Apply distinct staged styling to selected card
        const suggestionId = `hist_sug_${fNameClean}_${value}`;
        const selectedSug = document.getElementById(suggestionId);
        if (selectedSug) {
            selectedSug.classList.remove('bg-surface', 'border-bordercol');
            selectedSug.classList.add('staged', 'bg-ember-light', 'border-ember', 'ring-1', 'ring-ember');
        }
    }

    async function applyHistoricalValue(field, value) {
        // Find input element for this field
        const inputs = document.querySelectorAll(`[data-field="${field}"]`);
        if (inputs.length === 0) {
            showToast(`Field ${field} not found in form`, true);
            return;
        }

        const input = inputs[0];

        // Save revert state if not already saved
        if (!revertState.hasOwnProperty(field)) {
             revertState[field] = input.type === 'checkbox' ? (input.checked ? 'true' : 'false') : input.value;
        }

        // Apply
        if (input.type === 'checkbox') {
             input.checked = (value.toLowerCase() === 'true' || value === '1' || value === 'yes');
        } else {
             input.value = value;
        }

        // Micro-interaction: Flash the updated input with fern border to confirm receipt
        input.classList.add('ring-2', 'ring-fern', 'border-fern');
        setTimeout(() => {
            input.classList.remove('ring-2', 'ring-fern', 'border-fern');
        }, 1200);

        // Clear related problems locally
        if (currentRecord.observation) {
            const probKeys = Object.keys(currentRecord.observation).filter(k => k === field + '_Problem' || (activeSchema.ui_sections.problems && activeSchema.ui_sections.problems.some(p => p.name === k && p.target === field))); // Assuming target might exist, or just clear exact match

            // For Arbor, problem fields usually match `${field}_Problem` or similar, let's clear it
            const exactProb = `${field}_Problem`;
            if (currentRecord.observation.hasOwnProperty(exactProb)) {
                 currentRecord.observation[exactProb] = false;
                 const probToggle = document.getElementById(`prob_${exactProb}`);
                 if (probToggle) probToggle.checked = false;
            }
        }

        // Trigger save and update UI
        triggerAutoSave();
        showToast(`Applied historical value for ${field}`);

        // Update local currentRecord so rendering reflects changes
        if (currentRecord.registration && currentRecord.registration[field] !== undefined) {
             currentRecord.registration[field] = value;
        } else if (currentRecord.observation && currentRecord.observation[field] !== undefined) {
             currentRecord.observation[field] = value;
        }

        // Re-inject history UI for this field to show new current value
        injectHistoricalData();

        // Hide the container after application
        const fNameClean = field.replace(/[^a-zA-Z0-9_]/g, '_');
        const container = document.getElementById(`history_container_${fNameClean}`);
        if (container) {
            container.classList.add('hidden');
        }
    }

    async function undoHistoricalValue(field, originalValue) {
        if (!revertState.hasOwnProperty(field)) return;

        const inputs = document.querySelectorAll(`[data-field="${field}"]`);
        if (inputs.length > 0) {
            const input = inputs[0];
            if (input.type === 'checkbox') {
                 input.checked = (originalValue.toLowerCase() === 'true' || originalValue === '1' || originalValue === 'yes');
            } else {
                 input.value = originalValue;
            }
        }

        if (currentRecord.registration && currentRecord.registration[field] !== undefined) {
             currentRecord.registration[field] = originalValue;
        } else if (currentRecord.observation && currentRecord.observation[field] !== undefined) {
             currentRecord.observation[field] = originalValue;
        }

        delete revertState[field];

        triggerAutoSave();
        showToast(`Reverted ${field} to original value`);
        injectHistoricalData();
    }



    // Photo viewer state
    let photoUrls = [];
    let currentPhotoIdx = 0;
    let photoZoom = 1;
    let photoRotation = 0;
    let photoPan = { x: 0, y: 0 };
    let isDraggingPhoto = false;
    let photoDragStart = { x: 0, y: 0 };

    async function apiFetch(url, options = {}) {
      options.headers = options.headers || {};
      options.headers['X-Session-Token'] = TOKEN;
      options.headers['Content-Type'] = 'application/json';
      const sep = url.includes('?') ? '&' : '?';
      try {
        const res = await fetch(`${url}${sep}token=${encodeURIComponent(TOKEN)}`, options);
        if (!res.ok) {
          console.warn(`API response status ${res.status} for ${url}`);
        }
        return await res.json();
      } catch (err) {
        console.error(`Fetch error on ${url}:`, err);
        return {};
      }
    }

    function showToast(msg, isError = false) {
      const toast = document.getElementById('toast');
      toast.textContent = msg;
      toast.className = `fixed top-4 left-4 right-4 max-w-sm mx-auto ${isError ? 'bg-ember-dark' : 'bg-fern-dark'} text-white text-xs font-bold py-2.5 px-4 rounded-[2px] shadow-lg text-center z-50 transition-opacity`;
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 2200);
    }

    function openModal(id) {
      document.getElementById(id).classList.remove('hidden');
    }

    function closeModal(id) {
      document.getElementById(id).classList.add('hidden');
    }

    // ==========================================
    // INITIALIZATION & SCHEMA LOADING
    // ==========================================
    async function init() {
      try {
        // 1. Fetch Schema from Master config.py
        activeSchema = await apiFetch('/api/schema');
        const dbName = (activeSchema && activeSchema.database_name) ? activeSchema.database_name : 'Active Database';
        document.getElementById('headerDbName').textContent = dbName;
        document.getElementById('connModalDbName').textContent = dbName;

        // 2. Fetch Initial List
        await fetchList();

        // 3. Populate Discrepancy Field Select Options
        populateDiscrepancyFields();

        // 4. Setup SSE live events + reconnect on mobile wake & network online
        setupEventSource();
        document.addEventListener('visibilitychange', () => {
          if (document.visibilityState === 'visible') {
            setupEventSource();  // closes stale connection and opens a fresh one
          }
        });
        window.addEventListener('online', () => setupEventSource());
        window.addEventListener('offline', () => updateConnectionState('disconnected'));
      } catch (err) {
        console.error("Initialization error:", err);
        document.getElementById('headerDbName').textContent = 'Database Connected';
        fetchList();
      }
    }

    let _evtSource = null;

    function updateConnectionState(state) {
      const badge = document.getElementById('pingBadge');
      const footerHost = document.getElementById('footerTickerHost');
      const dotHeader = document.getElementById('connPingDot');
      const dotHeaderAnim = document.getElementById('connPingDotAnimate');
      const dotFooter = document.getElementById('footerConnDot');
      const dotFooterAnim = document.getElementById('footerConnDotAnimate');
      const offlineBanner = document.getElementById('offlineBanner');

      if (state === 'connected') {
        if (badge) badge.textContent = 'Live';
        if (footerHost) footerHost.textContent = 'Host Connected';
        if (offlineBanner) offlineBanner.classList.add('hidden');
        [dotHeader, dotFooter].forEach(d => { if (d) d.className = 'relative inline-flex rounded-full h-2 w-2 bg-fern'; });
        [dotHeaderAnim, dotFooterAnim].forEach(d => { if (d) d.className = 'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-fern'; });
      } else if (state === 'connecting') {
        if (badge) badge.textContent = 'Connecting...';
        if (footerHost) footerHost.textContent = 'Connecting to host...';
        [dotHeader, dotFooter].forEach(d => { if (d) d.className = 'relative inline-flex rounded-full h-2 w-2 bg-ember'; });
        [dotHeaderAnim, dotFooterAnim].forEach(d => { if (d) d.className = 'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-ember'; });
      } else {
        if (badge) badge.textContent = 'Offline';
        if (footerHost) footerHost.textContent = 'Host Disconnected';
        if (offlineBanner) offlineBanner.classList.remove('hidden');
        [dotHeader, dotFooter].forEach(d => { if (d) d.className = 'relative inline-flex rounded-full h-2 w-2 bg-ember-dark'; });
        [dotHeaderAnim, dotFooterAnim].forEach(d => { if (d) d.className = 'hidden'; });
      }
    }

    function setupEventSource() {
      try {
        if (_evtSource) { _evtSource.close(); _evtSource = null; }
        updateConnectionState('connecting');
        _evtSource = new EventSource(`/api/events?token=${encodeURIComponent(TOKEN)}`);

        _evtSource.onopen = function() {
          updateConnectionState('connected');
        };

        _evtSource.onerror = function() {
          updateConnectionState('disconnected');
        };

        _evtSource.onmessage = function(e) {
          try {
            const data = JSON.parse(e.data);
            if (data.type === 'record_updated') {
              if (document.getElementById('listView').classList.contains('hidden') && currentOid === data.data.id) {
                // Background notification — no action needed
              } else if (!document.getElementById('listView').classList.contains('hidden')) {
                fetchList();
              }
            }
          } catch(err) {}
        };
      } catch(err) {
        updateConnectionState('disconnected');
      }
    }

    // ==========================================
    // SCREEN WAKE LOCK (WALK MODE)
    // ==========================================
    async function toggleWakeLock() {
      const btn = document.getElementById('btnWakeLock');
      const icon = document.getElementById('wakeLockIcon');
      if (wakeLockSentinel) {
        await wakeLockSentinel.release();
        wakeLockSentinel = null;
        btn.className = 'p-2 rounded-[2px] border transition-colors touch-target-min bg-ink text-surface border-ink hover:bg-ink-muted flex items-center justify-center';
        icon.innerText = '🌙';
        icon.classList.remove('animate-spin-slow');
        showToast('Walk Mode Deactivated (Sleep Allowed)');
      } else if ('wakeLock' in navigator) {
        try {
          wakeLockSentinel = await navigator.wakeLock.request('screen');
          btn.className = 'p-2 rounded-[2px] border transition-colors touch-target-min bg-surface text-ink-muted border-bordercol hover:bg-tonal1 flex items-center justify-center';
          icon.innerText = '☀️';
          icon.classList.add('animate-spin-slow');
          showToast('Walk Mode Active (Screen Sleep Prevented)');
          wakeLockSentinel.addEventListener('release', () => {
            wakeLockSentinel = null;
            btn.className = 'p-2 rounded-[2px] border transition-colors touch-target-min bg-ink text-surface border-ink hover:bg-ink-muted flex items-center justify-center';
            icon.innerText = '🌙';
            icon.classList.remove('animate-spin-slow');
          });
        } catch (err) {
          showToast('Wake Lock unavailable on this device', true);
        }
      } else {
        showToast('Wake Lock API not supported on this browser', true);
      }
    }

    // ==========================================
    // SPECIMEN LIST RENDERING & SEARCH
    // ==========================================
    function debounceSearch() {
      clearTimeout(searchDebounceTimer);
      searchQuery = document.getElementById('searchBox').value.trim();
      const clearBtn = document.getElementById('searchClearBtn');
      if (searchQuery) clearBtn.classList.remove('hidden');
      else clearBtn.classList.add('hidden');
      searchDebounceTimer = setTimeout(fetchList, 350);
    }

    function clearSearch() {
      document.getElementById('searchBox').value = '';
      document.getElementById('searchClearBtn').classList.add('hidden');
      searchQuery = '';
      fetchList();
    }

    function setStatusFilter(status) {
      activeStatusFilter = status;
      const filterStyles = {
        all: {
          active: 'bg-ink text-white border-ink font-semibold',
          inactive: 'bg-surface text-ink-muted border-bordercol hover:bg-tonal1'
        },
        pending: {
          active: 'bg-ink text-white border-ink font-semibold',
          inactive: 'bg-surface text-ink-muted border-bordercol hover:bg-tonal1'
        },
        flagged: {
          active: 'bg-ember text-white border-ember shadow-xs font-semibold',
          inactive: 'bg-ember-light text-ember-dark border-ember-border hover:bg-ember-light/80'
        },
        reviewed: {
          active: 'bg-fern text-white border-fern shadow-xs font-semibold',
          inactive: 'bg-fern-light text-fern-dark border-fern-border hover:bg-fern-light/80'
        }
      };

      ['all', 'pending', 'flagged', 'reviewed'].forEach(s => {
        const pill = document.getElementById(`pill-${s}`);
        if (!pill) return;
        const isSelected = (s === status);
        const styleRule = filterStyles[s];
        pill.className = `min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border transition-colors touch-press flex items-center justify-center gap-1.5 ${isSelected ? styleRule.active : styleRule.inactive}`;
      });
      fetchList();
    }

    function handleSortChange() {
      activeSortBy = document.getElementById('sortBySelect').value;
      renderList();
    }

    function toggleNoImageFilter() {
      noImageFilterActive = !noImageFilterActive;
      const pill = document.getElementById('pill-no-image');
      if (noImageFilterActive) {
        pill.className = 'min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center justify-center gap-1.5 transition-colors bg-ink text-white border-ink';
      } else {
        pill.className = 'min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center justify-center gap-1.5 transition-colors bg-surface text-ink-muted border-bordercol hover:bg-tonal1';
      }
      fetchList();
    }

    function openFilterModal() {
      // Populate Location Filters
      const locContainer = document.getElementById('filterModalLocations');
      locContainer.innerHTML = '';
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.location) {
        activeSchema.ui_sections.location.forEach(field => {
          if (field.type === 'checkbox') return; // Skip bool locations for simplicity, or implement if needed

          let inputHtml = '';
          if (field.type === 'choice' && field.choices) {
            inputHtml = `
              <select id="filter_loc_${field.name}" class="w-full bg-surface border border-bordercol rounded-[2px] px-2.5 py-1.5 text-xs font-sans text-ink outline-none focus:border-fern cursor-pointer">
                <option value="">Any ${field.name}</option>
                ${field.choices.map(c => `<option value="${c}" ${activeAdvancedFilters.locations[field.name] === c ? 'selected' : ''}>${c}</option>`).join('')}
              </select>
            `;
          } else {
            inputHtml = `
              <input type="text" id="filter_loc_${field.name}" placeholder="Any ${field.name}..." value="${activeAdvancedFilters.locations[field.name] || ''}" class="w-full bg-surface border border-bordercol rounded-[2px] px-2.5 py-1.5 text-xs font-sans text-ink placeholder:text-ink-faint outline-none focus:border-fern" />
            `;
          }

          locContainer.innerHTML += `
            <div>
              <label class="block text-[11px] font-bold text-ink-muted mb-1">${field.name}</label>
              ${inputHtml}
            </div>
          `;
        });
      }

      // Populate Specific Problems
      const probContainer = document.getElementById('filterModalProblems');
      probContainer.innerHTML = '';

      // Static specific problems
      let staticProblems = [
        { name: "Any_Problem", label: "Any problem (except images)" },
        { name: "Images_Missing", label: "Missing Images" }
      ];

      let dynamicProblems = [];
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.problems) {
        dynamicProblems = activeSchema.ui_sections.problems.map(p => {
          return { name: p.name, label: p.name.replace('_Problem', '').replace(/_/g, ' ') };
        });
      }

      const allProblems = staticProblems.concat(dynamicProblems);

      allProblems.forEach(p => {
        const isChecked = activeAdvancedFilters.problems.includes(p.name);
        probContainer.innerHTML += `
          <label class="flex items-center gap-2 p-1.5 rounded-[2px] hover:bg-tonal1 cursor-pointer">
            <input type="checkbox" id="filter_prob_${p.name}" value="${p.name}" ${isChecked ? 'checked' : ''} class="w-4 h-4 text-fern rounded-[2px] border-bordercol cursor-pointer" />
            <span class="text-xs font-sans text-ink">${p.label}</span>
          </label>
        `;
      });

      openModal('filterModal');
    }

    function closeFilterModal() {
      closeModal('filterModal');
    }

    function applyAdvancedFilters() {
      // Gather Locations
      activeAdvancedFilters.locations = {};
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.location) {
        activeSchema.ui_sections.location.forEach(field => {
          if (field.type === 'checkbox') return;
          const el = document.getElementById(`filter_loc_${field.name}`);
          if (el && el.value.trim()) {
            activeAdvancedFilters.locations[field.name] = el.value.trim();
          }
        });
      }

      // Gather Problems
      activeAdvancedFilters.problems = [];
      const probCheckboxes = document.querySelectorAll('#filterModalProblems input[type="checkbox"]');
      probCheckboxes.forEach(cb => {
        if (cb.checked) {
          activeAdvancedFilters.problems.push(cb.value);
        }
      });

      closeFilterModal();
      fetchList();
    }

    function clearAdvancedFilters() {
      activeAdvancedFilters = { locations: {}, problems: [] };
      closeFilterModal();
      fetchList();
    }

    async function fetchList() {
      try {
        let url = `/api/objects?limit=150&q=${encodeURIComponent(searchQuery)}`;
        if (activeStatusFilter !== 'all') {
          url += `&status=${encodeURIComponent(activeStatusFilter)}`;
        }

        // Append No Image filter
        if (noImageFilterActive) {
          // If we also had specific problems, we append it, but handled below
        }

        // Append Location Filters
        for (const [key, val] of Object.entries(activeAdvancedFilters.locations)) {
          url += `&loc_${encodeURIComponent(key)}=${encodeURIComponent(val)}`;
        }

        // Append Specific Problems (merge with No Image pill logic)
        let combinedProblems = [...activeAdvancedFilters.problems];
        if (noImageFilterActive && !combinedProblems.includes('Images_Missing')) {
          combinedProblems.push('Images_Missing');
        }

        if (combinedProblems.length > 0) {
          url += `&specific_problems=${encodeURIComponent(combinedProblems.join(','))}`;
        }
        const res = await apiFetch(url);
        objectList = res.objects || [];

        // Update counts safely
        const facets = res.facets || {};
        const revCount = facets.reviewed_count || 0;
        const pendCount = facets.pending_count || 0;
        const flaggedCount = facets.flagged_count !== undefined 
          ? facets.flagged_count 
          : objectList.filter(o => o.has_flags).length;
        const total = res.total_matching !== undefined ? res.total_matching : objectList.length;

        document.getElementById('matchingCount').textContent = total;
        document.getElementById('pill-all').textContent = `All (${total})`;
        document.getElementById('pill-pending').innerHTML = `<span>🕒</span> <span>Unreviewed (${pendCount})</span>`;
        document.getElementById('pill-flagged').innerHTML = `<span>⚠</span> <span>Flagged (${flaggedCount})</span>`;
        document.getElementById('pill-reviewed').innerHTML = `<span>✓</span> <span>Reviewed (${revCount})</span>`;
        document.getElementById('connModalReviewed').textContent = `${revCount} / ${total} items`;

        renderList();
      } catch (err) {
        console.error("Failed to fetch specimen list:", err);
      }
    }

    // Substring-based highlight without regex escaping hazards
    function highlightMatch(text, query) {
      if (!query || !text) return text || '';
      const str = String(text);
      const q = query.trim().toLowerCase();
      if (!q) return str;
      const idx = str.toLowerCase().indexOf(q);
      if (idx === -1) return str;
      const match = str.substring(idx, idx + q.length);
      return str.substring(0, idx) + '<mark class="bg-ember-light text-ember font-semibold px-0.5 rounded-[1px]">' + match + '</mark>' + str.substring(idx + q.length);
    }

    function renderList() {
      const container = document.getElementById('specimenListContainer');
      if (objectList.length === 0) {
        container.innerHTML = `
          <div class="bg-surface border border-bordercol rounded-[2px] p-8 text-center mt-4">
            <span class="text-3xl text-ink-faint">🌿</span>
            <p class="font-serif font-bold text-base text-ink mt-2">No specimens match filter</p>
            <p class="font-sans text-xs text-ink-muted mt-1">If no database is currently loaded, please open an Excel database in Arbor Desktop.</p>
          </div>
        `;
        return;
      }

      // Sort in-place if requested
      const sorted = [...objectList].sort((a, b) => {
        if (activeSortBy === 'name-asc') return (a.scientific_name || '').localeCompare(b.scientific_name || '');
        if (activeSortBy === 'name-desc') return (b.scientific_name || '').localeCompare(a.scientific_name || '');
        if (activeSortBy === 'id-asc') return (a.id || '').localeCompare(b.id || '', undefined, { numeric: true });
        return 0; // default server order
      });

      container.innerHTML = sorted.map(s => {
        const isRev = s.review_status === 'reviewed';
        const statusBadge = isRev
          ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[10px] font-sans font-semibold bg-fern-light text-fern-dark border border-fern-border">✓ REVIEWED</span>`
          : (s.has_flags
            ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[10px] font-sans font-semibold bg-ember-light text-ember-dark border border-ember-border">⚠ FLAGGED</span>`
            : `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[10px] font-sans font-medium bg-tonal1 text-ink-muted border border-bordercol">🕒 UNREVIEWED</span>`);

        let locStr = [];
        if (s.location) {
          if (s.location.building) locStr.push(s.location.building);
          if (s.location.floor) locStr.push(`Fl ${s.location.floor}`);
          if (s.location.cabinet) locStr.push(`Cab ${s.location.cabinet}`);
          if (s.location.stored_as) locStr.push(s.location.stored_as);
        }
        const locDisplay = locStr.join(' • ') || 'Location unrecorded';

        return `
          <div
            onclick="loadSpecimen('${s.id}')"
            class="bg-surface border border-bordercol hover:border-borderdark rounded-[2px] p-3.5 transition-all cursor-pointer touch-press shadow-xs"
          >
            <div class="flex items-center justify-between mb-1.5">
              <div class="flex items-center gap-1.5">
                <span class="font-mono text-xs font-bold text-ink-muted">
                  ${highlightMatch(s.accession_number || s.id, searchQuery)}
                </span>
                ${s.family ? `<span class="font-sans text-[10px] text-ink-faint bg-tonal1 px-1.5 py-0.2 rounded-[1px] border border-tonal3">${highlightMatch(s.family, searchQuery)}</span>` : ''}
              </div>
              ${statusBadge}
            </div>

            <h2 class="font-serif italic font-bold text-base text-ink leading-snug">
              ${highlightMatch(s.scientific_name, searchQuery)}
            </h2>

            <div class="flex items-center gap-2 text-xs font-sans text-ink-muted mt-0.5">
              ${s.author ? `<span class="text-ink font-medium">${highlightMatch(s.author, searchQuery)}</span>` : ''}
              ${s.collector ? `<span>•</span> <span class="truncate max-w-[140px]">👤 ${highlightMatch(s.collector, searchQuery)}</span>` : ''}
            </div>

            <div class="flex items-center justify-between mt-2.5 pt-2 border-t border-tonal2 text-xs">
              <div class="flex items-center gap-1.5 text-ink truncate max-w-[240px]">
                <span class="text-fern text-xs">📍</span>
                <span class="font-mono text-[11px] text-ink-muted truncate">${locDisplay}</span>
              </div>
              <div class="flex items-center gap-1 text-[11px] font-sans font-medium text-fern shrink-0">
                <span>Inspect</span>
                <span>&gt;</span>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    function showListView() {
      document.getElementById('detailView').classList.add('hidden');
      document.getElementById('listView').classList.remove('hidden');
      fetchList();
    }

    function showDetailView() {
      document.getElementById('listView').classList.add('hidden');
      document.getElementById('detailView').classList.remove('hidden');
    }

    // ==========================================
    // SPECIMEN DETAIL VIEW & DYNAMIC FORM ENGINE
    // ==========================================
    async function loadSpecimen(oid) {
      // Flush any pending debounced save for the outgoing specimen BEFORE currentOid changes.
      // Without this, navigating via prev/next saves the old form data under the new specimen's OID.
      if (autoSaveTimer !== null) {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = null;
        if (currentOid && currentOid !== oid) {
          await saveCurrentEdits();
        }
      }
      currentOid = oid;
      showDetailView();

      // Reset scroll position to top
      document.querySelector('#detailView main').scrollTop = 0;

      // Update Nav Index
      const idx = objectList.findIndex(o => o.id === oid);
      if (idx !== -1) {
        document.getElementById('detailNavIndex').textContent = `${idx + 1} of ${objectList.length}`;
        document.getElementById('btnPrevSpecimen').disabled = (idx === 0);
        document.getElementById('btnNextSpecimen').disabled = (idx === objectList.length - 1);
      }

      // Set Instant Loading State (Clears stale specimen data)
      document.getElementById('detailAccession').textContent = `#${oid}`;
      document.getElementById('detailScientificName').innerHTML = '<span class="text-ink-muted animate-pulse font-serif italic">Loading specimen record...</span>';
      document.getElementById('detailAuthor').textContent = '';
      document.getElementById('detailFamily').textContent = '';
      document.getElementById('detailTopLocation').textContent = 'Location: Retrieving...';
      document.getElementById('detailReviewStatusBadge').innerHTML = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[10px] font-sans font-medium bg-tonal2 text-ink-muted border border-bordercol animate-pulse">⏳ LOADING</span>';
      
      // Skeleton placeholders for accordions
      document.getElementById('detailAccordionsContainer').innerHTML = `
        <div class="bg-surface border border-bordercol rounded-[2px] p-4 space-y-3 animate-pulse">
          <div class="h-4 bg-tonal2 rounded-[2px] w-1/3"></div>
          <div class="h-9 bg-tonal1 rounded-[2px] w-full"></div>
          <div class="h-9 bg-tonal1 rounded-[2px] w-full"></div>
        </div>
      `;

      // Reset Photo State
      document.getElementById('photoPlaceholder').classList.remove('hidden');
      document.getElementById('specimenImg').classList.add('hidden');
      document.getElementById('photoWatermark').classList.add('hidden');
      document.getElementById('specimenImg').src = '';
      const thumbStrip = document.getElementById('photoThumbStrip');
      if (thumbStrip) {
        thumbStrip.classList.add('hidden');
        thumbStrip.innerHTML = '';
      }

      try {
        const data = await apiFetch(`/api/object/${encodeURIComponent(oid)}`);
        currentRecord = data;
        isReviewed = (data.review_status === 'reviewed');

        // Top Summary Info
        document.getElementById('detailAccession').textContent = `#${data.accession_number || data.id}`;
        document.getElementById('detailScientificName').textContent = data.scientific_name || 'Specimen';
        document.getElementById('detailAuthor').textContent = data.registration ? (data.registration.Author || '') : '';
        document.getElementById('detailFamily').textContent = data.registration ? (data.registration.Family || '') : '';

        let locStr = [];
        if (data.observation) {
          if (data.observation.Building) locStr.push(data.observation.Building);
          if (data.observation.Floor) locStr.push(`Floor ${data.observation.Floor}`);
          if (data.observation.Cabinet) locStr.push(`Cab ${data.observation.Cabinet}`);
          if (data.observation["Stored as"]) locStr.push(data.observation["Stored as"]);
        }
        document.getElementById('detailTopLocation').textContent = locStr.length > 0 ? `Location: ${locStr.join(' • ')}` : 'Location: Unrecorded';

        updateReviewButtonUI();

        // Load Photos & Thumbnails
        photoUrls = (data.images && data.images.online_urls) ? data.images.online_urls : [];
        document.getElementById('photoCountBadge').textContent = `${photoUrls.length} available`;
        const mainContainer = document.getElementById('photoMainContainer');
        const placeholder = document.getElementById('photoPlaceholder');
        const specimenImg = document.getElementById('specimenImg');
        const watermark = document.getElementById('photoWatermark');

        if (photoUrls.length > 0) {
          currentPhotoIdx = 0;
          specimenImg.src = photoUrls[0];
          placeholder.classList.add('hidden');
          specimenImg.classList.remove('hidden');
          watermark.classList.remove('hidden');
          mainContainer.classList.add('cursor-pointer');
          mainContainer.classList.remove('cursor-default');
          renderPhotoThumbnails();
        } else {
          placeholder.innerHTML = `
            <span class="text-2xl text-ink-faint">📷</span>
            <p class="font-sans text-xs font-semibold text-ink-muted">No Archival Scans Attached</p>
            <p class="font-mono text-[10px] text-ink-faint">Attach images in desktop catalog</p>
          `;
          placeholder.classList.remove('hidden');
          specimenImg.classList.add('hidden');
          watermark.classList.add('hidden');
          mainContainer.classList.remove('cursor-pointer');
          mainContainer.classList.add('cursor-default');
          const strip = document.getElementById('photoThumbStrip');
          if (strip) { strip.classList.add('hidden'); strip.innerHTML = ''; }
        }

        // Render Dynamic Forms Driven by config.py
        renderDynamicForm(activeSchema, data);

        // Render Problems & Discrepancies
        renderDiscrepancies(data);

        // Fetch Historical Data
        revertState = {};
        fetchHistoricalData(oid);

      } catch (err) {
        console.error("Failed to load specimen details:", err);
        document.getElementById('detailScientificName').textContent = 'Error Loading Specimen';
        showToast('Failed to load specimen data from host', true);
      }
    }

    function navSpecimen(offset) {
      const idx = objectList.findIndex(o => o.id === currentOid);
      if (idx !== -1 && objectList[idx + offset]) {
        loadSpecimen(objectList[idx + offset].id);
      }
    }

    // ==========================================
    // DYNAMIC SCHEMA-DRIVEN FORM GENERATOR
    // ==========================================
    function renderDynamicForm(schema, record) {
      const container = document.getElementById('detailAccordionsContainer');
      if (!schema || !schema.ui_sections) {
        container.innerHTML = '';
        return;
      }

      const uiSec = schema.ui_sections;
      const regGroups = uiSec.reg_groups || [];
      const regFields = uiSec.registration || [];
      const locFields = uiSec.location || [];

      let html = '';

      // 1. Render Registration Groups from config.py
      regGroups.forEach((grp, gIdx) => {
        const isTaxonomy = grp.name.toLowerCase().includes('tax');
        const icon = isTaxonomy ? '🧬' : (grp.name.toLowerCase().includes('collect') ? '📦' : (grp.name.toLowerCase().includes('obj') ? '🌿' : (grp.name.toLowerCase().includes('note') ? '📝' : '🔒')));
        const isOpen = (gIdx <= 1); // First two open by default

        let fieldsHtml = '';
        grp.fields.forEach(fName => {
          const fDef = regFields.find(f => f.name === fName) || { name: fName, type: 'text' };
          const val = (record.registration && record.registration[fName] !== undefined) ? record.registration[fName] : '';
          fieldsHtml += renderFieldInput(fDef, val, 'registration');
        });

        html += `
          <div class="bg-surface border border-bordercol rounded-[2px] shadow-xs overflow-hidden accordion ${isOpen ? 'acc-open' : ''}">
            <button
              type="button"
              onclick="toggleAccordion(this)"
              class="w-full p-3 flex items-center justify-between bg-tonal1 hover:bg-tonal2 transition focus:outline-none touch-press border-b border-bordercol text-left"
            >
              <div class="flex items-center gap-2.5">
                <span class="text-base">${icon}</span>
                <div>
                  <h3 class="font-bold text-xs text-ink uppercase tracking-wider">${grp.name}</h3>
                  <p class="text-[10px] text-ink-muted">${grp.fields.join(' • ')}</p>
                </div>
              </div>
              <span class="acc-icon text-ink-muted font-bold transition-transform duration-200 text-xs">▼</span>
            </button>
            <div class="p-3.5 space-y-3 acc-content ${isOpen ? 'block' : 'hidden'}">
              ${fieldsHtml}
            </div>
          </div>
        `;
      });

      // 2. Render Physical Location Group from config.py
      if (locFields.length > 0) {
        let locFieldsHtml = '';
        locFields.forEach(fDef => {
          const val = (record.observation && record.observation[fDef.name] !== undefined) ? record.observation[fDef.name] : '';
          locFieldsHtml += renderFieldInput(fDef, val, 'observation');
        });

        html += `
          <div class="bg-surface border border-bordercol rounded-[2px] shadow-xs overflow-hidden accordion acc-open">
            <button
              type="button"
              onclick="toggleAccordion(this)"
              class="w-full p-3 flex items-center justify-between bg-tonal1 hover:bg-tonal2 transition focus:outline-none touch-press border-b border-bordercol text-left"
            >
              <div class="flex items-center gap-2.5">
                <span class="text-base">📍</span>
                <div>
                  <h3 class="font-bold text-xs text-ink uppercase tracking-wider">Physical Storage Location</h3>
                  <p class="text-[10px] text-ink-muted">Museum coordinates & storage trait</p>
                </div>
              </div>
              <span class="acc-icon text-ink-muted font-bold transition-transform duration-200 text-xs">▼</span>
            </button>
            <div class="p-3.5 space-y-3 acc-content block">
              ${locFieldsHtml}
            </div>
          </div>
        `;
      }

      container.innerHTML = html;
    }

    function renderFieldInput(field, value, section) {
      const fName = field.name;
      const fType = field.type || 'text';
      const isReadOnly = !!field.readonly;
      const inputId = `input_${section}_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;

      const toggleBtnId = `history_toggle_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;
      const containerId = `history_container_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;

      const historyControls = `
        <button
          type="button"
          id="${toggleBtnId}"
          onclick="toggleHistoryContainer('${fName}')"
          class="hidden min-h-[44px] px-2.5 py-1.5 text-xs font-sans font-medium text-ember bg-ember-light border border-ember-border rounded-[2px] touch-target-min touch-press ml-1 flex items-center gap-1"
          title="View historical value suggestions"
        >
          <span>📖</span>
          <span>History</span>
        </button>
        ${!isReadOnly ? `
          <button
            type="button"
            onclick="openAddDiscrepancyModal('${fName}')"
            class="min-h-[44px] px-2.5 py-1.5 text-xs font-sans font-medium text-ink-muted hover:text-ember bg-tonal1 hover:bg-tonal2 border border-bordercol rounded-[2px] touch-target-min touch-press ml-1 flex items-center gap-1"
            title="Flag discrepancy for ${fName}"
          >
            <span>⚑</span>
            <span>Flag</span>
          </button>
        ` : ''}
      `;

      const historyContainerHtml = `
        <div id="${containerId}" class="hidden mt-2 p-2.5 bg-tonal1 border border-bordercol rounded-[2px] shadow-xs">
           <!-- History suggestions injected here -->
        </div>
      `;

      // Choice / Select
      if (fType === 'choice' && Array.isArray(field.choices)) {
        const optionsHtml = ['<option value="">Select option...</option>']
          .concat(field.choices.map(c => `<option value="${c}" ${String(value) === String(c) ? 'selected' : ''}>${c}</option>`))
          .join('');

        return `
          <div class="space-y-1">
            <div class="flex items-center justify-between min-h-[32px]">
              <label for="${inputId}" class="text-xs font-bold text-ink">${fName}</label>
              <div class="flex items-center">${historyControls}</div>
            </div>
            <select
              id="${inputId}"
              data-section="${section}"
              data-field="${fName}"
              onchange="triggerAutoSave()" onblur="saveCurrentEdits()"
              class="w-full min-h-[44px] bg-surface border border-bordercol rounded-[2px] px-3 py-2 text-xs text-ink outline-none focus:border-fern cursor-pointer"
            >
              ${optionsHtml}
            </select>
            ${historyContainerHtml}
          </div>
        `;
      }

      // Checkbox
      if (fType === 'checkbox' || fType === 'bool') {
        const isChecked = (String(value).toLowerCase() === 'true' || value === true || value === '1' || value === 'yes');
        return `
          <div class="space-y-1">
            <div class="flex items-center justify-between min-h-[44px] py-1">
              <label for="${inputId}" class="flex-1 text-xs font-bold text-ink cursor-pointer flex items-center">${fName}</label>
              <div class="flex items-center gap-1.5">
                ${historyControls}
                <label class="min-w-[44px] min-h-[44px] flex items-center justify-center cursor-pointer">
                  <input
                    type="checkbox"
                    id="${inputId}"
                    data-section="${section}"
                    data-field="${fName}"
                    ${isChecked ? 'checked' : ''}
                    onchange="triggerAutoSave()"
                    class="w-5 h-5 text-fern rounded-[2px] border-bordercol focus:ring-fern cursor-pointer"
                  />
                </label>
              </div>
            </div>
            ${historyContainerHtml}
          </div>
        `;
      }

      // Multiline
      if (fType === 'multiline') {
        return `
          <div class="space-y-1">
            <div class="flex items-center justify-between min-h-[32px]">
              <label for="${inputId}" class="text-xs font-bold text-ink">${fName}</label>
              <div class="flex items-center">${historyControls}</div>
            </div>
            <textarea
              id="${inputId}"
              data-section="${section}"
              data-field="${fName}"
              rows="2"
              oninput="triggerAutoSave()" onblur="saveCurrentEdits()"
              class="w-full bg-surface border border-bordercol rounded-[2px] px-3 py-2 text-xs text-ink outline-none focus:border-fern"
            >${value || ''}</textarea>
            ${historyContainerHtml}
          </div>
        `;
      }

      // Standard Text or Readonly
      return `
        <div class="space-y-1">
          <div class="flex items-center justify-between min-h-[32px]">
            <label for="${inputId}" class="text-xs font-bold text-ink">${fName} ${isReadOnly ? '<span class="text-[9px] text-ink-faint font-normal font-mono">(Locked)</span>' : ''}</label>
            <div class="flex items-center">${historyControls}</div>
          </div>
          <input
            type="text"
            id="${inputId}"
            data-section="${section}"
            data-field="${fName}"
            value="${value || ''}"
            ${isReadOnly ? 'readonly class="w-full min-h-[44px] bg-tonal1 border border-bordercol rounded-[2px] px-3 py-2 text-xs text-ink-muted font-mono outline-none"' : 'class="w-full min-h-[44px] bg-surface border border-bordercol rounded-[2px] px-3 py-2 text-xs text-ink outline-none focus:border-fern" oninput="triggerAutoSave()" onblur="saveCurrentEdits()"'}
          />
          ${historyContainerHtml}
        </div>
      `;
    }

    function toggleAccordion(btn) {
      const acc = btn.closest('.accordion');
      acc.classList.toggle('acc-open');
      const content = acc.querySelector('.acc-content');
      if (acc.classList.contains('acc-open')) {
        content.classList.remove('hidden');
      } else {
        content.classList.add('hidden');
      }
    }

    // ==========================================
    // DISCREPANCY & PROBLEM TOGGLES
    // ==========================================
    function renderDiscrepancies(record) {
      const listContainer = document.getElementById('activeDiscrepanciesList');
      const togglesContainer = document.getElementById('problemTogglesContainer');

      const issues = record.flagged_issues || [];
      if (issues.length === 0) {
        listContainer.innerHTML = `<p class="text-xs text-ink-faint italic">No active discrepancies flagged for this specimen.</p>`;
      } else {
        listContainer.innerHTML = issues.map((iss, idx) => `
          <div class="bg-ember-light border border-ember-border p-2.5 rounded-[2px] flex items-start justify-between gap-2 text-xs">
            <div>
              <span class="font-bold text-ember-dark">${iss.field || 'General'}:</span>
              <p class="text-ember-dark mt-0.5">${iss.reason || 'Flagged problem'}</p>
            </div>
            <button
              type="button"
              onclick="resolveDiscrepancy('${iss.id}')"
              class="min-h-[44px] px-3 py-1.5 bg-surface hover:bg-ember-light border border-ember-border text-ember-dark font-bold text-xs rounded-[2px] shrink-0 touch-target-min touch-press flex items-center justify-center"
            >
              Resolve
            </button>
          </div>
        `).join('');
      }

      // Quick Toggles from ui_sections.problems
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.problems) {
        const probs = activeSchema.ui_sections.problems;
        togglesContainer.innerHTML = probs.map(p => {
          const pName = p.name;
          const pLabel = pName.replace('_Problem', '').replace(/_/g, ' ');
          const isFlagged = (record.observation && (String(record.observation[pName]).toLowerCase() === 'true' || record.observation[pName] === true || record.observation[pName] === '1'));
          return `
            <label class="touch-target-min min-h-[44px] flex items-center gap-2 p-2.5 border rounded-[2px] transition-colors touch-press cursor-pointer ${isFlagged ? 'border-ember bg-ember-light text-ember-dark font-semibold' : 'border-bordercol bg-surface text-ink hover:bg-tonal1'}">
              <input
                type="checkbox"
                id="prob_${pName}"
                ${isFlagged ? 'checked' : ''}
                onchange="toggleProblemFlag('${pName}')"
                class="w-4 h-4 text-ember rounded-[2px] border-bordercol focus:ring-ember cursor-pointer shrink-0"
              />
              <span class="truncate font-sans text-xs select-none">${pLabel}</span>
            </label>
          `;
        }).join('');
      }
    }

    function populateDiscrepancyFields() {
      const select = document.getElementById('discrepancyFieldSelect');
      if (!activeSchema || !activeSchema.ui_sections) return;
      const reg = (activeSchema.ui_sections.registration || []).map(f => f.name);
      const loc = (activeSchema.ui_sections.location || []).map(f => f.name);
      const all = ['General Specimen Issue'].concat(reg).concat(loc);
      select.innerHTML = all.map(f => `<option value="${f}">${f}</option>`).join('');
    }

    function openAddDiscrepancyModal(fieldName) {
      if (fieldName) {
        document.getElementById('discrepancyFieldSelect').value = fieldName;
      }
      openModal('addDiscrepancyModal');
    }

    async function submitDiscrepancy(e) {
      e.preventDefault();
      const field = document.getElementById('discrepancyFieldSelect').value;
      const reason = document.getElementById('discrepancyReasonInput').value.trim();
      const severity = document.querySelector('input[name="severity"]:checked').value;

      if (!reason) return;

      // Add to flagged issues locally and trigger save
      currentRecord.flagged_issues = currentRecord.flagged_issues || [];
      currentRecord.flagged_issues.push({
        id: `flag_${Date.now()}`,
        field: field,
        severity: severity,
        reason: reason,
        resolved: false
      });

      // Match corresponding problem toggle if it exists
      const matchProb = `${field}_Problem`;
      if (currentRecord.observation) {
        currentRecord.observation[matchProb] = true;
      }

      closeModal('addDiscrepancyModal');
      document.getElementById('discrepancyReasonInput').value = '';
      renderDiscrepancies(currentRecord);
      await saveCurrentEdits();
      showToast('Discrepancy flagged on host');
    }

    async function resolveDiscrepancy(issId) {
      if (!currentRecord || !currentRecord.flagged_issues) return;
      currentRecord.flagged_issues = currentRecord.flagged_issues.filter(i => i.id !== issId);
      renderDiscrepancies(currentRecord);
      await saveCurrentEdits();
      showToast('Discrepancy resolved');
    }

    async function toggleProblemFlag(probName) {
      const el = document.getElementById(`prob_${probName}`);
      if (!el || !currentRecord) return;
      currentRecord.observation = currentRecord.observation || {};
      currentRecord.observation[probName] = el.checked;
      await saveCurrentEdits();
    }

    // ==========================================
    // AUTO-SAVE & PRIMARY ACTION: MARK REVIEWED
    // ==========================================
    function triggerAutoSave() {
      const syncStatus = document.getElementById('footerSyncStatus');
      syncStatus.innerHTML = '<span class="font-mono text-ember font-medium animate-pulse">Saving changes...</span>';
      clearTimeout(autoSaveTimer);
      autoSaveTimer = setTimeout(saveCurrentEdits, 800);  // 800ms per guide requirement
    }

    async function saveCurrentEdits() {
      if (!currentOid) return;

      const regPayload = {};
      const obsPayload = {};

      // Collect all dynamic inputs
      document.querySelectorAll('[data-section="registration"]').forEach(input => {
        const f = input.getAttribute('data-field');
        regPayload[f] = (input.type === 'checkbox') ? input.checked : input.value;
      });

      document.querySelectorAll('[data-section="observation"]').forEach(input => {
        const f = input.getAttribute('data-field');
        if (input.type === 'checkbox') {
          obsPayload[f] = input.checked;
        } else {
          obsPayload[f] = input.value;
        }
      });

      // Merge problem flags
      if (currentRecord && currentRecord.observation) {
        Object.keys(currentRecord.observation).forEach(k => {
          if (k.endsWith('_Problem') || k.startsWith('Unknown_')) {
            obsPayload[k] = currentRecord.observation[k];
          }
        });
      }

      const payload = {
        id: currentOid,
        reviewed: isReviewed,
        registration: regPayload,
        observation: obsPayload
      };

      try {
        await apiFetch('/api/update', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        document.getElementById('footerSyncStatus').innerHTML = '<span class="font-mono text-fern-dark font-medium">✓ Synced to host</span>';
      } catch (err) {
        document.getElementById('footerSyncStatus').innerHTML = '<span class="font-mono text-ember-dark font-medium">⚠ Sync Error</span>';
      }
    }

    function updateReviewButtonUI() {
      const btn = document.getElementById('btnMarkReviewed');
      const label = document.getElementById('btnReviewedLabel');
      const badgeContainer = document.getElementById('detailReviewStatusBadge');

      if (isReviewed) {
        btn.className = 'w-full py-3.5 px-4 rounded-[2px] font-sans font-bold text-sm flex items-center justify-center gap-2 border-2 transition-all touch-target-min touch-press bg-fern text-white border-fern-dark shadow-md';
        label.textContent = '✓ Reviewed (Tap to undo)';
        badgeContainer.innerHTML = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[10px] font-sans font-semibold bg-fern-light text-fern-dark border border-fern-border">✓ REVIEWED</span>';
      } else {
        btn.className = 'w-full py-3.5 px-4 rounded-[2px] font-sans font-bold text-sm flex items-center justify-center gap-2 border-2 transition-all touch-target-min touch-press bg-surface text-ink border-bordercol hover:bg-tonal1 shadow-xs';
        label.textContent = 'Mark Reviewed';
        badgeContainer.innerHTML = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[10px] font-sans font-medium bg-tonal1 text-ink-muted border border-bordercol">🕒 UNREVIEWED</span>';
      }
    }

    async function toggleReviewed() {
      isReviewed = !isReviewed;
      updateReviewButtonUI();
      await saveCurrentEdits();
      showToast(isReviewed ? '✓ Specimen marked as Reviewed' : 'Specimen marked Unreviewed');
    }

    // ==========================================
    // FULLSCREEN PHOTO VIEWER MODAL & THUMBNAIL STRIP
    // ==========================================
    function renderPhotoThumbnails() {
      const strip = document.getElementById('photoThumbStrip');
      if (!strip) return;
      if (!photoUrls || photoUrls.length <= 1) {
        strip.classList.add('hidden');
        strip.innerHTML = '';
        return;
      }

      strip.classList.remove('hidden');
      strip.innerHTML = photoUrls.map((url, idx) => `
        <button
          type="button"
          onclick="selectSpecimenPhoto(${idx})"
          class="min-w-[44px] min-h-[44px] w-12 h-12 rounded-[2px] border-2 overflow-hidden shrink-0 touch-target-min touch-press transition-all ${idx === currentPhotoIdx ? 'border-fern ring-2 ring-fern-border' : 'border-bordercol opacity-70 hover:opacity-100'}"
          title="View Scan ${idx + 1}"
          aria-label="View archival scan ${idx + 1}"
        >
          <img src="${url}" alt="Thumbnail ${idx + 1}" class="w-full h-full object-cover" />
        </button>
      `).join('');
    }

    function selectSpecimenPhoto(idx) {
      if (!photoUrls || !photoUrls[idx]) return;
      currentPhotoIdx = idx;
      const mainImg = document.getElementById('specimenImg');
      mainImg.src = photoUrls[idx];
      document.getElementById('photoPlaceholder').classList.add('hidden');
      mainImg.classList.remove('hidden');
      renderPhotoThumbnails();
    }

    function openFullscreenPhoto() {
      if (!photoUrls || photoUrls.length === 0) return;
      photoZoom = 1;
      photoRotation = 0;
      photoPan = { x: 0, y: 0 };
      updatePhotoTransform();
      document.getElementById('photoViewerImg').src = photoUrls[currentPhotoIdx] || photoUrls[0];
      document.getElementById('photoViewerCounter').textContent = `(${currentPhotoIdx + 1}/${photoUrls.length})`;
      openModal('photoViewerModal');
    }

    function onPhotoLoaded() {
      document.getElementById('photoPlaceholder').classList.add('hidden');
      document.getElementById('specimenImg').classList.remove('hidden');
      document.getElementById('photoWatermark').classList.remove('hidden');
    }

    function onPhotoError() {
      document.getElementById('photoPlaceholder').innerHTML = `
        <span class="text-2xl text-ink-faint">📷</span>
        <p class="font-semibold text-ink-muted">Photo scan unavailable</p>
      `;
    }

    function zoomPhoto(delta) {
      photoZoom = Math.min(Math.max(photoZoom + delta, 1), 4);
      if (photoZoom === 1) photoPan = { x: 0, y: 0 };
      updatePhotoTransform();
    }

    function rotatePhoto() {
      photoRotation = (photoRotation + 90) % 360;
      updatePhotoTransform();
    }

    function resetPhotoTransform() {
      photoZoom = 1;
      photoRotation = 0;
      photoPan = { x: 0, y: 0 };
      updatePhotoTransform();
    }

    function updatePhotoTransform() {
      const img = document.getElementById('photoViewerImg');
      document.getElementById('zoomLevelDisplay').textContent = `${photoZoom.toFixed(1)}x`;
      img.style.transform = `scale(${photoZoom}) rotate(${photoRotation}deg) translate(${photoPan.x}px, ${photoPan.y}px)`;
    }

    function startPhotoDrag(e) {
      if (photoZoom > 1) {
        isDraggingPhoto = true;
        photoDragStart = { x: e.clientX - photoPan.x, y: e.clientY - photoPan.y };
        window.addEventListener('mousemove', onPhotoDrag);
        window.addEventListener('mouseup', stopPhotoDrag);
      }
    }

    function onPhotoDrag(e) {
      if (isDraggingPhoto && photoZoom > 1) {
        photoPan = { x: e.clientX - photoDragStart.x, y: e.clientY - photoDragStart.y };
        updatePhotoTransform();
      }
    }

    function stopPhotoDrag() {
      isDraggingPhoto = false;
      window.removeEventListener('mousemove', onPhotoDrag);
      window.removeEventListener('mouseup', stopPhotoDrag);
    }

    function startPhotoTouch(e) {
      if (e.touches.length === 1 && photoZoom > 1) {
        isDraggingPhoto = true;
        photoDragStart = { x: e.touches[0].clientX - photoPan.x, y: e.touches[0].clientY - photoPan.y };
        window.addEventListener('touchmove', onPhotoTouchMove);
        window.addEventListener('touchend', stopPhotoTouch);
      }
    }

    function onPhotoTouchMove(e) {
      if (isDraggingPhoto && e.touches.length === 1 && photoZoom > 1) {
        photoPan = { x: e.touches[0].clientX - photoDragStart.x, y: e.touches[0].clientY - photoDragStart.y };
        updatePhotoTransform();
      }
    }

    function stopPhotoTouch() {
      isDraggingPhoto = false;
      window.removeEventListener('touchmove', onPhotoTouchMove);
      window.removeEventListener('touchend', stopPhotoTouch);
    }

    // Initialize application
    init();
  </script>
</body>
</html>

"""
