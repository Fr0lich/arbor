import pytest
from models import AppState
from backend.mobile_server import MobileServer
import time

@pytest.fixture
def mock_app_state(tmp_path):
    app = AppState()
    app.config_name = "Test"
    app.config = {}
    return app

def test_mobile_rate_limiting_with_user_agents(mock_app_state):
    # Enable PIN
    import config
    original_load = config.load_prefs
    def mock_load():
        return {"require_mobile_pin": True}
    config.load_prefs = mock_load

    server = MobileServer(mock_app_state, port=5101)
    client = server.flask_app.test_client()

    # Send 10 failed login requests with the same IP but different User-Agent
    for i in range(10):
        # We need to set consecutive failures. The rate limit allows up to 10 consecutive failures.
        res = client.post('/login', data={"pin": "wrong"}, environ_base={'REMOTE_ADDR': '127.0.0.1'}, headers={'User-Agent': f'Client-A'})

    # The 11th request for Client-A should be rate limited (429)
    res_a = client.post('/login', data={"pin": "wrong"}, environ_base={'REMOTE_ADDR': '127.0.0.1'}, headers={'User-Agent': f'Client-A'})
    assert res_a.status_code == 429

    # A request for Client-B should NOT be rate limited, because of unique UA
    res_b = client.post('/login', data={"pin": "wrong"}, environ_base={'REMOTE_ADDR': '127.0.0.1'}, headers={'User-Agent': f'Client-B'})
    assert res_b.status_code != 429

    config.load_prefs = original_load


def test_mobile_session_token_upgrades(mock_app_state):
    # Enable PIN so that the auto-login bypass does not immediately create a session and return 200
    import config
    original_load = config.load_prefs
    def mock_load():
        return {"require_mobile_pin": True}
    config.load_prefs = mock_load

    server = MobileServer(mock_app_state, port=5102)
    client = server.flask_app.test_client()

    master_token = server.session_token

    # Use master token via query parameter
    res1 = client.get(f'/?token={master_token}')
    assert res1.status_code == 302 # Redirected

    # The redirect URL should have a NEW token, not the master token
    assert f"token={master_token}" not in res1.headers['Location']
    assert "token=" in res1.headers['Location']

    # Extract new token
    new_token = res1.headers['Location'].split("token=")[1]

    # Requesting with the new token should return 200 (authenticated)
    res2 = client.get(f'/?token={new_token}')
    assert res2.status_code == 200

    # V2 route using master token
    res_v2 = client.get(f'/v2?token={master_token}')
    assert res_v2.status_code == 302
    assert f"token={master_token}" not in res_v2.headers['Location']

    # API auth route upgrading token
    res_api = client.post('/api/auth', json={"token": master_token})
    assert res_api.status_code == 200
    assert res_api.json["token"] != master_token

    config.load_prefs = original_load
