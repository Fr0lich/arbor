import requests
import concurrent.futures
import re
from typing import List, Dict, Optional, Any

UNDETERMINED_SPECIES_EXACT = {
    "", "sp", "sp.", "spp", "spp.", "spec", "spec.", "species",
    "indet", "indet.", "undet", "undet.", "unknown", "?", "-", "--",
    "none", "n/a", "na", "null"
}

_MORPHOSPECIES_PATTERN = re.compile(
    r"^(sp\.?|spec\.?|indet\.?|species)\s*([0-9]+|[a-zA-Z]|nov\.?|nr\.?|aff\.?|cf\.?.*)?$",
    re.IGNORECASE
)


def is_undetermined_species(species: Any) -> bool:
    """
    Returns True if species string indicates an undetermined taxon, open nomenclature,
    morphospecies, or unassigned species (e.g. 'sp.', 'spp.', 'indet.', 'sp. 1', 'sp. nov.', '?').
    """
    if species is None:
        return True
    s = str(species).strip().lower()
    if s in UNDETERMINED_SPECIES_EXACT:
        return True
    s_clean = s.rstrip(".").strip()
    if s_clean in UNDETERMINED_SPECIES_EXACT:
        return True
    if _MORPHOSPECIES_PATTERN.match(s):
        return True
    return False


def check_gbif(genus: str, species: str):
    genus = (genus or "").strip()
    species = (species or "").strip()
    name = f"{genus} {species}".strip()
    if not name or not genus:
        return None
    url = f"https://api.gbif.org/v1/species/match?name={name}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        scientific_name = data.get("scientificName", "")
        canonical_name = data.get("canonicalName", "")

        # get authorship directly if available, otherwise fallback to parsing
        author = data.get("authorship", "")
        if not author:
             author = scientific_name.replace(canonical_name, "").strip() if canonical_name and scientific_name.startswith(canonical_name) else ""

        # The gbif API sometimes returns exact matches for genus only if species is not found.
        if data.get("rank") == "GENUS" and species:
            match_type = "HIGHERRANK"
        else:
            match_type = data.get("matchType")

        new_genus = data.get("genus", "")
        new_species = data.get("species", data.get("canonicalName", ""))
        if new_genus and new_species and new_species.startswith(new_genus + " "):
            new_species = new_species[len(new_genus):].strip()

        higher_classification = " | ".join(filter(None, [
            (data.get("kingdom") or "").strip(),
            (data.get("phylum") or "").strip(),
            (data.get("class") or "").strip(),
            (data.get("order") or "").strip()
        ]))

        return {
            "matchType": match_type,
            "status": data.get("status"),
            "canonicalName": data.get("canonicalName"),
            "scientificName": data.get("scientificName"),
            "genus": new_genus,
            "species": new_species,
            "author": author,
            "family": data.get("family", ""),
            "higherClassification": higher_classification,
            "rank": data.get("rank"),
            "synonym": data.get("status") == "SYNONYM",
            "acceptedUsageKey": data.get("acceptedUsageKey"),
        }
    except Exception as e:
        print(f"Error checking GBIF: {e}")
        return {"error": str(e)}

def get_accepted_name(usage_key: int):
    url = f"https://api.gbif.org/v1/species/{usage_key}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        scientific_name = data.get("scientificName", "")
        canonical_name = data.get("canonicalName", "")

        author = data.get("authorship", "")
        if not author:
             author = scientific_name.replace(canonical_name, "").strip() if canonical_name and scientific_name.startswith(canonical_name) else ""

        new_genus = data.get("genus", "")
        new_species = data.get("species", data.get("canonicalName", ""))
        if new_genus and new_species and new_species.startswith(new_genus + " "):
            new_species = new_species[len(new_genus):].strip()

        higher_classification = " | ".join(filter(None, [
            (data.get("kingdom") or "").strip(),
            (data.get("phylum") or "").strip(),
            (data.get("class") or "").strip(),
            (data.get("order") or "").strip()
        ]))

        return {
            "canonicalName": data.get("canonicalName"),
            "scientificName": data.get("scientificName"),
            "genus": new_genus,
            "species": new_species,
            "author": author,
            "family": data.get("family", ""),
            "higherClassification": higher_classification,
        }
    except Exception as e:
        print(f"Error checking GBIF accepted name: {e}")
        return {"error": str(e)}


def is_author_equivalent(a1: Any, a2: Any) -> bool:
    """Compare two author strings taking into account abbreviations, spacing, and punctuation."""
    s1 = str(a1 or "").strip()
    s2 = str(a2 or "").strip()
    if not s1 and not s2:
        return True
    if not s1 or not s2:
        return False
    if s1 == s2:
        return True
    norm1 = s1.replace(".", "").replace(",", "").replace("(", "").replace(")", "").replace(" ", "").lower()
    norm2 = s2.replace(".", "").replace(",", "").replace("(", "").replace(")", "").replace(" ", "").lower()
    return norm1 == norm2


