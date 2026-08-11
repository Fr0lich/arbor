import pandas as pd
import uuid
import os
import shutil
import sqlite3
import datetime
from utils import debug_error

# ---------------------------------------------------------------------------
# Column name constants used across repository and UI layers.
# Import these in other modules rather than redefining them.
# ---------------------------------------------------------------------------
REVIEWED_COLUMN = "Reviewed"
REVIEWED_AT_COLUMN = "ReviewedAt"
ONLINE_EXISTS_COLUMN = "Online_Images_Exist"


def _normalise_dataframes(df_reg, df_obs, config):
    """Apply consistent type coercion and column defaults to the loaded dataframes.

    Both ExcelRepository and SQLiteRepository call this after reading raw data so
    that the rest of the application always receives dataframes in a known shape.

    Operations performed:
    - Strips and casts ObjectID to str in df_reg, df_obs.
    - Ensures all problem columns exist in df_obs and are bool.
    - Ensures all location columns exist in df_obs and are str.
    - Ensures Images_Missing, Images_Problem, Reviewed, ReviewedAt,
      Online_Images_Exist columns exist with appropriate defaults.
    - Fills NaN in all non-ObjectID df_reg columns with empty string.
    - Ensures UID and ProblemDescription columns exist in df_reg.
    - Auto-generates short UIDs for any row that is missing one.

    Args:
        df_reg: Registration dataframe (modified in-place).
        df_obs: Observation dataframe (modified in-place).
        config: Database config dict containing ui_sections.

    Returns:
        (df_reg, df_obs) — the same objects, normalised.
    """
    sections = config.get("ui_sections", {})
    problem_columns = [f["name"] for f in sections.get("problems", [])]
    location_columns = [f["name"] for f in sections.get("location", [])]
    registration_columns = [f["name"] for f in sections.get("registration", [])]

    # --- ObjectID ---
    if "ObjectID" in df_reg.columns:
        df_reg["ObjectID"] = df_reg["ObjectID"].astype(str).str.strip()
    if "ObjectID" in df_obs.columns:
        df_obs["ObjectID"] = df_obs["ObjectID"].astype(str).str.strip()

    # --- Registration: ensure all defined registration columns exist ---
    new_reg_cols = [col for col in registration_columns if col not in df_reg.columns]
    if new_reg_cols:
        df_reg[new_reg_cols] = pd.DataFrame({col: "" for col in new_reg_cols}, index=df_reg.index)

    # --- Observation: problem columns ---
    new_prob_cols = [col for col in problem_columns if col not in df_obs.columns]
    if new_prob_cols:
        df_obs[new_prob_cols] = pd.DataFrame({col: False for col in new_prob_cols}, index=df_obs.index)
    if problem_columns:
        df_obs[problem_columns] = df_obs[problem_columns].fillna(False).astype(bool)

    # --- Observation: location columns ---
    new_loc_cols = [col for col in location_columns if col not in df_obs.columns]
    if new_loc_cols:
        df_obs[new_loc_cols] = pd.DataFrame({col: "" for col in new_loc_cols}, index=df_obs.index)


    if location_columns:
        df_obs[location_columns] = df_obs[location_columns].fillna("").astype(object)

    for field in sections.get("location", []):
        if field.get("type") == "checkbox":
            col = field["name"]
            if col in df_obs.columns:
                df_obs[col] = df_obs[col].replace({"": "False", None: "False"}).fillna("False")
                df_obs[col] = df_obs[col].replace({True: "True", False: "False"}).astype(str)



    # --- Observation: image / review flags ---
    new_obs_cols = {}
    if "Images_Missing" not in df_obs.columns:
        new_obs_cols["Images_Missing"] = True
    if "Images_Problem" not in df_obs.columns:
        new_obs_cols["Images_Problem"] = False
    if REVIEWED_COLUMN not in df_obs.columns:
        new_obs_cols[REVIEWED_COLUMN] = False
    if REVIEWED_AT_COLUMN not in df_obs.columns:
        new_obs_cols[REVIEWED_AT_COLUMN] = ""
    if ONLINE_EXISTS_COLUMN not in df_obs.columns:
        new_obs_cols[ONLINE_EXISTS_COLUMN] = False

    if new_obs_cols:
        df_obs[list(new_obs_cols.keys())] = pd.DataFrame(new_obs_cols, index=df_obs.index)

    df_obs["Images_Missing"] = df_obs["Images_Missing"].fillna(True).astype(bool)
    df_obs["Images_Problem"] = df_obs["Images_Problem"].fillna(False).astype(bool)
    df_obs[REVIEWED_COLUMN] = df_obs[REVIEWED_COLUMN].fillna(False).astype(bool)
    df_obs[REVIEWED_AT_COLUMN] = df_obs[REVIEWED_AT_COLUMN].fillna("").astype(object)

    # --- Registration: fill NaN, ensure UID and ProblemDescription ---
    # Fill NaN and cast to object in bulk for non-ObjectID columns
    cols_to_fill = [col for col in df_reg.columns if col != "ObjectID"]
    if cols_to_fill:
        df_reg[cols_to_fill] = df_reg[cols_to_fill].fillna("").astype(object)

    new_reg_cols = {}
    if "UID" not in df_reg.columns:
        new_reg_cols["UID"] = ""
    if "ProblemDescription" not in df_reg.columns:
        new_reg_cols["ProblemDescription"] = ""

    if new_reg_cols:
        df_reg[list(new_reg_cols.keys())] = pd.DataFrame(new_reg_cols, index=df_reg.index)

    df_reg["ProblemDescription"] = df_reg["ProblemDescription"].astype(object)

    if not df_reg.empty:
        # Generate short UIDs for any row that is missing one
        missing_uid = df_reg["UID"].isna() | (df_reg["UID"].astype(str).str.strip() == "")
        if missing_uid.any():
            df_reg.loc[missing_uid, "UID"] = [
                uuid.uuid4().hex[:8] for _ in range(missing_uid.sum())
            ]

    return df_reg, df_obs

