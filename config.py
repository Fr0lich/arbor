# =====================
# UI SCALE (DPI)
# =====================
# Set at startup in main.py based on screen DPI.
# Use sc(n) everywhere instead of raw pixel/font sizes.
UI_SCALE = 1.0
ENABLE_TUTORIALS = True
_detected_scale = 1.0  # Overwritten at startup with the actual detected DPI ratio
_PREFS_PATH = "user_prefs.json"  # Overwritten at startup with the correct exe-relative path

import os
import json
import sys
from datetime import datetime

def get_system_theme():
    """Detect platform and return system theme name."""
    if sys.platform.startswith("win"):
        return "vista"
    elif sys.platform.startswith("darwin"):
        return "aqua"
    else:
        return "clam"

def get_theme():
    """Get the current theme to use (defaulting to 'clam' for now)."""
    # Defaults to clam as per requirements, but can easily be switched to get_system_theme()
    return "clam"


# In-memory prefs cache — populated on first read, invalidated on write.
_prefs_cache = None

def load_prefs():
    global _prefs_cache
    if _prefs_cache is not None:
        return _prefs_cache
    if os.path.exists(_PREFS_PATH):
        try:
            with open(_PREFS_PATH, "r", encoding="utf-8") as f:
                _prefs_cache = json.load(f)
                return _prefs_cache
        except Exception:
            pass
    _prefs_cache = {}
    return _prefs_cache

