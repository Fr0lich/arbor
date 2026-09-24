import pytest
import pandas as pd
import json
import time
from unittest.mock import patch
from models import AppState
from backend.mobile_server import MobileServer
import config


@pytest.fixture
def mock_app_state(tmp_path):
    app = AppState()
    app.config_name = "Botanical Herbarium"
    app.config = {
        "sheets": {"reg": "Registration", "obs": "Observation", "photo": "Photo", "log": "Log"},
        "ui_sections": {
            "registration": [
                {"name": "Genus"}, {"name": "Species"}, {"name": "Family"}, {"name": "Author"},
                {"name": "UID"}, {"name": "ProblemDescription"}
            ],
            "problems": [{"name": "MissingLabel", "label": "Missing Label", "maps_to": "ProblemDescription"}],
            "reg_groups": [{"name": "Taxonomy", "fields": ["Genus", "Species", "Family", "Author"]}],
            "location": [{"name": "Building"}, {"name": "Room"}, {"name": "Cabinet"}, {"name": "Shelf"}]
        },
        "image_url_pattern": "https://www.unimus.no/photos/image/jpeg/O-V-OE-{id}.jpg"
    }

    reg_data = {
        "ObjectID": ["1024", "1025", "1026"],
        "Genus": ["Pinus", "Betula", "Quercus"],
        "Species": ["sylvestris", "pendula", "robur"],
        "Family": ["Pinaceae", "Betulaceae", "Fagaceae"],
        "Author": ["L.", "Roth", "L."],
        "UID": ["u1024", "u1025", "u1026"],
        "ProblemDescription": ["", "", ""]
    }
    df_reg = pd.DataFrame(reg_data).set_index("ObjectID")

    obs_data = {
        "ObjectID": ["1024", "1025", "1026"],
        "Room": ["Room 304", "Room 304", "Room 305"],
        "Cabinet": ["C-12", "C-12", "C-15"],
        "Shelf": ["Shelf 3", "Shelf 4", "Shelf 1"],
        "Notes": ["Initial inspection note", "", ""],
        "Reviewed": [False, True, False],
        "ReviewedAt": ["", "2026-08-20T10:00:00", ""],
        "MissingLabel": [False, False, True]
    }
    df_obs = pd.DataFrame(obs_data).set_index("ObjectID")
    df_photo = pd.DataFrame({"ObjectID": ["1024", "1025", "1026"], "Images": ["1024.jpg", "", ""]}).set_index("ObjectID")
    df_log = pd.DataFrame()

    app.df_reg = df_reg
    app.df_obs = df_obs
    app.df_photo = df_photo
    app.df_log = df_log
    app.excel_path = str(tmp_path / "test_db.xlsx")
    app.output_path = app.excel_path
    app._log_records = []
    app.dirty = False

    return app


def test_cloudflare_ip_proxy_and_rate_limiting(mock_app_state):
    """Test CF-Connecting-IP / X-Forwarded-For headers and per-IP rate limiting lockout."""
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()

    ip_a = "198.51.100.1"
    ip_b = "198.51.100.2"

    # 1. Test IP extraction via CF-Connecting-IP
    with server.flask_app.test_request_context('/', headers={'CF-Connecting-IP': ip_a}):
        assert server._get_client_ip() == ip_a

    # Test IP extraction via X-Forwarded-For (with proxies in chain)
    with server.flask_app.test_request_context('/', headers={'X-Forwarded-For': f"{ip_b}, 10.0.0.1, 127.0.0.1"}):
        assert server._get_client_ip() == ip_b

    # 2. Trigger 5 failed attempts from IP A
    for _ in range(5):
        res = client.post('/api/auth', json={"pin": "WRONG_PIN"}, headers={'CF-Connecting-IP': ip_a})
        assert res.status_code == 401

    # IP A should now be rate-limited (429)
    res_a = client.post('/api/auth', json={"pin": server.pin}, headers={'CF-Connecting-IP': ip_a})
    assert res_a.status_code == 429
    assert "Too many failed attempts" in res_a.json.get("error", "")

    # IP B (different worker) should NOT be rate limited and should authenticate cleanly
    res_b = client.post('/api/auth', json={"pin": server.pin}, headers={'CF-Connecting-IP': ip_b})
    assert res_b.status_code == 200
    assert "token" in res_b.json


