import os
import pytest
from repository import ExcelRepository
import config

def test_demo_collection_exists_and_loads():
    demo_path = os.path.join("data", "demo_collection.xlsx")
    assert os.path.exists(demo_path), "demo_collection.xlsx should exist in data/"

    cfg = config.DATABASE_CONFIGS.get("Økonomisk Botanisk")
    assert cfg is not None, "Økonomisk Botanisk config should exist"

    df_reg, df_obs, df_photo, df_log, df_unval = ExcelRepository.load_excel(demo_path, cfg)

    assert len(df_reg) == 220, f"Expected 220 specimens, got {len(df_reg)}"
    assert len(df_obs) == 220, f"Expected 220 observation rows, got {len(df_obs)}"
    assert "ObjectID" in df_reg.columns
    assert "ObjectID" in df_obs.columns
    assert "PlantPart_Problem" in df_obs.columns
    assert len(df_log) > 0, "Log rows should be preserved"
    # Check that ObjectIDs match
    assert set(df_reg["ObjectID"]) == set(df_obs["ObjectID"]), "ObjectIDs must match across Registration and Observation"
