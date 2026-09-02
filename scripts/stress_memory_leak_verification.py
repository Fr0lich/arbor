import os
import sys
import tracemalloc
import gc
import pandas as pd
from unittest.mock import MagicMock
import tkinter as tk

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import AppState
from ui.main_window import ObjectProgramUI
from ui.image_panel import ImagePanel

def test_memory_leak_verification(num_iterations=1000):
    print("=" * 60)
    print(f"RUNNING MEMORY LEAK & ENDURANCE AUDIT ({num_iterations} OBJECT CYCLES)")
    print("=" * 60)

    # Setup headless Tkinter root
    root = tk.Tk()
    root.withdraw()

    # Generate synthetic 1000-object AppState
    app = AppState()
    n_records = num_iterations
    oids = [f"SPEC-{i:04d}" for i in range(n_records)]
    app.active_object_ids = oids
    app.current_object_id = oids[0]

    app.df_reg = pd.DataFrame({
        "Genus": [f"Genus_{i}" for i in range(n_records)],
        "Species": [f"species_{i}" for i in range(n_records)],
        "Notes": [f"Sample note for object {i}" for i in range(n_records)]
    }, index=pd.Index(oids, name="ObjectID"))

    app.df_obs = pd.DataFrame({
        "Reviewed": [False] * n_records,
        "Cabinet": [f"Cabinet-{i % 20}" for i in range(n_records)],
        "MissingLabel": [False] * n_records
    }, index=pd.Index(oids, name="ObjectID"))

    main = MagicMock()
    main.app = app
    main.root = root
    main.initializing = False
    main.reg_entries = {}
    main.reg_vars = {}
    main.location_vars = {"Cabinet": tk.StringVar(value="Cabinet-0")}
    main.reviewed_var = tk.BooleanVar(value=False)
    main.problem_vars = {}
    main.loaded_problem_states = {}
    main.reg_field_widgets = {}
    main.app.redo_stacks = {}
    main.app.undo_stacks = {}
    main._cached_obs_dict = {oid: {"Cabinet": f"Cabinet-{i % 20}", "Reviewed": False} for i, oid in enumerate(oids)}
    main._is_navigating = False

    gc.collect()
    tracemalloc.start()
    snapshot_start = tracemalloc.take_snapshot()

    print(f"Starting navigation and edit loop over {num_iterations} iterations...")
    memory_samples = []

    for i in range(num_iterations):
        target_oid = oids[i]
        app.current_object_id = target_oid

        # Simulate user edit
        main.location_vars["Cabinet"].set(f"Updated-Cabinet-{i % 10}")
        main.reviewed_var.set(i % 2 == 0)

        # Commit current object
        ObjectProgramUI.commit_current_object(main, skip_heavy=False)

        # Sample memory every 200 iterations
        if (i + 1) % 200 == 0:
            gc.collect()
            current_mem, peak_mem = tracemalloc.get_traced_memory()
            memory_samples.append((i + 1, current_mem / (1024 * 1024), peak_mem / (1024 * 1024)))
            print(f"   Iteration {i + 1:4d}: Current Memory = {current_mem / (1024 * 1024):.2f} MB | Peak = {peak_mem / (1024 * 1024):.2f} MB")

    snapshot_end = tracemalloc.take_snapshot()
    tracemalloc.stop()
    root.destroy()

    # Compare memory growth between iteration 400 and iteration 1000
    mem_at_400 = memory_samples[1][1]  # at 400
    mem_at_1000 = memory_samples[-1][1] # at 1000
    growth = mem_at_1000 - mem_at_400

    print("-" * 60)
    print(f"Memory at 400 iterations:  {mem_at_400:.2f} MB")
    print(f"Memory at 1000 iterations: {mem_at_1000:.2f} MB")
    print(f"Memory delta across 600 cycles: {growth:+.2f} MB")

    # Assert bounded plateau (less than 25MB delta across 600 cycles with bounded undo stacks)
    assert growth < 25.0, f"Potential memory leak detected: growth of {growth:.2f} MB!"
    print("=" * 60)
    print(f"[PASS] Memory plateau verified! Endurance test passed ({num_iterations} cycles).")
    print("=" * 60)

if __name__ == "__main__":
    test_memory_leak_verification()
