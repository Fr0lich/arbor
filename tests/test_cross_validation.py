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


def test_gbif_batch_in_place_apply_and_undo():
    """Test in-place UI updating without canvas destroying, and undo roundtrip for single field & whole specimen."""
    root = tk.Tk()
    root.withdraw()

    df_reg = pd.DataFrame(
        [
            {"ObjectID": "3001", "Genus": "Quercus", "Species": "rubra_old", "Family": "Fagaceae", "Author": "L_old"}
        ]
    ).set_index("ObjectID")

    df_obs = pd.DataFrame(
        [
            {"ObjectID": "3001", "Species_Problem": True, "Author_Problem": True}
        ]
    ).set_index("ObjectID")

    app_state = MockAppState(df_reg=df_reg)
    app_state.df_obs = df_obs
    app_state.config = {
        "ui_sections": {
            "problems": [
                {"name": "Species_Problem", "maps_to": "Species"},
                {"name": "Author_Problem", "maps_to": "Author"},
            ]
        }
    }

    diff_results = [
        {
            "oid": "3001",
            "current": {"Genus": "Quercus", "Species": "rubra_old", "Family": "Fagaceae", "Author": "L_old"},
            "proposed": {"Genus": "Quercus", "Species": "rubra", "Family": "Fagaceae", "Author": "L."},
            "changes": [
                {"field": "Species", "old": "rubra_old", "new": "rubra"},
                {"field": "Author", "old": "L_old", "new": "L."},
            ],
            "status": "ACCEPTED",
            "match_type": "EXACT"
        }
    ]

    dialog = GBIFReviewDialog(root, app_state, diff_results)

    # Check widgets are registered
    assert ("3001", "Species") in dialog.field_row_widgets
    assert ("3001", "Author") in dialog.field_row_widgets
    assert "3001" in dialog.card_header_widgets

    sp_widget = dialog.field_row_widgets[("3001", "Species")]
    sp_chk = sp_widget["chk"]
    assert sp_chk.cget("state") == "normal"

    # 1. Apply single field (Species)
    dialog._apply_single_field("3001", "Species", "rubra_old", "rubra")

    # Verify db and obs
    assert app_state.df_reg.at["3001", "Species"] == "rubra"
    assert bool(app_state.df_obs.at["3001", "Species_Problem"]) is False
    assert ("3001", "Species") in dialog.applied_changes

    # Verify field row widget updated in-place (no new widget instance created, checkbox disabled)
    assert sp_chk.cget("state") == "disabled"
    # Check that Undo button is present in btn_box
    btn_box = sp_widget["btn_box"]
    btn_texts = [w.cget("text") for w in btn_box.winfo_children() if isinstance(w, tk.Button) or isinstance(w, tk.Label)]
    assert any("APPLIED" in t for t in btn_texts)
    assert any("Undo" in t for t in btn_texts)

    # 2. Undo single field (Species)
    dialog._undo_single_field("3001", "Species", "rubra_old", "rubra")

    # Verify db and obs reverted
    assert app_state.df_reg.at["3001", "Species"] == "rubra_old"
    assert bool(app_state.df_obs.at["3001", "Species_Problem"]) is True
    assert ("3001", "Species") not in dialog.applied_changes
    assert sp_chk.cget("state") == "normal"
    btn_texts_after_undo = [w.cget("text") for w in btn_box.winfo_children() if isinstance(w, tk.Button) or isinstance(w, tk.Label)]
    assert any("Apply Field" in t for t in btn_texts_after_undo)
    assert not any("APPLIED" in t for t in btn_texts_after_undo)

    # 3. Apply entire specimen
    dialog._apply_specimen("3001")
    assert app_state.df_reg.at["3001", "Species"] == "rubra"
    assert app_state.df_reg.at["3001", "Author"] == "L."
    assert bool(app_state.df_obs.at["3001", "Species_Problem"]) is False
    assert bool(app_state.df_obs.at["3001", "Author_Problem"]) is False
    assert ("3001", "Species") in dialog.applied_changes
    assert ("3001", "Author") in dialog.applied_changes

    # 4. Undo entire specimen
    dialog._undo_specimen("3001")
    assert app_state.df_reg.at["3001", "Species"] == "rubra_old"
    assert app_state.df_reg.at["3001", "Author"] == "L_old"
    assert bool(app_state.df_obs.at["3001", "Species_Problem"]) is True
    assert bool(app_state.df_obs.at["3001", "Author_Problem"]) is True
    assert ("3001", "Species") not in dialog.applied_changes
    assert ("3001", "Author") not in dialog.applied_changes

    dialog.destroy()
    root.destroy()