def is_classification_equivalent(existing_val: Any, gbif_val: Any) -> bool:
    """Compare existing higher classification against GBIF considering rank depth, formatting, and division synonyms."""
    if existing_val is None or gbif_val is None:
        return False
    e_str = str(existing_val).strip()
    g_str = str(gbif_val).strip()
    if not e_str and not g_str:
        return True
    if not e_str or not g_str:
        return False
    if e_str == g_str:
        return True

    import re
    def tokenize(s):
        raw_tokens = re.split(r"[|/;,]+", s)
        tokens = []
        for t in raw_tokens:
            cleaned = t.strip().lower()
            if cleaned:
                if cleaned in ("magnoliophyta", "angiospermae", "spermatophyta", "anthophyta"):
                    cleaned = "tracheophyta"
                elif cleaned in ("pinophyta", "coniferophyta", "gymnospermae"):
                    cleaned = "tracheophyta"
                tokens.append(cleaned)
        return tokens

    e_tokens = tokenize(e_str)
    g_tokens = tokenize(g_str)

    if not e_tokens or not g_tokens:
        return False

    if e_tokens == g_tokens:
        return True

    set_e = set(e_tokens)
    set_g = set(g_tokens)

    if set_e == set_g:
        return True

    # If existing has all GBIF ranks plus extras (e.g. family or subranks), it is equivalent
    if set_g.issubset(set_e):
        return True

    # If existing has at least 3 ranks (e.g. Class+Order+Kingdom) and matches GBIF ranks, it is equivalent
    if len(e_tokens) >= 3 and set_e.issubset(set_g):
        return True

    return False


def _process_single_item(item: Dict[str, Any], cancel_event=None) -> Optional[Dict[str, Any]]:
    """Process a single item against GBIF and return proposed changes if any."""
    if cancel_event and cancel_event.is_set():
        return None

    oid = str(item.get("oid", ""))
    genus = str(item.get("genus", "") or "").strip()
    species = str(item.get("species", "") or "").strip()
    author = str(item.get("author", "") or "").strip()
    family = str(item.get("family", "") or "").strip()

    if not genus:
        return None

    gbif_data = check_gbif(genus, species)
    if not gbif_data or "error" in gbif_data:
        return None

    # If synonym, optionally fetch accepted name
    if gbif_data.get("synonym") and gbif_data.get("acceptedUsageKey"):
        if cancel_event and cancel_event.is_set():
            return None
        acc_data = get_accepted_name(gbif_data["acceptedUsageKey"])
        if acc_data and "error" not in acc_data:
            if acc_data.get("genus"):
                gbif_data["genus"] = acc_data["genus"]
            if acc_data.get("species"):
                gbif_data["species"] = acc_data["species"]
            if acc_data.get("author"):
                gbif_data["author"] = acc_data["author"]
            if acc_data.get("family"):
                gbif_data["family"] = acc_data["family"]

    prop_genus = gbif_data.get("genus") or ""
    prop_species = gbif_data.get("species") or ""
    prop_author = gbif_data.get("author") or ""
    prop_family = gbif_data.get("family") or ""

    current_map = {
        "Genus": genus,
        "Species": species,
        "Author": author,
        "Family": family,
    }
    proposed_map = {
        "Genus": prop_genus,
        "Species": prop_species,
        "Author": prop_author,
        "Family": prop_family,
    }

    changes = []
    for k in ["Genus", "Species", "Author", "Family"]:
        c_val = current_map[k]
        p_val = proposed_map[k]
        if k == "Author":
            if p_val and not is_author_equivalent(c_val, p_val):
                changes.append({"field": k, "old": c_val, "new": p_val})
        elif k == "Family":
            if p_val and p_val.lower() != c_val.lower():
                changes.append({"field": k, "old": c_val, "new": p_val})
        else:
            if p_val and p_val != c_val:
                changes.append({"field": k, "old": c_val, "new": p_val})

    if changes:
        return {
            "oid": oid,
            "current": current_map,
            "proposed": proposed_map,
            "changes": changes,
            "match_type": gbif_data.get("matchType") or "MATCH",
            "status": gbif_data.get("status") or "ACCEPTED",
            "rank": gbif_data.get("rank") or "SPECIES"
        }
    return None


