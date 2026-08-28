import re

with open("backend/mobile_server.py", "r") as f:
    content = f.read()

# Replace argument reading
search_args = """
            # New query parameters
            cabinet_filter = request.args.get('cabinet', '').strip().lower()
            room_filter = request.args.get('room', '').strip().lower()
            genus_filter = request.args.get('genus', '').strip().lower()
            collector_filter = request.args.get('collector', '').strip().lower()
            has_problems_filter = request.args.get('has_problems', '').strip().lower()
"""
replace_args = """
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
"""
content = content.replace(search_args, replace_args)

# Replace filtering logic
search_filters = """
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
"""
replace_filters = """
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
"""
content = content.replace(search_filters, replace_filters)

with open("backend/mobile_server.py", "w") as f:
    f.write(content)