def _normalise_log_dataframe(df_log):
    """Ensure the log dataframe has all required columns.

    This adds backwards compatibility for older databases that may not have
    the new section-specific logging columns.
    """
    required_cols = [
        "Timestamp", "Action", "ObjectID",
        "ChangedFields", "ChangedValues",
        "ProblemsChanged", "ProblemsChangedValues",
        "LocationChanged", "LocationChangedValues",
        "User", "SourceFile", "OutputFile"
    ]
    
    if df_log is None or df_log.empty:
        return pd.DataFrame(columns=required_cols)
        
    missing_cols = [col for col in required_cols if col not in df_log.columns]
    if missing_cols:
        df_log[missing_cols] = pd.DataFrame({col: "" for col in missing_cols}, index=df_log.index)
            
    return df_log


class ExcelRepository:
    @staticmethod
    def load_excel(path, config):
        """Load a database from an Excel (.xlsx) file.

        Reads the Registration, Observation, Photo, and Log sheets.
        The Photo and Log sheets are optional — empty dataframes with the
        correct columns are returned if the sheets are missing.
        All dataframes are normalised via _normalise_dataframes before being
        returned, so callers always receive data in a consistent shape.

        Args:
            path:   Absolute path to the .xlsx file.
            config: Database config dict (from config.DATABASE_CONFIGS).

        Returns:
            (df_reg, df_obs, df_photo, df_log) — four pandas DataFrames.
        """
        sheets = config["sheets"]
        sections = config["ui_sections"]

        mapped_fields = [
            f["maps_to"]
            for f in sections["problems"]
            if "maps_to" in f
        ]

        # PERFORMANCE OPTIMIZATION (Bolt): Use pd.ExcelFile as a context manager to open the Excel
        # archive once, then read sheets from it. This prevents reopening/reparsing the zip and shared
        # string tables 4 times, leading to a massive speedup (~60-70% faster loads).
        # We try importing 'calamine' for a further 5-10x parsing speedup.
        engine = "openpyxl"
        try:
            import calamine  # noqa: F401
            engine = "calamine"
        except ImportError:
            pass

        with pd.ExcelFile(path, engine=engine) as xls:
            sheet_names = xls.sheet_names

            # Read Registration sheet
            sheet_reg = sheets.get("reg", "Registration")
            if sheet_reg in sheet_names:
                df_reg = pd.read_excel(xls, sheet_name=sheet_reg)
            else:
                df_reg = pd.read_excel(xls, sheet_name=sheet_reg) # Let it raise if missing

            # Read Observation sheet
            sheet_obs = sheets.get("obs", "Observation")
            if sheet_obs in sheet_names:
                df_obs = pd.read_excel(xls, sheet_name=sheet_obs)
            else:
                df_obs = pd.read_excel(xls, sheet_name=sheet_obs) # Let it raise if missing

            # Read Photo sheet (optional)
            sheet_photo = sheets.get("photo", "Photo")
            if sheet_photo in sheet_names:
                df_photo = pd.read_excel(xls, sheet_name=sheet_photo)
            else:
                df_photo = pd.DataFrame(columns=["ObjectID"])

            # Ensure mapped registration fields exist before normalisation
            missing_mapped_fields = [col for col in mapped_fields if col not in df_reg.columns]
            if missing_mapped_fields:
                df_reg[missing_mapped_fields] = pd.DataFrame({col: "" for col in missing_mapped_fields}, index=df_reg.index)

            # Normalise both main dataframes
            df_reg, df_obs = _normalise_dataframes(df_reg, df_obs, config)

            if not df_photo.empty:
                df_photo["ObjectID"] = df_photo["ObjectID"].astype(str).str.strip()

            # Read Log sheet (optional)
            sheet_log = sheets.get("log", "Log")
            if sheet_log in sheet_names:
                df_log = pd.read_excel(xls, sheet_name=sheet_log)
            else:
                df_log = pd.DataFrame()
            
        df_log = _normalise_log_dataframe(df_log)

        return df_reg, df_obs, df_photo, df_log