def test_separate_client_sessions_and_worker_tracking(mock_app_state):
    """Test distinct worker session creation and audit log session_id tracking."""
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()

    # Authenticate Worker 1
    auth1 = client.post('/api/auth', json={"pin": server.pin}, headers={'CF-Connecting-IP': '10.0.1.1'})
    assert auth1.status_code == 200
    token1 = auth1.json["token"]
    session1 = server._get_session_by_token(token1)
    assert session1 is not None
    sid1 = session1["session_id"]

    # Authenticate Worker 2
    auth2 = client.post('/api/auth', json={"pin": server.pin}, headers={'CF-Connecting-IP': '10.0.1.2'})
    assert auth2.status_code == 200
    token2 = auth2.json["token"]
    session2 = server._get_session_by_token(token2)
    assert session2 is not None
    sid2 = session2["session_id"]

    # Must be separate sessions
    assert token1 != token2
    assert sid1 != sid2

    # Worker 1 updates Object 1024
    res_w1 = client.post('/api/update',
                         json={"id": "1024", "registration": {"Genus": "Pinus", "Species": "mugo"}},
                         headers={"X-Session-Token": token1})
    assert res_w1.status_code == 200

    # Worker 2 updates Object 1025
    res_w2 = client.post('/api/update',
                         json={"id": "1025", "registration": {"Genus": "Betula", "Species": "nana"}},
                         headers={"X-Session-Token": token2})
    assert res_w2.status_code == 200

    # Verify audit log records contain correct _session_id attribution
    log_1024 = [r for r in mock_app_state._log_records if r.get("ObjectID") == "1024"]
    assert len(log_1024) > 0
    assert log_1024[-1]["User"] == "Mobile-Companion"
    assert log_1024[-1].get("_session_id") == sid1

    log_1025 = [r for r in mock_app_state._log_records if r.get("ObjectID") == "1025"]
    assert len(log_1025) > 0
    assert log_1025[-1]["User"] == "Mobile-Companion"
    assert log_1025[-1].get("_session_id") == sid2


def test_session_isolated_undo(mock_app_state):
    """Test that undo operations are scoped to the requesting worker's session."""
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()

    auth1 = client.post('/api/auth', json={"pin": server.pin})
    token1 = auth1.json["token"]
    sid1 = server._get_session_by_token(token1)["session_id"]

    auth2 = client.post('/api/auth', json={"pin": server.pin})
    token2 = auth2.json["token"]
    sid2 = server._get_session_by_token(token2)["session_id"]

    # Worker 1 modifies Genus of 1024 to 'Pinus-W1'
    client.post('/api/update',
                json={"id": "1024", "registration": {"Genus": "Pinus-W1", "Species": "sylvestris"}},
                headers={"X-Session-Token": token1})

    # Worker 2 modifies Species of 1024 to 'sylvestris-W2'
    client.post('/api/update',
                json={"id": "1024", "registration": {"Genus": "Pinus-W1", "Species": "sylvestris-W2"}},
                headers={"X-Session-Token": token2})

    assert mock_app_state.df_reg.loc["1024", "Genus"] == "Pinus-W1"
    assert mock_app_state.df_reg.loc["1024", "Species"] == "sylvestris-W2"

    # Worker 2 triggers undo
    undo_res2 = client.post('/api/undo', json={"id": "1024"}, headers={"X-Session-Token": token2})
    assert undo_res2.status_code == 200
    assert undo_res2.json["success"] is True

    # After Worker 2 undid their edit:
    # Species should revert back to 'sylvestris', but Worker 1's Genus edit ('Pinus-W1') should remain!
    assert mock_app_state.df_reg.loc["1024", "Species"] == "sylvestris"
    assert mock_app_state.df_reg.loc["1024", "Genus"] == "Pinus-W1"

    # Worker 1 triggers undo
    undo_res1 = client.post('/api/undo', json={"id": "1024"}, headers={"X-Session-Token": token1})
    assert undo_res1.status_code == 200
    assert undo_res1.json["success"] is True

    # Now Genus should also be restored to initial 'Pinus'
    assert mock_app_state.df_reg.loc["1024", "Genus"] == "Pinus"


