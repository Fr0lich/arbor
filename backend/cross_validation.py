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


def collect_field_provenance(app_state: Any, oid: str, field: str) -> List[Dict[str, Any]]:
    """
    Collect all archival historical candidates for a specimen field from:
    1. Loaded historical ledger books (app_state.historical_dbs), preserving exact sheet names.
    2. Audit log history (app_state.df_log), extracting original pre-GBIF mutation values.
    Returns list of candidate dicts: [{"value": ..., "source_name": ..., "source_type": ..., "timestamp": ...}]
    """
    candidates: List[Dict[str, Any]] = []
    oid_str = str(oid).strip()
    if not oid_str or not app_state:
        return candidates

    field_norm = field.strip().lower()

    # 1. Archival Books (app_state.historical_dbs)
    hist_dbs = getattr(app_state, "historical_dbs", None) or []
    for db in hist_dbs:
        db_name = db.get("name", "Historical Book")
        dict_cache = db.get("dict_cache", {})
        vals = []

        # Try dict cache
        oid_data = dict_cache.get(oid_str)
        if oid_data is None and oid_str.isdigit():
            oid_data = dict_cache.get(int(oid_str))

        if oid_data:
            for c, v_list in oid_data.items():
                if str(c).strip().lower() == field_norm:
                    vals.extend([str(v).strip() for v in v_list if str(v).strip() and str(v).strip().lower() != "nan"])
        else:
            # Fallback to direct df_reg lookup
            df = db.get("df_reg")
            if df is not None and hasattr(df, "index"):
                target_rows = None
                if "ObjectID" in df.columns:
                    target_rows = df[df["ObjectID"].astype(str) == oid_str]
                elif oid_str in df.index:
                    target_rows = df.loc[[oid_str]]
                elif oid_str.isdigit() and int(oid_str) in df.index:
                    target_rows = df.loc[[int(oid_str)]]

                if target_rows is not None and not target_rows.empty:
                    for col in target_rows.columns:
                        if str(col).strip().lower() == field_norm:
                            vals.extend([str(v).strip() for v in target_rows[col].dropna().values if str(v).strip() and str(v).strip().lower() != "nan"])

        for v in vals:
            if v and v.lower() != "(no data found)":
                candidates.append({
                    "value": v,
                    "source_name": db_name,
                    "source_type": "BOOK",
                    "timestamp": None
                })

    # 2. Audit Log (app_state.df_log / _log_records)
    log_records = getattr(app_state, "_log_records", None)
    if not log_records:
        df_log = getattr(app_state, "df_log", None)
        if df_log is not None and not df_log.empty:
            log_records = df_log.to_dict(orient="records")
        else:
            log_records = []

    for entry in log_records:
        entry_oid = str(entry.get("ObjectID", "")).strip()
        if entry_oid != oid_str:
            continue

        action = str(entry.get("Action", ""))
        if action not in ("GBIF_UPDATE", "GBIF_BATCH_UPDATE", "RESOLVE_HISTORICAL_CONFLICT"):
            continue

        ts = str(entry.get("Timestamp", "")).strip()
        cv_str = str(entry.get("ChangedValues", ""))
        # Parse: Field: "old" -> "new"
        diffs = cv_str.split(" | ")
        for d in diffs:
            if ' -> ' in d and ': "' in d:
                parts = d.split(': "', 1)
                f_name = parts[0].strip()
                if f_name.lower() == field_norm:
                    val_parts = parts[1].split('" -> "', 1)
                    old_v = val_parts[0].strip()
                    if old_v and old_v.lower() != "nan":
                        candidates.append({
                            "value": old_v,
                            "source_name": f"Audit Log ({ts})" if ts else "Audit Log",
                            "source_type": "AUDIT_LOG",
                            "timestamp": ts
                        })

    return candidates


