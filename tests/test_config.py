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
        result = config.load_prefs()
        assert result == {}
        assert config._prefs_cache == {}

def test_load_prefs_file_not_exists():
    """Test loading preferences when the file does not exist."""
    with patch("os.path.exists", return_value=False):
        result = config.load_prefs()
        assert result == {}
        assert config._prefs_cache == {}
