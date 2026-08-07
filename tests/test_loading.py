import pytest
from repository import ExcelRepository
import pandas as pd
import os
import sqlite3

class TestLoading:
    def test_loading_excel(self, tmp_path):
        excel_path = tmp_path / "test.xlsx"

        # Create a dummy excel file
        df_reg = pd.DataFrame({"ObjectID": ["1", "2"]})
        df_obs = pd.DataFrame({"ObjectID": ["1", "2"]})

        with pd.ExcelWriter(excel_path) as writer:
            df_reg.to_excel(writer, sheet_name="Registration", index=False)
            df_obs.to_excel(writer, sheet_name="Observation", index=False)

        config = {
            "sheets": {"reg": "Registration", "obs": "Observation"},
            "ui_sections": {
                "problems": [{"name": "Prob1"}],
                "location": [{"name": "Loc1"}],
                "registration": [{"name": "Reg1"}]
            }
        }

        df_reg_out, df_obs_out, df_photo_out, df_log_out = ExcelRepository.load_excel(excel_path, config)

        assert not df_reg_out.empty
        assert not df_obs_out.empty
        assert list(df_reg_out["ObjectID"]) == ["1", "2"]
