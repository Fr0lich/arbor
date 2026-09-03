import pytest
import pandas as pd
from models import AppState
from ui.gbif_review import rollback_gbif_updates


def test_sequential_gbif_rollbacks():
    app = AppState()
    app.df_reg = pd.DataFrame([
        {"ObjectID": "101", "Genus": "Pinus", "Species": "sylvestris", "Author": "Linnaeus"},
        {"ObjectID": "102", "Genus": "Betula", "Species": "pendula", "Author": "Roth"}
    ]).set_index("ObjectID")
    
    # 1. Batch 1 update at 10:00:00: Pinus author was changed from L. -> Linnaeus
    # 2. Batch 2 update at 11:00:00: Betula author was changed from Ehrh. -> Roth
    app._log_records = [
        {
            "Timestamp": "2026-09-03T10:00:00",
            "User": "botanist",
            "Action": "GBIF_UPDATE",
            "ObjectID": "101",
            "Reviewed": "",
            "ChangedFields": "Author",
            "ChangedValues": 'Author: "L." -> "Linnaeus"',
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": "",
            "SourceFile": "test.xlsx",
            "OutputFile": "test.xlsx"
        },
        {
            "Timestamp": "2026-09-03T11:00:00",
            "User": "botanist",
            "Action": "GBIF_UPDATE",
            "ObjectID": "102",
            "Reviewed": "",
            "ChangedFields": "Author",
            "ChangedValues": 'Author: "Ehrh." -> "Roth"',
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": "",
            "SourceFile": "test.xlsx",
            "OutputFile": "test.xlsx"
        }
    ]
    app.df_log = pd.DataFrame(app._log_records)

    # First Rollback: Should target Batch 2 (11:00:00)
    success1, msg1 = rollback_gbif_updates(app)
    assert success1 is True
    assert app.df_reg.at["102", "Author"] == "Ehrh."
    assert app.df_reg.at["101", "Author"] == "Linnaeus"
    assert app._log_records[-1]["Action"] == "GBIF_ROLLBACK"
    assert "from GBIF update at 2026-09-03T11:00:00" in app._log_records[-1]["ChangedFields"]

    # Second Rollback: Should skip Batch 2 and target Batch 1 (10:00:00)
    success2, msg2 = rollback_gbif_updates(app)
    assert success2 is True
    assert app.df_reg.at["101", "Author"] == "L."
    assert "from GBIF update at 2026-09-03T10:00:00" in app._log_records[-1]["ChangedFields"]

    # Third Rollback: No more un-reverted batches left
    success3, msg3 = rollback_gbif_updates(app)
    assert success3 is False
    assert "No GBIF updates found" in msg3
