import pandas as pd
from utils import sanitize_df_for_excel

def test_sanitize_df_timezone():
    df = pd.DataFrame({"a": [pd.Timestamp("2020-01-01", tz="UTC")]})
    df_safe = sanitize_df_for_excel(df)
    assert pd.api.types.is_datetime64_any_dtype(df_safe["a"])
    assert df_safe["a"].dt.tz is None

def test_sanitize_df_illegal_chars():
    df = pd.DataFrame({"a": ["hello\x00world"]})
    df_safe = sanitize_df_for_excel(df)
    assert df_safe["a"].iloc[0] == "helloworld"

def test_sanitize_df_formula_injection():
    df = pd.DataFrame({"a": ["=1+1", "-2+2", "cmd|foo", "test"]})
    df_safe = sanitize_df_for_excel(df)
    assert df_safe["a"].iloc[0] == "'=1+1"
    assert df_safe["a"].iloc[1] == "'-2+2"
    assert df_safe["a"].iloc[2] == "'cmd|foo"
    assert df_safe["a"].iloc[3] == "test"
