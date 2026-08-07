from repository import SQLiteRepository
import pandas as pd
import os

class TestSaving:
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
