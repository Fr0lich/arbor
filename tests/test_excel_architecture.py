import os
import pytest
import pandas as pd
import openpyxl
from unittest import mock
from repository import (
    ExcelRepository,
    SQLiteRepository,
    _normalise_dataframes,
    _coerce_bool_series,
    _normalize_object_id_series,
    _open_excel_reader,
    _find_sheet_name,
    REVIEWED_COLUMN,
    REVIEWED_AT_COLUMN
)
from models import AppState


class TestExcelArchitecture:

    def test_boolean_coercion_edge_cases(self):
        # Truthy cases
        truthy_series = pd.Series(["True", "true", "TRUE", "1", 1, 1.0, "yes", "YES", "y", "t", "on", True])
        coerced_true = _coerce_bool_series(truthy_series, default=False)
        assert coerced_true.all(), "All truthy variants should coerce to True"

        # Falsy cases - CRITICAL: string "False" must NOT be evaluated as truthy
        falsy_series = pd.Series(["False", "false", "FALSE", "0", 0, 0.0, "no", "NO", "n", "f", "off", "", None, False])
        coerced_false = _coerce_bool_series(falsy_series, default=False)
        assert not coerced_false.any(), "All falsy variants should coerce to False"

    def test_object_id_normalization_edge_cases(self):
        # 1024.0 -> "1024", but "1024.1" -> "1024.1", "00123" -> "00123", "  ABC-1  " -> "ABC-1"
        oids = pd.Series([1024, 1025.0, "1026.0", "1027.5", "0042", "  999  ", "O-V-001", None, ""])
        normalized = _normalize_object_id_series(oids)
        assert list(normalized) == ["1024", "1025", "1026", "1027.5", "0042", "999", "O-V-001", "", ""]

    def test_normalise_dataframes_comprehensive(self):
        config = {
            "ui_sections": {
                "registration": [{"name": "Genus"}, {"name": "Species"}, {"name": "UID"}],
                "location": [
                    {"name": "Building", "type": "choice"},
                    {"name": "Loaned out", "type": "checkbox"}
                ],
                "problems": [
                    {"name": "Genus_Problem", "type": "bool", "maps_to": "Genus"}
                ]
            }
        }

        df_reg = pd.DataFrame({
            "ObjectID": [101.0, " 00102 ", "103.5"],
            "Genus": ["Quercus", "Rosa", "Betula"],
            "UID": ["", None, "custom_uid"]
        })

        df_obs = pd.DataFrame({
            "ObjectID": [101.0, "00102", "103.5"],
            "Genus_Problem": ["False", "True", "0"],
            "Loaned out": [1, "false", "yes"],
            "Reviewed": ["no", "yes", "False"]
        })

        df_reg_out, df_obs_out = _normalise_dataframes(df_reg, df_obs, config)

        # Verify ObjectID cleaning
        assert list(df_reg_out["ObjectID"]) == ["101", "00102", "103.5"]
        assert list(df_obs_out["ObjectID"]) == ["101", "00102", "103.5"]

        # Verify UID generation
        assert len(df_reg_out.loc[0, "UID"]) == 8
        assert len(df_reg_out.loc[1, "UID"]) == 8
        assert df_reg_out.loc[2, "UID"] == "custom_uid"

        # Verify Problem boolean coercion
        assert df_obs_out.loc[0, "Genus_Problem"] == False
        assert df_obs_out.loc[1, "Genus_Problem"] == True
        assert df_obs_out.loc[2, "Genus_Problem"] == False
        assert df_obs_out["Genus_Problem"].dtype == bool

        # Verify Location Checkbox string contract ("True"/"False")
        assert df_obs_out.loc[0, "Loaned out"] == "True"
        assert df_obs_out.loc[1, "Loaned out"] == "False"
        assert df_obs_out.loc[2, "Loaned out"] == "True"

        # Verify Reviewed boolean coercion
        assert df_obs_out.loc[0, "Reviewed"] == False
        assert df_obs_out.loc[1, "Reviewed"] == True
        assert df_obs_out.loc[2, "Reviewed"] == False

    def test_find_sheet_name_case_and_whitespace(self):
        sheets = ["Registration ", "OBSERVATION", "Photo", "Log_Sheet"]
        assert _find_sheet_name(sheets, "registration") == "Registration "
        assert _find_sheet_name(sheets, "observation") == "OBSERVATION"
        assert _find_sheet_name(sheets, "Photo") == "Photo"
        assert _find_sheet_name(sheets, "NonExistent") is None

    def test_export_and_import_with_photo_sheet_and_styling(self, tmp_path):
        excel_path = str(tmp_path / "styled_export.xlsx")

        config = {
            "sheets": {
                "reg": "Registration",
                "obs": "Observation",
                "photo": "Photo",
                "log": "Log"
            },
            "ui_sections": {
                "registration": [{"name": "Genus"}],
                "location": [],
                "problems": [{"name": "Genus_Problem"}]
            }
        }

        df_reg = pd.DataFrame({"ObjectID": ["1", "2"], "Genus": ["Quercus", "Pinus"], "UID": ["u1", "u2"]})
        df_obs = pd.DataFrame({"ObjectID": ["1", "2"], "Genus_Problem": [False, True]})
        df_photo = pd.DataFrame({"ObjectID": ["1", "1", "2"], "Filename": ["img1.jpg", "img2.jpg", "img3.jpg"]})
        df_log = pd.DataFrame({"Timestamp": ["2026-08-17 12:00:00"], "Action": ["TEST"], "ObjectID": ["1"]})

        # Export to Excel
        SQLiteRepository.export_to_excel(
            sqlite_path=None,
            excel_path=excel_path,
            config=config,
            df_reg=df_reg,
            df_obs=df_obs,
            df_log=df_log,
            df_photo=df_photo
        )

        assert os.path.exists(excel_path)

        # Inspect with openpyxl for freeze_panes and auto_filter
        wb = openpyxl.load_workbook(excel_path)
        assert set(wb.sheetnames) == {"Registration", "Observation", "Photo", "Log"}

        ws_reg = wb["Registration"]
        assert ws_reg.freeze_panes == "A2"
        assert ws_reg.auto_filter.ref is not None
        assert ws_reg.column_dimensions["A"].width >= 10

        # Load back with ExcelRepository and verify data integrity
        df_reg_in, df_obs_in, df_photo_in, df_log_in = ExcelRepository.load_excel(excel_path, config)
        assert list(df_reg_in["ObjectID"]) == ["1", "2"]
        assert list(df_obs_in["ObjectID"]) == ["1", "2"]
        assert list(df_photo_in["ObjectID"]) == ["1", "1", "2"]
        assert list(df_photo_in["Filename"]) == ["img1.jpg", "img2.jpg", "img3.jpg"]
        assert len(df_log_in) == 1

    def test_permission_error_handling_on_export(self, tmp_path):
        excel_path = str(tmp_path / "locked.xlsx")
        config = {"sheets": {}, "ui_sections": {}}
        df_reg = pd.DataFrame({"ObjectID": ["1"]})
        df_obs = pd.DataFrame({"ObjectID": ["1"]})

        with mock.patch("os.replace", side_effect=PermissionError("File locked by Excel")):
            with pytest.raises(PermissionError) as exc_info:
                SQLiteRepository.export_to_excel(
                    sqlite_path=None,
                    excel_path=excel_path,
                    config=config,
                    df_reg=df_reg,
                    df_obs=df_obs
                )
            assert "The file is open in Microsoft Excel" in str(exc_info.value)
            # Ensure tmp file was removed
            tmp_path_check = excel_path + ".tmp.xlsx"
            assert not os.path.exists(tmp_path_check)
