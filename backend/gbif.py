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
