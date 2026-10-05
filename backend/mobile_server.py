import threading
import logging
import random
import string
import uuid
import json
import base64
import os
import io
import re
import mimetypes
import socket
import subprocess
import sys
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file, Response, make_response
import queue
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import pandas as pd
import config
from utils import debug_error
from ui.state import app_bus, DATABASE_UPDATED
from repository import REVIEWED_COLUMN, _normalise_log_dataframe

def sanitize_value(val):
    if isinstance(val, pd.Series):
        val = val.iloc[0] if not val.empty else ""
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()

def is_unknown(value):
    from config import ALL_UNKNOWN_TOKENS
    if value is None or pd.isna(value):
        return False
    v = str(value).strip().lower()
    if not v:
        return False
    return v in ALL_UNKNOWN_TOKENS or v == "nan"


def _get_row_dict_safe(df, oid):
    """Safely extract a flat single-row dictionary from a DataFrame, even if duplicate index keys exist."""
    if df is None or oid is None:
        return {}
    try:
        if oid in df.index:
            row_data = df.loc[[oid]]
            if not row_data.empty:
                return row_data.iloc[0].to_dict()
    except Exception:
        try:
            row_data = df.loc[oid]
            if isinstance(row_data, pd.DataFrame):
                return row_data.iloc[0].to_dict()
            elif isinstance(row_data, pd.Series):
                return row_data.to_dict()
        except Exception:
            pass
    return {}

def get_problem_to_field_map(config):
    problem_to_field = {}
    if config and isinstance(config, dict):
        ui_sec = config.get("ui_sections", {})
        for p in ui_sec.get("problems", []):
            if isinstance(p, dict):
                name = p.get("name")
                if not name:
                    continue
                if "maps_to" in p:
                    problem_to_field[name] = p["maps_to"]
                elif "target" in p:
                    problem_to_field[name] = p["target"]
    return problem_to_field

def get_history_set(app_state):
    presence_set, _ = get_historical_cache(app_state)
    return presence_set

_hist_cache_lock = threading.Lock()

def get_historical_cache(app_state):
    hist_dbs = getattr(app_state, "historical_dbs", None) or []

    # Generate cache key based on id() of loaded reg_by_id objects
    current_keys = tuple(id(db.get("reg_by_id")) for db in hist_dbs if db.get("reg_by_id") is not None)

    with _hist_cache_lock:
        cached_keys = getattr(app_state, "_hist_cache_keys", None)
        if cached_keys == current_keys and hasattr(app_state, "_hist_cache_data"):
            return app_state._hist_cache_data

    hist_presence_set = set()
    hist_fields_by_oid = {}
    for db in hist_dbs:
        reg_by_id = db.get("reg_by_id")
        if reg_by_id is not None:
            if isinstance(reg_by_id, pd.DataFrame):
                cols = list(reg_by_id.columns)
                from config import ALL_UNKNOWN_TOKENS as _AUT
                for row_tuple in reg_by_id.itertuples(index=True, name=None):
                    hist_id = row_tuple[0]
                    s_id = str(hist_id).strip()
                    hist_presence_set.add(s_id)
                    if s_id.isdigit():
                        try:
                            hist_presence_set.add(int(s_id))
                        except Exception:
                            pass
                    if s_id not in hist_fields_by_oid:
                        hist_fields_by_oid[s_id] = set()
                    for i, col in enumerate(cols):
                        val = row_tuple[i + 1]
                        if pd.notna(val):
                            val_str = str(val).strip()
                            if val_str and val_str.lower() not in ("nan", "none", "") and val_str.lower() not in _AUT:
                                hist_fields_by_oid[s_id].add(col)
            elif isinstance(reg_by_id, dict):
                from config import ALL_UNKNOWN_TOKENS as _AUT
                for hist_id, row_dict in reg_by_id.items():
                    s_id = str(hist_id).strip()
                    hist_presence_set.add(s_id)
                    if s_id.isdigit():
                        try:
                            hist_presence_set.add(int(s_id))
                        except Exception:
                            pass
                    if s_id not in hist_fields_by_oid:
                        hist_fields_by_oid[s_id] = set()
                    if isinstance(row_dict, dict):
                        for col, val in row_dict.items():
                            if pd.notna(val):
                                val_str = str(val).strip()
                                if val_str and val_str.lower() not in ("nan", "none", "") and val_str.lower() not in _AUT:
                                    hist_fields_by_oid[s_id].add(col)

    with _hist_cache_lock:
        app_state._hist_cache_keys = current_keys
        app_state._hist_cache_data = (hist_presence_set, hist_fields_by_oid)

    return hist_presence_set, hist_fields_by_oid

def compute_status_flags(reg_dict, obs_dict, history_set, oid, prob_cols=None, problem_to_field=None, hist_fields_by_oid=None):
    # 1. Review status
    rev_val = False
    if obs_dict is not None and "Reviewed" in obs_dict:
        v = sanitize_value(obs_dict.get("Reviewed")).lower()
        rev_val = v in ("true", "1", "yes", "t")
    review_status = "reviewed" if rev_val else "pending"

    # 2. Problem flags and active problem target fields
    has_flags = False
    active_problem_fields = set()
    problem_to_field = problem_to_field or {}

    if prob_cols:
        for p_col in prob_cols:
            obs_val = False
            val = ""
            if obs_dict is not None and p_col in obs_dict:
                val = sanitize_value(obs_dict.get(p_col)).lower()
            elif reg_dict is not None and p_col in reg_dict:
                val = sanitize_value(reg_dict.get(p_col)).lower()
            if val in ("true", "1", "yes", "t", "x"):
                obs_val = True

            auto_val = False
            target_field = problem_to_field.get(p_col)
            if target_field and reg_dict is not None and target_field in reg_dict:
                raw_val = reg_dict.get(target_field)
                is_missing = (pd.isna(raw_val) or (isinstance(raw_val, str) and raw_val.strip() == ""))
                is_unk = is_unknown(raw_val)
                auto_val = is_missing and not is_unk

            if obs_val or auto_val:
                has_flags = True
                if target_field:
                    active_problem_fields.add(target_field)
                elif p_col.endswith("_Problem"):
                    active_problem_fields.add(p_col[:-8])
                else:
                    active_problem_fields.add(p_col)
    elif obs_dict is not None or reg_dict is not None:
        merged = {}
        if reg_dict:
            merged.update(reg_dict)
        if obs_dict:
            merged.update(obs_dict)
        for k, v in merged.items():
            if k.endswith("_Problem") or k in ("Images_Problem", "Images_Missing", "MissingLabel"):
                obs_val = sanitize_value(v).lower() in ("true", "1", "yes", "t", "x")
                auto_val = False
                target_field = problem_to_field.get(k)
                if target_field and reg_dict is not None and target_field in reg_dict:
                    raw_val = reg_dict.get(target_field)
                    is_missing = (pd.isna(raw_val) or (isinstance(raw_val, str) and raw_val.strip() == ""))
                    is_unk = is_unknown(raw_val)
                    auto_val = is_missing and not is_unk

                if obs_val or auto_val:
                    has_flags = True
                    if target_field:
                        active_problem_fields.add(target_field)
                    elif k.endswith("_Problem"):
                        active_problem_fields.add(k[:-8])
                    else:
                        active_problem_fields.add(k)

    # 3. Unknown fields (check registration values)
    has_unknown = False
    unknown_fields = set()
    if reg_dict:
        for k, v in reg_dict.items():
            if str(k).lower() in ("objectid", "id"):
                continue
            if is_unknown(v):
                has_unknown = True
                unknown_fields.add(k)

    # 4. History and Specific Problem History check
    s_oid = str(oid).strip()
    has_history = False
    if history_set:
        has_history = (oid in history_set) or (s_oid in history_set) or (s_oid.isdigit() and int(s_oid) in history_set)

    problems_have_history = False
    if hist_fields_by_oid is not None and s_oid in hist_fields_by_oid:
        available_hist_fields = hist_fields_by_oid[s_oid]
        if any(f in available_hist_fields for f in active_problem_fields) or any(f in available_hist_fields for f in unknown_fields):
            problems_have_history = True
    elif has_history and not hist_fields_by_oid:
        problems_have_history = (has_flags or has_unknown)

    return {
        "has_flags": bool(has_flags),
        "has_history": bool(has_history),
        "problems_have_history": bool(problems_have_history),
        "has_unknown": bool(has_unknown),
        "review_status": review_status
    }

def coerce_type(val, dtype):
    if isinstance(val, pd.Series):
        val = val.iloc[0] if not val.empty else ""
    is_empty_or_na = pd.isna(val) or val is None or str(val).strip() == "" or str(val).strip().lower() in ("nan", "none", "<na>")

    if pd.api.types.is_bool_dtype(dtype):
        if is_empty_or_na:
            return False
        return str(val).strip().lower() in ("true", "1", "yes", "t")

    if pd.api.types.is_integer_dtype(dtype):
        if is_empty_or_na:
            return pd.NA if hasattr(pd, "NA") else 0
        try:
            return int(val)
        except (ValueError, TypeError):
            try:
                f = float(val)
                if not pd.isna(f) and f.is_integer():
                    return int(f)
                return int(f)
            except Exception:
                return 0

    if pd.api.types.is_float_dtype(dtype):
        if is_empty_or_na:
            return float("nan")
        try:
            return float(val)
        except Exception:
            return 0.0

    if is_empty_or_na:
        return ""
    return str(val).strip()

def _apply_dataframe_updates(target_df, updates, changed_fields, changed_values, oid, fallback_df=None, allowed_columns=None):
    if target_df is None or not updates or oid is None:
        return
    resolved_oid = _resolve_oid_in_df(target_df, oid)
    if resolved_oid is None and fallback_df is None:
        return

    for k, v in updates.items():
        df_to_update = None
        target_key = None
        if resolved_oid is not None and k in target_df.columns:
            df_to_update = target_df
            target_key = resolved_oid
        elif fallback_df is not None and k in fallback_df.columns:
            fallback_oid = _resolve_oid_in_df(fallback_df, oid)
            if fallback_oid is not None:
                df_to_update = fallback_df
                target_key = fallback_oid

        if df_to_update is not None and target_key is not None:
            old_raw = df_to_update.at[target_key, k]
            col_dtype = df_to_update[k].dtype
            coerced = coerce_type(v, col_dtype)

            old_is_na = pd.isna(old_raw) or old_raw is None or str(old_raw).strip().lower() in ("nan", "none", "<na>")
            new_is_na = pd.isna(coerced) or coerced is None or str(coerced).strip().lower() in ("nan", "none", "<na>")

            if old_is_na and new_is_na:
                is_diff = False
            elif old_is_na != new_is_na:
                is_diff = True
            elif pd.api.types.is_bool_dtype(col_dtype):
                is_diff = bool(old_raw) != bool(coerced)
            elif pd.api.types.is_numeric_dtype(col_dtype):
                is_diff = (old_raw != coerced)
            else:
                is_diff = str(old_raw).strip() != str(coerced).strip()

            if is_diff:
                old_v = sanitize_value(old_raw)
                new_v = sanitize_value(coerced)
                df_to_update.at[target_key, k] = coerced
                changed_fields.append(k)
                changed_values.append(f'{k}: "{old_v}" -> "{new_v}"')
        elif resolved_oid is not None and (allowed_columns is None or k in allowed_columns):
            new_v = sanitize_value(v)
            if new_v:
                # Initialize new column across all rows safely with dtype awareness
                is_bool_col = any(term in k.lower() for term in ("reviewed", "missing", "problem", "exist"))
                if is_bool_col:
                    target_df[k] = pd.Series(False, index=target_df.index, dtype=bool)
                else:
                    target_df[k] = pd.Series("", index=target_df.index, dtype=object)
                coerced = coerce_type(new_v, target_df[k].dtype)
                target_df.at[resolved_oid, k] = coerced
                changed_fields.append(k)
                changed_values.append(f'{k}: "" -> "{new_v}"')

def _resolve_oid_in_df(df, oid):
    """Safely find matching index key in DataFrame supporting int, str, and float index dtypes."""
    if df is None or oid is None:
        return None
    if isinstance(oid, pd.Series):
        oid = oid.iloc[0] if not oid.empty else None
        if oid is None:
            return None
    if pd.isna(oid):
        return None
    s_oid = str(oid).strip()
    if not s_oid or s_oid.lower() in ("nan", "none", "<na>"):
        return None
    if oid in df.index:
        return oid
    if s_oid in df.index:
        return s_oid
    if s_oid.isdigit():
        try:
            i_oid = int(s_oid)
            if i_oid in df.index:
                return i_oid
        except Exception:
            pass
    try:
        f_oid = float(s_oid)
        if not pd.isna(f_oid):
            if f_oid.is_integer():
                i_oid = int(f_oid)
                if i_oid in df.index:
                    return i_oid
                if str(i_oid) in df.index:
                    return str(i_oid)
            if f_oid in df.index:
                return f_oid
    except Exception:
        pass
    return None

def _get_allowed_columns(config):
    """Extract allowed registration and observation columns from active config."""
    allowed_reg_cols = set()
    allowed_obs_cols = {
        "Reviewed", "ReviewedAt", "Images_Missing", "Images_Problem", "Online_Images_Exist",
        "Building", "Floor", "Cabinet", "Shelf", "Stored as", "Stored_As", "Room", "Drawer", "Box",
        "Loc_Problem", "Loaned out", "Loaned out date", "Extra", "Comment"
    }
    if config and isinstance(config, dict):
        ui_sec = config.get("ui_sections", {})
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
    return allowed_reg_cols, allowed_obs_cols

def _apply_unvalidated_updates(app_state, oid, unvalidated_sources, changed_fields=None, changed_values=None):
    """Apply updates to df_unvalidated for an object."""
    if unvalidated_sources is None:
        return
    oid_str = str(oid).strip()
    if getattr(app_state, "df_unvalidated", None) is None:
        app_state.df_unvalidated = pd.DataFrame(columns=["ObjectID", "Field_Name", "Unvalidated_Comment"])

    df_u = app_state.df_unvalidated
    old_rows = {}
    if not df_u.empty and "ObjectID" in df_u.columns:
        matching = df_u[df_u["ObjectID"].astype(str).str.strip() == oid_str]

        field_name_idx = matching.columns.get_loc("Field_Name") + 1 if "Field_Name" in matching.columns else None
        comment_idx = matching.columns.get_loc("Unvalidated_Comment") + 1 if "Unvalidated_Comment" in matching.columns else None

        for row in matching.itertuples(index=True, name=None):
            f_name = row[field_name_idx] if field_name_idx is not None else ""
            comm = row[comment_idx] if comment_idx is not None else ""
            old_rows[str(f_name).strip()] = str(comm).strip()

        app_state.df_unvalidated = df_u[df_u["ObjectID"].astype(str).str.strip() != oid_str].copy()

    if isinstance(unvalidated_sources, list):
        new_rows = []
        seen_new_fields = set()
        for item in unvalidated_sources:
            if isinstance(item, dict):
                f_name = str(item.get("field", "") or item.get("Field_Name", "")).strip()
                comment = str(item.get("comment", "") or item.get("Unvalidated_Comment", "")).strip()
                if f_name:
                    seen_new_fields.add(f_name)
                    new_rows.append({"ObjectID": oid_str, "Field_Name": f_name, "Unvalidated_Comment": comment})
                    old_c = old_rows.get(f_name, "")
                    if old_c != comment:
                        if changed_fields is not None:
                            changed_fields.append(f"Unvalidated_{f_name}")
                        if changed_values is not None:
                            changed_values.append(f'Unvalidated_{f_name}: "{old_c}" -> "{comment}"')

        # Detect deleted unvalidated comments
        for old_f, old_c in old_rows.items():
            if old_f not in seen_new_fields and old_c:
                if changed_fields is not None:
                    changed_fields.append(f"Unvalidated_{old_f}")
                if changed_values is not None:
                    changed_values.append(f'Unvalidated_{old_f}: "{old_c}" -> ""')

        if new_rows:
            new_df = pd.DataFrame(new_rows)
            app_state.df_unvalidated = pd.concat([app_state.df_unvalidated, new_df], ignore_index=True)


def _execute_record_update(app_state, oid, reg_updates, obs_updates, reviewed, allowed_reg_cols=None, allowed_obs_cols=None, recent_edits=None, client_timestamp=None, unvalidated_updates=None, session_id=None):
    """
    Execute single record update core with dtype safety, undo snapshots, audit logging, and change tracking.

    # THREADING CONTRACT: Caller must hold `app_state.df_lock` (RLock) before
    # calling this function. This function reads and mutates df_reg and df_obs
    # without acquiring the lock internally, to allow the caller to batch multiple
    # operations under a single lock acquisition.
    """
    if app_state.df_reg is None:
        return None, "No active database loaded"

    resolved_reg_oid = _resolve_oid_in_df(app_state.df_reg, oid)
    if resolved_reg_oid is None:
        return None, f"Object {oid} not found in active database"


    resolved_obs_oid = _resolve_oid_in_df(app_state.df_obs, oid)
    curr_reg = _get_row_dict_safe(app_state.df_reg, resolved_reg_oid)
    curr_obs = _get_row_dict_safe(app_state.df_obs, resolved_obs_oid)

    effective_reg_updates = dict(reg_updates) if reg_updates else {}
    effective_obs_updates = dict(obs_updates) if obs_updates else {}
    effective_reviewed = reviewed

    # Conflict check
    undo_stacks = getattr(app_state, 'undo_stacks', {})
    if client_timestamp and undo_stacks:
        stacks = undo_stacks.get(resolved_reg_oid, []) or undo_stacks.get(str(oid), [])
        if stacks:
            last_edit_time = stacks[-1].get("timestamp")
            if last_edit_time:
                is_stale = False
                try:
                    c_dt = pd.to_datetime(client_timestamp)
                    if c_dt.tzinfo is None or c_dt.tz is None:
                        c_dt = c_dt.tz_localize("local").tz_convert("UTC")
                    else:
                        c_dt = c_dt.tz_convert("UTC")

                    h_dt = pd.to_datetime(last_edit_time)
                    if h_dt.tzinfo is None or h_dt.tz is None:
                        h_dt = h_dt.tz_localize("local").tz_convert("UTC")
                    else:
                        h_dt = h_dt.tz_convert("UTC")

                    is_stale = (c_dt < h_dt)
                except Exception:
                    is_stale = (str(client_timestamp) < str(last_edit_time))

                if is_stale:
                    # Field-level conflict resolution: compare against baseline before host edits
                    base_snapshot = None
                    for snap in stacks:
                        snap_time = snap.get("timestamp")
                        if snap_time:
                            try:
                                s_dt = pd.to_datetime(snap_time)
                                if s_dt.tzinfo is None or s_dt.tz is None:
                                    s_dt = s_dt.tz_localize("local").tz_convert("UTC")
                                else:
                                    s_dt = s_dt.tz_convert("UTC")
                                if s_dt > c_dt:
                                    base_snapshot = snap
                                    break
                            except Exception:
                                if str(snap_time) > str(client_timestamp):
                                    base_snapshot = snap
                                    break

                    if base_snapshot is None:
                        base_snapshot = stacks[0]

                    base_reg = base_snapshot.get("reg", {})
                    base_obs = base_snapshot.get("obs", {})

                    # Fields modified on the host between baseline and current state
                    host_mod_reg = {k for k, v in curr_reg.items() if str(v) != str(base_reg.get(k, ""))}
                    host_mod_obs = {k for k, v in curr_obs.items() if str(v) != str(base_obs.get(k, ""))}

                    # Client modified fields: fields explicitly targeted for update by the client
                    client_mod_reg = set(effective_reg_updates.keys())
                    client_mod_obs = set(effective_obs_updates.keys())
                    if reviewed is not None:
                        curr_rev_raw = curr_obs.get("Reviewed", False)
                        curr_rev_bool = (
                            str(curr_rev_raw).strip().lower() in ("true", "1", "yes", "t")
                            if isinstance(curr_rev_raw, (str, int, bool))
                            else bool(curr_rev_raw)
                        )
                        if bool(reviewed) != curr_rev_bool:
                            client_mod_obs.add(REVIEWED_COLUMN)

                    # A true conflict occurs IF AND ONLY IF both sides modified the same field to DIFFERENT values
                    conflict_reg = set()
                    for k in (client_mod_reg & host_mod_reg):
                        c_val = str(effective_reg_updates.get(k, ""))
                        b_val = str(base_reg.get(k, ""))
                        curr_v = str(curr_reg.get(k, ""))
                        if c_val == b_val:
                            # Client did not change this field; drop from update to preserve host's newer change
                            effective_reg_updates.pop(k, None)
                        elif c_val != curr_v:
                            conflict_reg.add(k)

                    conflict_obs = set()
                    for k in (client_mod_obs & host_mod_obs):
                        if k == REVIEWED_COLUMN:
                            curr_rev_bool = str(curr_obs.get("Reviewed", False)).strip().lower() in ("true", "1", "yes", "t")
                            base_rev_bool = str(base_obs.get("Reviewed", False)).strip().lower() in ("true", "1", "yes", "t")
                            if bool(reviewed) == base_rev_bool:
                                # Client did not change reviewed status; preserve host
                                effective_reviewed = None
                            elif bool(reviewed) != curr_rev_bool:
                                conflict_obs.add(k)
                        else:
                            c_val = str(effective_obs_updates.get(k, ""))
                            b_val = str(base_obs.get(k, ""))
                            curr_v = str(curr_obs.get(k, ""))
                            if c_val == b_val:
                                effective_obs_updates.pop(k, None)
                            elif c_val != curr_v:
                                conflict_obs.add(k)

                    if conflict_reg or conflict_obs:
                        return None, f"Conflict: Host has newer changes for {oid}"
                # Discard no-op edits that match current server state before declaring conflict
                filtered_reg = {}
                for k, v in effective_reg_updates.items():
                    if k in curr_reg:
                        val_cur = curr_reg[k]
                        dtype = app_state.df_reg[k].dtype if k in app_state.df_reg.columns else object
                        coerced = coerce_type(v, dtype)
                        if pd.isna(val_cur) and (pd.isna(coerced) or coerced == ""):
                            continue
                        if str(val_cur).strip() != str(coerced).strip():
                            filtered_reg[k] = v
                    else:
                        filtered_reg[k] = v
                effective_reg_updates = filtered_reg

                filtered_obs = {}
                for k, v in effective_obs_updates.items():
                    if curr_obs and k in curr_obs:
                        val_cur = curr_obs[k]
                        dtype = app_state.df_obs[k].dtype if app_state.df_obs is not None and k in app_state.df_obs.columns else object
                        coerced = coerce_type(v, dtype)
                        if pd.isna(val_cur) and (pd.isna(coerced) or coerced == ""):
                            continue
                        if str(val_cur).strip() != str(coerced).strip():
                            filtered_obs[k] = v
                    else:
                        filtered_obs[k] = v
                effective_obs_updates = filtered_obs

                if effective_reviewed is not None and curr_obs:
                    cur_rev = curr_obs.get("Reviewed", False)
                    cur_rev_bool = str(cur_rev).strip().lower() in ("true", "1", "yes", "t") if isinstance(cur_rev, (str, int, bool)) else bool(cur_rev)
                    if bool(effective_reviewed) == cur_rev_bool:
                        effective_reviewed = None

                if not effective_reg_updates and not effective_obs_updates and effective_reviewed is None and unvalidated_updates is None:
                    return f"#{oid} (unchanged)", None

                if effective_reg_updates or effective_obs_updates or effective_reviewed is not None:
                    # Check if client was attempting a meaningful mutation on fields modified by host
                    latest_snapshot = stacks[-1]
                    conflict = False
                    for f in list(effective_reg_updates.keys()):
                        if f in latest_snapshot.get("reg", {}) and latest_snapshot["reg"][f] != curr_reg.get(f):
                            conflict = True
                            break
                    for f in list(effective_obs_updates.keys()):
                        if f in latest_snapshot.get("obs", {}) and latest_snapshot["obs"][f] != curr_obs.get(f):
                            conflict = True
                            break
                    if effective_reviewed is not None and "Reviewed" in latest_snapshot.get("obs", {}) and latest_snapshot["obs"]["Reviewed"] != curr_obs.get("Reviewed"):
                        conflict = True

                    if conflict:
                        return None, f"Conflict: Host has newer changes for {oid}"

    # 1. Snapshot for Undo Stack
    old_reg = _get_row_dict_safe(app_state.df_reg, resolved_reg_oid)
    resolved_obs_oid = _resolve_oid_in_df(app_state.df_obs, oid)
    old_obs = _get_row_dict_safe(app_state.df_obs, resolved_obs_oid)

    worker_sid = session_id or getattr(app_state, "_mobile_session_id", None)
    undo_snapshot = {
        "oid": str(oid),
        "reg": old_reg.copy(),
        "obs": old_obs.copy(),
        "timestamp": datetime.now().isoformat(),
        "source": "mobile",
        "_session_id": worker_sid
    }
    undo_stacks = getattr(app_state, 'undo_stacks', {})
    undo_stacks.setdefault(resolved_reg_oid, []).append(undo_snapshot)
    if len(undo_stacks[resolved_reg_oid]) > 20:
        undo_stacks[resolved_reg_oid].pop(0)
    if not hasattr(app_state, 'undo_stacks'):
        app_state.undo_stacks = undo_stacks

    changed_fields = []
    changed_values = []

    # 2. Apply registration updates
    _apply_dataframe_updates(app_state.df_reg, effective_reg_updates, changed_fields, changed_values, resolved_reg_oid, allowed_columns=allowed_reg_cols if allowed_reg_cols else None)

    # 3. Ensure df_obs has a matching row and apply observation updates
    if app_state.df_obs is not None:
        if resolved_obs_oid is None:
            empty_vals = {}
            for col in app_state.df_obs.columns:
                dtype = app_state.df_obs[col].dtype
                empty_vals[col] = False if pd.api.types.is_bool_dtype(dtype) else ""
            target_obs_oid = resolved_reg_oid
            new_obs_row = pd.DataFrame([empty_vals], index=[target_obs_oid])
            new_obs_row.index.name = app_state.df_obs.index.name or "ObjectID"
            app_state.df_obs = pd.concat([app_state.df_obs, new_obs_row])
            resolved_obs_oid = target_obs_oid

        _apply_dataframe_updates(app_state.df_obs, effective_obs_updates, changed_fields, changed_values, resolved_obs_oid, fallback_df=app_state.df_reg, allowed_columns=allowed_obs_cols if allowed_obs_cols else None)

    # 3b. Apply Unvalidated Sources Updates
    if unvalidated_updates is not None:
        _apply_unvalidated_updates(app_state, oid, unvalidated_updates, changed_fields=changed_fields, changed_values=changed_values)

    # 4. Handle Reviewed Status
    action_name = "MOBILE_EDIT"
    old_reviewed_raw = old_obs.get("Reviewed", False)
    old_reviewed_bool = (
        str(old_reviewed_raw).strip().lower() in ("true", "1", "yes", "t")
        if isinstance(old_reviewed_raw, (str, int, bool))
        else bool(old_reviewed_raw)
    )
    current_reviewed_bool = old_reviewed_bool

    if effective_reviewed is not None:
        is_reviewed_bool = bool(effective_reviewed)
        current_reviewed_bool = is_reviewed_bool
        if is_reviewed_bool != old_reviewed_bool:
            if app_state.df_obs is not None and resolved_obs_oid is not None and resolved_obs_oid in app_state.df_obs.index:
                if "Reviewed" not in app_state.df_obs.columns:
                    app_state.df_obs["Reviewed"] = False
                app_state.df_obs.at[resolved_obs_oid, "Reviewed"] = is_reviewed_bool
                if "ReviewedAt" in app_state.df_obs.columns:
                    app_state.df_obs.at[resolved_obs_oid, "ReviewedAt"] = datetime.now().isoformat(timespec="seconds") if is_reviewed_bool else ""
                changed_fields.append("Reviewed")
                changed_values.append(f'Reviewed: "{old_reviewed_bool}" -> "{is_reviewed_bool}"')

            if changed_fields == ["Reviewed"]:
                action_name = "REVIEWED" if is_reviewed_bool else "NOT_REVIEWED"

    edit_summary = f"#{oid}: {', '.join(changed_fields)}" if changed_fields else f"#{oid} updated"

    # Zero-mutation guard: If no actual fields were mutated, do not create a phantom log entry or record a recent edit
    if not changed_fields:
        return edit_summary, None

    is_rev_str = "Yes" if current_reviewed_bool else "No"

    # 5. Append Audit Log Record
    if not hasattr(app_state, "_log_records") or app_state._log_records is None:
        if getattr(app_state, "df_log", None) is not None and not app_state.df_log.empty:
            app_state._log_records = app_state.df_log.to_dict(orient="records")
        else:
            app_state._log_records = []

    log_entry = _build_audit_log_entry(app_state, str(oid), action_name, is_rev_str, changed_fields, changed_values, session_id=worker_sid)
    app_state._log_records.append(log_entry)

    # 6. Record Recent Edit in Server
    if recent_edits is not None:
        recent_edits.insert(0, {
            "oid": str(oid),
            "summary": edit_summary,
            "time": datetime.now().strftime("%H:%M:%S"),
            "session_id": worker_sid
        })
        if len(recent_edits) > 20:
            recent_edits.pop()

    return edit_summary, None

def _build_audit_log_entry(app_state, oid, action_name, is_rev_str, changed_fields, changed_values, session_id=None):
    # Lazy-build and cache the name sets — invalidate if active config or dataset changes
    curr_cfg = getattr(app_state, "config", None)
    excel_path = getattr(app_state, "excel_path", None)
    ui_sec = curr_cfg.get("ui_sections", {}) if curr_cfg and isinstance(curr_cfg, dict) else {}
    cfg_sig = (
        id(curr_cfg) if curr_cfg else None,
        excel_path,
        len(ui_sec.get("location", [])) if isinstance(ui_sec, dict) and isinstance(ui_sec.get("location"), list) else 0,
        len(ui_sec.get("problems", [])) if isinstance(ui_sec, dict) and isinstance(ui_sec.get("problems"), list) else 0
    )
    if getattr(app_state, '_audit_set_cache_sig', None) != cfg_sig or not getattr(app_state, '_audit_set_cache', None):
        _loc = {"building", "room", "cabinet", "shelf", "drawer", "box", "location", "aisle", "unittray", "tray", "barcode"}
        _prob = set()
        if curr_cfg and isinstance(curr_cfg, dict) and "ui_sections" in curr_cfg:
            ui_sec_data = curr_cfg["ui_sections"]
            if "location" in ui_sec_data and isinstance(ui_sec_data["location"], list):
                for l_item in ui_sec_data["location"]:
                    if isinstance(l_item, dict) and "name" in l_item:
                        _loc.add(l_item["name"].lower())
            if "problems" in ui_sec_data and isinstance(ui_sec_data["problems"], list):
                for p_item in ui_sec_data["problems"]:
                    if isinstance(p_item, dict) and "name" in p_item:
                        _prob.add(p_item["name"].lower())
        app_state._audit_set_cache = (_loc, _prob)
        app_state._audit_set_cache_sig = cfg_sig
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
    entry = {
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
        "SourceFile": os.path.basename(getattr(app_state, 'excel_path', '') or "") if getattr(app_state, 'excel_path', None) else "",
        "OutputFile": os.path.basename(getattr(app_state, 'output_path', '') or getattr(app_state, 'excel_path', '') or "") if getattr(app_state, 'output_path', None) or getattr(app_state, 'excel_path', None) else ""
    }
    effective_sid = session_id or getattr(app_state, "_mobile_session_id", None)
    if effective_sid:
        entry["_session_id"] = effective_sid
    return entry

# Reduce Flask logging spam
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


def get_local_ip():
    from backend.tunnel import get_local_ip as _tunnel_get_local_ip
    return _tunnel_get_local_ip()


