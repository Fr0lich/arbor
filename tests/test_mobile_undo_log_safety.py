import pytest
import pandas as pd
from datetime import datetime
from models import AppState
from backend.mobile_server import MobileServer, _execute_record_update
import config


def test_mobile_undo_protects_prior_session_and_disk_logs():
    app = AppState()
    app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
    app.df_reg = pd.DataFrame([{"ObjectID": "1001", "Genus": "Acer", "Species": "rubrum"}]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([{"ObjectID": "1001", "Reviewed": False, "Location": "Room 101"}]).set_index("ObjectID")
    app.df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath"]).set_index("ObjectID")
    
    # Pre-populate historical log records from previous sessions
    app._log_records = [
        {
            "Timestamp": "2026-09-01T09:00:00",
            "Action": "EDIT",
            "Reviewed": "No",
            "ObjectID": "1001",
            "ChangedFields": "Species",
            "ChangedValues": 'Species: "saccharum" -> "rubrum"',
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": "",
            "User": "prior_desktop_user",
            "SourceFile": "db.xlsx",
            "OutputFile": "db.xlsx"
        },
        {
            "Timestamp": "2026-09-02T14:00:00",
            "Action": "MOBILE_EDIT",
            "Reviewed": "No",
            "ObjectID": "1001",
            "ChangedFields": "Location",
            "ChangedValues": 'Location: "Room 100" -> "Room 101"',
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "Location",
            "LocationChangedValues": "Room 101",
            "User": "Mobile-Companion",
            "SourceFile": "db.xlsx",
            "OutputFile": "db.xlsx",
            "_session_id": "old_session_123"
        }
    ]
    app.df_log = pd.DataFrame(app._log_records)

    server = MobileServer(app, port=5120)
    client = server.flask_app.test_client()

    # Authenticate mobile client
    with client.session_transaction() as sess:
        sess['authenticated'] = True

    # 1. Perform mobile edit in current session
    resp = client.post('/api/batch_update', json={
        "updates": [{
            "id": "1001",
            "registration": {"Species": "platanoides"},
            "observation": {},
            "reviewed": True
        }]
    })
    assert resp.status_code == 200
    assert len(app._log_records) == 3
    assert app._log_records[-1]["Action"] == "MOBILE_EDIT"
    assert app._log_records[-1]["_session_id"] == server.session_id

    # 2. Perform Undo via mobile API
    undo_resp = client.post('/api/undo', json={"oid": "1001"})
    assert undo_resp.status_code == 200

    # 3. Assert current session log was popped, but the 2 prior session records remain completely intact
    assert len(app._log_records) == 2
    assert app._log_records[0]["User"] == "prior_desktop_user"
    assert app._log_records[1]["_session_id"] == "old_session_123"
    assert app._log_records[1]["ChangedValues"] == 'Location: "Room 100" -> "Room 101"'

    # 4. Perform a second Undo when there are no more current session edits for this oid
    undo_resp2 = client.post('/api/undo', json={"oid": "1001"})
    # Even if undo stack is exhausted or has past snapshots, prior session logs must NOT be popped!
    assert len(app._log_records) == 2


def test_mobile_zero_mutation_guard():
    app = AppState()
    app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
    app.df_reg = pd.DataFrame([{"ObjectID": "2001", "Genus": "Betula", "Species": "pendula"}]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([{"ObjectID": "2001", "Reviewed": True}]).set_index("ObjectID")
    app._log_records = []
    app.df_log = pd.DataFrame()
    app.dirty = False

    with app.df_lock:
        summary, err = _execute_record_update(
            app_state=app,
            oid="2001",
            reg_updates={"Genus": "Betula", "Species": "pendula"},
            obs_updates={"Reviewed": True},
            reviewed=True
        )

    assert err is None
    assert len(app._log_records) == 0
    assert app.df_log.empty
