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
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file
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
                provided_pin = request.form.get('pin', '').strip()
                if provided_pin == self.pin:
                    session['authenticated'] = True
                    return redirect(url_for('index'))
                else:
                    error = 'Invalid PIN'
            return render_template_string(LOGIN_TEMPLATE, error=error)

        @app.route('/logout')
        def logout():
            session.pop('authenticated', None)
            return redirect(url_for('login'))

        @app.route('/api/auth', methods=['POST'])
        def api_auth():
            data = request.get_json(silent=True) or {}
            provided_pin = str(data.get('pin', '')).strip()
            provided_token = str(data.get('token', '')).strip()
            if provided_token == self.session_token or provided_pin == self.pin:
                session['authenticated'] = True
                return jsonify({
                    "success": True,
                    "token": self.session_token,
                    "message": "Authenticated successfully"
                })
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

                total_matching = len(matched_indices)
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
                "objects": objects
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


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Arbor Mobile Companion</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    .touch-min { min-height: 44px; }
  </style>
</head>
<body class="bg-[#121915] text-[#1c241f] min-h-screen flex items-center justify-center p-0 sm:p-4 antialiased font-sans select-none">
  
  <div class="w-full max-w-md bg-[#ffffff] sm:rounded-[20px] shadow-2xl overflow-hidden flex flex-col h-screen sm:h-[820px] border border-neutral-800 relative">
    
    <!-- Top Status Bar -->
    <div class="bg-[#1b4332] text-white px-4 py-2 flex items-center justify-between text-xs font-mono">
      <div class="flex items-center gap-1.5 font-bold">
        <span class="inline-block w-2 h-2 rounded-full bg-[#52b788] animate-pulse"></span>
        <span id="headerDbName">Herbarium Database</span>
      </div>
      <div class="flex items-center gap-2 text-[11px] text-emerald-200">
        <span id="syncStatusBadge">⚡ Connected</span>
      </div>
    </div>

    <!-- Header Navigation -->
    <header class="bg-[#2d6a4f] text-white px-4 py-2.5 flex items-center justify-between shadow-sm">
      <div class="flex items-center gap-2">
        <span class="text-xl">🌿</span>
        <div>
          <h1 class="font-bold text-sm tracking-tight leading-tight">Arbor Companion</h1>
          <p class="text-[10px] text-emerald-100/80 font-mono" id="headerCount">Loading records...</p>
        </div>
      </div>
      <div class="flex items-center gap-1.5">
        <button id="btnListView" onclick="toggleListView()" class="bg-emerald-700/80 hover:bg-emerald-600 px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1 transition">
          📋 List
        </button>
      </div>
    </header>

    <!-- Search & Sequential Jump Bar -->
    <div class="bg-[#f4f6f4] px-4 py-2 border-b border-[#e0e3df] flex items-center gap-2">
      <div class="relative flex-1">
        <input id="searchBox" type="text" placeholder="Search ID, Genus, Species..." onkeydown="if(event.key==='Enter') doSearch()"
               class="w-full bg-white border border-[#d0d6d1] rounded-md px-3 py-1.5 text-xs text-[#1c241f] focus:outline-none focus:border-[#2d6a4f] font-mono">
      </div>
      <div class="flex items-center gap-1">
        <button onclick="navPrev()" class="bg-white border border-[#d0d6d1] text-[#2d6a4f] hover:bg-emerald-50 px-2.5 py-1.5 rounded-md text-xs font-bold touch-min flex items-center justify-center">◀</button>
        <button onclick="navNext()" class="bg-white border border-[#d0d6d1] text-[#2d6a4f] hover:bg-emerald-50 px-2.5 py-1.5 rounded-md text-xs font-bold touch-min flex items-center justify-center">▶</button>
      </div>
    </div>

    <!-- Toast Notification Overlay -->
    <div id="toast" class="hidden absolute top-14 left-4 right-4 bg-emerald-800 text-white text-xs font-bold py-2 px-3 rounded-lg shadow-lg text-center z-50 transition-all">
      Edits saved & synchronized
    </div>

    <!-- Main Container -->
    <main id="mainContent" class="flex-1 overflow-y-auto p-4 space-y-3 bg-[#fbfbf9]">
      
      <!-- Specimen Primary Identity Card -->
      <div class="bg-white rounded-lg border border-[#e0e3df] p-3 shadow-xs">
        <div class="flex items-start justify-between">
          <div>
            <span id="accessionTag" class="text-[10px] font-mono font-bold tracking-wider text-[#2d6a4f] uppercase bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
              Accession #---
            </span>
            <h2 id="scientificNameTitle" class="text-base font-bold text-[#1c241f] mt-1 italic">Loading Specimen...</h2>
            <p id="familySubtitle" class="text-xs text-[#5a655e]">Family: ---</p>
          </div>
          <span id="reviewBadge" class="bg-amber-100 text-amber-800 text-[10px] font-bold px-2 py-0.5 rounded-full border border-amber-300">
            ⏳ Pending
          </span>
        </div>
      </div>

      <!-- Specimen Photo Plate (On-Demand Click to Load) -->
      <div class="bg-white rounded-lg border border-[#e0e3df] overflow-hidden">
        <div class="px-3 py-2 border-b border-[#e0e3df] bg-[#f8f9fa] flex items-center justify-between text-xs">
          <div class="flex items-center gap-1.5 font-semibold text-[#1c241f]">
            <span>🖼️</span> <span>Specimen Photo Scan</span>
          </div>
          <span class="text-[10px] text-[#5a655e] font-mono">Cloud Archive</span>
        </div>
        
        <div id="imagePlaceholder" class="p-5 text-center bg-[#fafafa] flex flex-col items-center justify-center gap-2 cursor-pointer hover:bg-[#f0f4f1] transition border-b border-dashed border-[#e0e3df]" onclick="loadImage()">
          <div class="w-10 h-10 rounded-full bg-emerald-100 text-[#2d6a4f] flex items-center justify-center text-lg">🔍</div>
          <div>
            <p class="text-xs font-bold text-[#2d6a4f]">Tap to Load Specimen Plate</p>
            <p class="text-[10px] text-[#5a655e]">Loads directly from cloud CDN (0 laptop bandwidth)</p>
          </div>
        </div>

        <div id="imageContainer" class="hidden relative bg-neutral-900 flex items-center justify-center min-h-[160px]">
          <img id="specimenImg" src="" alt="Specimen Plate" class="max-h-56 w-auto object-contain mx-auto">
        </div>
      </div>

      <!-- Segmented Category Tabs -->
      <div class="flex rounded-md bg-[#e6eae6] p-1 gap-1 text-xs font-medium">
        <button id="tabTax" class="flex-1 py-1.5 rounded text-center transition bg-white text-[#2d6a4f] shadow-xs font-bold" onclick="switchTab('tax')">
          🏷️ Taxonomy
        </button>
        <button id="tabLoc" class="flex-1 py-1.5 rounded text-center transition text-[#5a655e] hover:text-[#1c241f]" onclick="switchTab('loc')">
          📍 Location
        </button>
        <button id="tabObs" class="flex-1 py-1.5 rounded text-center transition text-[#5a655e] hover:text-[#1c241f]" onclick="switchTab('obs')">
          📝 Notes
        </button>
      </div>

      <!-- Tab Content 1: Taxonomy -->
      <div id="contentTax" class="bg-white rounded-lg border border-[#e0e3df] p-3 space-y-2.5 text-xs">
        <div>
          <label class="text-[11px] font-semibold text-[#5a655e] block mb-1">Genus</label>
          <input id="inputGenus" type="text" class="w-full bg-[#fbfbf9] border border-[#d0d6d1] rounded px-2.5 py-1.5 text-xs text-[#1c241f] focus:outline-none focus:border-[#2d6a4f]">
        </div>
        <div>
          <label class="text-[11px] font-semibold text-[#5a655e] block mb-1">Species Epithet</label>
          <input id="inputSpecies" type="text" class="w-full bg-[#fbfbf9] border border-[#d0d6d1] rounded px-2.5 py-1.5 text-xs text-[#1c241f] focus:outline-none focus:border-[#2d6a4f]">
        </div>
        <div>
          <label class="text-[11px] font-semibold text-[#5a655e] block mb-1">Author / Infraspecific</label>
          <input id="inputAuthor" type="text" class="w-full bg-[#fbfbf9] border border-[#d0d6d1] rounded px-2.5 py-1.5 text-xs text-[#1c241f] focus:outline-none focus:border-[#2d6a4f]">
        </div>
      </div>

      <!-- Tab Content 2: Location -->
      <div id="contentLoc" class="hidden bg-white rounded-lg border border-[#e0e3df] p-3 space-y-2.5 text-xs">
        <div>
          <label class="text-[11px] font-semibold text-[#5a655e] block mb-1">Building & Room</label>
          <input id="inputRoom" type="text" class="w-full bg-[#fbfbf9] border border-[#d0d6d1] rounded px-2.5 py-1.5 text-xs text-[#1c241f]">
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="text-[11px] font-semibold text-[#5a655e] block mb-1">Cabinet</label>
            <input id="inputCabinet" type="text" class="w-full bg-[#fbfbf9] border border-[#d0d6d1] rounded px-2.5 py-1.5 text-xs text-[#1c241f]">
          </div>
          <div>
            <label class="text-[11px] font-semibold text-[#5a655e] block mb-1">Shelf / Drawer</label>
            <input id="inputShelf" type="text" class="w-full bg-[#fbfbf9] border border-[#d0d6d1] rounded px-2.5 py-1.5 text-xs text-[#1c241f]">
          </div>
        </div>
      </div>

      <!-- Tab Content 3: Notes & Observation -->
      <div id="contentObs" class="hidden bg-white rounded-lg border border-[#e0e3df] p-3 space-y-2.5 text-xs">
        <div>
          <label class="text-[11px] font-semibold text-[#5a655e] block mb-1">Inspection Notes & Comments</label>
          <textarea id="inputNotes" rows="4" class="w-full bg-[#fbfbf9] border border-[#d0d6d1] rounded px-2.5 py-1.5 text-xs text-[#1c241f] focus:outline-none focus:border-[#2d6a4f]"></textarea>
        </div>
      </div>

    </main>

    <!-- Specimen List View Overlay (Hidden by default) -->
    <div id="listViewModal" class="hidden absolute inset-0 bg-white z-40 flex flex-col">
      <div class="bg-[#2d6a4f] text-white p-3 flex items-center justify-between">
        <h3 class="font-bold text-sm">Specimens in Database</h3>
        <button onclick="toggleListView()" class="text-white font-bold text-lg px-2">✕</button>
      </div>
      <div id="specimenListContainer" class="flex-1 overflow-y-auto p-2 divide-y divide-gray-100">
        <!-- populated dynamically -->
      </div>
    </div>

    <!-- Sticky Bottom Action Bar -->
    <footer class="bg-white border-t border-[#e0e3df] p-3 flex items-center gap-2 shadow-lg">
      <button id="btnReviewed" onclick="toggleReviewed()" class="flex-1 bg-[#2d6a4f] hover:bg-[#1b4332] text-white py-2.5 rounded-md font-bold text-xs flex items-center justify-center gap-1.5 touch-min shadow-sm transition">
        <span>✓</span> <span>Mark Reviewed</span>
      </button>
      <button onclick="saveAndNext()" class="bg-[#f0f4f1] border border-[#d0d6d1] text-[#2d6a4f] hover:bg-emerald-100 px-4 py-2.5 rounded-md font-bold text-xs touch-min transition">
        Save & Next ▶
      </button>
    </footer>

  </div>

  <script>
    const TOKEN = "{{ token }}";
    let currentOid = null;
    let currentRecord = null;
    let isReviewed = false;
    let objectList = [];
    let currentIndex = 0;

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

    async function init() {
      try {
        const status = await apiFetch('/api/status');
        document.getElementById('headerDbName').textContent = status.database_name || 'Arbor Database';
        document.getElementById('headerCount').textContent = `${status.reviewed_count} / ${status.total_objects} reviewed`;

        const objRes = await apiFetch('/api/objects?limit=500');
        objectList = objRes.objects || [];
        if (objectList.length > 0) {
          loadObject(objectList[0].id);
        }
      } catch (err) {
        console.error("Init failed:", err);
      }
    }

    async function loadObject(oid) {
      currentOid = oid;
      currentIndex = objectList.findIndex(o => o.id === oid);
      if (currentIndex === -1) currentIndex = 0;

      document.getElementById('imagePlaceholder').classList.remove('hidden');
      document.getElementById('imageContainer').classList.add('hidden');
      document.getElementById('specimenImg').src = '';

      try {
        const data = await apiFetch(`/api/object/${encodeURIComponent(oid)}`);
        currentRecord = data;
        
        document.getElementById('accessionTag').textContent = `Accession #${data.accession_number}`;
        document.getElementById('scientificNameTitle').textContent = data.scientific_name || `Specimen #${oid}`;
        document.getElementById('familySubtitle').textContent = `Family: ${data.registration.Family || '---'}`;
        
        document.getElementById('inputGenus').value = data.registration.Genus || '';
        document.getElementById('inputSpecies').value = data.registration.Species || '';
        document.getElementById('inputAuthor').value = data.registration.Author || '';
        
        document.getElementById('inputRoom').value = data.observation.Room || data.registration.Room || '';
        document.getElementById('inputCabinet').value = data.observation.Cabinet || data.registration.Cabinet || '';
        document.getElementById('inputShelf').value = data.observation.Shelf || data.registration.Shelf || '';
        document.getElementById('inputNotes').value = data.observation.Notes || '';

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

    function switchTab(tab) {
      document.getElementById('contentTax').classList.add('hidden');
      document.getElementById('contentLoc').classList.add('hidden');
      document.getElementById('contentObs').classList.add('hidden');

      document.getElementById('tabTax').className = 'flex-1 py-1.5 rounded text-center transition text-[#5a655e] hover:text-[#1c241f]';
      document.getElementById('tabLoc').className = 'flex-1 py-1.5 rounded text-center transition text-[#5a655e] hover:text-[#1c241f]';
      document.getElementById('tabObs').className = 'flex-1 py-1.5 rounded text-center transition text-[#5a655e] hover:text-[#1c241f]';

      if (tab === 'tax') {
        document.getElementById('contentTax').classList.remove('hidden');
        document.getElementById('tabTax').className = 'flex-1 py-1.5 rounded text-center transition bg-white text-[#2d6a4f] shadow-xs font-bold';
      } else if (tab === 'loc') {
        document.getElementById('contentLoc').classList.remove('hidden');
        document.getElementById('tabLoc').className = 'flex-1 py-1.5 rounded text-center transition bg-white text-[#2d6a4f] shadow-xs font-bold';
      } else if (tab === 'obs') {
        document.getElementById('contentObs').classList.remove('hidden');
        document.getElementById('tabObs').className = 'flex-1 py-1.5 rounded text-center transition bg-white text-[#2d6a4f] shadow-xs font-bold';
      }
    }

    function updateReviewButton() {
      const badge = document.getElementById('reviewBadge');
      const btn = document.getElementById('btnReviewed');
      if (isReviewed) {
        badge.className = 'bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-0.5 rounded-full border border-emerald-300';
        badge.textContent = '✓ Reviewed';
        btn.className = 'flex-1 bg-emerald-800 text-white py-2.5 rounded-md font-bold text-xs flex items-center justify-center gap-1.5 touch-min shadow-sm';
        btn.innerHTML = '<span>✓</span> <span>Reviewed (Tap to undo)</span>';
      } else {
        badge.className = 'bg-amber-100 text-amber-800 text-[10px] font-bold px-2 py-0.5 rounded-full border border-amber-300';
        badge.textContent = '⏳ Pending';
        btn.className = 'flex-1 bg-[#2d6a4f] hover:bg-[#1b4332] text-white py-2.5 rounded-md font-bold text-xs flex items-center justify-center gap-1.5 touch-min shadow-sm';
        btn.innerHTML = '<span>✓</span> <span>Mark Reviewed</span>';
      }
    }

    async function toggleReviewed() {
      isReviewed = !isReviewed;
      updateReviewButton();
      await saveCurrentEdits();
    }

    async function saveCurrentEdits() {
      if (!currentOid) return;
      const payload = {
        id: currentOid,
        reviewed: isReviewed,
        registration: {
          Genus: document.getElementById('inputGenus').value,
          Species: document.getElementById('inputSpecies').value,
          Author: document.getElementById('inputAuthor').value
        },
        observation: {
          Room: document.getElementById('inputRoom').value,
          Cabinet: document.getElementById('inputCabinet').value,
          Shelf: document.getElementById('inputShelf').value,
          Notes: document.getElementById('inputNotes').value
        }
      };

      try {
        await apiFetch('/api/update', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        showToast('✓ Edits synced to desktop database');
      } catch (err) {
        showToast('⚠ Error syncing edits');
      }
    }

    async function saveAndNext() {
      await saveCurrentEdits();
      navNext();
    }

    function navPrev() {
      if (currentIndex > 0) {
        loadObject(objectList[currentIndex - 1].id);
      }
    }

    function navNext() {
      if (currentIndex < objectList.length - 1) {
        loadObject(objectList[currentIndex + 1].id);
      }
    }

    function doSearch() {
      const q = document.getElementById('searchBox').value.trim();
      if (!q) return;
      apiFetch(`/api/objects?q=${encodeURIComponent(q)}`).then(res => {
        if (res.objects && res.objects.length > 0) {
          objectList = res.objects;
          loadObject(objectList[0].id);
        } else {
          showToast('No matching specimens found');
        }
      });
    }

    function toggleListView() {
      const modal = document.getElementById('listViewModal');
      modal.classList.toggle('hidden');
      if (!modal.classList.contains('hidden')) {
        const container = document.getElementById('specimenListContainer');
        container.innerHTML = objectList.map(o => `
          <div onclick="loadObject('${o.id}'); toggleListView();" class="p-3 hover:bg-emerald-50 cursor-pointer flex items-center justify-between">
            <div>
              <span class="font-mono text-[10px] text-emerald-800 font-bold">#${o.id}</span>
              <p class="font-bold text-xs italic">${o.scientific_name}</p>
            </div>
            <span class="text-[10px] px-2 py-0.5 rounded-full ${o.review_status === 'reviewed' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}">
              ${o.review_status}
            </span>
          </div>
        `).join('');
      }
    }

    if ('wakeLock' in navigator) {
      navigator.wakeLock.request('screen').catch(() => {});
    }

    init();
  </script>
</body>
</html>"""
