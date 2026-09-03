import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from models import AppState
from ui.gbif_review import rollback_gbif_updates


@patch("tkinter.messagebox.showinfo")
def test_gbif_rollback_timestamp_space_and_iso_normalization(mock_showinfo):
    app = AppState()
    app.df_reg = pd.DataFrame([
        {"ObjectID": "201", "Genus": "Pinus", "Species": "sylvestris", "Author": "Linnaeus"}
    ]).set_index("ObjectID")

    # Entry has ISO timestamp '2026-09-03T10:30:00'
    # But rollback reference has space '2026-09-03 10:30:00' (from Excel/SQLite)
    app._log_records = [
        {
            "Timestamp": "2026-09-03T10:30:00",
            "User": "botanist",
            "Action": "GBIF_UPDATE",
            "ObjectID": "201",
            "Reviewed": "",
            "ChangedFields": "Author",
            "ChangedValues": 'Author: "L." -> "Linnaeus"',
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": "",
            "SourceFile": "test.xlsx",
            "OutputFile": "test.xlsx"
        }
    ]
    app.df_log = pd.DataFrame(app._log_records)

    mock_ui = MagicMock()
    mock_ui.app = app
    mock_ui._invalidate_row_cache = MagicMock()
    mock_ui.invalidate_search_index = MagicMock()

    # 1. Rollback should succeed and normalize timestamp
    success, msg = rollback_gbif_updates(app, main_window=mock_ui)
    assert success is True
    assert app.df_reg.at["201", "Author"] == "L."
    assert mock_ui._invalidate_row_cache.called
    assert mock_ui.invalidate_search_index.called

    # 2. Simulate a space-formatted timestamp in the rollback log (e.g. SQLite read)
    app._log_records[-1]["ChangedFields"] = "Rolled back 1 fields from GBIF update at 2026-09-03 10:30:00"

    # 3. Second rollback must recognize that batch 2026-09-03T10:30:00 is already rolled back
    success2, msg2 = rollback_gbif_updates(app, main_window=mock_ui)
    assert success2 is False
    assert "No GBIF updates found" in msg2
