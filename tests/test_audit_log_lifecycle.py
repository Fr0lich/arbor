import os
import tempfile
import pytest
import pandas as pd
from unittest.mock import MagicMock
from models import AppState
from repository import ExcelRepository, SQLiteRepository, _normalise_log_dataframe
import config


def test_normalise_log_dataframe_canonical_columns():
    # Test normalization of empty and incomplete log dataframes
    empty_df = pd.DataFrame()
    norm_empty = _normalise_log_dataframe(empty_df)
    expected_cols = [
        "Timestamp", "Action", "Reviewed", "ObjectID", "ChangedFields",
        "ChangedValues", "ProblemsChanged", "ProblemsChangedValues",
        "LocationChanged", "LocationChangedValues", "User", "SourceFile", "OutputFile"
    ]
    assert list(norm_empty.columns) == expected_cols
    assert norm_empty.empty

    partial_df = pd.DataFrame([{
        "Timestamp": "2026-09-03T10:00:00",
        "Action": "EDIT",
        "ObjectID": "1001",
        "ChangedFields": "Species"
    }])
    norm_partial = _normalise_log_dataframe(partial_df)
    assert set(norm_partial.columns) == set(expected_cols)
    assert len(norm_partial.columns) == len(expected_cols)
    assert norm_partial.at[0, "ChangedFields"] == "Species"
    assert norm_partial.at[0, "User"] == ""


def test_excel_sqlite_log_roundtrip_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        excel_path = os.path.join(tmpdir, "test_roundtrip.xlsx")
        sqlite_path = os.path.join(tmpdir, "test_roundtrip.db")

        df_reg = pd.DataFrame([{"ObjectID": "1001", "Genus": "Quercus", "Species": "robur"}]).set_index("ObjectID")
        df_obs = pd.DataFrame([{"ObjectID": "1001", "Reviewed": True, "Location": "Shelf A"}]).set_index("ObjectID")
        df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath", "ImageNote"]).set_index("ObjectID")
        df_unval = pd.DataFrame([{"ObjectID": "1001", "Field_Name": "Collector", "Unvalidated_Comment": "Needs verification"}])
        
        raw_log = pd.DataFrame([{
            "Timestamp": "2026-09-03T10:00:00",
            "Action": "EDIT",
            "Reviewed": "Yes",
            "ObjectID": "1001",
            "ChangedFields": "Species",
            "ChangedValues": 'Species: "petraea" -> "robur"',
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "Location",
            "LocationChangedValues": "Shelf A",
            "User": "admin",
            "SourceFile": "test_roundtrip.xlsx",
            "OutputFile": "test_roundtrip.xlsx"
        }])
        df_log = _normalise_log_dataframe(raw_log)

        cfg = config.DATABASE_CONFIGS["Økonomisk Botanisk"]

        # 1. Save to Excel
        ExcelRepository.save_excel(excel_path, cfg, df_reg=df_reg, df_obs=df_obs, df_photo=df_photo, df_log=df_log, df_unvalidated=df_unval)
        assert os.path.exists(excel_path)

        # 2. Import Excel to SQLite via SQLiteRepository.import_from_excel
        SQLiteRepository.import_from_excel(excel_path, sqlite_path, cfg)
        assert os.path.exists(sqlite_path)

        # 3. Load from SQLite
        l_reg, l_obs, l_photo, l_log, l_unval = SQLiteRepository.load_sqlite(sqlite_path, cfg)
        assert len(l_log) == 1
        assert l_log.at[0, "Action"] == "EDIT"
        assert str(l_log.at[0, "ObjectID"]) == "1001"
        assert l_log.at[0, "ChangedValues"] == 'Species: "petraea" -> "robur"'
        assert len(l_unval) == 1
        assert l_unval.at[0, "Field_Name"] == "Collector"

        # 4. Export SQLite back to Excel
        excel_out = os.path.join(tmpdir, "exported_back.xlsx")
        SQLiteRepository.export_to_excel(sqlite_path, excel_out, cfg, df_unvalidated=df_unval)
        assert os.path.exists(excel_out)

        # 5. Load exported Excel
        e_reg, e_obs, e_photo, e_log, e_unval = ExcelRepository.load_excel(excel_out, cfg)
        assert len(e_log) == 1
        assert e_log.at[0, "ChangedFields"] == "Species"
        assert len(e_unval) == 1


def test_import_to_sqlite_and_save_as_integration():
    app = AppState()
    app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
    app.excel_path = "test.xlsx"
    app.output_path = "test.xlsx"
    app.df_reg = pd.DataFrame([{"ObjectID": "1", "Genus": "Pinus"}]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([{"ObjectID": "1", "Reviewed": False}]).set_index("ObjectID")
    app.df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath"]).set_index("ObjectID")
    app.df_log = pd.DataFrame([{
        "Timestamp": "2026-09-03T10:00:00", "Action": "EDIT", "Reviewed": "No", "ObjectID": "1",
        "ChangedFields": "Genus", "ChangedValues": 'Genus: "" -> "Pinus"',
        "ProblemsChanged": "", "ProblemsChangedValues": "",
        "LocationChanged": "", "LocationChangedValues": "",
        "User": "tester", "SourceFile": "test.xlsx", "OutputFile": "test.xlsx"
    }])
    app.df_unvalidated = pd.DataFrame([{"ObjectID": "1", "Field_Name": "Genus", "Unvalidated_Comment": "Auto"}])
    app._log_records = app.df_log.to_dict(orient="records")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_xl = os.path.join(tmpdir, "test.xlsx")
        dest_db = os.path.join(tmpdir, "imported.db")
        ExcelRepository.save_excel(test_xl, app.config, df_reg=app.df_reg, df_obs=app.df_obs, df_photo=app.df_photo, df_log=app.df_log, df_unvalidated=app.df_unvalidated)
        
        # Test import to sqlite flow
        SQLiteRepository.import_from_excel(test_xl, dest_db, app.config)
        df_reg, df_obs, df_photo, df_log, df_unvalidated = SQLiteRepository.load_sqlite(dest_db, app.config)
        
        app.excel_path = dest_db
        app.df_reg = df_reg
        app.df_obs = df_obs
        app.df_photo = df_photo
        app.df_log = df_log
        app.df_unvalidated = df_unvalidated
        app._log_records = df_log.to_dict(orient="records")

        assert app.excel_path == dest_db
        assert len(app._log_records) == 1
        assert app._log_records[0]["Action"] == "EDIT"
        assert app.df_unvalidated is not None
        assert len(app.df_unvalidated) == 1
