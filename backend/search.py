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
        if reg_dict:
            items_iter = reg_dict.items()
        elif df_reg is not None and not df_reg.empty:
            items_iter = df_reg.to_dict(orient="index").items()
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

        matched_with_priority = []

        for oid, tokens_dict in index.items():
            if query not in tokens_dict["all"]:
                continue

            if query == tokens_dict["id"]:
                priority = 1
            elif query in tokens_dict["id"]:
                priority = 2
            elif query in tokens_dict["genus_species"]:
                priority = 3
            elif query in tokens_dict["family"]:
                priority = 4
            else:
                priority = 5

            matched_with_priority.append((priority, oid))

        matched_with_priority.sort(key=lambda x: x[0])
        return [oid for priority, oid in matched_with_priority]
