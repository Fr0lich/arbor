import pytest
from datetime import datetime, timedelta
import pandas as pd
from backend.mobile_server import MobileServer
from models import AppState

@pytest.fixture
def mock_app_state():
    app = AppState()
    app.config = {
        "ui_sections": {
            "registration": [{"name": "Genus"}, {"name": "Species"}],
            "location": [{"name": "Cabinet"}],
            "problems": [{"name": "MissingLabel"}]
        }
    }
    app.df_reg = pd.DataFrame({
        "Genus": ["Pinus", "Betula"],
        "Species": ["sylvestris", "pendula"],
        "Cabinet": ["Cab 1", "Cab 2"]
    }, index=pd.Index([1001, 1002], name="ObjectID"))

    app.df_obs = pd.DataFrame({
        "Reviewed": [True, False],
        "Cabinet": ["Cab 1", "Cab 2"]
    }, index=pd.Index([1001, 1002], name="ObjectID"))

    # Pre-populate undo stack with a recent change for 1001
    now = datetime.now()
    app.undo_stacks = {
        "1001": [
            {
                "oid": "1001",
                "timestamp": now.isoformat()
            }
        ]
    }
    return app

def test_offline_mutation_queue_batch_update_success(mock_app_state):
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    now = datetime.now()
    # A valid queued update (newer than any stack changes, or for an object without stack)
    future_time = (now + timedelta(minutes=5)).isoformat()

    payload = {
        "updates": [
            {
                "id": "1002",
                "reviewed": True,
                "timestamp": future_time,
                "observation": {"Cabinet": "Cab 88"}
            }
        ]
    }

    res = client.post('/api/batch_update', headers=headers, json=payload)
    assert res.status_code == 200
    assert res.json["updated_count"] == 1
    assert mock_app_state.df_obs.at[1002, "Cabinet"] == "Cab 88"

def test_offline_mutation_queue_conflict_rejection(mock_app_state):
    server = MobileServer(mock_app_state, port=5098)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    now = datetime.now()
    # An older queued update for 1001 (older than the stack change)
    past_time = (now - timedelta(minutes=5)).isoformat()

    payload = {
        "updates": [
            {
                "id": "1001",
                "reviewed": False,
                "timestamp": past_time,
                "observation": {"Cabinet": "Cab 99"} # Should be rejected
            }
        ]
    }

    res = client.post('/api/batch_update', headers=headers, json=payload)
    assert res.status_code == 200
    assert res.json.get("updated_count") == 0
    # Data should not be changed
    assert mock_app_state.df_obs.at[1001, "Cabinet"] == "Cab 1"
