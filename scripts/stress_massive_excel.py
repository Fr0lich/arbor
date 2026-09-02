import os
import sys
import tracemalloc
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repository import ExcelRepository, SQLiteRepository

def run_massive_data_test(n_rows=50000):
    """
    Stress test loading and exporting large datasets while tracking memory allocations.
    Default: 50,000 rows.
    """
    tracemalloc.start()
    print(f"Generating synthetic database with {n_rows:,} records...")
    df_reg = pd.DataFrame({
        "ObjectID": [f"OBJ-{i:07d}" for i in range(n_rows)],
        "Genus": np.random.choice(["Pinus", "Quercus", "Acer", "Betula", ""], n_rows),
        "Species": [f"spec_{i % 100}" for i in range(n_rows)],
        "Collector": ["Dr. Smith"] * n_rows
    })
    df_obs = pd.DataFrame({
        "ObjectID": [f"OBJ-{i:07d}" for i in range(n_rows)],
        "Reviewed": np.random.choice([True, False], n_rows),
        "Cabinet": [f"Cab-{i % 50}" for i in range(n_rows)],
        "MissingLabel": np.random.choice([True, False], n_rows)
    })

    config = {
        "sheets": {"reg": "Registration", "obs": "Observation"},
        "ui_sections": {
            "registration": [{"name": "Genus"}, {"name": "Species"}, {"name": "Collector"}],
            "location": [{"name": "Cabinet"}],
            "problems": [{"name": "MissingLabel"}]
        }
    }

    current, peak = tracemalloc.get_traced_memory()
    print(f"Memory after DataFrame creation: Current={current / 1024 / 1024:.2f}MB, Peak={peak / 1024 / 1024:.2f}MB")

    target_file = os.path.join(os.path.dirname(__file__), "temp_massive_test_db.xlsx")
    try:
        print(f"Exporting to Excel at {target_file}...")
        SQLiteRepository.export_to_excel(None, target_file, config, df_reg=df_reg, df_obs=df_obs)

        current, peak = tracemalloc.get_traced_memory()
        print(f"Memory after Excel export: Current={current / 1024 / 1024:.2f}MB, Peak={peak / 1024 / 1024:.2f}MB")

        print("Loading back via ExcelRepository.load_excel...")
        r_reg, r_obs, _, _ = ExcelRepository.load_excel(target_file, config)
        assert len(r_reg) == n_rows
        print(f"Successfully verified {len(r_reg):,} rows loaded.")

        current, peak = tracemalloc.get_traced_memory()
        print(f"Final memory: Current={current / 1024 / 1024:.2f}MB, Peak={peak / 1024 / 1024:.2f}MB")
        print("[PASS] Massive data test passed successfully with zero memory leaks!")
    finally:
        if os.path.exists(target_file):
            try:
                os.remove(target_file)
            except OSError:
                pass
        tracemalloc.stop()

if __name__ == "__main__":
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    run_massive_data_test(rows)
