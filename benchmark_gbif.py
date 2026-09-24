import time
from backend.gbif import batch_gbif_match, get_accepted_name, check_gbif

# create some dummy items
items = [
    {"oid": 1, "genus": "Bombus", "species": "lucorum"},
    {"oid": 2, "genus": "Bombus", "species": "terrestris"},
    {"oid": 3, "genus": "Apis", "species": "mellifera"},
    {"oid": 4, "genus": "Vespa", "species": "crabro"},
    {"oid": 5, "genus": "Formica", "species": "rufa"},
    {"oid": 6, "genus": "Lasius", "species": "niger"},
    {"oid": 7, "genus": "Myrmica", "species": "rubra"},
    {"oid": 8, "genus": "Camponotus", "species": "herculeanus"},
    {"oid": 9, "genus": "Panorpa", "species": "communis"},
    {"oid": 10, "genus": "Sialis", "species": "lutaria"},
] * 2

start = time.time()
res = batch_gbif_match(items, max_workers=5)
end = time.time()

print(f"Time taken: {end - start:.2f} seconds")

# Benchmark sequential calls
start2 = time.time()
for i in range(10):
    check_gbif("Bombus", "lucorum")
end2 = time.time()
print(f"Sequential check_gbif time taken: {end2 - start2:.2f} seconds")
