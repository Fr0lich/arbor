import pytest
import tkinter as tk
from ui.filter_dialog import FilterDialogController


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        root.destroy()
    except Exception as e:
        pytest.skip(f"Tkinter display not available: {e}")


class DummyApp:
    def __init__(self):
        self.config = {
            "ui_sections": {
                "location": [
                    {"name": "Room", "type": "text"},
                    {"name": "Status", "type": "choice", "choices": ["Active", "Archived"]},
                ]
            }
        }
        self.df_reg = None
        self.active_object_ids = []


class DummyUI:
    def __init__(self, root):
        self.root = root
        self.app = DummyApp()
        self.filter_window = None
        self.problem_columns = ["Genus_Problem", "Species_Problem", "Image_Problem"]
        self.filter_vars = {
            "Reviewed": tk.BooleanVar(),
            "Not_Reviewed": tk.BooleanVar(),
            "Reviewed_With_Problem": tk.BooleanVar(),
            "Problem_With_History": tk.BooleanVar(),
            "Has_History": tk.BooleanVar(),
            "Comment_Empty": tk.BooleanVar(),
            "Comment_Not_Empty": tk.BooleanVar(),
            "Extra_Empty": tk.BooleanVar(),
            "Extra_Not_Empty": tk.BooleanVar(),
            "Genus_Problem": tk.StringVar(value="Ignore"),
            "Species_Problem": tk.StringVar(value="Ignore"),
            "Image_Problem": tk.BooleanVar(),
            "Any_Problem": tk.StringVar(value="Ignore"),
            "Historical_Data": tk.StringVar(value="Ignore"),
            "Images_Missing": tk.BooleanVar(),
            "Has_Images": tk.BooleanVar(),
        }
        self.filter_location_vars = {}
        self.filter_tabs = {}
        self.filter_tab_buttons = {}

    def update_filter_button_text(self):
        pass

    def apply_filter(self, win=None):
        pass

    def refresh_list(self):
        pass

    def update_object_count(self):
        pass


def test_open_filter_menu(tk_root):
    ui = DummyUI(tk_root)
    # Should open without raising NameError or other exceptions
    FilterDialogController.open_filter_menu(ui)
    assert ui.filter_window is not None
    assert ui.filter_window.winfo_exists()
    assert "status" in ui.filter_tabs
    assert "problems" in ui.filter_tabs
    assert "location" in ui.filter_tabs
    assert "images" in ui.filter_tabs

    # Clean up
    ui.filter_window.destroy()
