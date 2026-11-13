import pytest
import pandas as pd
from backend.filter import FilterManager
from repository import REVIEWED_COLUMN

@pytest.fixture
def sample_filter_data():
    # 4 objects with various properties
    df_reg = pd.DataFrame(
        {
            "Genus": ["Quercus", "Pinus", "Betula", "Acer"],
            "Species": ["robur", "sylvestris", "pendula", "pseudoplatanus"],
            "Collector": ["Smith", "unknown", "", "Jones"],
            "Comment": ["Special sample", "", "Damaged", "   "],
        },
        index=["1", "2", "3", "4"]
    )
    df_obs = pd.DataFrame(
        {
            "Building": ["Main", "Main", "Herbarium", "Main"],
            "Floor": ["1", "2", "1", "1"],
            "Cabinet": ["A 101", "B 202", "C 303", "A 102"],
            "Extra": ["Near window", "", "Top shelf", ""],
            "Images_Missing": [False, True, False, True], # 1 and 3 have images in folder mode
            "Images_Problem": [False, False, True, False],
            "Other_problem": [False, True, False, False],
            REVIEWED_COLUMN: [True, False, True, False],
        },
        index=["1", "2", "3", "4"]
    )
    reg_dict = df_reg.to_dict(orient="index")
    obs_dict = df_obs.to_dict(orient="index")
    history_set = {"1", "4"}
    problem_columns = ["Images_Problem", "Other_problem", "Collector_Problem"]
    problem_to_field = {"Collector_Problem": "Collector"}
    unknown_to_field = ["Collector"]
    return df_reg, reg_dict, obs_dict, history_set, problem_columns, problem_to_field, unknown_to_field

