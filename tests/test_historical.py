import pytest
import pandas as pd
from collections import OrderedDict
from ui.historical_suggestions import HistoricalSuggestionsMixin

class DummyApp:
    def __init__(self):
        self.current_object_id = None
        self.historical_dbs = []

class DummyVar:
    def __init__(self, value=False):
        self._val = value
    def get(self):
        return self._val

class DummyUI(HistoricalSuggestionsMixin):
    def __init__(self):
        self.app = DummyApp()
        self.show_all_history_var = DummyVar(False)
        self.problem_to_field = {
            "Genus_Problem": "Genus",
            "Species_Problem": "Species"
        }
        self.problem_vars = {
            "Genus_Problem": DummyVar(False),
            "Species_Problem": DummyVar(False)
        }
        self.reg_by_id = pd.DataFrame()
        self._history_cache = OrderedDict()

    def is_unknown(self, val):
        val = str(val).lower().strip()
        return val in ("unknown", "?", "none", "")

    def is_problem_active(self, oid, prob_col):
        if prob_col in self.problem_vars:
            return self.problem_vars[prob_col].get()
        return False

    def is_word_ignored(self, val):
        return str(val).lower() in ("ignored_word",)

def test_get_db_dict_cache():
    ui = DummyUI()

    # Test with empty db
    db = {}
    cache = ui._get_db_dict_cache(db)
    assert cache == {}

    # Test with oid not in reg_by_id
    db = {"reg_by_id": pd.DataFrame({"Genus": ["A"]}, index=["2"])}
    cache = ui._get_db_dict_cache(db, oid="1")
    assert "1" in cache
    assert cache["1"] == {}

    # Test with single row (Series)
    db = {"reg_by_id": pd.DataFrame({"Genus": ["Rosa"]}, index=["1"])}
    cache = ui._get_db_dict_cache(db, oid="1")
    assert cache["1"]["Genus"] == ["Rosa"]

    # Test with duplicate rows (DataFrame)
    db = {"reg_by_id": pd.DataFrame({"Genus": ["Rosa", "Rosa", "Rubus"]}, index=["1", "1", "1"])}
    db["dict_cache"] = {} # clear cache to re-evaluate
    cache = ui._get_db_dict_cache(db, oid="1")
    assert cache["1"]["Genus"] == ["Rosa", "Rubus"]

def test_collect_historical_suggestions_no_db():
    ui = DummyUI()
    suggestions = ui.collect_historical_suggestions(oid="1")
    assert suggestions == {}

def test_collect_historical_suggestions_active_problems():
    ui = DummyUI()

    # Setup current data
    ui.reg_by_id = pd.DataFrame({"Genus": ["CurrentGenus"], "Species": ["CurrentSpecies"]}, index=["1"])
    ui.problem_vars["Genus_Problem"] = DummyVar(True)
    ui.problem_vars["Species_Problem"] = DummyVar(False)

    # Setup historical dbs
    df1 = pd.DataFrame({"Genus": ["OldGenus1"], "Species": ["OldSpecies1"]}, index=["1"])
    df2 = pd.DataFrame({"Genus": ["OldGenus2"], "Species": ["OldSpecies2"]}, index=["1"])

    ui.app.historical_dbs = [
        {"name": "DB1", "reg_by_id": df1},
        {"name": "DB2", "reg_by_id": df2}
    ]

    suggestions = ui.collect_historical_suggestions(oid="1")

    # Since Genus is active problem, it should collect suggestions
    assert "Genus" in suggestions
    assert suggestions["Genus"]["OldGenus1"] == ["DB1"]
    assert suggestions["Genus"]["OldGenus2"] == ["DB2"]

    # Species is not active problem and not unknown, shouldn't be collected
    assert "Species" not in suggestions

def test_collect_historical_suggestions_unknown_values():
    ui = DummyUI()

    # Setup current data with unknown value
    ui.reg_by_id = pd.DataFrame({"Genus": ["?"], "Species": ["CurrentSpecies"]}, index=["1"])
    # No active problems
    ui.problem_vars["Genus_Problem"] = DummyVar(False)
    ui.problem_vars["Species_Problem"] = DummyVar(False)

    # Setup historical dbs
    df1 = pd.DataFrame({"Genus": ["OldGenus1"], "Species": ["OldSpecies1"]}, index=["1"])

    ui.app.historical_dbs = [
        {"name": "DB1", "reg_by_id": df1}
    ]

    suggestions = ui.collect_historical_suggestions(oid="1")

    # Genus is unknown, should be collected
    assert "Genus" in suggestions
    assert suggestions["Genus"]["OldGenus1"] == ["DB1"]

    # Species is known and no problem, shouldn't be collected
    assert "Species" not in suggestions

def test_collect_historical_suggestions_show_all():
    ui = DummyUI()

    # Setup current data
    ui.reg_by_id = pd.DataFrame({"Genus": ["CurrentGenus"], "Species": ["CurrentSpecies"], "OtherField": ["Val"]}, index=["1"])

    # No active problems, all values known
    ui.problem_vars["Genus_Problem"] = DummyVar(False)
    ui.problem_vars["Species_Problem"] = DummyVar(False)

    # Setup historical dbs
    df1 = pd.DataFrame({"Genus": ["OldGenus1"], "Species": ["OldSpecies1"], "OtherField": ["OldVal1"]}, index=["1"])

    ui.app.historical_dbs = [
        {"name": "DB1", "reg_by_id": df1}
    ]

    # Show all is False -> no suggestions
    suggestions = ui.collect_historical_suggestions(oid="1", show_all_override=False)
    assert suggestions == {}

    # Clear cache
    ui._history_cache.clear()

    # Show all is True -> all fields collected
    suggestions = ui.collect_historical_suggestions(oid="1", show_all_override=True)
    assert "Genus" in suggestions
    assert "Species" in suggestions
    assert "OtherField" in suggestions

    assert suggestions["OtherField"]["OldVal1"] == ["DB1"]

def test_collect_historical_suggestions_ignored_words():
    ui = DummyUI()

    # Setup current data
    ui.reg_by_id = pd.DataFrame({"Genus": ["CurrentGenus"]}, index=["1"])
    ui.problem_vars["Genus_Problem"] = DummyVar(True)

    # Setup historical dbs with ignored word
    df1 = pd.DataFrame({"Genus": ["ignored_word"]}, index=["1"])
    df2 = pd.DataFrame({"Genus": ["valid_word"]}, index=["1"])

    ui.app.historical_dbs = [
        {"name": "DB1", "reg_by_id": df1},
        {"name": "DB2", "reg_by_id": df2}
    ]

    suggestions = ui.collect_historical_suggestions(oid="1")

    assert "Genus" in suggestions
    assert "ignored_word" not in suggestions["Genus"]
    assert "valid_word" in suggestions["Genus"]
    assert suggestions["Genus"]["valid_word"] == ["DB2"]
