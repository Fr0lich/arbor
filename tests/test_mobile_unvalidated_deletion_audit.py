import pytest
import pandas as pd
from models import AppState
from backend.mobile_server import MobileServer
import config


def test_mobile_unvalidated_deletion_triggers_audit_and_guard():
    app = AppState()
    app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
    app.df_reg = pd.DataFrame([{"ObjectID": "4001", "Genus": "Fraxinus"}]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([{"ObjectID": "4001", "Reviewed": True}]).set_index("ObjectID")
    app.df_unvalidated = pd.DataFrame([
        {"ObjectID": "4001", "Field_Name": "Taxonomy", "Unvalidated_Comment": "Needs herbarium review"}
    ])
    app.df_photo = pd.DataFrame()
    app.df_log = pd.DataFrame()
    app._log_records = []

    server = MobileServer(app, port=5150)
    client = server.flask_app.test_client()

    with client.session_transaction() as sess:
        sess['authenticated'] = True

    # Mobile update clears all unvalidated comments for 4001
    resp = client.post('/api/update', json={
        "id": "4001",
        "unvalidated_sources": [],
        "registration": {},
        "observation": {}
    })
    assert resp.status_code == 200

    # 1. df_unvalidated must no longer have the deleted comment
    remaining = app.df_unvalidated[app.df_unvalidated["ObjectID"] == "4001"]
    assert len(remaining) == 0

    # 2. Deletion must NOT be silenced by zero-mutation guard; audit log must capture it
    assert len(app._log_records) == 1
    log_entry = app._log_records[0]
    assert "Unvalidated_Taxonomy" in log_entry["ChangedFields"]
    assert 'Unvalidated_Taxonomy: "Needs herbarium review" -> ""' in log_entry["ChangedValues"]
