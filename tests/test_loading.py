from repository import ExcelRepository
import pandas as pd

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

    def test_loading_excel_missing_sheets(self, tmp_path):
        excel_path = tmp_path / "test_missing.xlsx"

        # Create a dummy excel file with ONLY Registration
        df_reg = pd.DataFrame({"ObjectID": ["1", "2"]})

        with pd.ExcelWriter(excel_path) as writer:
            df_reg.to_excel(writer, sheet_name="Registration", index=False)

        config = {
            "sheets": {"reg": "Registration", "obs": "Observation", "log": "Log"},
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
        assert list(df_obs_out["ObjectID"]) == ["1", "2"]
        assert "Prob1" in df_obs_out.columns
        assert "Loc1" in df_obs_out.columns
        assert df_log_out.empty  # Normalised log DataFrame is empty of rows
        assert "Timestamp" in df_log_out.columns
