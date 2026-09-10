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
            "higher_classification": "3456"  # Dalla Torre number
        },
        {
            "oid": "1002",
            "genus": "Betula",
            "species": "pendula",
            "author": "Roth",
            "family": "Betulaceae",
            "higher_classification": "1234"
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
    assert "Higher Classification" not in changed_fields
    assert "Genus" not in changed_fields


def test_dalla_torre_numbers_not_overwritten():
    items = [{
        "oid": "500",
        "genus": "Pinus",
        "species": "sylvestris",
        "author": "L.",
        "family": "Pinaceae",
        "higher_classification": "3456.0"  # Dalla Torre number
    }]
    gbif_data = {
        "genus": "Pinus",
        "species": "sylvestris",
        "author": "L.",
        "family": "Pinaceae",
        "higherClassification": "Plantae | Tracheophyta | Pinopsida | Pinales",
        "status": "ACCEPTED",
        "synonym": False,
        "matchType": "EXACT",
        "rank": "SPECIES"
    }
    with patch("backend.gbif.check_gbif", return_value=gbif_data):
        diffs = batch_gbif_match(items)
        assert len(diffs) == 0  # No changes proposed since Genus, Species, Author, Family all match


def test_gbif_apply_and_rollback():
    app = AppState()
    app.df_reg = pd.DataFrame([
        {
            "ObjectID": "1001",
            "Genus": "Pinus",
            "Species": "sylvestris",
            "Author": "L.",
            "Family": "Pinaceae",
            "Higher Classification": "3456"
        }
    ]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([
        {
            "ObjectID": "1001",
            "Genus_Problem": False,
            "Author_Problem": True,
            "Collector_Problem": True  # Unrelated problem
        }
    ]).set_index("ObjectID")
    app.df_log = pd.DataFrame(columns=["Timestamp", "User", "Action", "ObjectID", "ChangedFields", "ChangedValues", "ProblemsChanged", "ProblemsChangedValues"])

    # Mock GBIF dialog application
    with app.df_lock:
        app.df_reg.at["1001", "Author"] = "Linnaeus"
        app.df_obs.at["1001", "Author_Problem"] = False
        app._log_records = [{
            "Timestamp": "2026-09-03T12:00:00",
            "User": "test_user",
            "Action": "GBIF_UPDATE",
            "ObjectID": "1001",
            "Reviewed": "",
            "ChangedFields": "Author",
            "ChangedValues": 'Author: "L." -> "Linnaeus"',
            "ProblemsChanged": "Author_Problem",
            "ProblemsChangedValues": 'Author_Problem: "True" -> "False"',
            "LocationChanged": "",
            "LocationChangedValues": ""
        }]
        app.df_log = pd.DataFrame(app._log_records)
        app.dirty = True

    assert app.df_reg.at["1001", "Author"] == "Linnaeus"
    assert app.df_reg.at["1001", "Higher Classification"] == "3456"
    assert bool(app.df_obs.at["1001", "Author_Problem"]) is False
    assert bool(app.df_obs.at["1001", "Collector_Problem"]) is True

    # Test Rollback
    success, msg = rollback_gbif_updates(app)
    assert success is True
    assert app.df_reg.at["1001", "Author"] == "L."
    assert app.df_reg.at["1001", "Higher Classification"] == "3456"
    assert bool(app.df_obs.at["1001", "Author_Problem"]) is True
    assert bool(app.df_obs.at["1001", "Collector_Problem"]) is True
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
        "family": "OldFamily"
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
    assert "Higher Classification" not in proposed


def test_batch_gbif_match_cancellation():
    import threading
    items = [{"oid": str(i), "genus": "Pinus", "species": f"spec_{i}"} for i in range(20)]
    cancel_event = threading.Event()
    cancel_event.set()

    with patch("backend.gbif.check_gbif") as mock_check:
        res = batch_gbif_match(items, cancel_event=cancel_event, max_workers=2)
        assert len(res) == 0


def test_batch_gbif_match_taxon_deduplication():
    # 100 items with only 2 unique taxa
    items = []
    for i in range(50):
        items.append({"oid": f"p_{i}", "genus": "Pinus", "species": "sylvestris", "author": "L.", "family": "Pinaceae"})
    for i in range(50):
        items.append({"oid": f"b_{i}", "genus": "Betula", "species": "pendula", "author": "Roth", "family": "Betulaceae"})

    mock_resp = {
        ("Pinus", "sylvestris"): {"genus": "Pinus", "species": "sylvestris", "author": "Linnaeus", "family": "Pinaceae", "status": "ACCEPTED", "matchType": "EXACT", "rank": "SPECIES"},
        ("Betula", "pendula"): {"genus": "Betula", "species": "pendula", "author": "Roth", "family": "Betulaceae", "status": "ACCEPTED", "matchType": "EXACT", "rank": "SPECIES"}
    }

    with patch("backend.gbif.check_gbif", side_effect=lambda g, s: mock_resp.get((g, s))) as mock_check:
        diffs = batch_gbif_match(items, max_workers=2)
        # Should only call check_gbif 2 times (once per unique taxon) instead of 100 times!
        assert mock_check.call_count == 2
        # Diff for all 50 Pinus specimens (author changed)
        assert len(diffs) == 50


def test_batch_apply_clears_mapped_problems_and_records_audit_log():
    import tkinter as tk
    from ui.gbif_review import GBIFReviewDialog
    app = AppState()
    app.config = {
        "ui_sections": {
            "problems": [
                {"name": "Genus_Problem", "maps_to": "Genus"},
                {"name": "Species_Problem", "maps_to": "Species"},
                {"name": "Location_Problem", "maps_to": "Location"}
            ]
        }
    }
    app.df_reg = pd.DataFrame([
        {"ObjectID": "101", "Genus": "Pinu", "Species": "sylvestri", "Author": "L.", "Family": "Pinaceae"}
    ]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([
        {"ObjectID": "101", "Genus_Problem": True, "Species_Problem": True, "Location_Problem": True}
    ]).set_index("ObjectID")
    app.df_log = pd.DataFrame(columns=["Timestamp", "User", "Action", "ObjectID", "ChangedFields", "ChangedValues", "ProblemsChanged", "ProblemsChangedValues"])

    diff_results = [{
        "oid": "101",
        "current": {"Genus": "Pinu", "Species": "sylvestri", "Author": "L.", "Family": "Pinaceae"},
        "proposed": {"Genus": "Pinus", "Species": "sylvestris", "Author": "L.", "Family": "Pinaceae"},
        "changes": [
            {"field": "Genus", "old": "Pinu", "new": "Pinus"},
            {"field": "Species", "old": "sylvestri", "new": "sylvestris"}
        ],
        "status": "ACCEPTED",
        "rank": "SPECIES"
    }]

    root = tk.Tk()
    root.withdraw()
    try:
        dialog = GBIFReviewDialog(root, app, diff_results)
        # Apply selected
        with patch("tkinter.messagebox.showinfo"):
            dialog._apply_selected()

        # Verify registration DataFrame updated
        assert app.df_reg.at["101", "Genus"] == "Pinus"
        assert app.df_reg.at["101", "Species"] == "sylvestris"

        # Verify problem flags mapped to Genus and Species are cleared
        assert bool(app.df_obs.at["101", "Genus_Problem"]) is False
        assert bool(app.df_obs.at["101", "Species_Problem"]) is False
        # Unrelated problem remains intact
        assert bool(app.df_obs.at["101", "Location_Problem"]) is True

        # Verify audit log contains Action GBIF_UPDATE and problem diffs
        assert len(app._log_records) == 1
        log_rec = app._log_records[0]
        assert log_rec["Action"] == "GBIF_UPDATE"
        assert "Genus" in log_rec["ChangedFields"]
        assert "Species" in log_rec["ChangedFields"]
        assert "Genus_Problem" in log_rec["ProblemsChanged"]
        assert "Species_Problem" in log_rec["ProblemsChanged"]
        assert 'Genus_Problem: "True" -> "False"' in log_rec["ProblemsChangedValues"]
    finally:
        root.destroy()


def test_gbif_batch_config_dialog_scopes():
    import tkinter as tk
    from ui.gbif_batch_config import GBIFBatchConfigDialog
    from unittest.mock import MagicMock

    root = tk.Tk()
    root.withdraw()
    try:
        main_app = MagicMock()
        main_app.root = root
        main_app.app.df_reg = pd.DataFrame([
            {"ObjectID": "1", "Genus": "Pinus", "Species": "sylvestris", "Author": "L.", "Family": "Pinaceae"},
            {"ObjectID": "2", "Genus": "Betula", "Species": "pendula", "Author": "Roth", "Family": "Betulaceae"},
            {"ObjectID": "3", "Genus": "Quercus", "Species": "robur", "Author": "L.", "Family": "Fagaceae"}
        ]).set_index("ObjectID")
        main_app.app.active_object_ids = ["1", "2"]
        main_app.object_list.get_selected_ids.return_value = ["1"]

        config_dlg = GBIFBatchConfigDialog(root, main_app)
        assert config_dlg.all_count == 3
        assert config_dlg.filtered_count == 2
        assert config_dlg.selected_count == 1
        assert config_dlg.scope_var.get() == "selected"
    finally:
        root.destroy()


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


def test_gbif_toolbar_button_and_dropdown():
    import tkinter as tk
    from ui.navigation_bar import NavigationBar
    from unittest.mock import MagicMock, patch

    root = tk.Tk()
    root.withdraw()
    try:
        mock_app = MagicMock()
        mock_app.root = root
        mock_app.toolbar_buttons = {}
        mock_app.toolbar_vars = {}
        mock_app.config = {"ui_sections": {"problems": []}}

        nav_bar = tk.Frame(root)
        NavigationBar.build_nav_ui(mock_app, nav_bar)

        assert "🌿 GBIF ▾" in mock_app.toolbar_buttons
        btn = mock_app.toolbar_buttons["🌿 GBIF ▾"]
        assert btn is not None

        # Test show_gbif_dropdown method
        from ui.main_window import ObjectProgramUI
        with patch("tkinter.Menu") as mock_menu_cls:
            mock_menu_instance = MagicMock()
            mock_menu_cls.return_value = mock_menu_instance
            ui_instance = MagicMock()
            ui_instance.root = root
            ObjectProgramUI.show_gbif_dropdown(ui_instance)

            # Ensure batch update and rollback were added as commands
            added_labels = [call.kwargs.get("label") for call in mock_menu_instance.add_command.call_args_list]
            assert any("Batch Update Taxonomy" in str(l) for l in added_labels)
            assert any("Revert Latest GBIF" in str(l) for l in added_labels)
    finally:
        root.destroy()


def test_gbif_batch_config_progress_and_percent():
    import tkinter as tk
    from ui.gbif_batch_config import GBIFBatchConfigDialog
    from backend.task_queue import app_worker
    from unittest.mock import MagicMock, patch

    root = tk.Tk()
    root.withdraw()
    app_worker.start(root)
    try:
        main_app = MagicMock()
        main_app.root = root
        main_app.app.df_reg = pd.DataFrame([
            {"ObjectID": "1", "Genus": "Pinus", "Species": "sylvestris", "Author": "L.", "Family": "Pinaceae"},
            {"ObjectID": "2", "Genus": "Betula", "Species": "pendula", "Author": "Roth", "Family": "Betulaceae"}
        ]).set_index("ObjectID")
        main_app.app.active_object_ids = ["1", "2"]
        main_app.object_list.get_selected_ids.return_value = []

        config_dlg = GBIFBatchConfigDialog(root, main_app)

        # Progress bar and percentage elements exist
        assert hasattr(config_dlg, "progress_bar")
        assert hasattr(config_dlg, "pct_var")
        assert hasattr(config_dlg, "status_var")
        assert hasattr(config_dlg, "detail_var")

        # Mock batch_gbif_match with progress callback execution
        def mock_batch_match(items, progress_callback=None, cancel_event=None, max_workers=None):
            if progress_callback:
                progress_callback(1, 2, "Pinus sylvestris")
                progress_callback(2, 2, "Betula pendula")
            return []

        with patch("backend.gbif.batch_gbif_match", side_effect=mock_batch_match), \
             patch.object(config_dlg, "_on_analysis_complete") as mock_complete:
            config_dlg._start_analysis()
            config_dlg._worker_thread.join(timeout=2.0)

            # Process task queue tasks on the main thread
            app_worker._poll()
            root.update()

            assert config_dlg.progress_var.get() == 100.0
            assert config_dlg.pct_var.get() == "100%"
            assert "Betula pendula" in config_dlg.detail_var.get()
            mock_complete.assert_called_once()
    finally:
        app_worker.stop()
        root.destroy()
