import pytest
import pandas as pd
from models import AppState

def test_app_state_initialization():
    state = AppState()
    assert state.df_reg is None
    assert state.df_obs is None
    assert state.df_photo is None
    assert state.dirty is False
    assert state.active_object_ids == []

def test_app_state_repr():
    state = AppState()
    repr_str = repr(state)
    assert "dirty=False" in repr_str
    assert "objects=0" in repr_str

    # Simulate loading data
    state.df_reg = pd.DataFrame({"ObjectID": [1, 2, 3]})
    state.dirty = True
    state.excel_path = "test.xlsx"
    state.current_object_id = "1"

    repr_str = repr(state)
    assert "dirty=True" in repr_str
    assert "objects=3" in repr_str
    assert "test.xlsx" in repr_str
    assert "active_id=1" in repr_str

def test_app_state_str():
    state = AppState()
    str_rep = str(state)
    assert "No File Loaded" in str_rep
    assert "Saved" in str_rep

    state.excel_path = "data.xlsx"
    state.active_object_ids = ["1", "2"]
    state.dirty = True

    str_rep = str(state)
    assert "data.xlsx" in str_rep
    assert "Unsaved Changes" in str_rep
    assert "2 active objects" in str_rep
