import pandas as pd
from repository import REVIEWED_COLUMN

class FilterManager:
    def __init__(self):
        pass

    def apply_filter(self, df_reg, reg_dict, obs_dict, history_set, groups, group_modes, not_reviewed_only, location_filters, problem_columns, problem_to_field, unknown_fields, image_mode):
        filtered_ids = []
        if df_reg is None:
            return filtered_ids

        building_filter, floor_filter, cabinet_filter = location_filters

        has_location_filter = bool(building_filter or floor_filter or cabinet_filter)
        no_filters = all(len(v) == 0 for v in groups.values()) and not has_location_filter

        if no_filters and not not_reviewed_only:
            return list(df_reg.index)

        fast_problem_cache = {}

        def get_location_str(val):
            if pd.isna(val) or val == "":
                return ""
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            return str(val)

        def is_unknown(val):
            if pd.isna(val):
                return True
            s = str(val).strip().lower()
            return s in ("", "unknown", "?", "ukjent")

        def fast_has_history(oid):
            return oid in history_set

        def fast_is_problem_active(oid, prob_col):
            obs_row = obs_dict.get(oid, {})
            reg_row = reg_dict.get(oid, {})

            if prob_col == "Other_problem":
                return bool(obs_row.get(prob_col, False))

            if prob_col == "Reviewed":
                return bool(obs_row.get(REVIEWED_COLUMN, False))

            if oid not in obs_dict:
                return False

            if prob_col == "Has_Images":
                return not obs_row.get("Images_Missing", False)

            if prob_col == "Images_Missing":
                if image_mode in ("online", "offline"):
                    return False
                return obs_row.get("Images_Missing", False)

            obs_val = bool(obs_row.get(prob_col, False))
            auto_val = False

            if prob_col in problem_to_field:
                field = problem_to_field.get(prob_col)
                if not field:
                    return obs_val

                raw_val = reg_row.get(field, "")

                is_missing = (
                    pd.isna(raw_val) or
                    (isinstance(raw_val, str) and raw_val.strip() == "")
                )

                auto_val = is_missing and not is_unknown(raw_val)

            return obs_val or auto_val

        def fast_has_any_problem(oid, include_image_problems=True):
            for p in problem_columns:
                if p == "Images_Missing":
                    continue
                if not include_image_problems:
                    if "Image" in p:
                        continue
                if fast_is_problem_active(oid, p):
                    return True
            return False

        def fast_get_cached_problem(oid):
            if oid not in fast_problem_cache:
                fast_problem_cache[oid] = fast_has_any_problem(
                    oid,
                    include_image_problems=(image_mode == "folder")
                )
            return fast_problem_cache[oid]

        def check_group(oid, items, mode):
            if not items:
                return None

            results = []
            obs_row = obs_dict.get(oid, {})
            reg_row = reg_dict.get(oid, {})

            for p in items:
                if p == "Any_Problem":
                    val = fast_has_any_problem(oid)
                elif p == "Has_Images":
                    val = not obs_row.get("Images_Missing", False)
                elif p == "Images_Missing":
                    val = obs_row.get("Images_Missing", False)
                elif p == "Reviewed":
                    val = bool(obs_row.get(REVIEWED_COLUMN, False))
                elif p == "Not_Reviewed":
                    val = not bool(obs_row.get(REVIEWED_COLUMN, False))
                elif p == "Comment_Empty":
                    val = not str(reg_row.get("Comment", "")).strip()
                elif p == "Comment_Not_Empty":
                    val = bool(str(reg_row.get("Comment", "")).strip())
                elif p == "Extra_Empty":
                    val = not str(obs_row.get("Extra", "")).strip()
                elif p == "Extra_Not_Empty":
                    val = bool(str(obs_row.get("Extra", "")).strip())
                elif p == "Unknown":
                    val = any(is_unknown(reg_row.get(field, "")) for field in unknown_fields)
                elif p == "Reviewed_With_Problem":
                    val = (bool(obs_row.get(REVIEWED_COLUMN, False)) and fast_get_cached_problem(oid))
                elif p == "Problem_With_History":
                    val = fast_get_cached_problem(oid) and fast_has_history(oid)
                elif p == "Has_History":
                    val = fast_has_history(oid)
                else:
                    val = fast_is_problem_active(oid, p)

                results.append(val)

            return all(results) if mode == "AND" else any(results)


        for oid in df_reg.index:
            if not_reviewed_only:
                obs_row = obs_dict.get(oid, {})
                if obs_row.get(REVIEWED_COLUMN):
                    continue
                filtered_ids.append(oid)
                continue

            group_results = []
            for group_name, items in groups.items():
                mode = group_modes.get(group_name, "AND")
                result = check_group(oid, items, mode)
                if result is not None:
                    group_results.append(result)

            location_match = True
            obs_row = obs_dict.get(oid, {})

            if building_filter:
                if get_location_str(obs_row.get("Building", "")) != building_filter:
                    location_match = False
            if floor_filter:
                if get_location_str(obs_row.get("Floor", "")) != floor_filter:
                    location_match = False
            if cabinet_filter:
                cabinet_val = get_location_str(obs_row.get("Cabinet", "")).lower()
                if cabinet_filter.replace(" ", "") not in cabinet_val.replace(" ", ""):
                    location_match = False

            ok = all(group_results) if group_results else True
            ok = ok and location_match

            if ok:
                filtered_ids.append(oid)

        return filtered_ids
