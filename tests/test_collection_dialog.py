import os
import pytest
import tkinter as tk
from ui.create_collection_dialog import CreateCollectionDialog, create_standard_collection_file, SHEET_BLUEPRINT_INFO
from ui.dialogs import CreateCollectionDialog as ReexportedDialog
from repository import ExcelRepository
import config

def test_sheet_blueprint_info_completeness():
    assert "reg" in SHEET_BLUEPRINT_INFO
    assert "obs" in SHEET_BLUEPRINT_INFO
    assert "log" in SHEET_BLUEPRINT_INFO

    for key, info in SHEET_BLUEPRINT_INFO.items():
        assert "title" in info
        assert "badge" in info
        assert "summary" in info
        assert "chips" in info
        assert "new_curator_bullets" in info
        assert "curator_bullets" in info
        assert len(info["chips"]) > 0
        assert "🌱" in info["new_curator_bullets"]
        assert "🏛️" in info["curator_bullets"]

def test_reexported_dialog_is_identical():
    assert ReexportedDialog is CreateCollectionDialog

def test_create_standard_collection_file(tmp_path):
    target = str(tmp_path / "test_new_collection.xlsx")
    create_standard_collection_file(target)

    assert os.path.exists(target)

    cfg = config.DATABASE_CONFIGS.get("Økonomisk Botanisk")
    assert cfg is not None

    df_reg, df_obs, df_photo, df_log, df_unval = ExcelRepository.load_excel(target, cfg)

    # 1 sample specimen created
    assert len(df_reg) == 1
    assert len(df_obs) == 1
    assert "ObjectID" in df_reg.columns
    assert "Genus" in df_reg.columns
    assert "Species" in df_reg.columns
    assert "UID" in df_reg.columns
    assert df_reg.iloc[0]["Genus"] == "Welwitschia"
    assert df_reg.iloc[0]["Species"] == "mirabilis"

    # Observation verification
    assert "PlantPart_Problem" in df_obs.columns
    assert "Building" in df_obs.columns
    assert df_obs.iloc[0]["PlantPart_Problem"] == False

    # Log verification
    assert len(df_log) >= 1
    assert "Action" in df_log.columns
    assert df_log.iloc[0]["Action"] == "DATABASE_CREATED"

    # Unvalidated source exists
    assert isinstance(df_unval, type(df_reg))
