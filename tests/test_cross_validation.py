import pytest
import tkinter as tk
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.cross_validation import find_book_matches_for_gbif, check_gbif_corroboration_for_historical
from ui.gbif_review import GBIFReviewDialog


class MockAppState:
    def __init__(self, df_reg=None, historical_dbs=None):
        self.df_reg = df_reg
        self.df_log = pd.DataFrame()
        self.df_obs = pd.DataFrame()
        self.excel_path = "test.xlsx"
        self.output_path = "test.xlsx"
        self._log_records = []
        self.historical_dbs = historical_dbs or []
        self.current_object_id = "1001"
        self.df_lock = MagicMock()
        self.df_lock.__enter__ = MagicMock(return_value=None)
        self.df_lock.__exit__ = MagicMock(return_value=None)


def test_find_book_matches_author_equivalence():
    hist_df = pd.DataFrame([
        {"ObjectID": "1001", "Author": "L.", "Family": "Fagaceae", "Species": "robur"}
    ]).set_index("ObjectID")

    hist_db = {
        "name": "Books: Ledger 1904",
        "reg_by_id": hist_df,
        "dict_cache": {
            "1001": {"Author": ["L."], "Family": ["Fagaceae"], "Species": ["robur"]}
        }
    }

    app_state = MockAppState(historical_dbs=[hist_db])

    # 1. Author "Linnaeus" should match "L." via is_author_equivalent
    matches = find_book_matches_for_gbif(app_state, "1001", "Author", "Linnaeus")
    assert matches == ["Books: Ledger 1904"]

    # 2. Non-matching author should return empty
    matches_no = find_book_matches_for_gbif(app_state, "1001", "Author", "Smith")
    assert matches_no == []

    # 3. Family match (case-insensitive)
    matches_fam = find_book_matches_for_gbif(app_state, "1001", "Family", "fagaceae")
    assert matches_fam == ["Books: Ledger 1904"]

    # 4. Non-matching family
    matches_fam_no = find_book_matches_for_gbif(app_state, "1001", "Family", "Betulaceae")
    assert matches_fam_no == []


def test_check_gbif_corroboration_for_historical():
    df_reg = pd.DataFrame([
        {"ObjectID": "1001", "Genus": "Quercus", "Species": "robur", "Author": "OldAuth", "Family": "OldFam"}
    ]).set_index("ObjectID")

    app_state = MockAppState(df_reg=df_reg)

    mock_gbif = {
        "genus": "Quercus",
        "species": "robur",
        "author": "L.",
        "family": "Fagaceae",
        "status": "ACCEPTED"
    }

    with patch("backend.cross_validation.check_gbif", return_value=mock_gbif):
        # Author "Linnaeus" should match GBIF "L."
        assert check_gbif_corroboration_for_historical(app_state, "1001", "Author", "Linnaeus") is True
        assert check_gbif_corroboration_for_historical(app_state, "1001", "Author", "Smith") is False

        # Family "Fagaceae" matches
        assert check_gbif_corroboration_for_historical(app_state, "1001", "Family", "Fagaceae") is True
        assert check_gbif_corroboration_for_historical(app_state, "1001", "Family", "Pinaceae") is False


def test_gbif_review_dialog_sidebar_reactive_status_and_fullscreen():
    root = tk.Tk()
    root.withdraw()

    hist_df = pd.DataFrame([
        {"ObjectID": "1001", "Author": "L.", "Family": "Fagaceae"}
    ]).set_index("ObjectID")
    hist_db = {
        "name": "Books: Sheet 1",
        "reg_by_id": hist_df,
        "dict_cache": {"1001": {"Author": ["L."]}}
    }

    df_reg = pd.DataFrame([
        {"ObjectID": "1001", "Genus": "Quercus", "Species": "robur", "Author": "", "Family": ""}
    ]).set_index("ObjectID")
    app_state = MockAppState(df_reg=df_reg, historical_dbs=[hist_db])

    diff_results = [
        {
            "oid": "1001",
            "status": "ACCEPTED",
            "match_type": "EXACT",
            "changes": [
                {"field": "Author", "old": "", "new": "Linnaeus"},
                {"field": "Family", "old": "", "new": "Fagaceae"}
            ]
        }
    ]

    dialog = GBIFReviewDialog(root, app_state, diff_results)

    # 1. Check sidebar initial state: ACCEPTED
    assert "1001" in dialog.specimen_dir_widgets
    assert dialog.specimen_dir_widgets["1001"]["tag_lbl"].cget("text") == "ACCEPTED"

    # 2. Uncheck 1 change -> status updates to ACCEPTED (1/2)
    dialog.selection_state[("1001", "Author")] = False
    dialog._update_sidebar_item("1001")
    assert dialog.specimen_dir_widgets["1001"]["tag_lbl"].cget("text") == "ACCEPTED (1/2)"

    # 3. Uncheck all changes -> status updates to SKIPPED
    dialog.selection_state[("1001", "Family")] = False
    dialog._update_sidebar_item("1001")
    assert dialog.specimen_dir_widgets["1001"]["tag_lbl"].cget("text") == "SKIPPED"

    # 4. Deselect all batch -> all marked SKIPPED
    dialog._deselect_all_batch()
    assert dialog.specimen_dir_widgets["1001"]["tag_lbl"].cget("text") == "SKIPPED"

    # 5. Select all batch -> marked ACCEPTED
    dialog._select_all_batch()
    assert dialog.specimen_dir_widgets["1001"]["tag_lbl"].cget("text") == "ACCEPTED"

    # 6. Test fullscreen toggle
    assert dialog._is_fullscreen is False
    dialog._toggle_fullscreen()
    assert dialog._is_fullscreen is True
    dialog._toggle_fullscreen()
    assert dialog._is_fullscreen is False

    # 7. Test Verified in Books filter & smart selection buttons
    dialog.status_var.set("✓ Verified in Books (1)")
    dialog._on_status_filter_changed()
    assert len(dialog._get_filtered_results()) == 1
    assert "Select Filtered" in dialog.sel_all_btn.cget("text")
    assert "Deselect Filtered" in dialog.desel_all_btn.cget("text")

    # 8. Test Deselect Filtered and Select Filtered
    dialog._deselect_filtered_batch()
    assert dialog.selection_state[("1001", "Author")] is False
    assert dialog.selection_state[("1001", "Family")] is False

    dialog._select_filtered_batch()
    assert dialog.selection_state[("1001", "Author")] is True
    assert dialog.selection_state[("1001", "Family")] is True

    # 9. Reset filter to All and check buttons restore to Select All
    dialog._set_category_tab("pending")
    assert "Select All" in dialog.sel_all_btn.cget("text")
    assert "Deselect All" in dialog.desel_all_btn.cget("text")

    # 10. Test Phased Apply: Switch to verified tab and apply
    dialog._set_category_tab("verified")
    assert "APPLY 2 [VERIFIED] UPDATES" in dialog.apply_btn.cget("text")
    dialog._apply_selected()

    # Specimen 1001 should now be recorded in applied_oids
    assert "1001" in dialog.applied_oids
    assert app_state.df_reg.at["1001", "Author"] == "Linnaeus"
    assert app_state.df_reg.at["1001", "Family"] == "Fagaceae"

    # Tab counts: pending is 0, applied is 1
    counts = dialog._get_tab_counts()
    assert counts["pending"] == 0
    assert counts["applied"] == 1

    dialog.destroy()
    root.destroy()


