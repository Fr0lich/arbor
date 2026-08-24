"""
tests/test_mobile_api.py

Comprehensive unit tests for the embedded Flask Mobile Companion server (backend/mobile_server.py).
Tests REST endpoints, thread safety, authentication, undo stack preservation, and LFI defense.
"""

import os
import tempfile
import threading
import time
import pandas as pd
import pytest

from models import AppState
from backend.mobile_server import MobileServerManager, _find_object_index, _extract_photo_filenames, _safe_resolve_local_image
from repository import REVIEWED_COLUMN, REVIEWED_AT_COLUMN


@pytest.fixture
def sample_app_state():
    """Creates a mock AppState populated with test data."""
    app = AppState()
    app.config = {
        "has_images": True,
        "image_url_pattern": "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg",
        "image_mode": "online"
    }
    app.config_name = "Botanical Test Vault"
    app.excel_path = "C:/fake/path/test_collection.xlsx"

    # df_reg (indexed by ObjectID)
    app.df_reg = pd.DataFrame([
        {"ObjectID": "1001", "Genus": "Quercus", "Species": "robur", "Family": "Fagaceae", "Cabinet": "01", "Drawer": "05"},
        {"ObjectID": "1002", "Genus": "Pinus", "Species": "sylvestris", "Family": "Pinaceae", "Cabinet": "01", "Drawer": "06"},
        {"ObjectID": "1003", "Genus": "Betula", "Species": "pendula", "Family": "Betulaceae", "Cabinet": "02", "Drawer": "01"},
    ]).set_index("ObjectID")

    # df_obs (indexed by ObjectID)
    app.df_obs = pd.DataFrame([
        {"ObjectID": "1001", REVIEWED_COLUMN: True, REVIEWED_AT_COLUMN: "2026-08-20 10:00:00", "Genus_Problem": False, "Notes": "Verified"},
        {"ObjectID": "1002", REVIEWED_COLUMN: False, REVIEWED_AT_COLUMN: None, "Genus_Problem": True, "Notes": "Check genus spelling"},
        {"ObjectID": "1003", REVIEWED_COLUMN: False, REVIEWED_AT_COLUMN: None, "Genus_Problem": False, "Notes": ""},
    ]).set_index("ObjectID")

    # df_photo (multi-row photo index)
    app.df_photo = pd.DataFrame([
        {"ObjectID": "1001", "Filename": "1001_a.jpg"},
        {"ObjectID": "1001", "Filename": "1001_b.jpg"},
        {"ObjectID": "1002", "Filename": "1002_a.jpg"},
    ]).set_index("ObjectID")

    app.df_log = pd.DataFrame()
    app._log_records = []
    app.undo_stacks = {}
    return app


def test_index_lookup_and_photo_extraction(sample_app_state):
    # Test _find_object_index with str, int, whitespace
    assert _find_object_index(sample_app_state.df_reg, "1001") == "1001"
    assert _find_object_index(sample_app_state.df_reg, 1001) == "1001"
    assert _find_object_index(sample_app_state.df_reg, " 1001 ") == "1001"
    assert _find_object_index(sample_app_state.df_reg, "9999") is None

    # Test _extract_photo_filenames (multiple rows vs single row vs none)
    assert _extract_photo_filenames(sample_app_state.df_photo, "1001") == ["1001_a.jpg", "1001_b.jpg"]
    assert _extract_photo_filenames(sample_app_state.df_photo, "1002") == ["1002_a.jpg"]
    assert _extract_photo_filenames(sample_app_state.df_photo, "1003") == []


def test_server_lifecycle(sample_app_state):
    mgr = MobileServerManager(sample_app_state)
    assert not mgr.is_running
    
    port = mgr.start()
    assert mgr.is_running
    assert port > 0

    status = mgr.get_status()
    assert status["is_running"] is True
    assert status["port"] == port
    assert len(status["session_token"]) == 8

    mgr.stop()
    assert not mgr.is_running


def test_api_auth_and_status(sample_app_state):
    mgr = MobileServerManager(sample_app_state)
    client = mgr.app.test_client()
    token = mgr.session_token

    # Missing token -> 401
    resp = client.get("/api/status")
    assert resp.status_code == 401

    # Valid token via header
    resp = client.get("/api/status", headers={"X-Session-Token": token})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "online"
    assert data["database_name"] == "Botanical Test Vault"
    assert data["total_objects"] == 3
    assert data["reviewed_count"] == 1
    assert data["pending_count"] == 2

    # Valid token via query param
    resp = client.get(f"/api/status?token={token}")
    assert resp.status_code == 200


