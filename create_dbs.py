import pandas as pd

# Historical correct data
hist_data = {
    "Object ID": ["PL001", "PL002", "PL003", "PL004", "PL005", "PL006", "PL007", "PL008", "PL009", "PL010"],
    "Genus": ["Quercus", "Acer", "Pinus", "Rosa", "Helianthus", "Taraxacum", "Trifolium", "Fagus", "Betula", "Salix"],
    "Species": ["robur", "saccharum", "strobus", "rubra", "annuus", "officinale", "repens", "grandifolia", "papyrifera", "alba"],
    "Author": ["L.", "Marshall", "L.", "L.", "L.", "Wiggers", "L.", "Ehrh.", "Marshall", "L."],
    "Family": ["Fagaceae", "Sapindaceae", "Pinaceae", "Rosaceae", "Asteraceae", "Asteraceae", "Fabaceae", "Fagaceae", "Betulaceae", "Salicaceae"],
    "Location": ["Room A", "Room B", "Room C", "Room A", "Room D", "Room B", "Room C", "Room D", "Room A", "Room B"],
    "Reviewed": ["Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes"],
    "Genus_Problem": [False, False, False, False, False, False, False, False, False, False],
    "Species_Problem": [False, False, False, False, False, False, False, False, False, False]
}

hist_df = pd.DataFrame(hist_data)
hist_df.to_excel("historical_books.xlsx", index=False)

# Current inventory with intentional errors
curr_data = {
    "Object ID": ["PL001", "PL002", "PL003", "PL004", "PL005", "PL006", "PL007", "PL008", "PL009", "PL010"],
    "Genus": ["Quercs", "Acer", "Pinus", "Rosea", "Helianthus", "Taraxcum", "Trifolium", "Fagus", "Betula", ""], # typos and blanks
    "Species": ["robur", "sacharum", "strobus", "rubra", "annuus", "officinalis", "repens", "grandifolia", "papyrifera", "alba"], # typos
    "Author": ["L.", "Marshall", "L.", "L.", "L.", "Wiggers", "L.", "Ehrh.", "Marshall", "L."],
    "Family": ["Fagaceae", "Sapindaceae", "Pinaceae", "Rosaceae", "Asteraceae", "Asteraceae", "Fabaceae", "Fagaceae", "Betulaceae", "Salicaceae"],
    "Location": ["Room A", "Basement", "Room C", "Room A", "Room D", "Room B", "Room C", "Lost", "Room A", "Room B"], # wrong locations
    "Reviewed": ["No", "No", "No", "No", "No", "No", "No", "No", "No", "No"],
    "Genus_Problem": [False, True, False, False, False, False, False, False, False, False], # incorrectly checked/unchecked
    "Species_Problem": [False, False, False, False, False, False, False, False, False, False]
}

curr_df = pd.DataFrame(curr_data)
curr_df.to_excel("current_inventory.xlsx", index=False)

print("Created databases.")