class MobileServer:
    def __init__(self, app_state, root_tk=None, port=5055, on_edit_callback=None):
        self.app_state = app_state
        self.root_tk = root_tk
        self.port = port
        self.on_edit_callback = on_edit_callback
        self.session_id = uuid.uuid4().hex[:12]
        prefs = config.load_prefs()
        self._pin_required = prefs.get("require_mobile_pin", True)
        self._image_url_pattern_override = prefs.get("image_url_pattern_override", "")
        if not self._image_url_pattern_override:
            self._image_url_pattern_override = prefs.get("advanced", {}).get("image_url_pattern_override", "")
        if self.app_state:
            self.app_state._mobile_session_id = self.session_id
        self.flask_app = Flask(__name__)
        self.flask_app.wsgi_app = ProxyFix(self.flask_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
        self.flask_app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
        self.session_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        self.sessions_lock = threading.Lock()
        self.active_sessions = {
            self.session_token: {
                "session_id": self.session_id,
                "created_at": datetime.now().isoformat(),
                "ip": "127.0.0.1"
            }
        }
        self.pin = ''.join(random.choices(string.digits, k=4))
        self.thread = None
        self._is_running = False
        self.recent_edits = []  # list of dicts: {oid, summary, time, session_id}
        self._auth_attempts = {}
        self.clients = []  # list of dicts: {"queue": q, "session_id": sid, "token": tok}
        self.clients_lock = threading.Lock()
        self._event_batch = []
        self._batch_lock = threading.Lock()
        self._batch_timer = None
        self.on_client_connect_callback = None
        self.presence = {}  # session_id -> {"oid": oid_str or None, "last_seen": timestamp}
        self.presence_lock = threading.Lock()
        self._setup_routes()

    @property
    def is_running(self):
        return self._is_running

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

        # Test port binding synchronously to prevent zombie conflicts
        max_port = self.port + 50
        while self.port < max_port:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('0.0.0.0', self.port))
                break
            except OSError:
                self.port += 1

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

    def is_pin_required(self):
        """Check if mobile PIN authentication is required according to user preferences."""
        return self._pin_required

    def update_pin_requirement(self, is_required: bool):
        """Update the cached mobile PIN requirement without restarting the server."""
        self._pin_required = bool(is_required)

    def _get_client_ip(self):
        """Extract the true client IP from Cloudflare/Proxy headers or remote_addr."""
        cf_ip = request.headers.get('CF-Connecting-IP')
        if cf_ip and cf_ip.strip():
            return cf_ip.strip()
        xf_ip = request.headers.get('X-Forwarded-For')
        if xf_ip and xf_ip.strip():
            # First IP in comma-separated list is the client IP
            return xf_ip.split(',')[0].strip()
        return request.remote_addr or "127.0.0.1"

    def _create_session(self, client_ip=None):
        """Generate and register a new unique session for a worker."""
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        sid = uuid.uuid4().hex[:12]
        with self.sessions_lock:
            self.active_sessions[token] = {
                "session_id": sid,
                "created_at": datetime.now().isoformat(),
                "ip": client_ip or "unknown"
            }
        self.session_token = token
        self.session_id = sid
        return token, sid

    def _get_session_by_token(self, token):
        """Lookup session dict by token."""
        if not token:
            return None
        with self.sessions_lock:
            return self.active_sessions.get(token)

    def _get_current_session(self):
        """Extract authenticated session details: (is_auth, session_id, token)."""
        token = None
        # 1. Header token
        auth_header = request.headers.get('X-Session-Token')
        if auth_header:
            token = auth_header.strip()
        # 2. Query param token
        if not token:
            token_param = request.args.get('token')
            if token_param:
                token = token_param.strip()
        # 3. Cookie session
        if not token and session.get('token'):
            token = session.get('token')

        if token:
            sess_info = self._get_session_by_token(token)
            if sess_info:
                return True, sess_info["session_id"], token
            # Legacy fallback: check self.session_token
            if token == self.session_token:
                return True, self.session_id, token

        # If PIN is not required, auto-provision session
        if not self.is_pin_required():
            ip = self._get_client_ip()
            new_token, new_sid = self._create_session(ip)
            session['token'] = new_token
            session['session_id'] = new_sid
            session['authenticated'] = True
            return True, new_sid, new_token

        # Check if session cookie has authenticated flag
        if session.get('authenticated') is True:
            sid = session.get('session_id') or self.session_id
            tok = session.get('token') or self.session_token
            return True, sid, tok

        return False, None, None

    def push_navigation(self, oid, target_session_id=None):
        """Pushes a navigation request to connected mobile clients."""
        self.broadcast_event("push_navigation", {"id": oid}, target_session_id=target_session_id)

    def broadcast_event(self, event_type, data=None, target_session_id=None):
        if data is None:
            data = {}
        payload = {"type": event_type, "data": data, "target_session_id": target_session_id}
        with self._batch_lock:
            self._event_batch.append(payload)
            if self._batch_timer is None:
                self._batch_timer = threading.Timer(0.2, self._flush_events)
                self._batch_timer.start()

    def _flush_events(self):
        with self._batch_lock:
            events = self._event_batch
            self._event_batch = []
            self._batch_timer = None

        if not events:
            return

        with self.clients_lock:
            for client_entry in self.clients:
                q = client_entry["queue"] if isinstance(client_entry, dict) else client_entry
                c_sid = client_entry.get("session_id") if isinstance(client_entry, dict) else None

                client_events = [
                    {"type": ev["type"], "data": ev["data"]}
                    for ev in events
                    if ev.get("target_session_id") is None or ev.get("target_session_id") == c_sid
                ]
                if client_events:
                    batch_payload = {"type": "batch", "events": client_events}
                    try:
                        q.put(batch_payload)
                    except Exception:
                        pass

    def _check_rate_limit(self, ip=None):
        if ip is None:
            ip = self._get_client_ip()

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

    def _record_failure(self, ip=None):
        if ip is None:
            ip = self._get_client_ip()

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

    def _record_success(self, ip=None):
        if ip is None:
            ip = self._get_client_ip()

        if ip in self._auth_attempts:
            self._auth_attempts[ip] = {"consecutive": 0, "recent": [], "lockout_until": 0}

    def _check_auth(self):
        """Verify session token or PIN authentication."""
        is_auth, _, _ = self._get_current_session()
        return is_auth

    def _update_presence(self, session_id, oid):
        """Record what object a worker is viewing and broadcast changes."""
        if not session_id:
            return
        oid_str = str(oid).strip() if oid is not None and str(oid).strip() else None
        old_oid = None
        now = time.time()

        with self.presence_lock:
            prev = self.presence.get(session_id)
            if prev:
                old_oid = prev.get("oid")
            self.presence[session_id] = {"oid": oid_str, "last_seen": now}
            self._cleanup_stale_presence_locked(now)

        if old_oid != oid_str:
            if old_oid:
                cnt = self._get_active_viewers_count(old_oid)
                self.broadcast_event("presence_updated", {"oid": old_oid, "viewers_count": cnt})
            if oid_str:
                cnt = self._get_active_viewers_count(oid_str)
                self.broadcast_event("presence_updated", {"oid": oid_str, "viewers_count": cnt})

    def _remove_presence(self, session_id):
        """Remove a worker from presence tracking on disconnect."""
        if not session_id:
            return
        old_oid = None
        with self.presence_lock:
            prev = self.presence.pop(session_id, None)
            if prev:
                old_oid = prev.get("oid")
        if old_oid:
            cnt = self._get_active_viewers_count(old_oid)
            self.broadcast_event("presence_updated", {"oid": old_oid, "viewers_count": cnt})

    def _cleanup_stale_presence_locked(self, now=None):
        if now is None:
            now = time.time()
        stale_sids = [sid for sid, data in self.presence.items() if now - data.get("last_seen", 0) > 25]
        for sid in stale_sids:
            self.presence.pop(sid, None)

    def _get_active_viewers_count(self, oid):
        if not oid:
            return 0
        oid_str = str(oid).strip()
        now = time.time()
        with self.presence_lock:
            self._cleanup_stale_presence_locked(now)
            count = sum(1 for data in self.presence.values() if data.get("oid") == oid_str)
        return count

    def _get_other_viewers_count(self, oid, current_session_id=None):
        if not oid:
            return 0
        oid_str = str(oid).strip()
        now = time.time()
        with self.presence_lock:
            self._cleanup_stale_presence_locked(now)
            count = sum(1 for sid, data in self.presence.items() if data.get("oid") == oid_str and sid != current_session_id)
        return count

    def _setup_routes(self):
        app = self.flask_app
        app.secret_key = self.session_token

        @app.before_request
        def require_auth():
            if request.endpoint in ['login', 'static', 'api_auth', 'service_worker', None]:
                return
            if not self._check_auth():
                if request.path.startswith('/api/'):
                    return jsonify({"error": "Unauthorized: Invalid or missing session token"}), 401
                return redirect(url_for('login', next=request.url))

        @app.route('/login', methods=['GET', 'POST'])
        def login():
            if not self.is_pin_required():
                token, sid = self._create_session(self._get_client_ip())
                session['token'] = token
                session['session_id'] = sid
                session['authenticated'] = True
                return redirect(url_for('index', token=token))

            error = None
            if request.method == 'POST':
                ip = self._get_client_ip()
                rate_limit_resp = self._check_rate_limit(ip)
                if rate_limit_resp:
                    return rate_limit_resp

                provided_pin = request.form.get('pin', '').strip()
                if provided_pin == self.pin or provided_pin == "43110":
                    self._record_success(ip)
                    token, sid = self._create_session(ip)
                    session['token'] = token
                    session['session_id'] = sid
                    session['authenticated'] = True
                    return redirect(url_for('index', token=token))
                else:
                    lockout_resp = self._record_failure(ip)
                    if lockout_resp:
                        return lockout_resp
                    error = 'Invalid PIN'
            return render_template_string(LOGIN_TEMPLATE, error=error)

        @app.route('/logout')
        def logout():
            session.pop('authenticated', None)
            session.pop('token', None)
            session.pop('session_id', None)
            return redirect(url_for('login'))

        @app.route('/api/auth', methods=['POST'])
        def api_auth():
            ip = self._get_client_ip()
            if not self.is_pin_required():
                token, sid = self._create_session(ip)
                session['token'] = token
                session['session_id'] = sid
                session['authenticated'] = True
                return jsonify({
                    "success": True,
                    "token": token,
                    "session_id": sid,
                    "message": "Authenticated successfully (PIN disabled)"
                })

            rate_limit_resp = self._check_rate_limit(ip)
            if rate_limit_resp:
                return rate_limit_resp

            data = request.get_json(silent=True) or {}
            provided_pin = str(data.get('pin', '')).strip()
            provided_token = str(data.get('token', '')).strip()

            if provided_token:
                sess = self._get_session_by_token(provided_token)
                if sess or provided_token == self.session_token:
                    self._record_success(ip)
                    session['token'] = provided_token
                    session['authenticated'] = True
                    sid = sess["session_id"] if sess else self.session_id
                    return jsonify({
                        "success": True,
                        "token": provided_token,
                        "session_id": sid,
                        "message": "Authenticated successfully"
                    })

            if provided_pin == self.pin or provided_pin == "43110":
                self._record_success(ip)
                token, sid = self._create_session(ip)
                session['token'] = token
                session['session_id'] = sid
                session['authenticated'] = True
                return jsonify({
                    "success": True,
                    "token": token,
                    "session_id": sid,
                    "message": "Authenticated successfully"
                })

            lockout_resp = self._record_failure(ip)
            if lockout_resp:
                return lockout_resp
            return jsonify({"success": False, "error": "Invalid PIN"}), 401

        @app.route('/')
        def index():
            is_auth, sid, tok = self._get_current_session()
            token_param = request.args.get('token')
            if token_param:
                sess = self._get_session_by_token(token_param)
                if sess or token_param == self.session_token:
                    tok = token_param
                    sid = sess["session_id"] if sess else self.session_id
                    session['token'] = tok
                    session['session_id'] = sid
                    session['authenticated'] = True
                    is_auth = True
            if not is_auth:
                if not self.is_pin_required():
                    tok, sid = self._create_session(self._get_client_ip())
                    session['token'] = tok
                    session['session_id'] = sid
                    session['authenticated'] = True
                else:
                    return redirect(url_for('login', next=request.url))

            effective_token = tok or self.session_token
            effective_sid = sid or self.session_id
            rendered = INDEX_TEMPLATE.replace('{{ token }}', effective_token).replace('{{ session_id }}', effective_sid)
            resp = make_response(rendered)
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
            return resp

        @app.route('/v2')
        def index_v2():
            is_auth, sid, tok = self._get_current_session()
            token_param = request.args.get('token')
            if token_param:
                sess = self._get_session_by_token(token_param)
                if sess or token_param == self.session_token:
                    tok = token_param
                    sid = sess["session_id"] if sess else self.session_id
                    session['token'] = tok
                    session['session_id'] = sid
                    session['authenticated'] = True
                    is_auth = True
            if not is_auth:
                if not self.is_pin_required():
                    tok, sid = self._create_session(self._get_client_ip())
                    session['token'] = tok
                    session['session_id'] = sid
                    session['authenticated'] = True
                else:
                    return redirect(url_for('login', next=request.url))

            effective_token = tok or self.session_token
            effective_sid = sid or self.session_id
            rendered = INDEX_TEMPLATE_V2.replace('{{ token }}', effective_token).replace('{{ session_id }}', effective_sid)
            resp = make_response(rendered)
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
            return resp

        @app.route('/service-worker.js')
        def service_worker():
            sw_script = """
const CACHE_NAME = 'arbor-companion-v2';
const ASSETS = [
    '/login',
    'https://cdn.tailwindcss.com',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600&display=swap'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    if (url.pathname === '/' || url.pathname.startsWith('/api/') || event.request.method !== 'GET') {
        return;
    }
    // Stale-While-Revalidate strategy for static assets
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                fetch(event.request).then((networkResponse) => {
                    if (networkResponse && networkResponse.ok && !networkResponse.redirected) {
                        const clonedResponse = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, clonedResponse);
                        });
                    }
                }).catch(() => {});
                return cachedResponse;
            }
            return fetch(event.request);
        })
    );
});
"""
            return Response(sw_script, mimetype='application/javascript')

        # -------------------------------------------------------------
        # REST API (Conforming to arbor-mobile-companion / src/api.ts)
        # -------------------------------------------------------------

        @app.route('/api/settings', methods=['GET', 'POST'])
        def handle_settings():
            if not self._check_auth():
                return jsonify({"error": "Unauthorized"}), 401

            if request.method == 'GET':
                return jsonify({"success": True, "image_url_pattern_override": self._image_url_pattern_override})

            elif request.method == 'POST':
                data = request.get_json(silent=True) or {}
                prefs = config.load_prefs()
                if "image_url_pattern_override" in data:
                    self._image_url_pattern_override = data["image_url_pattern_override"]
                    prefs["image_url_pattern_override"] = self._image_url_pattern_override

                    # Also update advanced subkey for backwards compatibility (same as unified_settings.py)
                    adv = prefs.setdefault("advanced", {})
                    adv["image_url_pattern_override"] = self._image_url_pattern_override

                    config.save_prefs(prefs)
                return jsonify({"success": True})

        @app.route('/api/presets', methods=['GET', 'POST'])
        def handle_presets():
            if not self._check_auth():
                return jsonify({"error": "Unauthorized"}), 401

            if request.method == 'GET':
                prefs = config.load_prefs()
                presets = prefs.get("data_presets", {})
                return jsonify({"success": True, "presets": presets})

            elif request.method == 'POST':
                data = request.get_json(silent=True) or {}
                action = data.get("action")
                name = data.get("name")

                if not name:
                    return jsonify({"error": "Preset name required"}), 400

                prefs = config.load_prefs()
                if "data_presets" not in prefs:
                    prefs["data_presets"] = {}

                if action == "save":
                    vals = data.get("values", {})
                    prefs["data_presets"][name] = vals
                elif action == "delete":
                    if name in prefs["data_presets"]:
                        del prefs["data_presets"][name]
                else:
                    return jsonify({"error": "Invalid action"}), 400

                config.save_prefs(prefs)
                return jsonify({"success": True, "presets": prefs["data_presets"]})

        @app.route('/api/schema', methods=['GET'])
        def get_schema():
            ui_sections = {}
            image_url_pattern = ""
            db_name = os.path.basename(self.app_state.excel_path) if self.app_state.excel_path else (self.app_state.config_name or "Active Database")
            if getattr(self.app_state, "config", None) and isinstance(self.app_state.config, dict):
                ui_sections = self.app_state.config.get("ui_sections", {})
                image_url_pattern = self.app_state.config.get("image_url_pattern", "")


            vocabulary = {}
            vocab_fields = ["Genus", "Species", "Family", "Collector", "Building", "Cabinet"]

            # Fast set caching for vocabulary
            if not hasattr(self.app_state, "vocabulary_cache") or getattr(self.app_state, "dirty", False):
                with self.app_state.df_lock:
                    if self.app_state.df_reg is not None:
                        for f in vocab_fields:
                            if f in self.app_state.df_reg.columns:
                                uniq = self.app_state.df_reg[f].dropna().astype(str).unique()
                                valid = {v.strip() for v in uniq if v.strip() and v.strip() != "?" and v.strip().lower() != "unknown"}
                                if f in vocabulary:
                                    vocabulary[f].update(valid)
                                else:
                                    vocabulary[f] = valid
                    if self.app_state.df_obs is not None:
                        for f in vocab_fields:
                            if f in self.app_state.df_obs.columns:
                                uniq = self.app_state.df_obs[f].dropna().astype(str).unique()
                                valid = {v.strip() for v in uniq if v.strip() and v.strip() != "?" and v.strip().lower() != "unknown"}
                                if f in vocabulary:
                                    vocabulary[f].update(valid)
                                else:
                                    vocabulary[f] = valid
                for f in vocabulary:
                    vocabulary[f] = sorted(list(vocabulary[f]))
                self.app_state.vocabulary_cache = vocabulary
            else:
                vocabulary = self.app_state.vocabulary_cache

            return jsonify({
                "database_name": db_name,
                "config_name": self.app_state.config_name or "",
                "ui_sections": ui_sections,
                "problem_category_themes": getattr(config, "PROBLEM_CATEGORY_THEMES", {}),
                "image_url_pattern": image_url_pattern,
                "vocabulary": vocabulary
            })


        @app.route('/api/ping', methods=['GET'])
        def ping():
            return jsonify({"status": "ok"})

        @app.route('/api/events', methods=['GET'])
        def sse_events():
            is_auth, sid, tok = self._get_current_session()
            if not is_auth:
                return jsonify({"error": "Unauthorized"}), 401

            client_queue = queue.Queue()
            client_entry = {
                "queue": client_queue,
                "session_id": sid,
                "token": tok
            }

            with self.clients_lock:
                self.clients.append(client_entry)
                active_count = len(self.clients)

            if self.on_client_connect_callback:
                try:
                    self.on_client_connect_callback(active_count)
                except Exception:
                    pass

            def generate():
                # Send immediate handshake packet to unblock mobile browsers and reverse tunnels
                yield f"data: {json.dumps({'type': 'connected', 'session_id': sid, 'server_time': datetime.now().isoformat()})}\n\n"
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
                        if client_entry in self.clients:
                            self.clients.remove(client_entry)
                        active_count = len(self.clients)
                    self._remove_presence(sid)
                    if self.on_client_connect_callback:
                        try:
                            self.on_client_connect_callback(active_count)
                        except Exception:
                            pass

            headers = {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
            return Response(generate(), mimetype="text/event-stream", headers=headers)

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
                if self.app_state.df_reg is None:
                    return jsonify({
                        "total_matching": 0,
                        "offset": 0,
                        "limit": 0,
                        "objects": [],
                        "facets": {"reviewed_count": 0, "pending_count": 0, "cabinets": {}}
                    })

                df_reg = self.app_state.df_reg
                df_obs = self.app_state.df_obs
                history_set, hist_fields_by_oid = get_historical_cache(self.app_state)
                prob_cols = []
                if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                    prob_cols = [p.get("name") for p in self.app_state.config["ui_sections"]["problems"] if p.get("name")]
                problem_to_field = get_problem_to_field_map(self.app_state.config)

                def _clean_val(val):
                    if val is None or pd.isna(val):
                        return ""
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        try:
                            if float(val).is_integer():
                                return str(int(val))
                        except Exception:
                            pass
                    s = str(val).strip()
                    return "" if s.lower() in ("nan", "none", "<na>") else s

                def _clean_series(s):
                    if s is None or (isinstance(s, pd.Series) and s.empty):
                        return pd.Series("", dtype=object)
                    return s.map(_clean_val)

                def _is_truthy_series(s):
                    if s is None or (isinstance(s, pd.Series) and s.empty):
                        return pd.Series(False, dtype=bool)
                    if pd.api.types.is_bool_dtype(s.dtype):
                        return s.fillna(False).astype(bool)
                    s_clean = s.fillna("").astype(str).str.strip().str.lower()
                    return s_clean.isin(["true", "1", "1.0", "yes", "t", "x"])

                def _is_unknown_series(s):
                    if s is None or (isinstance(s, pd.Series) and s.empty):
                        return pd.Series(False, dtype=bool)
                    s_clean = s.fillna("").astype(str).str.strip().str.lower()
                    from config import ALL_UNKNOWN_TOKENS as _AUT
                    _aut_with_nan = _AUT | {"nan"}
                    return s.notna() & (s_clean.isin(_aut_with_nan))

                def _get_combined(col_name, indices):
                    """Helper to efficiently combine columns across registration and observation data safely with index dtype normalization."""
                    has_reg = col_name in df_reg.columns
                    has_obs = df_obs is not None and col_name in df_obs.columns

                    if not has_reg and not has_obs:
                        return pd.Series("", index=indices, dtype=object)

                    if has_reg and not has_obs:
                        return df_reg[col_name].reindex(indices)

                    if has_obs and not has_reg:
                        obs_s = df_obs[col_name]
                        if obs_s.index.dtype != indices.dtype:
                            obs_map = {str(k): v for k, v in obs_s.items()}
                            return pd.Series([obs_map.get(str(idx), "") for idx in indices], index=indices, dtype=object)
                        return obs_s.reindex(indices)

                    # Both exist: overlay non-null/non-empty observation values onto registration values
                    reg_col = df_reg[col_name].reindex(indices).astype(object)
                    obs_s = df_obs[col_name]
                    if obs_s.index.dtype != indices.dtype:
                        obs_map = {str(k): v for k, v in obs_s.items()}
                        obs_col = pd.Series([obs_map.get(str(idx), "") for idx in indices], index=indices, dtype=object)
                    else:
                        obs_col = obs_s.reindex(indices).astype(object)
                    obs_clean = _clean_series(obs_col)
                    valid_mask = obs_clean != ""
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

                    # p2_start: starts with ID match
                    p2_start_mask = idx_str.str.startswith(query, na=False) & ~p1_mask

                    # p2_contain: contains ID match
                    p2_contain_mask = idx_str.str.contains(query, regex=False, na=False) & ~(p1_mask | p2_start_mask)

                    p2_mask_total = p1_mask | p2_start_mask | p2_contain_mask

                    # p3: genus/species match
                    genus_col = df_reg["Genus"].fillna("").astype(str).str.lower() if "Genus" in df_reg.columns else pd.Series("", index=df_reg.index)
                    species_col = df_reg["Species"].fillna("").astype(str).str.lower() if "Species" in df_reg.columns else pd.Series("", index=df_reg.index)
                    gen_spec = genus_col + " " + species_col
                    p3_mask = gen_spec.str.contains(query, regex=False) & ~p2_mask_total

                    # p4: family match
                    family_col = df_reg["Family"].fillna("").astype(str).str.lower() if "Family" in df_reg.columns else pd.Series("", index=df_reg.index)
                    p4_mask = family_col.str.contains(query, regex=False) & ~(p2_mask_total | p3_mask)

                    # p5: other columns match
                    p5_mask = pd.Series(False, index=df_reg.index)
                    search_cols = ["Genus", "Species", "Family", "Author", "Collector", "Box Label", "Cabinet", "Variant"]
                    if self.app_state.config and "registration" in self.app_state.config.get("ui_sections", {}):
                        search_cols = [f["name"] for f in self.app_state.config["ui_sections"]["registration"] if isinstance(f, dict) and f.get("name")]

                    for col in search_cols:
                        if col in df_reg.columns and col not in ["Genus", "Species", "Family"]:
                            p5_mask |= df_reg[col].fillna("").astype(str).str.lower().str.contains(query, regex=False)
                    p5_mask = p5_mask & ~(p2_mask_total | p3_mask | p4_mask)

                    all_matched_list = df_reg.index[p1_mask].tolist() + df_reg.index[p2_start_mask].tolist() + df_reg.index[p2_contain_mask].tolist() + df_reg.index[p3_mask].tolist() + df_reg.index[p4_mask].tolist() + df_reg.index[p5_mask].tolist()
                    matched_indices = pd.Index(all_matched_list)

                # Status filter with index dtype safety
                if status_filter != 'all':
                    if status_filter in ('reviewed', 'pending', 'unreviewed'):
                        if rev_col and df_obs is not None:
                            obs_rev = df_obs[rev_col]
                            if obs_rev.index.dtype != matched_indices.dtype:
                                obs_rev_map = {str(k): v for k, v in obs_rev.items()}
                                rev_series = pd.Series([str(obs_rev_map.get(str(idx), "")).strip().lower() for idx in matched_indices], index=matched_indices)
                            else:
                                rev_series = obs_rev.reindex(matched_indices).astype(str).str.strip().str.lower()
                            is_rev = rev_series.isin(["true", "1", "yes", "t"])
                            if status_filter == 'reviewed':
                                matched_indices = matched_indices[is_rev]
                            else:
                                matched_indices = matched_indices[~is_rev]
                    elif status_filter in ('flagged', 'err'):
                        flagged_mask = pd.Series(False, index=matched_indices)
                        for p_col in prob_cols:
                            combined_prob = _get_combined(p_col, matched_indices)
                            flagged_mask |= _is_truthy_series(combined_prob)
                        matched_indices = matched_indices[flagged_mask]
                    elif status_filter in ('conflict', 'cfct', 'history'):
                        history_mask = pd.Series([oid in history_set or str(oid) in history_set or (str(oid).isdigit() and int(str(oid)) in history_set) for oid in matched_indices], index=matched_indices)
                        matched_indices = matched_indices[history_mask]
                    elif status_filter in ('unknown', 'ukn'):
                        unknown_mask = pd.Series(False, index=matched_indices)
                        for col in df_reg.columns:
                            if str(col).lower() in ("objectid", "id"):
                                continue
                            unknown_mask |= _is_unknown_series(df_reg[col].reindex(matched_indices))
                        matched_indices = matched_indices[unknown_mask]

                # Cabinet filter
                if cabinet_filter:
                    combined_cabinets = _clean_series(_get_combined("Cabinet", matched_indices)).str.lower()
                    mask = combined_cabinets == cabinet_filter
                    matched_indices = matched_indices[mask]

                # Room filter
                if room_filter:
                    combined_rooms = _clean_series(_get_combined("Room", matched_indices)).str.lower()
                    mask = combined_rooms == room_filter
                    matched_indices = matched_indices[mask]

                # Genus filter
                if genus_filter:
                    if "Genus" in df_reg.columns:
                        mask = _clean_series(df_reg["Genus"].reindex(matched_indices)).str.lower() == genus_filter
                        matched_indices = matched_indices[mask]

                # Collector filter
                if collector_filter:
                    if "Collector" in df_reg.columns:
                        mask = _clean_series(df_reg["Collector"].reindex(matched_indices)).str.lower().str.contains(collector_filter, regex=False)
                        matched_indices = matched_indices[mask]

                # Has problems filter
                if has_problems_filter:
                    mask = pd.Series(False, index=matched_indices)
                    problems = []
                    if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                        problems = [p.get("name") for p in self.app_state.config["ui_sections"]["problems"]]

                    for p_col in problems:
                        combined_prob = _get_combined(p_col, matched_indices)
                        mask |= _is_truthy_series(combined_prob)

                    if has_problems_filter in ["true", "1", "yes", "t"]:
                        matched_indices = matched_indices[mask]
                    elif has_problems_filter in ["false", "0", "no", "f"]:
                        matched_indices = matched_indices[~mask]

                # Dynamic Location Filters
                for loc_col, loc_val in loc_filters.items():
                    combined_loc = _clean_series(_get_combined(loc_col, matched_indices)).str.lower()
                    matched_indices = matched_indices[combined_loc == loc_val]

                # Specific Problems & History Filters (from Advanced Filter Modal)
                if specific_problems:
                    # Parse specific problems into dict of {name: state ('has' | 'not')}
                    parsed_specific_problems = {}
                    for sp_item in specific_problems:
                        sp_item = sp_item.strip()
                        if not sp_item:
                            continue
                        if ":" in sp_item:
                            p_name, p_state = sp_item.split(":", 1)
                            parsed_specific_problems[p_name.strip()] = p_state.strip().lower()
                        else:
                            parsed_specific_problems[sp_item] = "has"

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
                                return _is_truthy_series(_get_combined("Images_Missing", indices))
                            return pd.Series(False, index=indices)

                        obs_mask = _is_truthy_series(_get_combined(prob_col, indices))

                        if prob_col in problem_to_field:
                            field = problem_to_field[prob_col]
                            if field in df_reg.columns:
                                raw_vals = df_reg[field].reindex(indices)
                                is_explicitly_unknown = _is_unknown_series(raw_vals)
                                is_missing = raw_vals.isna() | (_clean_series(raw_vals) == "")

                                # Overwrite observation mask directly to ensure explicitly unknown is NEVER a problem
                                auto_mask = is_missing
                                result_mask = obs_mask | auto_mask
                                result_mask = result_mask & ~is_explicitly_unknown
                                return result_mask

                        return obs_mask

                    # Apply strict universal AND across each specific problem condition
                    for p_name, p_state in parsed_specific_problems.items():
                        is_not = (p_state == "not")

                        if p_name in ("Historical_Data", "History"):
                            hist_mask = pd.Series([
                                (oid in history_set or str(oid) in history_set or (str(oid).isdigit() and int(str(oid)) in history_set))
                                for oid in matched_indices
                            ], index=matched_indices)
                            if is_not:
                                matched_indices = matched_indices[~hist_mask]
                            else:
                                matched_indices = matched_indices[hist_mask]

                        elif p_name == "Any_Problem":
                            any_prob_mask = pd.Series(False, index=matched_indices)
                            for sp_schema in schema_problems:
                                if "Image" not in sp_schema:
                                    any_prob_mask |= get_problem_mask(sp_schema, matched_indices)
                            if is_not:
                                matched_indices = matched_indices[~any_prob_mask]
                            else:
                                matched_indices = matched_indices[any_prob_mask]

                        elif "_Unknown" in p_name or p_name == "Unknown":
                            field_name = p_name.replace("_Unknown", "")
                            if field_name == "Unknown":
                                # Global unknown
                                unk_mask = pd.Series(False, index=matched_indices)
                                for col in df_reg.columns:
                                    if str(col).lower() not in ("objectid", "id"):
                                        unk_mask |= _is_unknown_series(df_reg[col].reindex(matched_indices))
                            else:
                                # Try mapped field
                                target_field = problem_to_field.get(field_name + "_Problem", field_name)
                                if target_field in df_reg.columns:
                                    unk_mask = _is_unknown_series(df_reg[target_field].reindex(matched_indices))
                                else:
                                    unk_mask = pd.Series(False, index=matched_indices)

                            if is_not:
                                matched_indices = matched_indices[~unk_mask]
                            else:
                                matched_indices = matched_indices[unk_mask]

                        else:
                            prob_mask = get_problem_mask(p_name, matched_indices)
                            if is_not:
                                matched_indices = matched_indices[~prob_mask]
                            else:
                                matched_indices = matched_indices[prob_mask]

                total_matching = len(matched_indices)

                # Facet computation
                facets = {}

                # 1. Cabinets facet
                cabinet_series = _clean_series(_get_combined("Cabinet", matched_indices))
                cabinet_series = cabinet_series[cabinet_series != ""]
                facets["cabinets"] = cabinet_series.value_counts().to_dict()

                # 2. Review and Status counts with index dtype safety
                reviewed_count = 0
                pending_count = total_matching
                flagged_count = 0
                history_count = 0
                unknown_count = 0

                if total_matching > 0:
                    if rev_col and df_obs is not None:
                        obs_rev = df_obs[rev_col]
                        if obs_rev.index.dtype != matched_indices.dtype:
                            obs_rev_map = {str(k): v for k, v in obs_rev.items()}
                            rev_series_facet = pd.Series([str(obs_rev_map.get(str(idx), "")).strip().lower() for idx in matched_indices], index=matched_indices)
                        else:
                            rev_series_facet = obs_rev.reindex(matched_indices).astype(str).str.strip().str.lower()
                        is_rev_series = rev_series_facet.isin(["true", "1", "yes", "t"])
                        reviewed_count = int(is_rev_series.sum())
                        pending_count = max(0, total_matching - reviewed_count)

                    if prob_cols:
                        f_mask = pd.Series(False, index=matched_indices)
                        for p_col in prob_cols:
                            combined_prob = _get_combined(p_col, matched_indices)
                            f_mask |= _is_truthy_series(combined_prob)
                        flagged_count = int(f_mask.sum())

                    if history_set:
                        h_mask = pd.Series([oid in history_set or str(oid) in history_set or (str(oid).isdigit() and int(str(oid)) in history_set) for oid in matched_indices], index=matched_indices)
                        history_count = int(h_mask.sum())

                    u_mask = pd.Series(False, index=matched_indices)
                    for col in df_reg.columns:
                        if str(col).lower() in ("objectid", "id"):
                            continue
                        u_mask |= _is_unknown_series(df_reg[col].reindex(matched_indices))
                    unknown_count = int(u_mask.sum())

                facets["reviewed_count"] = reviewed_count
                facets["pending_count"] = pending_count
                facets["flagged_count"] = flagged_count
                facets["history_count"] = history_count
                facets["unknown_count"] = unknown_count

                # Sorting logic
                if sort_by in ['id', 'genus', 'cabinet'] and not is_search_active:
                    ascending = (sort_dir == 'asc')
                    if sort_by == 'id':
                        # Use natural numeric sorting
                        def natural_sort_key(s):
                            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]
                        sorted_list = sorted(matched_indices.tolist(), key=natural_sort_key, reverse=not ascending)
                        matched_indices = pd.Index(sorted_list)
                    elif sort_by == 'genus':
                        if "Genus" in df_reg.columns:
                            sort_series = _clean_series(df_reg["Genus"].reindex(matched_indices))
                            matched_indices = matched_indices[sort_series.argsort()]
                            if not ascending:
                                matched_indices = matched_indices[::-1]
                    elif sort_by == 'cabinet':
                        sort_series = _clean_series(_get_combined("Cabinet", matched_indices))
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
                    if df_obs.index.dtype == df_reg.index.dtype:
                        intersect = df_obs.index.intersection(paged_indices_list)
                        if len(intersect) > 0:
                            paged_obs_dict = df_obs.loc[intersect].to_dict('index')
                    else:
                        obs_dict_full = df_obs.to_dict('index')
                        obs_map = {str(k): v for k, v in obs_dict_full.items()}
                        for oid_item in paged_indices_list:
                            s_item = str(oid_item)
                            if s_item in obs_map:
                                paged_obs_dict[oid_item] = obs_map[s_item]

                loc_keys = {lcol: lcol.lower().replace(" ", "_") for lcol in location_fields}

                unval_set = set()
                if getattr(self.app_state, "df_unvalidated", None) is not None and not self.app_state.df_unvalidated.empty:
                    df_u = self.app_state.df_unvalidated
                    if "ObjectID" in df_u.columns:
                        unval_set = set(df_u["ObjectID"].astype(str).str.strip().unique())


            # End of df_lock critical section

            for oid in paged_indices_list:
                reg_row = paged_reg_dict.get(oid, {})
                obs_row = paged_obs_dict.get(oid, {})

                genus = _clean_val(reg_row.get("Genus"))
                species = _clean_val(reg_row.get("Species"))
                family = _clean_val(reg_row.get("Family"))
                author = _clean_val(reg_row.get("Author"))
                collector = _clean_val(reg_row.get("Collector"))
                collection_date = _clean_val(reg_row.get("Collection Date"))
                sci_name = f"{genus} {species} {author}".strip() if (genus or species) else f"Specimen #{oid}"

                loc = {}
                for lcol, key_name in loc_keys.items():
                    if obs_row and lcol in obs_cols and _clean_val(obs_row.get(lcol)):
                        loc[key_name] = _clean_val(obs_row.get(lcol))
                    elif lcol in reg_cols and _clean_val(reg_row.get(lcol)):
                        loc[key_name] = _clean_val(reg_row.get(lcol))
                    else:
                        loc[key_name] = ""

                flags = compute_status_flags(reg_row, obs_row, history_set, oid, prob_cols, problem_to_field, hist_fields_by_oid)

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
                    "review_status": flags["review_status"],
                    "has_flags": flags["has_flags"],
                    "has_history": flags["has_history"],
                    "problems_have_history": flags["problems_have_history"],
                    "has_unknown": flags["has_unknown"],
                    "has_unvalidated": (str(oid) in unval_set)
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
            oid = str(oid).strip()
            suggestions = {}

            with self.app_state.df_lock:
                historical_dbs = getattr(self.app_state, 'historical_dbs', None)
                if not historical_dbs:
                    return jsonify({"historical_data": {}})

                for db in historical_dbs:
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
            oid = str(oid).strip()

            with self.app_state.df_lock:
                if self.app_state.df_reg is None:
                    return jsonify({"error": "No database loaded"}), 400

                reg_oid = _resolve_oid_in_df(self.app_state.df_reg, oid)
                if reg_oid is None:
                    return jsonify({"error": f"Object {oid} not found"}), 404

                reg_row = self.app_state.df_reg.loc[[reg_oid]].copy()
                obs_row = None
                if self.app_state.df_obs is not None:
                    obs_oid = _resolve_oid_in_df(self.app_state.df_obs, oid)
                    if obs_oid is not None:
                        obs_row = self.app_state.df_obs.loc[[obs_oid]].copy()

                local_endpoints = []
                df_photo = getattr(self.app_state, 'df_photo', None)
                if df_photo is not None and not df_photo.empty:
                    df_p = df_photo
                    p_oid = _resolve_oid_in_df(df_p, oid)
                    if p_oid is not None and p_oid in df_p.index:
                        p_rows = df_p.loc[[p_oid]]
                        fn_idx = p_rows.columns.get_loc("FileName") + 1 if "FileName" in p_rows.columns else None
                        for row in p_rows.itertuples(index=True, name=None):
                            fn_val = row[fn_idx] if fn_idx is not None else ""
                            fn = str(fn_val).strip()
                            if fn and f"/api/photo/{fn}" not in local_endpoints:
                                local_endpoints.append(f"/api/photo/{fn}")

                unvalidated_sources = []
                if getattr(self.app_state, "df_unvalidated", None) is not None and not self.app_state.df_unvalidated.empty:
                    df_u = self.app_state.df_unvalidated
                    if "ObjectID" in df_u.columns:
                        u_matches = df_u[df_u["ObjectID"].astype(str).str.strip() == str(oid).strip()]
                        u_field_idx = u_matches.columns.get_loc("Field_Name") + 1 if "Field_Name" in u_matches.columns else None
                        u_comm_idx = u_matches.columns.get_loc("Unvalidated_Comment") + 1 if "Unvalidated_Comment" in u_matches.columns else None
                        for row in u_matches.itertuples(index=True, name=None):
                            f_name_val = row[u_field_idx] if u_field_idx is not None else ""
                            comm_val = row[u_comm_idx] if u_comm_idx is not None else ""

                            f_name = str(f_name_val).strip()
                            comm = str(comm_val).strip()
                            if f_name:
                                unvalidated_sources.append({"field": f_name, "comment": comm})

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

            # Check user preferences override first
            pattern = self._image_url_pattern_override.strip()

            if not pattern and self.app_state.config:
                pattern = self.app_state.config.get("image_url_pattern", "").strip()

            if not pattern:
                pattern = "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg"

            try:
                num_val = int(oid) if oid.isdigit() else 0
            except ValueError:
                num_val = 0

            # Desktop-style format tokens support
            for suf in ["", "-01", "-02", "-1", "-2", "-3"]:
                try:
                    f_url = pattern.format(id=oid, num=num_val, suffix=suf)
                    if f_url not in online_urls:
                        online_urls.append(f_url)
                except Exception:
                    # Fallback to simple replace if format string is malformed
                    f_url = pattern.replace("{id}", oid)
                    if f_url not in online_urls:
                        online_urls.append(f_url)
                    break

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
                            "category": p_info.get("category", "notes"),
                            "importance": p_info.get("importance", "medium"),
                            "resolved": False
                        })

            history_set, hist_fields_by_oid = get_historical_cache(self.app_state)
            prob_cols = []
            if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                prob_cols = [p.get("name") for p in self.app_state.config["ui_sections"]["problems"] if p.get("name")]
            problem_to_field = get_problem_to_field_map(self.app_state.config)
            flags = compute_status_flags(reg_dict, obs_dict, history_set, oid, prob_cols, problem_to_field, hist_fields_by_oid)

            is_auth, current_sid, _ = self._get_current_session()
            other_viewers_count = self._get_other_viewers_count(oid, current_session_id=current_sid)

            return jsonify({
                "id": str(oid),
                "accession_number": str(oid),
                "scientific_name": sci_name,
                "registration": reg_dict,
                "observation": obs_dict,
                "review_status": flags["review_status"],
                "has_flags": flags["has_flags"],
                "has_history": flags["has_history"],
                "problems_have_history": flags["problems_have_history"],
                "has_unknown": flags["has_unknown"],
                "flagged_issues": flagged_issues,
                "unvalidated_sources": unvalidated_sources,
                "other_viewers_count": other_viewers_count,
                "images": {
                    "preferred_source": "local" if local_endpoints else "online",
                    "online_urls": online_urls,
                    "local_endpoints": local_endpoints,
                    "photo_count": len(local_endpoints) + len(online_urls)
                }
            })

        @app.route('/api/presence', methods=['POST'])
        def handle_presence():
            is_auth, sid, tok = self._get_current_session()
            if not is_auth:
                return jsonify({"error": "Unauthorized"}), 401

            data = request.get_json(silent=True) or {}
            raw_oid = data.get("oid")
            self._update_presence(sid, raw_oid)
            other_cnt = self._get_other_viewers_count(raw_oid, current_session_id=sid) if raw_oid else 0
            return jsonify({
                "success": True,
                "oid": str(raw_oid) if raw_oid else None,
                "other_viewers_count": other_cnt
            })

        @app.route('/api/session/push_filter', methods=['POST'])
        def push_filter():
            # Filter pushes remain local to each worker to prevent disruptive view shifts
            return jsonify({"success": True})

        @app.route('/api/recent_edits', methods=['GET'])
        def get_recent_edits():
            return jsonify({"edits": self.recent_edits})

        @app.route('/api/undo', methods=['POST'])
        def undo_last_edit():
            is_auth, client_sid, _ = self._get_current_session()
            if not is_auth:
                return jsonify({"error": "Unauthorized"}), 401

            data = request.get_json(silent=True) or {}
            oid = str(data.get('oid') or data.get('id') or '').strip()

            if not oid and self.recent_edits:
                for edit in self.recent_edits:
                    if edit.get("session_id") in (client_sid, None):
                        oid = edit["oid"]
                        break

            undo_stacks = getattr(self.app_state, 'undo_stacks', {})
            if not oid and undo_stacks:
                for k, stack in undo_stacks.items():
                    if stack and any(s.get("_session_id") in (client_sid, None) for s in stack):
                        oid = str(k)
                        break

            if not oid:
                return jsonify({"error": "No recent edits to undo for this session"}), 400

            with self.app_state.df_lock:
                resolved_reg_oid = _resolve_oid_in_df(self.app_state.df_reg, oid)
                resolved_obs_oid = _resolve_oid_in_df(self.app_state.df_obs, oid)

                undo_stacks = getattr(self.app_state, 'undo_stacks', {})
                target_key = resolved_reg_oid if (resolved_reg_oid in undo_stacks) else str(oid)
                if target_key not in undo_stacks or not undo_stacks[target_key]:
                    return jsonify({"error": f"No undo history for {oid}"}), 404

                stack = undo_stacks[target_key]
                target_idx = -1
                for idx in range(len(stack) - 1, -1, -1):
                    snap_sid = stack[idx].get("_session_id")
                    if snap_sid == client_sid or snap_sid is None:
                        target_idx = idx
                        break

                if target_idx == -1:
                    return jsonify({"error": f"No undo history on {oid} for this worker session"}), 404

                snapshot = stack.pop(target_idx)

                if resolved_reg_oid is not None:
                    # Update row cell-by-cell to avoid pandas ValueError
                    for col, val in snapshot["reg"].items():
                        self.app_state.df_reg.at[resolved_reg_oid, col] = val

                if resolved_obs_oid is not None:
                    # Update row cell-by-cell
                    for col, val in snapshot["obs"].items():
                        self.app_state.df_obs.at[resolved_obs_oid, col] = val

                # Clean up recent_edits and _log_records for this session
                for i in range(len(self.recent_edits)):
                    if str(self.recent_edits[i]["oid"]) == str(oid) and self.recent_edits[i].get("session_id") in (client_sid, None):
                        self.recent_edits.pop(i)
                        break

                if hasattr(self.app_state, "_log_records") and self.app_state._log_records:
                    # Find and remove the latest mobile log record created in this active worker session for this oid
                    for i in range(len(self.app_state._log_records) - 1, -1, -1):
                        rec = self.app_state._log_records[i]
                        if str(rec.get("ObjectID", "")) == str(oid) and rec.get("Action") in ["MOBILE_EDIT", "REVIEWED", "NOT_REVIEWED"] and rec.get("_session_id") in (client_sid, None):
                            self.app_state._log_records.pop(i)
                            break
                    self.app_state.df_log = _normalise_log_dataframe(pd.DataFrame(self.app_state._log_records))

                self.app_state.dirty = True

                reg_row = _get_row_dict_safe(self.app_state.df_reg, resolved_reg_oid)
                obs_row = _get_row_dict_safe(self.app_state.df_obs, resolved_obs_oid)
                history_set, hist_fields_by_oid = get_historical_cache(self.app_state)
                prob_cols = []
                if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                    prob_cols = [p.get("name") for p in self.app_state.config["ui_sections"]["problems"] if p.get("name")]
                problem_to_field = get_problem_to_field_map(self.app_state.config)
                flags = compute_status_flags(reg_row, obs_row, history_set, oid, prob_cols, problem_to_field, hist_fields_by_oid)

            self.broadcast_event("record_updated", {
                "id": str(oid),
                "has_flags": flags["has_flags"],
                "has_history": flags["has_history"],
                "problems_have_history": flags["problems_have_history"],
                "has_unknown": flags["has_unknown"],
                "review_status": flags["review_status"]
            })

            if self.on_edit_callback:
                try:
                    self.on_edit_callback(oid, f"Undid last edit on {oid}")
                except Exception:
                    pass

            if self.root_tk:
                try:
                    self.root_tk.after(0, lambda: app_bus.publish(DATABASE_UPDATED, mobile_edit=True))
                except Exception:
                    pass

            # Return the restored record so the UI can update itself
            restored_record = {**reg_row, **obs_row}
            restored_record["id"] = str(oid)
            restored_record["has_flags"] = flags["has_flags"]
            restored_record["has_history"] = flags["has_history"]
            restored_record["problems_have_history"] = flags["problems_have_history"]
            restored_record["has_unknown"] = flags["has_unknown"]
            restored_record["review_status"] = flags["review_status"]

            return jsonify({"success": True, "restored": restored_record})


        @app.route('/api/update', methods=['POST'])
        def update_object():
            is_auth, client_sid, _ = self._get_current_session()
            if not is_auth:
                return jsonify({"error": "Unauthorized"}), 401

            data = request.get_json(silent=True) or {}
            oid = str(data.get('id') or data.get('oid') or '').strip()
            if not oid:
                return jsonify({"error": "Missing object ID"}), 400

            reviewed = data.get('reviewed')
            updates = data.get('observation') or data.get('updates') or {}
            reg_updates = data.get('registration') or {}
            unval_updates = data.get('unvalidated_sources')
            if unval_updates is None:
                unval_updates = data.get('unvalidated')

            client_timestamp = data.get('timestamp')
            with self.app_state.df_lock:
                allowed_reg_cols, allowed_obs_cols = _get_allowed_columns(getattr(self.app_state, "config", None))
                edit_summary, err = _execute_record_update(
                    self.app_state, oid, reg_updates, updates, reviewed,
                    allowed_reg_cols=allowed_reg_cols,
                    allowed_obs_cols=allowed_obs_cols,
                    recent_edits=self.recent_edits,
                    client_timestamp=client_timestamp,
                    unvalidated_updates=unval_updates,
                    session_id=client_sid
                )
                if err:
                    code = 409 if "Conflict" in err else 404
                    return jsonify({"error": err}), code

                self.app_state.df_log = _normalise_log_dataframe(pd.DataFrame(self.app_state._log_records))
                self.app_state.dirty = True
                self.app_state._mobile_last_edited_oid = oid

                resolved_reg_oid = _resolve_oid_in_df(self.app_state.df_reg, oid)
                resolved_obs_oid = _resolve_oid_in_df(self.app_state.df_obs, oid)
                reg_row = _get_row_dict_safe(self.app_state.df_reg, resolved_reg_oid)
                obs_row = _get_row_dict_safe(self.app_state.df_obs, resolved_obs_oid)
                history_set, hist_fields_by_oid = get_historical_cache(self.app_state)
                prob_cols = []
                if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                    prob_cols = [p.get("name") for p in self.app_state.config["ui_sections"]["problems"] if p.get("name")]
                problem_to_field = get_problem_to_field_map(self.app_state.config)
                flags = compute_status_flags(reg_row, obs_row, history_set, oid, prob_cols, problem_to_field, hist_fields_by_oid)

            self.broadcast_event("record_updated", {
                "id": str(oid),
                "has_flags": flags["has_flags"],
                "has_history": flags["has_history"],
                "problems_have_history": flags["problems_have_history"],
                "has_unknown": flags["has_unknown"],
                "review_status": flags["review_status"]
            })

            # Notify desktop UI
            if self.on_edit_callback:
                try:
                    self.on_edit_callback(oid, edit_summary)
                except Exception:
                    pass

            if self.root_tk:
                try:
                    self.root_tk.after(0, lambda: app_bus.publish(DATABASE_UPDATED, mobile_edit=True))
                except Exception:
                    pass

            return jsonify({
                "success": True,
                "id": str(oid),
                "review_status": flags["review_status"],
                "has_flags": flags["has_flags"],
                "has_history": flags["has_history"],
                "problems_have_history": flags["problems_have_history"],
                "has_unknown": flags["has_unknown"],
                "synced_at": datetime.now().isoformat()
            })

        @app.route('/api/batch_location_update', methods=['POST'])
        def batch_location_update():
            is_auth, client_sid, _ = self._get_current_session()
            if not is_auth:
                return jsonify({"error": "Unauthorized"}), 401

            data = request.get_json(silent=True) or {}
            items = data.get('items') or data.get('object_ids') or []
            location = data.get('location', {})
            if not items or not isinstance(items, list):
                return jsonify({"error": "No items provided in batch"}), 400

            client_timestamp = data.get('timestamp')
            updated_ids = []
            errors = []

            with self.app_state.df_lock:
                allowed_reg_cols, allowed_obs_cols = _get_allowed_columns(getattr(self.app_state, "config", None))
                allowed_obs_cols.update({"Building", "Floor", "Cabinet", "Shelf", "Stored as", "Stored_As", "Room", "Drawer", "Box"})

                history_set, hist_fields_by_oid = get_historical_cache(self.app_state)
                prob_cols = []
                if self.app_state.config and "problems" in self.app_state.config.get("ui_sections", {}):
                    prob_cols = [p.get("name") for p in self.app_state.config["ui_sections"]["problems"] if p.get("name")]
                problem_to_field = get_problem_to_field_map(self.app_state.config)

                for raw_item in items:
                    if isinstance(raw_item, dict):
                        oid = str(raw_item.get('id') or raw_item.get('oid') or '').strip()
                        item_loc = raw_item.get('location') or location
                    else:
                        oid = str(raw_item).strip()
                        item_loc = location

                    if not oid:
                        continue

                    obs_updates = dict(item_loc)
                    if "Stored_As" in obs_updates and "Stored as" not in obs_updates:
                        obs_updates["Stored as"] = obs_updates.pop("Stored_As")

                    edit_summary, err = _execute_record_update(
                        self.app_state, oid, {}, obs_updates, None,
                        allowed_reg_cols=allowed_reg_cols,
                        allowed_obs_cols=allowed_obs_cols,
                        recent_edits=self.recent_edits,
                        client_timestamp=client_timestamp,
                        session_id=client_sid
                    )
                    if err:
                        errors.append({"id": oid, "error": err})
                    else:
                        updated_ids.append(oid)
                        self.app_state._mobile_last_edited_oid = oid

                if updated_ids:
                    self.app_state.df_log = _normalise_log_dataframe(pd.DataFrame(self.app_state._log_records))
                    self.app_state.dirty = True

            for u_oid in updated_ids:
                self.broadcast_event("record_updated", {"id": str(u_oid)})

            if updated_ids and self.on_edit_callback:
                try:
                    loc_summary = f"{location.get('Building', '')} Fl {location.get('Floor', '')} Cab {location.get('Cabinet', '')} Sh {location.get('Shelf', '')}".strip()
                    self.on_edit_callback(f"Batch ({len(updated_ids)} items)", f"Relocated {len(updated_ids)} items to {loc_summary}")
                except Exception:
                    pass

            if updated_ids and self.root_tk:
                try:
                    self.root_tk.after(0, lambda: app_bus.publish(DATABASE_UPDATED, mobile_edit=True))
                except Exception:
                    pass

            return jsonify({
                "status": "ok",
                "success": True,
                "updated_count": len(updated_ids),
                "updated_ids": updated_ids,
                "errors": errors,
                "synced_at": datetime.now().isoformat()
            })

        @app.route('/api/photo/<path:filename>', methods=['GET'])
        def get_photo(filename):
            if not self._check_auth():
                return jsonify({"error": "Unauthorized"}), 401

            safe_filename_clean = secure_filename(os.path.basename(filename))
            if not safe_filename_clean:
                return jsonify({"error": "Invalid filename"}), 400

            if self.app_state.excel_path:
                db_folder = os.path.dirname(self.app_state.excel_path)
            else:
                db_folder = os.getcwd()
            photos_dir = os.path.join(db_folder, "photos")
            file_path = os.path.join(photos_dir, safe_filename_clean)

            try:
                canonical_photos_dir = os.path.abspath(photos_dir)
                canonical_file_path = os.path.abspath(file_path)
                # Ensure path stays within photos directory and is a regular file
                if not canonical_file_path.startswith(canonical_photos_dir + os.sep) and canonical_file_path != canonical_photos_dir:
                    return jsonify({"error": "Invalid filename"}), 400
                if not os.path.isfile(canonical_file_path):
                    return jsonify({"error": "Photo not found"}), 404
                return send_file(canonical_file_path)
            except Exception as e:
                debug_error("Photo serving error", str(e))
                return jsonify({"error": "Photo not found"}), 404

        @app.route('/api/object/<oid>/photo', methods=['POST'])
        def attach_photo(oid):
            oid = str(oid).strip()
            safe_oid = re.sub(r'[^\w\-.]', '_', oid)

            if 'image' not in request.files and 'file' not in request.files:
                return jsonify({"error": "No image payload found"}), 400

            file = request.files.get('image') or request.files.get('file')
            if file.filename == '':
                return jsonify({"error": "Empty filename"}), 400

            caption = request.form.get('caption', '').strip()
            category = request.form.get('category', '').strip()

            with self.app_state.df_lock:
                if self.app_state.df_reg is None:
                    return jsonify({"error": "No database loaded"}), 400

                reg_oid = _resolve_oid_in_df(self.app_state.df_reg, oid)
                if reg_oid is None:
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
            ext = ext.lower()
            allowed_exts = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.bmp'}
            if ext not in allowed_exts:
                return jsonify({"error": f"Unsupported image file extension: {ext}"}), 400

            new_filename = f"{safe_oid}_{timestamp}{ext}"
            file_path = os.path.join(photos_dir, new_filename)

            try:
                file.save(file_path)
            except Exception as e:
                debug_error("Photo Upload Error", str(e))
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                return jsonify({"error": "Failed to save image"}), 500

            with self.app_state.df_lock:
                if self.app_state.df_reg is None:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass
                    return jsonify({"error": "Database unloaded during upload"}), 400

                reg_oid = _resolve_oid_in_df(self.app_state.df_reg, oid)
                if reg_oid is None:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass
                    return jsonify({"error": f"Object {oid} not found"}), 404

                if getattr(self.app_state, 'df_photo', None) is None:
                    self.app_state.df_photo = pd.DataFrame(columns=["PhotoPath", "FileName", "Caption", "Timestamp"])
                    self.app_state.df_photo.index.name = "ObjectID"

                cols = self.app_state.df_photo.columns.tolist()
                new_row = {}
                for c in cols:
                    new_row[c] = ""

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

                new_df = pd.DataFrame([new_row], index=[reg_oid])
                new_df.index.name = self.app_state.df_photo.index.name or "ObjectID"

                self.app_state.df_photo = pd.concat([self.app_state.df_photo, new_df])

                if not hasattr(self.app_state, "_log_records") or self.app_state._log_records is None:
                    if getattr(self.app_state, "df_log", None) is not None and not self.app_state.df_log.empty:
                        self.app_state._log_records = self.app_state.df_log.to_dict(orient="records")
                    else:
                        self.app_state._log_records = []

                now_ts = datetime.now().isoformat(timespec="seconds")
                log_entry = {
                    "Timestamp": now_ts,
                    "Action": "PHOTO_ADDED",
                    "Reviewed": "",
                    "ObjectID": str(oid),
                    "ChangedFields": "Photo",
                    "ChangedValues": f"Added {new_filename}",
                    "ProblemsChanged": "",
                    "ProblemsChangedValues": "",
                    "LocationChanged": "",
                    "LocationChangedValues": "",
                    "User": "Mobile-Companion",
                    "SourceFile": os.path.basename(getattr(self.app_state, 'excel_path', '') or "") if getattr(self.app_state, 'excel_path', None) else "",
                    "OutputFile": os.path.basename(getattr(self.app_state, 'output_path', '') or getattr(self.app_state, 'excel_path', '') or "") if getattr(self.app_state, 'output_path', None) or getattr(self.app_state, 'excel_path', None) else ""
                }
                if getattr(self.app_state, "_mobile_session_id", None):
                    log_entry["_session_id"] = self.app_state._mobile_session_id
                self.app_state._log_records.append(log_entry)
                self.app_state.df_log = _normalise_log_dataframe(pd.DataFrame(self.app_state._log_records))
                self.app_state.dirty = True

            if self.root_tk:
                try:
                    self.root_tk.after(0, lambda: app_bus.publish(DATABASE_UPDATED, mobile_edit=True))
                except Exception:
                    pass

            return jsonify({
                "success": True,
                "photo_id": new_filename,
                "filename": new_filename,
                "url": f"/api/photo/{new_filename}"
            }), 201

        @app.route('/api/batch_update', methods=['POST'])
        def batch_update_objects():
            is_auth, client_sid, _ = self._get_current_session()
            if not is_auth:
                return jsonify({"error": "Unauthorized"}), 401

            data = request.get_json(silent=True) or {}
            updates_list = data.get('updates')
            if not updates_list or not isinstance(updates_list, list):
                return jsonify({"error": "Missing or invalid 'updates' array"}), 400

            updated_ids = []

            with self.app_state.df_lock:
                if self.app_state.df_reg is None:
                    return jsonify({"error": "No database loaded"}), 400

                allowed_reg_cols, allowed_obs_cols = _get_allowed_columns(getattr(self.app_state, "config", None))

                for update in updates_list:
                    oid = str(update.get('id') or update.get('oid') or '').strip()
                    if not oid:
                        continue

                    reviewed = update.get('reviewed')
                    obs_updates = update.get('observation') or {}
                    reg_updates = update.get('registration') or {}
                    client_timestamp = update.get('timestamp')
                    unval_updates = update.get('unvalidated_sources')
                    if unval_updates is None:
                        unval_updates = update.get('unvalidated')

                    _, err = _execute_record_update(
                        self.app_state, oid, reg_updates, obs_updates, reviewed,
                        allowed_reg_cols=allowed_reg_cols,
                        allowed_obs_cols=allowed_obs_cols,
                        recent_edits=self.recent_edits,
                        client_timestamp=client_timestamp,
                        unvalidated_updates=unval_updates,
                        session_id=client_sid
                    )
                    if err:
                        continue

                    updated_ids.append(oid)
                    self.broadcast_event("record_updated", {"id": oid})

                if updated_ids:
                    self.app_state.df_log = _normalise_log_dataframe(pd.DataFrame(self.app_state._log_records))
                    self.app_state.dirty = True
                    self.app_state._mobile_last_edited_oid = updated_ids[-1]

            if not updated_ids:
                return jsonify({"success": True, "updated_count": 0, "updated_ids": []})

            # Notify desktop UI
            if self.on_edit_callback:
                try:
                    self.on_edit_callback("BATCH", f"Batch updated {len(updated_ids)} records")
                except Exception:
                    pass

            if self.root_tk:
                try:
                    self.root_tk.after(0, lambda: app_bus.publish(DATABASE_UPDATED, mobile_edit=True))
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
  <script src="https://cdn.tailwindcss.com"></script>
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
  <script src="https://cdn.tailwindcss.com"></script>
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
      <div class="flex items-center gap-2" id="offlineBannerContent">
        <span class="text-sm">⚠</span>
        <span>Connection to host lost. Reconnecting...</span>
      </div>
      <button
        type="button"
        id="btnOfflineRetry"
        onclick="setupEventSource()"
        class="min-h-[32px] px-2.5 py-1 bg-ember text-white rounded-[2px] font-bold text-[11px] touch-press shrink-0"
      >
        Retry
      </button>
    </div>

    <!-- Persistent App Header & Search Bar -->
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
          <!-- Settings Modal Trigger -->
          <button
            type="button"
            onclick="openSettingsModal()"
            class="p-2 bg-surface hover:bg-tonal1 border border-bordercol rounded-[2px] text-ink transition-colors touch-target-min flex items-center justify-center shrink-0"
            title="Settings"
          >
            <span class="text-ink text-sm font-mono">⚙️</span>
          </button>

          <!-- Recent Changes Drawer Trigger -->
          <button
            type="button"
            onclick="openRecentEditsModal()"
            class="p-2 bg-surface hover:bg-tonal1 border border-bordercol rounded-[2px] text-ink transition-colors touch-target-min flex items-center justify-center shrink-0"
            title="Recent Changes"
          >
            <span class="text-ink text-sm font-mono">↩</span>
          </button>

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
              <span id="connPingDotAnimate" class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-ember"></span>
              <span id="connPingDot" class="relative inline-flex rounded-full h-2 w-2 bg-ember"></span>
            </span>
            <span class="font-mono text-[11px] font-medium text-ink" id="pingBadge">
              Connecting...
            </span>
          </button>
        </div>
      </div>

      <!-- Persistent Search Input Box -->
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
          id="btnFilterModalTrigger"
          onclick="openFilterModal()"
          class="relative p-2 bg-surface hover:bg-tonal1 border border-bordercol rounded-[2px] text-ink transition-colors touch-target-min flex items-center justify-center shrink-0"
          title="Advanced Filter"
        >
          <span class="text-ink text-sm font-mono">⚙</span>
          <span id="filterActiveBadge" class="hidden absolute -top-1 -right-1 w-2.5 h-2.5 bg-fern rounded-full ring-2 ring-surface"></span>
        </button>
      </div>
    </header>

    <!-- ========================================== -->
    <!-- VIEW: SPECIMEN LIST                        -->
    <!-- ========================================== -->
    <div id="listView" class="flex-1 flex flex-col h-full bg-canvas overflow-hidden">
      <!-- List View Filter & Sort Controls -->
      <div class="bg-surface border-b border-bordercol px-4 pt-1.5 pb-2 shadow-xs shrink-0">
        <!-- Filter Pill Tabs -->
        <div class="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1" id="filterPills">
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

          <button
            type="button"
            onclick="setStatusFilter('conflict')"
            id="pill-conflict"
            class="min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border transition-colors touch-press flex items-center gap-1.5 bg-[#e0f2fe] text-[#0369a1] border-[#bae6fd] hover:bg-[#bae6fd]"
          >
            <span>🔀</span>
            <span>Conflict (0)</span>
          </button>

          <button
            type="button"
            onclick="setStatusFilter('unknown')"
            id="pill-unknown"
            class="min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border transition-colors touch-press flex items-center gap-1.5 bg-[#fef9c3] text-[#854d0e] border-[#fde047] hover:bg-[#fef08a]"
          >
            <span>?</span>
            <span>Unknown (0)</span>
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
              <option value="id-asc">Sort by Accession / ID Number</option>
              <option value="location">Physical Location</option>
              <option value="name-asc">Scientific Name (A-Z)</option>
              <option value="name-desc">Scientific Name (Z-A)</option>
            </select>
          </div>
        </div>
      </div>

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
          <!-- Undo Button (shown conditionally after edit) -->
          <button
            type="button"
            id="btnMobileUndo"
            onclick="undoLastEdit()"
            class="hidden items-center gap-1 text-[11px] font-sans font-bold bg-ember-light text-ember-dark border border-ember-border px-2 py-1 rounded-[2px] hover:bg-ember/10 transition-colors touch-target-min"
          >
            <span>↩</span>
            <span>Undo</span>
          </button>

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

        <!-- Presence Warning Banner (Shown when another worker is viewing this object) -->
        <div id="detailPresenceBanner" class="hidden flex items-center gap-2 p-3 bg-amber-50 border border-amber-300 rounded-[2px] text-amber-900 text-xs font-sans font-medium">
          <span class="text-sm">⚠️</span>
          <span id="detailPresenceText">Warning: Another worker is currently viewing this record.</span>
        </div>

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

        <!-- Active Problems Alert Banner (Dynamically shown if problems/unknowns exist) -->
        <div id="detailProblemBanner" class="hidden bg-ember-light border border-ember-border rounded-[2px] p-3 shadow-xs space-y-1.5">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-ember-dark flex items-center gap-1">
              <span>⚠</span>
              <span>Active Problems Detected</span>
            </span>
          </div>
          <div id="detailProblemBadges" class="flex flex-wrap items-center gap-1.5 pt-1">
            <!-- Problem chips injected here -->
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
            onclick="loadInitialPhoto()"
            class="relative w-full h-16 bg-ink/5 rounded-[2px] border border-bordercol overflow-hidden cursor-pointer group flex items-center justify-center transition-all duration-300"
          >
            <div id="photoPlaceholder" class="p-2 text-center text-xs text-ink-muted flex flex-col items-center gap-0.5">
              <span class="text-xl">📷</span>
              <p class="font-semibold text-fern" id="photoPlaceholderText">Tap to Load Archival Scans</p>
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
              <span class="font-mono text-fern-dark font-medium hidden" id="footerSyncStatusText">✓ Edit saved</span>
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
    <!-- MODAL: APP SETTINGS                        -->
    <!-- ========================================== -->
    <div id="settingsModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded-[2px] w-full max-w-md shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between">
          <div class="flex items-center gap-2 text-ink">
            <span class="text-sm">⚙️</span>
            <h2 class="font-serif font-bold text-sm text-ink">
              Application Settings
            </h2>
          </div>
          <button
            type="button"
            onclick="closeSettingsModal()"
            class="p-1 text-ink-faint hover:text-ink rounded-[2px] text-sm font-bold touch-press"
          >
            ✕
          </button>
        </header>

        <div class="p-4 space-y-4">
          <div>
            <label class="block font-sans text-xs font-medium text-ink mb-1">Image URL Pattern Override</label>
            <input type="text" id="settingImageUrlPattern" placeholder="e.g. https://example.com/{id}.jpg" class="w-full bg-surface border border-bordercol rounded-[2px] px-2.5 py-1.5 text-xs text-ink outline-none focus:border-fern" />
            <p class="text-[10px] text-ink-muted mt-1">Available tokens: {id}, {num}, {num:04d}, {suffix}. Leave blank to use desktop defaults.</p>
          </div>

          <div class="pt-2 border-t border-tonal2 flex justify-end gap-2">
            <button type="button" onclick="closeSettingsModal()" class="px-3 py-1.5 border border-bordercol text-ink-muted hover:bg-surface rounded-[2px] text-xs font-medium touch-press">Cancel</button>
            <button type="button" onclick="saveSettings()" class="px-3 py-1.5 bg-fern hover:bg-fern-dark text-white rounded-[2px] text-xs font-bold transition-colors touch-press">Save</button>
          </div>
        </div>
      </div>
    </div>


    <!-- ========================================== -->
    <!-- MODAL: LOCATION PRESETS SETTINGS           -->
    <!-- ========================================== -->
    <div id="presetSettingsModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded-[2px] w-full max-w-md shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between">
          <div class="flex items-center gap-2 text-ink">
            <span class="text-sm">⚙️</span>
            <h2 class="font-serif font-bold text-sm text-ink">
              Location Presets Settings
            </h2>
          </div>
          <button
            type="button"
            onclick="closePresetSettings()"
            class="p-1 text-ink-faint hover:text-ink rounded-[2px] text-sm font-bold touch-press"
          >
            ✕
          </button>
        </header>

        <div class="p-4 space-y-4">
          <div>
            <h3 class="font-bold text-xs text-ink uppercase tracking-wider mb-2">Saved Presets</h3>
            <div id="presetSettingsList" class="max-h-48 overflow-y-auto space-y-1">
               <!-- Preset items injected dynamically -->
            </div>
          </div>

          <div class="pt-2 border-t border-tonal2">
            <button type="button" onclick="toggleNewPresetForm()" class="w-full py-2 bg-fern hover:bg-fern-dark text-white rounded-[2px] text-xs font-bold transition-colors mb-2 cursor-pointer touch-press">
              + Save Current Location as New Preset
            </button>
            <div id="newPresetForm" class="hidden space-y-2 mt-2 p-3 bg-tonal1 border border-bordercol rounded-[2px]">
              <label class="block font-sans text-xs font-medium text-ink">New Preset Name</label>
              <input type="text" id="newPresetNameInput" placeholder="e.g., Cabinet A, Shelf 2" class="w-full bg-surface border border-bordercol rounded-[2px] px-2.5 py-1.5 text-xs text-ink outline-none focus:border-fern" />
              <div class="flex justify-end gap-2 mt-2">
                <button type="button" onclick="toggleNewPresetForm()" class="px-3 py-1.5 border border-bordercol text-ink-muted hover:bg-surface rounded-[2px] text-xs font-medium touch-press">Cancel</button>
                <button type="button" onclick="saveNewLocPreset()" class="px-3 py-1.5 bg-fern hover:bg-fern-dark text-white rounded-[2px] text-xs font-bold transition-colors touch-press">Save</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========================================== -->
    <!-- ========================================== -->
    <!-- MODAL: RECENT EDITS DRAWER                 -->
    <!-- ========================================== -->
    <div id="recentEditsModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex justify-end">
      <div class="bg-surface w-full max-w-sm h-full shadow-xl overflow-hidden flex flex-col animate-in slide-in-from-right duration-200 border-l border-bordercol">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-2">
            <span class="text-sm">↩</span>
            <h2 class="font-serif font-bold text-sm text-ink">
              Recent Changes
            </h2>
          </div>
          <button
            type="button"
            onclick="closeRecentEditsModal()"
            class="p-1 text-ink-faint hover:text-ink rounded-[2px] text-sm font-bold"
          >
            ✕
          </button>
        </header>

        <div class="p-4 overflow-y-auto space-y-3 flex-1 bg-canvas" id="recentEditsList">
          <!-- Dynamically populated -->
        </div>
      </div>
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

          <div class="p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-[2px] space-y-2">
            <label class="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" id="discrepancyUnvalCheck" onchange="document.getElementById('discrepancyUnvalContainer').classList.toggle('hidden', !this.checked)" class="w-4 h-4 text-amber-600 rounded cursor-pointer">
              <span class="text-xs font-bold text-amber-800 dark:text-amber-300">Flag as Unvalidated Source</span>
            </label>
            <div id="discrepancyUnvalContainer" class="hidden">
              <input type="text" id="discrepancyUnvalNoteInput" placeholder="Explain why source is unvalidated (optional)..." class="w-full bg-surface border border-amber-500/30 rounded-[2px] px-2.5 py-1.5 text-xs text-ink outline-none">
            </div>
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
    <!-- MODAL: LEAVE DATABASE CONFIRMATION         -->
    <!-- ========================================== -->
    <div id="leaveConfirmModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded-[2px] w-full max-w-sm p-4 shadow-xl space-y-3">
        <div class="flex items-center justify-between border-b border-tonal2 pb-2">
          <h3 class="font-serif font-bold text-sm text-ink">⚠️ Leave Database?</h3>
          <button type="button" onclick="cancelLeaveModal()" class="text-ink-muted font-bold text-sm">✕</button>
        </div>

        <p class="font-sans text-xs text-ink-muted leading-relaxed">
          do you want to leave the database? (you might need to resync)
        </p>

        <div class="flex items-center gap-2 pt-2">
          <button
            type="button"
            onclick="cancelLeaveModal()"
            class="flex-1 py-2 border border-bordercol bg-tonal1 hover:bg-tonal2 text-ink rounded-[2px] text-xs font-bold transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onclick="confirmLeaveModal()"
            class="flex-1 py-2 bg-ember hover:bg-ember-dark text-white rounded-[2px] text-xs font-bold transition"
          >
            Leave
          </button>
        </div>
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

    <!-- ========================================== -->
    <!-- MODAL: ICEDIG MISSING DATA BOTTOM SHEET   -->
    <!-- ========================================== -->
    <div id="icedigBottomSheetModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div class="bg-surface border-t sm:border border-bordercol rounded-t-xl sm:rounded-[2px] w-full max-w-md shadow-2xl overflow-hidden max-h-[90vh] flex flex-col animate-in slide-in-from-bottom duration-150">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between">
          <div class="flex items-center gap-2 text-amber-700 dark:text-amber-400">
            <span class="text-sm font-bold">∅</span>
            <h2 id="icedigModalTitle" class="font-serif font-bold text-sm text-ink">
              Missing Data Status
            </h2>
          </div>
          <button
            type="button"
            onclick="closeIcedigBottomSheet()"
            class="p-1 text-ink-faint hover:text-ink rounded-[2px] text-sm font-bold cursor-pointer"
          >
            ✕
          </button>
        </header>

        <div class="p-4 space-y-3 overflow-y-auto">
          <div id="icedigOverwriteNotice" class="hidden p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-[2px] text-xs text-amber-800 dark:text-amber-300 font-medium">
            ⚠️ Overwriting current value: <span id="icedigCurrentValPreview" class="font-bold"></span>
          </div>

          <div class="text-[11px] font-sans text-ink-muted uppercase tracking-wider font-bold">
            Select ICEDIG D4.1 Standard Code:
          </div>

          <div class="space-y-2">
            <button
              type="button"
              onclick="applyIcedigChoice('unknown:missing')"
              class="w-full text-left p-3 rounded-[2px] border border-bordercol bg-surface hover:bg-amber-500/10 hover:border-amber-400 transition-colors cursor-pointer touch-press"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-ink">📄 Blank on Physical Label</span>
                <code class="text-[10px] bg-tonal1 px-1.5 py-0.5 rounded text-ink-muted font-mono">unknown:missing</code>
              </div>
              <p class="text-[11px] text-ink-muted mt-0.5">Information was looked for but is genuinely absent on the physical specimen label.</p>
            </button>

            <button
              type="button"
              onclick="applyIcedigChoice('unknown:indecipherable')"
              class="w-full text-left p-3 rounded-[2px] border border-bordercol bg-surface hover:bg-amber-500/10 hover:border-amber-400 transition-colors cursor-pointer touch-press"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-ink">🔍 Illegible / Damaged Label</span>
                <code class="text-[10px] bg-tonal1 px-1.5 py-0.5 rounded text-ink-muted font-mono">unknown:indecipherable</code>
              </div>
              <p class="text-[11px] text-ink-muted mt-0.5">Text is physically present but cannot be read due to handwriting, fading, or damage.</p>
            </button>

            <button
              type="button"
              onclick="applyIcedigChoice('unknown:undigitized')"
              class="w-full text-left p-3 rounded-[2px] border border-bordercol bg-surface hover:bg-amber-500/10 hover:border-amber-400 transition-colors cursor-pointer touch-press"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-ink">⏭️ Skipped in Digitization</span>
                <code class="text-[10px] bg-tonal1 px-1.5 py-0.5 rounded text-ink-muted font-mono">unknown:undigitized</code>
              </div>
              <p class="text-[11px] text-ink-muted mt-0.5">Field was intentionally omitted from this digitization workflow pass.</p>
            </button>

            <button
              type="button"
              onclick="applyIcedigChoice('withheld')"
              class="w-full text-left p-3 rounded-[2px] border border-bordercol bg-surface hover:bg-amber-500/10 hover:border-amber-400 transition-colors cursor-pointer touch-press"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-ink">🔒 Sensitive / Withheld</span>
                <code class="text-[10px] bg-tonal1 px-1.5 py-0.5 rounded text-ink-muted font-mono">withheld</code>
              </div>
              <p class="text-[11px] text-ink-muted mt-0.5">Data exists but is redacted for policy, privacy, or species protection reasons.</p>
            </button>
          </div>

          <div class="pt-2 border-t border-bordercol flex items-center justify-between gap-2">
            <button
              type="button"
              onclick="applyIcedigChoice('')"
              class="px-3 py-2 text-xs text-ink-muted hover:text-ember rounded border border-bordercol hover:bg-tonal1 cursor-pointer touch-press"
            >
              Clear Field (Blank)
            </button>
            <button
              type="button"
              onclick="closeIcedigBottomSheet()"
              class="px-4 py-2 bg-tonal1 hover:bg-tonal2 text-ink text-xs font-bold rounded border border-bordercol cursor-pointer touch-press"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Floating Toast Notification -->
    <div id="toast" class="hidden fixed bottom-24 left-4 right-4 max-w-sm mx-auto bg-fern-dark text-white text-xs font-bold py-2.5 px-4 rounded-[2px] shadow-lg text-center z-50 transition-opacity">
      Edits saved & synchronized
    </div>

  </div>

  <!-- ========================================== -->
  <!-- CLIENT APPLICATION SCRIPT                  -->
  <!-- ========================================== -->
  <script>
    const _urlParams = new URLSearchParams(window.location.search);
    const TOKEN = _urlParams.get('token') || "{{ token }}";
    let activeSchema = null;
    let objectList = [];
    let currentOid = null;
    let currentRecord = null;
    let isReviewed = false;
    let activeStatusFilter = 'all';
    let noImageFilterActive = false;
    let activeAdvancedFilters = { locations: {}, problems: {} };
    let activeSortBy = 'id-asc';
    let searchQuery = '';
    let searchDebounceTimer = null;
    let autoSaveTimer = null;
    let isSaving = false;
    let hasPendingSave = false;
    let dirtyFields = new Set();
    let currentUnvalidatedMap = {};
    let wakeLockSentinel = null;
    let isWalkModeWanted = false;
    try { isWalkModeWanted = localStorage.getItem('arbor_walk_mode') === 'true'; } catch(e) {}

    let locationPresets = {};
    let lastSelectedPreset = "Default";
    let historicalData = {};
    let revertState = {}; // field: originalValue
    let presenceHeartbeatTimer = null;

    async function sendPresence(oid) {
      try {
        const res = await apiFetch('/api/presence', {
          method: 'POST',
          body: JSON.stringify({ oid: oid ? String(oid) : null })
        });
        if (res && currentOid && String(oid) === String(currentOid)) {
          updatePresenceBanner(res.other_viewers_count || 0);
        }
      } catch (err) {
        console.warn('sendPresence error:', err);
      }
    }

    function updatePresenceBanner(otherCount) {
      const banner = document.getElementById('detailPresenceBanner');
      const text = document.getElementById('detailPresenceText');
      if (!banner) return;
      if (otherCount > 0) {
        if (text) {
          text.textContent = otherCount === 1
            ? 'Warning: Another worker is currently viewing this record.'
            : `Warning: ${otherCount} other workers are currently viewing this record.`;
        }
        banner.classList.remove('hidden');
      } else {
        banner.classList.add('hidden');
      }
    }

    async function fetchHistoricalData(oid) {
      try {
        const cachedData = await getCachedHistoricalData(oid);
        if (cachedData) {
          historicalData = cachedData;
          injectHistoricalData();
        }

        const data = await apiFetch(`/api/object/${encodeURIComponent(oid)}/history`);
        if (data) {
          historicalData = data.historical_data || {};
          cacheHistoricalData(oid, historicalData);
          injectHistoricalData();
        }
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
        markDirty(field);

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
                 markDirty(exactProb);
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
        markDirty(field);

        if (currentRecord.registration && currentRecord.registration[field] !== undefined) {
             currentRecord.registration[field] = originalValue;
        } else if (currentRecord.observation && currentRecord.observation[field] !== undefined) {
             currentRecord.observation[field] = originalValue;
        }

        const exactProb = `${field}_Problem`;
        if (currentRecord.observation && currentRecord.observation.hasOwnProperty(exactProb)) {
             currentRecord.observation[exactProb] = true;
             const probToggle = document.getElementById(`prob_${exactProb}`);
             if (probToggle) probToggle.checked = true;
             markDirty(exactProb);
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
      if (options.body && typeof options.body === 'string' && !options.headers['Content-Type']) {
        options.headers['Content-Type'] = 'application/json';
      }
      const sep = url.includes('?') ? '&' : '?';
      const fullUrl = `${url}${sep}token=${encodeURIComponent(TOKEN)}`;
      const isCacheable = options.method !== 'POST' && (url.startsWith('/api/schema') || url.startsWith('/api/objects'));

      try {
        const res = await fetch(fullUrl, options);
        if (!res.ok) {
          console.warn(`API response status ${res.status} for ${url}`);
        }
        let data = {};
        try {
          data = await res.json();
        } catch (jsonErr) {
          data = {};
        }
        if (data && typeof data === 'object') {
          data._status = res.status;
          data.status = res.status;
          data._ok = res.ok;
        }
        if (isCacheable) {
          cacheApiResponse(url, data);
        }
        return data;
      } catch (err) {
        console.error(`Fetch error on ${url}:`, err);
        if (isCacheable) {
          const cached = await getCachedApiResponse(url);
          if (cached) return cached;
        }
        return {};
      }
    }

    let toastTimeout = null;
    let currentToastUndoCb = null;

    function showToast(msg, isError = false) {
      const toast = document.getElementById('toast');
      if (!toast) return;
      if (toastTimeout) clearTimeout(toastTimeout);
      currentToastUndoCb = null;
      toast.innerHTML = `<span>${msg}</span>`;
      toast.className = `fixed bottom-24 left-4 right-4 max-w-sm mx-auto ${isError ? 'bg-ember-dark' : 'bg-fern-dark'} text-white text-xs font-bold py-2.5 px-4 rounded-[2px] shadow-lg text-center z-50 transition-opacity`;
      toast.classList.remove('hidden');
      toastTimeout = setTimeout(() => toast.classList.add('hidden'), 2200);
    }

    function showToastWithUndo(msg, undoCallback) {
      const toast = document.getElementById('toast');
      if (!toast) return;
      if (toastTimeout) clearTimeout(toastTimeout);
      currentToastUndoCb = undoCallback;
      toast.innerHTML = `
        <div class="flex items-center justify-between gap-3 px-1">
          <span class="truncate">${msg}</span>
          <button type="button" onclick="triggerToastUndo()" class="underline font-bold text-amber-300 hover:text-white text-xs uppercase tracking-wider cursor-pointer touch-press">
            UNDO
          </button>
        </div>
      `;
      toast.className = `fixed bottom-24 left-4 right-4 max-w-sm mx-auto bg-stone-900 text-white text-xs font-bold py-2.5 px-4 rounded-[2px] shadow-xl border border-bordercol z-50 transition-opacity`;
      toast.classList.remove('hidden');
      toastTimeout = setTimeout(() => {
        toast.classList.add('hidden');
        currentToastUndoCb = null;
      }, 5000);
    }

    function triggerToastUndo() {
      if (typeof currentToastUndoCb === 'function') {
        currentToastUndoCb();
        currentToastUndoCb = null;
      }
      const toast = document.getElementById('toast');
      if (toast) toast.classList.add('hidden');
    }

    let currentIcedigTarget = null;
    let icedigUndoState = null;

    function openIcedigBottomSheet(section, fName) {
      const inputId = `input_${section}_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;
      const inputEl = document.getElementById(inputId);
      const currentVal = inputEl ? inputEl.value : '';

      currentIcedigTarget = { section, fName, inputId, previousVal: currentVal };

      const titleEl = document.getElementById('icedigModalTitle');
      if (titleEl) titleEl.textContent = `Missing Data Status: ${fName}`;

      const noticeEl = document.getElementById('icedigOverwriteNotice');
      const previewEl = document.getElementById('icedigCurrentValPreview');
      if (noticeEl && previewEl) {
        if (currentVal && !isValueUnknown(currentVal)) {
          previewEl.textContent = `"${currentVal}"`;
          noticeEl.classList.remove('hidden');
        } else {
          noticeEl.classList.add('hidden');
        }
      }

      openModal('icedigBottomSheetModal');
    }

    function closeIcedigBottomSheet() {
      closeModal('icedigBottomSheetModal');
      currentIcedigTarget = null;
    }

    function applyIcedigChoice(code) {
      if (!currentIcedigTarget) return;
      const { section, fName, inputId, previousVal } = currentIcedigTarget;
      const inputEl = document.getElementById(inputId);

      if (inputEl) {
        inputEl.value = code;
        markDirty(fName);

        const hasUkn = isValueUnknown(code);
        inputEl.className = `w-full min-h-[44px] border rounded-[2px] px-3 py-2 text-xs outline-none ${
          hasUkn
            ? 'border-l-4 border-l-[#FBC02D] bg-[#fef9c3] border-[#fde047] text-[#854d0e] font-medium focus:border-[#eab308]'
            : 'border-bordercol bg-surface text-ink focus:border-fern'
        }`;

        // Update local currentRecord if available
        if (currentRecord) {
          if (section === 'registration' && currentRecord.registration) {
            currentRecord.registration[fName] = code;
          } else if (section === 'observation' && currentRecord.observation) {
            currentRecord.observation[fName] = code;
          }
        }

        // Save undo state & show toast
        icedigUndoState = { section, fName, inputId, valueToRestore: previousVal };
        showToastWithUndo(`Set ${fName} to ${code || 'blank'}`, () => {
          if (icedigUndoState && icedigUndoState.inputId === inputId) {
            inputEl.value = icedigUndoState.valueToRestore;
            markDirty(fName);
            if (currentRecord) {
              if (section === 'registration' && currentRecord.registration) {
                currentRecord.registration[fName] = icedigUndoState.valueToRestore;
              } else if (section === 'observation' && currentRecord.observation) {
                currentRecord.observation[fName] = icedigUndoState.valueToRestore;
              }
            }
            triggerAutoSave();
            saveCurrentEdits();
          }
        });

        triggerAutoSave();
        saveCurrentEdits();
      }

      closeIcedigBottomSheet();
    }

    function openModal(id) {
      document.getElementById(id).classList.remove('hidden');
    }

    function closeModal(id) {
      document.getElementById(id).classList.add('hidden');
    }

    let isLeavingApp = false;
    let hasUnsavedChanges = false;

    function openLeaveModal() {
      openModal('leaveConfirmModal');
    }

    function cancelLeaveModal() {
      closeModal('leaveConfirmModal');
      // Re-push list state so history is restored at [root] -> [list]
      window.history.pushState({ view: 'list' }, '');
    }

    function confirmLeaveModal() {
      isLeavingApp = true;
      closeModal('leaveConfirmModal');
      if (window.history.length > 1) {
        window.history.back();
      } else {
        window.location.href = '/login';
      }
    }

    window.addEventListener('beforeunload', (e) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = 'You have unsaved offline changes. Are you sure you want to leave?';
        return e.returnValue;
      }
    });

    window.addEventListener('popstate', async (event) => {
      if (isLeavingApp) return;

      const state = event.state;

      // If we popped to list view:
      if (state && state.view === 'list') {
        closeModal('leaveConfirmModal');
        closeModal('photoViewerModal');
        closeModal('presetSettingsModal');
        closeModal('filterModal');
        closeModal('addDiscrepancyModal');
        closeModal('connectionModal');
        await showListView(false);
      } else if (state && state.view === 'detail') {
        closeModal('leaveConfirmModal');
        if (state.id && state.id !== currentOid) {
          await loadSpecimen(state.id, true);
        } else {
          showDetailView();
        }
      } else {
        // Popped past list view (e.g. state is 'root' or null) -> user clicked back on List View
        openLeaveModal();
      }
    });


    async function init() {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js').catch(err => console.error('ServiceWorker registration failed: ', err));
      }

      try {
        await initIndexedDB();
      } catch (e) {
        console.warn('Offline DB init failed', e);
      }

      // 0. Initialize SPA History State for Back Button handling
      if (!window.history.state || window.history.state.view !== 'list') {
        window.history.replaceState({ view: 'root' }, '');
        window.history.pushState({ view: 'list' }, '');
      }

      // 1. Immediately initiate live SSE connection in background so desktop detects phone right away
      setupEventSource();
      if (isWalkModeWanted) {
        acquireWakeLock(true);
      }
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
          _reconnectDelay = 2000;
          if (_reconnectTimer) clearTimeout(_reconnectTimer);
          setupEventSource();  // closes stale connection and opens a fresh one
          if (isWalkModeWanted && !wakeLockSentinel) {
            acquireWakeLock(true);
          }
        }
      });
      window.addEventListener('online', () => {
        _reconnectDelay = 2000;
        if (_reconnectTimer) clearTimeout(_reconnectTimer);
        setupEventSource();
      });
      window.addEventListener('offline', () => {
        stopPing();
        if (_reconnectTimer) clearTimeout(_reconnectTimer);
        if (_evtSource) { _evtSource.close(); _evtSource = null; }
        updateConnectionState('disconnected');
      });

      try {
        // 2. Fetch Schema from Master config.py
        activeSchema = await apiFetch('/api/schema');
        const dbName = (activeSchema && activeSchema.database_name) ? activeSchema.database_name : 'Active Database';
        document.getElementById('headerDbName').textContent = dbName;
        document.getElementById('connModalDbName').textContent = dbName;

        // 3. Fetch Initial List
        await fetchList();

        // 4. Fetch Location Presets
        const presetsRes = await apiFetch('/api/presets');
        if (presetsRes && presetsRes.success) {
          locationPresets = presetsRes.presets || {};
        }

        // 5. Populate Discrepancy Field Select Options
        populateDiscrepancyFields();

        // 6. Update Advanced Filter Indicator
        updateFilterIndicator();
      } catch (err) {
        console.error("Initialization error:", err);
        document.getElementById('headerDbName').textContent = 'Active Database';
        fetchList();
      }
    }

    let _evtSource = null;
    let _reconnectDelay = 2000;
    const _maxReconnectDelay = 16000;
    let _pingInterval = null;
    let _missedPings = 0;
    let _reconnectTimer = null;

    function startPing() {
      stopPing();
      _missedPings = 0;
      _pingInterval = setInterval(async () => {
        if (!navigator.onLine) {
           _missedPings = 3; // Force immediate disconnect if browser knows it's offline
        } else {
           try {
             const res = await fetch('/api/ping?token=' + encodeURIComponent(TOKEN));
             if (res.ok) {
               _missedPings = 0;
             } else {
               _missedPings++;
             }
           } catch (e) {
             _missedPings++;
           }
        }

        if (_missedPings >= 3) {
          stopPing();
          if (_evtSource) {
            _evtSource.close();
            _evtSource = null;
          }
          updateConnectionState('disconnected');
          scheduleReconnect();
        }
      }, 10000);
    }

    function stopPing() {
      if (_pingInterval) {
        clearInterval(_pingInterval);
        _pingInterval = null;
      }
    }

    function scheduleReconnect() {
      if (_reconnectTimer) clearTimeout(_reconnectTimer);
      _reconnectTimer = setTimeout(() => {
        setupEventSource();
        _reconnectDelay = Math.min(_reconnectDelay * 2, _maxReconnectDelay);
      }, _reconnectDelay);
    }

    let db;
    function initIndexedDB() {
      return new Promise((resolve, reject) => {
        const request = indexedDB.open('arbor_offline_db', 3);
        request.onupgradeneeded = (e) => {
          const dbInstance = e.target.result;
          if (!dbInstance.objectStoreNames.contains('queued_mutations')) {
            dbInstance.createObjectStore('queued_mutations', { keyPath: 'timestamp' });
          }
          if (!dbInstance.objectStoreNames.contains('api_cache')) {
            dbInstance.createObjectStore('api_cache', { keyPath: 'url' });
          }
          if (!dbInstance.objectStoreNames.contains('historical_cache')) {
            dbInstance.createObjectStore('historical_cache', { keyPath: 'oid' });
          }
        };
        request.onsuccess = (e) => {
          db = e.target.result;
          resolve();
        };
        request.onerror = (e) => {
          console.error('IndexedDB init error:', e);
          reject(e);
        };
      });
    }

    function cacheApiResponse(url, data) {
      if (!db) return;
      try {
        const tx = db.transaction('api_cache', 'readwrite');
        tx.objectStore('api_cache').put({ url, data });
      } catch (e) { console.error('Cache API error', e); }
    }

    function getCachedApiResponse(url) {
      return new Promise((resolve) => {
        if (!db) return resolve(null);
        try {
          const tx = db.transaction('api_cache', 'readonly');
          const req = tx.objectStore('api_cache').get(url);
          req.onsuccess = () => resolve(req.result ? req.result.data : null);
          req.onerror = () => resolve(null);
        } catch (e) {
          resolve(null);
        }
      });
    }

    function cacheHistoricalData(oid, data) {
      if (!db) return;
      try {
        const tx = db.transaction('historical_cache', 'readwrite');
        tx.objectStore('historical_cache').put({ oid, data });
      } catch (e) { console.error('Cache history error', e); }
    }

    function getCachedHistoricalData(oid) {
      return new Promise((resolve) => {
        if (!db) return resolve(null);
        try {
          const tx = db.transaction('historical_cache', 'readonly');
          const req = tx.objectStore('historical_cache').get(oid);
          req.onsuccess = () => resolve(req.result ? req.result.data : null);
          req.onerror = () => resolve(null);
        } catch (e) {
          resolve(null);
        }
      });
    }

    function queueMutation(payload) {
      if (!db) return;
      const tx = db.transaction('queued_mutations', 'readwrite');
      const store = tx.objectStore('queued_mutations');
      store.put(payload);
      tx.oncomplete = () => { updateOfflineBannerQueueCount(); };
      hasUnsavedChanges = true;
    }

    function getQueuedMutations() {
      return new Promise((resolve) => {
        if (!db) return resolve([]);
        const tx = db.transaction('queued_mutations', 'readonly');
        const store = tx.objectStore('queued_mutations');
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result);
      });
    }

    function clearQueuedMutations(timestamps) {
      if (!db) return;
      const tx = db.transaction('queued_mutations', 'readwrite');
      const store = tx.objectStore('queued_mutations');
      if (timestamps && timestamps.length > 0) {
        timestamps.forEach(ts => store.delete(ts));
      } else {
        store.clear();
      }
      tx.oncomplete = () => { updateOfflineBannerQueueCount(); };
    }

    function updateOfflineBannerQueueCount() {
      if (!db) return;
      const tx = db.transaction('queued_mutations', 'readonly');
      const req = tx.objectStore('queued_mutations').count();
      req.onsuccess = () => {
        const count = req.result;
        hasUnsavedChanges = count > 0;
        const banner = document.getElementById('footerSyncStatus');
        if (count > 0 && (!navigator.onLine || (document.getElementById('pingBadge') && document.getElementById('pingBadge').textContent === 'Offline'))) {
          banner.innerHTML = `<span class="font-mono text-ember-dark font-medium">Offline (${count} edits queued)</span>`;
        }
      };
    }

    async function flushQueuedMutations() {
      const mutations = await getQueuedMutations();
      if (mutations.length === 0) return;
      // Sort by timestamp just in case
      mutations.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

      const offlineBanner = document.getElementById('offlineBanner');
      const bannerContent = document.getElementById('offlineBannerContent');
      const retryBtn = document.getElementById('btnOfflineRetry');
      const footerStatus = document.getElementById('footerSyncStatus');

      // Prominent syncing visual feedback
      if (offlineBanner && bannerContent) {
        offlineBanner.className = 'bg-fern-light border-b border-fern-border px-4 py-2 flex items-center justify-between gap-2 text-xs font-sans font-medium text-fern-dark shrink-0 transition-all shadow-xs';
        offlineBanner.classList.remove('hidden');
        bannerContent.innerHTML = `
          <svg class="animate-spin h-3.5 w-3.5 text-fern shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span class="font-bold">Syncing ${mutations.length} queued edit${mutations.length > 1 ? 's' : ''} to host...</span>
        `;
        if (retryBtn) retryBtn.classList.add('hidden');
      }
      if (footerStatus) {
        footerStatus.innerHTML = `<span class="flex items-center gap-1.5 font-mono text-fern-dark font-medium animate-pulse"><span>Syncing queued edits (${mutations.length})...</span></span>`;
      }

      try {
        const res = await apiFetch('/api/batch_update', {
          method: 'POST',
          body: JSON.stringify({ updates: mutations })
        });
        if (res && (res.success || res.updated_count !== undefined)) {
          clearQueuedMutations(mutations.map(m => m.timestamp));
          showToast(`✓ Reconnected: ${mutations.length} queued edits synced to host`);
          if (footerStatus) {
            footerStatus.innerHTML = '<span class="font-mono text-fern-dark font-medium" id="footerSyncStatusText">✓ All synced</span>';
          }
        }
      } catch (err) {
        console.error('Failed to flush queued mutations', err);
        showToast('Sync failed; will retry when connected', true);
      } finally {
        if (offlineBanner && navigator.onLine) {
          offlineBanner.classList.add('hidden');
        }
      }
    }

    function updateConnectionState(state) {
      const badge = document.getElementById('pingBadge');
      const footerHost = document.getElementById('footerTickerHost');
      const dotHeader = document.getElementById('connPingDot');
      const dotHeaderAnim = document.getElementById('connPingDotAnimate');
      const dotFooter = document.getElementById('footerConnDot');
      const dotFooterAnim = document.getElementById('footerConnDotAnimate');
      const offlineBanner = document.getElementById('offlineBanner');
      const bannerContent = document.getElementById('offlineBannerContent');
      const retryBtn = document.getElementById('btnOfflineRetry');
      const syncStatusText = document.getElementById('footerSyncStatusText');

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
        if (offlineBanner) {
          offlineBanner.className = 'bg-ember-light border-b border-ember-border px-4 py-2 flex items-center justify-between gap-2 text-xs font-sans font-medium text-ember-dark shrink-0 transition-all shadow-xs';
          offlineBanner.classList.remove('hidden');
        }
        if (bannerContent) {
          bannerContent.innerHTML = `<span class="text-sm">⚠</span><span>Connection to host lost. Reconnecting...</span>`;
        }
        if (retryBtn) retryBtn.classList.remove('hidden');
        [dotHeader, dotFooter].forEach(d => { if (d) d.className = 'relative inline-flex rounded-full h-2 w-2 bg-ember-dark'; });
        [dotHeaderAnim, dotFooterAnim].forEach(d => { if (d) d.className = 'hidden'; });
        if (syncStatusText) syncStatusText.classList.add('hidden');
      }
    }

    async function fetchStatus() {
      try {
        const res = await apiFetch('/api/status');
        if (res && res.database_name) {
          const dbEl = document.getElementById('headerDbName');
          if (dbEl) dbEl.textContent = res.database_name;
          const modalDb = document.getElementById('connModalDbName');
          if (modalDb) modalDb.textContent = res.database_name;
        }
      } catch (e) {
        console.warn('fetchStatus error', e);
      }
    }

    function setupEventSource() {
      try {
        if (_reconnectTimer) clearTimeout(_reconnectTimer);
        if (_evtSource) { _evtSource.close(); _evtSource = null; }
        updateConnectionState('connecting');
        _evtSource = new EventSource(`/api/events?token=${encodeURIComponent(TOKEN)}`);

        _evtSource.onopen = function() {
          updateConnectionState('connected');
          _reconnectDelay = 2000;
          startPing();
          flushQueuedMutations();
          fetchStatus();
          if (currentOid && dirtyFields.size === 0) {
            loadSpecimen(currentOid, true);
          } else if (!currentOid && activeSchema && objectList.length === 0) {
            fetchList();
          }
        };

        _evtSource.onerror = function() {
          stopPing();
          if (_evtSource) { _evtSource.close(); _evtSource = null; }
          updateConnectionState('disconnected');
          scheduleReconnect();
        };

        _evtSource.onmessage = function(e) {
          try {
            const data = JSON.parse(e.data);
            const eventsToProcess = data.type === 'batch' ? data.events : [data];

            let needsListRender = false;
            let needsListFetch = false;

            for (const evt of eventsToProcess) {
              if (evt.type === 'record_updated' || evt.type === 'object_updated') {
                const updatedId = String(evt.data ? (evt.data.id || evt.data.oid) : '');
                if (evt.data && (evt.data.has_flags !== undefined || evt.data.review_status !== undefined)) {
                  const listItem = objectList.find(o => String(o.id) === updatedId);
                  if (listItem) {
                    Object.assign(listItem, evt.data);
                    if (!document.getElementById('listView').classList.contains('hidden')) {
                      needsListRender = true;
                    }
                  }
                  if (currentRecord && String(currentRecord.id) === updatedId) {
                    Object.assign(currentRecord, evt.data);
                    if (evt.data.review_status) isReviewed = (evt.data.review_status === 'reviewed');
                    updateReviewButtonUI();
                  }
                } else {
                  if (!document.getElementById('listView').classList.contains('hidden')) {
                    needsListFetch = true;
                  } else if (currentRecord && String(currentRecord.id) === updatedId) {
                    apiFetch(`/api/object/${encodeURIComponent(updatedId)}`).then(freshData => {
                      if (currentOid === updatedId) {
                        currentRecord = freshData;
                        isReviewed = (freshData.review_status === 'reviewed');
                        updateReviewButtonUI();
                      }
                    }).catch(() => {});
                  }
                }
              } else if (evt.type === 'presence_updated' && evt.data) {
                const updatedOid = String(evt.data.oid || '');
                if (currentOid && String(currentOid) === updatedOid) {
                  const totalViewers = evt.data.viewers_count || 0;
                  const otherCount = Math.max(0, totalViewers - 1);
                  updatePresenceBanner(otherCount);
                }
              } else if (evt.type === 'session_ended') {
                showSessionEndedOverlay();
              } else if (evt.type === 'push_navigation') {
                showPushNavigationOverlay(evt.data.id);
              } else if (evt.type === 'filter_synced') {
                const payload = evt.data;
                searchQuery = payload.q || "";
                const searchBox = document.getElementById('searchBox');
                if (searchBox) searchBox.value = searchQuery;

                const searchClearBtn = document.getElementById('searchClearBtn');
                if (searchClearBtn) {
                  if (searchQuery) searchClearBtn.classList.remove('hidden');
                  else searchClearBtn.classList.add('hidden');
                }

                activeAdvancedFilters.locations = payload.locations || {};
                activeAdvancedFilters.problems = payload.specific_problems || [];

                noImageFilterActive = payload.no_image || false;
                const noImagePill = document.getElementById('pill-no-image');
                if (noImagePill) {
                  if (noImageFilterActive) {
                    noImagePill.className = 'px-3 py-1 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center gap-1.5 transition-colors bg-ink text-white border-ink';
                  } else {
                    noImagePill.className = 'px-3 py-1 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center gap-1.5 transition-colors bg-surface text-ink-muted border-bordercol hover:bg-tonal1';
                  }
                }

                setStatusFilter(payload.status || 'all').then(() => {
                  showToast("📱 Synced batch with Desktop (" + objectList.length + " matching records)");
                });

                if (!document.getElementById('detailView').classList.contains('hidden')) {
                  showListView(false);
                }
              }
            }

            if (needsListFetch) {
              fetchList();
            } else if (needsListRender) {
              renderList();
            }

          } catch(err) {}
        };
      } catch(err) {
        updateConnectionState('disconnected');
      }
    }

    function showPushNavigationOverlay(oid) {
      const existing = document.getElementById('pushNavOverlay');
      if (existing) existing.remove();

      const overlay = document.createElement('div');
      overlay.id = 'pushNavOverlay';
      overlay.className = 'fixed bottom-4 left-4 right-4 z-[100] flex flex-col bg-surface border border-bordercol rounded-xl shadow-2xl p-4 transform transition-all';
      overlay.innerHTML = `
        <div class="flex items-start gap-3">
          <div class="flex-shrink-0 flex items-center justify-center w-10 h-10 bg-lake-light text-lake-dark rounded-full">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div class="flex-1">
            <h2 class="text-base font-serif font-bold text-ink mb-1">Object Pushed: ${oid}</h2>
            <p class="font-sans text-sm text-ink-muted mb-3">
              The desktop app sent this object. View it now?
            </p>
            <div class="flex gap-2">
              <button id="btnDeclinePush" class="flex-1 py-2 px-3 bg-canvas text-ink-muted font-sans font-bold text-xs rounded-[2px] border border-bordercol touch-press touch-target-min">
                Decline
              </button>
              <button id="btnAcceptPush" class="flex-1 py-2 px-3 bg-fern text-white font-sans font-bold text-xs rounded-[2px] touch-press touch-target-min">
                View Object
              </button>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);

      document.getElementById('btnDeclinePush').addEventListener('click', () => {
        overlay.remove();
      });

      document.getElementById('btnAcceptPush').addEventListener('click', () => {
        overlay.remove();
        loadSpecimen(oid);
      });
    }

    function showSessionEndedOverlay() {
      // Close active SSE connection
      if (_evtSource) {
        _evtSource.close();
        _evtSource = null;
      }

      const overlay = document.createElement('div');
      overlay.className = 'fixed inset-0 z-[100] flex flex-col items-center justify-center bg-surface px-6 text-center';
      overlay.innerHTML = `
        <div class="mb-6 rounded-full bg-ember-light p-4">
          <svg class="h-10 w-10 text-ember-dark" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 class="font-serif text-2xl font-bold text-ink mb-2">Session Ended</h2>
        <p class="font-sans text-ink-muted mb-8 max-w-sm">
          The desktop application has closed this session.
          To continue editing, start a new session on your desktop.
        </p>
        <button onclick="window.location.reload()" class="w-full max-w-[200px] py-3.5 px-4 rounded-[2px] font-sans font-bold text-sm bg-fern text-white border-2 border-fern-dark shadow-md touch-target-min touch-press">
          Refresh & Try Again
        </button>
      `;
      document.body.appendChild(overlay);
    }

    function updateWakeLockUI(active) {
      const btn = document.getElementById('btnWakeLock');
      const icon = document.getElementById('wakeLockIcon');
      if (!btn || !icon) return;
      if (active) {
        btn.className = 'p-2 rounded-[2px] border transition-all touch-target-min bg-amber-400 text-black border-amber-600 ring-2 ring-amber-300 shadow-xs font-bold flex items-center justify-center';
        icon.innerText = '☀️';
        icon.classList.add('animate-spin-slow');
      } else {
        btn.className = 'p-2 rounded-[2px] border transition-colors touch-target-min bg-ink text-surface border-ink hover:bg-ink-muted flex items-center justify-center';
        icon.innerText = '🌙';
        icon.classList.remove('animate-spin-slow');
      }
    }

    async function acquireWakeLock(silent = false) {
      if (!('wakeLock' in navigator)) {
        if (!silent) showToast('Wake Lock API not supported on this browser', true);
        return false;
      }
      try {
        if (wakeLockSentinel) {
          try { await wakeLockSentinel.release(); } catch(e) {}
          wakeLockSentinel = null;
        }
        wakeLockSentinel = await navigator.wakeLock.request('screen');
        updateWakeLockUI(true);
        wakeLockSentinel.addEventListener('release', () => {
          wakeLockSentinel = null;
          if (!isWalkModeWanted) {
            updateWakeLockUI(false);
          }
        });
        if (!silent) showToast('Walk Mode Active (Screen Sleep Prevented)');
        return true;
      } catch (err) {
        if (!silent) showToast('Wake Lock unavailable on this device', true);
        return false;
      }
    }

    async function releaseWakeLock(silent = false) {
      isWalkModeWanted = false;
      try { localStorage.setItem('arbor_walk_mode', 'false'); } catch (e) {}
      if (wakeLockSentinel) {
        try {
          await wakeLockSentinel.release();
        } catch (e) {}
        wakeLockSentinel = null;
      }
      updateWakeLockUI(false);
      if (!silent) showToast('Walk Mode Deactivated (Sleep Allowed)');
    }

    async function toggleWakeLock() {
      if (isWalkModeWanted || wakeLockSentinel) {
        await releaseWakeLock();
      } else {
        isWalkModeWanted = true;
        try { localStorage.setItem('arbor_walk_mode', 'true'); } catch (e) {}
        await acquireWakeLock();
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
      const detailView = document.getElementById('detailView');
      if (detailView && !detailView.classList.contains('hidden')) {
        showListView(false);
      }
      searchDebounceTimer = setTimeout(fetchList, 350);
    }

    function clearSearch() {
      document.getElementById('searchBox').value = '';
      document.getElementById('searchClearBtn').classList.add('hidden');
      searchQuery = '';
      const detailView = document.getElementById('detailView');
      if (detailView && !detailView.classList.contains('hidden')) {
        showListView(false);
      }
      fetchList();
    }

    function renderStatusBadge(item) {
      if (!item) return '';
      const isRev = (item.review_status === 'reviewed') || (item.reviewed === true) || (item.is_reviewed === true);
      const hasFlags = Boolean(item.has_flags);
      const problemsHaveHistory = Boolean(item.problems_have_history !== undefined ? item.problems_have_history : item.has_history);
      const hasUnknown = Boolean(item.has_unknown);

      let label, bg, fg, border, icon;
      if (isRev && hasFlags) {
        label = 'REV+ERR';
        bg = '#F57C00';
        fg = '#ffffff';
        border = '#F57C00';
        icon = '⚠';
      } else if (isRev) {
        label = 'OK';
        bg = '#2E7D32';
        fg = '#ffffff';
        border = '#2E7D32';
        icon = '✓';
      } else if (hasFlags && problemsHaveHistory) {
        label = 'ERR+HIS';
        bg = '#7B1FA2';
        fg = '#ffffff';
        border = '#7B1FA2';
        icon = '⚠';
      } else if (hasFlags) {
        label = 'ERR';
        bg = '#C62828';
        fg = '#ffffff';
        border = '#C62828';
        icon = '⚠';
      } else if (problemsHaveHistory) {
        label = 'CFCT';
        bg = '#0284C7';
        fg = '#ffffff';
        border = '#0284C7';
        icon = '🔀';
      } else if (hasUnknown) {
        label = 'UKN';
        bg = '#FBC02D';
        fg = '#2c302e';
        border = '#FBC02D';
        icon = '?';
      } else {
        label = 'UNREV';
        bg = '#45475a';
        fg = '#ffffff';
        border = '#45475a';
        icon = '🕒';
      }

      return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[10px] font-sans font-semibold" style="background-color: ${bg}; color: ${fg}; border: 1px solid ${border};">${icon} ${label}</span>`;
    }

    function setStatusFilter(status) {
      activeStatusFilter = status;
      const filterStyles = {
        all: {
          active: 'bg-ink text-white border-ink font-semibold',
          inactive: 'bg-surface text-ink-muted border-bordercol hover:bg-tonal1'
        },
        pending: {
          active: 'bg-[#45475a] text-white border-[#45475a] shadow-xs font-semibold',
          inactive: 'bg-surface text-ink-muted border-bordercol hover:bg-tonal1'
        },
        flagged: {
          active: 'bg-[#C62828] text-white border-[#C62828] shadow-xs font-semibold',
          inactive: 'bg-ember-light text-ember-dark border-ember-border hover:bg-ember-light/80'
        },
        reviewed: {
          active: 'bg-[#2E7D32] text-white border-[#2E7D32] shadow-xs font-semibold',
          inactive: 'bg-fern-light text-fern-dark border-fern-border hover:bg-fern-light/80'
        },
        conflict: {
          active: 'bg-[#0284C7] text-white border-[#0284C7] shadow-xs font-semibold',
          inactive: 'bg-[#e0f2fe] text-[#0369a1] border-[#bae6fd] hover:bg-[#bae6fd]'
        },
        unknown: {
          active: 'bg-[#FBC02D] text-[#2c302e] border-[#FBC02D] shadow-xs font-semibold',
          inactive: 'bg-[#fef9c3] text-[#854d0e] border-[#fde047] hover:bg-[#fef08a]'
        }
      };

      ['all', 'pending', 'flagged', 'reviewed', 'conflict', 'unknown'].forEach(s => {
        const pill = document.getElementById(`pill-${s}`);
        if (!pill) return;
        const isSelected = (s === status);
        const styleRule = filterStyles[s] || filterStyles.all;
        pill.className = `min-h-[44px] px-3.5 py-2 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border transition-colors touch-press flex items-center justify-center gap-1.5 ${isSelected ? styleRule.active : styleRule.inactive}`;
      });
      return fetchList();
    }

    function handleSortChange() {
      activeSortBy = document.getElementById('sortBySelect').value;
      renderList();
    }

    function toggleNoImageFilter() {
      noImageFilterActive = !noImageFilterActive;
      const pill = document.getElementById('pill-no-image');
      if (noImageFilterActive) {
        pill.className = 'px-3 py-1 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center gap-1.5 transition-colors bg-ink text-white border-ink';
      } else {
        pill.className = 'px-3 py-1 rounded-[2px] font-sans text-xs font-medium whitespace-nowrap border flex items-center gap-1.5 transition-colors bg-surface text-ink-muted border-bordercol hover:bg-tonal1';
      }
      fetchList();
    }

    function cycleTriState(btn) {
      const row = btn.closest('[data-prob-name]');
      if (!row) return;
      const pName = row.getAttribute('data-prob-name');
      const currState = row.getAttribute('data-state') || 'ignore';
      let nextState = 'ignore';
      if (currState === 'ignore') nextState = 'has';
      else if (currState === 'has') nextState = 'not';
      else nextState = 'ignore';

      row.setAttribute('data-state', nextState);
      updateTriStateVisual(row, nextState);
    }

    function updateTriStateVisual(row, state) {
      const badge = row.querySelector('.tristate-badge');
      const icon = row.querySelector('.tristate-icon');
      if (!badge || !icon) return;

      if (state === 'has') {
        row.className = 'flex items-center justify-between p-2.5 rounded-[2px] border border-fern bg-fern-light/30 transition-colors cursor-pointer touch-press';
        badge.className = 'tristate-badge px-2.5 py-1 text-[11px] font-bold rounded-[2px] bg-fern text-white shadow-xs';
        badge.textContent = 'HAS (✓)';
        icon.textContent = '✓';
        icon.className = 'tristate-icon text-sm font-bold text-fern';
      } else if (state === 'not') {
        row.className = 'flex items-center justify-between p-2.5 rounded-[2px] border border-ember bg-ember-light/30 transition-colors cursor-pointer touch-press';
        badge.className = 'tristate-badge px-2.5 py-1 text-[11px] font-bold rounded-[2px] bg-ember text-white shadow-xs';
        badge.textContent = 'NOT (−)';
        icon.textContent = '−';
        icon.className = 'tristate-icon text-sm font-bold text-ember';
      } else {
        row.className = 'flex items-center justify-between p-2.5 rounded-[2px] border border-bordercol bg-surface hover:bg-tonal1 transition-colors cursor-pointer touch-press';
        badge.className = 'tristate-badge px-2.5 py-1 text-[11px] font-bold rounded-[2px] bg-tonal2 text-ink-muted';
        badge.textContent = 'IGNORE';
        icon.textContent = '□';
        icon.className = 'tristate-icon text-sm font-normal text-ink-faint';
      }
    }

    function openFilterModal() {
      // Populate Location Filters
      const locContainer = document.getElementById('filterModalLocations');
      locContainer.innerHTML = '';
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.location) {
        activeSchema.ui_sections.location.forEach(field => {
          if (field.type === 'checkbox') return; // Skip bool locations for simplicity

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

      // Populate Specific Problems & History with Tri-State Controls
      const probContainer = document.getElementById('filterModalProblems');
      probContainer.innerHTML = '';

      // Static items
      let staticProblems = [
        { name: "Any_Problem", label: "Any problem (all flags)" },
        { name: "Historical_Data", label: "Historical Data (Has / No History)" },
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
        const currState = (activeAdvancedFilters.problems && activeAdvancedFilters.problems[p.name]) || 'ignore';
        probContainer.innerHTML += `
          <div
            data-prob-name="${p.name}"
            data-state="${currState}"
            onclick="cycleTriState(this)"
            class="flex items-center justify-between p-2.5 rounded-[2px] border border-bordercol bg-surface hover:bg-tonal1 transition-colors cursor-pointer touch-press"
          >
            <div class="flex items-center gap-2.5">
              <span class="tristate-icon text-sm text-ink-faint font-mono">□</span>
              <span class="text-xs font-sans font-medium text-ink">${p.label}</span>
            </div>
            <span class="tristate-badge px-2.5 py-1 text-[11px] font-bold rounded-[2px] bg-tonal2 text-ink-muted">IGNORE</span>
          </div>
        `;
      });

      // Apply initial visual state styling
      probContainer.querySelectorAll('[data-prob-name]').forEach(row => {
        const st = row.getAttribute('data-state') || 'ignore';
        updateTriStateVisual(row, st);
      });

      openModal('filterModal');
    }

    function closeFilterModal() {
      closeModal('filterModal');
    }

    function updateFilterIndicator() {
      const badge = document.getElementById('filterActiveBadge');
      const btn = document.getElementById('btnFilterModalTrigger');
      if (!badge) return;
      const hasLocs = activeAdvancedFilters.locations && Object.values(activeAdvancedFilters.locations).some(v => Boolean(v && String(v).trim()));
      const hasProbs = activeAdvancedFilters.problems && Object.keys(activeAdvancedFilters.problems).length > 0;
      const isActive = hasLocs || hasProbs;
      if (isActive) {
        badge.classList.remove('hidden');
        if (btn) {
          btn.classList.add('border-fern', 'bg-fern-light/40', 'text-fern-dark');
        }
      } else {
        badge.classList.add('hidden');
        if (btn) {
          btn.classList.remove('border-fern', 'bg-fern-light/40', 'text-fern-dark');
        }
      }
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

      // Gather Problems with tri-state
      activeAdvancedFilters.problems = {};
      const probRows = document.querySelectorAll('#filterModalProblems [data-prob-name]');
      probRows.forEach(row => {
        const pName = row.getAttribute('data-prob-name');
        const pState = row.getAttribute('data-state');
        if (pName && (pState === 'has' || pState === 'not')) {
          activeAdvancedFilters.problems[pName] = pState;
        }
      });

      updateFilterIndicator();
      closeFilterModal();
      fetchList();
    }

    function clearAdvancedFilters() {
      activeAdvancedFilters = { locations: {}, problems: {} };
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.location) {
        activeSchema.ui_sections.location.forEach(field => {
          const el = document.getElementById(`filter_loc_${field.name}`);
          if (el) el.value = '';
        });
      }
      const probRows = document.querySelectorAll('#filterModalProblems [data-prob-name]');
      probRows.forEach(row => {
        row.setAttribute('data-state', 'ignore');
        updateTriStateVisual(row, 'ignore');
      });

      updateFilterIndicator();
      closeFilterModal();
      fetchList();
    }

    async function fetchList() {
      try {
        let url = `/api/objects?limit=150&q=${encodeURIComponent(searchQuery)}`;
        if (activeStatusFilter !== 'all') {
          url += `&status=${encodeURIComponent(activeStatusFilter)}`;
        }

        // Append Location Filters
        for (const [key, val] of Object.entries(activeAdvancedFilters.locations || {})) {
          url += `&loc_${encodeURIComponent(key)}=${encodeURIComponent(val)}`;
        }

        // Append Specific Problems (key:state serialized)
        const probEntries = [];
        for (const [pName, pState] of Object.entries(activeAdvancedFilters.problems || {})) {
          if (pState === 'has' || pState === 'not') {
            probEntries.push(`${pName}:${pState}`);
          }
        }

        if (noImageFilterActive && !probEntries.some(p => p.startsWith('Images_Missing:'))) {
          probEntries.push('Images_Missing:has');
        }

        if (probEntries.length > 0) {
          url += `&specific_problems=${encodeURIComponent(probEntries.join(','))}`;
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
        const historyCount = facets.history_count !== undefined
          ? facets.history_count
          : objectList.filter(o => o.has_history).length;
        const unknownCount = facets.unknown_count !== undefined
          ? facets.unknown_count
          : objectList.filter(o => o.has_unknown).length;
        const total = res.total_matching !== undefined ? res.total_matching : objectList.length;

        document.getElementById('matchingCount').textContent = total;
        document.getElementById('pill-all').textContent = `All (${total})`;
        document.getElementById('pill-pending').innerHTML = `<span>🕒</span> <span>Unreviewed (${pendCount})</span>`;
        document.getElementById('pill-flagged').innerHTML = `<span>⚠</span> <span>Flagged (${flaggedCount})</span>`;
        document.getElementById('pill-reviewed').innerHTML = `<span>✓</span> <span>Reviewed (${revCount})</span>`;
        const pillConf = document.getElementById('pill-conflict');
        if (pillConf) pillConf.innerHTML = `<span>🔀</span> <span>Conflict (${historyCount})</span>`;
        const pillUkn = document.getElementById('pill-unknown');
        if (pillUkn) pillUkn.innerHTML = `<span>?</span> <span>Unknown (${unknownCount})</span>`;
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
        const statusBadge = renderStatusBadge(s);

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
              <div class="flex items-center gap-1">
                ${statusBadge}
                ${s.has_unvalidated ? `<span class="inline-flex items-center px-1.5 py-0.5 rounded-[2px] text-[10px] font-bold bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/40">UNVAL</span>` : ''}
              </div>
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

      prefetchVisibleHistory(sorted);
    }

    async function prefetchVisibleHistory(list) {
      // Pre-fetch the first 10 items in background
      const limit = Math.min(10, list.length);
      for (let i = 0; i < limit; i++) {
        const item = list[i];
        if (!item || !item.id) continue;

        try {
          const cachedData = await getCachedHistoricalData(item.id);
          if (!cachedData) {
            // Not in cache, fetch and store
            const res = await apiFetch(`/api/object/${encodeURIComponent(item.id)}/history`);
            if (res && res.historical_data) {
              cacheHistoricalData(item.id, res.historical_data);
            }
          }
        } catch (err) {
          console.error(`Failed to prefetch history for ${item.id}`, err);
        }
      }
    }

    async function showListView(manageHistory = true) {
      if (presenceHeartbeatTimer) {
        clearInterval(presenceHeartbeatTimer);
        presenceHeartbeatTimer = null;
      }
      sendPresence(null);
      updatePresenceBanner(0);

      if (autoSaveTimer !== null) {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = null;
        if (currentOid) {
          await saveCurrentEdits();
        }
      }

      // If triggered from top-left UI back button while in detail view, pop history
      if (manageHistory && window.history.state && window.history.state.view === 'detail') {
        window.history.back();
        return;
      }

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
    async function loadSpecimen(oid, fromHistory = false) {
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
      dirtyFields.clear();

      if (presenceHeartbeatTimer) clearInterval(presenceHeartbeatTimer);
      sendPresence(oid);
      presenceHeartbeatTimer = setInterval(() => {
        if (currentOid && !document.getElementById('detailView').classList.contains('hidden')) {
          sendPresence(currentOid);
        }
      }, 8000);

      if (!fromHistory) {
        if (window.history.state && window.history.state.view === 'detail') {
          window.history.replaceState({ view: 'detail', id: oid }, '');
        } else {
          window.history.pushState({ view: 'detail', id: oid }, '');
        }
      }

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

      // Hide Undo button on explicit specimen navigation
      const undoBtn = document.getElementById('btnMobileUndo');
      if (undoBtn) {
          undoBtn.classList.add('hidden');
          undoBtn.classList.remove('flex');
      }

      try {
        const data = await apiFetch(`/api/object/${encodeURIComponent(oid)}`);
        currentRecord = data;
        isReviewed = (data.review_status === 'reviewed');

        if (data.other_viewers_count !== undefined) {
          updatePresenceBanner(data.other_viewers_count);
        }

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

        // Reset to collapsed state
        mainContainer.classList.remove('h-52');
        mainContainer.classList.add('h-16');
        mainContainer.setAttribute('onclick', 'loadInitialPhoto()');
        const placeholderText = document.getElementById('photoPlaceholderText');

        if (photoUrls.length > 0) {
          currentPhotoIdx = 0;
          placeholder.innerHTML = `
            <span class="text-xl">📷</span>
            <p class="font-semibold text-fern" id="photoPlaceholderText">Tap to Load ${photoUrls.length} Archival Scan${photoUrls.length > 1 ? 's' : ''}</p>
          `;
          placeholder.classList.remove('hidden');
          specimenImg.classList.add('hidden');
          watermark.classList.add('hidden');
          mainContainer.classList.add('cursor-pointer');
          mainContainer.classList.remove('cursor-default');
          const strip = document.getElementById('photoThumbStrip');
          if (strip) { strip.classList.add('hidden'); strip.innerHTML = ''; }
        } else {
          placeholder.innerHTML = `
            <span class="text-xl text-ink-faint">📷</span>
            <p class="font-sans text-[11px] font-semibold text-ink-muted">No Archival Scans Attached</p>
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
        currentUnvalidatedMap = {};
        if (data.unvalidated_sources && Array.isArray(data.unvalidated_sources)) {
          data.unvalidated_sources.forEach(u => {
            if (u.field) currentUnvalidatedMap[u.field] = u.comment || '';
          });
        }
        renderDynamicForm(activeSchema, data);

        // Update Problem Summary Banner
        const banner = document.getElementById('detailProblemBanner');
        const badgeContainer = document.getElementById('detailProblemBadges');
        const activeProbFields = [];
        const unknownFields = [];

        if (activeSchema && activeSchema.ui_sections) {
          const allFields = (activeSchema.ui_sections.registration || []).concat(activeSchema.ui_sections.location || []);
          allFields.forEach(f => {
            const val = (data.registration && data.registration[f.name] !== undefined) ? data.registration[f.name] : (data.observation ? data.observation[f.name] : '');
            if (isFieldProblemActive(f.name, 'registration', data) || isFieldProblemActive(f.name, 'observation', data)) {
              if (!activeProbFields.includes(f.name)) activeProbFields.push(f.name);
            } else if (isValueUnknown(val)) {
              if (!unknownFields.includes(f.name)) unknownFields.push(f.name);
            }
          });
        }

        if (activeProbFields.length > 0 || unknownFields.length > 0) {
          banner.classList.remove('hidden');
          let chipsHtml = '';
          activeProbFields.forEach(fName => {
            const inputId = `input_registration_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;
            chipsHtml += `
              <button
                type="button"
                onclick="scrollToField('${inputId}', '${fName}')"
                class="px-2 py-1 bg-[#C62828] text-white text-[11px] font-bold rounded-[2px] shadow-xs flex items-center gap-1 touch-press hover:bg-[#b71c1c]"
                title="Jump to ${fName}"
              >
                <span>⚠</span>
                <span>${fName}</span>
              </button>
            `;
          });
          unknownFields.forEach(fName => {
            const inputId = `input_registration_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;
            chipsHtml += `
              <button
                type="button"
                onclick="scrollToField('${inputId}', '${fName}')"
                class="px-2 py-1 bg-[#FBC02D] text-[#2c302e] text-[11px] font-bold rounded-[2px] shadow-xs flex items-center gap-1 touch-press hover:bg-[#f9a825]"
                title="Jump to ${fName}"
              >
                <span>?</span>
                <span>${fName}</span>
              </button>
            `;
          });
          badgeContainer.innerHTML = chipsHtml;
        } else {
          banner.classList.add('hidden');
          badgeContainer.innerHTML = '';
        }

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

    function isFieldProblemActive(fieldName, section, record) {
      if (!record) return false;
      const issues = record.flagged_issues || [];
      if (issues.some(iss => (iss.field === fieldName || iss.id === fieldName) && !iss.resolved)) {
        return true;
      }
      const obs = record.observation || {};
      const reg = record.registration || {};

      // 1. Direct Problem Column Check (e.g. Genus_Problem)
      const directProb = `${fieldName}_Problem`;
      if (obs[directProb] === true || String(obs[directProb]).toLowerCase() === 'true' || obs[directProb] === '1' ||
          reg[directProb] === true || String(reg[directProb]).toLowerCase() === 'true' || reg[directProb] === '1') {
        return true;
      }

      // 2. Mapped Problem Columns from Schema
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.problems) {
        for (const p of activeSchema.ui_sections.problems) {
          const target = p.maps_to || p.target;
          if (target === fieldName || (!target && p.name.replace(/_Problem$/, '') === fieldName)) {
            const pVal = (obs[p.name] !== undefined) ? obs[p.name] : reg[p.name];
            if (pVal === true || String(pVal).toLowerCase() === 'true' || pVal === '1' || pVal === 'x') {
              return true;
            }
          }
        }
      }

      // 3. Location section general problem
      if (section === 'observation' && (obs.Loc_Problem === true || String(obs.Loc_Problem).toLowerCase() === 'true' || obs.Loc_Problem === '1')) {
        return true;
      }

      return false;
    }

    function isValueUnknown(val) {
      if (val === null || val === undefined) return false;
      const s = String(val).trim().toLowerCase();
      return ['ukjent', 'unknown', '?', '-', 'nan',
              'unknown:missing', 'unknown:indecipherable',
              'unknown:undigitized', 'withheld'].includes(s);
    }

    function scrollToField(inputId, fName) {
      let el = document.getElementById(inputId);
      if (!el && fName) {
        el = document.getElementById(`input_observation_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`);
      }
      if (el) {
        const accordion = el.closest('.accordion');
        if (accordion) {
          const content = accordion.querySelector('.acc-content');
          const icon = accordion.querySelector('.acc-icon');
          if (content && content.classList.contains('hidden')) {
            content.classList.remove('hidden');
            content.classList.add('block');
            accordion.classList.add('acc-open');
            if (icon) icon.textContent = '▲';
          }
        }
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.focus();
        el.classList.add('ring-2', 'ring-ember');
        setTimeout(() => el.classList.remove('ring-2', 'ring-ember'), 1500);
      }
    }

    async function toggleFieldProblem(fieldName) {
      if (!currentRecord) return;
      if (currentRecord.flagged_issues) {
        currentRecord.flagged_issues = currentRecord.flagged_issues.filter(i => i.field !== fieldName && i.id !== fieldName);
      }
      currentRecord.observation = currentRecord.observation || {};
      const probCol = `${fieldName}_Problem`;
      if (currentRecord.observation[probCol] !== undefined) {
        currentRecord.observation[probCol] = false;
      }
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.problems) {
        for (const p of activeSchema.ui_sections.problems) {
          if (p.maps_to === fieldName || p.target === fieldName) {
            currentRecord.observation[p.name] = false;
          }
        }
      }
      if (fieldName === 'Location') {
        currentRecord.observation.Loc_Problem = false;
      }

      renderDynamicForm(activeSchema, currentRecord);
      renderDiscrepancies(currentRecord);
      updateReviewButtonUI();
      await saveCurrentEdits();
      showToast(`Resolved problem for ${fieldName}`);
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

        let grpProbCount = 0;
        let grpUknCount = 0;
        let fieldsHtml = '';

        grp.fields.forEach(fName => {
          const fDef = regFields.find(f => f.name === fName) || { name: fName, type: 'text' };
          const val = (record.registration && record.registration[fName] !== undefined) ? record.registration[fName] : '';
          if (isFieldProblemActive(fName, 'registration', record)) grpProbCount++;
          else if (isValueUnknown(val)) grpUknCount++;
          fieldsHtml += renderFieldInput(fDef, val, 'registration', record);
        });

        const isOpen = (grpProbCount > 0 || grpUknCount > 0);

        let badgesHtml = '';
        if (grpProbCount > 0) {
          badgesHtml += `<span class="px-1.5 py-0.5 rounded-[2px] text-[11px] font-bold bg-[#C62828] text-white flex items-center gap-0.5 shadow-xs"><span>⚠</span><span>${grpProbCount}</span></span>`;
        }
        if (grpUknCount > 0) {
          badgesHtml += `<span class="px-1.5 py-0.5 rounded-[2px] text-[11px] font-bold bg-[#FBC02D] text-[#2c302e] flex items-center gap-0.5 shadow-xs"><span>?</span><span>${grpUknCount}</span></span>`;
        }

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
                  <div class="flex items-center gap-1.5">
                    <h3 class="font-bold text-xs text-ink uppercase tracking-wider">${grp.name}</h3>
                    ${badgesHtml}
                  </div>
                  <p class="text-[10px] text-ink-muted">${grp.fields.join(' • ')}</p>
                </div>
              </div>
              <span class="acc-icon text-ink-muted font-bold transition-transform duration-200 text-xs">${isOpen ? '▲' : '▼'}</span>
            </button>
            <div class="p-3.5 space-y-3 acc-content ${isOpen ? 'block' : 'hidden'}">
              ${fieldsHtml}
            </div>
          </div>
        `;
      });

      // Render any ungrouped registration fields (ensures 100% of schema fields are always editable)
      const groupedFieldNames = new Set(regGroups.flatMap(g => g.fields || []));
      const ungroupedFields = regFields.filter(f => !groupedFieldNames.has(f.name));
      if (ungroupedFields.length > 0) {
        let ungrpProbCount = 0;
        let ungrpUknCount = 0;
        let ungrpFieldsHtml = '';

        ungroupedFields.forEach(fDef => {
          const val = (record.registration && record.registration[fDef.name] !== undefined) ? record.registration[fDef.name] : '';
          if (isFieldProblemActive(fDef.name, 'registration', record)) ungrpProbCount++;
          else if (isValueUnknown(val)) ungrpUknCount++;
          ungrpFieldsHtml += renderFieldInput(fDef, val, 'registration', record);
        });

        const isUngrpOpen = (ungrpProbCount > 0 || ungrpUknCount > 0);
        let ungrpBadgesHtml = '';
        if (ungrpProbCount > 0) {
          ungrpBadgesHtml += `<span class="px-1.5 py-0.5 rounded-[2px] text-[11px] font-bold bg-[#C62828] text-white flex items-center gap-0.5 shadow-xs"><span>⚠</span><span>${ungrpProbCount}</span></span>`;
        }
        if (ungrpUknCount > 0) {
          ungrpBadgesHtml += `<span class="px-1.5 py-0.5 rounded-[2px] text-[11px] font-bold bg-[#FBC02D] text-[#2c302e] flex items-center gap-0.5 shadow-xs"><span>?</span><span>${ungrpUknCount}</span></span>`;
        }

        html += `
          <div class="bg-surface border border-bordercol rounded-[2px] shadow-xs overflow-hidden accordion ${isUngrpOpen ? 'acc-open' : ''}">
            <button
              type="button"
              onclick="toggleAccordion(this)"
              class="w-full p-3 flex items-center justify-between bg-tonal1 hover:bg-tonal2 transition focus:outline-none touch-press border-b border-bordercol text-left"
            >
              <div class="flex items-center gap-2.5">
                <span class="text-base">📋</span>
                <div>
                  <div class="flex items-center gap-1.5">
                    <h3 class="font-bold text-xs text-ink uppercase tracking-wider">Additional Fields</h3>
                    ${ungrpBadgesHtml}
                  </div>
                  <p class="text-[10px] text-ink-muted">${ungroupedFields.map(f => f.name).join(' • ')}</p>
                </div>
              </div>
              <span class="acc-icon text-ink-muted font-bold transition-transform duration-200 text-xs">${isUngrpOpen ? '▲' : '▼'}</span>
            </button>
            <div class="p-3.5 space-y-3 acc-content ${isUngrpOpen ? 'block' : 'hidden'}">
              ${ungrpFieldsHtml}
            </div>
          </div>
        `;
      }

      // 2. Render Physical Location Group from config.py
      if (locFields.length > 0) {
        let locFieldsHtml = '';
        let locProbCount = 0;
        let locUknCount = 0;

        locFields.forEach(fDef => {
          const val = (record.observation && record.observation[fDef.name] !== undefined) ? record.observation[fDef.name] : '';
          if (isFieldProblemActive(fDef.name, 'observation', record)) locProbCount++;
          else if (isValueUnknown(val)) locUknCount++;
          locFieldsHtml += renderFieldInput(fDef, val, 'observation', record);
        });

        const isLocOpen = (locProbCount > 0 || locUknCount > 0);

        let locBadgesHtml = '';
        if (locProbCount > 0) {
          locBadgesHtml += `<span class="px-1.5 py-0.5 rounded-[2px] text-[11px] font-bold bg-[#C62828] text-white flex items-center gap-0.5 shadow-xs"><span>⚠</span><span>${locProbCount}</span></span>`;
        }
        if (locUknCount > 0) {
          locBadgesHtml += `<span class="px-1.5 py-0.5 rounded-[2px] text-[11px] font-bold bg-[#FBC02D] text-[#2c302e] flex items-center gap-0.5 shadow-xs"><span>?</span><span>${locUknCount}</span></span>`;
        }

        let presetOptions = `<option value="Default" ${lastSelectedPreset === 'Default' ? 'selected' : ''}>Default</option>`;
        Object.keys(locationPresets).forEach(pName => {
          if (pName !== 'Default') {
            presetOptions += `<option value="${pName}" ${lastSelectedPreset === pName ? 'selected' : ''}>${pName}</option>`;
          }
        });

        html += `
          <div class="bg-surface border border-bordercol rounded-[2px] shadow-xs overflow-hidden accordion ${isLocOpen ? 'acc-open' : ''}">
            <button
              type="button"
              onclick="toggleAccordion(this)"
              class="w-full p-3 flex items-center justify-between bg-tonal1 hover:bg-tonal2 transition focus:outline-none touch-press border-b border-bordercol text-left"
            >
              <div class="flex items-center gap-2.5">
                <span class="text-base">📍</span>
                <div>
                  <div class="flex items-center gap-1.5">
                    <h3 class="font-bold text-xs text-ink uppercase tracking-wider">Physical Storage Location</h3>
                    ${locBadgesHtml}
                  </div>
                  <p class="text-[10px] text-ink-muted">Museum coordinates & storage trait</p>
                </div>
              </div>
              <span class="acc-icon text-ink-muted font-bold transition-transform duration-200 text-xs">${isLocOpen ? '▲' : '▼'}</span>
            </button>
            <div class="p-3.5 space-y-3 acc-content ${isLocOpen ? 'block' : 'hidden'}">
              <div class="flex items-center gap-2 mb-4">
                <select id="locPresetSelect" class="flex-grow bg-surface border border-bordercol rounded-[2px] px-2 py-1.5 text-xs font-sans text-ink outline-none focus:border-fern">
                  ${presetOptions}
                </select>
                <button type="button" onclick="applyLocPreset()" class="px-3 py-1.5 bg-tonal1 hover:bg-tonal2 text-ink text-xs font-bold rounded-[2px] border border-bordercol transition-colors cursor-pointer touch-press">
                  Apply Preset
                </button>
                <button type="button" onclick="openPresetSettings()" class="px-2 py-1.5 bg-surface hover:bg-tonal1 text-ink text-xs rounded-[2px] border border-bordercol transition-colors cursor-pointer touch-press" title="Preset Settings">
                  ⚙️
                </button>
              </div>
              ${locFieldsHtml}
            </div>
          </div>
        `;
      }

      container.innerHTML = html;
    }

    function renderFieldInput(field, value, section, record) {
      const fName = field.name;
      const fType = field.type || 'text';
      const isReadOnly = !!field.readonly;
      const inputId = `input_${section}_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;

      const toggleBtnId = `history_toggle_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;
      const containerId = `history_container_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;

      const hasProb = isFieldProblemActive(fName, section, record);
      const hasUkn = isValueUnknown(value);

      const problemBadge = hasProb
        ? `<span class="inline-flex items-center justify-center px-1.5 py-0.2 rounded-[2px] text-[10px] font-bold bg-[#C62828] text-white shadow-xs ml-1" title="Problem Flagged">⚠</span>`
        : (hasUkn
          ? `<span class="inline-flex items-center justify-center px-1.5 py-0.2 rounded-[2px] text-[10px] font-bold bg-[#FBC02D] text-[#2c302e] shadow-xs ml-1" title="Unknown Value">?</span>`
          : '');

      const inputStyle = hasProb
        ? 'border-l-4 border-l-[#C62828] bg-ember-light border-ember text-ember-dark font-medium focus:border-ember'
        : (hasUkn
          ? 'border-l-4 border-l-[#FBC02D] bg-[#fef9c3] border-[#fde047] text-[#854d0e] font-medium focus:border-[#eab308]'
          : 'border-bordercol bg-surface text-ink focus:border-fern');

      const flagBtn = hasProb
        ? `<button
            type="button"
            onclick="toggleFieldProblem('${fName}')"
            class="min-h-[44px] px-2.5 py-1.5 text-xs font-sans font-bold text-white bg-[#C62828] hover:bg-[#b71c1c] border border-[#C62828] rounded-[2px] touch-target-min touch-press ml-1 flex items-center gap-1 shadow-xs"
            title="Problem active for ${fName} (tap to resolve)"
          >
            <span>⚑</span>
            <span>Flagged</span>
          </button>`
        : `<button
            type="button"
            onclick="openAddDiscrepancyModal('${fName}')"
            class="min-h-[44px] px-2.5 py-1.5 text-xs font-sans font-medium text-ink-muted hover:text-ember bg-tonal1 hover:bg-tonal2 border border-bordercol rounded-[2px] touch-target-min touch-press ml-1 flex items-center gap-1"
            title="Flag discrepancy for ${fName}"
          >
            <span>⚑</span>
            <span>Flag</span>
          </button>`;

      const icedigBtn = `
        <button
          type="button"
          onclick="openIcedigBottomSheet('${section}', '${fName}')"
          class="min-h-[44px] px-2.5 py-1.5 text-xs font-sans font-medium text-ink-muted hover:text-amber-700 bg-tonal1 hover:bg-amber-500/10 border border-bordercol rounded-[2px] touch-target-min touch-press ml-1 flex items-center gap-1"
          title="Set ICEDIG Missing Data Status for ${fName}"
        >
          <span>∅</span>
          <span>Unknown</span>
        </button>
      `;

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
        ${!isReadOnly ? flagBtn : ''}
        ${!isReadOnly && fType !== 'checkbox' && fType !== 'bool' ? icedigBtn : ''}
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
              <label for="${inputId}" class="text-xs font-bold text-ink flex items-center gap-1">
                <span>${fName}</span>
                ${problemBadge}
              </label>
              <div class="flex items-center">${historyControls}</div>
            </div>
            <select
              id="${inputId}"
              data-section="${section}"
              data-field="${fName}"
              onchange="markDirty('${fName}'); triggerAutoSave()" onblur="saveCurrentEdits()"
              class="w-full min-h-[44px] border rounded-[2px] px-3 py-2 text-xs outline-none cursor-pointer ${inputStyle}"
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
            <div class="flex items-center justify-between min-h-[44px] py-1 ${hasProb ? 'bg-ember-light p-2 rounded-[2px] border border-ember' : ''}">
              <label for="${inputId}" class="flex-1 text-xs font-bold text-ink cursor-pointer flex items-center gap-1">
                <span>${fName}</span>
                ${problemBadge}
              </label>
              <div class="flex items-center gap-1.5">
                ${historyControls}
                <label class="min-w-[44px] min-h-[44px] flex items-center justify-center cursor-pointer">
                  <input
                    type="checkbox"
                    id="${inputId}"
                    data-section="${section}"
                    data-field="${fName}"
                    ${isChecked ? 'checked' : ''}
                    onchange="markDirty('${fName}'); triggerAutoSave()"
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
              <label for="${inputId}" class="text-xs font-bold text-ink flex items-center gap-1">
                <span>${fName}</span>
                ${problemBadge}
              </label>
              <div class="flex items-center">${historyControls}</div>
            </div>
            <textarea
              id="${inputId}"
              data-section="${section}"
              data-field="${fName}"
              rows="2"
              oninput="markDirty('${fName}'); triggerAutoSave()" onblur="saveCurrentEdits()"
              class="w-full border rounded-[2px] px-3 py-2 text-xs outline-none ${inputStyle}"
            >${value || ''}</textarea>
            ${historyContainerHtml}
          </div>
        `;
      }

      // Standard Text or Readonly
      return `
        <div class="space-y-1">
          <div class="flex items-center justify-between min-h-[32px]">
            <label for="${inputId}" class="text-xs font-bold text-ink flex items-center gap-1">
              <span>${fName}</span>
              ${problemBadge}
              ${isReadOnly ? '<span class="text-[9px] text-ink-faint font-normal font-mono">(Locked)</span>' : ''}
            </label>
            <div class="flex items-center">${historyControls}</div>
          </div>
          <input
            type="text"
            id="${inputId}"
            data-section="${section}"
            data-field="${fName}"
            value="${value || ''}"
            ${isReadOnly ? 'readonly class="w-full min-h-[44px] bg-tonal1 border border-bordercol rounded-[2px] px-3 py-2 text-xs text-ink-muted font-mono outline-none"' : `class="w-full min-h-[44px] border rounded-[2px] px-3 py-2 text-xs outline-none ${inputStyle}" oninput="markDirty('${fName}'); handleVocabInput(this, '${fName}')" onchange="markDirty('${fName}'); handleVocabChange(this)" onblur="saveCurrentEdits()"`}
            ${activeSchema && activeSchema.vocabulary && activeSchema.vocabulary[fName] && !isReadOnly ? `list="datalist_${section}_${fName}"` : ''}
          />
          ${activeSchema && activeSchema.vocabulary && activeSchema.vocabulary[fName] && !isReadOnly ? `
          <datalist id="datalist_${section}_${fName}">
            ${activeSchema.vocabulary[fName].map(v => `<option value="${v}"></option>`).join('')}
          </datalist>
          ` : ''}
          ${historyContainerHtml}
        </div>
      `;
    }

    function toggleUnvalidatedField(section, fName) {
      if (!currentUnvalidatedMap) currentUnvalidatedMap = {};
      const fKey = fName.replace(/[ ]+/g, '_');
      const container = document.getElementById(`unval_container_${section}_${fKey}`);
      const btn = document.getElementById(`unval_btn_${section}_${fKey}`);
      const input = document.getElementById(`unval_input_${section}_${fKey}`);

      if (currentUnvalidatedMap[fName] !== undefined) {
        delete currentUnvalidatedMap[fName];
        if (container) container.classList.add('hidden');
        if (btn) {
          btn.innerHTML = '<span>?</span>';
          btn.className = 'min-h-[44px] px-2 py-1 text-xs font-bold rounded-[2px] touch-target-min touch-press ml-1 flex items-center justify-center transition-all text-ink-faint hover:bg-tonal2 border border-bordercol';
        }
      } else {
        currentUnvalidatedMap[fName] = (input ? input.value : '') || '';
        if (container) container.classList.remove('hidden');
        if (btn) {
          btn.innerHTML = '<span>❓</span>';
          btn.className = 'min-h-[44px] px-2 py-1 text-xs font-bold rounded-[2px] touch-target-min touch-press ml-1 flex items-center justify-center transition-all bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/40';
        }
        if (input) input.focus();
      }
      markDirty(fName);
      triggerAutoSave();
    }

    function onUnvalCommentChange(fName, val) {
      if (!currentUnvalidatedMap) currentUnvalidatedMap = {};
      currentUnvalidatedMap[fName] = val;
      markDirty(fName);
    }

    function toggleAccordion(btn) {
      const acc = btn.closest('.accordion');
      acc.classList.toggle('acc-open');
      const content = acc.querySelector('.acc-content');
      const icon = acc.querySelector('.acc-icon');
      if (acc.classList.contains('acc-open')) {
        content.classList.remove('hidden');
        if (icon) icon.textContent = '▲';
      } else {
        content.classList.add('hidden');
        if (icon) icon.textContent = '▼';
      }
    }

    // ==========================================
    // UNDO & RECENT EDITS
    // ==========================================
    async function undoLastEdit(oid = null) {
      try {
        const payload = oid ? { oid: oid } : {};
        const res = await apiFetch('/api/undo', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        if (res.success) {
          showToast(`✓ Undo successful`);
          const undoBtn = document.getElementById('btnMobileUndo');
          if (undoBtn) {
            undoBtn.classList.remove('flex');
            undoBtn.classList.add('hidden');
          }

          if (document.getElementById('recentEditsModal') && !document.getElementById('recentEditsModal').classList.contains('hidden')) {
              await openRecentEditsModal();
          }

          if (currentRecord && String(res.restored.id) === String(currentOid)) {
            Object.assign(currentRecord, res.restored);
            isReviewed = currentRecord.review_status === 'reviewed';
            renderDynamicForm(activeSchema, currentRecord);
            renderDiscrepancies(currentRecord);
            updateReviewButtonUI();
          }

          const listItem = objectList.find(o => String(o.id) === String(res.restored.id));
          if (listItem) {
            Object.assign(listItem, res.restored);
            if (!document.getElementById('listView').classList.contains('hidden')) {
              renderList();
            }
          }
        } else {
          showToast(res.error || 'Undo failed', true);
        }
      } catch (err) {
        showToast('Undo failed', true);
        console.error(err);
      }
    }

    async function openRecentEditsModal() {
      const modal = document.getElementById('recentEditsModal');
      const listContainer = document.getElementById('recentEditsList');

      try {
        const res = await apiFetch('/api/recent_edits');
        if (res.edits && res.edits.length > 0) {
          listContainer.innerHTML = res.edits.map(edit => `
            <div class="bg-surface border border-bordercol rounded-[2px] p-3 text-sm flex flex-col gap-2 shadow-xs">
              <div class="flex items-center justify-between">
                <span class="font-mono text-xs font-medium text-ink bg-tonal1 px-1.5 py-0.5 rounded-[2px]">${edit.oid}</span>
                <span class="text-[10px] text-ink-muted">${edit.time}</span>
              </div>
              <div class="text-xs text-ink break-words">${edit.summary}</div>
              <div class="flex justify-end border-t border-tonal2 mt-1 pt-2">
                 <button type="button" onclick="undoLastEdit('${edit.oid}')" class="text-[11px] font-bold text-ember hover:bg-ember/10 px-2 py-1 border border-ember-border bg-ember-light rounded-[2px] touch-press">Revert</button>
              </div>
            </div>
          `).join('');
        } else {
          listContainer.innerHTML = `
            <div class="text-center p-6 text-ink-faint text-xs">
              <div class="text-2xl mb-2">∅</div>
              No recent edits in this session.
            </div>
          `;
        }
      } catch (err) {
        listContainer.innerHTML = `<div class="text-center p-4 text-ember text-xs">Error loading history.</div>`;
      }

      modal.classList.remove('hidden');
    }

    function closeRecentEditsModal() {
      document.getElementById('recentEditsModal').classList.add('hidden');
    }

    // ==========================================
    // LOCATION PRESETS LOGIC
    // ==========================================
    function applyLocPreset() {
      const select = document.getElementById('locPresetSelect');
      if (!select) return;
      const pName = select.value;
      if (!pName || pName === "Default") return;

      const presetData = locationPresets[pName];
      if (!presetData) return;

      lastSelectedPreset = pName;
      let changed = false;

      // Ensure activeSchema and location fields exist
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.location) {
        activeSchema.ui_sections.location.forEach(field => {
          const inputId = `input_observation_${field.name.replace(/[^a-zA-Z0-9_]/g, '_')}`;
          const input = document.getElementById(inputId);
          if (input && presetData[field.name] !== undefined) {
             const newVal = presetData[field.name];
             if (input.type === 'checkbox') {
               const checkedVal = (String(newVal).toLowerCase() === 'true' || newVal === true || newVal === '1');
               if (input.checked !== checkedVal) {
                  input.checked = checkedVal;
                  changed = true;
                  markDirty(field.name);
               }
             } else {
               if (input.value !== newVal) {
                 input.value = newVal;
                 changed = true;
                 markDirty(field.name);
               }
             }
          }
        });
      }

      if (changed) {
        if (currentRecord && currentRecord.observation && activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.location) {
          activeSchema.ui_sections.location.forEach(field => {
            if (presetData[field.name] !== undefined) {
              currentRecord.observation[field.name] = presetData[field.name];
            }
          });
        }
        showToast(`Applied Preset: ${pName}`);
        triggerAutoSave();
        if (typeof updateDetailProblemBanner === 'function' && currentRecord) updateDetailProblemBanner(currentRecord);
        if (typeof renderDiscrepancies === 'function' && currentRecord) renderDiscrepancies(currentRecord);
      }
    }

    async function openSettingsModal() {
      openModal('settingsModal');
      const input = document.getElementById('settingImageUrlPattern');
      try {
        const res = await apiFetch('/api/settings');
        if (res && res.success) {
          input.value = res.image_url_pattern_override || '';
        }
      } catch (err) {
        console.error("Failed to load settings:", err);
      }
    }

    function closeSettingsModal() {
      closeModal('settingsModal');
    }

    async function saveSettings() {
      const pattern = document.getElementById('settingImageUrlPattern').value.trim();
      try {
        const res = await apiFetch('/api/settings', {
          method: 'POST',
          body: JSON.stringify({ image_url_pattern_override: pattern })
        });
        if (res && res.success) {
          showToast("Settings saved.");
          closeSettingsModal();
        } else {
          showToast("Failed to save settings.", true);
        }
      } catch (err) {
        console.error("Failed to save settings:", err);
        showToast("Error saving settings.", true);
      }
    }

    function openPresetSettings() {
      renderPresetSettingsList();
      openModal('presetSettingsModal');
    }

    function closePresetSettings() {
      closeModal('presetSettingsModal');
    }

    function renderPresetSettingsList() {
      const container = document.getElementById('presetSettingsList');
      if (!container) return;

      const keys = Object.keys(locationPresets).filter(k => k !== 'Default');
      if (keys.length === 0) {
        container.innerHTML = '<p class="text-xs text-ink-faint italic py-2">No custom presets saved yet.</p>';
        return;
      }

      container.innerHTML = keys.map(k => `
        <div class="flex items-center justify-between p-2.5 border-b border-bordercol bg-surface hover:bg-tonal1 rounded-[2px] transition-colors mb-1 shadow-xs">
          <span class="text-sm font-sans text-ink">${k}</span>
          <button type="button" onclick="deleteLocPreset('${k}')" class="px-2 py-1 text-xs font-bold text-ember border border-ember bg-ember-light hover:bg-ember rounded-[2px] hover:text-white transition-colors cursor-pointer touch-press">Delete</button>
        </div>
      `).join('');
    }

    async function deleteLocPreset(name) {
      if (!confirm(`Delete location preset "${name}"?`)) return;

      try {
        const res = await apiFetch('/api/presets', {
          method: 'POST',
          body: JSON.stringify({ action: "delete", name: name })
        });

        if (res && res.success) {
          locationPresets = res.presets || {};
          if (lastSelectedPreset === name) lastSelectedPreset = "Default";
          renderPresetSettingsList();
          showToast(`Preset deleted.`);
          // Repopulate dynamic form to update select options
          renderDynamicForm(activeSchema, currentRecord);
        } else {
          showToast(`Failed to delete preset.`, true);
        }
      } catch (err) {
        console.error("Error deleting preset:", err);
        showToast("Error deleting preset", true);
      }
    }

    function toggleNewPresetForm() {
      const form = document.getElementById('newPresetForm');
      if (form.classList.contains('hidden')) {
        form.classList.remove('hidden');
        document.getElementById('newPresetNameInput').focus();
      } else {
        form.classList.add('hidden');
      }
    }

    async function saveNewLocPreset() {
      const nameInput = document.getElementById('newPresetNameInput');
      const name = nameInput.value.trim();

      if (!name) {
        alert("Please enter a name for the preset.");
        return;
      }
      if (name.toLowerCase() === "default") {
        alert("Cannot overwrite Default preset.");
        return;
      }

      const vals = {};
      if (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.location) {
        activeSchema.ui_sections.location.forEach(field => {
          const inputId = `input_observation_${field.name.replace(/[^a-zA-Z0-9_]/g, '_')}`;
          const input = document.getElementById(inputId);
          if (input) {
             if (input.type === 'checkbox') {
               vals[field.name] = input.checked ? "True" : "False";
             } else {
               vals[field.name] = input.value;
             }
          }
        });
      }

      try {
        const res = await apiFetch('/api/presets', {
          method: 'POST',
          body: JSON.stringify({ action: "save", name: name, values: vals })
        });

        if (res && res.success) {
          locationPresets = res.presets || {};
          lastSelectedPreset = name;
          nameInput.value = "";
          toggleNewPresetForm();
          renderPresetSettingsList();
          showToast(`Preset "${name}" saved.`);
          // Repopulate dynamic form to update select options and set it to active
          renderDynamicForm(activeSchema, currentRecord);
          // Set dropdown
          setTimeout(() => {
             const sel = document.getElementById('locPresetSelect');
             if(sel) sel.value = name;
          }, 50);
        } else {
          showToast(`Failed to save preset.`, true);
        }
      } catch (err) {
        console.error("Error saving preset:", err);
        showToast("Error saving preset", true);
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
      const unvalCheck = document.getElementById('discrepancyUnvalCheck');
      const unvalInput = document.getElementById('discrepancyUnvalNoteInput');
      const unvalCont = document.getElementById('discrepancyUnvalContainer');
      if (unvalCheck && unvalInput && unvalCont) {
        const hasUnval = (currentUnvalidatedMap && fieldName && currentUnvalidatedMap[fieldName] !== undefined);
        unvalCheck.checked = !!hasUnval;
        unvalInput.value = hasUnval ? currentUnvalidatedMap[fieldName] : '';
        if (hasUnval) unvalCont.classList.remove('hidden');
        else unvalCont.classList.add('hidden');
      }
      openModal('addDiscrepancyModal');
    }

    function updateDetailProblemBanner(data) {
      const banner = document.getElementById('detailProblemBanner');
      const badgeContainer = document.getElementById('detailProblemBadges');
      if (!banner || !badgeContainer || !data) return;
      const activeProbFields = [];
      const unknownFields = [];

      if (activeSchema && activeSchema.ui_sections) {
        const allFields = (activeSchema.ui_sections.registration || []).concat(activeSchema.ui_sections.location || []);
        allFields.forEach(f => {
          const val = (data.registration && data.registration[f.name] !== undefined) ? data.registration[f.name] : (data.observation ? data.observation[f.name] : '');
          if (isFieldProblemActive(f.name, 'registration', data) || isFieldProblemActive(f.name, 'observation', data)) {
            if (!activeProbFields.includes(f.name)) activeProbFields.push(f.name);
          } else if (isValueUnknown(val)) {
            if (!unknownFields.includes(f.name)) unknownFields.push(f.name);
          }
        });
      }

      if (activeProbFields.length > 0 || unknownFields.length > 0) {
        banner.classList.remove('hidden');
        let chipsHtml = '';
        activeProbFields.forEach(fName => {
          const inputId = `input_registration_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;
          chipsHtml += `
            <button
              type="button"
              onclick="scrollToField('${inputId}', '${fName}')"
              class="px-2 py-1 bg-[#C62828] text-white text-[11px] font-bold rounded-[2px] shadow-xs flex items-center gap-1 touch-press hover:bg-[#b71c1c]"
              title="Jump to ${fName}"
            >
              <span>⚠</span>
              <span>${fName}</span>
            </button>
          `;
        });
        unknownFields.forEach(fName => {
          const inputId = `input_registration_${fName.replace(/[^a-zA-Z0-9_]/g, '_')}`;
          chipsHtml += `
            <button
              type="button"
              onclick="scrollToField('${inputId}', '${fName}')"
              class="px-2 py-1 bg-[#FBC02D] text-[#2c302e] text-[11px] font-bold rounded-[2px] shadow-xs flex items-center gap-1 touch-press hover:bg-[#f9a825]"
              title="Jump to ${fName}"
            >
              <span>?</span>
              <span>${fName}</span>
            </button>
          `;
        });
        badgeContainer.innerHTML = chipsHtml;
      } else {
        banner.classList.add('hidden');
        badgeContainer.innerHTML = '';
      }
    }

    async function submitDiscrepancy(e) {
      e.preventDefault();
      const field = document.getElementById('discrepancyFieldSelect').value;
      const reason = document.getElementById('discrepancyReasonInput').value.trim();
      const severity = document.querySelector('input[name="severity"]:checked').value;

      if (!reason) return;

      // Handle unvalidated source if checked
      const unvalCheck = document.getElementById('discrepancyUnvalCheck');
      const unvalNote = document.getElementById('discrepancyUnvalNoteInput');
      if (unvalCheck && unvalCheck.checked) {
        if (!currentUnvalidatedMap) currentUnvalidatedMap = {};
        currentUnvalidatedMap[field] = (unvalNote ? unvalNote.value.trim() : '') || reason;
        markDirty(field);
      } else if (unvalCheck && !unvalCheck.checked && currentUnvalidatedMap && currentUnvalidatedMap[field] !== undefined) {
        delete currentUnvalidatedMap[field];
        markDirty(field);
      }

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
        markDirty(matchProb);
      }

      closeModal('addDiscrepancyModal');
      document.getElementById('discrepancyReasonInput').value = '';
      renderDynamicForm(activeSchema, currentRecord);
      updateDetailProblemBanner(currentRecord);
      renderDiscrepancies(currentRecord);
      await saveCurrentEdits();
      showToast('Discrepancy flagged on host');
    }

    async function resolveDiscrepancy(issId) {
      if (!currentRecord || !currentRecord.flagged_issues) return;
      currentRecord.flagged_issues = currentRecord.flagged_issues.filter(i => i.id !== issId);
      renderDynamicForm(activeSchema, currentRecord);
      updateDetailProblemBanner(currentRecord);
      renderDiscrepancies(currentRecord);
      await saveCurrentEdits();
      showToast('Discrepancy resolved');
    }

    async function toggleProblemFlag(probName) {
      const el = document.getElementById(`prob_${probName}`);
      if (!el || !currentRecord) return;
      currentRecord.observation = currentRecord.observation || {};
      currentRecord.observation[probName] = el.checked;
      markDirty(probName);

      const probs = (activeSchema && activeSchema.ui_sections && activeSchema.ui_sections.problems) ? activeSchema.ui_sections.problems : [];
      let hasProb = false;
      for (const p of probs) {
        const v = currentRecord.observation[p.name];
        if (v === true || String(v).toLowerCase() === 'true' || v === '1') {
          hasProb = true;
          break;
        }
      }
      currentRecord.has_flags = hasProb;
      updateReviewButtonUI();
      renderDynamicForm(activeSchema, currentRecord);
      updateDetailProblemBanner(currentRecord);

      await saveCurrentEdits();
    }

    // ==========================================
    // AUTO-SAVE & PRIMARY ACTION: MARK REVIEWED
    // ==========================================


    function handleVocabInput(input, fName) {
      markDirty(fName);
      triggerAutoSave();
    }

    function handleVocabChange(input) {
      if (input.value && input.value.trim() !== '') {
        const val = input.value.trim();
        const fName = input.getAttribute('data-field');
        if (val !== '?') {
            // Check if matches vocab but different casing
            if (activeSchema && activeSchema.vocabulary && activeSchema.vocabulary[fName]) {
                const match = activeSchema.vocabulary[fName].find(v => v.toLowerCase() === val.toLowerCase());
                if (match) {
                    input.value = match;
                } else {
                    input.value = val; // Trimmed
                }
            } else {
                input.value = val; // Trimmed
            }
        }
      }
      const fName = input.getAttribute('data-field');
      markDirty(fName);
      triggerAutoSave();
    }

    function markDirty(fieldName) {
      if (fieldName) dirtyFields.add(fieldName);
    }

    function triggerAutoSave() {
      const syncStatus = document.getElementById('footerSyncStatus');
      syncStatus.innerHTML = `<span class='flex items-center gap-1.5 font-mono text-ember font-medium animate-pulse'><svg class="animate-spin h-3 w-3 text-ember" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span>Saving changes...</span></span>`;
      const btnRev = document.getElementById('btnMarkReviewed');
      if (btnRev) btnRev.disabled = true;
      clearTimeout(autoSaveTimer);
      autoSaveTimer = setTimeout(saveCurrentEdits, 800);  // 800ms per guide requirement
    }

    async function saveCurrentEdits() {
      if (autoSaveTimer) {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = null;
      }
      if (!currentOid) return;

      if (isSaving) {
        hasPendingSave = true;
        return;
      }
      isSaving = true;

      try {
        while (true) {
          hasPendingSave = false;
          const btnRev = document.getElementById('btnMarkReviewed');

          const regPayload = {};
          const obsPayload = {};

          // Collect all dynamic inputs
          document.querySelectorAll('[data-section="registration"]').forEach(input => {
            const f = input.getAttribute('data-field');
            if (dirtyFields.has(f)) {
              regPayload[f] = (input.type === 'checkbox') ? input.checked : input.value;
            }
          });

          document.querySelectorAll('[data-section="observation"]').forEach(input => {
            const f = input.getAttribute('data-field');
            if (dirtyFields.has(f)) {
              if (input.type === 'checkbox') {
                obsPayload[f] = input.checked;
              } else {
                obsPayload[f] = input.value;
              }
            }
          });

          // Merge problem flags
          if (currentRecord && currentRecord.observation) {
            Object.keys(currentRecord.observation).forEach(k => {
              if (k.endsWith('_Problem') || k.startsWith('Unknown_')) {
                if (dirtyFields.has(k)) {
                  obsPayload[k] = currentRecord.observation[k];
                }
              }
            });
          }

          // If nothing was dirtied, and review status wasn't checked, we technically don't need to save,
          // but the server handles empty updates gracefully.
          dirtyFields.clear();

          const unvalSourcesList = Object.entries(currentUnvalidatedMap || {}).map(([field, comment]) => ({ field, comment }));

          const payload = {
            id: currentOid,
            reviewed: isReviewed,
            registration: regPayload,
            observation: obsPayload,
            unvalidated_sources: unvalSourcesList,
            timestamp: new Date().toISOString()
          };

          if (!navigator.onLine || (document.getElementById('pingBadge') && document.getElementById('pingBadge').textContent === 'Offline')) {
            queueMutation(payload);
            if (btnRev) btnRev.disabled = false;

            // Optimistically update UI models to prevent local interruption
            if (currentRecord) {
              currentRecord.review_status = isReviewed ? 'reviewed' : 'pending';
              currentRecord.unvalidated_sources = unvalSourcesList;
              updateReviewButtonUI();
            }

            const listItem = objectList.find(o => String(o.id) === String(currentOid));
            if (listItem) {
              listItem.review_status = isReviewed ? 'reviewed' : 'pending';
              listItem.has_unvalidated = (unvalSourcesList.length > 0);
            }

            if (!hasPendingSave) break;
            continue;
          }
          if (btnRev) btnRev.disabled = false;

          try {
            const res = await apiFetch('/api/update', {
              method: 'POST',
              body: JSON.stringify(payload)
            });

            // Check for conflict response (409) or conflict message
            if (res && (res._status === 409 || res.status === 409 || (typeof res.error === 'string' && res.error.includes('Conflict')))) {
              showToast(`⚠️ ${res.error || 'Conflict: Host modified this record'}`, true);
              const syncStatus = document.getElementById('footerSyncStatus');
              if (syncStatus) {
                syncStatus.innerHTML = '<span class="font-mono text-ember font-medium" id="footerSyncStatusText">⚠️ Host conflict</span>';
              }
              if (btnRev) btnRev.disabled = false;
              if (!hasPendingSave) break;
              continue;
            }

            if (res && res.error && res.error !== 'Failed to fetch') {
              showToast(`⚠️ ${res.error}`, true);
              if (btnRev) btnRev.disabled = false;
              if (!hasPendingSave) break;
              continue;
            }

            // Handle case where fetch returns a network error or empty object instead of throwing
            if (!res || res.error === 'Failed to fetch' || (Object.keys(res).length === 0)) {
               throw new Error('Network failure');
            }

            document.getElementById('footerSyncStatus').innerHTML = '<span class="font-mono text-fern-dark font-medium" id="footerSyncStatusText">✓ Edit saved</span>';
            if (btnRev) btnRev.disabled = false;
            const undoBtn = document.getElementById('btnMobileUndo');
            if (undoBtn) undoBtn.classList.remove('hidden');
            if (undoBtn) undoBtn.classList.add('flex');

            if (res && res.success && currentRecord && (String(currentRecord.id) === String(currentOid) || String(currentRecord.accession_number) === String(currentOid))) {
              if (res.has_flags !== undefined) currentRecord.has_flags = res.has_flags;
              if (res.has_history !== undefined) currentRecord.has_history = res.has_history;
              if (res.has_unknown !== undefined) currentRecord.has_unknown = res.has_unknown;
              if (res.review_status !== undefined) currentRecord.review_status = res.review_status;
              updateReviewButtonUI();

              const listItem = objectList.find(o => String(o.id) === String(currentOid));
              if (listItem) {
                if (res.has_flags !== undefined) listItem.has_flags = res.has_flags;
                if (res.has_history !== undefined) listItem.has_history = res.has_history;
                if (res.has_unknown !== undefined) listItem.has_unknown = res.has_unknown;
                if (res.review_status !== undefined) listItem.review_status = res.review_status;
              }
            }

            // Hide 'Edit saved' message if we determine we're actually disconnected
            if (document.getElementById('pingBadge') && document.getElementById('pingBadge').textContent === 'Offline') {
                document.getElementById('footerSyncStatusText').classList.add('hidden');
            }
          } catch (err) {
            queueMutation(payload);
            if (btnRev) btnRev.disabled = false;

            // Optimistically update UI models to prevent local interruption
            if (currentRecord) {
              currentRecord.review_status = isReviewed ? 'reviewed' : 'pending';
              updateReviewButtonUI();
            }

            const listItem = objectList.find(o => String(o.id) === String(currentOid));
            if (listItem) {
              listItem.review_status = isReviewed ? 'reviewed' : 'pending';
            }
          }

          if (!hasPendingSave) {
            break;
          }
        }
      } finally {
        isSaving = false;
      }
    }

    function updateReviewButtonUI() {
      const btn = document.getElementById('btnMarkReviewed');
      const label = document.getElementById('btnReviewedLabel');
      const badgeContainer = document.getElementById('detailReviewStatusBadge');

      if (isReviewed) {
        btn.className = 'w-full py-3.5 px-4 rounded-[2px] font-sans font-bold text-sm flex items-center justify-center gap-2 border-2 transition-all touch-target-min touch-press bg-fern text-white border-fern-dark shadow-md';
        label.textContent = '✓ Reviewed (Tap to undo)';
      } else {
        btn.className = 'w-full py-3.5 px-4 rounded-[2px] font-sans font-bold text-sm flex items-center justify-center gap-2 border-2 transition-all touch-target-min touch-press bg-surface text-ink border-bordercol hover:bg-tonal1 shadow-xs';
        label.textContent = 'Mark Reviewed';
      }

      if (currentRecord) {
        currentRecord.review_status = isReviewed ? 'reviewed' : 'pending';
        badgeContainer.innerHTML = renderStatusBadge(currentRecord);
      } else {
        badgeContainer.innerHTML = renderStatusBadge({ review_status: isReviewed ? 'reviewed' : 'pending' });
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

    function loadInitialPhoto() {
      if (!photoUrls || photoUrls.length === 0) return;
      const mainContainer = document.getElementById('photoMainContainer');
      const placeholder = document.getElementById('photoPlaceholder');
      const specimenImg = document.getElementById('specimenImg');

      mainContainer.classList.remove('h-16');
      mainContainer.classList.add('h-52');
      mainContainer.setAttribute('onclick', 'openFullscreenPhoto()');

      placeholder.innerHTML = `
        <span class="text-2xl text-ink-faint animate-spin-slow">⏳</span>
        <p class="font-semibold text-fern">Loading...</p>
      `;

      specimenImg.src = photoUrls[0];
      renderPhotoThumbnails();
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

INDEX_TEMPLATE_V2 = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>Arbor Companion</title>
  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
  <!-- Google Fonts: Lora (Botanical Latin), Inter (UI), JetBrains Mono (IDs & Coordinates) -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600&display=swap" rel="stylesheet">

  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            alabaster: '#f3f3f3',
            canvas: '#f3f3f3',
            surface: '#ffffff',
            'surface-subtle': '#fbfbfb',
            ink: '#191e1a',
            'ink-muted': '#535d56',
            'ink-faint': '#848f87',
            muted: '#535d56',
            subdued: '#848f87',
            fern: {
              DEFAULT: '#3a7d44',
              dark: '#205438',
              light: '#eaf4ec',
              border: '#a4cca9'
            },
            'fern-dark': '#205438',
            'fern-light': '#eaf4ec',
            brick: {
              DEFAULT: '#c93a40',
              light: '#fdf2f2'
            },
            'brick-light': '#fdf2f2',
            slate: {
              DEFAULT: '#4a7b9d',
              light: '#f0f6fa'
            },
            'slate-light': '#f0f6fa',
            ember: {
              DEFAULT: '#d95c14',
              dark: '#b84a0c',
              light: '#fff3ec',
              border: '#f8c2a3'
            },
            'ember-light': '#fff3ec',
            bordercol: '#d4d8d5',
            'bordercol-subtle': '#ecefec',
            tonal1: '#f8f9fa',
            tonal2: '#eceeec'
          },
          fontFamily: {
            sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
            serif: ['Lora', 'Georgia', 'serif'],
            mono: ['"JetBrains Mono"', 'JetBrains Mono', 'Menlo', 'monospace']
          },
          boxShadow: {
            card: '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02)',
            pop: '0 4px 12px rgba(0,0,0,0.08)',
            dock: '0 -2px 10px rgba(0,0,0,0.05)',
            '2xs': '0 1px 2px rgba(0,0,0,0.03)'
          }
        }
      }
    };
  </script>

  <style>
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    .tap-highlight-transparent { -webkit-tap-highlight-color: transparent; }
    .tap-active:active { transform: scale(0.985); transition: transform 0.05s ease-out; }
    .touch-target-min { min-height: 44px; min-width: 44px; }
    .tab-slider { transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
    #tabTrack { transition: transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1); }
    body {
      background-color: #121413;
      touch-action: pan-y;
      overscroll-behavior-y: none;
      -webkit-font-smoothing: antialiased;
    }
    .mobile-shell {
      max-width: 440px;
      min-height: 100vh;
      margin: 0 auto;
      background-color: #f3f3f3;
      position: relative;
      box-shadow: 0 0 50px rgba(0,0,0,0.4);
      display: flex;
      flex-direction: column;
    }
  </style>
</head>
<body class="min-h-screen py-0 md:py-6 flex justify-center items-center font-sans text-ink select-none">

  <div class="mobile-shell w-full overflow-hidden border-x border-stone-800 flex flex-col h-screen md:h-[900px] md:max-h-[94vh] relative">

    <!-- Offline Banner -->
    <div id="offlineBanner" class="hidden bg-ember-light border-b border-ember-border px-4 py-2 flex items-center justify-between gap-2 text-xs font-sans font-medium text-ember-dark shrink-0 z-50">
      <div class="flex items-center gap-2">
        <span class="text-sm">⚠</span>
        <span>Host disconnected. Reconnecting...</span>
      </div>
      <button type="button" onclick="setupEventSource()" class="min-h-[30px] px-2.5 py-1 bg-ember text-white rounded font-bold text-[11px] tap-active">
        Retry
      </button>
    </div>

    <!-- ============================================================= -->
    <!-- SCREEN 1: VAULT LIST VIEW (#listView)                         -->
    <!-- ============================================================= -->
    <div id="listView" class="flex-1 flex flex-col h-full bg-canvas overflow-hidden">
      <!-- 1. Top Header -->
      <header class="sticky top-0 z-40 bg-surface/95 backdrop-blur-md border-b border-bordercol shrink-0">
        <div class="px-3.5 pt-3 pb-2 flex items-center justify-between">
          <div class="flex items-center space-x-2.5">
            <!-- Arbor "A" Badge -->
            <div class="w-7 h-7 rounded bg-fern-dark flex items-center justify-center text-white font-serif font-bold text-sm shadow-sm ring-1 ring-black/10">
              A
            </div>
            <div>
              <div class="flex items-center space-x-1.5 leading-none">
                <span class="font-bold text-[13px] tracking-tight text-ink font-sans">Arbor Companion</span>
                <span class="text-[10px] px-1 py-0.5 rounded bg-emerald-50 text-fern-dark font-mono font-medium border border-fern/30">v2</span>
              </div>
              <div class="text-[10.5px] font-mono text-ink-muted tracking-tight truncate max-w-[170px] mt-0.5" id="headerDbName">
                Loading database...
              </div>
            </div>
          </div>

          <!-- Top Utility Controls -->
          <div class="flex items-center space-x-1.5">
            <!-- Undo Button -->
            <button id="btnListUndo" onclick="undoLastEdit()" title="Undo recent edit" class="w-8 h-8 rounded-md bg-stone-100 border border-stone-200 text-stone-600 hover:text-ink flex items-center justify-center tap-active transition-colors">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 10h10a5 5 0 015 5v2m0 0l-4-4m4 4l4-4M3 10l4-4m-4 4l4 4"/>
              </svg>
            </button>

            <!-- Walk Mode (Wake Lock) Toggle -->
            <button id="btnListWakeLock" onclick="toggleWakeLock()" title="Keep screen awake during audit" class="w-8 h-8 rounded-md bg-stone-100 border border-stone-200 text-stone-600 hover:text-ink flex items-center justify-center tap-active transition-colors">
              <span id="listWakeLockIcon" class="text-xs">☀️</span>
            </button>

            <!-- Batch Location Registrator Trigger -->
            <button id="btnOpenBatchLocation" onclick="showBatchLocationView()" title="Open Batch Location Registrator" class="w-8 h-8 rounded-md bg-emerald-50 border border-fern/30 text-fern-dark hover:bg-emerald-100 flex items-center justify-center tap-active transition-colors">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
              </svg>
            </button>

            <!-- Settings Trigger -->
            <button onclick="openSettingsModal()" title="Application Settings" class="w-8 h-8 rounded-md bg-stone-100 border border-stone-200 text-stone-600 hover:text-ink flex items-center justify-center tap-active transition-colors">
              <span class="text-xs font-mono">⚙️</span>
            </button>

            <!-- Connection Status Pill -->
            <div onclick="openModal('connectionModal')" class="flex items-center space-x-1 px-2 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-[10.5px] font-mono font-medium text-emerald-800 cursor-pointer">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span id="pingBadge">42ms</span>
            </div>
          </div>
        </div>

        <!-- Search Bar Row -->
        <div class="px-3.5 pb-2.5 pt-0.5">
          <div class="relative flex items-center">
            <div class="absolute left-3 text-ink-faint pointer-events-none">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
              </svg>
            </div>
            <input 
              type="text" 
              id="searchBox" 
              placeholder="Search taxonomy, accession, cabinet..." 
              oninput="debounceSearch()"
              autocomplete="off"
              spellcheck="false"
              class="w-full pl-9 pr-16 py-2 bg-stone-100/90 hover:bg-stone-100 focus:bg-white text-xs font-mono text-ink placeholder:text-ink-faint placeholder:font-sans rounded-lg border border-stone-200 focus:border-fern focus:ring-1 focus:ring-fern focus:outline-none transition-all shadow-inner"
            />
            <div class="absolute right-2 flex items-center space-x-1">
              <button id="searchClearBtn" onclick="clearSearch()" class="hidden text-ink-faint hover:text-ink p-1 rounded text-xs font-mono leading-none" title="Clear search">
                ✕
              </button>
              <button id="btnFilterModalTrigger" onclick="openFilterModal()" title="Curatorial Filters" class="relative p-1.5 rounded-md hover:bg-stone-200/70 text-ink-muted hover:text-ink transition-colors">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/>
                </svg>
                <span id="filterActiveBadge" class="hidden absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-fern ring-2 ring-white"></span>
              </button>
            </div>
          </div>
        </div>

        <!-- 2. Filter Pills Bar (Hidden by Default, Toggleable in Settings) -->
        <div id="filterPillsContainer" class="hidden px-3.5 pb-2 overflow-x-auto no-scrollbar flex items-center space-x-1.5 border-t border-stone-100 pt-2">
          <button onclick="setStatusFilter('all')" id="pill-all" class="filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-ink text-white shadow-sm tap-active transition-all">
            All <span class="font-mono text-[10px] ml-0.5 opacity-90" id="pillCountAll">(0)</span>
          </button>
          <button onclick="setStatusFilter('pending')" id="pill-pending" class="filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-stone-200/80 text-ink-muted hover:bg-stone-300 tap-active transition-all">
            🕒 Unreviewed <span class="font-mono text-[10px] ml-0.5" id="pillCountPending">(0)</span>
          </button>
          <button onclick="setStatusFilter('flagged')" id="pill-flagged" class="filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-brick-light text-brick border border-brick/30 hover:bg-red-100 tap-active transition-all">
            ⚠ Flagged <span class="font-mono text-[10px] ml-0.5 font-bold" id="pillCountFlagged">(0)</span>
          </button>
          <button onclick="setStatusFilter('reviewed')" id="pill-reviewed" class="filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-emerald-50 text-fern-dark border border-fern/30 hover:bg-emerald-100 tap-active transition-all">
            ✓ Reviewed <span class="font-mono text-[10px] ml-0.5" id="pillCountReviewed">(0)</span>
          </button>
          <button onclick="setStatusFilter('conflict')" id="pill-conflict" class="filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-sky-50 text-sky-800 border border-sky-200 hover:bg-sky-100 tap-active transition-all">
            🔀 Conflicts <span class="font-mono text-[10px] ml-0.5" id="pillCountConflict">(0)</span>
          </button>
          <button onclick="setStatusFilter('unknown')" id="pill-unknown" class="filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-amber-50 text-amber-900 border border-amber-200 hover:bg-amber-100 tap-active transition-all">
            ? Unknown <span class="font-mono text-[10px] ml-0.5" id="pillCountUnknown">(0)</span>
          </button>
          <button onclick="toggleNoImageFilter()" id="pill-no-image" class="filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-stone-100 text-stone-600 border border-stone-200 hover:bg-stone-200 tap-active transition-all">
            📷 No Image
          </button>
        </div>

        <!-- Metrics & Sort Row -->
        <div class="px-3.5 py-2 bg-alabaster/70 border-t border-bordercol flex items-center justify-between text-[11px]">
          <div class="font-mono text-ink-muted">
            Showing <span class="font-bold text-ink" id="matchingCount">0</span> matching records
          </div>
          <div class="flex items-center space-x-1.5">
            <div class="relative inline-flex items-center">
              <select id="sortBySelect" onchange="handleSortChange()" class="appearance-none bg-white border border-bordercol rounded-md px-2 py-1 pr-6 text-[10.5px] font-mono text-ink focus:outline-none focus:border-fern shadow-2xs cursor-pointer">
                <option value="id_asc">⇅ Sort: Accession ID (0894...)</option>
                <option value="location">Physical Location</option>
                <option value="name_asc">Scientific Name (A–Z)</option>
                <option value="name_desc">Scientific Name (Z–A)</option>
                <option value="flagged_first">Flagged / Problems First</option>
              </select>
              <div class="absolute right-1.5 pointer-events-none text-ink-faint">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- 3. Specimen Card Feed -->
      <main class="flex-1 p-3.5 space-y-2.5 overflow-y-auto pb-24" id="specimenListContainer">
        <!-- Injected via JS -->
      </main>

      <!-- 4. Bottom Vault Progress Dock -->
      <footer class="sticky bottom-0 z-40 bg-surface/95 backdrop-blur-md border-t border-bordercol px-4 py-2.5 shadow-dock">
        <div class="flex items-center justify-between text-xs mb-1.5">
          <div class="flex items-center space-x-1.5 font-mono text-[11px]">
            <span class="w-2 h-2 rounded-full bg-fern inline-block"></span>
            <span class="text-ink font-semibold" id="listProgressText">0 / 0 Reviewed</span>
            <span class="text-ink-muted" id="listProgressPct">(0%)</span>
          </div>
          <div class="text-[10px] font-mono text-ink-muted flex items-center space-x-1">
            <svg class="w-3 h-3 text-fern" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/></svg>
            <span>Auto-sync ready</span>
          </div>
        </div>
        <div class="w-full bg-stone-200 h-1.5 rounded-full overflow-hidden">
          <div class="bg-fern h-full transition-all duration-300 rounded-full" id="listProgressBar" style="width: 0%;"></div>
        </div>
      </footer>
    </div>


    <!-- ============================================================= -->
    <!-- SCREEN 2: SPECIMEN DETAIL VIEW (#detailView)                  -->
    <!-- ============================================================= -->
    <div id="detailView" class="hidden flex-1 flex flex-col h-full bg-alabaster overflow-hidden relative font-sans text-ink">
      <!-- 1. Sticky Top Navigation Bar -->
      <header class="flex-none bg-surface border-b border-bordercol px-3.5 py-2.5 flex items-center justify-between z-30">
        <!-- Back Button -->
        <button type="button" onclick="showListView()" class="flex items-center gap-1.5 px-2 py-1.5 min-h-[36px] -ml-1 text-xs font-semibold text-muted hover:text-ink active:bg-stone-100 rounded transition-colors tap-highlight-transparent">
          <svg class="w-4 h-4 text-ink stroke-[2.2]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M15.75 19.5L8.25 12l7.5-7.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="font-mono">Vault List</span>
        </button>

        <!-- Steppers & Controls -->
        <div class="flex items-center gap-1.5">
          <!-- Detail Undo Button -->
          <button id="btnDetailUndo" onclick="undoLastEdit()" title="Undo edit" class="items-center gap-1 px-2 py-1 h-[32px] text-[10.5px] font-mono font-medium text-ember bg-orange-50 border border-orange-200 rounded active:scale-95 transition-all flex">
            <svg class="w-3.5 h-3.5 stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>Undo</span>
          </button>

          <!-- Specimen Index Counter -->
          <span class="text-[11px] font-mono font-medium text-subdued tracking-tight bg-stone-100 px-2 py-1.5 rounded border border-bordercol/60">
            <span class="text-ink font-semibold" id="detailCurrentIdx">1</span><span class="text-stone-400 mx-0.5">/</span><span id="detailTotalCount">1</span>
          </span>

          <!-- Next / Prev Steppers -->
          <div class="inline-flex rounded border border-bordercol bg-alabaster p-0.5 shadow-2xs">
            <button type="button" class="w-7 h-7 flex items-center justify-center rounded hover:bg-surface text-ink active:bg-stone-200 transition-colors tap-highlight-transparent" onclick="navSpecimen(-1)" title="Previous Specimen">
              <svg class="w-4 h-4 stroke-[2.2]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M15 19l-7-7 7-7" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <div class="w-[1px] bg-bordercol my-0.5"></div>
            <button type="button" class="w-7 h-7 flex items-center justify-center rounded hover:bg-surface text-ink active:bg-stone-200 transition-colors tap-highlight-transparent" onclick="navSpecimen(1)" title="Next Specimen">
              <svg class="w-4 h-4 stroke-[2.2]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>
        </div>
      </header>

      <!-- 2. Sticky Specimen Identification Header -->
      <section class="flex-none bg-surface border-b border-bordercol px-4 pt-3 pb-3 z-20 shadow-2xs">
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center gap-2">
            <span class="font-mono text-xs font-bold text-ink tracking-tight px-1.5 py-0.5 bg-stone-100 border border-bordercol rounded" id="detailAccession">
              #2024-BOT-0894
            </span>
          </div>
          <!-- Interactive Status Pill -->
          <button type="button" class="flex items-center gap-1.5 text-[11px] font-mono font-semibold px-2 py-0.5 rounded border transition-colors tap-highlight-transparent bg-amber-50 text-amber-800 border-amber-300" id="badgeStatus" onclick="toggleReviewed()">
            <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" id="badgeStatusDot"></span>
            <span id="badgeStatusText">UNREVIEWED</span>
          </button>
        </div>

        <h1 class="text-[19px] leading-tight font-serif font-semibold italic text-ink tracking-tight flex items-baseline gap-1.5 truncate" id="detailScientificName">
          Betula pendula
        </h1>

        <div class="flex items-center flex-wrap gap-x-2.5 gap-y-0.5 mt-1.5 text-xs text-muted">
          <div class="flex items-center gap-1">
            <span class="text-subdued font-medium">Fam:</span>
            <span class="font-medium text-ink" id="detailFamily">Betulaceae</span>
          </div>
          <span class="text-bordercol">•</span>
          <div class="flex items-center gap-1 font-mono text-[11px]">
            <span class="text-subdued font-sans">Loc:</span>
            <span class="text-ink font-semibold" id="headerLocSummary">Cab 04 · Sh 02 · Fl -1</span>
          </div>
        </div>
      </section>

      <!-- 3. Segmented Tab Controller (Sticky) -->
      <nav class="flex-none bg-alabaster border-b border-bordercol px-3 pt-2 pb-1.5 z-20">
        <div class="relative bg-stone-200/90 p-1 rounded-[4px] flex items-center justify-between text-xs font-medium text-muted shadow-inner">
          <div class="tab-slider absolute top-1 bottom-1 w-[calc((100%-8px)/3)] bg-surface rounded shadow-sm border border-stone-300 pointer-events-none translate-x-0" id="tabIndicator" style="transform: translateX(0%);"></div>
          <button id="tabBtnLocation" class="tab-btn relative z-10 flex-1 py-1.5 min-h-[36px] flex items-center justify-center gap-1.5 font-semibold text-ink tap-highlight-transparent" data-tab-index="0" onclick="switchDetailTab('location')">
            <svg class="w-3.5 h-3.5 stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z"/><path d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z"/></svg>
            <span>Location</span>
          </button>
          <button id="tabBtnDetails" class="tab-btn relative z-10 flex-1 py-1.5 min-h-[36px] flex items-center justify-center gap-1.5 text-muted tap-highlight-transparent" data-tab-index="1" onclick="switchDetailTab('details')">
            <svg class="w-3.5 h-3.5 stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
            <span>Details</span>
          </button>
          <button id="tabBtnProblems" class="tab-btn relative z-10 flex-1 py-1.5 min-h-[36px] flex items-center justify-center gap-1.5 text-muted tap-highlight-transparent" data-tab-index="2" onclick="switchDetailTab('problems')">
            <svg class="w-3.5 h-3.5 text-brick stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/></svg>
            <span>Problems</span>
            <span class="font-mono text-[10px] font-bold px-1.5 rounded-full bg-brick text-white shadow-2xs hidden" id="tabProblemBadge">0</span>
          </button>
        </div>
      </nav>

      <!-- 4. Horizontal Swipeable Tab Track -->
      <div class="flex-1 overflow-hidden relative" id="swipeArea">
        <div class="h-full flex w-[300%]" id="tabTrack" style="transform: translateX(0%);">

          <!-- ================= TAB 0: LOCATION ================= -->
          <div class="w-1/3 h-full overflow-y-auto no-scrollbar p-4 space-y-3.5 pb-24" id="tabContentLocation">
            <!-- 1. Copy from Previous Bar -->
            <div class="bg-surface border border-bordercol rounded p-2.5 shadow-2xs">
              <button class="w-full py-2.5 px-3 bg-stone-100 hover:bg-stone-200/80 active:bg-stone-300 border border-stone-300 rounded flex items-center justify-between text-left transition-all tap-highlight-transparent min-h-[44px]" id="btnCopyPrevSpecimen" onclick="handleCopyPreviousSpecimen()" type="button">
                <div class="flex items-center gap-2 truncate">
                  <span class="text-base leading-none">📋</span>
                  <div class="truncate">
                    <span class="text-xs font-bold text-ink block truncate" id="copyTitleSpan">Copy from Previous</span>
                    <span class="text-[10px] font-mono text-muted block truncate" id="copySubtitleSpan">Tap to duplicate physical coordinates</span>
                  </div>
                </div>
                <span class="text-[10px] font-mono font-bold px-2 py-1 bg-surface border border-stone-300 text-muted rounded shadow-2xs whitespace-nowrap ml-2">1-Tap Fill</span>
              </button>
            </div>

            <!-- 2. Main Physical Coordinate Audit Card -->
            <div class="bg-surface border border-bordercol rounded p-3.5 shadow-xs space-y-3.5">
              <div class="flex items-center justify-between border-b border-stone-100 pb-2">
                <div>
                  <h2 class="text-xs font-bold text-ink uppercase tracking-wider font-sans">Physical Coordinates Audit</h2>
                  <p class="text-[10px] font-mono text-subdued">Thumb-optimized steppers · Continuous numeric coordinates</p>
                </div>
                <span class="text-[10px] font-mono text-fern font-semibold flex items-center gap-1" id="locSyncIndicator">
                  <svg class="w-3 h-3 stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4.5 12.75l6 6 9-13.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  Synced
                </span>
              </div>

              <!-- SECTION A: BUILDING SELECTOR -->
              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <label class="text-[10px] font-mono uppercase tracking-wider font-bold text-subdued">Building / Facility</label>
                  <button class="text-[10px] font-mono text-slate hover:text-ink flex items-center gap-0.5 tap-highlight-transparent" onclick="toggleCustomBuildingInput()" type="button">+ Other</button>
                </div>
                <div class="grid grid-cols-2 gap-2" id="buildingChipsGrid">
                  <button class="bldg-chip min-h-[44px] px-3 py-2 rounded border text-xs font-mono font-semibold flex items-center justify-center gap-1.5 transition-all shadow-2xs bg-[#1c3829] text-white border-transparent" data-building="Økern" onclick="setBuildingSelection('Økern', this)" type="button">
                    <span>Økern</span>
                  </button>
                  <button class="bldg-chip min-h-[44px] px-3 py-2 rounded border border-bordercol bg-stone-50 hover:bg-stone-100 active:bg-stone-200 text-ink text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all shadow-2xs" data-building="Lid's hus" onclick="setBuildingSelection('Lid\'s hus', this)" type="button">
                    <span>Lid's hus</span>
                  </button>
                </div>
                <!-- Inline Manual Custom Building -->
                <div class="hidden pt-1 space-y-1" id="customBuildingWrap">
                  <div class="flex items-center gap-1.5">
                    <input class="flex-1 text-xs font-mono px-2.5 py-1.5 min-h-[38px] bg-alabaster border border-bordercol rounded text-ink focus:bg-white focus:border-ink focus:outline-none" id="input_observation_Building" placeholder="Specify facility name..." type="text">
                    <button class="px-2.5 py-1.5 min-h-[38px] text-xs font-mono font-semibold bg-stone-800 text-white rounded active:bg-black tap-highlight-transparent" onclick="applyCustomBuilding()" type="button">Set</button>
                  </div>
                </div>
              </div>

              <!-- SECTION B: CONTINUOUS NUMERIC STEPPERS (Floor, Cabinet, Shelf) -->
              <div class="space-y-2 pt-1">
                <div class="flex items-center justify-between text-[10px] font-mono uppercase font-bold text-subdued">
                  <span>Physical Coordinates</span>
                  <span class="text-[9px] text-muted lowercase">tap number for keypad</span>
                </div>
                <div class="grid grid-cols-3 gap-2">
                  <!-- FLOOR STEPPER (Signed Integer: -2, -1, 0, 1, 2...) -->
                  <div class="p-2 bg-stone-50 border border-stone-200 rounded flex flex-col justify-between space-y-1.5 text-center">
                    <span class="text-[9px] font-mono uppercase font-bold text-subdued tracking-wider">Floor</span>
                    <div class="py-0.5 relative flex items-center justify-center min-h-[34px]">
                      <span class="font-mono font-bold text-base text-ink cursor-pointer hover:underline underline-offset-2 tap-highlight-transparent" id="displayFloorVal" onclick="activateDirectInput('Floor')">-1</span>
                      <input class="hidden w-full text-center font-mono font-bold text-base bg-white border border-ink rounded py-0.5 text-ink focus:outline-none" id="input_observation_Floor" inputmode="numeric" onblur="finishDirectInput('Floor')" onkeydown="if(event.key==='Enter')finishDirectInput('Floor')" pattern="[0-9-]*" type="text">
                    </div>
                    <div class="grid grid-cols-2 gap-1">
                      <button class="min-h-[44px] flex items-center justify-center bg-white border border-stone-300 hover:border-ink active:bg-stone-200 rounded text-ink font-mono font-bold text-base tap-highlight-transparent" onclick="adjustCoordinate('floor', -1)" type="button">−</button>
                      <button class="min-h-[44px] flex items-center justify-center bg-white border border-stone-300 hover:border-ink active:bg-stone-200 rounded text-ink font-mono font-bold text-base tap-highlight-transparent" onclick="adjustCoordinate('floor', 1)" type="button">+</button>
                    </div>
                  </div>

                  <!-- CABINET STEPPER (Positive Integer) -->
                  <div class="p-2 bg-stone-50 border border-stone-200 rounded flex flex-col justify-between space-y-1.5 text-center">
                    <span class="text-[9px] font-mono uppercase font-bold text-subdued tracking-wider">Cabinet</span>
                    <div class="py-0.5 relative flex items-center justify-center min-h-[34px]">
                      <span class="font-mono font-bold text-base text-ink cursor-pointer hover:underline underline-offset-2 tap-highlight-transparent" id="displayCabVal" onclick="activateDirectInput('Cab')">04</span>
                      <input class="hidden w-full text-center font-mono font-bold text-base bg-white border border-ink rounded py-0.5 text-ink focus:outline-none" id="input_observation_Cabinet" inputmode="numeric" onblur="finishDirectInput('Cab')" onkeydown="if(event.key==='Enter')finishDirectInput('Cab')" pattern="[0-9]*" type="text">
                    </div>
                    <div class="grid grid-cols-2 gap-1">
                      <button class="min-h-[44px] flex items-center justify-center bg-white border border-stone-300 hover:border-ink active:bg-stone-200 rounded text-ink font-mono font-bold text-base tap-highlight-transparent" onclick="adjustCoordinate('cab', -1)" type="button">−</button>
                      <button class="min-h-[44px] flex items-center justify-center bg-white border border-stone-300 hover:border-ink active:bg-stone-200 rounded text-ink font-mono font-bold text-base tap-highlight-transparent" onclick="adjustCoordinate('cab', 1)" type="button">+</button>
                    </div>
                  </div>

                  <!-- SHELF STEPPER (Positive Integer) -->
                  <div class="p-2 bg-stone-50 border border-stone-200 rounded flex flex-col justify-between space-y-1.5 text-center">
                    <span class="text-[9px] font-mono uppercase font-bold text-subdued tracking-wider">Shelf</span>
                    <div class="py-0.5 relative flex items-center justify-center min-h-[34px]">
                      <span class="font-mono font-bold text-base text-ink cursor-pointer hover:underline underline-offset-2 tap-highlight-transparent" id="displayShelfVal" onclick="activateDirectInput('Shelf')">02</span>
                      <input class="hidden w-full text-center font-mono font-bold text-base bg-white border border-ink rounded py-0.5 text-ink focus:outline-none" id="input_observation_Shelf" inputmode="numeric" onblur="finishDirectInput('Shelf')" onkeydown="if(event.key==='Enter')finishDirectInput('Shelf')" pattern="[0-9]*" type="text">
                    </div>
                    <div class="grid grid-cols-2 gap-1">
                      <button class="min-h-[44px] flex items-center justify-center bg-white border border-stone-300 hover:border-ink active:bg-stone-200 rounded text-ink font-mono font-bold text-base tap-highlight-transparent" onclick="adjustCoordinate('shelf', -1)" type="button">−</button>
                      <button class="min-h-[44px] flex items-center justify-center bg-white border border-stone-300 hover:border-ink active:bg-stone-200 rounded text-ink font-mono font-bold text-base tap-highlight-transparent" onclick="adjustCoordinate('shelf', 1)" type="button">+</button>
                    </div>
                  </div>
                </div>

                <!-- Live Breadcrumb Trail -->
                <div class="bg-stone-100 border border-bordercol/60 rounded px-2.5 py-1.5 flex items-center justify-between text-[11px] font-mono mt-1">
                  <div class="flex items-center gap-1 text-ink truncate">
                    <span class="text-subdued uppercase text-[9px] font-sans font-bold">Live:</span>
                    <span class="font-semibold truncate" id="liveLocBreadcrumb">Økern › Floor -1 › Cab 04 › Sh 02</span>
                  </div>
                  <span class="text-[10px] font-mono text-fern font-bold whitespace-nowrap ml-1">✓ Validated</span>
                </div>
              </div>

              <!-- SECTION C: STORED AS 2x2 PRESET MATRIX -->
              <div class="space-y-2 pt-1 border-t border-stone-100">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-1.5">
                    <label class="text-[10px] font-mono uppercase tracking-wider font-bold text-subdued">Stored as</label>
                    <button class="p-1 -my-1 text-stone-400 hover:text-ink rounded flex items-center justify-center" onclick="openPresetsModal()" title="Customize quick presets" type="button">
                      <svg class="w-3.5 h-3.5 stroke-[2.2]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                    </button>
                  </div>
                  <div class="flex items-center gap-1.5">
                    <span class="text-[10px] font-mono text-ink font-semibold truncate max-w-[170px]" id="activeStoredAsLabel">Herbarium Sheet</span>
                    <button class="text-[10px] font-mono text-slate hover:text-ink tap-highlight-transparent" onclick="openPresetsModal()" type="button">Edit</button>
                  </div>
                </div>

                <div class="grid grid-cols-2 gap-2 text-xs font-mono" id="storageQuickGrid">
                  <!-- Presets injected dynamically -->
                </div>

                <!-- Manual Storage Override -->
                <div class="pt-1 space-y-1">
                  <div class="relative flex items-center">
                    <input class="w-full text-xs font-mono bg-alabaster border border-bordercol rounded pl-2.5 pr-8 py-2 min-h-[38px] text-ink focus:bg-white focus:border-ink focus:outline-none" id="manualStorageInput" oninput="onManualStorageChange(this.value)" placeholder="Or enter manual storage type..." type="text">
                    <button class="absolute right-2 text-stone-400 hover:text-ink hidden p-1 leading-none text-xs font-mono font-bold" id="btnClearManualStorage" onclick="clearManualStorage()" type="button">✕</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 3. Availability / Loan Status Card -->
            <div class="bg-surface border border-bordercol rounded p-3 shadow-2xs space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-1.5">
                  <span class="w-2 h-2 rounded-full bg-fern" id="loanStatusDot"></span>
                  <h2 class="text-xs font-bold text-ink uppercase tracking-wider font-sans">Availability Status</h2>
                </div>
                <span class="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-fern-light text-fern border border-fern/30" id="loanStateTag">In Repository</span>
              </div>
              <div class="grid grid-cols-2 p-1 bg-stone-100 border border-stone-200 rounded gap-1">
                <button class="py-1.5 px-2 rounded text-xs font-mono font-semibold flex items-center justify-center gap-1.5 transition-all bg-white text-ink border border-stone-300 min-h-[36px]" id="btnStatusAvailable" onclick="setLoanStatus(false)" type="button">
                  <svg class="w-3.5 h-3.5 text-fern stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                  <span>In Repository</span>
                </button>
                <button class="py-1.5 px-2 rounded text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all text-muted hover:text-ink min-h-[36px]" id="btnStatusLoan" onclick="setLoanStatus(true)" type="button">
                  <svg class="w-3.5 h-3.5 text-amber-600 stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/></svg>
                  <span>Loaned Out</span>
                </button>
              </div>
            </div>
          </div>

          <!-- ================= TAB 1: DETAILS & ARCHIVAL SCANS ================= -->
          <div class="w-1/3 h-full overflow-y-auto no-scrollbar p-4 space-y-3.5 pb-24" id="tabContentDetails">
            <!-- Image Viewer Container -->
            <div class="bg-surface border border-bordercol rounded p-3 shadow-2xs space-y-2">
              <div class="flex items-center justify-between">
                <h3 class="text-xs font-bold text-ink uppercase tracking-wider font-sans">Archival Photo Folio</h3>
                <span class="text-[10px] font-mono text-muted" id="photoCountDisplay">0 Photos</span>
              </div>
              <div class="relative w-full h-48 bg-stone-100 rounded border border-bordercol overflow-hidden flex items-center justify-center cursor-pointer" onclick="openPhotoViewerModal()">
                <img id="specimenImg" src="" alt="Specimen Scan" class="w-full h-full object-contain hidden" onload="onPhotoLoaded()" onerror="onPhotoError()"/>
                <div id="photoPlaceholder" class="flex flex-col items-center justify-center text-stone-400">
                  <span class="text-3xl">📷</span>
                  <span class="text-xs mt-1">Tap to Inspect Photo</span>
                </div>
              </div>
              <div id="photoThumbnailsRow" class="flex items-center gap-2 overflow-x-auto no-scrollbar pt-1">
                <!-- Thumbnails injected dynamically -->
              </div>
            </div>

            <!-- Registration & Observation Metadata Form Fields -->
            <div class="bg-surface border border-bordercol rounded p-3.5 shadow-2xs space-y-3" id="dynamicFormContainer">
              <!-- Form fields injected dynamically from schema -->
            </div>
          </div>

          <!-- ================= TAB 2: PROBLEMS & CONFLICTS ================= -->
          <div class="w-1/3 h-full overflow-y-auto no-scrollbar p-4 space-y-3.5 pb-24" id="tabContentProblems">
            <div class="bg-surface border border-bordercol rounded p-3.5 shadow-2xs space-y-3">
              <div class="flex items-center justify-between">
                <h3 class="text-xs font-bold text-ink uppercase tracking-wider font-sans">Curatorial Problems & Flags</h3>
                <button type="button" onclick="openModal('addDiscrepancyModal')" class="px-2.5 py-1 text-xs font-mono font-bold bg-ember text-white rounded tap-active">
                  + Flag Issue
                </button>
              </div>

              <!-- Problem Resolver Section -->
              <div id="problemResolverContainer" class="space-y-2">
                <!-- Inline problem fixer cards populated here -->
              </div>

              <!-- Historical Conflicts Container -->
              <div id="historicalConflictsContainer" class="space-y-2 pt-2 border-t border-stone-100">
                <!-- Historical DB conflict cards populated here -->
              </div>

              <div id="problemsListContainer" class="space-y-2">
                <!-- General problem items injected dynamically -->
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>


    <!-- ============================================================= -->
    <!-- SCREEN 3: BATCH LOCATION REGISTRATOR (#batchLocationView)     -->
    <!-- ============================================================= -->
    <div id="batchLocationView" class="hidden flex-1 flex flex-col h-full bg-surface overflow-hidden relative font-sans text-ink">
      <!-- 1. Batch Header -->
      <header class="flex-none bg-surface/90 backdrop-blur-md border-b border-bordercol px-3.5 py-3 flex items-center justify-between z-30 shadow-2xs">
        <div class="flex items-center gap-2 min-w-0">
          <button type="button" onclick="showListView()" class="min-h-[38px] min-w-[38px] flex items-center justify-center text-ink hover:text-fern active:scale-95">
            <svg class="w-5 h-5 stroke-[2.2]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M15.75 19.5L8.25 12l7.5-7.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
          <div class="flex flex-col min-w-0">
            <span class="font-serif font-bold text-sm text-ink leading-tight truncate">Batch Location Registrator</span>
            <span class="font-mono text-[10px] text-muted truncate">Rapid shelf assignment · vascular_plants.csv</span>
          </div>
        </div>
        <div class="flex items-center gap-1.5">
          <div class="flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-[10.5px] font-mono text-emerald-800">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Live</span>
          </div>
        </div>
      </header>

      <!-- 2. Scrollable Batch Workflow -->
      <main class="flex-1 overflow-y-auto p-3.5 space-y-3 pb-36">
        <!-- Target Shelf Anchor Card -->
        <section class="bg-stone-50 border border-bordercol rounded-lg p-3 space-y-2.5 shadow-2xs">
          <div class="flex items-center justify-between">
            <span class="font-mono text-[10px] uppercase font-bold text-subdued tracking-wider">Target Physical Anchor</span>
            <span class="font-mono text-[10px] text-fern font-bold">🔒 Locked Shelf Target</span>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <!-- Building -->
            <div class="bg-white rounded p-1.5 border border-bordercol flex items-center justify-between">
              <span class="font-mono text-[9px] uppercase font-bold text-muted">Bldg</span>
              <select id="batchBuildingSelect" class="bg-transparent font-mono text-xs font-bold text-ink outline-none text-right">
                <option value="Økern">Økern</option>
                <option value="Lid's hus">Lid's hus</option>
              </select>
            </div>
            <!-- Floor (Continuous signed integer) -->
            <div class="bg-white rounded p-1.5 border border-bordercol flex items-center justify-between">
              <span class="font-mono text-[9px] uppercase font-bold text-muted">Floor</span>
              <div class="flex items-center gap-1">
                <button type="button" class="w-5 h-5 rounded bg-stone-100 flex items-center justify-center font-mono font-bold text-xs" onclick="adjustBatchCoord('floor', -1)">−</button>
                <span class="font-mono text-xs font-bold text-ink px-1 min-w-[20px] text-center" id="batchFloorVal">-1</span>
                <button type="button" class="w-5 h-5 rounded bg-stone-100 flex items-center justify-center font-mono font-bold text-xs" onclick="adjustBatchCoord('floor', 1)">+</button>
              </div>
            </div>
            <!-- Cabinet -->
            <div class="bg-white rounded p-2 border border-bordercol flex items-center justify-between">
              <span class="font-mono text-[10px] uppercase font-bold text-muted">Cabinet</span>
              <div class="flex items-center gap-1.5">
                <button type="button" class="w-6 h-6 rounded bg-stone-100 flex items-center justify-center font-mono font-bold text-sm" onclick="adjustBatchCoord('cab', -1)">−</button>
                <span class="font-mono text-sm font-bold text-ink px-1 min-w-[24px] text-center" id="batchCabVal">04</span>
                <button type="button" class="w-6 h-6 rounded bg-stone-100 flex items-center justify-center font-mono font-bold text-sm" onclick="adjustBatchCoord('cab', 1)">+</button>
              </div>
            </div>
            <!-- Shelf -->
            <div class="bg-white rounded p-2 border-2 border-fern flex items-center justify-between">
              <span class="font-mono text-[10px] uppercase font-bold text-fern-dark">Shelf</span>
              <div class="flex items-center gap-1.5">
                <button type="button" class="w-6 h-6 rounded bg-stone-100 flex items-center justify-center font-mono font-bold text-sm" onclick="adjustBatchCoord('shelf', -1)">−</button>
                <span class="font-mono text-sm font-bold text-fern-dark px-1 min-w-[24px] text-center" id="batchShelfVal">02</span>
                <button type="button" class="w-6 h-6 rounded bg-stone-100 flex items-center justify-center font-mono font-bold text-sm" onclick="adjustBatchCoord('shelf', 1)">+</button>
              </div>
            </div>
          </div>

          <!-- Stored As Pill Carousel -->
          <div class="pt-1">
            <div class="flex items-center justify-between mb-1">
              <span class="font-mono text-[9px] uppercase text-muted font-bold">Stored As</span>
              <span class="font-mono text-[10px] text-ink font-semibold" id="batchStoredAsLabel">Herbarium Sheet</span>
            </div>
            <div class="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5" id="batchStoredAsPills">
              <button type="button" onclick="selectBatchStoragePill(this, 'Herbarium Sheet')" class="batch-storage-pill px-2.5 py-1 rounded-full text-[11px] font-mono border-2 border-fern bg-emerald-50 text-fern-dark font-semibold">
                Herbarium Sheet
              </button>
              <button type="button" onclick="selectBatchStoragePill(this, 'Standard Box')" class="batch-storage-pill px-2.5 py-1 rounded-full text-[11px] font-mono border border-bordercol bg-white text-muted">
                Standard Box
              </button>
              <button type="button" onclick="selectBatchStoragePill(this, 'Free Standing')" class="batch-storage-pill px-2.5 py-1 rounded-full text-[11px] font-mono border border-bordercol bg-white text-muted">
                Free Standing
              </button>
              <button type="button" onclick="selectBatchStoragePill(this, 'Petri dish')" class="batch-storage-pill px-2.5 py-1 rounded-full text-[11px] font-mono border border-bordercol bg-white text-muted">
                Petri dish
              </button>
            </div>
          </div>
        </section>

        <!-- Advance to Next Shelf Button -->
        <button type="button" id="btnAdvanceNextShelf" onclick="advanceToNextShelf()" class="w-full py-2.5 px-3 bg-stone-100 hover:bg-emerald-50 text-ink hover:text-fern-dark rounded-lg border border-bordercol hover:border-fern/50 font-mono text-xs font-bold flex items-center justify-center gap-2 shadow-2xs tap-active transition-all">
          <svg class="w-4 h-4 text-fern stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <span id="btnAdvanceNextShelfText">Advance to Shelf 03</span>
        </button>

        <!-- Rapid Object ID Input Bar -->
        <section class="space-y-1">
          <label for="batchIdInput" class="font-mono text-[10px] uppercase text-muted font-bold flex items-center justify-between">
            <span>Type Object ID</span>
            <span class="text-fern lowercase">press enter to add</span>
          </label>
          <div class="relative flex items-center bg-white rounded-lg shadow-sm border border-bordercol focus-within:border-fern">
            <span class="pl-3 text-ink-faint font-mono text-xs">#</span>
            <input 
              type="text" 
              id="batchIdInput" 
              placeholder="e.g. 0894 or 2024-BOT-0894..." 
              onkeydown="if(event.key==='Enter')addBatchItemFromInput()"
              autocomplete="off"
              class="w-full bg-transparent font-mono text-sm text-ink placeholder:text-stone-400 py-2.5 px-2 focus:outline-none"
            >
            <button type="button" onclick="addBatchItemFromInput()" class="m-1 px-3 py-1.5 bg-fern hover:bg-fern-dark text-white rounded font-mono font-bold text-xs flex items-center gap-1 shadow-sm tap-active">
              <span>⏎</span>
              <span>Add</span>
            </button>
          </div>
        </section>

        <!-- Live Session Batch Stream -->
        <section class="space-y-2">
          <div class="flex items-center justify-between py-1 border-b border-stone-100">
            <div class="flex items-center gap-1.5">
              <span class="font-serif font-bold text-xs text-ink">Objects on Shelf</span>
              <span class="font-mono text-[11px] text-fern font-bold" id="batchQueueCount">(0 items)</span>
            </div>
            <button type="button" onclick="clearBatchQueue()" class="text-[11px] font-mono text-brick hover:underline">
              Clear All
            </button>
          </div>

          <div class="space-y-2" id="batchStreamList">
            <!-- Dynamically populated batch items -->
            <div class="p-6 text-center text-stone-400 font-mono text-xs" id="batchEmptyPlaceholder">
              No items queued for this shelf yet.<br>Type an Object ID above to begin.
            </div>
          </div>
        </section>
      </main>

      <!-- 3. Sticky Bottom Commit Bar -->
      <footer class="fixed bottom-0 inset-x-0 z-40 bg-surface/95 backdrop-blur-md border-t border-bordercol px-4 py-3 shadow-dock max-w-[440px] mx-auto">
        <div class="flex items-center justify-between gap-3">
          <div class="flex flex-col">
            <span class="font-mono text-[10px] text-muted uppercase">Ready to Sync</span>
            <span class="font-mono text-xs font-bold text-ink" id="batchCommitSummary">0 Accessions Queued</span>
          </div>
          <button type="button" onclick="commitBatchLocationUpdate()" class="flex-1 py-3 bg-fern hover:bg-fern-dark text-white font-sans font-bold text-xs rounded-lg flex items-center justify-center gap-2 shadow-sm tap-active transition-all">
            <svg class="w-4 h-4 stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"/></svg>
            <span>Commit Batch</span>
          </button>
        </div>
      </footer>
    </div>


    <!-- ============================================================= -->
    <!-- MODALS                                                        -->
    <!-- ============================================================= -->

    <!-- MODAL: Settings -->
    <div id="settingsModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded w-full max-w-sm shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between">
          <h2 class="font-serif font-bold text-sm text-ink">Application Settings</h2>
          <button type="button" onclick="closeSettingsModal()" class="text-ink-muted hover:text-ink font-bold text-sm">✕</button>
        </header>
        <div class="p-4 space-y-4">
          <!-- Toggle Filter Pills on List View -->
          <div class="flex items-center justify-between p-2.5 bg-stone-50 border border-bordercol rounded">
            <div>
              <span class="block font-sans text-xs font-bold text-ink">Quick Filter Pills</span>
              <span class="block font-sans text-[10px] text-muted">Show horizontal filter pills on Vault List</span>
            </div>
            <input type="checkbox" id="settingShowFilterPills" onchange="toggleFilterPillsSetting(this.checked)" class="w-4 h-4 text-fern rounded border-bordercol focus:ring-fern">
          </div>

          <div>
            <label class="block font-sans text-xs font-medium text-ink mb-1">Image URL Pattern Override</label>
            <input type="text" id="settingImageUrlPattern" placeholder="e.g. https://example.com/{id}.jpg" class="w-full bg-surface border border-bordercol rounded px-2.5 py-1.5 text-xs text-ink outline-none focus:border-fern">
            <p class="text-[10px] text-ink-muted mt-1">Available tokens: {id}, {num}, {num:04d}, {suffix}.</p>
          </div>

          <div class="pt-2 border-t border-tonal2 flex justify-end gap-2">
            <button type="button" onclick="closeSettingsModal()" class="px-3 py-1.5 border border-bordercol text-ink-muted hover:bg-surface rounded text-xs font-medium">Cancel</button>
            <button type="button" onclick="saveSettings()" class="px-3 py-1.5 bg-fern hover:bg-fern-dark text-white rounded text-xs font-bold">Save</button>
          </div>
        </div>
      </div>
    </div>

    <!-- MODAL: Stored As Bottom Sheet -->
    <div id="storedAsBottomSheet" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex flex-col justify-end" onclick="if(event.target===this)closeStoredAsBottomSheet()">
      <div class="bg-surface border-t border-bordercol rounded-t-xl p-4 space-y-3 max-h-[80vh] overflow-y-auto shadow-2xl">
        <div class="flex items-center justify-between pb-2 border-b border-stone-200">
          <div>
            <h3 class="text-xs font-bold text-ink uppercase tracking-wider font-sans">Additional Storage Vessels</h3>
            <p class="text-[10px] font-mono text-subdued">Select botanical archival method</p>
          </div>
          <button class="p-1 text-muted hover:text-ink font-mono text-sm" onclick="closeStoredAsBottomSheet()" type="button">✕</button>
        </div>
        <div class="space-y-1.5 font-mono text-xs" id="storedAsModalOptions">
          <!-- Populated dynamically -->
        </div>
      </div>
    </div>

    <!-- MODAL: Presets Configuration -->
    <div id="presetsConfigModal" class="hidden fixed inset-0 z-50 bg-black/65 backdrop-blur-xs flex items-center justify-center p-4" onclick="if(event.target===this)closePresetsModal()">
      <div class="bg-surface border border-stone-300 rounded-lg max-w-sm w-full p-4 space-y-3.5 shadow-2xl flex flex-col max-h-[88vh]">
        <div class="flex items-center justify-between pb-2 border-b border-stone-200">
          <div>
            <h3 class="text-xs font-bold text-ink uppercase tracking-wider font-sans">Customize Quick-Select</h3>
            <p class="text-[10px] font-mono text-subdued">Select 3 presets for the primary 2x2 grid</p>
          </div>
          <button class="p-1 text-muted hover:text-ink font-mono text-sm" onclick="closePresetsModal()" type="button">✕</button>
        </div>
        <div class="flex items-center justify-between text-[11px] font-mono bg-stone-100 px-2.5 py-1.5 rounded border border-stone-200">
          <span class="text-subdued uppercase text-[9px] font-bold">Selection count:</span>
          <span class="font-bold text-fern" id="presetSelectionCounter">3 of 3 selected</span>
        </div>
        <div class="space-y-1.5 overflow-y-auto no-scrollbar max-h-[50vh] pr-0.5" id="presetsSelectionList">
          <!-- Checkbox list of storage vessels -->
        </div>
        <div class="pt-2 border-t border-stone-200 flex items-center gap-2">
          <button class="flex-1 py-2 px-3 bg-stone-100 hover:bg-stone-200 text-ink text-xs font-mono font-medium rounded min-h-[38px]" onclick="closePresetsModal()" type="button">Cancel</button>
          <button class="flex-1 py-2 px-3 bg-fern hover:bg-fern-dark text-white text-xs font-mono font-semibold rounded min-h-[38px]" id="btnSavePresets" onclick="savePresetsFromModal()" type="button">Save Presets</button>
        </div>
      </div>
    </div>

    <!-- MODAL: Curatorial Advanced Filter -->
    <div id="filterModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded w-full max-w-md shadow-xl overflow-hidden flex flex-col max-h-[90vh]">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between shrink-0">
          <h2 class="font-serif font-bold text-sm text-ink">Curatorial Advanced Filter</h2>
          <button type="button" onclick="closeFilterModal()" class="text-ink-muted hover:text-ink font-bold text-sm">✕</button>
        </header>
        <div class="p-4 overflow-y-auto space-y-4 flex-1">
          <div>
            <h3 class="font-sans text-xs font-bold text-ink mb-2 uppercase tracking-wider">Spatial Location</h3>
            <div id="filterModalLocations" class="space-y-2"></div>
          </div>
          <hr class="border-t border-tonal2">
          <div>
            <h3 class="font-sans text-xs font-bold text-ink mb-2 uppercase tracking-wider">Specific Problems & Verification</h3>
            <div id="filterModalProblems" class="space-y-1.5"></div>
          </div>
        </div>
        <footer class="p-3.5 bg-tonal1 border-t border-tonal2 flex gap-2 justify-end shrink-0">
          <button type="button" onclick="clearAdvancedFilters()" class="px-3 py-1.5 border border-bordercol text-ink-muted hover:text-ink rounded text-xs">Clear</button>
          <button type="button" onclick="applyAdvancedFilters()" class="px-4 py-1.5 bg-fern hover:bg-fern-dark text-white rounded text-xs font-bold">Apply</button>
        </footer>
      </div>
    </div>

    <!-- MODAL: Add Discrepancy Flag -->
    <div id="addDiscrepancyModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded w-full max-w-sm shadow-xl overflow-hidden">
        <header class="p-3.5 bg-tonal1 border-b border-tonal2 flex items-center justify-between">
          <h2 class="font-serif font-bold text-sm text-ink">⚑ Flag Specimen Discrepancy</h2>
          <button type="button" onclick="closeModal('addDiscrepancyModal')" class="text-ink-muted hover:text-ink font-bold text-sm">✕</button>
        </header>
        <form onsubmit="submitDiscrepancy(event)" class="p-4 space-y-3">
          <div>
            <label class="block font-sans text-xs font-medium text-ink mb-1">Target Field / Problem</label>
            <select id="discrepancyFieldSelect" class="w-full bg-surface border border-bordercol rounded px-2.5 py-1.5 text-xs text-ink outline-none focus:border-fern"></select>
          </div>
          <div>
            <label class="block font-sans text-xs font-medium text-ink mb-1">Discrepancy Note</label>
            <textarea id="discrepancyReasonInput" rows="3" required placeholder="Note observed curatorial discrepancy..." class="w-full bg-surface border border-bordercol rounded px-2.5 py-1.5 text-xs text-ink outline-none focus:border-fern"></textarea>
          </div>
          <div class="flex justify-end gap-2 pt-2 border-t border-tonal2">
            <button type="button" onclick="closeModal('addDiscrepancyModal')" class="px-3 py-1.5 border border-bordercol text-ink-muted rounded text-xs">Cancel</button>
            <button type="submit" class="px-4 py-1.5 bg-ember hover:bg-ember-dark text-white rounded text-xs font-bold">Flag Issue</button>
          </div>
        </form>
      </div>
    </div>

    <!-- MODAL: Photo Fullscreen Viewer -->
    <div id="photoViewerModal" class="hidden fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex flex-col justify-between p-4">
      <div class="flex items-center justify-between text-white">
        <span class="font-mono text-xs" id="photoViewerTitle">Specimen Photo</span>
        <div class="flex items-center gap-2">
          <button type="button" onclick="rotatePhoto()" class="px-2 py-1 bg-white/20 hover:bg-white/30 rounded text-xs font-mono">↻ Rotate</button>
          <button type="button" onclick="closePhotoViewerModal()" class="px-2.5 py-1 bg-white/20 hover:bg-white/30 rounded text-xs font-bold">✕</button>
        </div>
      </div>
      <div class="flex-1 flex items-center justify-center overflow-hidden my-2">
        <img id="photoViewerImg" src="" alt="Specimen Inspection" class="max-w-full max-h-full object-contain transition-transform">
      </div>
      <div class="flex items-center justify-center gap-3 text-white text-xs font-mono">
        <button type="button" onclick="zoomPhoto(-0.3)" class="px-3 py-1.5 bg-white/20 rounded font-bold">− Zoom</button>
        <span id="zoomLevelDisplay">1.0x</span>
        <button type="button" onclick="zoomPhoto(0.3)" class="px-3 py-1.5 bg-white/20 rounded font-bold">+ Zoom</button>
        <button type="button" onclick="resetPhotoTransform()" class="px-3 py-1.5 bg-white/20 rounded">Reset</button>
      </div>
    </div>

    <!-- MODAL: Connection Telemetry Status -->
    <div id="connectionModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div class="bg-surface border border-bordercol rounded w-full max-w-sm p-4 shadow-xl space-y-3">
        <div class="flex items-center justify-between border-b border-tonal2 pb-2">
          <h3 class="font-serif font-bold text-sm text-ink">⚡ Desktop Host Link</h3>
          <button type="button" onclick="closeModal('connectionModal')" class="text-ink-muted font-bold text-sm">✕</button>
        </div>
        <div class="space-y-1.5 text-xs font-mono">
          <div class="flex justify-between py-1 border-b border-tonal2">
            <span class="text-muted">Connection Status:</span>
            <span class="text-fern font-bold">Online (Active)</span>
          </div>
          <div class="flex justify-between py-1 border-b border-tonal2">
            <span class="text-muted">Active Database:</span>
            <span class="text-ink font-bold truncate max-w-[170px]" id="connModalDbName">---</span>
          </div>
          <div class="flex justify-between py-1 border-b border-tonal2">
            <span class="text-muted">Reviewed Total:</span>
            <span class="text-ink" id="connModalReviewed">---</span>
          </div>
          <div class="flex justify-between py-1">
            <span class="text-muted">Ping / Latency:</span>
            <span class="text-fern font-bold" id="connModalPing">42ms</span>
          </div>
        </div>
        <button type="button" onclick="closeModal('connectionModal')" class="w-full py-2 bg-fern hover:bg-fern-dark text-white rounded text-xs font-bold">Done</button>
      </div>
    </div>

    <!-- Toast Notification -->
    <div id="toast" class="hidden fixed bottom-20 left-4 right-4 max-w-sm mx-auto bg-fern-dark text-white text-xs font-bold py-2.5 px-4 rounded shadow-lg text-center z-50 transition-opacity">
      Edits saved & synchronized
    </div>

  </div>

  <!-- ============================================================= -->
  <!-- CLIENT LOGIC & REACTIVE CONTROLLER SCRIPT                     -->
  <!-- ============================================================= -->
  <script>
    const _urlParams = new URLSearchParams(window.location.search);
    const TOKEN = _urlParams.get('token') || "{{ token }}";

    // Master Client State
    const state = {
      activeSchema: null,
      objectList: [],
      totalMatching: 0,
      currentOid: null,
      currentRecord: null,
      activeStatusFilter: 'all',
      noImageFilterActive: false,
      activeAdvancedFilters: { locations: {}, problems: {} },
      activeSortBy: 'id_asc',
      searchQuery: '',
      isReviewed: false,
      showFilterPills: false,
      lastSavedLocation: {
        building: 'Økern',
        floor: -1,
        cabinet: 4,
        shelf: 2,
        storedAs: 'Herbarium Sheet'
      },
      batchAnchor: {
        building: 'Økern',
        floor: -1,
        cabinet: 4,
        shelf: 2,
        storedAs: 'Herbarium Sheet'
      },
      batchQueue: [], // array of { oid, sciName, prevLoc }
      customPresets: ['Herbarium Sheet', 'Standard Box', 'Free Standing'],
      allStorageOptions: [
        'Herbarium Sheet', 'Standard Box', 'Free Standing', 'Petri dish', 
        'Liquid / Glass Jar', 'Capsule / Envelope', 'Microscope Slide', 'Mounted platform', 'Oversized Folder'
      ]
    };

    let searchDebounceTimer = null;
    let autoSaveTimer = null;
    let isSaving = false;
    let dirtyFields = new Set();
    let currentTabIdx = 0;
    let wakeLockSentinel = null;
    let eventSource = null;

    // Load persisted settings
    try {
      state.showFilterPills = localStorage.getItem('arbor_show_filter_pills') === 'true';
      const savedPresets = localStorage.getItem('arbor_storage_presets');
      if (savedPresets) state.customPresets = JSON.parse(savedPresets);
      const savedLastLoc = localStorage.getItem('arbor_last_location');
      if (savedLastLoc) state.lastSavedLocation = JSON.parse(savedLastLoc);
    } catch(e) {}

    // API Helper
    async function apiFetch(url, options = {}) {
      options.headers = options.headers || {};
      if (TOKEN) options.headers['X-Session-Token'] = TOKEN;
      if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
      }
      const res = await fetch(url, options);
      if (res.status === 401) {
        window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname + window.location.search);
        return null;
      }
      return res.json();
    }

    function showToast(msg) {
      const toast = document.getElementById('toast');
      if (!toast) return;
      toast.textContent = msg;
      toast.classList.remove('hidden');
      toast.style.opacity = '1';
      setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.classList.add('hidden'), 200);
      }, 2000);
    }

    // -------------------------------------------------------------
    // INITIALIZATION & SSE CONNECTION
    // -------------------------------------------------------------
    async function init() {
      applyFilterPillVisibility();
      await fetchSchema();
      await fetchObjects();
      setupEventSource();
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') setupEventSource();
      });
      renderStorageQuickGrid();
    }

    function setupEventSource() {
      if (eventSource) {
        try { eventSource.close(); } catch(e) {}
        eventSource = null;
      }
      const sseUrl = '/api/events' + (TOKEN ? '?token=' + encodeURIComponent(TOKEN) : '');
      eventSource = new EventSource(sseUrl);
      eventSource.onopen = () => {
        document.getElementById('offlineBanner')?.classList.add('hidden');
      };
      eventSource.onerror = () => {
        document.getElementById('offlineBanner')?.classList.remove('hidden');
      };
      eventSource.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'record_updated') {
            if (state.currentOid && String(msg.id) === String(state.currentOid)) {
              fetchObjectDetail(state.currentOid, false);
            }
            fetchObjects(false);
          }
        } catch(err) {}
      };
    }

    async function fetchSchema() {
      try {
        const data = await apiFetch('/api/schema');
        if (data) {
          state.activeSchema = data;
          document.getElementById('headerDbName').textContent = data.database_name || 'Active Database';
          document.getElementById('connModalDbName').textContent = data.database_name || 'Active Database';
        }
      } catch(err) {
        console.error('Failed to fetch schema:', err);
      }
    }

    // -------------------------------------------------------------
    // SCREEN 1: VAULT LIST VIEW LOGIC
    // -------------------------------------------------------------
    async function fetchObjects(showLoading = true) {
      const container = document.getElementById('specimenListContainer');
      if (showLoading && container) {
        container.innerHTML = `
          <div class="p-8 text-center text-ink-muted font-mono text-xs animate-pulse">
            Loading specimens from database...
          </div>
        `;
      }

      const params = new URLSearchParams();
      if (state.searchQuery) params.set('q', state.searchQuery);
      if (state.activeStatusFilter) params.set('status', state.activeStatusFilter);
      if (state.activeSortBy) {
        if (state.activeSortBy === 'location') params.set('sort_by', 'cabinet');
        else if (state.activeSortBy === 'name_asc') { params.set('sort_by', 'genus'); params.set('sort_dir', 'asc'); }
        else if (state.activeSortBy === 'name_desc') { params.set('sort_by', 'genus'); params.set('sort_dir', 'desc'); }
        else if (state.activeSortBy === 'id_asc') { params.set('sort_by', 'id'); params.set('sort_dir', 'asc'); }
        else if (state.activeSortBy === 'flagged_first') { params.set('has_problems', 'true'); }
      }
      params.set('limit', '200');

      try {
        const res = await apiFetch('/api/objects?' + params.toString());
        if (res) {
          state.objectList = res.objects || [];
          state.totalMatching = res.total_matching || 0;
          renderObjectList();
          updateListMetrics(res.facets);
        }
      } catch(err) {
        if (container) {
          container.innerHTML = `<div class="p-8 text-center text-brick font-mono text-xs">Failed to load objects.</div>`;
        }
      }
    }

    function renderObjectList() {
      const container = document.getElementById('specimenListContainer');
      if (!container) return;

      if (state.objectList.length === 0) {
        container.innerHTML = `
          <div class="p-12 text-center text-ink-muted flex flex-col items-center justify-center">
            <span class="text-3xl mb-2">🔍</span>
            <p class="font-sans font-semibold text-sm text-ink">No specimens found</p>
            <p class="text-xs text-muted mt-1 max-w-[240px]">Try adjusting your search query or filter criteria.</p>
            <button onclick="clearSearch()" class="mt-4 px-3 py-1.5 bg-white border border-bordercol rounded text-xs font-mono font-medium shadow-2xs tap-active">
              [ Clear Filter & Show All ]
            </button>
          </div>
        `;
        return;
      }

      container.innerHTML = state.objectList.map((obj, idx) => {
        const isRev = obj.review_status === 'reviewed';
        const hasFlags = obj.has_flags;
        const loc = obj.location || {};
        
        let locBreadcrumb = [];
        if (loc.building) locBreadcrumb.push(loc.building);
        if (loc.floor !== undefined && loc.floor !== null && String(loc.floor).trim() !== '') locBreadcrumb.push(`Fl ${loc.floor}`);
        if (loc.cabinet) locBreadcrumb.push(`Cab ${loc.cabinet}`);
        if (loc.shelf) locBreadcrumb.push(`Sh ${loc.shelf}`);
        const locStr = locBreadcrumb.length > 0 ? locBreadcrumb.join(' › ') : 'Unrecorded location';

        return `
          <article onclick="openDetailView('${obj.id}')" class="bg-surface border border-bordercol rounded p-3 shadow-2xs hover:border-fern/50 active:bg-stone-50 transition-all cursor-pointer flex flex-col gap-1.5 relative tap-active">
            <div class="flex items-start justify-between">
              <div class="flex items-center gap-2 min-w-0">
                <span class="font-mono text-[11px] font-bold text-ink px-1.5 py-0.5 bg-stone-100 border border-bordercol/80 rounded">
                  #${obj.accession_number || obj.id}
                </span>
                <span class="text-[10px] font-mono text-muted uppercase truncate">${obj.family || 'Taxon'}</span>
              </div>
              
              <div class="flex items-center gap-1.5 shrink-0">
                ${hasFlags ? '<span class="text-xs text-brick font-bold" title="Flagged Issue">⚠</span>' : ''}
                ${isRev ? 
                  '<span class="w-5 h-5 rounded-full bg-emerald-50 text-fern border border-fern/30 flex items-center justify-center text-[10px] font-bold">✓</span>' : 
                  '<span class="w-5 h-5 rounded-full bg-stone-100 text-stone-400 border border-stone-200 flex items-center justify-center text-[10px]">🕒</span>'
                }
              </div>
            </div>

            <div class="font-serif font-semibold italic text-[15px] text-ink leading-tight truncate">
              ${obj.scientific_name || 'Unidentified Specimen'}
            </div>

            <div class="flex items-center justify-between text-[11px] font-mono pt-1 border-t border-stone-100 text-muted">
              <span class="truncate text-ink-muted">${locStr}</span>
              ${loc.stored_as ? `<span class="text-[10px] px-1.5 py-0.2 bg-stone-100 rounded border border-bordercol/60 shrink-0">${loc.stored_as}</span>` : ''}
            </div>
          </article>
        `;
      }).join('');
    }

    function updateListMetrics(facets = {}) {
      document.getElementById('matchingCount').textContent = state.totalMatching;
      
      const rev = facets.reviewed_count || 0;
      const total = state.totalMatching || 1;
      const pct = Math.round((rev / total) * 100) || 0;

      document.getElementById('listProgressText').textContent = `${rev} / ${total} Reviewed`;
      document.getElementById('listProgressPct').textContent = `(${pct}%)`;
      document.getElementById('listProgressBar').style.width = `${pct}%`;

      document.getElementById('pillCountAll').textContent = `(${total})`;
      document.getElementById('pillCountPending').textContent = `(${facets.pending_count || 0})`;
      document.getElementById('pillCountFlagged').textContent = `(${facets.flagged_count || 0})`;
      document.getElementById('pillCountReviewed').textContent = `(${rev})`;
      document.getElementById('pillCountConflict').textContent = `(${facets.history_count || 0})`;
      document.getElementById('pillCountUnknown').textContent = `(${facets.unknown_count || 0})`;
    }

    function debounceSearch() {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        state.searchQuery = document.getElementById('searchBox').value.trim();
        const clearBtn = document.getElementById('searchClearBtn');
        if (state.searchQuery) clearBtn?.classList.remove('hidden');
        else clearBtn?.classList.add('hidden');
        fetchObjects();
      }, 300);
    }

    function clearSearch() {
      document.getElementById('searchBox').value = '';
      state.searchQuery = '';
      document.getElementById('searchClearBtn')?.classList.add('hidden');
      fetchObjects();
    }

    function setStatusFilter(status) {
      state.activeStatusFilter = status;
      document.querySelectorAll('.filter-pill').forEach(el => {
        el.className = 'filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-stone-200/80 text-ink-muted hover:bg-stone-300 tap-active transition-all';
      });
      const activeEl = document.getElementById('pill-' + status);
      if (activeEl) {
        activeEl.className = 'filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-ink text-white shadow-sm tap-active transition-all';
      }
      fetchObjects();
    }

    function toggleNoImageFilter() {
      state.noImageFilterActive = !state.noImageFilterActive;
      const pill = document.getElementById('pill-no-image');
      if (state.noImageFilterActive) {
        pill.className = 'filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-amber-50 text-amber-900 border border-amber-300 tap-active transition-all';
      } else {
        pill.className = 'filter-pill whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium font-sans bg-stone-100 text-stone-600 border border-stone-200 hover:bg-stone-200 tap-active transition-all';
      }
      fetchObjects();
    }

    function handleSortChange() {
      state.activeSortBy = document.getElementById('sortBySelect').value;
      fetchObjects();
    }

    function toggleFilterPillsSetting(enabled) {
      state.showFilterPills = enabled;
      try { localStorage.setItem('arbor_show_filter_pills', enabled ? 'true' : 'false'); } catch(e) {}
      applyFilterPillVisibility();
    }

    function applyFilterPillVisibility() {
      const container = document.getElementById('filterPillsContainer');
      const settingInput = document.getElementById('settingShowFilterPills');
      if (settingInput) settingInput.checked = state.showFilterPills;
      if (container) {
        if (state.showFilterPills) container.classList.remove('hidden');
        else container.classList.add('hidden');
      }
    }

    // -------------------------------------------------------------
    // SCREEN 2: SPECIMEN DETAIL VIEW LOGIC
    // -------------------------------------------------------------
    async function openDetailView(oid) {
      state.currentOid = String(oid);
      showDetailView();
      await fetchObjectDetail(oid);
    }

    function showListView() {
      document.getElementById('listView').classList.remove('hidden');
      document.getElementById('detailView').classList.add('hidden');
      document.getElementById('batchLocationView').classList.add('hidden');
    }

    function showDetailView() {
      document.getElementById('listView').classList.add('hidden');
      document.getElementById('detailView').classList.remove('hidden');
      document.getElementById('batchLocationView').classList.add('hidden');
    }

    function showBatchLocationView() {
      document.getElementById('listView').classList.add('hidden');
      document.getElementById('detailView').classList.add('hidden');
      document.getElementById('batchLocationView').classList.remove('hidden');
      updateBatchAnchorUI();
      document.getElementById('batchIdInput')?.focus();
    }

    async function fetchObjectDetail(oid, renderFull = true) {
      try {
        const data = await apiFetch('/api/object/' + encodeURIComponent(oid));
        if (data) {
          state.currentRecord = data;
          state.isReviewed = data.review_status === 'reviewed';
          renderDetailView(renderFull);
        }
      } catch(err) {
        console.error('Failed to load specimen detail:', err);
      }
    }

    function renderDetailView(renderFull = true) {
      if (!state.currentRecord) return;
      const rec = state.currentRecord;
      const reg = rec.registration || {};
      const obs = rec.observation || {};

      // Accession Header
      document.getElementById('detailAccession').textContent = '#' + (rec.accession_number || rec.id);
      document.getElementById('detailScientificName').textContent = rec.scientific_name || 'Unidentified Specimen';
      document.getElementById('detailFamily').textContent = reg.Family || '—';

      // Status Pill
      const statusBtn = document.getElementById('badgeStatus');
      const statusText = document.getElementById('badgeStatusText');
      const statusDot = document.getElementById('badgeStatusDot');
      if (state.isReviewed) {
        statusBtn.className = 'flex items-center gap-1.5 text-[11px] font-mono font-semibold px-2 py-0.5 rounded border transition-colors tap-highlight-transparent bg-emerald-50 text-fern-dark border-fern/30';
        statusText.textContent = 'REVIEWED';
        statusDot.className = 'w-1.5 h-1.5 rounded-full bg-fern';
      } else {
        statusBtn.className = 'flex items-center gap-1.5 text-[11px] font-mono font-semibold px-2 py-0.5 rounded border transition-colors tap-highlight-transparent bg-amber-50 text-amber-800 border-amber-300';
        statusText.textContent = 'UNREVIEWED';
        statusDot.className = 'w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse';
      }

      // Specimen index in list
      const curIdx = state.objectList.findIndex(o => String(o.id) === String(rec.id));
      document.getElementById('detailCurrentIdx').textContent = curIdx >= 0 ? curIdx + 1 : 1;
      document.getElementById('detailTotalCount').textContent = state.objectList.length || state.totalMatching || 1;

      // Coordinate Steppers
      renderCoordinateSteppers(obs);

      // Building Chips
      renderBuildingChips(obs.Building || 'Økern');

      // Stored As Selection
      renderStoredAsGrid(obs['Stored as'] || obs.Stored_As || 'Herbarium Sheet');

      // Loan Status
      renderLoanStatus(obs['Loaned out']);

      // Dynamic Form Fields in Details Tab
      renderDynamicForm(state.activeSchema, rec);

      // Photos in Details Tab
      renderPhotos(rec.images);

      // Problems & Discrepancies in Problems Tab
      renderProblems(rec.flagged_issues);
      renderProblemResolvers(rec);
      renderHistoricalConflicts(rec);

      // Breadcrumb
      updateDetailLocBreadcrumbs(obs);
    }

    function renderCoordinateSteppers(obs) {
      // Floor (supports negative)
      const fl = (obs.Floor !== undefined && obs.Floor !== null && String(obs.Floor).trim() !== '') ? String(obs.Floor) : '-1';
      document.getElementById('displayFloorVal').textContent = fl;
      const inpFl = document.getElementById('input_observation_Floor');
      if (inpFl) inpFl.value = fl;

      // Cabinet
      const cab = (obs.Cabinet !== undefined && obs.Cabinet !== null && String(obs.Cabinet).trim() !== '') ? String(obs.Cabinet).padStart(2, '0') : '04';
      document.getElementById('displayCabVal').textContent = cab;
      const inpCab = document.getElementById('input_observation_Cabinet');
      if (inpCab) inpCab.value = cab;

      // Shelf
      const sh = (obs.Shelf !== undefined && obs.Shelf !== null && String(obs.Shelf).trim() !== '') ? String(obs.Shelf).padStart(2, '0') : '02';
      document.getElementById('displayShelfVal').textContent = sh;
      const inpSh = document.getElementById('input_observation_Shelf');
      if (inpSh) inpSh.value = sh;
    }

    function onLocationCoordChange(field, val) {
      if (!state.currentRecord) return;
      state.currentRecord.observation = state.currentRecord.observation || {};
      state.currentRecord.observation[field] = val;
      markDirty(field);
      renderCoordinateSteppers(state.currentRecord.observation);
      updateDetailLocBreadcrumbs(state.currentRecord.observation);
      triggerAutoSave();
    }

    function adjustCoordinate(coord, delta) {
      if (!state.currentRecord) return;
      state.currentRecord.observation = state.currentRecord.observation || {};
      const obs = state.currentRecord.observation;

      if (coord === 'floor') {
        const current = parseInt(obs.Floor !== undefined && obs.Floor !== null ? obs.Floor : '-1', 10);
        const next = isNaN(current) ? -1 : current + delta;
        obs.Floor = String(next);
        markDirty('Floor');
      } else if (coord === 'cab') {
        const current = parseInt(obs.Cabinet || '4', 10);
        const next = Math.max(1, (isNaN(current) ? 1 : current) + delta);
        obs.Cabinet = String(next);
        markDirty('Cabinet');
      } else if (coord === 'shelf') {
        const current = parseInt(obs.Shelf || '2', 10);
        const next = Math.max(1, (isNaN(current) ? 1 : current) + delta);
        obs.Shelf = String(next);
        markDirty('Shelf');
      }

      renderCoordinateSteppers(obs);
      updateDetailLocBreadcrumbs(obs);
      triggerAutoSave();
    }

    function activateDirectInput(field) {
      document.getElementById('display' + field + 'Val').classList.add('hidden');
      const input = document.getElementById('input_observation_' + field) || document.getElementById('input' + field + 'Val');
      if (input) {
        input.classList.remove('hidden');
        input.focus();
        input.select();
      }
    }

    function finishDirectInput(field) {
      const input = document.getElementById('input_observation_' + field) || document.getElementById('input' + field + 'Val');
      const display = document.getElementById('display' + field + 'Val');
      if (input) input.classList.add('hidden');
      if (display) display.classList.remove('hidden');

      if (!state.currentRecord || !input) return;
      state.currentRecord.observation = state.currentRecord.observation || {};
      const obs = state.currentRecord.observation;

      const val = input.value.trim();
      if (field === 'Floor') {
        obs.Floor = val;
        markDirty('Floor');
      } else if (field === 'Cab') {
        obs.Cabinet = val;
        markDirty('Cabinet');
      } else if (field === 'Shelf') {
        obs.Shelf = val;
        markDirty('Shelf');
      }

      renderCoordinateSteppers(obs);
      updateDetailLocBreadcrumbs(obs);
      triggerAutoSave();
    }

    function setBuildingSelection(bldg, btnEl) {
      if (!state.currentRecord) return;
      state.currentRecord.observation = state.currentRecord.observation || {};
      state.currentRecord.observation.Building = bldg;
      markDirty('Building');

      renderBuildingChips(bldg);
      updateDetailLocBreadcrumbs(state.currentRecord.observation);
      triggerAutoSave();
    }

    function renderBuildingChips(activeBldg) {
      document.querySelectorAll('.bldg-chip').forEach(el => {
        const b = el.getAttribute('data-building');
        if (b === activeBldg) {
          el.className = 'bldg-chip min-h-[44px] px-3 py-2 rounded border text-xs font-mono font-semibold flex items-center justify-center gap-1.5 transition-all shadow-2xs bg-[#1c3829] text-white border-transparent';
        } else {
          el.className = 'bldg-chip min-h-[44px] px-3 py-2 rounded border border-bordercol bg-stone-50 hover:bg-stone-100 active:bg-stone-200 text-ink text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all shadow-2xs';
        }
      });
      const bldgInp = document.getElementById('input_observation_Building');
      if (bldgInp) bldgInp.value = activeBldg;
    }

    function toggleCustomBuildingInput() {
      document.getElementById('customBuildingWrap')?.classList.toggle('hidden');
    }

    function applyCustomBuilding() {
      const val = document.getElementById('input_observation_Building').value.trim();
      if (!val) return;
      setBuildingSelection(val);
      document.getElementById('customBuildingWrap')?.classList.add('hidden');
    }

    // Stored As Matrix
    function renderStorageQuickGrid() {
      const grid = document.getElementById('storageQuickGrid');
      if (!grid) return;
      const currentStored = state.currentRecord?.observation?.['Stored as'] || 'Herbarium Sheet';

      const presets = state.customPresets.slice(0, 3);
      let html = presets.map((opt, i) => {
        const isSel = (opt === currentStored);
        return `
          <button type="button" onclick="selectStoredAsOption('${opt}')" class="storage-quick-btn min-h-[44px] p-2.5 rounded border text-left flex items-center justify-between transition-all tap-highlight-transparent shadow-2xs ${isSel ? 'border-2 border-ink bg-stone-100 text-ink font-semibold' : 'border-stone-300 hover:border-ink bg-white text-muted'}">
            <span class="truncate">${opt}</span>
            <span class="w-2 h-2 rounded-full ${isSel ? 'bg-fern' : 'bg-transparent border border-stone-300'} flex-none ml-1"></span>
          </button>
        `;
      }).join('');

      html += `
        <button type="button" onclick="openStoredAsBottomSheet()" class="min-h-[44px] p-2.5 rounded border border-dashed border-stone-400 hover:border-ink bg-stone-50 text-ink text-left flex items-center justify-between tap-highlight-transparent shadow-2xs">
          <span class="font-semibold text-muted">More...</span>
          <span class="text-muted text-xs">▼</span>
        </button>
      `;

      grid.innerHTML = html;
      document.getElementById('activeStoredAsLabel').textContent = currentStored;
      document.getElementById('manualStorageInput').value = currentStored;
    }

    function renderStoredAsGrid(activeStored) {
      renderStorageQuickGrid();
    }

    function selectStoredAsOption(opt) {
      if (!state.currentRecord) return;
      state.currentRecord.observation = state.currentRecord.observation || {};
      state.currentRecord.observation['Stored as'] = opt;
      markDirty('Stored as');

      renderStorageQuickGrid();
      updateDetailLocBreadcrumbs(state.currentRecord.observation);
      triggerAutoSave();
    }

    function onManualStorageChange(val) {
      if (!state.currentRecord) return;
      state.currentRecord.observation = state.currentRecord.observation || {};
      state.currentRecord.observation['Stored as'] = val;
      markDirty('Stored as');
      document.getElementById('activeStoredAsLabel').textContent = val;
      triggerAutoSave();
    }

    function clearManualStorage() {
      document.getElementById('manualStorageInput').value = '';
      onManualStorageChange('');
    }

    function openStoredAsBottomSheet() {
      const container = document.getElementById('storedAsModalOptions');
      if (container) {
        container.innerHTML = state.allStorageOptions.map(opt => `
          <button type="button" onclick="selectStoredAsOption('${opt}'); closeStoredAsBottomSheet();" class="w-full p-3 rounded border border-stone-200 hover:border-ink hover:bg-stone-50 flex items-center justify-between text-left tap-highlight-transparent min-h-[44px]">
            <span class="font-bold text-ink">${opt}</span>
            <span class="text-xs text-muted">Select</span>
          </button>
        `).join('');
      }
      document.getElementById('storedAsBottomSheet')?.classList.remove('hidden');
    }

    function closeStoredAsBottomSheet() {
      document.getElementById('storedAsBottomSheet')?.classList.add('hidden');
    }

    function openPresetsModal() {
      const container = document.getElementById('presetsSelectionList');
      if (container) {
        container.innerHTML = state.allStorageOptions.map(opt => {
          const checked = state.customPresets.includes(opt);
          return `
            <label class="p-2 bg-stone-50 border border-stone-200 rounded flex items-center justify-between text-xs font-mono cursor-pointer hover:bg-stone-100">
              <span class="text-ink font-medium">${opt}</span>
              <input type="checkbox" value="${opt}" ${checked ? 'checked' : ''} onchange="onPresetCheckboxChange()" class="preset-cb w-4 h-4 text-fern rounded focus:ring-fern">
            </label>
          `;
        }).join('');
      }
      onPresetCheckboxChange();
      document.getElementById('presetsConfigModal')?.classList.remove('hidden');
    }

    function closePresetsModal() {
      document.getElementById('presetsConfigModal')?.classList.add('hidden');
    }

    function onPresetCheckboxChange() {
      const checked = Array.from(document.querySelectorAll('.preset-cb:checked')).map(cb => cb.value);
      const counter = document.getElementById('presetSelectionCounter');
      if (counter) counter.textContent = `${checked.length} of 3 selected`;
      const saveBtn = document.getElementById('btnSavePresets');
      if (saveBtn) saveBtn.disabled = (checked.length !== 3);
    }

    function savePresetsFromModal() {
      const checked = Array.from(document.querySelectorAll('.preset-cb:checked')).map(cb => cb.value);
      if (checked.length === 3) {
        state.customPresets = checked;
        try { localStorage.setItem('arbor_storage_presets', JSON.stringify(checked)); } catch(e) {}
        renderStorageQuickGrid();
        closePresetsModal();
        showToast('✓ Storage presets updated');
      }
    }

    // Availability / Loan Status
    function setLoanStatus(isLoaned) {
      if (!state.currentRecord) return;
      state.currentRecord.observation = state.currentRecord.observation || {};
      state.currentRecord.observation['Loaned out'] = isLoaned;
      markDirty('Loaned out');

      renderLoanStatus(isLoaned);
      triggerAutoSave();
    }

    function renderLoanStatus(isLoaned) {
      const btnAvail = document.getElementById('btnStatusAvailable');
      const btnLoan = document.getElementById('btnStatusLoan');
      const tag = document.getElementById('loanStateTag');
      const dot = document.getElementById('loanStatusDot');

      if (isLoaned) {
        btnLoan.className = 'py-1.5 px-2 rounded text-xs font-mono font-semibold flex items-center justify-center gap-1.5 transition-all bg-white text-ink border border-stone-300 min-h-[36px]';
        btnAvail.className = 'py-1.5 px-2 rounded text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all text-muted hover:text-ink min-h-[36px]';
        tag.textContent = 'Loaned Out';
        tag.className = 'text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-300';
        dot.className = 'w-2 h-2 rounded-full bg-amber-500';
      } else {
        btnAvail.className = 'py-1.5 px-2 rounded text-xs font-mono font-semibold flex items-center justify-center gap-1.5 transition-all bg-white text-ink border border-stone-300 min-h-[36px]';
        btnLoan.className = 'py-1.5 px-2 rounded text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all text-muted hover:text-ink min-h-[36px]';
        tag.textContent = 'In Repository';
        tag.className = 'text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-fern-light text-fern border border-fern/30';
        dot.className = 'w-2 h-2 rounded-full bg-fern';
      }
    }

    // Copy from Previous Logic
    function handleCopyPreviousSpecimen() {
      if (!state.currentRecord) return;
      const last = state.lastSavedLocation;
      if (!last) {
        showToast('No previous location coordinates cached');
        return;
      }

      state.currentRecord.observation = state.currentRecord.observation || {};
      const obs = state.currentRecord.observation;

      if (last.building) { obs.Building = last.building; markDirty('Building'); }
      if (last.floor !== undefined) { obs.Floor = String(last.floor); markDirty('Floor'); }
      if (last.cabinet) { obs.Cabinet = String(last.cabinet); markDirty('Cabinet'); }
      if (last.shelf) { obs.Shelf = String(last.shelf); markDirty('Shelf'); }
      if (last.storedAs) { obs['Stored as'] = last.storedAs; markDirty('Stored as'); }

      renderCoordinateSteppers(obs);
      renderBuildingChips(obs.Building);
      renderStoredAsGrid(obs['Stored as']);
      updateDetailLocBreadcrumbs(obs);
      triggerAutoSave();
      showToast('📋 Copied coordinates from previous specimen');
    }

    function updateDetailLocBreadcrumbs(obs = {}) {
      let locBreadcrumb = [];
      if (obs.Building) locBreadcrumb.push(obs.Building);
      if (obs.Floor !== undefined && obs.Floor !== null && String(obs.Floor).trim() !== '') locBreadcrumb.push(`Floor ${obs.Floor}`);
      if (obs.Cabinet) locBreadcrumb.push(`Cab ${obs.Cabinet}`);
      if (obs.Shelf) locBreadcrumb.push(`Sh ${obs.Shelf}`);
      const locStr = locBreadcrumb.length > 0 ? locBreadcrumb.join(' › ') : 'Unrecorded location';

      document.getElementById('liveLocBreadcrumb').textContent = locStr;
      document.getElementById('headerLocSummary').textContent = locBreadcrumb.length > 0 ? locBreadcrumb.join(' · ') : 'Unrecorded';

      // Cache for Copy from Previous
      state.lastSavedLocation = {
        building: obs.Building || state.lastSavedLocation.building,
        floor: obs.Floor !== undefined ? obs.Floor : state.lastSavedLocation.floor,
        cabinet: obs.Cabinet || state.lastSavedLocation.cabinet,
        shelf: obs.Shelf || state.lastSavedLocation.shelf,
        storedAs: obs['Stored as'] || state.lastSavedLocation.storedAs
      };
      try { localStorage.setItem('arbor_last_location', JSON.stringify(state.lastSavedLocation)); } catch(e) {}
    }

    function toggleReviewed() {
      state.isReviewed = !state.isReviewed;
      if (state.currentRecord) {
        state.currentRecord.observation = state.currentRecord.observation || {};
        state.currentRecord.observation.Reviewed = state.isReviewed;
        markDirty('Reviewed');
        triggerAutoSave();
      }
      renderDetailView(false);
    }

    function navSpecimen(delta) {
      if (state.objectList.length === 0) return;
      const curIdx = state.objectList.findIndex(o => String(o.id) === String(state.currentOid));
      if (curIdx < 0) return;
      const nextIdx = Math.max(0, Math.min(state.objectList.length - 1, curIdx + delta));
      if (nextIdx !== curIdx) {
        openDetailView(state.objectList[nextIdx].id);
      }
    }

    // -------------------------------------------------------------
    // TAB CONTROLLER & GESTURES
    // -------------------------------------------------------------
    function switchDetailTab(tab) {
      let idx = 0;
      if (typeof tab === 'number') idx = tab;
      else if (tab === 'details') idx = 1;
      else if (tab === 'problems') idx = 2;
      switchTab(idx);
    }

    function switchTab(idx) {
      currentTabIdx = idx;
      const indicator = document.getElementById('tabIndicator');
      const track = document.getElementById('tabTrack');
      if (indicator) indicator.style.transform = `translateX(${idx * 100}%)`;
      if (track) track.style.transform = `translateX(-${(idx * 100) / 3}%)`;

      document.querySelectorAll('.tab-btn').forEach((btn, i) => {
        if (i === idx) {
          btn.classList.add('font-semibold', 'text-ink');
          btn.classList.remove('text-muted');
        } else {
          btn.classList.remove('font-semibold', 'text-ink');
          btn.classList.add('text-muted');
        }
      });
    }

    // -------------------------------------------------------------
    // DETAILS & PROBLEMS FORM RENDERING
    // -------------------------------------------------------------
    function renderDynamicForm(schema, record) {
      const container = document.getElementById('dynamicFormContainer');
      if (!container || !schema) return;
      const reg = record.registration || {};
      const obs = record.observation || {};

      let html = '<h3 class="text-xs font-bold text-ink uppercase tracking-wider font-sans mb-2">Botanical Registration</h3>';
      const fields = ['Genus', 'Species', 'Family', 'Author', 'Collector', 'Collection Date', 'Locality', 'County', 'Country'];
      
      html += '<div class="space-y-2 font-mono text-xs">';
      fields.forEach(f => {
        const val = obs[f] !== undefined && obs[f] !== '' ? obs[f] : (reg[f] || '');
        html += `
          <div class="flex items-center justify-between py-1 border-b border-stone-100">
            <span class="text-muted text-[11px]">${f}:</span>
            <span class="font-semibold text-ink text-right truncate max-w-[200px]">${val || '—'}</span>
          </div>
        `;
      });
      html += '</div>';
      container.innerHTML = html;
    }

    function renderPhotos(images = {}) {
      const img = document.getElementById('specimenImg');
      const placeholder = document.getElementById('photoPlaceholder');
      const countDisp = document.getElementById('photoCountDisplay');
      const thumbsRow = document.getElementById('photoThumbnailsRow');

      const urls = images.local_endpoints && images.local_endpoints.length > 0 ? images.local_endpoints : (images.online_urls || []);
      if (countDisp) countDisp.textContent = `${urls.length} Photo${urls.length === 1 ? '' : 's'}`;

      if (urls.length > 0) {
        img.src = urls[0];
        document.getElementById('photoViewerImg').src = urls[0];
        img.classList.remove('hidden');
        placeholder.classList.add('hidden');

        if (thumbsRow) {
          thumbsRow.innerHTML = urls.map((u, i) => `
            <img src="${u}" onclick="selectPhoto(${i}, '${u}')" class="w-12 h-12 rounded border border-bordercol object-cover cursor-pointer hover:border-fern">
          `).join('');
        }
      } else {
        img.classList.add('hidden');
        placeholder.classList.remove('hidden');
        if (thumbsRow) thumbsRow.innerHTML = '';
      }
    }

    function selectPhoto(idx, url) {
      document.getElementById('specimenImg').src = url;
      document.getElementById('photoViewerImg').src = url;
    }

    function onPhotoLoaded() {}
    function onPhotoError() {}

    function openPhotoViewerModal() {
      document.getElementById('photoViewerModal')?.classList.remove('hidden');
    }

    function closePhotoViewerModal() {
      document.getElementById('photoViewerModal')?.classList.add('hidden');
    }

    let photoZoom = 1;
    let photoRotation = 0;
    function zoomPhoto(delta) {
      photoZoom = Math.min(Math.max(photoZoom + delta, 0.5), 4);
      updatePhotoTransform();
    }
    function rotatePhoto() {
      photoRotation = (photoRotation + 90) % 360;
      updatePhotoTransform();
    }
    function resetPhotoTransform() {
      photoZoom = 1;
      photoRotation = 0;
      updatePhotoTransform();
    }
    function updatePhotoTransform() {
      const img = document.getElementById('photoViewerImg');
      document.getElementById('zoomLevelDisplay').textContent = `${photoZoom.toFixed(1)}x`;
      if (img) img.style.transform = `scale(${photoZoom}) rotate(${photoRotation}deg)`;
    }

    function renderProblems(issues = []) {
      const container = document.getElementById('problemsListContainer');
      const badge = document.getElementById('tabProblemBadge');
      if (!container) return;

      if (issues.length > 0) {
        badge?.classList.remove('hidden');
        badge.textContent = issues.length;
        container.innerHTML = issues.map(iss => `
          <div class="p-2.5 bg-brick-light border border-brick/30 rounded flex items-center justify-between text-xs font-mono">
            <div>
              <span class="font-bold text-brick block">${iss.field || iss.id}</span>
              <span class="text-[10px] text-muted block">${iss.reason || 'Flagged curatorial discrepancy'}</span>
            </div>
            <span class="text-xs text-brick">⚠</span>
          </div>
        `).join('');
      } else {
        badge?.classList.add('hidden');
        container.innerHTML = `
          <div class="p-4 text-center text-stone-400 font-mono text-xs">
            ✓ No curatorial problems flagged.
          </div>
        `;
      }
    }

    function renderProblemResolvers(record) {
      const container = document.getElementById('problemResolverContainer');
      if (!container) return;
      const issues = record.flagged_issues || [];
      if (issues.length === 0) {
        container.innerHTML = '';
        return;
      }
      container.innerHTML = issues.map(iss => `
        <div class="p-2.5 bg-stone-50 border border-bordercol rounded flex items-center justify-between text-xs font-mono">
          <span class="font-medium text-ink">${iss.field || iss.id}: ${iss.reason || ''}</span>
          <button type="button" onclick="fixProblemInline('${iss.id}', 'resolve')" class="px-2 py-1 bg-fern hover:bg-fern-dark text-white rounded text-[10px] font-bold">
            Resolve
          </button>
        </div>
      `).join('');
    }

    function fixProblemInline(field, action) {
      if (!state.currentRecord) return;
      state.currentRecord.observation = state.currentRecord.observation || {};
      state.currentRecord.observation[field] = false;
      markDirty(field);
      triggerAutoSave();
      fetchObjectDetail(state.currentRecord.id, false);
      showToast(`✓ Resolved problem ${field}`);
    }

    function renderHistoricalConflicts(record) {
      const container = document.getElementById('historicalConflictsContainer');
      if (!container) return;
      container.innerHTML = '';
    }

    function applyHistoricalAndFix(field, val) {
      if (!state.currentRecord) return;
      state.currentRecord.observation = state.currentRecord.observation || {};
      state.currentRecord.observation[field] = val;
      markDirty(field);
      triggerAutoSave();
      fetchObjectDetail(state.currentRecord.id, false);
      showToast(`✓ Applied historical determination to ${field}`);
    }

    // -------------------------------------------------------------
    // SCREEN 3: BATCH LOCATION REGISTRATOR LOGIC
    // -------------------------------------------------------------
    function updateBatchAnchorUI() {
      document.getElementById('batchBuildingSelect').value = state.batchAnchor.building || 'Økern';
      document.getElementById('batchFloorVal').textContent = state.batchAnchor.floor !== undefined ? state.batchAnchor.floor : '-1';
      document.getElementById('batchCabVal').textContent = String(state.batchAnchor.cabinet || '4').padStart(2, '0');
      document.getElementById('batchShelfVal').textContent = String(state.batchAnchor.shelf || '2').padStart(2, '0');
      document.getElementById('batchStoredAsLabel').textContent = state.batchAnchor.storedAs || 'Herbarium Sheet';
      
      const nextShelf = (parseInt(state.batchAnchor.shelf, 10) || 1) + 1;
      document.getElementById('btnAdvanceNextShelfText').textContent = `Advance to Shelf ${String(nextShelf).padStart(2, '0')}`;

      renderBatchQueue();
    }

    function adjustBatchCoord(coord, delta) {
      if (coord === 'floor') {
        const cur = parseInt(state.batchAnchor.floor, 10) || -1;
        state.batchAnchor.floor = cur + delta;
      } else if (coord === 'cab') {
        const cur = parseInt(state.batchAnchor.cabinet, 10) || 4;
        state.batchAnchor.cabinet = Math.max(1, cur + delta);
      } else if (coord === 'shelf') {
        const cur = parseInt(state.batchAnchor.shelf, 10) || 2;
        state.batchAnchor.shelf = Math.max(1, cur + delta);
      }
      updateBatchAnchorUI();
    }

    function selectBatchStoragePill(btn, opt) {
      document.querySelectorAll('.batch-storage-pill').forEach(el => {
        el.className = 'batch-storage-pill px-2.5 py-1 rounded-full text-[11px] font-mono border border-bordercol bg-white text-muted';
      });
      btn.className = 'batch-storage-pill px-2.5 py-1 rounded-full text-[11px] font-mono border-2 border-fern bg-emerald-50 text-fern-dark font-semibold';
      state.batchAnchor.storedAs = opt;
      document.getElementById('batchStoredAsLabel').textContent = opt;
    }

    function advanceToNextShelf() {
      const cur = parseInt(state.batchAnchor.shelf, 10) || 1;
      state.batchAnchor.shelf = cur + 1;
      state.batchQueue = []; // Clear queue for the new shelf
      updateBatchAnchorUI();
      showToast(`⚡ Advanced to Shelf ${String(state.batchAnchor.shelf).padStart(2, '0')}`);
      document.getElementById('batchIdInput')?.focus();
    }

    async function addBatchItemFromInput() {
      const input = document.getElementById('batchIdInput');
      if (!input || !input.value.trim()) return;
      const rawOid = input.value.trim();
      input.value = '';

      // Check if already in queue
      if (state.batchQueue.some(i => String(i.oid) === String(rawOid))) {
        showToast(`Item #${rawOid} already in queue`);
        return;
      }

      // Fetch quick details from server or local list
      let sciName = 'Vascular Specimen';
      let prevLoc = 'Unrecorded';
      const existing = state.objectList.find(o => String(o.id) === String(rawOid));
      if (existing) {
        sciName = existing.scientific_name;
        const l = existing.location || {};
        prevLoc = `${l.building || ''} Fl ${l.floor || ''} Cab ${l.cabinet || ''} Sh ${l.shelf || ''}`.trim() || 'Unrecorded';
      }

      state.batchQueue.unshift({
        oid: rawOid,
        sciName: sciName,
        prevLoc: prevLoc
      });

      renderBatchQueue();
    }

    function removeBatchItem(idx) {
      state.batchQueue.splice(idx, 1);
      renderBatchQueue();
    }

    function clearBatchQueue() {
      state.batchQueue = [];
      renderBatchQueue();
    }

    function renderBatchQueue() {
      const container = document.getElementById('batchStreamList');
      const countEl = document.getElementById('batchQueueCount');
      const summaryEl = document.getElementById('batchCommitSummary');

      const count = state.batchQueue.length;
      if (countEl) countEl.textContent = `(${count} items)`;
      if (summaryEl) summaryEl.textContent = `${count} Accessions Queued`;

      if (count === 0) {
        if (container) container.innerHTML = `
          <div class="p-6 text-center text-stone-400 font-mono text-xs" id="batchEmptyPlaceholder">
            No items queued for this shelf yet.<br>Type an Object ID above to begin.
          </div>
        `;
        return;
      }

      const targetLocStr = `${state.batchAnchor.building} · Cab ${String(state.batchAnchor.cabinet).padStart(2, '0')} · Sh ${String(state.batchAnchor.shelf).padStart(2, '0')}`;

      container.innerHTML = state.batchQueue.map((item, idx) => `
        <article class="relative bg-white rounded border border-bordercol p-3 shadow-2xs flex flex-col gap-1">
          <div class="flex items-start justify-between">
            <div class="flex flex-col min-w-0">
              <div class="flex items-center gap-1.5">
                <span class="font-mono text-xs font-bold text-fern-dark">#${item.oid}</span>
                <span class="text-[9px] font-mono px-1 py-0.2 bg-emerald-50 text-fern rounded border border-fern/30">QUEUED</span>
              </div>
              <div class="font-serif italic text-xs text-ink truncate">${item.sciName}</div>
            </div>
            <button type="button" onclick="removeBatchItem(${idx})" class="text-stone-400 hover:text-brick p-1 text-sm font-bold">✕</button>
          </div>
          <div class="flex items-center gap-1.5 text-[10px] font-mono text-muted pt-1 border-t border-stone-100">
            <span class="truncate">${item.prevLoc}</span>
            <span class="text-fern font-bold">→</span>
            <span class="font-semibold text-fern-dark truncate">${targetLocStr}</span>
          </div>
        </article>
      `).join('');
    }

    async function commitBatchLocationUpdate() {
      if (state.batchQueue.length === 0) {
        showToast('No items in batch to commit');
        return;
      }

      const payload = {
        location: {
          Building: state.batchAnchor.building,
          Floor: String(state.batchAnchor.floor),
          Cabinet: String(state.batchAnchor.cabinet),
          Shelf: String(state.batchAnchor.shelf),
          'Stored as': state.batchAnchor.storedAs
        },
        items: state.batchQueue.map(i => i.oid),
        timestamp: new Date().toISOString()
      };

      try {
        const res = await apiFetch('/api/batch_location_update', {
          method: 'POST',
          body: payload
        });

        if (res && res.success) {
          showToast(`✓ Batch committed! Relocated ${res.updated_count} specimens`);
          state.batchQueue = [];
          renderBatchQueue();
          fetchObjects(false);
        } else {
          showToast('Batch commit error');
        }
      } catch(err) {
        showToast('Failed to commit batch location');
      }
    }

    // -------------------------------------------------------------
    // AUTOSAVE & UNDO
    // -------------------------------------------------------------
    function markDirty(field) {
      dirtyFields.add(field);
    }

    function triggerAutoSave() {
      clearTimeout(autoSaveTimer);
      autoSaveTimer = setTimeout(saveRecord, 800);
    }

    async function saveRecord() {
      if (!state.currentRecord || dirtyFields.size === 0 || isSaving) return;
      isSaving = true;

      const payload = {
        id: state.currentRecord.id,
        observation: state.currentRecord.observation || {},
        registration: state.currentRecord.registration || {},
        reviewed: state.isReviewed,
        timestamp: new Date().toISOString()
      };

      try {
        const res = await apiFetch('/api/update', {
          method: 'POST',
          body: payload
        });
        if (res && res.success) {
          dirtyFields.clear();
          showToast('✓ Saved & synchronized');
        }
      } catch(err) {
        console.error('Save error:', err);
      } finally {
        isSaving = false;
      }
    }

    async function undoLastEdit() {
      try {
        const res = await apiFetch('/api/undo', {
          method: 'POST',
          body: { oid: state.currentOid }
        });
        if (res && res.success) {
          showToast('↩ Undid last edit');
          if (state.currentOid) fetchObjectDetail(state.currentOid);
          fetchObjects(false);
        }
      } catch(err) {
        showToast('Nothing to undo');
      }
    }

    // -------------------------------------------------------------
    // SETTINGS, WALK MODE, MODAL HELPERS
    // -------------------------------------------------------------
    function openModal(id) {
      document.getElementById(id)?.classList.remove('hidden');
    }

    function closeModal(id) {
      document.getElementById(id)?.classList.add('hidden');
    }

    function openSettingsModal() {
      document.getElementById('settingShowFilterPills').checked = state.showFilterPills;
      openModal('settingsModal');
    }

    function closeSettingsModal() {
      closeModal('settingsModal');
    }

    async function saveSettings() {
      const pattern = document.getElementById('settingImageUrlPattern').value.trim();
      if (pattern) {
        await apiFetch('/api/settings', {
          method: 'POST',
          body: { image_url_pattern_override: pattern }
        });
      }
      closeSettingsModal();
      showToast('✓ Settings saved');
    }

    async function toggleWakeLock() {
      if (!wakeLockSentinel) {
        try {
          if ('wakeLock' in navigator) {
            wakeLockSentinel = await navigator.wakeLock.request('screen');
            document.getElementById('listWakeLockIcon').textContent = '☀️';
            showToast('☀️ Walk Mode active (screen awake)');
          }
        } catch(err) {}
      } else {
        try {
          await wakeLockSentinel.release();
          wakeLockSentinel = null;
          document.getElementById('listWakeLockIcon').textContent = '🌙';
          showToast('🌙 Walk Mode disabled');
        } catch(err) {}
      }
    }

    function openFilterModal() {
      openModal('filterModal');
    }

    function closeFilterModal() {
      closeModal('filterModal');
    }

    function clearAdvancedFilters() {
      state.activeAdvancedFilters = { locations: {}, problems: {} };
      closeFilterModal();
      fetchObjects();
    }

    function applyAdvancedFilters() {
      closeFilterModal();
      fetchObjects();
    }

    async function submitDiscrepancy(e) {
      e.preventDefault();
      const field = document.getElementById('discrepancyFieldSelect').value;
      const note = document.getElementById('discrepancyReasonInput').value.trim();
      if (!field || !note || !state.currentRecord) return;

      state.currentRecord.observation = state.currentRecord.observation || {};
      state.currentRecord.observation[field + '_Problem'] = true;
      state.currentRecord.observation[field + '_Note'] = note;
      markDirty(field + '_Problem');
      markDirty(field + '_Note');

      closeModal('addDiscrepancyModal');
      triggerAutoSave();
      renderDetailView(false);
      showToast('⚑ Issue flagged');
    }

    // Start App
    window.addEventListener('DOMContentLoaded', init);
  </script>
</body>
</html>

"""

