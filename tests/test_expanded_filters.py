import pytest
import pandas as pd
from backend.filter import FilterManager
from repository import REVIEWED_COLUMN


def test_filter_has_unvalidated_source():
    fm = FilterManager()
    df_reg = pd.DataFrame([
        {"ObjectID": "101", "Genus": "Pinus", "Species": "sylvestris"},
        {"ObjectID": "102", "Genus": "Betula", "Species": "pendula"},
        {"ObjectID": "103", "Genus": "Quercus", "Species": "robur"}
    ]).set_index("ObjectID")

    df_obs = pd.DataFrame([
        {"ObjectID": "101", REVIEWED_COLUMN: False},
        {"ObjectID": "102", REVIEWED_COLUMN: False},
        {"ObjectID": "103", REVIEWED_COLUMN: False}
    ]).set_index("ObjectID")

    df_unvalidated = pd.DataFrame([
        {"ObjectID": "102", "Field_Name": "Species", "Unvalidated_Comment": "Unclear handwriting"}
    ])

    reg_dict = df_reg.to_dict(orient="index")
    obs_dict = df_obs.to_dict(orient="index")

    groups = {"Status": ["Has_Unvalidated"]}
    matched = fm.apply_filter(
        df_reg=df_reg,
        reg_dict=reg_dict,
        obs_dict=obs_dict,
        history_set=set(),
        groups=groups,
        global_mode="AND",
        not_reviewed_only=False,
        location_filters=("", "", ""),
        problem_columns=[],
        problem_to_field={},
        unknown_fields=[],
        image_mode="online",
        df_unvalidated=df_unvalidated
    )

    assert matched == ["102"]


def test_filter_reviewed_with_problem():
    fm = FilterManager()
    df_reg = pd.DataFrame([
        {"ObjectID": "101", "Genus": "Pinus", "Species": "sylvestris"},
        {"ObjectID": "102", "Genus": "Betula", "Species": "pendula"},
        {"ObjectID": "103", "Genus": "Quercus", "Species": "robur"}
    ]).set_index("ObjectID")

    df_obs = pd.DataFrame([
        {"ObjectID": "101", REVIEWED_COLUMN: True, "Missing_Label": True},
        {"ObjectID": "102", REVIEWED_COLUMN: True, "Missing_Label": False},
        {"ObjectID": "103", REVIEWED_COLUMN: False, "Missing_Label": True}
    ]).set_index("ObjectID")

    reg_dict = df_reg.to_dict(orient="index")
    obs_dict = df_obs.to_dict(orient="index")

    groups = {"Status": ["Reviewed_With_Problem"]}
    matched = fm.apply_filter(
        df_reg=df_reg,
        reg_dict=reg_dict,
        obs_dict=obs_dict,
        history_set=set(),
        groups=groups,
        global_mode="AND",
        not_reviewed_only=False,
        location_filters=("", "", ""),
        problem_columns=["Missing_Label"],
        problem_to_field={},
        unknown_fields=[],
        image_mode="online"
    )

    assert matched == ["101"]


def test_filter_search_old_taxonomy():
    fm = FilterManager()
    df_reg = pd.DataFrame([
        {"ObjectID": "101", "Genus": "Pinus", "Species": "sylvestris"},
        {"ObjectID": "102", "Genus": "Betula", "Species": "pendula"}
    ]).set_index("ObjectID")

    df_obs = pd.DataFrame([
        {"ObjectID": "101", REVIEWED_COLUMN: True},
        {"ObjectID": "102", REVIEWED_COLUMN: False}
    ]).set_index("ObjectID")

    df_log = pd.DataFrame([
        {
            "Timestamp": "2026-09-03T10:00:00",
            "Action": "GBIF_UPDATE",
            "ObjectID": "101",
            "ChangedFields": "Species",
            "ChangedValues": 'Species: "montana" -> "sylvestris"'
        }
    ])

    reg_dict = df_reg.to_dict(orient="index")
    obs_dict = df_obs.to_dict(orient="index")

    groups = {"Status": ["Search_Old_Taxonomy"]}
    matched = fm.apply_filter(
        df_reg=df_reg,
        reg_dict=reg_dict,
        obs_dict=obs_dict,
        history_set=set(),
        groups=groups,
        global_mode="AND",
        not_reviewed_only=False,
        location_filters=("", "", ""),
        problem_columns=[],
        problem_to_field={},
        unknown_fields=[],
        image_mode="online",
        df_log=df_log,
        old_taxonomy_query="montana"
    )

    assert matched == ["101"]
