import pandas as pd
from repository import _normalise_dataframes

def test_normalise_dataframes_checkbox_default():
    config = {
        "ui_sections": {
            "location": [
                {"name": "Building", "type": "choice"},
                {"name": "Loaned out", "type": "checkbox"},
                {"name": "Loaned out date", "type": "text"}
            ],
            "problems": [],
            "registration": [{"name": "Genus"}]
        }
    }

    df_reg = pd.DataFrame({"ObjectID": ["1", "2", "3", "4", "5"]})
    df_obs = pd.DataFrame({
        "ObjectID": ["1", "2", "3", "4", "5"],
        "Loaned out": ["", "True", False, True, None]
    })

    df_reg, df_obs = _normalise_dataframes(df_reg, df_obs, config)

    # Check that "Loaned out" defaults to "False" properly for missing/empty values
    assert df_obs.loc[df_obs["ObjectID"] == "1", "Loaned out"].iloc[0] == "False"
    assert df_obs.loc[df_obs["ObjectID"] == "2", "Loaned out"].iloc[0] == "True"
    assert df_obs.loc[df_obs["ObjectID"] == "3", "Loaned out"].iloc[0] == "False"
    assert df_obs.loc[df_obs["ObjectID"] == "4", "Loaned out"].iloc[0] == "True"
    assert df_obs.loc[df_obs["ObjectID"] == "5", "Loaned out"].iloc[0] == "False"
