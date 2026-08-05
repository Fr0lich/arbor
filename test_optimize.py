import unittest
import pandas as pd
from ui.main_window import ObjectProgramUI

class TestOptimize(unittest.TestCase):
    def test_get_reg_by_id_cached(self):
        # When reg_by_id is already in the db dict, it should be returned directly
        mock_reg_by_id = object()
        db = {
            "reg_by_id": mock_reg_by_id
        }
        # ObjectProgramUI._get_reg_by_id can be called by passing None as self
        result = ObjectProgramUI._get_reg_by_id(None, db)
        self.assertIs(result, mock_reg_by_id)

    def test_get_reg_by_id_build_index(self):
        # When reg_by_id is None, it should set it using df_reg indexed by ObjectID
        df_reg = pd.DataFrame({
            "ObjectID": ["A1", "B2"],
            "Value": ["Val1", "Val2"]
        })
        db = {
            "df_reg": df_reg,
            "reg_by_id": None
        }
        result = ObjectProgramUI._get_reg_by_id(None, db)
        self.assertIsNotNone(result)
        self.assertIn("A1", result.index)
        self.assertIn("B2", result.index)
        self.assertEqual(result.loc["A1", "Value"], "Val1")
        self.assertIs(db["reg_by_id"], result)

    def test_get_reg_by_id_exception_handling(self):
        # When df_reg is missing or not a DataFrame, it should handle exception and return None
        db = {
            "df_reg": None,
            "reg_by_id": None
        }
        result = ObjectProgramUI._get_reg_by_id(None, db)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
