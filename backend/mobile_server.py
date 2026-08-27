import threading
import logging
import random
import string
import json
import base64
import os
import mimetypes
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file
import pandas as pd
import config
from utils import debug_error, resource_path

# Reduce Flask logging spam
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

class MobileServer:
    def __init__(self, app_state, root_tk, port=5000):
        self.app_state = app_state
        self.root_tk = root_tk
        self.port = port
        self.flask_app = Flask(__name__)
        self.flask_app.secret_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        self.pin = ''.join(random.choices(string.digits, k=4))
        self.thread = None
        self._is_running = False
        self._setup_routes()

    def start(self):
        if self._is_running:
            return
        self._is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.flask_app.run(host='127.0.0.1', port=self.port, debug=False, use_reloader=False)
        except Exception as e:
            debug_error("Mobile Server Crash", str(e))
        finally:
            self._is_running = False

    def stop(self):
        # We don't have a reliable way to stop flask without werkzeug context,
        # but since it's a daemon thread, it will die with Arbor.
        # This is fine for our use case where we only expose it while Arbor runs.
        self._is_running = False

    def _setup_routes(self):
        app = self.flask_app

        @app.before_request
        def require_pin():
            if request.endpoint in ['login', 'static', None]:
                return
            if session.get('authenticated') != True:
                return redirect(url_for('login'))

        @app.route('/login', methods=['GET', 'POST'])
        def login():
            error = None
            if request.method == 'POST':
                if request.form.get('pin') == self.pin:
                    session['authenticated'] = True
                    return redirect(url_for('index'))
                else:
                    error = 'Invalid PIN'
            return render_template_string(LOGIN_TEMPLATE, error=error)

        @app.route('/logout')
        def logout():
            session.pop('authenticated', None)
            return redirect(url_for('login'))

        @app.route('/')
        def index():
            return render_template_string(INDEX_TEMPLATE)

        @app.route('/api/search/<oid>')
        def search(oid):
            if not self.app_state.df_reg is not None:
                return jsonify({"error": "No database loaded"}), 400

            oid = str(oid).strip()

            with self.app_state.df_lock:
                if oid not in self.app_state.df_reg.index:
                    return jsonify({"error": "Object not found"}), 404

                reg_row = self.app_state.df_reg.loc[[oid]].copy()
                obs_row = None
                if self.app_state.df_obs is not None and oid in self.app_state.df_obs.index:
                    obs_row = self.app_state.df_obs.loc[[oid]].copy()

                photo_row = None
                if self.app_state.df_photo is not None and oid in self.app_state.df_photo.index:
                    photo_row = self.app_state.df_photo.loc[[oid]].copy()

            data = {}

            # Combine taxonomy, collection, location
            for col in reg_row.columns:
                val = reg_row.iloc[0][col]
                data[col] = str(val) if pd.notna(val) else ""

            if obs_row is not None:
                for col in obs_row.columns:
                    val = obs_row.iloc[0][col]
                    data[col] = str(val) if pd.notna(val) else ""

            # Historical comparisons
            historical_data = {}
            for hist_db in self.app_state.historical_dbs:
                df_hist = hist_db.get('df')
                if df_hist is not None and oid in df_hist.index:
                    name = hist_db.get('name', 'Historical')
                    hist_row = df_hist.loc[[oid]]
                    for col in hist_row.columns:
                        if col in data:
                            val = hist_row.iloc[0][col]
                            if pd.notna(val):
                                val_str = str(val)
                                if val_str != data[col]:
                                    if col not in historical_data:
                                        historical_data[col] = []
                                    historical_data[col].append(f"({name}): {val_str}")

            # Get problems
            problems = {}
            if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                for p_info in self.app_state.config["ui_sections"]["problems"]:
                    p_col = p_info["name"]
                    if p_col in data:
                        val = str(data[p_col]).lower()
                        problems[p_col] = (val == 'true' or val == 'yes' or val == 'x')

            has_image = False
            image_url = None
            if photo_row is not None and len(photo_row) > 0:
                 img_val = photo_row.iloc[0].get('Images', '')
                 if pd.notna(img_val) and str(img_val).strip() != '':
                     has_image = True

            if self.app_state.config and getattr(self.app_state, 'image_mode', 'online') == 'online':
                 pattern = self.app_state.config.get("image_url_pattern", "")
                 if pattern:
                     image_url = pattern.replace("{id}", oid)
            elif getattr(self.app_state, 'image_mode', 'online') == 'folder':
                if has_image:
                     image_url = url_for('get_image', oid=oid)

            return jsonify({
                "oid": oid,
                "data": data,
                "historical": historical_data,
                "problems": problems,
                "has_image": has_image,
                "image_url": image_url,
                "schema": self._get_schema()
            })

        @app.route('/api/image/<oid>')
        def get_image(oid):
             if getattr(self.app_state, 'image_mode', 'online') != 'folder':
                 return "Image not local", 404

             folder = getattr(self.app_state, 'image_folder', '')
             if not folder or not os.path.isdir(folder):
                 return "Image folder not found", 404

             # Secure lookup
             with self.app_state.df_lock:
                 if self.app_state.df_photo is None or oid not in self.app_state.df_photo.index:
                     return "Not found", 404
                 row = self.app_state.df_photo.loc[[oid]]
                 filenames = str(row.iloc[0].get('Images', '')).split(',')
                 if not filenames or not filenames[0].strip():
                     return "No image", 404

                 filename = filenames[0].strip()
                 path = os.path.join(folder, filename)
                 if not os.path.exists(path):
                     return "File not found", 404

                 mime_type, _ = mimetypes.guess_type(path)
                 if not mime_type:
                     mime_type = 'image/jpeg'
                 return send_file(path, mimetype=mime_type)


        @app.route('/api/save/<oid>', methods=['POST'])
        def save(oid):
            if self.app_state.df_reg is None:
                return jsonify({"error": "No database loaded"}), 400

            oid = str(oid).strip()
            updates = request.json

            if not updates:
                 return jsonify({"error": "No data"}), 400

            with self.app_state.df_lock:
                if oid not in self.app_state.df_reg.index:
                    return jsonify({"error": "Object not found"}), 404

                # Check for edits and record logs
                from utils import sanitize_value, coerce_type

                # We will just write directly to the DF, and then trigger <<MobileEdit>>
                # The main UI will pick it up, refresh, and commit.
                # This keeps the undo stack and logs managed by the main UI.

                # For safety, we only allow updates to fields defined in the schema
                schema = self._get_schema()
                allowed_fields = set()
                for group in schema['groups']:
                    for field in group['fields']:
                        allowed_fields.add(field['name'])
                for p in schema['problems']:
                    allowed_fields.add(p['name'])

                changed = False

                for key, val in updates.items():
                    if key not in allowed_fields:
                        continue

                    df_target = None
                    if key in self.app_state.df_reg.columns:
                        df_target = self.app_state.df_reg
                    elif self.app_state.df_obs is not None and key in self.app_state.df_obs.columns:
                        df_target = self.app_state.df_obs

                    if df_target is not None:
                        current_val = sanitize_value(df_target.iloc[df_target.index.get_loc(oid)][key])
                        new_val = sanitize_value(val)
                        if str(current_val) != str(new_val):
                            coerced_val = coerce_type(new_val, df_target[key].dtype)
                            df_target.at[oid, key] = coerced_val
                            changed = True

                if not changed:
                    return jsonify({"status": "no changes"})

                self.app_state.dirty = True

            # Notify UI
            try:
                # pass oid to the event somehow? virtual events don't take data easily
                # we set a temporary attribute on app_state
                self.app_state._mobile_last_edited_oid = oid
                self.root_tk.event_generate("<<MobileEdit>>", when="tail")
            except Exception as e:
                debug_error("Mobile Event Gen Error", str(e))

            return jsonify({"status": "success"})


    def _get_schema(self):
        ui_sections = self.app_state.config.get("ui_sections", {})

        groups = []
        reg_groups = ui_sections.get("reg_groups", [])
        reg_fields = {f["name"]: f for f in ui_sections.get("registration", [])}

        for g in reg_groups:
            if g["name"] in ["Taxonomy", "Collection", "Location"]:
                fields = []
                for fname in g["fields"]:
                    if fname in reg_fields and not reg_fields[fname].get("readonly"):
                        fields.append(reg_fields[fname])
                groups.append({"name": g["name"], "fields": fields})

        # Also include location explicitly if not in reg_groups
        has_loc = False
        for g in groups:
            if g["name"] == "Location":
                has_loc = True
                break

        if not has_loc and "location" in ui_sections:
             fields = []
             for f in ui_sections["location"]:
                 if not f.get("readonly"):
                     fields.append(f)
             groups.append({"name": "Location", "fields": fields})

        problems = ui_sections.get("problems", [])

        return {
            "groups": groups,
            "problems": problems
        }


LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Arbor Mobile</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100 h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded shadow-md w-full max-w-sm">
        <h2 class="text-2xl mb-4 font-bold text-center text-green-700">Arbor Mobile</h2>
        {% if error %}
            <p class="text-red-500 mb-4">{{ error }}</p>
        {% endif %}
        <form method="POST">
            <input type="number" name="pin" placeholder="Enter PIN" class="w-full border p-2 mb-4 rounded text-center text-xl" required pattern="\d*">
            <button type="submit" class="w-full bg-green-600 text-white p-2 rounded text-lg font-bold">Connect</button>
        </form>
    </div>
</body>
</html>
"""

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
    <title>Arbor Mobile Editor</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <style>
        body { -webkit-tap-highlight-color: transparent; }
        .historical { font-size: 0.75rem; color: #d97706; margin-top: -0.25rem; margin-bottom: 0.5rem; display: block; }
    </style>
</head>
<body class="bg-gray-100 text-gray-800 pb-24">

    <div class="bg-green-700 text-white p-4 shadow-md sticky top-0 z-50 flex justify-between items-center">
        <h1 class="text-xl font-bold">Arbor Mobile</h1>
        <a href="{{ url_for('logout') }}" class="text-sm bg-green-800 px-3 py-1 rounded">Logout</a>
    </div>

    <div class="p-4 max-w-md mx-auto">
        <div class="flex gap-2 mb-6">
            <input type="text" id="searchInput" placeholder="Scan or Enter Object ID" class="flex-1 p-3 border rounded shadow-inner text-lg">
            <button onclick="search()" class="bg-blue-600 text-white px-5 rounded font-bold shadow">Find</button>
        </div>

        <div id="loading" class="hidden text-center text-gray-500 my-8">Loading...</div>
        <div id="error" class="hidden bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4"></div>

        <div id="editor" class="hidden">
            <h2 id="objIdDisplay" class="text-2xl font-black text-center mb-4 border-b pb-2"></h2>

            <div id="imageContainer" class="hidden mb-6 flex justify-center">
                <img id="objImage" src="" class="max-w-full h-auto rounded shadow max-h-64 object-contain">
            </div>

            <div id="formFields"></div>

            <div id="problemsSection" class="mt-6 p-4 bg-red-50 rounded shadow-sm border border-red-100">
                <h3 class="font-bold text-red-800 mb-3 border-b border-red-200 pb-1">Problems</h3>
                <div id="problemsFields"></div>
            </div>
        </div>
    </div>

    <div id="saveBar" class="hidden fixed bottom-0 left-0 w-full bg-white border-t p-4 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
        <div class="max-w-md mx-auto">
             <button onclick="save()" id="saveBtn" class="w-full bg-green-600 text-white py-3 rounded text-xl font-bold shadow-lg active:bg-green-700 transition">Save Changes</button>
        </div>
    </div>

    <script>
        let currentOid = null;
        let currentData = null;

        document.getElementById('searchInput').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') search();
        });

        async function search() {
            const val = document.getElementById('searchInput').value.trim();
            if (!val) return;

            document.getElementById('editor').classList.add('hidden');
            document.getElementById('saveBar').classList.add('hidden');
            document.getElementById('error').classList.add('hidden');
            document.getElementById('loading').classList.remove('hidden');

            try {
                const res = await fetch('/api/search/' + encodeURIComponent(val));
                const json = await res.json();

                if (!res.ok) throw new Error(json.error || 'Not found');

                currentOid = json.oid;
                currentData = json;
                renderForm();

                document.getElementById('loading').classList.add('hidden');
                document.getElementById('editor').classList.remove('hidden');
                document.getElementById('saveBar').classList.remove('hidden');
            } catch (err) {
                document.getElementById('loading').classList.add('hidden');
                document.getElementById('error').textContent = err.message;
                document.getElementById('error').classList.remove('hidden');
            }
        }

        function renderForm() {
            document.getElementById('objIdDisplay').textContent = currentOid;

            const imgContainer = document.getElementById('imageContainer');
            const img = document.getElementById('objImage');
            if (currentData.image_url) {
                img.src = currentData.image_url;
                imgContainer.classList.remove('hidden');
            } else {
                imgContainer.classList.add('hidden');
            }

            const container = document.getElementById('formFields');
            container.innerHTML = '';

            currentData.schema.groups.forEach(group => {
                const grpDiv = document.createElement('div');
                grpDiv.className = 'mb-6 bg-white p-4 rounded shadow-sm border border-gray-100';

                const title = document.createElement('h3');
                title.className = 'font-bold text-gray-700 mb-3 border-b pb-1';
                title.textContent = group.name;
                grpDiv.appendChild(title);

                group.fields.forEach(field => {
                    const fDiv = document.createElement('div');
                    fDiv.className = 'mb-4';

                    const lbl = document.createElement('label');
                    lbl.className = 'block text-sm font-medium text-gray-600 mb-1';
                    lbl.textContent = field.name;
                    fDiv.appendChild(lbl);

                    let input;
                    if (field.type === 'multiline') {
                        input = document.createElement('textarea');
                        input.className = 'w-full border rounded p-2 text-base';
                        input.rows = 3;
                    } else if (field.type === 'choice' && field.choices) {
                        input = document.createElement('select');
                        input.className = 'w-full border rounded p-2 text-base bg-white';
                        const emptyOpt = document.createElement('option');
                        emptyOpt.value = ""; emptyOpt.text = "";
                        input.appendChild(emptyOpt);
                        field.choices.forEach(c => {
                            const opt = document.createElement('option');
                            opt.value = c; opt.text = c;
                            input.appendChild(opt);
                        });
                    } else if (field.type === 'checkbox') {
                         input = document.createElement('input');
                         input.type = 'checkbox';
                         input.className = 'w-6 h-6 ml-2';
                    } else {
                        input = document.createElement('input');
                        input.type = 'text';
                        input.className = 'w-full border rounded p-2 text-base';
                    }

                    input.id = 'f_' + field.name;
                    input.dataset.field = field.name;

                    const val = currentData.data[field.name];
                    if (field.type === 'checkbox') {
                         input.checked = (String(val).toLowerCase() === 'true' || String(val).toLowerCase() === 'yes' || String(val).toLowerCase() === 'x');
                    } else {
                         input.value = val || '';
                    }

                    if (field.type === 'checkbox') {
                         const wrap = document.createElement('div');
                         wrap.className = 'flex items-center';
                         lbl.className = 'text-sm font-medium text-gray-600';
                         wrap.appendChild(lbl);
                         wrap.appendChild(input);
                         fDiv.innerHTML = '';
                         fDiv.appendChild(wrap);
                    } else {
                         fDiv.appendChild(input);
                    }

                    // Historical
                    if (currentData.historical[field.name]) {
                        const hist = document.createElement('span');
                        hist.className = 'historical';
                        hist.textContent = currentData.historical[field.name].join(', ');
                        fDiv.appendChild(hist);
                    }

                    grpDiv.appendChild(fDiv);
                });

                container.appendChild(grpDiv);
            });

            // Problems
            const pContainer = document.getElementById('problemsFields');
            pContainer.innerHTML = '';

            currentData.schema.problems.forEach(prob => {
                const pDiv = document.createElement('div');
                pDiv.className = 'flex items-center mb-3 bg-white p-2 rounded border';

                const input = document.createElement('input');
                input.type = 'checkbox';
                input.className = 'w-6 h-6 text-red-600 border-red-300 rounded focus:ring-red-500';
                input.id = 'p_' + prob.name;
                input.dataset.field = prob.name;
                input.checked = currentData.problems[prob.name] || false;

                const lbl = document.createElement('label');
                lbl.className = 'ml-3 block text-base font-medium text-gray-900';
                lbl.textContent = prob.name.replace('_Problem', '').replace('_', ' ');
                lbl.setAttribute('for', input.id);

                pDiv.appendChild(input);
                pDiv.appendChild(lbl);
                pContainer.appendChild(pDiv);
            });
        }

        async function save() {
            const btn = document.getElementById('saveBtn');
            const origText = btn.textContent;
            btn.textContent = 'Saving...';
            btn.disabled = true;
            btn.classList.add('opacity-50');

            const updates = {};

            // Collect fields
            document.querySelectorAll('#formFields [data-field]').forEach(el => {
                if (el.type === 'checkbox') {
                     updates[el.dataset.field] = el.checked ? 'True' : 'False';
                } else {
                     updates[el.dataset.field] = el.value;
                }
            });

            // Collect problems
            document.querySelectorAll('#problemsFields [data-field]').forEach(el => {
                updates[el.dataset.field] = el.checked ? 'True' : 'False';
            });

            try {
                const res = await fetch('/api/save/' + encodeURIComponent(currentOid), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updates)
                });

                if (!res.ok) throw new Error('Save failed');

                btn.textContent = 'Saved!';
                btn.classList.remove('bg-green-600');
                btn.classList.add('bg-blue-600');

                setTimeout(() => {
                    btn.textContent = origText;
                    btn.disabled = false;
                    btn.classList.remove('opacity-50', 'bg-blue-600');
                    btn.classList.add('bg-green-600');
                }, 2000);

            } catch (err) {
                alert(err.message);
                btn.textContent = origText;
                btn.disabled = false;
                btn.classList.remove('opacity-50');
            }
        }
    </script>
</body>
</html>
"""
