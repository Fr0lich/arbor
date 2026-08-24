"""
tests/test_mobile_frontend_serving.py

Integration tests for Flask static SPA delivery and authentication boundary (backend/mobile_server.py).
Verifies that static assets (HTML/CSS/JS) are served without header restrictions,
while /api/* routes strictly enforce session token authorization.
"""

import os
import pandas as pd
import pytest
from models import AppState
from backend.mobile_server import MobileServerManager, DIST_DIR


@pytest.fixture
def mock_app_state():
    app = AppState()
    app.config = {"has_images": False}
    app.config_name = "Botanical Test Database"
    app.df_reg = pd.DataFrame([{"ObjectID": "101", "Genus": "Quercus", "Species": "robur"}]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([{"ObjectID": "101", "Reviewed": False}]).set_index("ObjectID")
    app.df_photo = pd.DataFrame()
    app.df_log = pd.DataFrame()
    app.undo_stacks = {}
    return app


def test_serve_index_html(mock_app_state):
    mgr = MobileServerManager(mock_app_state)
    client = mgr.app.test_client()

    # GET / without any auth headers should return the SPA index.html
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert "Arbor Companion" in resp.get_data(as_text=True)


def test_serve_static_assets(mock_app_state):
    mgr = MobileServerManager(mock_app_state)
    client = mgr.app.test_client()

    # CSS asset
    resp_css = client.get("/assets/index.css")
    assert resp_css.status_code == 200
    assert "text/css" in resp_css.mimetype or "text/plain" in resp_css.mimetype
    assert "--color-fern" in resp_css.get_data(as_text=True)

    # JS asset
    resp_js = client.get("/assets/index.js")
    assert resp_js.status_code == 200
    assert "javascript" in resp_js.mimetype or "text/plain" in resp_js.mimetype
    assert "Arbor Mobile Web Companion" in resp_js.get_data(as_text=True)


def test_spa_fallback_routing(mock_app_state):
    mgr = MobileServerManager(mock_app_state)
    client = mgr.app.test_client()

    # Deep client route should fallback to index.html
    resp = client.get("/specimens/101")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert "Arbor Companion" in resp.get_data(as_text=True)


def test_api_404_isolation(mock_app_state):
    mgr = MobileServerManager(mock_app_state)
    client = mgr.app.test_client()

    # Unknown /api/ route must return JSON 404, NOT HTML fallback
    resp = client.get("/api/unknown_endpoint", headers={"X-Session-Token": mgr.session_token})
    assert resp.status_code == 404
    data = resp.get_json()
    assert data is not None
    assert "error" in data


def test_api_auth_boundary(mock_app_state):
    mgr = MobileServerManager(mock_app_state)
    client = mgr.app.test_client()

    # Static index allowed without token
    assert client.get("/").status_code == 200

    # API endpoint rejected without token
    assert client.get("/api/status").status_code == 401

    # API endpoint accepted with token
    assert client.get("/api/status", headers={"X-Session-Token": mgr.session_token}).status_code == 200
