import pandas as pd
import threading
from typing import Optional, Dict, Any, Callable, List

class ObjectDataStore:
    def __init__(self, repository):
        self.app = repository
        self.lock = threading.RLock()

    def _get_db_dict_cache(self, db, oid=None):
        """Helper to get dict cache from db (handles both dict and DataFrame db structures)."""
        if hasattr(self.app, "_get_db_dict_cache"):
            return self.app._get_db_dict_cache(db, oid)

        if isinstance(db, dict):
            if "dict_cache" not in db:
                db["dict_cache"] = {}
            cache = db["dict_cache"]
            if oid is None:
                return cache

            if oid not in cache:
                oid_cache = {}
                reg_by_id = db.get("reg_by_id")
                if reg_by_id is None and "df" in db:
                    raw_df = db["df"]
                    if raw_df is not None:
                        if raw_df.index.name != 'catalogNumber' and 'catalogNumber' in raw_df.columns:
                            try:
                                reg_by_id = raw_df.set_index('catalogNumber', drop=False)
                            except Exception:
                                reg_by_id = raw_df
                        else:
                            reg_by_id = raw_df

                if reg_by_id is not None and oid in reg_by_id.index:
                    rows = reg_by_id.loc[oid]
                    if isinstance(rows, pd.DataFrame):
                        for row in rows.itertuples(index=False, name=None):
                            for col, val in zip(rows.columns, row):
                                if pd.notna(val):
                                    val_str = str(val).strip()
                                    if val_str and val_str != "nan":
                                        if col not in oid_cache:
                                            oid_cache[col] = []
                                        if val_str not in oid_cache[col]:
                                            oid_cache[col].append(val_str)
                    elif isinstance(rows, pd.Series):
                        for col, val in rows.items():
                            if pd.notna(val):
                                val_str = str(val).strip()
                                if val_str and val_str != "nan":
                                    if col not in oid_cache:
                                        oid_cache[col] = []
                                    if val_str not in oid_cache[col]:
                                        oid_cache[col].append(val_str)
                cache[oid] = oid_cache
            return cache

        # Fallback if db is directly a DataFrame
        if not hasattr(db, "_dict_cache"):
            db._dict_cache = {}
            if db.index.name != 'catalogNumber' and 'catalogNumber' in db.columns:
                try:
                    df_indexed = db.set_index('catalogNumber', drop=False)
                except Exception:
                    df_indexed = db
            else:
                df_indexed = db
            # Pre-group by index to drastically speed up lookups
            db._grouped_cache = df_indexed.groupby(level=0)

        if hasattr(db, "_grouped_cache"):
            try:
                if oid not in db._grouped_cache.groups:
                    return {}
                group = db._grouped_cache.get_group(oid)
                d = {}
                for col in group.columns:
                    vals = group[col].dropna().unique().tolist()
                    if vals:
                        d[col] = vals
                db._dict_cache[oid] = d
                return db._dict_cache
            except KeyError:
                return {}

        return {}


    def get_object_payload(self, oid: str, reg_columns=None) -> Dict[str, Any]:
        with self.lock:
            # Type coerce OID if needed (int fallback)
            if hasattr(self.app, "df_reg") and self.app.df_reg is not None and oid not in self.app.df_reg.index:
                try:
                    if str(oid).isdigit():
                        int_oid = int(oid)
                        if int_oid in self.app.df_reg.index:
                            oid = int_oid
                except Exception:
                    pass

            payload = {"oid": oid}

            # Gather historical suggestions
            current_object_suggestions = {}
            if oid and hasattr(self.app, 'historical_dbs') and self.app.historical_dbs:
                for db in self.app.historical_dbs:
                    dict_cache = self._get_db_dict_cache(db, oid)
                    oid_data = dict_cache.get(oid, {})
                    for field, field_vals in oid_data.items():
                        if reg_columns is None or field in reg_columns:
                            vals = current_object_suggestions.setdefault(field, [])
                            for v in field_vals:
                                if v not in vals:
                                    vals.append(v)
            payload["current_object_suggestions"] = current_object_suggestions

            # Check if reg_dict / obs_dict exist on the repo
            reg = None
            if hasattr(self.app, "_get_reg_dict"):
                reg_dict = self.app._get_reg_dict()
                reg = reg_dict.get(oid)
            elif hasattr(self.app, "df_reg") and self.app.df_reg is not None:
                if oid in self.app.df_reg.index:
                    reg = self.app.df_reg.loc[oid].to_dict()

            obs = None
            if hasattr(self.app, "_get_obs_dict"):
                obs_dict = self.app._get_obs_dict()
                obs = obs_dict.get(oid)
            elif hasattr(self.app, "df_obs") and self.app.df_obs is not None:
                if oid in self.app.df_obs.index:
                    obs = self.app.df_obs.loc[oid].to_dict()

            if reg is None:
                try:
                    if hasattr(self.app, "df_reg") and self.app.df_reg is not None:
                        reg = self.app.df_reg.loc[oid]
                        if isinstance(reg, pd.DataFrame):
                            reg = reg.iloc[0].to_dict()
                        else:
                            reg = reg.to_dict()
                except Exception:
                    reg = {}

            if obs is None:
                try:
                    if hasattr(self.app, "df_obs") and self.app.df_obs is not None:
                        obs = self.app.df_obs.loc[oid]
                        if isinstance(obs, pd.DataFrame):
                            obs = obs.iloc[0].to_dict()
                        else:
                            obs = obs.to_dict()
                except Exception:
                    obs = {}

            payload["reg"] = reg or {}
            payload["obs"] = obs or {}

            # Handle object specific defaults/fallbacks like Image_Missing, is_completed
            # We skip this for now, UI can handle these mappings or it's extracted from obs

            return payload
