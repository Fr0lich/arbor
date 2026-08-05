import unittest
import pandas as pd
import pickle
import os
import shutil
import tempfile
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

    def test_lambda_deferred_exception_binding(self):
        # Test that lambda behaves correctly when capturing exception details eagerly via default arguments
        callbacks = []
        try:
            raise ValueError("Test Exception")
        except ValueError as e:
            err_msg = str(e)
            tb = "mock_traceback"
            # Define lambda with default arguments to capture eagerly
            callbacks.append(lambda msg=err_msg, t=tb: (msg, t))
            # e will be deleted after the except block, but lambda should still succeed

        # Verify lambda successfully retrieves exception message and traceback without NameError
        msg, t = callbacks[0]()
        self.assertEqual(msg, "Test Exception")
        self.assertEqual(t, "mock_traceback")

    def test_pickle_serialization_and_deserialization(self):
        # Test that df dataframes can be pickled and unpickled correctly
        df_reg = pd.DataFrame({"ObjectID": ["1", "2"], "Genus": ["Genus1", "Genus2"]})
        df_obs = pd.DataFrame({"ObjectID": ["1", "2"], "Reviewed": [True, False]})
        df_photo = pd.DataFrame({"ObjectID": ["1"]})
        df_log = pd.DataFrame({"Timestamp": ["2025-02-15"]})

        data = {
            "df_reg": df_reg,
            "df_obs": df_obs,
            "df_photo": df_photo,
            "df_log": df_log
        }

        # Use temporary file
        fd, temp_path = tempfile.mkstemp(suffix=".pkl")
        os.close(fd)
        try:
            with open(temp_path, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Load it back
            with open(temp_path, "rb") as f:
                loaded = pickle.load(f)

            self.assertTrue(loaded["df_reg"].equals(df_reg))
            self.assertTrue(loaded["df_obs"].equals(df_obs))
            self.assertTrue(loaded["df_photo"].equals(df_photo))
            self.assertTrue(loaded["df_log"].equals(df_log))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_update_dashboard_vectorized_logic(self):
        # Test the core logic used in our optimized update_dashboard method.
        # We check that .any(axis=1) works properly on a DataFrame.
        df_obs = pd.DataFrame({
            "ObjectID": ["1", "2", "3"],
            "Genus_Problem": [True, False, False],
            "Species_Problem": [False, True, False]
        }).set_index("ObjectID")

        problem_columns = ["Genus_Problem", "Species_Problem"]
        cols = [p for p in problem_columns if p in df_obs.columns]

        has_prob_series = df_obs[cols].any(axis=1)
        self.assertTrue(has_prob_series.loc["1"])
        self.assertTrue(has_prob_series.loc["2"])
        self.assertFalse(has_prob_series.loc["3"])

        # Test dropping current_oid
        other_sum = has_prob_series.drop("1", errors="ignore").sum()
        self.assertEqual(other_sum, 1)

if __name__ == "__main__":
    unittest.main()
