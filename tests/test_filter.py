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
    unknown_fields = ["Collector"]
    return df_reg, reg_dict, obs_dict, history_set, problem_columns, problem_to_field, unknown_fields

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
            unknown_fields=unk_fields,
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
            unknown_fields=unk_fields,
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
            unknown_fields=unk_fields,
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
            unknown_fields=unk_fields,
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
            unknown_fields=unk_fields,
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
                unknown_fields=unk_fields,
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
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        # 1: Has_Images=True, Reviewed=True -> Match
        # 3: Has_Images=True, Reviewed=True -> Match
        assert res == ["1", "3"]

    def test_or_mode_multi_criteria(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Images_Problem OR Has_History
        groups = {"Problems": ["Images_Problem"], "Status": ["Has_History"]}
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode="OR",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        # History: 1, 4. Images_Problem: 3.
        assert res == ["1", "3", "4"]

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
            unknown_fields=unk_fields,
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
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert res == [1, 3]

    def test_text_and_unknown_filters(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Comment_Not_Empty
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Text": ["Comment_Not_Empty"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert res == ["1", "3"]

        # Unknown field filter (object 2 has Collector='unknown', object 3 has Collector='')
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
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert res_unk == ["2", "3"]

    def test_problem_with_history_filter(self, sample_filter_data):
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
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert res == ["1", "4"]

    def test_problem_with_history_type_coercion(self, sample_filter_data):
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
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert res == ["1", "4"]

    def test_problem_with_history_and_not_reviewed(self, sample_filter_data):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, unk_fields = sample_filter_data
        fm = FilterManager()
        # Object 1: Reviewed=True, History=True
        # Object 4: Reviewed=False, History=True
        groups = {"Status": ["Problem_With_History", "Not_Reviewed"]}
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
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert res == ["4"]
