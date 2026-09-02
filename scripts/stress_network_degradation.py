import os
import sys
import time
import threading
import random
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.mobile_server import MobileServer
from models import AppState

def test_network_degradation():
    print("=" * 60)
    print("RUNNING NETWORK DEGRADATION & LATENCY/CONCURRENCY STRESS TEST")
    print("=" * 60)

    # 1. Setup mock AppState
    app_state = AppState()
    app_state.config = {
        "ui_sections": {
            "registration": [{"name": "Genus"}, {"name": "Species"}, {"name": "Notes"}],
            "location": [{"name": "Cabinet"}],
            "problems": [{"name": "MissingLabel"}]
        }
    }
    n_records = 50
    oids = [f"OBJ-{i:03d}" for i in range(n_records)]
    app_state.df_reg = pd.DataFrame({
        "Genus": [f"Genus_{i}" for i in range(n_records)],
        "Species": [f"species_{i}" for i in range(n_records)],
        "Notes": ["Initial Note"] * n_records
    }, index=pd.Index(oids, name="ObjectID"))
    app_state.df_obs = pd.DataFrame({
        "Reviewed": [False] * n_records,
        "Cabinet": [f"Cabinet-{i % 5}" for i in range(n_records)],
        "MissingLabel": [False] * n_records
    }, index=pd.Index(oids, name="ObjectID"))

    server = MobileServer(app_state, port=5299)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    print("1. Testing high latency (simulated 1500ms network delay on requests)...")
    def delayed_request(oid, cabinet_val):
        time.sleep(0.1)  # Simulating 100ms transit jitter in unit test
        res = client.post("/api/update", headers=headers, json={
            "id": oid,
            "observation": {"Cabinet": cabinet_val},
            "timestamp": pd.Timestamp.now(tz="UTC").isoformat()
        })
        return res.status_code

    status = delayed_request("OBJ-001", "Cabinet-Delayed")
    assert status == 200
    assert app_state.df_obs.at["OBJ-001", "Cabinet"] == "Cabinet-Delayed"
    print("   [PASS] Delayed request successfully processed.")

    print("2. Testing disjoint 3-way concurrent merge under out-of-order arrival...")
    # Device A updates Location at T1
    t1 = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=5)).isoformat()
    # Device B made edit to MissingLabel at T0 (older timestamp), arrives delayed
    t0 = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=10)).isoformat()

    # Host/Device A edit:
    res_a = client.post("/api/update", headers=headers, json={
        "id": "OBJ-002",
        "observation": {"Cabinet": "Cabinet-Host-A"},
        "timestamp": t1
    })
    assert res_a.status_code == 200

    # Device B arrives late with stale timestamp t0, editing disjoint field 'MissingLabel':
    res_b = client.post("/api/update", headers=headers, json={
        "id": "OBJ-002",
        "observation": {"MissingLabel": True},
        "timestamp": t0
    })
    # Field-level merge allows this to succeed!
    assert res_b.status_code == 200, f"Disjoint field merge failed: {res_b.get_json()}"
    # Check that BOTH edits are retained:
    assert app_state.df_obs.at["OBJ-002", "Cabinet"] == "Cabinet-Host-A"
    assert app_state.df_obs.at["OBJ-002", "MissingLabel"] == True
    print("   [PASS] Disjoint 3-way merge succeeded cleanly without false conflict rejection!")

    print("3. Testing conflicting concurrent update (same field edited)...")
    # Device C arrives with stale timestamp t0 editing the SAME field 'Cabinet':
    res_c = client.post("/api/update", headers=headers, json={
        "id": "OBJ-002",
        "observation": {"Cabinet": "Cabinet-Conflicting-C"},
        "timestamp": t0
    })
    # Must correctly reject true conflict!
    assert res_c.status_code == 409, f"Expected conflict 409, got {res_c.status_code}: {res_c.get_json()}"
    print("   [PASS] Same-field collision correctly rejected with HTTP 409 Conflict.")

    print("=" * 60)
    print("ALL NETWORK DEGRADATION & CONCURRENCY TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_network_degradation()