def test_gbif_batch_sidebar_mousewheel_scrolling():
    """Test that the 'Page Specimens' left sidebar and cards area handle mousewheel scrolling properly."""
    root = tk.Tk()
    root.withdraw()

    # Create 30 specimens
    records = [{"ObjectID": str(1000 + i), "Genus": "Pinus", "Species": f"species_{i}", "Family": "Pinaceae", "Author": "L."} for i in range(30)]
    df_reg = pd.DataFrame(records).set_index("ObjectID")

    app_state = MockAppState(df_reg=df_reg)
    diff_results = [
        {
            "oid": str(1000 + i),
            "current": {"Genus": "Pinus", "Species": f"species_{i}", "Family": "Pinaceae", "Author": "L."},
            "proposed": {"Genus": "Pinus", "Species": f"species_{i}_corr", "Family": "Pinaceae", "Author": "L."},
            "changes": [{"field": "Species", "old": f"species_{i}", "new": f"species_{i}_corr"}],
            "status": "ACCEPTED",
            "match_type": "EXACT"
        }
        for i in range(30)
    ]

    dialog = GBIFReviewDialog(root, app_state, diff_results)

    # Check 25 page specimens are rendered in sidebar and main card canvas
    assert len(dialog.specimen_frames) == 25

    # Verify scrollregion is initialized
    bbox = dialog.dir_canvas.bbox("all")
    assert bbox is not None
    assert bbox[3] > 0  # height > 0

    class MockEvent:
        def __init__(self, delta=0, num=None):
            self.delta = delta
            self.num = num

    # 1. Test direct scroll on dir_canvas
    dialog.dir_canvas.yview_moveto(0.0)
    dialog._on_dir_mousewheel(MockEvent(delta=-120))
    # yview should have moved down (or attempted to scroll)
    pos_after_down = dialog.dir_canvas.yview()

    dialog._on_dir_mousewheel(MockEvent(delta=120))
    pos_after_up = dialog.dir_canvas.yview()

    # 2. Test routed mousewheel with active scroll target
    dialog._set_active_scroll_target("dir")
    dialog._on_routed_mousewheel(MockEvent(delta=-120))
    dialog._set_active_scroll_target("main")
    dialog._on_routed_mousewheel(MockEvent(delta=-120))

    # 3. Test Linux scroll button events (4 and 5)
    dialog._on_dir_mousewheel(MockEvent(num=5))
    dialog._on_dir_mousewheel(MockEvent(num=4))

    # 4. Clean dialog destruction and unbinding
    dialog.destroy()
    root.destroy()


def test_gbif_batch_floating_toast_notifications():
    """Test that toast notifications use floating overlay geometry (place) with zero window layout displacement."""
    root = tk.Tk()
    root.withdraw()

    df_reg = pd.DataFrame(
        [{"ObjectID": "5001", "Genus": "Quercus", "Species": "alba", "Family": "Fagaceae", "Author": "L."}]
    ).set_index("ObjectID")

    app_state = MockAppState(df_reg=df_reg)
    diff_results = [
        {
            "oid": "5001",
            "current": {"Genus": "Quercus", "Species": "alba", "Family": "Fagaceae", "Author": "L."},
            "proposed": {"Genus": "Quercus", "Species": "alba", "Family": "Fagaceae", "Author": "L."},
            "changes": [{"field": "Species", "old": "alba", "new": "alba L."}],
            "status": "ACCEPTED",
            "match_type": "EXACT"
        }
    ]

    dialog = GBIFReviewDialog(root, app_state, diff_results)

    # Toast frame should not be placed initially
    assert not dialog.toast_frame.place_info()

    # 1. Show success toast (Apply action)
    dialog._show_toast("✓ Applied Species for Specimen #5001", level="success")
    place_info = dialog.toast_frame.place_info()
    assert place_info != {}
    assert dialog.toast_icon.cget("text") == "✓"
    assert "✓ Applied" in dialog.toast_label.cget("text")
    assert dialog.toast_frame.cget("bg") == dialog.colors["success_bg"]

    # 2. Show undo toast (Undo action)
    dialog._show_toast("⎌ Undid Species for Specimen #5001", level="undo")
    assert dialog.toast_icon.cget("text") == "⎌"
    assert "⎌ Undid" in dialog.toast_label.cget("text")
    assert dialog.toast_frame.cget("bg") == dialog.colors["warning_bg"]

    # 3. Dismiss toast via _hide_toast
    dialog._hide_toast()
    assert not dialog.toast_frame.place_info()

    dialog.destroy()
    root.destroy()






