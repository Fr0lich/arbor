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

        def fast_has_history(oid):
            if oid in history_set:
                return True
            s_oid = str(oid)
            if s_oid in history_set:
                return True
            if s_oid.isdigit() and int(s_oid) in history_set:
                return True
            return False

        def get_obs_row(oid):
            row = obs_dict.get(oid)
            if row is None:
                s_oid = str(oid)
                row = obs_dict.get(s_oid)
                if row is None and s_oid.isdigit():
                    row = obs_dict.get(int(s_oid), {})
            return row if row is not None else {}

        def get_reg_row(oid):
            row = reg_dict.get(oid)
            if row is None:
                s_oid = str(oid)
                row = reg_dict.get(s_oid)
                if row is None and s_oid.isdigit():
                    row = reg_dict.get(int(s_oid), {})
            return row if row is not None else {}

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

                auto_val = is_missing and not _is_unknown(raw_val)

            return obs_val or auto_val

        def fast_has_any_problem(oid, obs_row, reg_row):
            for p in problem_columns:
                if p == "Images_Missing":
                    continue
                if not include_image_problems and "Image" in p:
                    continue
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

        def check_group(oid, items, mode, obs_row, reg_row):
            if not items:
                return None

            def evaluate(p):
                if p == "Any_Problem":
                    return fast_has_any_problem(oid, obs_row, reg_row)
                elif p == "Has_Images":
                    if image_mode == "online":
                        return True
                    elif image_mode == "offline":
                        return False
                    else:
                        return not bool(obs_row.get("Images_Missing", False))
                elif p == "Images_Missing":
                    if image_mode in ("online", "offline"):
                        return False
                    else:
                        return bool(obs_row.get("Images_Missing", False))
                elif p == "Reviewed":
                    return bool(obs_row.get(REVIEWED_COLUMN, False))
                elif p == "Not_Reviewed":
                    return not bool(obs_row.get(REVIEWED_COLUMN, False))
                elif p == "Comment_Empty":
                    return not str(reg_row.get("Comment", "")).strip()
                elif p == "Comment_Not_Empty":
                    return bool(str(reg_row.get("Comment", "")).strip())
                elif p == "Extra_Empty":
                    return not str(obs_row.get("Extra", "")).strip()
                elif p == "Extra_Not_Empty":
                    return bool(str(obs_row.get("Extra", "")).strip())
                elif p == "Unknown":
                    return any(_is_unknown(reg_row.get(field, "")) for field in unknown_fields)
                elif p == "Reviewed_With_Problem":
                    return (bool(obs_row.get(REVIEWED_COLUMN, False)) and fast_get_cached_problem(oid, obs_row, reg_row))
                elif p == "Problem_With_History":
                    return fast_has_history(oid)
                elif p == "Has_History":
                    return fast_has_history(oid)
                else:
                    return fast_is_problem_active(oid, p, obs_row, reg_row)

            if mode == "AND":
                return all(evaluate(p) for p in items)
            else:
                return any(evaluate(p) for p in items)

        for oid in df_reg.index:
            obs_row = get_obs_row(oid)

            if not_reviewed_only:
                if obs_row.get(REVIEWED_COLUMN):
                    continue
                filtered_ids.append(oid)
                continue

            # Short-circuit location checks early before executing heavy group evaluations
            if building_filter and _get_location_str(obs_row.get("Building", "")) != building_filter:
                continue
            if floor_filter and _get_location_str(obs_row.get("Floor", "")) != floor_filter:
                continue
            if clean_cabinet_filter:
                cabinet_val = _get_location_str(obs_row.get("Cabinet", "")).lower()
                if clean_cabinet_filter not in cabinet_val.replace(" ", ""):
                    continue

            reg_row = get_reg_row(oid)
            all_items = []
            for group_name, items in groups.items():
                if items:
                    all_items.extend(items)

            if not all_items:
                filtered_ids.append(oid)
                continue

            result = check_group(oid, all_items, global_mode, obs_row, reg_row)
            if result:
                filtered_ids.append(oid)

        return filtered_ids