def test_pin_requirement_toggle(mock_app_state):
    """Test that require_mobile_pin=False bypasses PIN check and auto-provisions sessions."""
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()

    # 1. When PIN required (default):
    with patch("config.load_prefs", return_value={"require_mobile_pin": True}):
        server.update_pin_requirement(True)
        assert server.is_pin_required() is True
        res_fail = client.post('/api/auth', json={"pin": "WRONG_PIN"})
        assert res_fail.status_code == 401

    # 2. When PIN requirement is disabled:
    with patch("config.load_prefs", return_value={"require_mobile_pin": False}):
        server.update_pin_requirement(False)
        assert server.is_pin_required() is False

        # POST /api/auth without valid PIN succeeds
        res_auth = client.post('/api/auth', json={"pin": ""})
        assert res_auth.status_code == 200
        assert "token" in res_auth.json
        assert res_auth.json.get("success") is True

        # GET /login redirects directly to / with a session cookie and token
        res_login = client.get('/login')
        assert res_login.status_code == 302
        assert "/?token=" in res_login.headers.get("Location", "")
        cookie_header = res_login.headers.get("Set-Cookie", "")
        assert "session=" in cookie_header


def test_independent_worker_views_and_sse_routing(mock_app_state):
    """Test targeted vs broadcast SSE message routing."""
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()

    auth1 = client.post('/api/auth', json={"pin": server.pin})
    token1 = auth1.json["token"]
    sid1 = server._get_session_by_token(token1)["session_id"]

    auth2 = client.post('/api/auth', json={"pin": server.pin})
    token2 = auth2.json["token"]
    sid2 = server._get_session_by_token(token2)["session_id"]

    # Register two simulated SSE client entries
    import queue
    q1 = queue.Queue(maxsize=10)
    q2 = queue.Queue(maxsize=10)
    server.clients = [
        {"queue": q1, "session_id": sid1, "token": token1},
        {"queue": q2, "session_id": sid2, "token": token2}
    ]

    # Targeted event for Worker 1 only
    server.broadcast_event("focus_specimen", {"id": "1024"}, target_session_id=sid1)
    server._flush_events()
    assert not q1.empty()
    assert q2.empty()
    msg1 = q1.get_nowait()
    assert msg1.get("type") == "batch"
    assert any(ev.get("type") == "focus_specimen" and ev.get("data", {}).get("id") == "1024" for ev in msg1.get("events", []))

    # Global data event for all workers
    server.broadcast_event("data_updated", {"id": "1024"})
    server._flush_events()
    assert not q1.empty()
    assert not q2.empty()
    msg1_global = q1.get_nowait()
    msg2_global = q2.get_nowait()
    assert any(ev.get("type") == "data_updated" for ev in msg1_global.get("events", []))
    assert any(ev.get("type") == "data_updated" for ev in msg2_global.get("events", []))


def test_presence_tracking_and_heartbeat(mock_app_state):
    """Test presence tracking, viewer counting, and object detail warnings."""
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()

    auth1 = client.post('/api/auth', json={"pin": server.pin})
    token1 = auth1.json["token"]
    sid1 = server._get_session_by_token(token1)["session_id"]

    auth2 = client.post('/api/auth', json={"pin": server.pin})
    token2 = auth2.json["token"]
    sid2 = server._get_session_by_token(token2)["session_id"]

    # 1. Worker 1 opens specimen 1024
    p1 = client.post('/api/presence', json={"oid": "1024"}, headers={"X-Session-Token": token1})
    assert p1.status_code == 200
    assert p1.json["other_viewers_count"] == 0

    # GET /api/object/1024 for Worker 1 shows 0 other viewers
    d1 = client.get('/api/object/1024', headers={"X-Session-Token": token1})
    assert d1.json["other_viewers_count"] == 0

    # 2. Worker 2 also opens specimen 1024
    p2 = client.post('/api/presence', json={"oid": "1024"}, headers={"X-Session-Token": token2})
    assert p2.status_code == 200
    assert p2.json["other_viewers_count"] == 1

    # Now GET /api/object/1024 shows 1 other viewer for both workers
    d1_again = client.get('/api/object/1024', headers={"X-Session-Token": token1})
    assert d1_again.json["other_viewers_count"] == 1

    d2 = client.get('/api/object/1024', headers={"X-Session-Token": token2})
    assert d2.json["other_viewers_count"] == 1

    # 3. Worker 1 leaves detail view (oid: None or empty)
    p1_leave = client.post('/api/presence', json={"oid": ""}, headers={"X-Session-Token": token1})
    assert p1_leave.status_code == 200

    # Worker 2 now sees 0 other viewers on 1024
    d2_after = client.get('/api/object/1024', headers={"X-Session-Token": token2})
    assert d2_after.json["other_viewers_count"] == 0
