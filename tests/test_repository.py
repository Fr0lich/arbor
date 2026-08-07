import pandas as pd
import os
from unittest import mock
from repository import ExcelRepository, SQLiteRepository, _normalise_dataframes, _normalise_log_dataframe

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

        SQLiteRepository.save_sqlite(str(db_path), df_reg, df_obs, df_photo, df_log)

        assert os.path.exists(db_path)

        config = {"ui_sections": {}}
        df_reg_read, df_obs_read, df_photo_read, df_log_read = SQLiteRepository.load_sqlite(str(db_path), config)

        assert list(df_reg_read["ObjectID"]) == ["1", "2"]
        assert list(df_obs_read["ObjectID"]) == ["1", "2"]
        assert list(df_photo_read["ObjectID"]) == ["1"]

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
        mock_load_excel.return_value = (mock_df_reg, mock_df_obs, mock_df_photo, mock_df_log)

        # Execute the method under test
        result = SQLiteRepository.import_from_excel(str(excel_path), str(sqlite_path), config)

        # Assert correct methods were called
        mock_load_excel.assert_called_once_with(str(excel_path), config)
        mock_save_sqlite.assert_called_once_with(str(sqlite_path), mock_df_reg, mock_df_obs, mock_df_photo, mock_df_log)

        # Assert return values
        assert result == (mock_df_reg, mock_df_obs, mock_df_photo, mock_df_log)

        # Assert backup was created correctly
        backup_dir = tmp_path / "backups"
        assert backup_dir.exists()
        assert backup_dir.is_dir()

        backup_files = list(backup_dir.iterdir())
        assert len(backup_files) == 1
        assert backup_files[0].name.startswith("data.xlsx.backup_")
        assert backup_files[0].name.endswith(".xlsx")
        assert backup_files[0].read_text() == "dummy content"
