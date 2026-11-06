import os
import openpyxl
import pandas as pd

def create_demo_subset():
    src_path = "excel_temporary_example/24.10.OBCJDF.xlsx"
    dest_dir = "data"
    dest_path = os.path.join(dest_dir, "demo_collection.xlsx")
    os.makedirs(dest_dir, exist_ok=True)

    print(f"Reading source: {src_path}")
    xls = pd.ExcelFile(src_path)

    # 1. Registration
    df_reg = pd.read_excel(xls, sheet_name="Registration")
    # Take first 220 specimens (~11%)
    df_reg_sub = df_reg.iloc[:220].copy()
    valid_oids = set(df_reg_sub["ObjectID"].astype(str))
    print(f"Registration rows: {len(df_reg_sub)}, Unique ObjectIDs: {len(valid_oids)}")

    # 2. Observation
    df_obs = pd.read_excel(xls, sheet_name="Observation")
    df_obs_sub = df_obs[df_obs["ObjectID"].astype(str).isin(valid_oids)].copy()
    print(f"Observation rows: {len(df_obs_sub)}")

    # 3. Log
    df_log = pd.read_excel(xls, sheet_name="Log")
    # Keep logs that match valid_oids or are initial setup/ALL
    df_log_sub = df_log[df_log["ObjectID"].astype(str).isin(valid_oids) | (df_log["ObjectID"].astype(str) == "ALL")].copy()
    print(f"Log rows: {len(df_log_sub)}")

    # 4. Unvalidated_source
    if "Unvalidated_source" in xls.sheet_names:
        df_unval = pd.read_excel(xls, sheet_name="Unvalidated_source")
        df_unval_sub = df_unval[df_unval["ObjectID"].astype(str).isin(valid_oids)].copy()
        print(f"Unvalidated_source rows: {len(df_unval_sub)}")
    else:
        df_unval_sub = pd.DataFrame(columns=["ObjectID", "Field_Name", "Unvalidated_Comment"])

    print(f"Writing demo collection to: {dest_path}")
    with pd.ExcelWriter(dest_path, engine="openpyxl") as writer:
        df_reg_sub.to_excel(writer, sheet_name="Registration", index=False)
        df_obs_sub.to_excel(writer, sheet_name="Observation", index=False)
        df_log_sub.to_excel(writer, sheet_name="Log", index=False)
        df_unval_sub.to_excel(writer, sheet_name="Unvalidated_source", index=False)

    print(f"Success! File size: {os.path.getsize(dest_path)} bytes")

if __name__ == "__main__":
    create_demo_subset()
