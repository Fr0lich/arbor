import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from models import AppState
from backend.gbif import batch_gbif_match
from ui.gbif_review import rollback_gbif_updates


def test_batch_gbif_match_detects_taxonomic_changes():
    items = [
        {
            "oid": "1001",
            "genus": "Pinus",
            "species": "sylvestris",
            "author": "L.",
            "family": "Pinaceae",
            "higher_classification": "Plantae | Tracheophyta"
        },
        {
            "oid": "1002",
            "genus": "Betula",
            "species": "pendula",
            "author": "Roth",
            "family": "Betulaceae",
            "higher_classification": "Plantae | Tracheophyta"
        }
    ]

    mock_gbif_responses = {
        ("Pinus", "sylvestris"): {
            "genus": "Pinus",
            "species": "sylvestris",
            "author": "Linnaeus, 1753",
            "family": "Pinaceae",
            "higherClassification": "Plantae | Tracheophyta | Pinopsida | Pinales",
            "status": "ACCEPTED",
            "matchType": "EXACT",
            "rank": "SPECIES",
            "synonym": False
        },
        ("Betula", "pendula"): {
            "genus": "Betula",
            "species": "pendula",
            "author": "Roth",
            "family": "Betulaceae",
            "higherClassification": "Plantae | Tracheophyta",
            "status": "ACCEPTED",
            "matchType": "EXACT",
            "rank": "SPECIES",
            "synonym": False
        }
    }

    def mock_check(g, s):
        return mock_gbif_responses.get((g, s))

    with patch("backend.gbif.check_gbif", side_effect=mock_check):
        diffs = batch_gbif_match(items)

    assert len(diffs) == 1
    diff = diffs[0]
    assert diff["oid"] == "1001"
    changed_fields = [c["field"] for c in diff["changes"]]
    assert "Author" in changed_fields
    assert "Higher Classification" in changed_fields
    assert "Genus" not in changed_fields


def test_gbif_apply_and_rollback():
    app = AppState()
    app.df_reg = pd.DataFrame([
        {
            "ObjectID": "1001",
            "Genus": "Pinus",
            "Species": "sylvestris",
            "Author": "L.",
            "Family": "Pinaceae"
        }
    ]).set_index("ObjectID")
    app.df_log = pd.DataFrame(columns=["Timestamp", "User", "Action", "ObjectID", "ChangedFields", "ChangedValues"])

    diff_results = [
        {
            "oid": "1001",
            "current": {"Genus": "Pinus", "Species": "sylvestris", "Author": "L.", "Family": "Pinaceae", "Higher Classification": ""},
            "proposed": {"Genus": "Pinus", "Species": "sylvestris", "Author": "Linnaeus", "Family": "Pinaceae", "Higher Classification": ""},
            "changes": [{"field": "Author", "old": "L.", "new": "Linnaeus"}],
            "status": "ACCEPTED",
            "rank": "SPECIES"
        }
    ]

    # Mock dialog application logic
    with app.df_lock:
        app.df_reg.at["1001", "Author"] = "Linnaeus"
        app._log_records = [{
            "Timestamp": "2026-09-03T12:00:00",
            "User": "test_user",
            "Action": "GBIF_UPDATE",
            "ObjectID": "1001",
            "Reviewed": "",
            "ChangedFields": "Author",
            "ChangedValues": 'Author: "L." -> "Linnaeus"',
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": ""
        }]
        app.df_log = pd.DataFrame(app._log_records)
        app.dirty = True

    assert app.df_reg.at["1001", "Author"] == "Linnaeus"

    # Test Rollback
    success, msg = rollback_gbif_updates(app)
    assert success is True
    assert app.df_reg.at["1001", "Author"] == "L."
    assert len(app._log_records) == 2
    assert app._log_records[-1]["Action"] == "GBIF_ROLLBACK"
