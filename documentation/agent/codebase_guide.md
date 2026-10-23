# codebase_guide.md

This document serves as a guide to help you understand the architecture of the **arbor** application, how the user interface (UI) is built up, and how you can easily edit it without losing any features.

---

## 1. System Architecture Map

The application is written in Python using the standard library **Tkinter** for UI layout, and **Pandas** + **Openpyxl** to read and write Excel databases. It consists of the following files:

`
.
├── main.py               # Application entry point & DPI config
├── config.py             # Global scaling, preferences, and database schemas
├── models.py             # Local database state and filters representation
├── repository.py         # Read/write connector interfacing with Excel files
├── utils.py              # Common visual and error logger helper functions
├── backend/              # Mobile companion app, search, and external integrations
│   ├── mobile_server.py  # Flask server and UI templates for mobile editing
│   ├── search.py         # Core search and filtering functionality
│   └── tunnel.py         # Local tunnel orchestration
└── ui/                   # UI layout and popups folder
    ├── main_window.py    # The main workspace window layout (primary layout)
    ├── dialogs.py        # Various dialog popups (startup, GBIF, etc.)
    ├── unified_settings.py # Settings dashboard and preferences configuration
    ├── dashboard.py      # Database overview and statistics dashboard
    ├── widgets.py        # Reusable custom UI components (buttons, scroll frames)
    └── ...               # Additional modules for features (bulk_edit, logs, etc.)
`

---

## 2. Deep Dive: ui/main_window.py

This file builds the main user workspace. It is structured into multiple layers using Tkinter packing. Here is the visual breakdown of the layout layers:

`
+-------------------------------------------------------------------------+
| Layer 1: App Title & Navigation Link Buttons (top)                      |
+-------------------------------------------------------------------------+
|                                                                         |
|  +---------------------+  +------------------------------------------+  |
|  | Layer 2: Left Pane  |  | Layer 3: Central Workspace Panel         |  |
|  |                     |  |                                          |  |
|  | - Live Search bar   |  |  +--------------------+---------------+  |  |
|  | - Object List tree  |  |  | Taxonomy Tabs Panel | Image Panel   |  |  |
|  |   (Rev | ID | Genus)|  |  |                     | (Gallery/     |  |  |
|  | - Filter presets    |  |  | - Genus / Species   |  Stack mode)  |  |  |
|  |                     |  |  | - Collection dates  | - Rotation &  |  |  |
|  |                     |  |  | - Comments / Notes  |   Zoom tools  |  |  |
|  |                     |  |  |                     |               |  |  |
|  |                     |  |  +--------------------+---------------+  |  |
|  |                     |  |  | Stored Location & Checkbox Problems   |  |  |
|  |                     |  |  | Container Panel (bottom)              |  |  |
|  +---------------------+  +------------------------------------------+  |
|                                                                         |
+-------------------------------------------------------------------------+
| Layer 4: Global Status Bar & Stats (bottom)                             |
+-------------------------------------------------------------------------+
`

### Key UI Subsections inside ui/main_window.py:

*   **build_ui()** (around line 3637): Organizes the container frames, grid columns, status bar, and binds global keyboard shortcuts.
*   **build_sections()** (around line 1128): Dynamically creates input fields (Entry boxes, Multiline text boxes, and Dropdowns) based on the schemas defined in config.py.
*   **_toggle_reviewed_for_id()**: Toggles checkmark status of selected object IDs, triggering visual indicators.
*   **Keyboard Hotkeys**: Binds common physical navigation controls for review efficiency:
    *   Spacebar: Check/uncheck problem indicators.
    *   Ctrl + Return or Ctrl + R: Mark current object as Reviewed.
    *   Left Arrow / Right Arrow: Go to the previous/next museum object.

---

## 3. Dynamic Configuration (config.py)

All visual fields shown in the program are loaded dynamically from schemas. For example, if you look at DATABASE_CONFIGS in config.py, fields are categorized under sections:

1.  **egistration**: General text labels, notes, comment textboxes, or admin metadata.
2.  **location**: Dropdowns or boxes specifying buildings, rooms, floor shelves, and loan status.
3.  **problems**: Checklist of issues mapping directly to fields (e.g., Genus_Problem maps to the Genus text field, highlighting it yellow when checked).

This allows you to add or modify data fields simply by updating lists in config.py without touching the Python UI source code.