def test_api_objects_query_and_filtering(sample_app_state):
    mgr = MobileServerManager(sample_app_state)
    client = mgr.app.test_client()
    headers = {"X-Session-Token": mgr.session_token}

    # All objects
    resp = client.get("/api/objects", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_matching"] == 3
    assert len(data["objects"]) == 3

    # Filter status=reviewed
    resp = client.get("/api/objects?status=reviewed", headers=headers)
    data = resp.get_json()
    assert data["total_matching"] == 1
    assert data["objects"][0]["id"] == "1001"

    # Filter status=pending
    resp = client.get("/api/objects?status=pending", headers=headers)
    data = resp.get_json()
    assert data["total_matching"] == 2
    assert [o["id"] for o in data["objects"]] == ["1002", "1003"]

    # Filter status=flagged
    resp = client.get("/api/objects?status=flagged", headers=headers)
    data = resp.get_json()
    assert data["total_matching"] == 1
    assert data["objects"][0]["id"] == "1002"

    # Search query
    resp = client.get("/api/objects?q=pinus", headers=headers)
    data = resp.get_json()
    assert data["total_matching"] == 1
    assert data["objects"][0]["genus"] == "Pinus"


def test_api_object_detail(sample_app_state):
    mgr = MobileServerManager(sample_app_state)
    client = mgr.app.test_client()
    headers = {"X-Session-Token": mgr.session_token}

    # 404 for unknown object
    resp = client.get("/api/object/9999", headers=headers)
    assert resp.status_code == 404

    # Valid detail
    resp = client.get("/api/object/1001", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == "1001"
    assert data["registration"]["Genus"] == "Quercus"
    assert data["observation"]["Reviewed"] is True
    assert data["review_status"] == "reviewed"
    assert len(data["images"]["online_urls"]) == 4
    assert len(data["images"]["local_endpoints"]) == 2


def test_api_update_mutation_undo_and_events(sample_app_state):
    mgr = MobileServerManager(sample_app_state)
    client = mgr.app.test_client()
    headers = {"X-Session-Token": mgr.session_token}

    assert sample_app_state.dirty is False
    assert "1002" not in sample_app_state.undo_stacks

    # Update object 1002: Mark as Reviewed and update Notes
    payload = {
        "id": "1002",
        "reviewed": True,
        "observation": {
            "Notes": "Spelling confirmed in herbarium sheet"
        }
    }
    resp = client.post("/api/update", json=payload, headers=headers)
    assert resp.status_code == 200
    res_data = resp.get_json()
    assert res_data["success"] is True
    assert res_data["review_status"] == "reviewed"

    # Verify AppState mutation
    assert bool(sample_app_state.df_obs.at["1002", REVIEWED_COLUMN]) is True
    assert sample_app_state.df_obs.at["1002", "Notes"] == "Spelling confirmed in herbarium sheet"
    assert sample_app_state.df_obs.at["1002", REVIEWED_AT_COLUMN] is not None
    assert sample_app_state.dirty is True

    # Verify Undo Stack Snapshotting
    assert "1002" in sample_app_state.undo_stacks
    assert len(sample_app_state.undo_stacks["1002"]) == 1
    prev_snapshot = sample_app_state.undo_stacks["1002"][0]
    assert bool(prev_snapshot[REVIEWED_COLUMN]) is False  # previous state before update

    # Verify Event Queue Delivery
    assert mgr.event_queue.qsize() == 1
    event = mgr.event_queue.get_nowait()
    assert event["oid"] == "1002"
    assert event["reviewed"] is True


def test_safe_image_resolution_and_lfi_defense(sample_app_state):
    with tempfile.TemporaryDirectory() as tmpdir:
        sample_app_state.image_folder = tmpdir
        sample_app_state.config["image_folder"] = tmpdir

        # Create valid image
        valid_img_path = os.path.join(tmpdir, "1001_a.jpg")
        with open(valid_img_path, "wb") as f:
            f.write(b"FAKE_JPEG_DATA")

        # Create outside image attempting traversal
        outside_dir = tempfile.gettempdir()
        outside_file = os.path.join(outside_dir, "secret.jpg")
        with open(outside_file, "wb") as f:
            f.write(b"SECRET_DATA")

        # 1. Valid resolution
        resolved = _safe_resolve_local_image("1001", 0, sample_app_state)
        assert resolved == valid_img_path

        # 2. Out of bounds index
        assert _safe_resolve_local_image("1001", 99, sample_app_state) is None

        # 3. Path traversal attack in df_photo
        sample_app_state.df_photo.at["1001", "Filename"] = "../../secret.jpg"
        resolved_bad = _safe_resolve_local_image("1001", 0, sample_app_state)
        assert resolved_bad is None  # Must reject path traversal


def test_concurrent_df_lock_stress(sample_app_state):
    mgr = MobileServerManager(sample_app_state)
    client = mgr.app.test_client()
    headers = {"X-Session-Token": mgr.session_token}
    errors = []

    def writer_task(worker_id):
        for i in range(20):
            try:
                resp = client.post("/api/update", json={
                    "id": "1003",
                    "reviewed": bool(i % 2 == 0),
                    "observation": {"Notes": f"Worker {worker_id} iteration {i}"}
                }, headers=headers)
                if resp.status_code != 200:
                    errors.append(f"Writer {worker_id} failed: {resp.status_code}")
            except Exception as e:
                errors.append(str(e))

    def reader_task():
        for _ in range(30):
            try:
                resp = client.get("/api/objects", headers=headers)
                if resp.status_code != 200:
                    errors.append(f"Reader failed: {resp.status_code}")
            except Exception as e:
                errors.append(str(e))

    threads = [
        threading.Thread(target=writer_task, args=(1,)),
        threading.Thread(target=writer_task, args=(2,)),
        threading.Thread(target=reader_task),
        threading.Thread(target=reader_task)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