def _query_single_taxon(genus: str, species: str, cancel_event=None) -> Optional[Dict[str, Any]]:
    """
    Query GBIF for a single genus/species taxon combination, resolving synonyms and family hierarchy.
    If species is undetermined ('sp.', 'indet.', blank), queries at genus rank.
    """
    if cancel_event and cancel_event.is_set():
        return None
    if not genus:
        return None

    is_undet = is_undetermined_species(species)
    # If undetermined, query genus only
    query_species = "" if is_undet else species

    gbif_data = check_gbif(genus, query_species)
    if not gbif_data or "error" in gbif_data:
        return None

    original_scientific_name = gbif_data.get("scientificName") or f"{genus} {query_species}".strip()
    is_synonym = bool(gbif_data.get("synonym"))
    accepted_scientific_name = ""

    if is_synonym and gbif_data.get("acceptedUsageKey"):
        if cancel_event and cancel_event.is_set():
            return None
        acc_data = get_accepted_name(gbif_data["acceptedUsageKey"])
        if acc_data and "error" not in acc_data:
            accepted_scientific_name = acc_data.get("scientificName") or ""
            if acc_data.get("genus"):
                gbif_data["genus"] = acc_data["genus"]
            if not is_undet and acc_data.get("species"):
                gbif_data["species"] = acc_data["species"]
            if not is_undet and acc_data.get("author"):
                gbif_data["author"] = acc_data["author"]
            if acc_data.get("family"):
                gbif_data["family"] = acc_data["family"]

    gbif_data["is_undetermined"] = is_undet
    gbif_data["is_synonym"] = is_synonym
    gbif_data["original_scientific_name"] = original_scientific_name
    gbif_data["accepted_scientific_name"] = accepted_scientific_name
    if is_undet:
        gbif_data["species"] = species
        gbif_data["rank"] = "GENUS"

    return gbif_data


