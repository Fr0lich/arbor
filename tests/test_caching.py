import cachetools
import pytest
from unittest.mock import MagicMock
from ui.historical_suggestions import HistoricalSuggestionsMixin


class DummyHost(HistoricalSuggestionsMixin):
    def __init__(self):
        self._history_lock = None
        self._history_cache = cachetools.LRUCache(maxsize=3)
        self.app = MagicMock()
        self.app.historical_dbs = []


def test_lru_cache_eviction_bounds():
    cache = cachetools.LRUCache(maxsize=3)
    cache[("1", False)] = {"Field": "Val1"}
    cache[("2", False)] = {"Field": "Val2"}
    cache[("3", False)] = {"Field": "Val3"}
    assert len(cache) == 3

    # Adding 4th element should evict oldest ("1", False)
    cache[("4", False)] = {"Field": "Val4"}
    assert len(cache) == 3
    assert ("1", False) not in cache
    assert ("4", False) in cache


def test_invalidate_history_cache_removes_oid_variants():
    host = DummyHost()
    host._history_cache = cachetools.LRUCache(maxsize=10)
    host._history_cache[("101", True)] = {"data": 1}
    host._history_cache[("101", False)] = {"data": 2}
    host._history_cache[(101, True)] = {"data": 3}
    host._history_cache[("202", False)] = {"data": 4}

    assert len(host._history_cache) == 4

    # Invalidate oid 101
    host.invalidate_history_cache("101")
    assert ("101", True) not in host._history_cache
    assert ("101", False) not in host._history_cache
    assert (101, True) not in host._history_cache
    assert ("202", False) in host._history_cache
    assert len(host._history_cache) == 1

    # Invalidate all
    host.invalidate_history_cache(None)
    assert len(host._history_cache) == 0


def test_finish_load_books_cache_initialization():
    from unittest.mock import patch
    host = DummyHost()
    host.root = MagicMock()
    host.app = MagicMock()
    host.system_status = MagicMock()
    host.image_scan_progress = MagicMock()
    host._hide_progress = MagicMock()
    host._history_cache = None

    with patch("tkinter.messagebox.showwarning"):
        host._finish_load_books([])

    assert host._history_cache is not None
    assert isinstance(host._history_cache, cachetools.LRUCache)
