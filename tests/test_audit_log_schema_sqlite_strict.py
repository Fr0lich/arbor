import os
import sqlite3
import tempfile
import pandas as pd
import pytest
from repository import SQLiteRepository, _normalise_log_dataframe
import config


def test_sqlite_strict_schema_log_save_with_session_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "strict_log_test.db")
        
        # 1. Create a SQLite DB with strict 13-column canonical Log table
        conn = sqlite3.connect(db_path)
        canonical_cols = [
            "Timestamp", "Action", "Reviewed", "ObjectID",
            "ChangedFields", "ChangedValues",
            "ProblemsChanged", "ProblemsChangedValues",
            "LocationChanged", "LocationChangedValues",
            "User", "SourceFile", "OutputFile"
        ]
        col_defs = ", ".join([f'"{col}" TEXT' for col in canonical_cols])
        conn.execute(f'CREATE TABLE "Log" ({col_defs});')
        conn.execute('CREATE TABLE "Registration" ("ObjectID" TEXT, "Genus" TEXT);')
        conn.execute('CREATE TABLE "Observation" ("ObjectID" TEXT, "Reviewed" BOOLEAN);')
        conn.commit()
        conn.close()

        # 2. Prepare DataFrames with a 14th private column (_session_id) in df_log
        df_reg = pd.DataFrame([{"ObjectID": "101", "Genus": "Quercus"}]).set_index("ObjectID")
        df_obs = pd.DataFrame([{"ObjectID": "101", "Reviewed": True}]).set_index("ObjectID")
        df_photo = pd.DataFrame()
        df_log = pd.DataFrame([{
            "Timestamp": "2026-09-03T12:00:00",
            "Action": "MOBILE_EDIT",
            "Reviewed": "Yes",
            "ObjectID": "101",
            "ChangedFields": "Genus",
            "ChangedValues": 'Genus: "Fagus" -> "Quercus"',
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": "",
            "User": "Mobile-Companion",
            "SourceFile": "test.db",
            "OutputFile": "test.db",
            "_session_id": "session_abc123"  # Non-canonical internal metadata
        }])

        # 3. save_sqlite must succeed without sqlite3.OperationalError: table Log has no column named _session_id
        SQLiteRepository.save_sqlite(db_path, df_reg, df_obs, df_photo, df_log)

        # 4. Load from SQLite and assert schema
        cfg = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
        _, _, _, loaded_log, _ = SQLiteRepository.load_sqlite(db_path, cfg)
        
        assert len(loaded_log) == 1
        assert list(loaded_log.columns) == canonical_cols
        assert "_session_id" not in loaded_log.columns
        assert loaded_log.at[0, "Action"] == "MOBILE_EDIT"
        assert loaded_log.at[0, "ChangedFields"] == "Genus"
