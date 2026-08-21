import pytest
import utils
from unittest.mock import patch, MagicMock
from ui.main_window import ObjectProgramUI
from models import AppState
import tkinter as tk
import pandas as pd

def test_gbif_taxonomy_util_not_found():
    res = utils.check_gbif_taxonomy("", "")
    assert res['status'] == 'not_found'

@patch('utils.requests.get')
def test_gbif_taxonomy_util_accepted(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'status': 'ACCEPTED'}
    mock_get.return_value = mock_resp

    res = utils.check_gbif_taxonomy("Quercus", "robur")
    assert res['status'] == 'accepted'

@patch('utils.requests.get')
def test_gbif_taxonomy_util_synonym(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'status': 'SYNONYM',
        'species': 'Felis catus',
        'genus': 'Felis'
    }
    mock_get.return_value = mock_resp

    res = utils.check_gbif_taxonomy("Felis", "domesticus")
    assert res['status'] == 'synonym'
    assert res['accepted_name'] == 'Felis catus'
    assert res['accepted_genus'] == 'Felis'
    assert res['accepted_species'] == 'catus'

def test_verify_taxonomy_gbif_no_object(mocker):
    app = AppState()
    root = tk.Tk()
    mw = ObjectProgramUI(root, app)

    mock_showinfo = mocker.patch("ui.main_window.messagebox.showinfo")
    mw.verify_taxonomy_gbif()
    mock_showinfo.assert_called_with("GBIF Taxonomy", "No object loaded.")

def test_verify_taxonomy_gbif_empty_fields(mocker):
    app = AppState()
    app.current_object_id = "OBJ1"
    root = tk.Tk()
    mw = ObjectProgramUI(root, app)
    mw.reg_vars = {"Genus": tk.StringVar(value=""), "Species": tk.StringVar(value="")}

    mock_showinfo = mocker.patch("ui.main_window.messagebox.showinfo")
    mw.verify_taxonomy_gbif()
    mock_showinfo.assert_called_with("GBIF Taxonomy", "Genus and Species are empty.")
