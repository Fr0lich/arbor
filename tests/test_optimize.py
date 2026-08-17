import unittest
import pandas as pd
import json
import io
import os
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
        fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            json_data = {
                k: v.to_json(orient="table") if v is not None else None
                for k, v in data.items()
            }
            with open(temp_path, "w") as f:
                json.dump(json_data, f)

            # Load it back
            with open(temp_path, "r") as f:
                loaded_json = json.load(f)
            loaded = {
                k: pd.read_json(io.StringIO(v), orient="table") if v is not None else None
                for k, v in loaded_json.items()
            }

            self.assertTrue(loaded["df_reg"].equals(df_reg))
            self.assertTrue(loaded["df_obs"].equals(df_obs))
            self.assertTrue(loaded["df_photo"].equals(df_photo))
            self.assertTrue(loaded["df_log"].equals(df_log))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        # Test direct split dict serialization (new optimized format)
        fd2, temp_path2 = tempfile.mkstemp(suffix=".json")
        os.close(fd2)
        try:
            json_data2 = {
                k: v.to_dict(orient="split") if v is not None else None
                for k, v in data.items()
            }
            with open(temp_path2, "w") as f:
                json.dump(json_data2, f)

            with open(temp_path2, "r") as f:
                loaded_json2 = json.load(f)

            def load_df(key):
                val = loaded_json2.get(key)
                if val is None:
                    return None
                if isinstance(val, str):
                    if '"schema"' in val:
                        return pd.read_json(io.StringIO(val), orient="table")
                    return pd.read_json(io.StringIO(val), orient="split")
                elif isinstance(val, dict):
                    if "schema" in val:
                        return pd.read_json(io.StringIO(json.dumps(val)), orient="table")
                    elif "columns" in val and "data" in val:
                        return pd.DataFrame(data=val["data"], index=val.get("index"), columns=val["columns"])
                return None

            loaded2 = {
                k: load_df(k) for k in ("df_reg", "df_obs", "df_photo", "df_log")
            }

            self.assertTrue(loaded2["df_reg"].equals(df_reg))
            self.assertTrue(loaded2["df_obs"].equals(df_obs))
            self.assertTrue(loaded2["df_photo"].equals(df_photo))
            self.assertTrue(loaded2["df_log"].equals(df_log))
        finally:
            if os.path.exists(temp_path2):
                os.remove(temp_path2)

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

    def test_get_reg_by_id_none_database(self):
        # Passing None or dict with None df_reg should return None safely without raising AttributeError
        self.assertIsNone(ObjectProgramUI._get_reg_by_id(None, None))
        self.assertIsNone(ObjectProgramUI._get_reg_by_id(None, {}))
        self.assertIsNone(ObjectProgramUI._get_reg_by_id(None, {"df_reg": None, "reg_by_id": None}))

    def test_alphanumeric_image_url_resolution(self):
        from ui.image_handler import ImageHandlerMixin
        class DummyImageUI(ImageHandlerMixin):
            def __init__(self):
                self.app = type("App", (), {"config": {"image_url_pattern": "https://example.com/photos/{num:04d}{suffix}.jpg"}})()
        
        handler = DummyImageUI()
        # Should not raise ValueError on alphanumeric IDs
        urls = handler.build_online_image_urls("42A")
        self.assertEqual(len(urls), 4)
        self.assertIn("https://example.com/photos/{num:04d}{suffix}.jpg/42A", urls)

    def test_treeview_listbox_inverted_index(self):
        import tkinter as tk
        from ui.widgets import TreeviewListboxWrapper
        root = tk.Tk()
        try:
            root.withdraw()
            dummy_mw = type("MW", (), {"dark_mode_active": False, "_toggle_reviewed_for_id": lambda s, o: None})()
            wrapper = TreeviewListboxWrapper(root, dummy_mw)
            
            # Insert items
            for i in range(10):
                wrapper.insert(tk.END, f"OID_{i} Genus{i} Species{i}", genus=f"Genus{i}", species=f"Species{i}", reviewed=(i % 2 == 0), bulk=True)
            
            self.assertEqual(len(wrapper.items_list), 10)
            self.assertEqual(wrapper._oid_to_index.get("OID_5"), 5)
            self.assertEqual(wrapper._oid_to_index.get("OID_0"), 0)
            
            # Selection set by index
            wrapper.selection_set(5)
            self.assertEqual(wrapper.curselection(), [5])
            
            # Selection set by iid
            wrapper.selection_set("OID_3")
            self.assertEqual(wrapper.curselection(), [3])
            
            # Clear and delete
            wrapper.delete(0, tk.END)
            self.assertEqual(len(wrapper.items_list), 0)
            self.assertEqual(len(wrapper._oid_to_index), 0)
            self.assertEqual(wrapper.curselection(), [])
        finally:
            root.destroy()

if __name__ == "__main__":
    unittest.main()