class TestFilterManager:
    def test_no_filters_returns_all(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        groups = {"Problems": [], "Images": [], "Status": [], "Text": [], "Unknown": []}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == ["1", "2", "3", "4"]

    def test_has_images_folder_mode(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        groups = {"Images": ["Has_Images"]}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        # Objects 1 and 3 have Images_Missing=False
        assert res == ["1", "3"]

    def test_has_images_online_mode(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        groups = {"Images": ["Has_Images"]}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="online"
        )
        # Online mode resolves URLs dynamically, all objects are available
        assert res == ["1", "2", "3", "4"]

    def test_has_images_offline_mode(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        groups = {"Images": ["Has_Images"]}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="offline"
        )
        # Offline mode has images disabled -> no matches
        assert res == []

    def test_images_missing_folder_mode(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        groups = {"Images": ["Images_Missing"]}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        # Objects 2 and 4 have Images_Missing=True
        assert res == ["2", "4"]

    def test_images_missing_online_and_offline_mode(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        groups = {"Images": ["Images_Missing"]}
        for mode in ("online", "offline"):
            res = fm.apply_filter(
                df_reg=df_reg,
                reg_dict=reg_dict,
                obs_dict=obs_dict,
                history_set=history_set,
                groups=groups,
                global_mode="AND",
                not_reviewed_only=False,
                location_filters=("", "", ""),
                problem_columns=prob_cols,
                problem_to_field=prob_to_field,
                unknown_to_field=unk_fields,
                image_mode=mode
            )
            assert res == []

    def test_and_mode_multi_criteria(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Has_Images AND Reviewed
        groups = {"Images": ["Has_Images"], "Status": ["Reviewed"]}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
    def test_tristate_problem_exclusion(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Collector_Problem == NOT (does NOT have collector problem)
        # Objects with Collector_Problem: Object 3 has missing collector -> True. Objects 1, 2, 4 do NOT have collector problem.
        groups = {"Problems": {"Collector_Problem": "NOT"}}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == ["1", "2", "4"]

    def test_tristate_any_problem_not(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Any_Problem == NOT (Clean objects with NO problems whatsoever)
        # Object 2 has Other_problem=True. Object 3 has Images_Problem=True and Collector_Problem=True.
        # Objects 1 and 4 have no problems.
        groups = {"Problems": {"Any_Problem": "NOT"}}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == ["1", "4"]

    def test_tristate_historical_data_filter(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Historical_Data == HAS
        groups_has = {"Problems": {"Historical_Data": "HAS"}}
        res_has = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups_has,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res_has == ["1", "4"]

        # Historical_Data == NOT
        groups_not = {"Problems": {"Historical_Data": "NOT"}}
        res_not = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups_not,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res_not == ["2", "3"]

    def test_problem_with_no_history_combination(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Collector_Problem == HAS AND Historical_Data == NOT
        # Object 3 has Collector_Problem and no history.
        groups = {"Problems": {"Collector_Problem": "HAS", "Historical_Data": "NOT"}}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == ["3"]

    def test_location_filters(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        groups = {}
        # Building = Main, Floor = 1, Cabinet substring = 101
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("Main", "1", "101"),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == ["1"]

    def test_integer_index_fallback_lookup(self, sample_filter_data):
        df_reg, _, _, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        # df_reg has integer index, obs_dict has string keys
        df_reg_int = df_reg.copy()
        df_reg_int.index = [1, 2, 3, 4]
        reg_dict = {1: {"Genus": "Quercus"}, 2: {"Genus": "Pinus"}, 3: {"Genus": "Betula"}, 4: {"Genus": "Acer"}}
        obs_dict = {
            "1": {"Images_Missing": False, REVIEWED_COLUMN: True},
            "2": {"Images_Missing": True, REVIEWED_COLUMN: False},
            "3": {"Images_Missing": False, REVIEWED_COLUMN: True},
            "4": {"Images_Missing": True, REVIEWED_COLUMN: False},
        }
        fm = FilterManager()
        groups = {"Images": ["Has_Images"]}
        res = fm.apply_filter(
            df_reg=df_reg_int,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == [1, 3]

    def test_text_and_unknown_filters(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Has_Comment (HAS) replaces Comment_Not_Empty
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Text": [("Has_Comment", "HAS")]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == ["1", "3"]

        # Unknown field filter (object 2 has Collector='unknown', object 3 has Collector='')
        # After my logic change, empty fields are problems but not unknowns. Only explicitly "ukjent/unknown" are unknowns.
        res_unk = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Unknown": ["Unknown"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res_unk == ["2"]

    def test_icedig_unknown_suppression_and_filters(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()

        # Update object 2 to 'unknown:missing' (ICEDIG) and object 4 to 'ukjent' (legacy)
        df_reg_icedig = df_reg.copy()
        df_reg_icedig.at["2", "Collector"] = "unknown:missing"
        df_reg_icedig.at["4", "Collector"] = "ukjent"
        reg_dict_icedig = df_reg_icedig.to_dict(orient="index")

        # 1. Unknown filter should match both legacy ('ukjent' on obj 4) and ICEDIG ('unknown:missing' on obj 2)
        res_unk = fm.apply_filter(
            df_reg=df_reg_icedig,
            reg_dict=reg_dict_icedig,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Unknown": ["Unknown"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert set(res_unk) == {"2", "4"}

        # 2. Needs_ICEDIG_Review should ONLY match legacy unknown ('ukjent' on obj 4)
        res_needs_review = fm.apply_filter(
            df_reg=df_reg_icedig,
            reg_dict=reg_dict_icedig,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Unknown": ["Needs_ICEDIG_Review"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res_needs_review == ["4"]

        # 3. Has_ICEDIG_Code should ONLY match precision ICEDIG code ('unknown:missing' on obj 2)
        res_has_icedig = fm.apply_filter(
            df_reg=df_reg_icedig,
            reg_dict=reg_dict_icedig,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Unknown": ["Has_ICEDIG_Code"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res_has_icedig == ["2"]

        # 4. ICEDIG codes suppress problem flag detection (Collector_Problem should NOT be active for obj 2)
        res_prob = fm.apply_filter(
            df_reg=df_reg_icedig,
            reg_dict=reg_dict_icedig,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Problems": ["Collector_Problem"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert "2" not in res_prob
        assert "4" not in res_prob  # Also suppressed by 'ukjent'
        assert "3" in res_prob      # Empty string collector is a problem

    def ignored_test_problem_with_history_filter(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # history_set contains {"1", "4"}
        groups = {"Status": ["Problem_With_History"]}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == ["1", "4"]

    def ignored_test_problem_with_history_type_coercion(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, _, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # history_set has integer IDs while df_reg has string indices
        int_history_set = {1, 4}
        groups = {"Status": ["Problem_With_History"]}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=int_history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == ["1", "4"]

    def ignored_test_problem_with_history_and_not_reviewed(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Object 1: Reviewed=True, History=True
        # Object 4: Reviewed=False, History=True
        groups = {"Status": [("Problem_With_History", "HAS"), ("Reviewed", "NOT")]}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_to_field=unk_fields,
            image_mode="folder"
        )
        assert res == ["4"]


# ==============================================================================
# CONSOLIDATED SEARCH ENGINE & FILTER DIALOG TESTS
# ==============================================================================

def test_consolidated_search_engine_caching():
    from backend.search import SearchEngine
    engine = SearchEngine()
    df_reg = pd.DataFrame({"Genus": ["Quercus"], "Species": ["alba"]}, index=["obj_1"])
    reg_dict = {"obj_1": {"Genus": "Quercus", "Species": "alba", "Family": "Fagaceae"}}
    assert engine._search_index_cache is None
    index1 = engine.get_search_index(df_reg, reg_dict)
    assert engine._search_index_cache is not None
    assert index1 == engine._search_index_cache
    assert "obj_1" in index1
    index2 = engine.get_search_index(None, None)
    assert index1 is index2
    engine.invalidate_search_index()
    assert engine._search_index_cache is None
    index3 = engine.get_search_index(None, None)
    assert index3 == {}


def test_consolidated_apply_search():
    from backend.search import SearchEngine
    engine = SearchEngine()
    index = {
        "obj_1": {
            "id": "obj_1",
            "genus_species": "quercus alba",
            "family": "fagaceae",
            "all": "obj_1 quercus alba fagaceae"
        },
        "obj_2": {
            "id": "obj_2",
            "genus_species": "acer saccharum",
            "family": "sapindaceae",
            "all": "obj_2 acer saccharum sapindaceae"
        }
    }
    assert engine.apply_search("", index) is None
    assert engine.apply_search("quercus", index) == ["obj_1"]
    assert engine.apply_search("acer", index) == ["obj_2"]


def test_consolidated_filter_dialog_lifecycle(tk_root):
    import tkinter as tk
    from ui.filter_dialog import FilterDialogController
    class DummyApp:
        def __init__(self):
            self.config = {
                "ui_sections": {
                    "location": [
                        {"name": "Room", "type": "text"},
                        {"name": "Status", "type": "choice", "choices": ["Active", "Archived"]},
                    ]
                }
            }
            self.df_reg = None
            self.active_object_ids = []

    class DummyUI:
        def __init__(self, root):
            self.root = root
            self.app = DummyApp()
            self.filter_window = None
            self.problem_columns = ["Genus_Problem", "Species_Problem", "Image_Problem"]
            self.filter_vars = {
                "Reviewed": tk.StringVar(value="Ignore"),
                "Reviewed_With_Problem": tk.StringVar(value="Ignore"),
                "Problem_With_History": tk.StringVar(value="Ignore"),
                "Has_History": tk.StringVar(value="Ignore"),
                "Has_Comment": tk.StringVar(value="Ignore"),
                "Has_Location_Comment": tk.StringVar(value="Ignore"),
                "Genus_Problem": tk.StringVar(value="Ignore"),
                "Species_Problem": tk.StringVar(value="Ignore"),
                "Image_Problem": tk.StringVar(value="Ignore"),
                "Any_Problem": tk.StringVar(value="Ignore"),
                "Historical_Data": tk.StringVar(value="Ignore"),
                "Has_Images": tk.StringVar(value="Ignore"),
            }
            self.filter_mode = tk.StringVar(value="AND")
            self.filter_entries = {"Room": tk.StringVar(value="")}
            self.filter_dropdowns = {"Status": tk.StringVar(value="")}
            self.filter_location_vars = {}
        def filter_objects(self): pass
        def select_object_id(self, oid): pass
        def update_filter_button_text(self): pass
        def refresh_list(self): pass
        def update_object_count(self): pass

    ui = DummyUI(tk_root)
    FilterDialogController.open_filter_menu(ui)
    assert ui.filter_window is not None
    assert ui.filter_window.winfo_exists()
    FilterDialogController.clear_filter(ui, ui.filter_window, destroy_win=True)
    assert ui.filter_vars["Reviewed"].get() == "Ignore"
