"""scratch/generate_parity_test_data.py
Generator script for Phase 6 Parity Verification test databases.
Produces:
  1. mock_current_db.xlsx (Primary Specimen Database following 'Økonomisk Botanisk' schema)
  2. mock_historical_books.xlsx (Archival Ledger Books with intentional discrepancies)
"""
import os
import pandas as pd
from datetime import datetime

def generate_parity_data():
    os.makedirs("scratch", exist_ok=True)
    current_db_path = os.path.join("scratch", "mock_current_db.xlsx")
    historical_books_path = os.path.join("scratch", "mock_historical_books.xlsx")

    # -------------------------------------------------------------
    # 1. Primary Specimen Database (25 specimens)
    # -------------------------------------------------------------
    specimens = [
        # 1001: Clean record (Pinus sylvestris)
        {"id": 1001, "var": "", "genus": "Pinus", "sp": "sylvestris", "auth": "L.", "fam": "Pinaceae",
         "high_class": "Plantae; Pinopsida; Pinales; Pinaceae", "n_part": "Furu kongle", "part": "Cone",
         "col": "M.N. Blytt", "col_nr": "104", "date": "1845-07-12", "place": "Oslo, Tøyen",
         "box": "Boks 1", "obs": "Typical cone sample.", "status": "LC", "comment": "Verified against herbarium sheet.",
         "uid": "NHMO-BOT-1001", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "2", "cab": "C-12", "shelf": "3", "probs": {}},

        # 1002: Clean record (Betula pendula)
        {"id": 1002, "var": "", "genus": "Betula", "sp": "pendula", "auth": "Roth", "fam": "Betulaceae",
         "high_class": "Plantae; Magnoliopsida; Fagales; Betulaceae", "n_part": "Bjørkenever", "part": "Bark",
         "col": "Ove Dahl", "col_nr": "D-89", "date": "1894-06-20", "place": "Kongsberg",
         "box": "Boks 2", "obs": "Clean bark roll.", "status": "LC", "comment": "Good condition.",
         "uid": "NHMO-BOT-1002", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "2", "cab": "C-12", "shelf": "4", "probs": {}},

        # 1003: Typo Genus 'Pinuss' (Problem Queue + GBIF trigger)
        {"id": 1003, "var": "", "genus": "Pinuss", "sp": "mugo", "auth": "Turra", "fam": "Pinaceae",
         "high_class": "Plantae; Pinopsida; Pinales; Pinaceae", "n_part": "Buskfuru kvist", "part": "Twig",
         "col": "J.M. Norman", "col_nr": "N-12", "date": "1888-08-05", "place": "Røros",
         "box": "Boks 1", "obs": "Spelling typo on genus label.", "status": "LC", "comment": "Needs genus correction.",
         "uid": "NHMO-BOT-1003", "prob_desc": "Genus misspelled as Pinuss", "rev": False, "bld": "Lid's hus", "fl": "2", "cab": "C-12", "shelf": "1",
         "probs": {"Genus_Problem": True}},

        # 1004: Missing Author (Problem Queue trigger)
        {"id": 1004, "var": "", "genus": "Abies", "sp": "alba", "auth": "", "fam": "Pinaceae",
         "high_class": "Plantae; Pinopsida; Pinales; Pinaceae", "n_part": "Edelgran nåler", "part": "Needles",
         "col": "R.E. Fridtz", "col_nr": "542", "date": "1902-09-14", "place": "Dovrefjell, Kongsvold",
         "box": "Boks 3", "obs": "Missing author citation.", "status": "LC", "comment": "Missing author citation.",
         "uid": "NHMO-BOT-1004", "prob_desc": "Author citation missing", "rev": False, "bld": "Økern", "fl": "1", "cab": "B-04", "shelf": "2",
         "probs": {"Author_Problem": True}},

        # 1005: Missing Species (Problem Queue trigger)
        {"id": 1005, "var": "", "genus": "Betula", "sp": "", "auth": "", "fam": "Betulaceae",
         "high_class": "Plantae; Magnoliopsida; Fagales; Betulaceae", "n_part": "Bjørk kvist", "part": "Twig",
         "col": "Ove Dahl", "col_nr": "D-112", "date": "1896-05-30", "place": "Alta",
         "box": "Boks 2", "obs": "Species epithet omitted on tag.", "status": "NE", "comment": "Refer to archival ledger.",
         "uid": "NHMO-BOT-1005", "prob_desc": "Missing species", "rev": False, "bld": "Lid's hus", "fl": "2", "cab": "C-14", "shelf": "1",
         "probs": {"Species_Problem": True}},

        # 1006: Clean record (Salix caprea)
        {"id": 1006, "var": "", "genus": "Salix", "sp": "caprea", "auth": "L.", "fam": "Salicaceae",
         "high_class": "Plantae; Magnoliopsida; Malpighiales; Salicaceae", "n_part": "Selje rakler", "part": "Catkin",
         "col": "M.N. Blytt", "col_nr": "231", "date": "1852-04-28", "place": "Christiania, Bygdøy",
         "box": "Boks 4", "obs": "Male catkins well preserved.", "status": "LC", "comment": "",
         "uid": "NHMO-BOT-1006", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "1", "cab": "A-01", "shelf": "2", "probs": {}},

        # 1007: Typo Genus 'Betulla' (Problem Queue + GBIF)
        {"id": 1007, "var": "var. pubescens", "genus": "Betulla", "sp": "pubescens", "auth": "Ehrh.", "fam": "Betulaceae",
         "high_class": "Plantae; Magnoliopsida; Fagales; Betulaceae", "n_part": "Dunbjørk blad", "part": "Leaf",
         "col": "Hjalmar Møller", "col_nr": "HM-09", "date": "1911-07-15", "place": "Tromsø",
         "box": "Boks 2", "obs": "Label reads Betulla with double l.", "status": "LC", "comment": "Spelling check needed.",
         "uid": "NHMO-BOT-1007", "prob_desc": "Double l typo in genus", "rev": False, "bld": "Lid's hus", "fl": "2", "cab": "C-14", "shelf": "3",
         "probs": {"Genus_Problem": True}},

        # 1008: Other problem (Physical box damage)
        {"id": 1008, "var": "", "genus": "Picea", "sp": "abies", "auth": "(L.) H.Karst.", "fam": "Pinaceae",
         "high_class": "Plantae; Pinopsida; Pinales; Pinaceae", "n_part": "Gran harpiks", "part": "Resin",
         "col": "J.M. Norman", "col_nr": "778", "date": "1885-09-01", "place": "Nordmarka, Oslo",
         "box": "Boks 5", "obs": "Glass container cracked.", "status": "LC", "comment": "Requires new storage vial.",
         "uid": "NHMO-BOT-1008", "prob_desc": "Storage vial cracked", "rev": False, "bld": "Lid's hus", "fl": "3", "cab": "D-08", "shelf": "1",
         "probs": {"Other_problem": True}},

        # 1009: Missing Author (Taxonomy Problem)
        {"id": 1009, "var": "", "genus": "Quercus", "sp": "robur", "auth": "", "fam": "Fagaceae",
         "high_class": "Plantae; Magnoliopsida; Fagales; Fagaceae", "n_part": "Sommereik nøtt", "part": "Acorn",
         "col": "Ove Dahl", "col_nr": "D-441", "date": "1905-10-12", "place": "Larvik, Bøkeskogen",
         "box": "Boks 6", "obs": "Acorns preserved in paper box.", "status": "LC", "comment": "Missing author citation.",
         "uid": "NHMO-BOT-1009", "prob_desc": "Missing author", "rev": False, "bld": "Økern", "fl": "1", "cab": "B-02", "shelf": "4",
         "probs": {"Author_Problem": True}},

        # 1010: Collector conflict with ledger
        {"id": 1010, "var": "", "genus": "Fraxinus", "sp": "excelsior", "auth": "L.", "fam": "Oleaceae",
         "high_class": "Plantae; Magnoliopsida; Lamiales; Oleaceae", "n_part": "Ask frø", "part": "Samara",
         "col": "Ove Dahl", "col_nr": "512", "date": "1899-09-22", "place": "Oslo, Hovedøya",
         "box": "Boks 7", "obs": "Winged seeds attached to twigs.", "status": "LC", "comment": "Historical ledger lists Blytt.",
         "uid": "NHMO-BOT-1010", "prob_desc": "Collector discrepancy with ledger", "rev": False, "bld": "Lid's hus", "fl": "1", "cab": "A-03", "shelf": "1",
         "probs": {"Collector_Problem": True}},

        # 1011: Collector Problem
        {"id": 1011, "var": "", "genus": "Populus", "sp": "tremula", "auth": "L.", "fam": "Salicaceae",
         "high_class": "Plantae; Magnoliopsida; Malpighiales; Salicaceae", "n_part": "Osp blad", "part": "Leaf",
         "col": "Unknown", "col_nr": "", "date": "1890-06-18", "place": "Gudbrandsdalen",
         "box": "Boks 4", "obs": "Collector name unreadable.", "status": "LC", "comment": "Illegible ink.",
         "uid": "NHMO-BOT-1011", "prob_desc": "Collector unknown", "rev": False, "bld": "Lid's hus", "fl": "1", "cab": "A-01", "shelf": "4",
         "probs": {"Collector_Problem": True}},

        # 1012: Typo Genus 'Salixx' (Problem Queue + GBIF)
        {"id": 1012, "var": "", "genus": "Salixx", "sp": "herbacea", "auth": "L.", "fam": "Salicaceae",
         "high_class": "Plantae; Magnoliopsida; Malpighiales; Salicaceae", "n_part": "Musøre dvergbusk", "part": "Whole plant",
         "col": "Gunnerus", "col_nr": "G-03", "date": "1767-08-01", "place": "Dovre, Snøhetta",
         "box": "Boks 8", "obs": "Pygmy willow pressed mount.", "status": "LC", "comment": "Archaic collection.",
         "uid": "NHMO-BOT-1012", "prob_desc": "Typo in genus Salixx", "rev": False, "bld": "Lid's hus", "fl": "3", "cab": "D-01", "shelf": "2",
         "probs": {"Genus_Problem": True}},

        # 1013: Clean record (Ulmus glabra)
        {"id": 1013, "var": "", "genus": "Ulmus", "sp": "glabra", "auth": "Huds.", "fam": "Ulmaceae",
         "high_class": "Plantae; Magnoliopsida; Rosales; Ulmaceae", "n_part": "Alm bark", "part": "Bark",
         "col": "J.M. Norman", "col_nr": "610", "date": "1882-05-12", "place": "Telemark, Skien",
         "box": "Boks 9", "obs": "Historical medicinal bark sample.", "status": "LC", "comment": "",
         "uid": "NHMO-BOT-1013", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "2", "cab": "C-05", "shelf": "3", "probs": {}},

        # 1014: Collection Date Problem
        {"id": 1014, "var": "", "genus": "Corylus", "sp": "avellana", "auth": "L.", "fam": "Betulaceae",
         "high_class": "Plantae; Magnoliopsida; Fagales; Betulaceae", "n_part": "Hassel nøtt", "part": "Nut",
         "col": "R.E. Fridtz", "col_nr": "902", "date": "", "place": "Kragerø",
         "box": "Boks 2", "obs": "Date missing on carton.", "status": "LC", "comment": "Year unknown.",
         "uid": "NHMO-BOT-1014", "prob_desc": "Date missing", "rev": False, "bld": "Lid's hus", "fl": "2", "cab": "C-14", "shelf": "2",
         "probs": {"Collection_Date_Problem": True}},

        # 1015: Typo Species 'sylvestriss'
        {"id": 1015, "var": "", "genus": "Pinus", "sp": "sylvestriss", "auth": "L.", "fam": "Pinaceae",
         "high_class": "Plantae; Pinopsida; Pinales; Pinaceae", "n_part": "Furu kvae", "part": "Resin",
         "col": "M.N. Blytt", "col_nr": "199", "date": "1848-06-11", "place": "Kongsvinger",
         "box": "Boks 1", "obs": "Typo in species epithet on herbarium sheet.", "status": "LC", "comment": "",
         "uid": "NHMO-BOT-1015", "prob_desc": "Species typo sylvestriss", "rev": False, "bld": "Lid's hus", "fl": "2", "cab": "C-12", "shelf": "2",
         "probs": {"Species_Problem": True}},

        # 1016: Clean record (Sorbus aucuparia)
        {"id": 1016, "var": "", "genus": "Sorbus", "sp": "aucuparia", "auth": "L.", "fam": "Rosaceae",
         "high_class": "Plantae; Magnoliopsida; Rosales; Rosaceae", "n_part": "Rogn bær", "part": "Berry",
         "col": "Ove Dahl", "col_nr": "D-305", "date": "1898-09-04", "place": "Hardanger, Ullensvang",
         "box": "Boks 10", "obs": "Dried berries in small tin.", "status": "LC", "comment": "",
         "uid": "NHMO-BOT-1016", "prob_desc": "", "rev": True, "bld": "Økern", "fl": "1", "cab": "B-09", "shelf": "1", "probs": {}},

        # 1017: Clean record (Acer platanoides)
        {"id": 1017, "var": "", "genus": "Acer", "sp": "platanoides", "auth": "L.", "fam": "Sapindaceae",
         "high_class": "Plantae; Magnoliopsida; Sapindales; Sapindaceae", "n_part": "Spisslønn blad", "part": "Leaf",
         "col": "Hjalmar Møller", "col_nr": "HM-77", "date": "1914-10-02", "place": "Kristiansand",
         "box": "Boks 11", "obs": "Autumn foliage mount.", "status": "LC", "comment": "",
         "uid": "NHMO-BOT-1017", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "1", "cab": "A-05", "shelf": "3", "probs": {}},

        # 1018: Family problem (incorrectly labeled Fagaceae instead of Betulaceae)
        {"id": 1018, "var": "", "genus": "Alnus", "sp": "incana", "auth": "(L.) Moench", "fam": "Fagaceae",
         "high_class": "Plantae; Magnoliopsida; Fagales; Betulaceae", "n_part": "Gråor kongler", "part": "Catkin",
         "col": "J.M. Norman", "col_nr": "415", "date": "1880-04-10", "place": "Trondheim, Lade",
         "box": "Boks 2", "obs": "Old label incorrectly marked Fagaceae.", "status": "LC", "comment": "Family needs update to Betulaceae.",
         "uid": "NHMO-BOT-1018", "prob_desc": "Family is Betulaceae not Fagaceae", "rev": False, "bld": "Lid's hus", "fl": "2", "cab": "C-14", "shelf": "4",
         "probs": {"Family_Problem": True}},

        # 1019: Clean record (Tilia cordata)
        {"id": 1019, "var": "", "genus": "Tilia", "sp": "cordata", "auth": "Mill.", "fam": "Malvaceae",
         "high_class": "Plantae; Magnoliopsida; Malvales; Malvaceae", "n_part": "Lind blomster", "part": "Flower",
         "col": "M.N. Blytt", "col_nr": "389", "date": "1855-07-20", "place": "Oslo, Malmøya",
         "box": "Boks 12", "obs": "Inflorescence with bract.", "status": "LC", "comment": "Fragrant sample.",
         "uid": "NHMO-BOT-1019", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "1", "cab": "A-07", "shelf": "2", "probs": {}},

        # 1020: Archaic locality conflict with historical books
        {"id": 1020, "var": "", "genus": "Taxus", "sp": "baccata", "auth": "L.", "fam": "Taxaceae",
         "high_class": "Plantae; Pinopsida; Pinales; Taxaceae", "n_part": "Barlind nåler og ved", "part": "Wood",
         "col": "R.E. Fridtz", "col_nr": "1002", "date": "1908-03-15", "place": "Oslo, Tøyen",
         "box": "Boks 13", "obs": "Wood cross-section.", "status": "NT", "comment": "Ledger specifies Christiania Botanisk Have.",
         "uid": "NHMO-BOT-1020", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "3", "cab": "D-05", "shelf": "1", "probs": {}},

        # 1021: Missing Author citation
        {"id": 1021, "var": "", "genus": "Juniperus", "sp": "communis", "auth": "", "fam": "Cupressaceae",
         "high_class": "Plantae; Pinopsida; Pinales; Cupressaceae", "n_part": "Einer bær", "part": "Cone",
         "col": "Ove Dahl", "col_nr": "D-601", "date": "1901-08-29", "place": "Valdres, Fagernes",
         "box": "Boks 14", "obs": "Fleshy cones.", "status": "LC", "comment": "Author missing.",
         "uid": "NHMO-BOT-1021", "prob_desc": "Author citation missing", "rev": False, "bld": "Lid's hus", "fl": "3", "cab": "D-05", "shelf": "3",
         "probs": {"Author_Problem": True}},

        # 1022: Clean record (Prunus padus)
        {"id": 1022, "var": "", "genus": "Prunus", "sp": "padus", "auth": "L.", "fam": "Rosaceae",
         "high_class": "Plantae; Magnoliopsida; Rosales; Rosaceae", "n_part": "Hegg blomster", "part": "Flower",
         "col": "Hjalmar Møller", "col_nr": "HM-120", "date": "1916-05-24", "place": "Lillehammer",
         "box": "Boks 10", "obs": "Pressed racemes.", "status": "LC", "comment": "",
         "uid": "NHMO-BOT-1022", "prob_desc": "", "rev": True, "bld": "Økern", "fl": "1", "cab": "B-09", "shelf": "2", "probs": {}},

        # 1023: Clean record (Larix decidua)
        {"id": 1023, "var": "", "genus": "Larix", "sp": "decidua", "auth": "Mill.", "fam": "Pinaceae",
         "high_class": "Plantae; Pinopsida; Pinales; Pinaceae", "n_part": "Lerk kongler", "part": "Cone",
         "col": "J.M. Norman", "col_nr": "850", "date": "1889-10-05", "place": "Bergen, Fløyen",
         "box": "Boks 1", "obs": "Small cones attached to dwarf shoots.", "status": "LC", "comment": "",
         "uid": "NHMO-BOT-1023", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "2", "cab": "C-12", "shelf": "3", "probs": {}},

        # 1024: Clean record (Ribes nigrum)
        {"id": 1024, "var": "", "genus": "Ribes", "sp": "nigrum", "auth": "L.", "fam": "Grossulariaceae",
         "high_class": "Plantae; Magnoliopsida; Saxifragales; Grossulariaceae", "n_part": "Solbær blad", "part": "Leaf",
         "col": "M.N. Blytt", "col_nr": "477", "date": "1858-07-03", "place": "Drammen",
         "box": "Boks 15", "obs": "Dried leaves with resinous glands.", "status": "LC", "comment": "",
         "uid": "NHMO-BOT-1024", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "1", "cab": "A-09", "shelf": "1", "probs": {}},

        # 1025: Clean record (Sambucus nigra)
        {"id": 1025, "var": "", "genus": "Sambucus", "sp": "nigra", "auth": "L.", "fam": "Adoxaceae",
         "high_class": "Plantae; Magnoliopsida; Dipsacales; Adoxaceae", "n_part": "Svarthyll marg", "part": "Pith",
         "col": "Ove Dahl", "col_nr": "D-730", "date": "1904-06-19", "place": "Tønsberg",
         "box": "Boks 16", "obs": "White stem pith sticks.", "status": "LC", "comment": "",
         "uid": "NHMO-BOT-1025", "prob_desc": "", "rev": True, "bld": "Lid's hus", "fl": "1", "cab": "A-09", "shelf": "4", "probs": {}},
    ]

    # Build df_reg
    reg_rows = []
    obs_rows = []
    photo_rows = []

    for sp in specimens:
        oid = sp["id"]
        reg_rows.append({
            "ObjectID": oid,
            "Variant": sp["var"],
            "Genus": sp["genus"],
            "Species": sp["sp"],
            "Author": sp["auth"],
            "Family": sp["fam"],
            "Higher Classification": sp["high_class"],
            "(N) Plant Part": sp["n_part"],
            "Plant Part": sp["part"],
            "Collector": sp["col"],
            "Innsammling Nr.": sp["col_nr"],
            "Collection Date": sp["date"],
            "Collection Place": sp["place"],
            "Box Label": sp["box"],
            "Observation": sp["obs"],
            "Conservation Status": sp["status"],
            "Comment": sp["comment"],
            "UID": sp["uid"],
            "ProblemDescription": sp["prob_desc"],
            "Online photo 1": f"https://www.unimus.no/photos/image/jpeg/O-V-OE-{oid}.jpg",
            "Online photo 2": "",
            "Online photo 3": ""
        })

        # Observation row
        p = sp["probs"]
        obs_rows.append({
            "ObjectID": oid,
            "Reviewed": sp["rev"],
            "ReviewedAt": "2026-09-01 10:00:00" if sp["rev"] else "",
            "Stored as": "in paper box" if "box" in sp["part"].lower() or oid % 2 == 0 else "Mounted on wooded platform",
            "Floor": sp["fl"],
            "Cabinet": sp["cab"],
            "Extra": f"Drawer {sp['shelf']}",
            "Building": sp["bld"],
            "Loaned out": False,
            "Loaned out date": "",
            "Genus_Problem": p.get("Genus_Problem", False),
            "Species_Problem": p.get("Species_Problem", False),
            "Family_Problem": p.get("Family_Problem", False),
            "Author_Problem": p.get("Author_Problem", False),
            "PlantPart_Problem": p.get("PlantPart_Problem", False),
            "Collector_Problem": p.get("Collector_Problem", False),
            "Collection_Date_Problem": p.get("Collection_Date_Problem", False),
            "Collection_Place_Problem": p.get("Collection_Place_Problem", False),
            "Box_Label_Problem": p.get("Box_Label_Problem", False),
            "Images_Problem": p.get("Images_Problem", False),
            "Other_problem": p.get("Other_problem", False),
        })

        # Photo row
        photo_rows.append({
            "ObjectID": oid,
            "Filename": f"O-V-OE-{oid}.jpg"
        })

    df_reg = pd.DataFrame(reg_rows)
    df_obs = pd.DataFrame(obs_rows)
    df_photo = pd.DataFrame(photo_rows)
    df_log = pd.DataFrame(columns=["ObjectID", "Timestamp", "User", "Action", "ChangedFields", "ChangedValues", "Details"])

    with pd.ExcelWriter(current_db_path, engine="openpyxl") as writer:
        df_reg.to_excel(writer, sheet_name="Registration", index=False)
        df_obs.to_excel(writer, sheet_name="Observation", index=False)
        df_photo.to_excel(writer, sheet_name="Photo", index=False)
        df_log.to_excel(writer, sheet_name="Log", index=False)

    print(f"Generated {current_db_path} with {len(df_reg)} records.")

    # -------------------------------------------------------------
    # 2. Historical Books Archival Database (mock_historical_books.xlsx)
    # -------------------------------------------------------------
    # Contains historical entries with both exact matches and deliberate discrepancies
    hist_entries = [
        # 1001: Exact match with current DB
        {"ObjectID": 1001, "Genus": "Pinus", "Species": "sylvestris", "Family": "Pinaceae", "Author": "L.",
         "Plant Part": "Cone", "Collector": "M.N. Blytt", "Innsammling Nr.": "104", "Collection Date": "1845-07-12",
         "Collection Place": "Oslo, Tøyen", "Box Label": "Boks 1", "Conservation Status": "LC"},

        # 1002: Exact match with current DB
        {"ObjectID": 1002, "Genus": "Betula", "Species": "pendula", "Family": "Betulaceae", "Author": "Roth",
         "Plant Part": "Bark", "Collector": "Ove Dahl", "Innsammling Nr.": "D-89", "Collection Date": "1894-06-20",
         "Collection Place": "Kongsberg", "Box Label": "Boks 2", "Conservation Status": "LC"},

        # 1003: Corrects typo 'Pinuss' -> 'Pinus'
        {"ObjectID": 1003, "Genus": "Pinus", "Species": "mugo", "Family": "Pinaceae", "Author": "Turra",
         "Plant Part": "Twig", "Collector": "J.M. Norman", "Innsammling Nr.": "N-12", "Collection Date": "1888-08-05",
         "Collection Place": "Røros", "Box Label": "Boks 1", "Conservation Status": "LC"},

        # 1004: Provides missing Author 'Mill.' (Abies alba Mill.)
        {"ObjectID": 1004, "Genus": "Abies", "Species": "alba", "Family": "Pinaceae", "Author": "Mill.",
         "Plant Part": "Needles", "Collector": "R.E. Fridtz", "Innsammling Nr.": "542", "Collection Date": "1902-09-14",
         "Collection Place": "Dovrefjell, Kongsvold", "Box Label": "Boks 3", "Conservation Status": "LC"},

        # 1005: Provides missing Species 'pendula'
        {"ObjectID": 1005, "Genus": "Betula", "Species": "pendula", "Family": "Betulaceae", "Author": "Roth",
         "Plant Part": "Twig", "Collector": "Ove Dahl", "Innsammling Nr.": "D-112", "Collection Date": "1896-05-30",
         "Collection Place": "Alta", "Box Label": "Boks 2", "Conservation Status": "LC"},

        # 1007: Corrects typo 'Betulla' -> 'Betula'
        {"ObjectID": 1007, "Genus": "Betula", "Species": "pubescens", "Family": "Betulaceae", "Author": "Ehrh.",
         "Plant Part": "Leaf", "Collector": "Hjalmar Møller", "Innsammling Nr.": "HM-09", "Collection Date": "1911-07-15",
         "Collection Place": "Tromsø", "Box Label": "Boks 2", "Conservation Status": "LC"},

        # 1010: Discrepancy in Collector ('M.N. Blytt' in ledger vs 'Ove Dahl' in current)
        {"ObjectID": 1010, "Genus": "Fraxinus", "Species": "excelsior", "Family": "Oleaceae", "Author": "L.",
         "Plant Part": "Samara", "Collector": "M.N. Blytt", "Innsammling Nr.": "512", "Collection Date": "1899-09-22",
         "Collection Place": "Oslo, Hovedøya", "Box Label": "Boks 7", "Conservation Status": "LC"},

        # 1012: Corrects typo 'Salixx' -> 'Salix'
        {"ObjectID": 1012, "Genus": "Salix", "Species": "herbacea", "Family": "Salicaceae", "Author": "L.",
         "Plant Part": "Whole plant", "Collector": "Gunnerus", "Innsammling Nr.": "G-03", "Collection Date": "1767-08-01",
         "Collection Place": "Dovre, Snøhetta", "Box Label": "Boks 8", "Conservation Status": "LC"},

        # 1015: Corrects typo 'sylvestriss' -> 'sylvestris'
        {"ObjectID": 1015, "Genus": "Pinus", "Species": "sylvestris", "Family": "Pinaceae", "Author": "L.",
         "Plant Part": "Resin", "Collector": "M.N. Blytt", "Innsammling Nr.": "199", "Collection Date": "1848-06-11",
         "Collection Place": "Kongsvinger", "Box Label": "Boks 1", "Conservation Status": "LC"},

        # 1020: Locality archaic toponym ('Christiania, Botanisk Have' vs 'Oslo, Tøyen')
        {"ObjectID": 1020, "Genus": "Taxus", "Species": "baccata", "Family": "Taxaceae", "Author": "L.",
         "Plant Part": "Wood", "Collector": "R.E. Fridtz", "Innsammling Nr.": "1002", "Collection Date": "1908-03-15",
         "Collection Place": "Christiania, Botanisk Have", "Box Label": "Boks 13", "Conservation Status": "NT"},

        # 1021: Provides missing Author 'L.'
        {"ObjectID": 1021, "Genus": "Juniperus", "Species": "communis", "Family": "Cupressaceae", "Author": "L.",
         "Plant Part": "Cone", "Collector": "Ove Dahl", "Innsammling Nr.": "D-601", "Collection Date": "1901-08-29",
         "Collection Place": "Valdres, Fagernes", "Box Label": "Boks 14", "Conservation Status": "LC"},
    ]

    df_hist = pd.DataFrame(hist_entries)

    with pd.ExcelWriter(historical_books_path, engine="openpyxl") as writer:
        df_hist.to_excel(writer, sheet_name="Ledger_1890", index=False)

    print(f"Generated {historical_books_path} with {len(df_hist)} historical records across sheet 'Ledger_1890'.")

if __name__ == "__main__":
    generate_parity_data()
