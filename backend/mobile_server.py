import threading
import logging
from flask import Flask, jsonify, request, send_file, render_template
import pandas as pd
import os

# Reduce Flask logging in the console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
# Enable CORS for local testing if needed, though usually frontend is served from same host
# from flask_cors import CORS
# CORS(app)

_app_state = None
_ui_root = None

def get_base_dir():
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@app.route('/')
def index():
    return render_template('mobile.html')

@app.route('/api/objects', methods=['GET'])
def get_objects():
    if not _app_state or _app_state.df_reg is None:
        return jsonify({"error": "No database loaded"}), 400

    with _app_state.df_lock:
        try:
            # Send a simplified list of objects for the list view
            active_ids = _app_state.active_object_ids
            if not active_ids:
                return jsonify({"objects": []})

            # Use active ids to keep the same filtered/sorted view as desktop
            df_subset = _app_state.df_reg.loc[active_ids]
            df_obs_subset = _app_state.df_obs.loc[active_ids]

            objects = []
            for oid in active_ids:
                try:
                    row = df_subset.loc[oid]
                    obs_row = df_obs_subset.loc[oid]
                    if isinstance(row, pd.DataFrame):
                        row = row.iloc[0]
                    if isinstance(obs_row, pd.DataFrame):
                        obs_row = obs_row.iloc[0]

                    objects.append({
                        "id": str(oid),
                        "genus": str(row.get("Genus", "")),
                        "species": str(row.get("Species", "")),
                        "reviewed": bool(obs_row.get("Reviewed", False))
                    })
                except Exception as e:
                    print(f"Error processing object {oid}: {e}")

            return jsonify({"objects": objects})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/object/<oid>', methods=['GET'])
def get_object_detail(oid):
    if not _app_state or _app_state.df_reg is None:
        return jsonify({"error": "No database loaded"}), 400

    with _app_state.df_lock:
        try:
            if oid not in _app_state.df_reg.index:
                return jsonify({"error": "Object not found"}), 404

            reg_row = _app_state.df_reg.loc[oid]
            obs_row = _app_state.df_obs.loc[oid]

            if isinstance(reg_row, pd.DataFrame):
                reg_row = reg_row.iloc[0]
            if isinstance(obs_row, pd.DataFrame):
                obs_row = obs_row.iloc[0]

            data = {
                "id": str(oid),
                "reg": reg_row.where(pd.notnull(reg_row), None).to_dict(),
                "obs": obs_row.where(pd.notnull(obs_row), None).to_dict()
            }

            # Try to find images
            images = []
            if _app_state.df_photo is not None and oid in _app_state.df_photo.index:
                photo_row = _app_state.df_photo.loc[oid]
                if isinstance(photo_row, pd.DataFrame):
                    photo_row = photo_row.iloc[0]
                for col in _app_state.df_photo.columns:
                    path = str(photo_row.get(col, ""))
                    if path and path != "nan" and os.path.exists(path):
                        images.append(f"/api/image/{oid}/{col}")

            data["images"] = images

            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/update', methods=['POST'])
def update_object():
    if not _app_state or _app_state.df_reg is None:
        return jsonify({"error": "No database loaded"}), 400

    data = request.json
    if not data or "id" not in data:
        return jsonify({"error": "Invalid request"}), 400

    oid = data["id"]

    with _app_state.df_lock:
        try:
            if oid not in _app_state.df_reg.index:
                return jsonify({"error": "Object not found"}), 404

            # Perform updates
            if "reg" in data:
                for k, v in data["reg"].items():
                    if k in _app_state.df_reg.columns:
                        _app_state.df_reg.at[oid, k] = v

            if "obs" in data:
                for k, v in data["obs"].items():
                    if k in _app_state.df_obs.columns:
                        _app_state.df_obs.at[oid, k] = v
                        if k == "Reviewed" and v:
                            import datetime
                            _app_state.df_obs.at[oid, "Reviewed_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            _app_state.dirty = True

            # Notify Tkinter main thread
            if _ui_root:
                _ui_root.event_generate("<<MobileEditReceived>>", when="tail")

            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/image/<oid>/<col>', methods=['GET'])
def get_image(oid, col):
    if not _app_state or _app_state.df_photo is None:
        return jsonify({"error": "No database loaded"}), 400

    with _app_state.df_lock:
        if oid not in _app_state.df_photo.index:
            return jsonify({"error": "Image not found"}), 404

        photo_row = _app_state.df_photo.loc[oid]
        if isinstance(photo_row, pd.DataFrame):
            photo_row = photo_row.iloc[0]

        if col not in _app_state.df_photo.columns:
             return jsonify({"error": "Image not found"}), 404

        filepath = str(photo_row.get(col, ""))
        if filepath and filepath != "nan" and os.path.exists(filepath):
            return send_file(filepath)
        else:
            return jsonify({"error": "Image not found"}), 404

def _run_server(host, port):
    # Disable reloader because it spawns a new thread which can break Tkinter
    app.run(host=host, port=port, debug=False, use_reloader=False)

def start_mobile_server(app_state, ui_root, host='0.0.0.0', port=5000):
    global _app_state, _ui_root
    _app_state = app_state
    _ui_root = ui_root

    thread = threading.Thread(target=_run_server, args=(host, port), daemon=True)
    thread.start()
    return thread
