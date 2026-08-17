import os
import tempfile
import tkinter as tk
from tkinter import messagebox
import pandas as pd
import pytest
import config
from ui.new_database_wizard import NewDatabaseWizard
from repository import ExcelRepository


@pytest.fixture(autouse=True)
def mock_messagebox(monkeypatch):
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **kw: True)
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **kw: True)
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **kw: True)
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **kw: True)


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def dummy_app():
    class DummyApp:
        def __init__(self):
            self.dark_mode_active = False
            self.config = config.DATABASE_CONFIGS.get("Økonomisk Botanisk", {})
            self.config_name = "Økonomisk Botanisk"
            self.excel_path = ""
            self.output_path = ""
            self.df_reg = None
            self.df_obs = None
            self.df_photo = None
            self.df_log = None
            self.initial_df_obs = None
    return DummyApp()


def test_wizard_init_and_dark_mode(tk_root, dummy_app):
    # Test light mode
    dummy_app.dark_mode_active = False
    wiz_light = NewDatabaseWizard(tk_root, dummy_app)
    assert wiz_light.current_step == 1
    assert wiz_light.dark_mode is False
    assert wiz_light.selected_template == "Botany / Herbarium"
    assert len(wiz_light.fields) > 0
    wiz_light.win.destroy()

    # Test dark mode
    dummy_app.dark_mode_active = True
    wiz_dark = NewDatabaseWizard(tk_root, dummy_app)
    assert wiz_dark.dark_mode is True
    assert wiz_dark.colors["surface"] == "#1e1e2e"
    wiz_dark.win.destroy()


def test_wizard_step_transitions_and_navigation(tk_root, dummy_app):
    wiz = NewDatabaseWizard(tk_root, dummy_app)

    # Step 1 -> Step 2
    wiz._on_next()
    assert wiz.current_step == 2

    # Step 2 -> Step 3
    wiz._on_next()
    assert wiz.current_step == 3

    # Step 3 -> Step 4
    wiz._on_next()
    assert wiz.current_step == 4

    # Step 4 -> Step 5
    wiz._on_next()
    assert wiz.current_step == 5

    # Step 5 -> Back to Step 4
    wiz._on_back()
    assert wiz.current_step == 4

    # Direct Stepper Click (visited steps)
    wiz._on_step_click(2)
    assert wiz.current_step == 2

    wiz.win.destroy()


def test_builtin_templates_loading(tk_root, dummy_app):
    wiz = NewDatabaseWizard(tk_root, dummy_app)

    # 1. Botany / Herbarium
    wiz._select_template("Botany / Herbarium")
    assert any("Genus" in f["name"] for f in wiz.fields)
    assert any("Species" in f["name"] for f in wiz.fields)

    # 2. Loan Tracking
    wiz._select_template("Loan Tracking")
    assert any("Borrower" in f["name"] for f in wiz.fields)
    assert any("Item Name" in f["name"] for f in wiz.fields)

    # 3. Blank Minimal
    wiz._select_template("Blank Minimal")
    assert any("Title" in f["name"] for f in wiz.fields)
    assert any("Category" in f["name"] for f in wiz.fields)

    wiz.win.destroy()


def test_schema_builder_actions(tk_root, dummy_app):
    wiz = NewDatabaseWizard(tk_root, dummy_app)
    wiz.goto_step(2)

    initial_count = len(wiz.fields)

    # Add custom field
    wiz.new_field_var.set("TestCustomField")
    wiz.new_field_type_var.set("multiline")
    wiz._add_field()

    assert len(wiz.fields) == initial_count + 1
    added = next(f for f in wiz.fields if f["name"] == "TestCustomField")
    assert added["type"] == "multiline"

    # Add reserved ObjectID (should not be added)
    wiz.new_field_var.set("ObjectID")
    wiz._add_field()
    assert len(wiz.fields) == initial_count + 1

    # Add duplicate (should not be added)
    wiz.new_field_var.set("TestCustomField")
    wiz._add_field()
    assert len(wiz.fields) == initial_count + 1

    # Move field up
    idx = [i for i, f in enumerate(wiz.fields) if f["name"] == "TestCustomField"][0]
    if idx > 0:
        prev_name = wiz.fields[idx - 1]["name"]
        wiz._move_field(idx, -1)
        assert wiz.fields[idx - 1]["name"] == "TestCustomField"
        assert wiz.fields[idx]["name"] == prev_name

    # Remove field
    new_idx = [i for i, f in enumerate(wiz.fields) if f["name"] == "TestCustomField"][0]
    wiz._remove_field(new_idx)
    assert not any(f["name"] == "TestCustomField" for f in wiz.fields)

    wiz.win.destroy()


