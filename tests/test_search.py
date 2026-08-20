import pandas as pd
from backend.search import SearchEngine

def test_search_engine_caching():
    engine = SearchEngine()

    # Mock data
    df_reg = pd.DataFrame({"Genus": ["Quercus"], "Species": ["alba"]}, index=["obj_1"])
    reg_dict = {"obj_1": {"Genus": "Quercus", "Species": "alba", "Family": "Fagaceae"}}

    # Initially cache should be None
    assert engine._search_index_cache is None

    # get_search_index should build and populate cache
    index1 = engine.get_search_index(df_reg, reg_dict)
    assert engine._search_index_cache is not None
    assert index1 == engine._search_index_cache
    assert "obj_1" in index1

    # subsequent call should return same cache
    index2 = engine.get_search_index(None, None) # should not error out since it uses cache
    assert index1 is index2

    # invalidate cache
    engine.invalidate_search_index()
    assert engine._search_index_cache is None

    # should return empty dict if df_reg is None
    index3 = engine.get_search_index(None, None)
    assert index3 == {}

def test_apply_search():
    engine = SearchEngine()

    index = {
        "obj_1": {
            "id": "obj_1",
            "genus_species": "quercus alba",
            "family": "fagaceae",
            "all": "obj_1 quercus alba fagaceae"
        },
        "obj_2": {
            "id": "obj_2",
            "genus_species": "acer saccharum",
            "family": "sapindaceae",
            "all": "obj_2 acer saccharum sapindaceae"
        }
    }

    # empty query returns None
    assert engine.apply_search("", index) is None

    # exact ID match (Priority 1)
    res = engine.apply_search("obj_1", index)
    assert res == ["obj_1"]

    # partial ID match (Priority 2)
    res = engine.apply_search("obj", index)
    assert res == ["obj_1", "obj_2"] # both match

    # genus_species match (Priority 3)
    res = engine.apply_search("quercus", index)
    assert res == ["obj_1"]

    # family match (Priority 4)
    res = engine.apply_search("sapindaceae", index)
    assert res == ["obj_2"]

    # all match (Priority 5) - fallback (though in this small data, it matches other categories)
    # Let's add something to "all" that isn't in others
    index["obj_3"] = {
        "id": "obj_3",
        "genus_species": "test test",
        "family": "test_family",
        "all": "obj_3 test test test_family random_notes"
    }
    res = engine.apply_search("random_notes", index)
    assert res == ["obj_3"]

    # No match
    res = engine.apply_search("nothing", index)
    assert res == []
