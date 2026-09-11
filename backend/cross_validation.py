from typing import List, Dict, Any, Optional
import pandas as pd
from backend.gbif import is_author_equivalent, is_classification_equivalent, check_gbif


AUTHOR_ALIASES = {
    "l": ["linnaeus", "linne", "c linnaeus", "c von linne"],
    "dc": ["de candolle", "candolle", "a p de candolle", "ap de candolle"],
    "hook": ["hooker", "w j hooker", "wj hooker"],
    "hook f": ["hooker f", "j d hooker", "jd hooker", "hookf"],
    "benth": ["bentham", "g bentham"],
    "fisch": ["fischer", "f e l fischer"],
    "mey": ["meyer", "c a meyer", "ca meyer"],
    "roxb": ["roxburgh", "w roxburgh"],
    "wall": ["wallich", "n wallich"],
    "ehrh": ["ehrhart", "f ehrhart"],
    "pers": ["persoon", "c h persoon"],
    "willd": ["willdenow", "c l willdenow"],
    "tourn": ["tournefort", "j p de tournefort"],
    "juss": ["jussieu", "a l de jussieu"],
    "r br": ["robert brown", "r brown", "brown", "rbr"],
    "lam": ["lamarck", "j b lamarck"],
    "schrad": ["schrader", "h a schrader"],
    "gaertn": ["gaertner", "j gaertner"],
}


def is_author_corroborated(a1: Any, a2: Any) -> bool:
    """
    Check if two author strings refer to the same author, taking into account
    IPNI standard abbreviations, full names, spacing, and punctuation.
    """
    s1 = str(a1 or "").strip()
    s2 = str(a2 or "").strip()
    if not s1 and not s2:
        return True
    if not s1 or not s2:
        return False
    if is_author_equivalent(s1, s2):
        return True

    def norm(s: str) -> str:
        return s.replace(".", "").replace(",", "").replace("(", "").replace(")", "").replace("  ", " ").strip().lower()

    n1 = norm(s1)
    n2 = norm(s2)
    if n1 == n2:
        return True

    for abbr, full_list in AUTHOR_ALIASES.items():
        if (n1 == abbr and n2 in full_list) or (n2 == abbr and n1 in full_list):
            return True
        if n1 in full_list and n2 in full_list:
            return True

    return False


def find_book_matches_for_gbif(app_state: Any, oid: str, field: str, proposed_val: str) -> List[str]:
    """
    Check in-memory historical books for matches against a GBIF proposed value for a given specimen.
    Returns a list of matching book/sheet names, or an empty list if none match.
    """
    if not app_state or not getattr(app_state, "historical_dbs", None):
        return []

    p_val_str = str(proposed_val or "").strip()
    if not p_val_str or p_val_str.lower() == "nan":
        return []

    matching_books = []
    oid_str = str(oid).strip()

    for db in app_state.historical_dbs:
        db_name = db.get("name", "Historical Book")
        dict_cache = db.get("dict_cache", {})

        # 1. Fast cache lookup
        oid_data = dict_cache.get(oid_str)
        if oid_data is None and oid_str.isdigit():
            oid_data = dict_cache.get(int(oid_str))

        # 2. Fallback to reg_by_id or df_reg if not yet in dict_cache
        if oid_data is None:
            reg_by_id = db.get("reg_by_id")
            if reg_by_id is not None and hasattr(reg_by_id, "index"):
                target_idx = None
                if oid_str in reg_by_id.index:
                    target_idx = oid_str
                elif oid_str.isdigit() and int(oid_str) in reg_by_id.index:
                    target_idx = int(oid_str)

                if target_idx is not None:
                    row = reg_by_id.loc[target_idx]
                    raw_vals = []
                    if isinstance(row, pd.DataFrame):
                        for col in row.columns:
                            if col.lower() == field.lower():
                                raw_vals.extend([str(v).strip() for v in row[col].dropna().values if str(v).strip() and str(v).strip() != "nan"])
                    elif isinstance(row, pd.Series):
                        for col, v in row.items():
                            if col.lower() == field.lower():
                                v_str = str(v).strip()
                                if v_str and v_str != "nan":
                                    raw_vals.append(v_str)
                else:
                    raw_vals = []
            else:
                raw_vals = []
        else:
            raw_vals = []
            for col, v_list in oid_data.items():
                if col.lower() == field.lower():
                    raw_vals.extend(v_list)

        # Check equivalence
        for v in raw_vals:
            v_str = str(v).strip()
            if not v_str or v_str.lower() == "nan":
                continue

            if field.lower() == "author":
                if is_author_corroborated(v_str, p_val_str):
                    if db_name not in matching_books:
                        matching_books.append(db_name)
                    break
            elif field.lower() == "family":
                if v_str.lower() == p_val_str.lower():
                    if db_name not in matching_books:
                        matching_books.append(db_name)
                    break
            else:
                if v_str.lower() == p_val_str.lower():
                    if db_name not in matching_books:
                        matching_books.append(db_name)
                    break

    return matching_books


def check_gbif_corroboration_for_historical(app_state: Any, oid: str, field: str, hist_val: str, genus: Optional[str] = None, species: Optional[str] = None) -> bool:
    """
    Check whether GBIF confirms a given historical suggestion value for a specimen.
    """
    h_val = str(hist_val or "").strip()
    if not h_val or h_val.lower() == "nan" or h_val == "(No data found)":
        return False

    # 1. If genus/species not provided, retrieve from df_reg
    if not genus and app_state and getattr(app_state, "df_reg", None) is not None:
        reg_oid = oid
        if reg_oid not in app_state.df_reg.index and str(oid).isdigit() and int(oid) in app_state.df_reg.index:
            reg_oid = int(oid)

        if reg_oid in app_state.df_reg.index:
            genus = str(app_state.df_reg.at[reg_oid, "Genus"] if "Genus" in app_state.df_reg.columns else "").strip()
            species = str(app_state.df_reg.at[reg_oid, "Species"] if "Species" in app_state.df_reg.columns else "").strip()

    if not genus:
        return False

    # Check GBIF
    gbif_data = check_gbif(genus, species or "")
    if not gbif_data or "error" in gbif_data:
        return False

    field_lower = field.lower()
    if field_lower == "author":
        gbif_author = str(gbif_data.get("author", "") or "").strip()
        return is_author_corroborated(h_val, gbif_author)
    elif field_lower == "family":
        gbif_family = str(gbif_data.get("family", "") or "").strip().lower()
        return h_val.lower() == gbif_family
    elif field_lower == "genus":
        gbif_genus = str(gbif_data.get("genus", "") or "").strip().lower()
        return h_val.lower() == gbif_genus
    elif field_lower == "species":
        gbif_species = str(gbif_data.get("species", "") or "").strip().lower()
        return h_val.lower() == gbif_species

    return False
