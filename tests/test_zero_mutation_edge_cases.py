import pytest
import pandas as pd
from models import AppState
from backend.mobile_server import _execute_record_update
import config


def test_zero_mutation_guard_comprehensive_types():
    app = AppState()
    app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
    app.df_reg = pd.DataFrame([{
        "ObjectID": "5001",
        "Genus": "Pinus",
        "Species": "sylvestris"
    }]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([{
        "ObjectID": "5001",
        "Reviewed": False,
        "Images_Missing": False
    }]).set_index("ObjectID")
    app._log_records = []
    app.df_log = pd.DataFrame()
    app.dirty = False

    with app.df_lock:
        # 1. Boolean False with incoming empty string or False or None
        summary, err = _execute_record_update(
            app_state=app,
            oid="5001",
            reg_updates={"Genus": "  Pinus  ", "Species": "sylvestris"},
            obs_updates={"Images_Missing": "", "Reviewed": False},
            reviewed=False
        )

    assert err is None
    # Must not log phantom changes
    assert len(app._log_records) == 0
    assert app.df_log.empty
    assert app.dirty is False