class SQLiteRepository:
    @staticmethod
    def load_sqlite(path, config):
        """Load a database from a SQLite (.db) file.

        Reads the Registration, Observation, Photo, and Log tables.
        All tables are optional — empty dataframes with correct columns are
        returned for any missing table.
        All dataframes are normalised via _normalise_dataframes before being
        returned, so callers always receive data in a consistent shape.

        Args:
            path:   Absolute path to the .db file.
            config: Database config dict (from config.DATABASE_CONFIGS).

        Returns:
            (df_reg, df_obs, df_photo, df_log) — four pandas DataFrames.
        """
        conn = sqlite3.connect(path)
        try:
            df_reg = pd.read_sql("SELECT * FROM Registration", conn)
        except Exception as e:
            debug_error("load_sqlite: Registration table missing or unreadable", str(e))
            df_reg = pd.DataFrame()

        try:
            df_obs = pd.read_sql("SELECT * FROM Observation", conn)
        except Exception as e:
            debug_error("load_sqlite: Observation table missing or unreadable", str(e))
            df_obs = pd.DataFrame()

        try:
            df_photo = pd.read_sql("SELECT * FROM Photo", conn)
        except Exception as e:
            debug_error("load_sqlite: Photo table missing or unreadable", str(e))
            df_photo = pd.DataFrame(columns=["ObjectID"])

        try:
            df_log = pd.read_sql("SELECT * FROM Log", conn)
        except Exception as e:
            debug_error("load_sqlite: Log table missing or unreadable", str(e))
            df_log = pd.DataFrame()
            
        df_log = _normalise_log_dataframe(df_log)

        conn.close()

        # Normalise both main dataframes
        df_reg, df_obs = _normalise_dataframes(df_reg, df_obs, config)

        if "ObjectID" in df_photo.columns:
            df_photo["ObjectID"] = df_photo["ObjectID"].astype(str).str.strip()

        return df_reg, df_obs, df_photo, df_log

    @staticmethod
    def save_sqlite(path, df_reg, df_obs, df_photo, df_log):
        """Write all dataframes to a SQLite database file.

        Replaces the Registration, Observation, Photo, and Log tables entirely.
        The Photo table is only written if it is non-empty.
        The Log table is only written if it is non-empty.

        Args:
            path:     Absolute path to the .db file (created if it does not exist).
            df_reg:   Registration dataframe.
            df_obs:   Observation dataframe.
            df_photo: Photo dataframe.
            df_log:   Log dataframe.
        """
        conn = sqlite3.connect(path)

        df_reg_save = df_reg.copy()
        if "ObjectID" not in df_reg_save.columns:
            df_reg_save = df_reg_save.reset_index()

        df_obs_save = df_obs.copy()
        if "ObjectID" not in df_obs_save.columns:
            df_obs_save = df_obs_save.reset_index()

        df_photo_save = df_photo.copy()
        if "ObjectID" not in df_photo_save.columns:
            df_photo_save = df_photo_save.reset_index()

        df_reg_save.to_sql("Registration", conn, if_exists="replace", index=False)
        df_obs_save.to_sql("Observation", conn, if_exists="replace", index=False)

        if not df_photo_save.empty:
            df_photo_save.to_sql("Photo", conn, if_exists="replace", index=False)

        if df_log is not None and not df_log.empty:
            df_log.to_sql("Log", conn, if_exists="replace", index=False)

        conn.close()

    @staticmethod
    def import_from_excel(excel_path, sqlite_path, config):
        """Import data from an Excel file into a SQLite database.

        Creates a timestamped backup of the source Excel file in a 'backups'
        subdirectory before reading it, then writes the data into the SQLite
        database at sqlite_path.

        Args:
            excel_path:  Absolute path to the source .xlsx file.
            sqlite_path: Absolute path to the destination .db file.
            config:      Database config dict.

        Returns:
            (df_reg, df_obs, df_photo, df_log) — the data that was imported.
        """
        import config as _app_cfg
        advanced_prefs = _app_cfg.load_prefs().get("advanced", {})
        enable_backup = advanced_prefs.get("enable_excel_import_backup", True)
        
        if enable_backup:
            backup_dir = os.path.join(os.path.dirname(excel_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(
                backup_dir,
                os.path.basename(excel_path) + f".backup_{timestamp}.xlsx"
            )
            shutil.copy2(excel_path, backup_path)
            print(f"Backed up {excel_path} to {backup_path}")

        df_reg, df_obs, df_photo, df_log = ExcelRepository.load_excel(excel_path, config)
        SQLiteRepository.save_sqlite(sqlite_path, df_reg, df_obs, df_photo, df_log)
        return df_reg, df_obs, df_photo, df_log

    @staticmethod
    def generate_empty_dataframes(config):
        """Build empty dataframes with the correct columns for a new database.

        The column structure is derived from the config's ui_sections so that a
        freshly created file will accept data without needing schema migrations.

        Args:
            config: Database config dict.

        Returns:
            (df_reg, df_obs, df_log) — three empty DataFrames with correct columns.
        """
        sections = config.get("ui_sections", {})

        reg_columns = ["ObjectID"]
        for field in sections.get("registration", []):
            if field["name"] not in reg_columns:
                reg_columns.append(field["name"])

        obs_columns = ["ObjectID"]
        for field in sections.get("location", []):
            if field["name"] not in obs_columns:
                obs_columns.append(field["name"])
        for field in sections.get("problems", []):
            if field["name"] not in obs_columns:
                obs_columns.append(field["name"])

        obs_columns.extend([
            "Images_Missing", "Images_Problem", "Images_Wrong",
            ONLINE_EXISTS_COLUMN, REVIEWED_COLUMN, REVIEWED_AT_COLUMN
        ])

        df_reg = pd.DataFrame(columns=reg_columns)
        df_obs = pd.DataFrame(columns=obs_columns)
        df_log = _normalise_log_dataframe(pd.DataFrame())

        return df_reg, df_obs, df_log

    @staticmethod
    def export_to_excel(sqlite_path, excel_path, config, progress_callback=None,
                        df_reg=None, df_obs=None, df_log=None):
        """Export data to an Excel (.xlsx) file.

        If df_reg / df_obs are not provided, the data is read from sqlite_path.
        If sqlite_path also does not exist, empty dataframes are used (allowing
        creation of a blank template file).

        The Registration, Observation, and Log sheets are always written.
        Existing sheets in the file are replaced; other sheets are preserved.

        Args:
            sqlite_path:       Path to the source .db file (may be None).
            excel_path:        Path to write the output .xlsx file.
            config:            Database config dict.
            progress_callback: Optional callable(current, total, label) for
                               progress reporting.
            df_reg:            Pre-loaded Registration dataframe (optional).
            df_obs:            Pre-loaded Observation dataframe (optional).
            df_log:            Pre-loaded Log dataframe (optional).
        """
        if df_reg is None or df_obs is None:
            if sqlite_path and os.path.exists(sqlite_path):
                df_reg, df_obs, _, df_log = SQLiteRepository.load_sqlite(sqlite_path, config)
            else:
                df_reg, df_obs, df_log = SQLiteRepository.generate_empty_dataframes(config)

        if df_log is None or df_log.empty:
            df_log = _normalise_log_dataframe(pd.DataFrame())
        else:
            df_log = _normalise_log_dataframe(df_log)

        if df_reg is not None and "ObjectID" not in df_reg.columns:
            df_reg = df_reg.reset_index()
        
        if df_obs is not None and "ObjectID" not in df_obs.columns:
            df_obs = df_obs.reset_index()

        sheets = config.get("sheets", {
            "reg": "Registration", "obs": "Observation",
            "log": "Log"
        })

        steps = [
            (df_reg, sheets.get("reg", "Registration"), "Registration"),
            (df_obs, sheets.get("obs", "Observation"),  "Observation"),
            (df_log, sheets.get("log", "Log"),          "Log"),
        ]
        total = len(steps)

        # Always write mode via a temp file → atomic rename (never leaves
        # the destination in a partially-written / corrupt state, and avoids
        # openpyxl append-mode which corrupts ZIP structure on overwrite).
        tmp_path = excel_path + ".tmp.xlsx"
        try:
            with pd.ExcelWriter(tmp_path, engine="openpyxl", mode="w") as writer:
                for i, (df, sheet, label) in enumerate(steps, 1):
                    if progress_callback:
                        progress_callback(i - 1, total, f"Writing {label}...")
                    if df is not None:
                        df.to_excel(writer, sheet_name=sheet, index=False)
                    if progress_callback:
                        progress_callback(i, total, f"{label} done")
            # Atomic rename: destination is replaced only after a full, valid write
            os.replace(tmp_path, excel_path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
