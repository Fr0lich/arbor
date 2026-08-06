import unittest
import pandas as pd
from repository import (
    ExcelRepository,
    SQLiteRepository,
    ONLINE_EXISTS_COLUMN,
    REVIEWED_COLUMN,
    REVIEWED_AT_COLUMN
)

class TestRepository(unittest.TestCase):
    def test_generate_empty_dataframes(self):
        config = {
            "ui_sections": {
                "registration": [
                    {"name": "Genus"},
                    {"name": "Species"}
                ],
                "location": [
                    {"name": "Country"},
                    {"name": "County"}
                ],
                "problems": [
                    {"name": "Genus_Problem"},
                    {"name": "Damage"}
                ]
            }
        }

        df_reg, df_obs, df_log = SQLiteRepository.generate_empty_dataframes(config)

        # Assert returned objects are DataFrames
        self.assertIsInstance(df_reg, pd.DataFrame)
        self.assertIsInstance(df_obs, pd.DataFrame)
        self.assertIsInstance(df_log, pd.DataFrame)

        # Verify df_reg columns
        expected_reg_cols = ["ObjectID", "Genus", "Species"]
        self.assertEqual(list(df_reg.columns), expected_reg_cols)

        # Verify df_obs columns
        expected_obs_cols = [
            "ObjectID",
            "Country",
            "County",
            "Genus_Problem",
            "Damage",
            "Images_Missing",
            "Images_Problem",
            "Images_Wrong",
            ONLINE_EXISTS_COLUMN,
            REVIEWED_COLUMN,
            REVIEWED_AT_COLUMN
        ]
        self.assertEqual(list(df_obs.columns), expected_obs_cols)

if __name__ == "__main__":
    unittest.main()
