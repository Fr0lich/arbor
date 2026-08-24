import sys
import os
import re
import pandas as pd

def fix_value_quotes(val_str):
    """
    Attempts to fix strings formatted as:
    Field: "Value1"  "Value2"
    Where Value1 and Value2 might contain internal, unescaped double quotes.
    """
    if not val_str or ":" not in val_str:
        return val_str

    field_part, rest = val_str.split(":", 1)
    rest = rest.strip()

    # We expect something that looks roughly like "..."  "..." or "..." "..."
    # The first character should be a quote and the last should be a quote.
    if rest.startswith('"') and rest.endswith('"'):
        # Find the delimiter between old and new values.
        # It's usually a space followed by a quote: ' "' or '  "'

        # A simple heuristic: find the middle split point
        # A robust way is not always possible, but we try to fix inner quotes.
        # Let's replace all inner double quotes with single quotes.

        # We can regex match the start and end quotes, and the middle split:
        # ^"(.*)"[ ]+"(.*)"$
        # But this doesn't work well if there are matching quotes inside.

        # Let's just fix the "trailing double double quote" bug seen in the screenshots
        rest = rest.replace('"" ', '" ')
        rest = rest.replace('""', '"')

        # If it ends with multiple quotes, trim them
        rest = re.sub(r'"+$', '"', rest)

        return f"{field_part}: {rest}"

    return val_str

def migrate_log_sheet(excel_path):
    if not os.path.exists(excel_path):
        print(f"File not found: {excel_path}")
        return

    try:
        xls = pd.ExcelFile(excel_path, engine="calamine")
        sheet_names = xls.sheet_names
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    log_sheet_name = next((s for s in sheet_names if s.lower() == "log"), None)
    if not log_sheet_name:
        print("Log sheet not found in the Excel file.")
        return

    df_log = pd.read_excel(excel_path, sheet_name=log_sheet_name)

    required_cols = [
        "Timestamp", "Action", "Reviewed", "ObjectID",
        "ChangedFields", "ChangedValues",
        "ProblemsChanged", "ProblemsChangedValues",
        "LocationChanged", "LocationChangedValues",
        "User", "SourceFile", "OutputFile"
    ]

    for col in required_cols:
        if col not in df_log.columns:
            df_log[col] = ""

    for col in ["ProblemsChanged", "ProblemsChangedValues", "LocationChanged", "LocationChangedValues", "ChangedFields", "ChangedValues"]:
        df_log[col] = df_log[col].fillna("").astype(str)

    problem_suffixes = ("_Problem", "_Missing", "_Wrong")

    def is_problem_field(f):
        return any(f.endswith(s) for s in problem_suffixes)

    def is_location_field(f):
        return f in ("Building", "Floor", "Cabinet", "Stored as", "Location")

    for idx, row in df_log.iterrows():
        cf = str(row.get("ChangedFields", ""))
        cv = str(row.get("ChangedValues", ""))

        if cf.strip() == "" or cf.strip() == "(no changes)" or cf.strip() == "nan":
            continue

        fields = [f.strip() for f in cf.split(",") if f.strip()]

        if pd.isna(cv) or cv == "nan":
            cv = ""
        values = [fix_value_quotes(v.strip()) for v in cv.split(" | ") if v.strip()]

        new_reg_fields = []
        new_reg_vals = []

        new_prob_fields = []
        new_prob_vals = []

        new_loc_fields = []
        new_loc_vals = []

        for f in fields:
            val_block = ""
            for v in values:
                if v.startswith(f + ":"):
                    val_block = v
                    break

            if is_problem_field(f):
                new_prob_fields.append(f)
                if val_block:
                    new_prob_vals.append(val_block)
            elif is_location_field(f):
                new_loc_fields.append(f)
                if val_block:
                    new_loc_vals.append(val_block)
            else:
                new_reg_fields.append(f)
                if val_block:
                    new_reg_vals.append(val_block)

        if new_prob_fields or new_loc_fields:
            existing_pf = [f.strip() for f in str(row.get("ProblemsChanged", "")).split(",") if f.strip() and f.strip() != "nan"]
            merged_pf = list(set(existing_pf + new_prob_fields))
            df_log.at[idx, "ProblemsChanged"] = ", ".join(sorted(merged_pf)) if merged_pf else ""

            existing_pv = [v.strip() for v in str(row.get("ProblemsChangedValues", "")).split(" | ") if v.strip() and v.strip() != "nan"]
            merged_pv = existing_pv + new_prob_vals
            df_log.at[idx, "ProblemsChangedValues"] = " | ".join(merged_pv) if merged_pv else ""

            existing_lf = [f.strip() for f in str(row.get("LocationChanged", "")).split(",") if f.strip() and f.strip() != "nan"]
            merged_lf = list(set(existing_lf + new_loc_fields))
            df_log.at[idx, "LocationChanged"] = ", ".join(sorted(merged_lf)) if merged_lf else ""

            existing_lv = [v.strip() for v in str(row.get("LocationChangedValues", "")).split(" | ") if v.strip() and v.strip() != "nan"]
            merged_lv = existing_lv + new_loc_vals
            df_log.at[idx, "LocationChangedValues"] = " | ".join(merged_lv) if merged_lv else ""

            df_log.at[idx, "ChangedFields"] = ", ".join(sorted(new_reg_fields)) if new_reg_fields else "(no changes)"
            df_log.at[idx, "ChangedValues"] = " | ".join(new_reg_vals) if new_reg_vals else ""
        else:
            # Reapply quote fix to values even if no migration
            df_log.at[idx, "ChangedValues"] = " | ".join(values) if values else ""

    print(f"Writing updated log to {excel_path}...")
    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df_log.to_excel(writer, sheet_name=log_sheet_name, index=False)
        print("Success!")
    except Exception as e:
        print(f"Error saving: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reformat_logs.py <path_to_excel_file>")
        sys.exit(1)

    migrate_log_sheet(sys.argv[1])