def _evaluate_item_diff(item: Dict[str, Any], gbif_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Compare an individual item against resolved GBIF data and produce diffs with taxonomic reasons."""
    if not gbif_data or "error" in gbif_data:
        return None

    oid = str(item.get("oid", ""))
    genus = str(item.get("genus", "") or "").strip()
    species = str(item.get("species", "") or "").strip()
    author = str(item.get("author", "") or "").strip()
    family = str(item.get("family", "") or "").strip()

    is_undet = is_undetermined_species(species) or gbif_data.get("is_undetermined", False)
    is_synonym = gbif_data.get("is_synonym", False)

    prop_genus = gbif_data.get("genus") or ""
    # If undetermined, NEVER change species name, but check Genus Author
    if is_undet:
        prop_species = species
        prop_author = gbif_data.get("author") or ""
    else:
        prop_species = gbif_data.get("species") or ""
        prop_author = gbif_data.get("author") or ""

    prop_family = gbif_data.get("family") or ""

    current_map = {
        "Genus": genus,
        "Species": species,
        "Author": author,
        "Family": family,
    }
    proposed_map = {
        "Genus": prop_genus,
        "Species": prop_species,
        "Author": prop_author,
        "Family": prop_family,
    }

    changes = []
    for k in ["Genus", "Species", "Author", "Family"]:
        c_val = current_map[k]
        p_val = proposed_map[k]

        if k == "Author":
            if p_val and not is_author_equivalent(c_val, p_val):
                if not c_val:
                    r_code = "MISSING_AUTHOR"
                    r_lbl = "+ Missing Author"
                    expl = f"Populated {'Genus' if is_undet else 'Species'} author '{p_val}' from GBIF."
                else:
                    r_code = "AUTHOR_STANDARDIZED"
                    r_lbl = "Author Standardized"
                    expl = f"Standardized author from '{c_val}' to '{p_val}'."
                changes.append({
                    "field": k, "old": c_val, "new": p_val,
                    "reason_code": r_code, "reason_label": r_lbl, "explanation": expl
                })
        elif k == "Family":
            if p_val and p_val.lower() != c_val.lower():
                if not c_val:
                    r_code = "MISSING_FAMILY"
                    r_lbl = "+ Missing Family"
                    expl = f"Assigned family '{p_val}' from GBIF classification for genus '{prop_genus}'."
                else:
                    r_code = "FAMILY_UPDATE"
                    r_lbl = "Family Reclassified"
                    expl = f"Updated family classification from '{c_val}' to '{p_val}'."
                changes.append({
                    "field": k, "old": c_val, "new": p_val,
                    "reason_code": r_code, "reason_label": r_lbl, "explanation": expl
                })
        elif k == "Species":
            if not is_undet and p_val and p_val != c_val:
                if is_synonym:
                    r_code = "SYNONYM_SPECIES"
                    r_lbl = "Accepted Species (Synonym)"
                    expl = f"'{species}' is an older synonym for accepted species '{p_val}'."
                else:
                    r_code = "SPELLING"
                    r_lbl = "Spelling / Typo Fix"
                    expl = f"Corrected species spelling from '{c_val}' to '{p_val}'."
                changes.append({
                    "field": k, "old": c_val, "new": p_val,
                    "reason_code": r_code, "reason_label": r_lbl, "explanation": expl
                })
        else:  # Genus
            if p_val and p_val != c_val:
                if is_synonym:
                    r_code = "SYNONYM_GENUS"
                    r_lbl = "⚠️ Reclassified Genus (Synonym)"
                    expl = f"'{genus} {species}'.strip() is cataloged as a synonym for modern combination '{prop_genus} {prop_species}'.strip() in GBIF."
                else:
                    r_code = "SPELLING"
                    r_lbl = "🔤 Spelling / Typo Fix"
                    expl = f"Corrected genus spelling from '{c_val}' to '{p_val}'."
                changes.append({
                    "field": k, "old": c_val, "new": p_val,
                    "reason_code": r_code, "reason_label": r_lbl, "explanation": expl
                })

    if changes:
        missing_family = (not bool(family)) and bool(prop_family)
        missing_author = (not bool(author)) and bool(prop_author)
        return {
            "oid": oid,
            "current": current_map,
            "proposed": proposed_map,
            "changes": changes,
            "match_type": gbif_data.get("matchType") or "MATCH",
            "status": "SYNONYM" if is_synonym else (gbif_data.get("status") or "ACCEPTED"),
            "rank": gbif_data.get("rank") or ("GENUS" if is_undet else "SPECIES"),
            "is_undetermined": is_undet,
            "is_synonym": is_synonym,
            "missing_family": missing_family,
            "missing_author": missing_author,
            "original_scientific_name": gbif_data.get("original_scientific_name", ""),
            "accepted_scientific_name": gbif_data.get("accepted_scientific_name", "")
        }
    return None


def batch_gbif_match(
    items: List[Dict[str, Any]],
    progress_callback=None,
    cancel_event=None,
    max_workers: Optional[int] = None,
    exclude_undetermined: bool = False
) -> List[Dict[str, Any]]:
    """
    Query GBIF concurrently for unique taxa and return proposed taxonomic changes across all items.
    Supports excluding undetermined ('sp.') specimens or validating their Family/Genus safely.
    """
    if not items:
        return []

    if exclude_undetermined:
        items = [item for item in items if not is_undetermined_species(item.get("species"))]
        if not items:
            return []

    if max_workers is None:
        try:
            import config
            prefs = config.load_prefs()
            max_workers = int(prefs.get("gbif_max_workers", 5))
        except Exception:
            max_workers = 5
    max_workers = max(1, min(10, max_workers))

    # 1. Deduplicate unique taxa:
    # Binomials map to (genus_lower, species_lower) -> (genus, species)
    # Undetermined taxa map to (genus_lower, "__undetermined__") -> (genus, "")
    unique_taxa = {}
    for item in items:
        g = str(item.get("genus", "") or "").strip()
        s = str(item.get("species", "") or "").strip()
        if g:
            if is_undetermined_species(s):
                key = (g.lower(), "__undetermined__")
                if key not in unique_taxa:
                    unique_taxa[key] = (g, s)
            else:
                key = (g.lower(), s.lower())
                if key not in unique_taxa:
                    unique_taxa[key] = (g, s)

    if not unique_taxa:
        return []

    total_taxa = len(unique_taxa)
    taxon_cache = {}
    completed_taxa = 0

    # 2. Query GBIF concurrently only for distinct taxa
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_key = {
            executor.submit(_query_single_taxon, g, s, cancel_event): key
            for key, (g, s) in unique_taxa.items()
        }

        for future in concurrent.futures.as_completed(future_to_key):
            if cancel_event and cancel_event.is_set():
                break

            key = future_to_key[future]
            completed_taxa += 1

            if progress_callback:
                try:
                    display_name = f"{unique_taxa[key][0]} {unique_taxa[key][1]}".strip()
                    progress_callback(completed_taxa, total_taxa, display_name)
                except Exception:
                    pass

            try:
                gbif_res = future.result()
                taxon_cache[key] = gbif_res
            except Exception as e:
                print(f"Error querying taxon {key}: {e}")
                taxon_cache[key] = None

    if cancel_event and cancel_event.is_set():
        return []

    # 3. Evaluate diffs for each item against the resolved taxon cache
    results = []
    for item in items:
        g = str(item.get("genus", "") or "").strip()
        s = str(item.get("species", "") or "").strip()
        if is_undetermined_species(s):
            key = (g.lower(), "__undetermined__")
        else:
            key = (g.lower(), s.lower())
        gbif_data = taxon_cache.get(key)
        diff = _evaluate_item_diff(item, gbif_data)
        if diff:
            results.append(diff)

    return results


