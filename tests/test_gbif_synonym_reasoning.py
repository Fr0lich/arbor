import pytest
from unittest.mock import patch, MagicMock
from backend.gbif import (
    _evaluate_item_diff,
    _query_single_taxon,
    batch_gbif_match
)


class TestGBIFSynonymReasoning:
    """Test explicit reasoning and categorization for Genus/Species updates."""

    def test_synonym_genus_transfer_generates_synonym_reason_and_explanation(self):
        item = {
            "oid": "1",
            "genus": "Apis",
            "species": "terrestris",
            "author": "Linnaeus, 1758",
            "family": "Apidae"
        }
        gbif_data = {
            "matchType": "EXACT",
            "status": "SYNONYM",
            "is_synonym": True,
            "genus": "Bombus",
            "species": "terrestris",
            "author": "(Linnaeus, 1758)",
            "family": "Apidae",
            "rank": "SPECIES",
            "is_undetermined": False,
            "original_scientific_name": "Apis terrestris Linnaeus, 1758",
            "accepted_scientific_name": "Bombus terrestris (Linnaeus, 1758)"
        }

        diff = _evaluate_item_diff(item, gbif_data)
        assert diff is not None
        assert diff["is_synonym"] is True
        assert diff["status"] == "SYNONYM"

        # Check Genus change reason
        genus_chg = next((c for c in diff["changes"] if c["field"] == "Genus"), None)
        assert genus_chg is not None
        assert genus_chg["reason_code"] == "SYNONYM_GENUS"
        assert "Synonym" in genus_chg["reason_label"]
        assert "is cataloged as a synonym" in genus_chg["explanation"]

    def test_spelling_correction_generates_spelling_reason(self):
        item = {
            "oid": "2",
            "genus": "Bumbus",
            "species": "pascuorum",
            "author": "(Scopoli, 1763)",
            "family": "Apidae"
        }
        gbif_data = {
            "matchType": "FUZZY",
            "status": "ACCEPTED",
            "is_synonym": False,
            "genus": "Bombus",
            "species": "pascuorum",
            "author": "(Scopoli, 1763)",
            "family": "Apidae",
            "rank": "SPECIES",
            "is_undetermined": False
        }

        diff = _evaluate_item_diff(item, gbif_data)
        assert diff is not None
        assert diff["is_synonym"] is False

        genus_chg = next((c for c in diff["changes"] if c["field"] == "Genus"), None)
        assert genus_chg is not None
        assert genus_chg["reason_code"] == "SPELLING"
        assert "Spelling" in genus_chg["reason_label"]
        assert "Corrected genus spelling" in genus_chg["explanation"]

    def test_missing_family_generates_missing_reason(self):
        item = {
            "oid": "3",
            "genus": "Bombus",
            "species": "sp.",
            "author": "",
            "family": ""
        }
        gbif_data = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "is_synonym": False,
            "genus": "Bombus",
            "species": "sp.",
            "author": "Latreille, 1802",
            "family": "Apidae",
            "rank": "GENUS",
            "is_undetermined": True
        }

        diff = _evaluate_item_diff(item, gbif_data)
        assert diff is not None
        fam_chg = next((c for c in diff["changes"] if c["field"] == "Family"), None)
        assert fam_chg is not None
        assert fam_chg["reason_code"] == "MISSING_FAMILY"
        assert "Missing Family" in fam_chg["reason_label"]