def save_prefs(prefs):
    global _prefs_cache
    _prefs_cache = prefs  # keep cache in sync before writing
    try:
        with open(_PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass

def get_last_dir(key):
    return load_prefs().get(key, "")

def set_last_dir(key, path):
    if not path:
        return
    directory = os.path.dirname(path) if os.path.isfile(path) else path
    prefs = load_prefs()
    prefs[key] = directory
    save_prefs(prefs)

def get_recent_files():
    """Return list of recent file dicts: [{"path": str, "modified": str}, ...]"""
    return load_prefs().get("recent_files", [])

def add_recent_file(path):
    """Add or refresh a file entry in recent_files (max 8, newest first)."""
    if not path or not os.path.exists(path):
        return
    try:
        mtime = os.path.getmtime(path)
        modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except Exception:
        modified = ""
    prefs = load_prefs()
    recent = [r for r in prefs.get("recent_files", []) if r.get("path") != path]
    recent.insert(0, {"path": path, "modified": modified})
    prefs["recent_files"] = recent[:8]
    save_prefs(prefs)

def sc(n):
    """Scale a pixel or font size by the current UI scale factor."""
    return max(1, int(n * UI_SCALE))

# =====================
# AUTOSAVE SETTINGS
# =====================
AUTOSAVE_INTERVAL_MS = 2 * 60 * 1000   # 2 minutes — change here or via Settings menu
# PERFORMANCE OPTIMIZATION (Bolt): Use .autosave.json for safer and fast serialization of active session state.
AUTOSAVE_SUFFIX = ".autosave.json"


# =====================
# DATABASE CONFIGS
# =====================

DATABASE_CONFIGS = {

    "Økonomisk Botanisk": {

        # ---------------------
        # GENERELT
        # ---------------------
        "has_images": True,
        "image_url_pattern": "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg",

        "sheets": {
            "reg": "Registration",
            "obs": "Observation",
            "photo": "Photo",
            "log": "Log",
        },

        # ---------------------
        # HISTORICAL DATA / BOOKS
        # ---------------------
        "books_columns": [
            "ObjectID",
            "Genus",
            "Species",
            "Family",
            "Author",
            "Plant Part",
            "Collector",
            "Innsammling Nr.",
            "Collection Date",
            "Collection Place",
            "Box Label",
            "Conservation Status"
        ],

        # ---------------------
        # UI STRUKTUR (NY MODELL)
        # ---------------------
        "ui_sections": {

            # -------- REGISTRATION --------
            "registration": [
                {"name": "Variant", "type": "text"},
                {"name": "Genus", "type": "text"},
                {"name": "Species", "type": "text"},
                {"name": "Author", "type": "text"},
                {"name": "Family", "type": "text"},
                {"name": "Higher Classification", "type": "text"},

                {"name": "(N) Plant Part", "type": "text"},
                {"name": "Plant Part", "type": "text"},

                {"name": "Collector", "type": "text"},
                {"name": "Innsammling Nr.", "type": "text"},

                {"name": "Collection Date", "type": "text"},
                {"name": "Collection Place", "type": "text"},

                {"name": "Box Label", "type": "text"},

                # ✅ multiline example
                {"name": "Observation", "type": "multiline"},

                {"name": "Conservation Status", "type": "text"},

                {"name": "Comment", "type": "multiline"},

                # ✅ låst felt
                {"name": "UID", "type": "text", "readonly": True},

                {"name": "ProblemDescription", "type": "multiline"}
            ],

            "reg_groups": [
                { "name": "Taxonomy", "fields": ["Genus", "Species", "Author", "Family", "Higher Classification"] },
                { "name": "Collection", "fields": ["Collector", "Innsammling Nr.", "Collection Date", "Collection Place"] },
                { "name": "Object", "fields": ["Variant", "(N) Plant Part", "Plant Part", "Box Label", "Conservation Status"] },
                { "name": "Notes", "fields": ["Observation", "Comment", "ProblemDescription"] },
                { "name": "Admin", "fields": ["UID"] }
            ],

            # -------- LOCATION --------
            "location": [
                {
                    "name": "Stored as",
                    "type": "choice",
                    "choices": [
                        "Mounted on wooded platform",
                        "Petridish",
                        "in plastic box",
                        "in paper box",
                        "Free standing",
                        "in plastic bag"
                    ]
                },
                {
                    "name": "Floor",
                    "type": "choice",
                    "choices": [
                        "4",
                        "3",
                        "2",
                        "1",
                        "-1",
                        "-2",
                    ]
                },

                {"name": "Cabinet", "type": "text"},
                {"name": "Extra", "type": "text"},
                {
                    "name": "Building",
                    "type": "choice",
                    "choices": [
                        "Lid's hus",
                        "Økern",
                        "Annet",
                    ]
                },
                {
                    "name": "Loaned out",
                    "type": "checkbox"
                },
                {
                    "name": "Loaned out date",
                    "type": "text",
                    "readonly": True
                },
            ], 

            # -------- PROBLEMS --------
            "problems": [
                {
                    "name": "Genus_Problem",
                    "type": "bool",
                    "maps_to": "Genus"
                },
                {
                    "name": "Species_Problem",
                    "type": "bool",
                    "maps_to": "Species"
                },
                {
                    "name": "Family_Problem",
                    "type": "bool",
                    "maps_to": "Family"
                },
                {
                    "name": "Author_Problem",
                    "type": "bool",
                    "maps_to": "Author"
                },

                {
                    "name": "PlantPart_Problem",
                    "type": "bool",
                    "maps_to": "Plant Part"
                },

                
                {
                    "name": "Collector_Problem",
                    "type": "bool",
                    "maps_to": "Collector"
                },
                {
                    "name": "Collection_Date_Problem",
                    "type": "bool",
                    "maps_to": "Collection Date"
                },
                {
                    "name": "Collection_Place_Problem",
                    "type": "bool",
                    "maps_to": "Collection Place"
                },

                {
                    "name": "Box_Label_Problem",
                    "type": "bool",
                    "maps_to": "Box Label"
                },

                {
                    "name": "Images_Problem",
                    "type": "bool"
                },
                {
                    "name": "Other_problem",
                    "type": "bool",
                    "maps_to": "Other"
                }

 
               
            ],

            # -------- UNKNOWN FIELDS --------
            "unknown_fields": [
                {
                  "name": "Unknown_Collector",
                  "maps_to": "Collector"
                },
                {
                  "name": "Unknown_Collection_Date",
                  "maps_to": "Collection Date"
                },
                {
                  "name": "Unknown_Collection_Place",
                  "maps_to": "Collection Place"
                }
            ]
        }
    }
}