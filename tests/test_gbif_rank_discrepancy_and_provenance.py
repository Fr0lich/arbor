import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from backend.gbif import (
    check_gbif,
    _evaluate_item_diff,
    is_likely_family_name
)
from backend.cross_validation import (
    collect_field_provenance,
    validate_candidate_with_gbif,
    get_validated_provenance_candidates,
    scan_taxonomic_rank_inversions,
    restore_provenance_candidate
)
from models import AppState


class TestGBIFRankDiscrepancyAndPrevention:
    """Test prevention of family-as-species pollution and proper rank classification."""

    def test_is_likely_family_name(self):
        assert is_likely_family_name("Pinaceae") is True
        assert is_likely_family_name("pinaceae") is True
        assert is_likely_family_name("Asteraceae") is True
        assert is_likely_family_name("Compositae") is True
        assert is_likely_family_name("Fabaceae") is True
        assert is_likely_family_name("excelsa") is False
        assert is_likely_family_name("sylvestris") is False
        assert is_likely_family_name("") is False

    def test_gbif_homonym_disambiguation_with_genus(self):
        # When genus is passed, Pinus excelsa must resolve to species wallichiana, NOT family Pinaceae
        res = check_gbif("Pinus", "excelsa")
        assert res is not None
        assert res.get("rank") == "SPECIES"
        assert res.get("genus") == "Pinus"
        assert res.get("species") == "wallichiana"
        assert res.get("status") == "SYNONYM"
        assert res.get("family") == "Pinaceae"

    def test_higher_rank_never_pollutes_species(self):
        # Mock a GBIF response that returns FAMILY
        mock_resp = {
            "usageKey": 3925,
            "scientificName": "Pinaceae",
            "canonicalName": "Pinaceae",
            "rank": "FAMILY",
            "status": "ACCEPTED",
            "confidence": 97,
            "matchType": "HIGHERRANK",
            "family": "Pinaceae"
        }
        with patch("backend.gbif._session.get") as mock_get:
            mock_res = MagicMock()
            mock_res.json.return_value = mock_resp
            mock_res.raise_for_status = MagicMock()
            mock_get.return_value = mock_res

            # Clear cache for isolated test
            check_gbif.cache_clear()
            res = check_gbif("UnknownGenus", "fakeSpecies")
            assert res is not None
            assert res.get("rank") == "FAMILY"
            # Species must be empty, NEVER Pinaceae!
            assert res.get("species") == ""
            assert res.get("family") == "Pinaceae"

    def test_low_similarity_is_never_labeled_as_spelling(self):
        item = {
            "oid": "67",
            "genus": "Pinus",
            "species": "excelsa",
            "family": "Pinaceae"
        }
        gbif_data = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "is_synonym": False,
            "genus": "Pinus",
            "species": "wallichiana",
            "rank": "SPECIES",
            "is_undetermined": False
        }
        diff = _evaluate_item_diff(item, gbif_data)
        assert diff is not None
        sp_chg = next(c for c in diff["changes"] if c["field"] == "Species")
        # excelsa -> wallichiana is NOT a spelling typo (similarity 22%)
        assert sp_chg["reason_code"] != "SPELLING"
        assert sp_chg["reason_code"] == "RECLASSIFICATION"

    def test_rank_discrepancy_flags_and_disables_auto_resolve(self):
        # Corrupted item where current species is a family name
        item = {
            "oid": "67",
            "genus": "Pinus",
            "species": "Pinaceae",
            "family": "Pinaceae"
        }
        gbif_data = {
            "matchType": "EXACT",
            "status": "SYNONYM",
            "is_synonym": True,
            "genus": "Pinus",
            "species": "wallichiana",
            "rank": "SPECIES",
            "is_undetermined": False
        }
        diff = _evaluate_item_diff(item, gbif_data)
        assert diff is not None
        assert diff["has_rank_discrepancy"] is True
        assert "Species → Family" in diff["rank_discrepancy"]
        assert diff["auto_resolve_eligible"] is False

        sp_chg = next(c for c in diff["changes"] if c["field"] == "Species")
        assert sp_chg["has_rank_discrepancy"] is True
        assert sp_chg["auto_resolve_eligible"] is False
        assert sp_chg["reason_code"] == "RANK_DISCREPANCY"