def validate_candidate_with_gbif(genus: str, candidate_val: str) -> Dict[str, Any]:
    """
    Run pre-flight GBIF validation on a proposed candidate value for a given genus.
    Returns structured taxonomic status:
    - ACCEPTED: Current accepted modern taxon
    - SYNONYM: Valid historical synonym with accepted target
    - FUZZY_TYPO: Spelling mistake in source ledger
    - NO_MATCH: Unverified / higher rank
    """
    val = str(candidate_val or "").strip()
    g = str(genus or "").strip()
    if not val or not g:
        return {
            "status": "NO_MATCH",
            "gbif_rank": "",
            "badge_label": "❓ Missing Taxon",
            "badge_color": "subdued",
            "accepted_name": None,
            "accepted_author": None,
            "confidence": 0
        }

    gbif_res = check_gbif(g, val)
    if not gbif_res or "error" in gbif_res:
        return {
            "status": "NO_MATCH",
            "gbif_rank": "",
            "badge_label": "❓ No GBIF Match",
            "badge_color": "subdued",
            "accepted_name": None,
            "accepted_author": None,
            "confidence": 0
        }

    status = (gbif_res.get("status") or "ACCEPTED").upper()
    rank = (gbif_res.get("rank") or "SPECIES").upper()
    match_type = (gbif_res.get("matchType") or "MATCH").upper()
    confidence = int(gbif_res.get("confidence", 0))

    # Synonym check
    if status == "SYNONYM" or gbif_res.get("synonym"):
        acc_key = gbif_res.get("acceptedUsageKey")
        acc_name = None
        acc_author = None
        if acc_key:
            from backend.gbif import get_accepted_name
            acc_data = get_accepted_name(acc_key)
            if acc_data and "error" not in acc_data:
                acc_name = acc_data.get("canonicalName") or acc_data.get("scientificName")
                acc_author = acc_data.get("author")

        target_display = acc_name if acc_name else "Modern Taxon"
        return {
            "status": "SYNONYM",
            "gbif_rank": rank,
            "badge_label": f"📜 Valid Synonym → {target_display}",
            "badge_color": "warning",
            "accepted_name": acc_name,
            "accepted_author": acc_author,
            "confidence": confidence
        }

    # Accepted species
    if rank == "SPECIES" and status == "ACCEPTED":
        if match_type == "FUZZY":
            matched = gbif_res.get("species") or gbif_res.get("canonicalName")
            return {
                "status": "FUZZY_TYPO",
                "gbif_rank": rank,
                "badge_label": f"🔤 Typo in Source → {matched}",
                "badge_color": "warning",
                "accepted_name": matched,
                "accepted_author": gbif_res.get("author"),
                "confidence": confidence
            }
        canonical = gbif_res.get("canonicalName") or f"{g} {val}"
        return {
            "status": "ACCEPTED",
            "gbif_rank": rank,
            "badge_label": "✅ Current Accepted Species",
            "badge_color": "success",
            "accepted_name": canonical,
            "accepted_author": gbif_res.get("author"),
            "confidence": confidence
        }

    # Higher rank or unrecognized
    return {
        "status": "NO_MATCH",
        "gbif_rank": rank,
        "badge_label": f"❓ Unverified ({rank})",
        "badge_color": "subdued",
        "accepted_name": None,
        "accepted_author": None,
        "confidence": confidence
    }


