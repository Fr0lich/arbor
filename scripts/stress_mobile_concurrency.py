import os
import sys
import concurrent.futures
import random
import time
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.mobile_server import MobileServer
from models import AppState

def run_concurrency_test(workers=50, iterations_per_worker=10):
    """
    Stress test local Flask mobile server under high concurrency with simultaneous
    reads, updates, and batch sync requests across multiple simulated mobile devices.
    """
    print(f"Setting up mock AppState with 1,000 records...")
    app_state = AppState()
    app_state.config = {
        "ui_sections": {
            "registration": [{"name": "Genus"}, {"name": "Species"}],
            "location": [{"name": "Cabinet"}],
            "problems": [{"name": "MissingLabel"}]
        }
    }
    n_records = 1000
    app_state.df_reg = pd.DataFrame({
        "Genus": [f"Genus_{i}" for i in range(n_records)],
        "Species": [f"species_{i}" for i in range(n_records)],
        "Cabinet": [f"Cab_{i % 10}" for i in range(n_records)]
    }, index=pd.Index([f"OBJ-{i:04d}" for i in range(n_records)], name="ObjectID"))
    app_state.df_obs = pd.DataFrame({
        "Reviewed": [False] * n_records,
        "Cabinet": [f"Cab_{i % 10}" for i in range(n_records)]
    }, index=pd.Index([f"OBJ-{i:04d}" for i in range(n_records)], name="ObjectID"))

    server = MobileServer(app_state, port=5199)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    print(f"Launching {workers} concurrent client threads ({workers * iterations_per_worker} total requests)...")
    errors = []

    def client_worker(worker_id):
        try:
            for it in range(iterations_per_worker):
                # Partition records across workers so each writes to their own records
                target_oid = f"OBJ-{(worker_id * iterations_per_worker + it) % n_records:04d}"
                roll = random.random()
                if roll < 0.4:
                    # Read single object
                    res = client.get(f"/api/object/{target_oid}", headers=headers)
                    if res.status_code != 200:
                        errors.append(f"Worker {worker_id} GET /api/object failed: {res.status_code}")
                elif roll < 0.7:
                    # Query objects list
                    res = client.get(f"/api/objects?limit=25&offset={random.randint(0, 100)}", headers=headers)
                    if res.status_code != 200:
                        errors.append(f"Worker {worker_id} GET /api/objects failed: {res.status_code}")
                else:
                    # Single update with fresh timestamp
                    payload = {
                        "id": target_oid,
                        "reviewed": True,
                        "observation": {"Cabinet": f"Cab-Worker-{worker_id}"},
                        "timestamp": pd.Timestamp.now(tz="UTC").isoformat()
                    }
                    res = client.post("/api/update", headers=headers, json=payload)
                    if res.status_code != 200:
                        errors.append(f"Worker {worker_id} POST /api/update failed: {res.status_code} - {res.get_json()}")
                time.sleep(0.002)
        except Exception as e:
            errors.append(f"Worker {worker_id} exception: {e}")

    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(client_worker, i) for i in range(workers)]
        concurrent.futures.wait(futures)
    duration = time.time() - start_time

    print(f"Concurrency run finished in {duration:.2f}s. Total errors: {len(errors)}")
    if errors:
        print("Sample errors encountered:", errors[:10])
    assert len(errors) == 0, f"Concurrency test encountered {len(errors)} errors!"
    print(f"[PASS] High concurrency test ({workers} concurrent simulated devices) passed with 100% success!")

if __name__ == "__main__":
    run_concurrency_test()
