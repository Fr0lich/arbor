import requests

def check_gbif(genus: str, species: str):
    name = f"{genus} {species}".strip()
    if not name:
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
            data.get("kingdom"),
            data.get("phylum"),
            data.get("class"),
            data.get("order")
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
        return None

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
            data.get("kingdom"),
            data.get("phylum"),
            data.get("class"),
            data.get("order")
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
        return None


def batch_gbif_match(items, progress_callback=None, cancel_event=None):
    """
    Query GBIF for a list of items and return proposed taxonomic changes.
    """
    results = []
    total = len(items)

    for i, item in enumerate(items):
        if cancel_event and cancel_event.is_set():
            break

        oid = str(item.get("oid", ""))
        genus = str(item.get("genus", "") or "").strip()
        species = str(item.get("species", "") or "").strip()
        author = str(item.get("author", "") or "").strip()
        family = str(item.get("family", "") or "").strip()
        higher = str(item.get("higher_classification", "") or item.get("Higher Classification", "") or "").strip()

        if progress_callback:
            try:
                progress_callback(i + 1, total, oid)
            except Exception:
                pass

        if not genus and not species:
            continue

        gbif_data = check_gbif(genus, species)
        if not gbif_data:
            continue

        # If synonym, optionally fetch accepted name
        if gbif_data.get("synonym") and gbif_data.get("acceptedUsageKey"):
            acc_data = get_accepted_name(gbif_data["acceptedUsageKey"])
            if acc_data:
                gbif_data["genus"] = acc_data.get("genus") or gbif_data.get("genus")
                gbif_data["species"] = acc_data.get("species") or gbif_data.get("species")
                gbif_data["author"] = acc_data.get("author") or gbif_data.get("author")
                gbif_data["family"] = acc_data.get("family") or gbif_data.get("family")
                gbif_data["higherClassification"] = acc_data.get("higherClassification") or gbif_data.get("higherClassification")

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
            if p_val and p_val != c_val:
                changes.append({"field": k, "old": c_val, "new": p_val})

        if changes:
            results.append({
                "oid": oid,
                "current": current_map,
                "proposed": proposed_map,
                "changes": changes,
                "match_type": gbif_data.get("matchType") or "MATCH",
                "status": gbif_data.get("status") or "ACCEPTED",
                "rank": gbif_data.get("rank") or "SPECIES"
            })

    return results
