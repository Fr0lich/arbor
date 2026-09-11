import pytest
import tkinter as tk
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.cross_validation import find_book_matches_for_gbif, check_gbif_corroboration_for_historical
from ui.gbif_review import GBIFReviewDialog


class MockAppState:
    def __init__(self, df_reg=None, historical_dbs=None):
        self.df_reg = df_reg
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
    dialog.status_var.set("All (1)")
    dialog._on_status_filter_changed()
    assert "Select All" in dialog.sel_all_btn.cget("text")
    assert "Deselect All" in dialog.desel_all_btn.cget("text")

    dialog.destroy()
    root.destroy()

