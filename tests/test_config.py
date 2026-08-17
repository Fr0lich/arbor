import pytest
from unittest.mock import patch, mock_open
import config

@pytest.fixture(autouse=True)
def reset_prefs_cache():
    """Reset the _prefs_cache before and after each test."""
    original_cache = config._prefs_cache
    config._prefs_cache = None
    yield
    config._prefs_cache = original_cache

def test_load_prefs_cache_hit():
    """Test that if _prefs_cache is already populated, it is returned directly."""
    config._prefs_cache = {"theme": "dark"}
    with patch("os.path.exists") as mock_exists:
        result = config.load_prefs()
        assert result == {"theme": "dark"}
        mock_exists.assert_not_called()

def test_load_prefs_valid_file():
    """Test loading preferences from a valid JSON file."""
    mock_json = '{"recent_files": []}'
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=mock_json)):
        result = config.load_prefs()
        assert result == {"recent_files": []}
        assert config._prefs_cache == {"recent_files": []}

def test_load_prefs_invalid_file():
    """Test loading preferences when the file contains invalid JSON."""
    mock_json = '{"recent_files": ' # invalid JSON
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=mock_json)):
        import pytest
        from exceptions import UIConfigurationError
        result = config.load_prefs()
    assert result == {}
    assert config._prefs_cache == {}



def test_add_recent_file_truncates_to_8():
    """Test that adding a 9th file truncates the list to 8 items, keeping newest."""
    existing_files = [{"path": f"file{i}.json", "modified": "2023-01-01"} for i in range(1, 9)]
    mock_prefs = {"recent_files": existing_files}

    with patch("config.load_prefs", return_value=mock_prefs), \
         patch("config.save_prefs") as mock_save, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getmtime", return_value=1672531200):

        config.add_recent_file("new_file.json")

        mock_save.assert_called_once()
        saved_prefs = mock_save.call_args[0][0]
        recent = saved_prefs["recent_files"]

        assert len(recent) == 8
        assert recent[0]["path"] == "new_file.json"
        assert isinstance(recent[0]["modified"], str)
        assert len(recent[0]["modified"]) > 0
        assert recent[-1]["path"] == "file7.json" # file8.json is truncated


def test_add_recent_file_deduplicates():
    """Test that adding an existing file moves it to the front without duplicating."""
    existing_files = [
        {"path": "file1.json", "modified": "old"},
        {"path": "file2.json", "modified": "old"}
    ]
    mock_prefs = {"recent_files": existing_files}

    with patch("config.load_prefs", return_value=mock_prefs), \
         patch("config.save_prefs") as mock_save, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getmtime", return_value=1672531200):

        config.add_recent_file("file2.json")

        mock_save.assert_called_once()
        saved_prefs = mock_save.call_args[0][0]
        recent = saved_prefs["recent_files"]

        assert len(recent) == 2
        assert recent[0]["path"] == "file2.json"
        assert isinstance(recent[0]["modified"], str)
        assert len(recent[0]["modified"]) > 0
        assert recent[1]["path"] == "file1.json"


def test_add_recent_file_invalid_path():
    """Test that adding an invalid or None path does nothing."""
    with patch("config.load_prefs") as mock_load, \
         patch("config.save_prefs") as mock_save, \
         patch("os.path.exists", return_value=False):

        config.add_recent_file("nonexistent.json")
        config.add_recent_file(None)
        config.add_recent_file("")

        mock_load.assert_not_called()
        mock_save.assert_not_called()


def test_add_recent_file_mtime_exception():
    """Test that if getmtime fails, modified date is set to empty string."""
    mock_prefs = {"recent_files": []}

    with patch("config.load_prefs", return_value=mock_prefs), \
         patch("config.save_prefs") as mock_save, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getmtime", side_effect=OSError("Permission denied")):

        config.add_recent_file("error_file.json")

        mock_save.assert_called_once()
        saved_prefs = mock_save.call_args[0][0]
        recent = saved_prefs["recent_files"]

        assert len(recent) == 1
        assert recent[0]["path"] == "error_file.json"
        assert recent[0]["modified"] == ""

def test_load_prefs_file_not_exists():
    """Test loading preferences when the file does not exist."""
    with patch("os.path.exists", return_value=False):
        result = config.load_prefs()
        assert result == {}
    assert config._prefs_cache == {}
