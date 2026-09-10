import requests
import concurrent.futures
from typing import List, Dict, Optional, Any

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


def _process_single_item(item: Dict[str, Any], cancel_event=None) -> Optional[Dict[str, Any]]:
    """Process a single item against GBIF and return proposed changes if any."""
    if cancel_event and cancel_event.is_set():
        return None

    oid = str(item.get("oid", ""))
    genus = str(item.get("genus", "") or "").strip()
    species = str(item.get("species", "") or "").strip()
    author = str(item.get("author", "") or "").strip()
    family = str(item.get("family", "") or "").strip()
    higher = str(item.get("higher_classification", "") or item.get("Higher Classification", "") or "").strip()

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
            if acc_data.get("higherClassification"):
                gbif_data["higherClassification"] = acc_data["higherClassification"]

    prop_genus = gbif_data.get("genus") or ""
    prop_species = gbif_data.get("species") or ""
    prop_author = gbif_data.get("author") or ""
    prop_family = gbif_data.get("family") or ""
    prop_higher = gbif_data.get("higherClassification") or ""

    current_map = {
        "Genus": genus,
        "Species": species,
        "Author": author,
        "Family": family,
        "Higher Classification": higher
    }
    proposed_map = {
        "Genus": prop_genus,
        "Species": prop_species,
        "Author": prop_author,
        "Family": prop_family,
        "Higher Classification": prop_higher
    }

    changes = []
    for k in ["Genus", "Species", "Author", "Family", "Higher Classification"]:
        c_val = current_map[k]
        p_val = proposed_map[k]
        if k == "Higher Classification":
            def _norm(s):
                if not s: return ""
                import re
                return " | ".join([t.strip().lower() for t in re.split(r"[|/;,]+", s) if t.strip()])
            if p_val and _norm(p_val) != _norm(c_val):
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


def batch_gbif_match(items: List[Dict[str, Any]], progress_callback=None, cancel_event=None, max_workers: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Query GBIF concurrently for a list of items and return proposed taxonomic changes.
    """
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

    total = len(items)
    results = []
    completed_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {
            executor.submit(_process_single_item, item, cancel_event): item
            for item in items
        }

        for future in concurrent.futures.as_completed(future_to_item):
            if cancel_event and cancel_event.is_set():
                break

            item = future_to_item[future]
            cur_oid = str(item.get("oid", ""))
            completed_count += 1

            if progress_callback:
                try:
                    progress_callback(completed_count, total, cur_oid)
                except Exception:
                    pass

            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"Error processing item {cur_oid}: {e}")

    # Maintain deterministic ordering matching item list
    oid_order = {str(item.get("oid", "")): idx for idx, item in enumerate(items)}
    results.sort(key=lambda r: oid_order.get(r.get("oid", ""), 0))

    return results

