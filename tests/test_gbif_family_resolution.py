import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.gbif import (
    is_undetermined_species,
    _query_single_taxon,
    _evaluate_item_diff,
    batch_gbif_match,
    check_gbif
)


class TestUndeterminedSpeciesDetection:
    """Test recognition of open nomenclature and undetermined species markers."""

    def test_exact_undetermined_tokens(self):
        assert is_undetermined_species("") is True
        assert is_undetermined_species(None) is True
        assert is_undetermined_species("sp.") is True
        assert is_undetermined_species("sp") is True
        assert is_undetermined_species("SP.") is True
        assert is_undetermined_species("spp.") is True
        assert is_undetermined_species("spp") is True
        assert is_undetermined_species("spec.") is True
        assert is_undetermined_species("species") is True
        assert is_undetermined_species("indet.") is True
        assert is_undetermined_species("indet") is True
        assert is_undetermined_species("undet.") is True
        assert is_undetermined_species("unknown") is True
        assert is_undetermined_species("?") is True
        assert is_undetermined_species("-") is True
        assert is_undetermined_species("none") is True
        assert is_undetermined_species("n/a") is True

    def test_morphospecies_patterns(self):
        assert is_undetermined_species("sp. 1") is True
        assert is_undetermined_species("sp. A") is True
        assert is_undetermined_species("sp. nov.") is True
        assert is_undetermined_species("sp. nr.") is True
        assert is_undetermined_species("indet. 2") is True
        assert is_undetermined_species("species 14") is True

    def test_valid_species_not_undetermined(self):
        assert is_undetermined_species("terrestris") is False
        assert is_undetermined_species("pascuorum") is False
        assert is_undetermined_species("mellifera") is False
        assert is_undetermined_species("vulgaris") is False


class TestTaxonQueryingAndFamilyResolution:
    """Test that GBIF queries resolve Family for both binomials and genus-only taxa."""

    @patch("backend.gbif.check_gbif")
    def test_binomial_resolves_family_and_species(self, mock_check):
        mock_check.return_value = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "genus": "Bombus",
            "species": "pascuorum",
            "author": "(Scopoli, 1763)",
            "family": "Apidae",
            "rank": "SPECIES",
            "synonym": False
        }

        res = _query_single_taxon("Bombus", "pascuorum")
        assert res is not None
        assert res["family"] == "Apidae"
        assert res["species"] == "pascuorum"
        assert res["is_undetermined"] is False
        mock_check.assert_called_once_with("Bombus", "pascuorum")

    @patch("backend.gbif.check_gbif")
    def test_undetermined_queries_genus_only_and_preserves_sp(self, mock_check):
        mock_check.return_value = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "genus": "Bombus",
            "species": "",
            "author": "Latreille, 1802",
            "family": "Apidae",
            "rank": "GENUS",
            "synonym": False
        }

        res = _query_single_taxon("Bombus", "sp.")
        assert res is not None
        assert res["family"] == "Apidae"
        assert res["species"] == "sp."  # Preserves raw undetermined string
        assert res["is_undetermined"] is True
        # Verify it passed empty species to check_gbif
        mock_check.assert_called_once_with("Bombus", "")


class TestDiffEvaluation:
    """Test diff generation for missing metadata and undetermined records."""

    def test_missing_family_populated_for_binomial(self):
        item = {
            "oid": "101",
            "genus": "Bombus",
            "species": "terrestris",
            "author": "(Linnaeus, 1758)",
            "family": ""  # Missing family
        }
        gbif_data = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "genus": "Bombus",
            "species": "terrestris",
            "author": "(Linnaeus, 1758)",
            "family": "Apidae",
            "rank": "SPECIES",
            "is_undetermined": False
        }

        diff = _evaluate_item_diff(item, gbif_data)
        assert diff is not None
        assert diff["missing_family"] is True
        assert diff["is_undetermined"] is False
        assert len(diff["changes"]) == 1
        assert diff["changes"][0]["field"] == "Family"
        assert diff["changes"][0]["new"] == "Apidae"

    def test_undetermined_item_never_changes_species(self):
        item = {
            "oid": "102",
            "genus": "Bombus",
            "species": "sp.",
            "author": "",
            "family": ""
        }
        gbif_data = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "genus": "Bombus",
            "species": "sp.",
            "author": "Latreille, 1802",  # Genus author from GBIF
            "family": "Apidae",
            "rank": "GENUS",
            "is_undetermined": True
        }

        diff = _evaluate_item_diff(item, gbif_data)
        assert diff is not None
        assert diff["is_undetermined"] is True
        assert diff["missing_family"] is True
        assert diff["missing_author"] is True
        # Verify Species is NEVER changed, but Family and Genus Author are proposed
        changed_fields = [c["field"] for c in diff["changes"]]
        assert "Species" not in changed_fields
        assert "Family" in changed_fields
        assert "Author" in changed_fields


class TestBatchGBIFMatchScope:
    """Test batch matching with deduplication and exclusion flags."""

    @patch("backend.gbif._query_single_taxon")
    def test_batch_match_deduplicates_undetermined_records(self, mock_query):
        mock_query.return_value = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "genus": "Bombus",
            "species": "sp.",
            "author": "",
            "family": "Apidae",
            "rank": "GENUS",
            "is_undetermined": True
        }

        items = [
            {"oid": "1", "genus": "Bombus", "species": "sp.", "author": "", "family": ""},
            {"oid": "2", "genus": "Bombus", "species": "indet.", "author": "", "family": ""},
            {"oid": "3", "genus": "Bombus", "species": "sp.", "author": "", "family": ""}
        ]

        results = batch_gbif_match(items, exclude_undetermined=False)
        assert len(results) == 3
        # Should have queried unique undetermined taxon only once
        assert mock_query.call_count == 1

    @patch("backend.gbif._query_single_taxon")
    def test_batch_match_excludes_undetermined_when_flagged(self, mock_query):
        mock_query.return_value = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "genus": "Apis",
            "species": "mellifera",
            "author": "Linnaeus, 1758",
            "family": "Apidae",
            "rank": "SPECIES",
            "is_undetermined": False
        }

        items = [
            {"oid": "1", "genus": "Bombus", "species": "sp.", "author": "", "family": ""},
            {"oid": "2", "genus": "Apis", "species": "mellifera", "author": "", "family": ""},
        ]

        results = batch_gbif_match(items, exclude_undetermined=True)
        # Bombus sp. excluded; only Apis mellifera processed
        assert len(results) == 1
        assert results[0]["oid"] == "2"
        assert mock_query.call_count == 1
