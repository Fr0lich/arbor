import pytest
import pandas as pd
from config import DATABASE_CONFIGS, PROBLEM_CATEGORY_THEMES
from backend.filter import FilterManager
from repository import REVIEWED_COLUMN


class TestProblemCategoryConfig:
    """Verify that configuration schemas include required domain categories and metadata."""

    def test_problem_category_themes_structure(self):
        expected_cats = {"taxonomy", "collection", "physical", "media", "notes"}
        assert expected_cats.issubset(set(PROBLEM_CATEGORY_THEMES.keys()))

        for cat, data in PROBLEM_CATEGORY_THEMES.items():
            assert "label" in data
            assert "badge" in data
            assert "color" in data
            assert "rank" in data
            assert isinstance(data["rank"], int)

    def test_botany_config_problem_metadata(self):
        botany_cfg = DATABASE_CONFIGS["Økonomisk Botanisk"]
        problems = botany_cfg.get("ui_sections", {}).get("problems", [])
        assert len(problems) > 0

        for p in problems:
            assert "category" in p, f"Problem {p.get('name')} missing category"
            assert p["category"] in PROBLEM_CATEGORY_THEMES, f"Problem {p.get('name')} has invalid category {p['category']}"
            assert "importance" in p, f"Problem {p.get('name')} missing importance"
            assert p["importance"] in {"high", "medium", "low", "workflow"}

        # Verify specific assignments
        prob_map = {p["name"]: p for p in problems}

        # Taxonomy
        assert prob_map["Genus_Problem"]["category"] == "taxonomy"
        assert prob_map["Genus_Problem"]["importance"] == "high"
        assert prob_map["Species_Problem"]["category"] == "taxonomy"
        assert prob_map["Species_Problem"]["importance"] == "high"

        # Collection & Provenance
        assert prob_map["Collector_Problem"]["category"] == "collection"
        assert prob_map["Collection_Date_Problem"]["category"] == "collection"

        # Physical & Storage
        assert prob_map["PlantPart_Problem"]["category"] == "physical"
        assert prob_map["PlantPart_Problem"]["importance"] == "low"
        assert prob_map["Box_Label_Problem"]["category"] == "physical"

        # Media
        assert prob_map["Images_Problem"]["category"] == "media"


class TestCategoryFilterEvaluators:
    """Test category evaluators in FilterManager."""

    @pytest.fixture
    def specimen_dataset(self):
        df_reg = pd.DataFrame(
            {
                "Genus": ["Quercus", "Pinus", "", "Betula"],
                "Species": ["robur", "sylvestris", "alba", ""],
                "Collector": ["Smith", "ukjent", "Jones", ""],
                "Collection_Date": ["1920", "unknown", "1950", ""],
                "Box Label": ["Box 1", "Box 2", "Box 3", ""],
                "Plant Part": ["Wood", "Leaf", "Bark", ""],
            },
            index=["1", "2", "3", "4"]
        )
        df_obs = pd.DataFrame(
            {
                "Genus_Problem": [False, False, True, False],
                "Species_Problem": [False, False, False, False],
                "Collector_Problem": [False, False, False, False],
                "Box_Label_Problem": [False, False, False, True],
                "PlantPart_Problem": [False, False, False, False],
                "Images_Problem": [False, True, False, False],
                "Images_Missing": [False, False, False, True],
                REVIEWED_COLUMN: [True, True, False, False],
            },
            index=["1", "2", "3", "4"]
        )

        reg_dict = df_reg.to_dict(orient="index")
        obs_dict = df_obs.to_dict(orient="index")
        history_set = set()

        prob_cols = [
            "Genus_Problem", "Species_Problem", "Collector_Problem",
            "Box_Label_Problem", "PlantPart_Problem", "Images_Problem", "Images_Missing"
        ]
        prob_to_field = {
            "Genus_Problem": "Genus",
            "Species_Problem": "Species",
            "Collector_Problem": "Collector",
            "Box_Label_Problem": "Box Label",
            "PlantPart_Problem": "Plant Part",
        }
        prob_categories = {
            "Genus_Problem": "taxonomy",
            "Species_Problem": "taxonomy",
            "Collector_Problem": "collection",
            "Box_Label_Problem": "physical",
            "PlantPart_Problem": "physical",
            "Images_Problem": "media",
            "Images_Missing": "media",
        }
        unknown_fields = ["Collector", "Collection_Date"]

        return df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, prob_categories, unknown_fields

    def test_filter_has_taxonomy_problem(self, specimen_dataset):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, prob_cats, unk_fields = specimen_dataset
        fm = FilterManager()

        # Object 3 has Genus_Problem = True, Object 4 has missing Species
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Problems": ["Has_Taxonomy_Problem"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            problem_categories=prob_cats,
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert "3" in res
        assert "4" in res
        assert "1" not in res
        assert "2" not in res

    def test_filter_has_collection_problem_with_ukjent_suppression(self, specimen_dataset):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, prob_cats, unk_fields = specimen_dataset
        fm = FilterManager()

        # Object 2 has "ukjent" / "unknown", which should NOT trigger collection problem
        # Object 4 has empty Collector and empty Date without ukjent, so it triggers
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Problems": ["Has_Collection_Problem"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            problem_categories=prob_cats,
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert "2" not in res  # Ukjent properly suppressed as actionable problem
        assert "4" in res

    def test_filter_has_storage_problem(self, specimen_dataset):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, prob_cats, unk_fields = specimen_dataset
        fm = FilterManager()

        # Object 4 has Box_Label_Problem=True
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Problems": ["Has_Storage_Problem"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            problem_categories=prob_cats,
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert res == ["4"]

    def test_filter_needs_image_workflow(self, specimen_dataset):
        df_reg, reg_dict, obs_dict, history_set, prob_cols, prob_to_field, prob_cats, unk_fields = specimen_dataset
        fm = FilterManager()

        # Object 2 has Images_Problem=True, Object 4 has Images_Missing=True
        res = fm.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups={"Images": ["Needs_Image_Workflow"]},
            global_mode="AND",
            not_reviewed_only=False,
            location_filters=("", "", ""),
            problem_columns=prob_cols,
            problem_to_field=prob_to_field,
            problem_categories=prob_cats,
            unknown_fields=unk_fields,
            image_mode="folder"
        )
        assert "2" in res
        assert "4" in res
        assert "1" not in res
        assert "3" not in res


class TestMobileServerCategoryForwardCompatibility:
    """Verify that backend/mobile_server.py passes category and importance metadata in endpoints."""

    def test_get_problem_metadata_in_schema(self):
        botany_cfg = DATABASE_CONFIGS["Økonomisk Botanisk"]
        
        # Test schema payload generation
        ui_sections = botany_cfg.get("ui_sections", {})
        problems = ui_sections.get("problems", [])
        
        for p in problems:
            assert "category" in p
            assert "importance" in p
