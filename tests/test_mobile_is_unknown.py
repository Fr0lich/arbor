import pytest
import pandas as pd
from backend.mobile_server import is_unknown

@pytest.mark.parametrize("value, expected", [
    # Null / Missing equivalents
    (None, False),
    (pd.NA, False),
    (float('nan'), False),

    # Empty string cases
    ("", False),
    ("   ", False),

    # Legacy tokens (which are the only ones strictly listed in the prompt's version)
    ("unknown", True),
    ("UNKNOWN", True),
    (" ukjent ", True),
    ("?", True),
    ("-", True),
    ("nan", True),

    # Valid data (Should be False)
    ("valid_data", False),
    (123, False),
    ("O-V-12345", False)
])
def test_is_unknown(value, expected):
    """
    Test the `is_unknown` function from mobile_server.py.
    Verifies that various forms of 'unknown' values (nulls, empty strings,
    legacy tokens, and valid data) are correctly identified.
    """
    assert is_unknown(value) == expected
