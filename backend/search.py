import pandas as pd

class SearchEngine:
    def __init__(self):
        self._search_index_cache = None

    def invalidate_search_index(self):
        """Call after any data change that affects Genus, Species, or ObjectID."""
        self._search_index_cache = None

    def get_search_index(self, df_reg, reg_dict):
        """
        Return the search index {oid: token_dict}.
        During startup the index is pre-built by _precompute_startup_caches() so this
        method just returns the cached result.  After a data-changing operation that
        calls invalidate_search_index(), the cache is rebuilt lazily here covering
        ALL registration columns (not just Genus + Species) for maximum recall.
        """
        if self._search_index_cache is not None:
            return self._search_index_cache

        index = {}

        # If we have a dataframe but no dict, build the index using vectorized Pandas methods
        if df_reg is not None and not df_reg.empty and not reg_dict:
            # Vectorized string conversion and filling NA
            df_str = df_reg.fillna("").astype(str)

            # Helper to safely extract columns or return empty strings
            def get_col(col):
                return df_str[col].str.strip().str.lower() if col in df_str.columns else pd.Series("", index=df_str.index)

            genus_s = get_col("Genus")
            species_s = get_col("Species")
            family_s = get_col("Family")

            genus_species_s = genus_s + " " + species_s
            genus_species_s = genus_species_s.str.strip()

            # Replace 'nan', 'none'
            df_str = df_str.replace(["nan", "none", "NaN", "None"], "")

            # Build the "all" column by joining all columns per row + index
            index_str = df_str.index.astype(str).str.lower()
            all_s = df_str.apply(lambda row: " ".join(v.strip().lower() for v in row if v.strip() and v.strip().lower() not in ("nan", "none")), axis=1)
            all_s = index_str + " " + all_s

            # Construct the dict efficiently bypassing pandas .iloc overhead
            oids = df_str.index.values
            ids_arr = index_str.values
            gs_arr = genus_species_s.values
            fam_arr = family_s.values
            all_arr = all_s.values

            for oid, id_val, gs, fam, all_text in zip(oids, ids_arr, gs_arr, fam_arr, all_arr):
                index[oid] = {
                    "id": id_val,
                    "genus_species": gs,
                    "family": fam,
                    "all": all_text
                }

            self._search_index_cache = index
            return index

        # Fallback to dictionary iteration if reg_dict is provided
        if reg_dict:
            items_iter = reg_dict.items()
        else:
            return index

        for oid, reg_row in items_iter:
            id_str = str(oid).lower()

            genus = reg_row.get("Genus", "")
            species = reg_row.get("Species", "")

            genus_str = str(genus).strip().lower() if genus and not pd.isna(genus) else ""
            species_str = str(species).strip().lower() if species and not pd.isna(species) else ""
            genus_species_str = f"{genus_str} {species_str}".strip() if (genus_str or species_str) else ""

            family_val = reg_row.get("Family", "")
            family = str(family_val).strip().lower() if family_val and not pd.isna(family_val) else ""

            parts = [id_str]
            for col_name, val in reg_row.items():
                if val and not pd.isna(val):
                    val_str = str(val).strip().lower()
                    if val_str and val_str not in ("nan", "none"):
                        parts.append(val_str)

            index[oid] = {
                "id": id_str,
                "genus_species": genus_species_str,
                "family": family,
                "all": " ".join(parts)
            }

        self._search_index_cache = index
        return index

    def apply_search(self, query, index):
        """
        Return list of matching object IDs based on search query.
        """
        query = query.strip().lower()
        if not query:
            return None # Indicate no match / return all

        p1 = []
        p2 = []
        p3 = []
        p4 = []
        p5 = []

        for oid, tokens_dict in index.items():
            if query not in tokens_dict["all"]:
                continue

            if query == tokens_dict["id"]:
                p1.append(oid)
            elif query in tokens_dict["id"]:
                p2.append(oid)
            elif query in tokens_dict["genus_species"]:
                p3.append(oid)
            elif query in tokens_dict["family"]:
                p4.append(oid)
            else:
                p5.append(oid)

        return p1 + p2 + p3 + p4 + p5