def test_gbif_batch_single_field_instant_apply():
    """Test Tier 1: Per-field instant apply commits only the specified field and updates state in-place."""
    root = tk.Tk()
    root.withdraw()

    df_reg = pd.DataFrame(
        [
            {"ObjectID": "2001", "Genus": "Pinus", "Species": "montana", "Family": "", "Author": "Mill."}
        ]
    ).set_index("ObjectID")

    df_obs = pd.DataFrame(
        [
            {"ObjectID": "2001", "Species_Problem": True, "Family_Problem": True}
        ]
    ).set_index("ObjectID")

    app_state = MockAppState(df_reg=df_reg)
    app_state.df_obs = df_obs
    app_state.config = {
        "ui_sections": {
            "problems": [
                {"name": "Species_Problem", "maps_to": "Species"},
                {"name": "Family_Problem", "maps_to": "Family"},
            ]
        }
    }

    diff_results = [
        {
            "oid": "2001",
            "current": {"Genus": "Pinus", "Species": "montana", "Family": "", "Author": "Mill."},
            "proposed": {"Genus": "Pinus", "Species": "mugo", "Family": "Pinaceae", "Author": "Turra"},
            "changes": [
                {"field": "Species", "old": "montana", "new": "mugo"},
                {"field": "Family", "old": "", "new": "Pinaceae"},
                {"field": "Author", "old": "Mill.", "new": "Turra"},
            ],
            "status": "SYNONYM",
            "match_type": "EXACT"
        }
    ]

    dialog = GBIFReviewDialog(root, app_state, diff_results)

    # Verify initial state: 1 pending item, 0 applied
    assert len(dialog.applied_changes) == 0
    counts = dialog._get_tab_counts()
    assert counts["pending"] == 1
    assert counts["applied"] == 0

    # 1. Apply single field (Species)
    dialog._apply_single_field("2001", "Species", "montana", "mugo")

    # Verify Species is updated in df_reg
    assert app_state.df_reg.at["2001", "Species"] == "mugo"
    # Verify Family and Author remain unchanged
    assert app_state.df_reg.at["2001", "Family"] == ""
    assert app_state.df_reg.at["2001", "Author"] == "Mill."

    # Verify Species_Problem was auto-cleared in df_obs, but Family_Problem remains True
    assert bool(app_state.df_obs.at["2001", "Species_Problem"]) is False
    assert bool(app_state.df_obs.at["2001", "Family_Problem"]) is True

    # Verify applied_changes has exactly ('2001', 'Species')
    assert ("2001", "Species") in dialog.applied_changes
    assert ("2001", "Family") not in dialog.applied_changes

    # Specimen is partially applied: still has 2 unapplied fields so pending is still 1, applied is 1
    counts_after = dialog._get_tab_counts()
    assert counts_after["pending"] == 1
    assert counts_after["applied"] == 1

    # 2. Test title formatting
    title_info = dialog._get_specimen_title_info(diff_results[0])
    assert "SPECIMEN #2001 • Pinus montana  →  Pinus mugo" in title_info["header_title"]
    assert title_info["is_rename"] is True

    # 3. Test card toggle chip: None and Verified
    dialog._select_card_fields("2001", "none")
    assert dialog.selection_state[("2001", "Family")] is False
    assert dialog.selection_state[("2001", "Author")] is False

    dialog._select_card_fields("2001", "all")
    assert dialog.selection_state[("2001", "Family")] is True
    assert dialog.selection_state[("2001", "Author")] is True

    # 4. Apply specimen (applies all remaining selected fields)
    dialog._apply_specimen("2001")
    assert app_state.df_reg.at["2001", "Family"] == "Pinaceae"
    assert app_state.df_reg.at["2001", "Author"] == "Turra"
    assert bool(app_state.df_obs.at["2001", "Family_Problem"]) is False

    # Now all fields are applied: pending is 0, applied is 1
    counts_final = dialog._get_tab_counts()
    assert counts_final["pending"] == 0
    assert counts_final["applied"] == 1

    dialog.destroy()
    root.destroy()



