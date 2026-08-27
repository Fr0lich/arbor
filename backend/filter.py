import pandas as pd
from repository import REVIEWED_COLUMN

def _get_location_str(val):
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)

def _is_unknown(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return True
    s = str(val).strip().lower()
    return s in ("", "unknown", "?", "ukjent")

class FilterManager:
    def __init__(self):
        pass

    def apply_filter(self, df_reg, reg_dict, obs_dict, history_set, groups, global_mode, not_reviewed_only, location_filters, problem_columns, problem_to_field, unknown_fields, image_mode):
        filtered_ids = []
        if df_reg is None:
            return filtered_ids

        building_filter, floor_filter, cabinet_filter = location_filters
        has_location_filter = bool(building_filter or floor_filter or cabinet_filter)
        clean_cabinet_filter = cabinet_filter.replace(" ", "").lower() if cabinet_filter else ""
        no_filters = all(len(v) == 0 for v in groups.values()) and not has_location_filter

        if no_filters and not not_reviewed_only:
            return list(df_reg.index)

        fast_problem_cache = {}
        include_image_problems = (image_mode == "folder")

        # Combine all group items once
        all_items = []
        for group_name, items in groups.items():
            if items:
                all_items.extend(items)

        def fast_has_history(oid):
            if oid in history_set:
                return True
            s_oid = str(oid)
            if s_oid in history_set:
                return True
            if s_oid.isdigit() and int(s_oid) in history_set:
                return True
            return False

        def fast_is_problem_active(oid, prob_col, obs_row, reg_row):
            if prob_col == "Other_problem":
                return bool(obs_row.get(prob_col, False))

            if prob_col == "Reviewed":
                return bool(obs_row.get(REVIEWED_COLUMN, False))

            if prob_col == "Has_Images":
                if image_mode == "online":
                    return True
                elif image_mode == "offline":
                    return False
                return not bool(obs_row.get("Images_Missing", False))

            if prob_col == "Images_Missing":
                if image_mode in ("online", "offline"):
                    return False
                return bool(obs_row.get("Images_Missing", False))

            obs_val = bool(obs_row.get(prob_col, False))
            auto_val = False

            if prob_col in problem_to_field:
                field = problem_to_field.get(prob_col)
                if not field:
                    return obs_val

                raw_val = reg_row.get(field, "")

                is_missing = (
                    raw_val is None or
                    (isinstance(raw_val, float) and pd.isna(raw_val)) or
                    (isinstance(raw_val, str) and raw_val.strip() == "")
                )

                if not is_missing:
                    return obs_val

                is_unknown = (
                    raw_val is None or
                    (isinstance(raw_val, float) and pd.isna(raw_val)) or
                    str(raw_val).strip().lower() in ("", "unknown", "?", "ukjent")
                )

                auto_val = is_missing and not is_unknown

            return obs_val or auto_val

        # Pre-filter problem_columns
        active_prob_cols = []
        for p in problem_columns:
            if p == "Images_Missing":
                continue
            if not include_image_problems and "Image" in p:
                continue
            active_prob_cols.append(p)

        def fast_has_any_problem(oid, obs_row, reg_row):
            for p in active_prob_cols:
                if fast_is_problem_active(oid, p, obs_row, reg_row):
                    return True
            return False

        def fast_get_cached_problem(oid, obs_row, reg_row):
            if oid not in fast_problem_cache:
                fast_problem_cache[oid] = fast_has_any_problem(
                    oid,
                    obs_row,
                    reg_row
                )
            return fast_problem_cache[oid]

        # Optimization: Create a fast check function closure that avoids dictionary lookups
        # for string conditions and pre-calculates loop invariants.
        def create_evaluator(p):
            if p == "Any_Problem":
                return lambda oid, obs, reg: fast_has_any_problem(oid, obs, reg)
            elif p == "Has_Images":
                if image_mode == "online":
                    return lambda oid, obs, reg: True
                elif image_mode == "offline":
                    return lambda oid, obs, reg: False
                else:
                    return lambda oid, obs, reg: not bool(obs.get("Images_Missing", False))
            elif p == "Images_Missing":
                if image_mode in ("online", "offline"):
                    return lambda oid, obs, reg: False
                else:
                    return lambda oid, obs, reg: bool(obs.get("Images_Missing", False))
            elif p == "Reviewed":
                return lambda oid, obs, reg: bool(obs.get(REVIEWED_COLUMN, False))
            elif p == "Not_Reviewed":
                return lambda oid, obs, reg: not bool(obs.get(REVIEWED_COLUMN, False))
            elif p == "Comment_Empty":
                return lambda oid, obs, reg: not str(reg.get("Comment", "")).strip()
            elif p == "Comment_Not_Empty":
                return lambda oid, obs, reg: bool(str(reg.get("Comment", "")).strip())
            elif p == "Extra_Empty":
                return lambda oid, obs, reg: not str(obs.get("Extra", "")).strip()
            elif p == "Extra_Not_Empty":
                return lambda oid, obs, reg: bool(str(obs.get("Extra", "")).strip())
            elif p == "Unknown":
                def check_unk(oid, obs, reg):
                    for field in unknown_fields:
                        raw_val = reg.get(field, "")
                        is_unk = (
                            raw_val is None or
                            (isinstance(raw_val, float) and pd.isna(raw_val)) or
                            str(raw_val).strip().lower() in ("", "unknown", "?", "ukjent")
                        )
                        if is_unk: return True
                    return False
                return check_unk
            elif p == "Reviewed_With_Problem":
                return lambda oid, obs, reg: (bool(obs.get(REVIEWED_COLUMN, False)) and fast_get_cached_problem(oid, obs, reg))
            elif p == "Problem_With_History" or p == "Has_History":
                return lambda oid, obs, reg: fast_has_history(oid)
            else:
                return lambda oid, obs, reg: fast_is_problem_active(oid, p, obs, reg)

        evaluators = [create_evaluator(p) for p in all_items]

        def get_location_str(val):
            if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
                return ""
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            return str(val)

        # Optimize dictionary lookups by pre-binding
        obs_get = obs_dict.get
        reg_get = reg_dict.get

        # Pre-compute DataFrame index logic as array or list
        indices = df_reg.index.tolist()

        if global_mode == "AND":
            for oid in indices:
                obs_row = obs_get(oid)
                if obs_row is None:
                    s_oid = str(oid)
                    obs_row = obs_get(s_oid)
                    if obs_row is None and s_oid.isdigit():
                        obs_row = obs_get(int(s_oid), {})
                        if obs_row is None:
                            obs_row = {}

                if not_reviewed_only:
                    if obs_row.get(REVIEWED_COLUMN):
                        continue
                    filtered_ids.append(oid)
                    continue

                # Short-circuit location checks early before executing heavy group evaluations
                if building_filter and get_location_str(obs_row.get("Building", "")) != building_filter:
                    continue
                if floor_filter and get_location_str(obs_row.get("Floor", "")) != floor_filter:
                    continue
                if clean_cabinet_filter:
                    cabinet_val = get_location_str(obs_row.get("Cabinet", "")).lower()
                    if clean_cabinet_filter not in cabinet_val.replace(" ", ""):
                        continue

                reg_row = reg_get(oid)
                if reg_row is None:
                    s_oid = str(oid)
                    reg_row = reg_get(s_oid)
                    if reg_row is None and s_oid.isdigit():
                        reg_row = reg_get(int(s_oid), {})
                        if reg_row is None:
                            reg_row = {}

                if not all_items:
                    filtered_ids.append(oid)
                    continue

                matched = True
                for eval_fn in evaluators:
                    if not eval_fn(oid, obs_row, reg_row):
                        matched = False
                        break
                if matched:
                    filtered_ids.append(oid)
        else: # OR mode
            for oid in indices:
                obs_row = obs_get(oid)
                if obs_row is None:
                    s_oid = str(oid)
                    obs_row = obs_get(s_oid)
                    if obs_row is None and s_oid.isdigit():
                        obs_row = obs_get(int(s_oid), {})
                        if obs_row is None:
                            obs_row = {}

                if not_reviewed_only:
                    if obs_row.get(REVIEWED_COLUMN):
                        continue
                    filtered_ids.append(oid)
                    continue

                # Short-circuit location checks early before executing heavy group evaluations
                if building_filter and get_location_str(obs_row.get("Building", "")) != building_filter:
                    continue
                if floor_filter and get_location_str(obs_row.get("Floor", "")) != floor_filter:
                    continue
                if clean_cabinet_filter:
                    cabinet_val = get_location_str(obs_row.get("Cabinet", "")).lower()
                    if clean_cabinet_filter not in cabinet_val.replace(" ", ""):
                        continue

                reg_row = reg_get(oid)
                if reg_row is None:
                    s_oid = str(oid)
                    reg_row = reg_get(s_oid)
                    if reg_row is None and s_oid.isdigit():
                        reg_row = reg_get(int(s_oid), {})
                        if reg_row is None:
                            reg_row = {}

                if not all_items:
                    filtered_ids.append(oid)
                    continue

                for eval_fn in evaluators:
                    if eval_fn(oid, obs_row, reg_row):
                        filtered_ids.append(oid)
                        break

        return filtered_ids
