import threading
import time
import pytest
import pandas as pd
from models import AppState
from ui.main_window import ObjectProgramUI
from unittest.mock import MagicMock
import config


def test_concurrent_log_action_thread_safety():
    app = AppState()
    app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
    app.df_reg = pd.DataFrame([{"ObjectID": f"{i}", "Genus": "Pinus"} for i in range(100)]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([{"ObjectID": f"{i}", "Reviewed": False} for i in range(100)]).set_index("ObjectID")
    app.df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath"]).set_index("ObjectID")
    app.df_log = pd.DataFrame()
    app._log_records = []

    mock_ui = MagicMock()
    mock_ui.app = app

    # Attach log_action method from ObjectProgramUI
    mock_ui.log_action = ObjectProgramUI.log_action.__get__(mock_ui, MagicMock)

    errors = []

    def worker(worker_id):
        try:
            for i in range(25):
                oid = f"{(worker_id * 25 + i) % 100}"
                mock_ui.log_action(
                    "EDIT",
                    changed_fields=["Genus"],
                    changed_values=[f'Genus: "Pinus" -> "Pinus_{worker_id}_{i}"'],
                    oid=oid
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(app._log_records) == 100
    assert len(app.df_log) == 100