class TestProvenanceAndValidation:
    """Test multi-source collection from books (preserving sheet names) and audit log with GBIF checks."""

    def test_collect_provenance_multi_sheets_and_audit_log(self):
        app = AppState()
        # Mock 2 different book sheets with different names
        df_sheet1 = pd.DataFrame([{"ObjectID": "67", "Species": "excelsa"}])
        df_sheet2 = pd.DataFrame([{"ObjectID": "67", "Species": "wallichiana"}])

        app.historical_dbs = [
            {"name": "Books: 1912 Ledger", "df_reg": df_sheet1},
            {"name": "Books: 1955 Catalog", "df_reg": df_sheet2}
        ]

        # Mock an audit log entry for this OID
        app._log_records = [
            {
                "Timestamp": "2026-09-03T10:00:00",
                "Action": "GBIF_UPDATE",
                "ObjectID": "67",
                "ChangedValues": 'Species: "excelsa" -> "Pinaceae"'
            }
        ]
        app.df_log = pd.DataFrame(app._log_records)

        candidates = collect_field_provenance(app, "67", "Species")
        assert len(candidates) == 3

        # Check that sheet names are accurately recorded
        source_names = [c["source_name"] for c in candidates]
        assert "Books: 1912 Ledger" in source_names
        assert "Books: 1955 Catalog" in source_names
        assert any("Audit Log" in s for s in source_names)

        values = [c["value"] for c in candidates]
        assert "excelsa" in values
        assert "wallichiana" in values

    def test_preflight_gbif_validation_on_candidates(self):
        # excelsa -> Valid historical synonym
        val_excelsa = validate_candidate_with_gbif("Pinus", "excelsa")
        assert val_excelsa["status"] == "SYNONYM"
        assert "Valid Synonym" in val_excelsa["badge_label"]
        assert "wallichiana" in val_excelsa["accepted_name"].lower()

        # wallichiana -> Accepted species
        val_wall = validate_candidate_with_gbif("Pinus", "wallichiana")
        assert val_wall["status"] == "ACCEPTED"
        assert "Current Accepted Species" in val_wall["badge_label"]


class TestScanAndRestoreTaxonomicInversions:
    """Test dataset-wide scan and safe audit-logged restoration."""

    def test_scan_and_restore_workflow(self):
        app = AppState()
        app.df_reg = pd.DataFrame([
            {"ObjectID": "101", "Genus": "Pinus", "Species": "Pinaceae", "Family": "Pinaceae"},
            {"ObjectID": "102", "Genus": "Betula", "Species": "pendula", "Family": "Betulaceae"}
        ]).set_index("ObjectID")

        # Mock historical books containing the genuine species for 101
        app.historical_dbs = [
            {
                "name": "Books: Primary Ledger",
                "df_reg": pd.DataFrame([{"ObjectID": "101", "Species": "sylvestris"}])
            }
        ]

        # 1. Scan detects the rank inversion on 101, but not on 102
        anomalies = scan_taxonomic_rank_inversions(app)
        assert len(anomalies) == 1
        assert anomalies[0]["oid"] == "101"
        assert anomalies[0]["current_species"] == "Pinaceae"
        assert len(anomalies[0]["candidates"]) == 1
        assert anomalies[0]["candidates"][0]["value"] == "sylvestris"

        # 2. Restore 101 to sylvestris
        ok = restore_provenance_candidate(app, "101", "Species", "sylvestris", "Books: Primary Ledger")
        assert ok is True
        assert app.df_reg.at["101", "Species"] == "sylvestris"

        # Verify audit log recorded the restoration
        assert len(app._log_records) == 1
        log_e = app._log_records[-1]
        assert log_e["Action"] == "TAXONOMIC_INVERSION_RESTORE"
        assert log_e["ObjectID"] == "101"
        assert 'Species: "Pinaceae" -> "sylvestris"' in log_e["ChangedValues"]

        # 3. Subsequent scan finds zero anomalies
        clean_scan = scan_taxonomic_rank_inversions(app)
        assert len(clean_scan) == 0


class TestAutoResolveSafeguardsInQt:
    """Test that Qt bulk selection actions strictly exclude items with rank discrepancies."""

    def test_select_all_and_select_confident_exclude_rank_discrepancy(self):
        import sys
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)

        from ui_qt.gbif_review import QtGbifReviewDialog

        app = AppState()
        dialog = QtGbifReviewDialog(app_state=app, auto_start=False)

        dialog.results = [
            {
                "oid": "1",
                "orig_name": "Betula pendula",
                "matched_name": "Betula pendula Roth",
                "status": "ACCEPTED",
                "confidence": 99,
                "has_rank_discrepancy": False,
                "checked": False
            },
            {
                "oid": "2",
                "orig_name": "Pinus Pinaceae",
                "matched_name": "Pinaceae",
                "status": "ACCEPTED",
                "confidence": 98,
                "has_rank_discrepancy": True,
                "rank_discrepancy": "⚠️ Species → Family",
                "checked": False
            }
        ]
        dialog.visible_indices = [0, 1]

        # 1. Test select_all
        dialog.select_all()
        assert dialog.results[0]["checked"] is True
        assert dialog.results[1]["checked"] is False  # MUST REMAIN FALSE

        # 2. Test deselect_all
        dialog.deselect_all()
        assert dialog.results[0]["checked"] is False
        assert dialog.results[1]["checked"] is False

        # 3. Test select_confident
        dialog.select_confident()
        assert dialog.results[0]["checked"] is True
        assert dialog.results[1]["checked"] is False  # MUST REMAIN FALSE
