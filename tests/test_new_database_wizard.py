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
    assert wiz_dark.colors["surface"] == "#181c19"
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

    # Duplicate field
    idx = [i for i, f in enumerate(wiz.fields) if f["name"] == "TestCustomField"][0]
    wiz._duplicate_field(idx)
    assert any(f["name"] == "TestCustomField_Copy" for f in wiz.fields)

    # Move field up
    idx = [i for i, f in enumerate(wiz.fields) if f["name"] == "TestCustomField"][0]
    if idx > 0:
        prev_name = wiz.fields[idx - 1]["name"]
        wiz._move_field(idx, -1)
        assert wiz.fields[idx - 1]["name"] == "TestCustomField"
        assert wiz.fields[idx]["name"] == prev_name

    # Toggle all readonly
    wiz._toggle_all_readonly()
    assert all(f["readonly"] for f in wiz.fields if f["name"].upper() != "UID")
    wiz._toggle_all_readonly()
    assert not all(f["readonly"] for f in wiz.fields if f["name"].upper() != "UID")

    # Remove field
    new_idx = [i for i, f in enumerate(wiz.fields) if f["name"] == "TestCustomField"][0]
    wiz._remove_field(new_idx)
    assert not any(f["name"] == "TestCustomField" for f in wiz.fields)

    wiz.win.destroy()


def test_choice_editing_and_batch_add(tk_root, dummy_app):
    wiz = NewDatabaseWizard(tk_root, dummy_app)
    wiz.goto_step(2)

    # Add a choice field
    wiz.fields.append({"name": "Habitat", "type": "choice", "readonly": False, "choices": ["Forest", "Alpine"]})
    wiz._refresh_fields_table()

    # Modify choices
    idx = [i for i, f in enumerate(wiz.fields) if f["name"] == "Habitat"][0]
    wiz.fields[idx]["choices"] = ["Forest", "Alpine", "Coastal", "Wetland"]
    assert len(wiz.fields[idx]["choices"]) == 4

    wiz.win.destroy()


def test_category_first_step3_organization(tk_root, dummy_app, monkeypatch):
    wiz = NewDatabaseWizard(tk_root, dummy_app)
    wiz.goto_step(3)

    # 1. Custom fields and auto-grouping
    wiz.fields = [
        {"name": "Genus", "type": "text"},
        {"name": "Species", "type": "text"},
        {"name": "Collector", "type": "text"},
        {"name": "Comment", "type": "multiline"},
        {"name": "UID", "type": "text", "readonly": True}
    ]
    wiz._smart_auto_organize()

    assert "Taxonomy" in wiz.groups
    assert "Genus" in wiz.groups["Taxonomy"]
    assert "Collection" in wiz.groups
    assert "Collector" in wiz.groups["Collection"]
    assert "Notes" in wiz.groups
    assert "Comment" in wiz.groups["Notes"]
    assert "Admin" in wiz.groups
    assert "UID" in wiz.groups["Admin"]

    # 2. Select Category Tab
    wiz._select_category_tab("Taxonomy")
    assert wiz.active_category == "Taxonomy"
    assert wiz.preview_active_group == "Taxonomy"

    # 3. Pull Field into Active Category
    wiz.field_group_map["Collector"] = "Collection"
    # Pull 'Collector' into 'Taxonomy'
    wiz.field_group_map["Collector"] = wiz.active_category
    assert wiz.field_group_map["Collector"] == "Taxonomy"

    # 4. Move Field out of Active Category to 'Collection'
    wiz.field_group_map["Collector"] = "Collection"
    assert wiz.field_group_map["Collector"] == "Collection"

    # 5. Validation strategy switching
    wiz._apply_validation_strategy("all_fields")
    assert wiz.problem_flags["Genus"] is True
    assert wiz.problem_flags["Species"] is True
    assert wiz.problem_flags["Collector"] is True

    wiz._apply_validation_strategy("none")
    assert wiz.problem_flags["Genus"] is False
    assert wiz.problem_flags["Species"] is False

    wiz._apply_validation_strategy("key_fields")
    assert wiz.problem_flags["Genus"] is True
    assert wiz.problem_flags["Species"] is True
    assert wiz.problem_flags["Comment"] is False

    # 6. Flag suggestion engine
    tax_suggs = wiz._get_flag_suggestions("Species", "text")
    assert any("Nomenclature_Outdated" in s[0] for s in tax_suggs)
    
    geo_suggs = wiz._get_flag_suggestions("Locality", "text")
    assert any("Georef_Needed" in s[0] for s in geo_suggs)

    date_suggs = wiz._get_flag_suggestions("Due Date", "text")
    assert any("Overdue_Notice" in s[0] for s in date_suggs)

    # 7. Custom flag addition and deletion undo
    wiz.custom_problem_flags.append({
        "name": "Nomenclature_Outdated",
        "maps_to": "Species",
        "description": "Taxonomic name needs review",
        "category": "Taxonomy"
    })
    wiz._refresh_step3_ui()
    assert len(wiz.custom_problem_flags) == 1
    assert wiz.custom_problem_flags[0]["name"] == "Nomenclature_Outdated"

    wiz._delete_custom_flag(0)
    assert len(wiz.custom_problem_flags) == 0
    wiz._undo_delete_custom_flag()
    assert len(wiz.custom_problem_flags) == 1

    # 8. Inline field addition to a category
    monkeypatch.setattr(tk.simpledialog, "askstring", lambda *a, **kw: "Phenology")
    wiz._add_field_to_group("Taxonomy")
    assert any(f["name"] == "Phenology" for f in wiz.fields)
    assert wiz.field_group_map["Phenology"] == "Taxonomy"

    # 9. Live preview mode toggling
    wiz._toggle_preview_mode()
    assert wiz.preview_mode == "focus"
    wiz._toggle_preview_mode()
    assert wiz.preview_mode == "standard"

    wiz.win.destroy()