def test_problem_flags_and_groups(tk_root, dummy_app):
    wiz = NewDatabaseWizard(tk_root, dummy_app)
    wiz.goto_step(3)

    # Auto-grouping
    wiz.fields = [
        {"name": "Genus", "type": "text"},
        {"name": "Species", "type": "text"},
        {"name": "Collector", "type": "text"},
        {"name": "Comment", "type": "multiline"},
        {"name": "UID", "type": "text", "readonly": True}
    ]
    wiz.goto_step(3)

    assert "Taxonomy" in wiz.groups
    assert "Genus" in wiz.groups["Taxonomy"]
    assert "Collection" in wiz.groups
    assert "Collector" in wiz.groups["Collection"]
    assert "Notes" in wiz.groups
    assert "Comment" in wiz.groups["Notes"]
    assert "Admin" in wiz.groups
    assert "UID" in wiz.groups["Admin"]

    wiz.win.destroy()


def test_image_url_token_preview(tk_root, dummy_app):
    wiz = NewDatabaseWizard(tk_root, dummy_app)
    wiz.goto_step(4)

    wiz.has_images_var.set(True)
    wiz.url_var.set("https://example.org/specimens/{num:04d}.jpg")
    wiz._update_url_preview()
    assert wiz.url_preview_lbl.cget("text") == "https://example.org/specimens/1001.jpg"

    wiz.url_var.set("https://example.org/specimens/{id}_{suffix}.jpg")
    wiz._update_url_preview()
    assert wiz.url_preview_lbl.cget("text") == "https://example.org/specimens/1001_.jpg"

    wiz.win.destroy()


def test_database_file_generation_and_loading(tk_root, dummy_app):
    completed_data = {}
    def on_complete(path, name):
        completed_data["path"] = path
        completed_data["name"] = name

    wiz = NewDatabaseWizard(tk_root, dummy_app, on_complete=on_complete)
    wiz.goto_step(5)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test_generated_db.xlsx")
        wiz.profile_name_var.set("Test Herbarium Profile")
        wiz.start_id_var.set("V-0010")
        wiz.row_count_var.set(3)
        wiz.output_path_var.set(test_file)

        wiz._initialize_database()

        # Check that Excel file was created
        assert os.path.exists(test_file)
        assert completed_data.get("path") == test_file
        assert completed_data.get("name") == "Test Herbarium Profile"

        # Verify Excel structure
        with pd.ExcelFile(test_file) as excel:
            assert "Registration" in excel.sheet_names
            assert "Observation" in excel.sheet_names
            assert "Photo" in excel.sheet_names
            assert "Log" in excel.sheet_names

        df_reg = pd.read_excel(test_file, sheet_name="Registration", index_col="ObjectID")
        assert len(df_reg) == 3
        assert list(df_reg.index) == ["V-0010", "V-0011", "V-0012"]
        assert "UID" in df_reg.columns

        # Verify load_excel compatibility
        loaded_reg, loaded_obs, loaded_photo, loaded_log = ExcelRepository.load_excel(test_file, dummy_app.config)
        assert len(loaded_reg) == 3
        assert "V-0010" in list(loaded_reg["ObjectID"])


def test_import_from_csv(tk_root, dummy_app, monkeypatch):
    wiz = NewDatabaseWizard(tk_root, dummy_app)

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "import_test.csv")
        sample_df = pd.DataFrame({
            "ObjectID": [1, 2],
            "BotanicalName": ["Quercus robur", "Betula pendula"],
            "IsProtected": [True, False],
            "FieldObservation": ["Found on hillside", "Riverbank specimen"]
        })
        sample_df.to_csv(csv_path, index=False)

        monkeypatch.setattr(tk.filedialog, "askopenfilename", lambda **kw: csv_path)
        wiz._import_schema_file()

        assert any(f["name"] == "BotanicalName" for f in wiz.fields)
        assert any(f["name"] == "IsProtected" and f["type"] == "checkbox" for f in wiz.fields)
        assert any(f["name"] == "FieldObservation" and f["type"] == "multiline" for f in wiz.fields)
        assert any(f["name"] == "UID" for f in wiz.fields)

    wiz.win.destroy()


def test_startup_dialog_integration(tk_root, dummy_app):
    from ui.dialogs import StartupDialog
    
    # Instantiate StartupDialog with (parent, app)
    dlg = StartupDialog(tk_root, dummy_app)
    
    # Verify create_new_database_startup method exists
    assert hasattr(dlg, "create_new_database_startup")
    assert hasattr(dlg, "on_new_db_created")

    # Simulate completion of wizard
    test_path = "C:/fake/path/my_new_database.xlsx"
    dlg.on_new_db_created(file_path=test_path, profile_name="Loan Tracking")

    assert dlg.db_path_var.get() == test_path
    if hasattr(dlg, "db_var"):
        assert dlg.db_var.get() == "Loan Tracking"
    
    dlg.win.destroy()
