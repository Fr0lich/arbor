import pandas as pd
import os
from unittest import mock
from repository import SQLiteRepository, _normalise_dataframes, _normalise_log_dataframe

class TestRepository:
    def test_normalise_dataframes(self):
        df_reg = pd.DataFrame({"ObjectID": [" 1 ", "2"]})
        df_obs = pd.DataFrame({"ObjectID": ["1", " 2 "]})
        config = {
            "ui_sections": {
                "problems": [{"name": "Prob1"}],
                "location": [{"name": "Loc1"}],
                "registration": [{"name": "Reg1"}]
            }
        }

        df_reg_out, df_obs_out = _normalise_dataframes(df_reg, df_obs, config)

        # Test ObjectID cleaning
        assert list(df_reg_out["ObjectID"]) == ["1", "2"]
        assert list(df_obs_out["ObjectID"]) == ["1", "2"]

        # Test registration columns
        assert "Reg1" in df_reg_out.columns
        assert "UID" in df_reg_out.columns
        assert "ProblemDescription" in df_reg_out.columns

        # Test problem columns
        assert "Prob1" in df_obs_out.columns

        # Test location columns
        assert "Loc1" in df_obs_out.columns

        # Test default obs columns
        assert "Images_Missing" in df_obs_out.columns
        assert "Images_Problem" in df_obs_out.columns
        assert "Reviewed" in df_obs_out.columns

    def test_sqlite_roundtrip(self, tmp_path):
        db_path = tmp_path / "test.db"

        df_reg = pd.DataFrame({"ObjectID": ["1", "2"], "UID": ["u1", "u2"], "ProblemDescription": ["p1", "p2"]})
        df_obs = pd.DataFrame({"ObjectID": ["1", "2"], "Images_Missing": [True, False], "Images_Problem": [False, False], "Reviewed": [False, False], "ReviewedAt": ["", ""], "Online_Images_Exist": [False, False]})
        df_photo = pd.DataFrame({"ObjectID": ["1"]})
        df_log = _normalise_log_dataframe(pd.DataFrame())
        df_unval = pd.DataFrame({"ObjectID": ["1"], "Field_Name": ["Genus"], "Unvalidated_Comment": ["Check spelling"]})

        SQLiteRepository.save_sqlite(str(db_path), df_reg, df_obs, df_photo, df_log, df_unval)

        assert os.path.exists(db_path)

        config = {"ui_sections": {}}
        df_reg_read, df_obs_read, df_photo_read, df_log_read, df_unval_read = SQLiteRepository.load_sqlite(str(db_path), config)

        assert list(df_reg_read["ObjectID"]) == ["1", "2"]
        assert list(df_obs_read["ObjectID"]) == ["1", "2"]
        assert list(df_photo_read["ObjectID"]) == ["1"]
        assert list(df_unval_read["Field_Name"]) == ["Genus"]
        assert list(df_unval_read["Unvalidated_Comment"]) == ["Check spelling"]

    @mock.patch("repository.ExcelRepository.load_excel")
    @mock.patch("repository.SQLiteRepository.save_sqlite")
    def test_import_from_excel(self, mock_save_sqlite, mock_load_excel, tmp_path):
        # Create a dummy excel file to be backed up
        excel_path = tmp_path / "data.xlsx"
        excel_path.write_text("dummy content")

        sqlite_path = tmp_path / "data.db"
        config = {"ui_sections": {}}

        # Setup mock return values for load_excel
        mock_df_reg = pd.DataFrame({"ObjectID": ["1"]})
        mock_df_obs = pd.DataFrame({"ObjectID": ["1"]})
        mock_df_photo = pd.DataFrame({"ObjectID": ["1"]})
        mock_df_log = pd.DataFrame({"ObjectID": ["1"]})
        mock_df_unval = pd.DataFrame({"ObjectID": ["1"], "Field_Name": ["Species"], "Unvalidated_Comment": ["Note"]})
        mock_load_excel.return_value = (mock_df_reg, mock_df_obs, mock_df_photo, mock_df_log, mock_df_unval)

        # Execute the method under test
        result = SQLiteRepository.import_from_excel(str(excel_path), str(sqlite_path), config)

        # Assert correct methods were called
        mock_load_excel.assert_called_once_with(str(excel_path), config)
        mock_save_sqlite.assert_called_once_with(str(sqlite_path), mock_df_reg, mock_df_obs, mock_df_photo, mock_df_log, mock_df_unval)

        # Assert return values
        assert result == (mock_df_reg, mock_df_obs, mock_df_photo, mock_df_log, mock_df_unval)

        # Assert backup was created correctly
        backup_dir = tmp_path / "backups"
        assert backup_dir.exists()
        assert backup_dir.is_dir()

        backup_files = list(backup_dir.iterdir())
        assert len(backup_files) == 1
        assert backup_files[0].name.startswith("data.xlsx.backup_")
        assert backup_files[0].name.endswith(".xlsx")
        assert backup_files[0].read_text() == "dummy content"


    def test_export_to_excel(self, tmp_path):
        excel_path = tmp_path / "test_out.xlsx"
        df_reg = pd.DataFrame({"ObjectID": ["1", "2"], "UID": ["u1", "u2"], "ProblemDescription": ["p1", "p2"]})
        df_obs = pd.DataFrame({"ObjectID": ["1", "2"]})
        df_log = pd.DataFrame()
        config = {
            "sheets": {"reg": "Registration", "obs": "Observation"},
            "ui_sections": {}
        }
        SQLiteRepository.export_to_excel(None, str(excel_path), config, df_reg=df_reg, df_obs=df_obs, df_log=df_log)
        assert os.path.exists(excel_path)
        df_reg_read = pd.read_excel(excel_path, sheet_name="Registration")
        assert list(df_reg_read["ObjectID"]) == [1, 2]

    def test_normalise_dataframes_checkbox_default(self):
        config = {
            "ui_sections": {
                "location": [
                    {"name": "Building", "type": "choice"},
                    {"name": "Loaned out", "type": "checkbox"},
                    {"name": "Loaned out date", "type": "text"}
                ],
                "problems": [],
                "registration": [{"name": "Genus"}]
            }
        }
        df_reg = pd.DataFrame({"ObjectID": ["1", "2", "3", "4", "5"]})
        df_obs = pd.DataFrame({
            "ObjectID": ["1", "2", "3", "4", "5"],
            "Loaned out": ["", "True", False, True, None]
        })
        df_reg, df_obs = _normalise_dataframes(df_reg, df_obs, config)
        assert df_obs.loc[df_obs["ObjectID"] == "1", "Loaned out"].iloc[0] == "False"
        assert df_obs.loc[df_obs["ObjectID"] == "2", "Loaned out"].iloc[0] == "True"
        assert df_obs.loc[df_obs["ObjectID"] == "3", "Loaned out"].iloc[0] == "False"
        assert df_obs.loc[df_obs["ObjectID"] == "4", "Loaned out"].iloc[0] == "True"
        assert df_obs.loc[df_obs["ObjectID"] == "5", "Loaned out"].iloc[0] == "False"

    def test_sanitize_df_timezone(self):
        from utils import sanitize_df_for_excel
        df = pd.DataFrame({"a": [pd.Timestamp("2020-01-01", tz="UTC")]})
        df_safe = sanitize_df_for_excel(df)
        assert pd.api.types.is_datetime64_any_dtype(df_safe["a"])
        assert df_safe["a"].dt.tz is None

    def test_sanitize_df_illegal_chars(self):
        from utils import sanitize_df_for_excel
        df = pd.DataFrame({"a": ["hello\x00world"]})
        df_safe = sanitize_df_for_excel(df)
        assert df_safe["a"].iloc[0] == "helloworld"

    def test_sanitize_df_formula_injection(self):
        from utils import sanitize_df_for_excel
        df = pd.DataFrame({"a": ["=1+1", "-2+2", "cmd|foo", "test"]})
        df_safe = sanitize_df_for_excel(df)
        assert df_safe["a"].iloc[0] == "'=1+1"
        assert df_safe["a"].iloc[1] == "'-2+2"
        assert df_safe["a"].iloc[2] == "'cmd|foo"
        assert df_safe["a"].iloc[3] == "test"

    def test_atomic_save_failure_leaves_original_intact(self, tmp_path):
        """Verify that if an error occurs midway through writing, the original Excel file remains untouched."""
        excel_path = tmp_path / "botanical_records.xlsx"
        config = {
            "sheets": {"reg": "Registration", "obs": "Observation"},
            "ui_sections": {}
        }
        # Create valid original file
        df_reg_orig = pd.DataFrame({"ObjectID": ["001", "002"], "Genus": ["Rosa", "Pinus"]})
        df_obs_orig = pd.DataFrame({"ObjectID": ["001", "002"], "Reviewed": [True, False]})
        SQLiteRepository.export_to_excel(None, str(excel_path), config, df_reg=df_reg_orig, df_obs=df_obs_orig)
        original_mtime = os.path.getmtime(excel_path)
        original_size = os.path.getsize(excel_path)

        # Attempt to overwrite with new data but simulate failure during save
        df_reg_bad = pd.DataFrame({"ObjectID": ["999"], "Genus": ["Corrupted"]})
        def failing_progress(cur, total, label):
            if cur >= 1:
                raise RuntimeError("Simulated write failure")

        import pytest
        with pytest.raises(RuntimeError, match="Simulated write failure"):
            SQLiteRepository.export_to_excel(
                None, str(excel_path), config,
                df_reg=df_reg_bad, df_obs=df_obs_orig,
                progress_callback=failing_progress
            )

        # Verify original file is completely intact
        assert os.path.exists(excel_path)
        assert os.path.getsize(excel_path) == original_size
        assert os.path.getmtime(excel_path) == original_mtime
        from repository import ExcelRepository
        df_reg_check, _, _, _, _ = ExcelRepository.load_excel(str(excel_path), config)
        assert list(df_reg_check["ObjectID"]) == ["001", "002"]

        # Verify no orphan temporary files left behind
        tmp_files = [f for f in os.listdir(tmp_path) if ".tmp_" in f]
        assert len(tmp_files) == 0

    def test_permission_error_locked_excel_handling(self, tmp_path):
        """Simulate Windows file lock (PermissionError) when desktop Excel has the file open."""
        from utils import ExcelFileLockedError
        import pytest
        excel_path = tmp_path / "locked_curation.xlsx"
        config = {
            "sheets": {"reg": "Registration", "obs": "Observation"},
            "ui_sections": {}
        }
        df_reg = pd.DataFrame({"ObjectID": ["000142"], "Genus": ["Betula"]})
        df_obs = pd.DataFrame({"ObjectID": ["000142"], "Reviewed": [True]})

        with mock.patch("os.replace", side_effect=PermissionError(13, "Permission denied")):
            with pytest.raises(ExcelFileLockedError) as exc_info:
                SQLiteRepository.export_to_excel(None, str(excel_path), config, df_reg=df_reg, df_obs=df_obs)

            # Check that the trainee-friendly error message is surfaced
            msg = str(exc_info.value)
            assert "locked_curation.xlsx" in msg
            assert "currently open in Microsoft Excel or another program" in msg
            assert "Please close Excel and click 'Retry Save'" in msg

        # Ensure temporary file was removed
        tmp_files = [f for f in os.listdir(tmp_path) if ".tmp_" in f]
        assert len(tmp_files) == 0

    def test_presave_backup_rolling_limit(self, tmp_path):
        """Verify automatic pre-save backups in .arbor_backups capped at rolling limit of 5."""
        from utils import create_presave_backup
        excel_path = tmp_path / "rolling_test.xlsx"
        config = {
            "sheets": {"reg": "Registration", "obs": "Observation"},
            "ui_sections": {}
        }
        df_reg = pd.DataFrame({"ObjectID": ["1"], "Genus": ["Carex"]})
        df_obs = pd.DataFrame({"ObjectID": ["1"]})

        # Save once to create the file
        SQLiteRepository.export_to_excel(None, str(excel_path), config, df_reg=df_reg, df_obs=df_obs)

        # Trigger 7 backup cycles directly
        for _ in range(7):
            create_presave_backup(str(excel_path), max_backups=5)

        backup_dir = tmp_path / ".arbor_backups"
        assert backup_dir.exists()
        backups = [f for f in os.listdir(backup_dir) if f.startswith("rolling_test.xlsx.") and f.endswith(".bak")]
        assert len(backups) <= 5

    def test_leading_zero_and_data_type_preservation(self, tmp_path):
        """Ensure string accession numbers with leading zeros (e.g. '000142') and booleans are preserved."""
        from repository import ExcelRepository
        excel_path = tmp_path / "accessions.xlsx"
        config = {
            "sheets": {"reg": "Registration", "obs": "Observation"},
            "ui_sections": {
                "problems": [{"name": "Genus_Problem"}],
                "location": [{"name": "Cabinet"}],
                "registration": [{"name": "Genus"}]
            }
        }
        raw_ids = ["000142", "000007", "008901", "12345"]
        df_reg = pd.DataFrame({
            "ObjectID": raw_ids,
            "Genus": ["Salix", "Vaccinium", "Empetrum", "Taraxacum"],
            "UID": ["u1", "u2", "u3", "u4"],
            "ProblemDescription": ["", "", "", ""]
        })
        df_obs = pd.DataFrame({
            "ObjectID": raw_ids,
            "Reviewed": [True, False, True, False],
            "ReviewedAt": ["2026-11-13 10:00:00", "", "2026-11-13 11:00:00", ""],
            "Genus_Problem": [False, True, False, False],
            "Images_Missing": [False, True, False, False],
            "Images_Problem": [False, False, False, False],
            "Online_Images_Exist": [False, False, False, False]
        })

        # Save and reload through Arbor's ExcelRepository
        SQLiteRepository.export_to_excel(None, str(excel_path), config, df_reg=df_reg, df_obs=df_obs)
        df_reg_loaded, df_obs_loaded, _, _, _ = ExcelRepository.load_excel(str(excel_path), config)

        # Assert leading zeroes are never coerced to integers
        assert list(df_reg_loaded["ObjectID"]) == raw_ids
        assert list(df_obs_loaded["ObjectID"]) == raw_ids

        # Assert booleans are strictly preserved
        assert list(df_obs_loaded["Reviewed"]) == [True, False, True, False]
        assert list(df_obs_loaded["Genus_Problem"]) == [False, True, False, False]
        assert list(df_obs_loaded["Images_Missing"]) == [False, True, False, False]

