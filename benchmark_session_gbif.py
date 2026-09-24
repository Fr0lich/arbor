import time
import requests
from backend.gbif import batch_gbif_match, get_accepted_name, check_gbif

session = requests.Session()

def check_gbif_session(genus: str, species: str):
    genus = (genus or "").strip()
    species = (species or "").strip()
    name = f"{genus} {species}".strip()
    if not name or not genus:
        return None
    url = f"https://api.gbif.org/v1/species/match?name={name}"
    try:
        response = session.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        return {"error": str(e)}

start2 = time.time()
for i in range(10):
    check_gbif_session("Bombus", "lucorum")
end2 = time.time()
print(f"Sequential check_gbif_session time taken: {end2 - start2:.2f} seconds")