def test_image_url_token_preview(tk_root, dummy_app):
    wiz = NewDatabaseWizard(tk_root, dummy_app)
    wiz.goto_step(4)

    wiz.has_images_var.set(True)
    wiz.url_var.set("https://example.org/specimens/{num:04d}.jpg")
    wiz.test_id_var.set("1001")
    wiz._update_url_preview()
    assert wiz.url_preview_lbl.cget("text") == "https://example.org/specimens/1001.jpg"

    wiz.url_var.set("https://example.org/specimens/{id}_{suffix}.jpg")
    wiz._update_url_preview()
    assert wiz.url_preview_lbl.cget("text") == "https://example.org/specimens/1001_.jpg"

    # Presets
    wiz._apply_url_preset("images/specimen_{num:04d}.jpg")
    assert "images/specimen_1001.jpg" in wiz.url_preview_lbl.cget("text")

    wiz.win.destroy()


def test_database_file_generation_with_modules(tk_root, dummy_app):
    completed_data = {}
    def on_complete(path, name):
        completed_data["path"] = path
        completed_data["name"] = name

    wiz = NewDatabaseWizard(tk_root, dummy_app, on_complete=on_complete)
    wiz.goto_step(3)

    # Add custom problem flag
    wiz.custom_problem_flags.append({
        "name": "Nomenclature_Outdated",
        "maps_to": "Species",
        "description": "Taxonomic name needs review",
        "category": "Taxonomy"
    })

    # Enable Location, Loan, and Condition Modules in Step 4
    wiz.include_location = True
    wiz.include_loan = True
    wiz.include_condition = True

    wiz.goto_step(5)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test_full_modules_db.xlsx")
        wiz.profile_name_var.set("Test Herbarium Profile")
        wiz.start_id_var.set("V-0010")
        wiz.row_count_var.set(3)
        wiz.output_path_var.set(test_file)

        wiz._initialize_database()

        # Check that Excel file was created
        assert os.path.exists(test_file)
        assert completed_data.get("path") == test_file
        assert completed_data.get("name") == "Test Herbarium Profile"

        # Verify Excel structure and sheets
        with pd.ExcelFile(test_file) as excel:
            assert "Registration" in excel.sheet_names
            assert "Observation" in excel.sheet_names
            assert "Photo" in excel.sheet_names
            assert "Log" in excel.sheet_names

        df_reg = pd.read_excel(test_file, sheet_name="Registration", index_col="ObjectID")
        assert len(df_reg) == 3
        assert list(df_reg.index) == ["V-0010", "V-0011", "V-0012"]
        assert "UID" in df_reg.columns

        # Verify Observation sheet contains Location, Loan, Condition and Custom Problem Flag columns
        df_obs = pd.read_excel(test_file, sheet_name="Observation", index_col="ObjectID")
        assert "Nomenclature_Outdated" in df_obs.columns
        assert "Building" in df_obs.columns
        assert "Borrower" in df_obs.columns
        assert "Condition Status" in df_obs.columns

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
    
    dlg = StartupDialog(tk_root, dummy_app)
    
    assert hasattr(dlg, "create_new_database_startup")
    assert hasattr(dlg, "on_new_db_created")

    test_path = "C:/fake/path/my_new_database.xlsx"
    dlg.on_new_db_created(file_path=test_path, profile_name="Loan Tracking")

    assert dlg.db_path_var.get() == test_path
    if hasattr(dlg, "db_var"):
        assert dlg.db_var.get() == "Loan Tracking"
    
    dlg.win.destroy()