def get_validated_provenance_candidates(app_state: Any, oid: str, field: str, genus: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Collects all provenance candidates across books and audit logs, validates each against GBIF,
    and returns deduplicated options with source badges and live taxonomic validation.
    """
    raw_candidates = collect_field_provenance(app_state, oid, field)
    if not genus and app_state and getattr(app_state, "df_reg", None) is not None:
        oid_clean = oid
        if oid_clean not in app_state.df_reg.index and str(oid).isdigit() and int(oid) in app_state.df_reg.index:
            oid_clean = int(oid)
        if oid_clean in app_state.df_reg.index and "Genus" in app_state.df_reg.columns:
            genus = str(app_state.df_reg.at[oid_clean, "Genus"] or "").strip()

    genus_str = str(genus or "").strip()

    # Group by value
    grouped: Dict[str, Dict[str, Any]] = {}
    for c in raw_candidates:
        val = c["value"]
        if val not in grouped:
            grouped[val] = {
                "value": val,
                "sources": [c["source_name"]],
                "source_types": [c["source_type"]],
                "latest_timestamp": c["timestamp"]
            }
        else:
            if c["source_name"] not in grouped[val]["sources"]:
                grouped[val]["sources"].append(c["source_name"])
            if c["source_type"] not in grouped[val]["source_types"]:
                grouped[val]["source_types"].append(c["source_type"])
            if c["timestamp"] and not grouped[val]["latest_timestamp"]:
                grouped[val]["latest_timestamp"] = c["timestamp"]

    results: List[Dict[str, Any]] = []
    for val, g_info in grouped.items():
        v_res = validate_candidate_with_gbif(genus_str, val)
        results.append({
            "value": val,
            "sources": g_info["sources"],
            "source_display": ", ".join(g_info["sources"]),
            "source_types": g_info["source_types"],
            "timestamp": g_info["latest_timestamp"],
            "gbif_validation": v_res
        })

    return results


def scan_taxonomic_rank_inversions(app_state: Any) -> List[Dict[str, Any]]:
    """
    Perform a fast (<50ms) scan across app_state.df_reg for taxonomic rank inversions
    (e.g. botanical family names like Pinaceae ending up in the Species column).
    For each anomalous record, attaches multi-source provenance candidates from books
    and audit log with pre-flight GBIF validation.
    """
    from backend.gbif import is_likely_family_name

    anomalies: List[Dict[str, Any]] = []
    df_reg = getattr(app_state, "df_reg", None)
    if df_reg is None or df_reg.empty:
        return anomalies

    species_col = "Species" if "Species" in df_reg.columns else None
    genus_col = "Genus" if "Genus" in df_reg.columns else None
    family_col = "Family" if "Family" in df_reg.columns else None

    if not species_col:
        return anomalies

    for idx, row in df_reg.iterrows():
        oid = str(idx)
        sp = str(row.get(species_col, "") or "").strip()
        fam = str(row.get(family_col, "") or "").strip() if family_col else ""
        gen = str(row.get(genus_col, "") or "").strip() if genus_col else ""

        if not sp or sp.lower() in ("nan", "none", "", "?"):
            continue

        is_inversion = is_likely_family_name(sp) or (fam and sp.lower() == fam.lower())
        if is_inversion:
            candidates = get_validated_provenance_candidates(app_state, oid, species_col, gen)
            anomalies.append({
                "oid": oid,
                "genus": gen,
                "current_species": sp,
                "current_family": fam,
                "issue": "Family rank detected in Species field",
                "candidates": candidates
            })

    return anomalies


def restore_provenance_candidate(
    app_state: Any,
    oid: str,
    field: str,
    restored_value: str,
    source_description: str = "Archival Book"
) -> bool:
    """
    Safely restore a corrupted field to a validated historical candidate and record
    a structured TAXONOMIC_INVERSION_RESTORE entry in the audit log.
    """
    df_reg = getattr(app_state, "df_reg", None)
    if df_reg is None or field not in df_reg.columns:
        return False

    oid_str = str(oid).strip()
    target_idx = None
    if oid_str in df_reg.index:
        target_idx = oid_str
    elif oid_str.isdigit() and int(oid_str) in df_reg.index:
        target_idx = int(oid_str)

    if target_idx is None:
        return False

    old_val = str(df_reg.at[target_idx, field] or "")
    df_reg.at[target_idx, field] = restored_value

    # Structured audit logging
    import getpass
    from datetime import datetime
    import os

    ts = datetime.now().isoformat(timespec="seconds")
    user = getpass.getuser()
    excel_p = getattr(app_state, "excel_path", "") or ""

    log_entry = {
        "Timestamp": ts,
        "User": user,
        "Action": "TAXONOMIC_INVERSION_RESTORE",
        "ObjectID": oid_str,
        "Reviewed": "",
        "ChangedFields": field,
        "ChangedValues": f'{field}: "{old_val}" -> "{restored_value}" (Restored from {source_description})',
        "ProblemsChanged": "",
        "ProblemsChangedValues": "",
        "LocationChanged": "",
        "LocationChangedValues": "",
        "SourceFile": os.path.basename(excel_p),
        "OutputFile": os.path.basename(excel_p)
    }

    if not hasattr(app_state, "_log_records") or not app_state._log_records:
        df_log = getattr(app_state, "df_log", None)
        if df_log is not None and not df_log.empty:
            app_state._log_records = df_log.to_dict(orient="records")
        else:
            app_state._log_records = []

    app_state._log_records.append(log_entry)
    app_state.df_log = pd.DataFrame(app_state._log_records)
    app_state.dirty = True

    return True
