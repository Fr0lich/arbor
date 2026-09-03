import pytest
import pandas as pd
from models import AppState
from backend.mobile_server import MobileServer
import config


def test_mobile_undo_pops_not_reviewed_action():
    app = AppState()
    app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
    app.df_reg = pd.DataFrame([{"ObjectID": "3001", "Genus": "Ulmus"}]).set_index("ObjectID")
    # Initially reviewed = True
    app.df_obs = pd.DataFrame([{"ObjectID": "3001", "Reviewed": True}]).set_index("ObjectID")
    app.df_photo = pd.DataFrame()
    app.df_log = pd.DataFrame()
    app._log_records = []

    server = MobileServer(app, port=5140)
    client = server.flask_app.test_client()

    with client.session_transaction() as sess:
        sess['authenticated'] = True

    # 1. Un-review via mobile API
    resp = client.post('/api/update', json={
        "id": "3001",
        "reviewed": False,
        "registration": {},
        "observation": {}
    })
    assert resp.status_code == 200
    assert not bool(app.df_obs.at["3001", "Reviewed"])
    assert len(app._log_records) == 1
    assert app._log_records[0]["Action"] == "NOT_REVIEWED"

    # 2. Undo the un-review action via mobile API
    undo_resp = client.post('/api/undo', json={"oid": "3001"})
    assert undo_resp.status_code == 200
    assert bool(app.df_obs.at["3001", "Reviewed"]) is True

    # 3. The NOT_REVIEWED log record must be cleanly popped from both _log_records and df_log
    assert len(app._log_records) == 0
    assert len(app.df_log) == 0
