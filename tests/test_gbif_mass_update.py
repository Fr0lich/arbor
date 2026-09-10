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


def test_check_gbif_network_error_returns_dict():
    from backend.gbif import check_gbif
    with patch("requests.get", side_effect=Exception("Connection timed out")):
        res = check_gbif("Quercus", "robur")
        assert isinstance(res, dict)
        assert "error" in res
        assert "Connection timed out" in res["error"]


def test_check_gbif_higher_classification_formatting():
    from backend.gbif import check_gbif
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "scientificName": "Quercus robur L.",
        "canonicalName": "Quercus robur",
        "genus": "Quercus",
        "species": "Quercus robur",
        "kingdom": "Plantae",
        "phylum": "Tracheophyta",
        "class": "",  # Empty
        "order": None,  # None
        "matchType": "EXACT",
        "status": "ACCEPTED",
        "rank": "SPECIES"
    }
    with patch("requests.get", return_value=mock_resp):
        res = check_gbif("Quercus", "robur")
        assert res["higherClassification"] == "Plantae | Tracheophyta"


def test_batch_gbif_match_skip_missing_genus():
    items = [
        {"oid": "1", "genus": "", "species": "robur"},
        {"oid": "2", "genus": "   ", "species": "sylvestris"}
    ]
    with patch("backend.gbif.check_gbif") as mock_check:
        res = batch_gbif_match(items)
        assert len(res) == 0
        mock_check.assert_not_called()


def test_batch_gbif_match_synonym_partial_overwrite():
    items = [{
        "oid": "101",
        "genus": "OldGenus",
        "species": "old_spec",
        "author": "OldAuthor",
        "family": "OldFamily",
        "higher_classification": "OldHigher"
    }]
    gbif_synonym = {
        "genus": "SynGenus",
        "species": "syn_spec",
        "author": "SynAuthor",
        "family": "SynFamily",
        "higherClassification": "SynHigher",
        "status": "SYNONYM",
        "synonym": True,
        "acceptedUsageKey": 99999,
        "matchType": "EXACT",
        "rank": "SPECIES"
    }
    # Accepted name only returns genus/species, empty author/family/higher
    acc_name = {
        "genus": "NewGenus",
        "species": "new_spec",
        "author": "",
        "family": "",
        "higherClassification": ""
    }

    with patch("backend.gbif.check_gbif", return_value=gbif_synonym), \
         patch("backend.gbif.get_accepted_name", return_value=acc_name):
        res = batch_gbif_match(items, max_workers=2)

    assert len(res) == 1
    proposed = res[0]["proposed"]
    assert proposed["Genus"] == "NewGenus"
    assert proposed["Species"] == "new_spec"
    assert proposed["Author"] == "SynAuthor"  # Retained from gbif_synonym because acc_data had empty
    assert proposed["Family"] == "SynFamily"
    assert proposed["Higher Classification"] == "SynHigher"


def test_batch_gbif_match_cancellation():
    import threading
    items = [{"oid": str(i), "genus": "Pinus", "species": f"spec_{i}"} for i in range(20)]
    cancel_event = threading.Event()
    cancel_event.set()

    with patch("backend.gbif.check_gbif") as mock_check:
        res = batch_gbif_match(items, cancel_event=cancel_event, max_workers=2)
        assert len(res) == 0


def test_batch_gbif_match_ignores_equivalent_higher_classification():
    items = [{
        "oid": "201",
        "genus": "Quercus",
        "species": "robur",
        "author": "L.",
        "family": "Fagaceae",
        "higher_classification": "Plantae|Tracheophyta|Magnoliopsida|Fagales"  # no spaces
    }]
    gbif_data = {
        "genus": "Quercus",
        "species": "robur",
        "author": "L.",
        "family": "Fagaceae",
        "higherClassification": "Plantae | Tracheophyta | Magnoliopsida | Fagales",  # spaces around pipes
        "status": "ACCEPTED",
        "synonym": False,
        "matchType": "EXACT",
        "rank": "SPECIES"
    }
    with patch("backend.gbif.check_gbif", return_value=gbif_data):
        res = batch_gbif_match(items)
        assert len(res) == 0  # No changes proposed because they are equivalent!


def test_author_equivalence_and_validation():
    from backend.gbif import is_author_equivalent
    # Identical with punctuation / dot variations
    assert is_author_equivalent("L.", "L") is True
    assert is_author_equivalent("L.", "L.") is True
    assert is_author_equivalent("(L.) Ehrh.", "(L.) Ehrh.") is True
    assert is_author_equivalent("Hook. f.", "Hook.f.") is True
    assert is_author_equivalent("", "") is True

    # Genuine differences
    assert is_author_equivalent("", "L.") is False
    assert is_author_equivalent("Ehrh.", "Roth") is False
    assert is_author_equivalent("L.", "Linnaeus") is False


def test_classification_equivalence_subsets_and_synonyms():
    from backend.gbif import is_classification_equivalent
    gbif_standard = "Plantae | Tracheophyta | Magnoliopsida | Fagales"

    # Subset with at least 3 ranks (e.g. Tracheophyta + Magnoliopsida + Fagales)
    assert is_classification_equivalent("Tracheophyta | Magnoliopsida | Fagales", gbif_standard) is True
    assert is_classification_equivalent("Plantae | Magnoliopsida | Fagales", gbif_standard) is True

    # Superset (with Family)
    assert is_classification_equivalent("Plantae | Tracheophyta | Magnoliopsida | Fagales | Fagaceae", gbif_standard) is True

    # Traditional division synonym
    assert is_classification_equivalent("Plantae | Magnoliophyta | Magnoliopsida | Fagales", gbif_standard) is True
    assert is_classification_equivalent("Plantae | Angiospermae | Magnoliopsida | Fagales", gbif_standard) is True

    # Incomplete high-level only (e.g. only 2 ranks, missing order & class) -> flags for update
    assert is_classification_equivalent("Plantae | Tracheophyta", gbif_standard) is False

    # Conflicting order
    assert is_classification_equivalent("Plantae | Tracheophyta | Magnoliopsida | Rosales", gbif_standard) is False

    # Empty vs filled
    assert is_classification_equivalent("", gbif_standard) is False
    assert is_classification_equivalent(None, gbif_standard) is False



