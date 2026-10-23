# codebase_guide.md

This document serves as a guide to help you understand the architecture of the **arbor** application, how the user interface (UI) is built up, and how you can easily edit it without losing any features.

---

## 1. System Architecture Map

The application is written in Python using the standard library **Tkinter** for UI layout, and **Pandas** + **Openpyxl** to read and write Excel databases. It consists of the following modules and files:

### Root Directory
*   `main.py`: Application entry point & DPI config.
*   `config.py`: Global scaling, preferences, and database schemas.
*   `models.py`: Local database state and filters representation.
*   `repository.py`: Read/write connector interfacing with Excel databases and SQLite.
*   `utils.py`: Common visual and error logger helper functions.
*   `conftest.py`: Pytest configuration for the test suite.
*   `resolve.py`: Helper script for resolving git conflicts in specific files.
*   `async_test.py`: Standalone script for testing async / Tkinter behaviors.

### `backend/` Directory (Core Logic and Services)
*   `__init__.py`: Package initialization.
*   `filter.py`: Filtering logic for dataframes based on user input.
*   `search.py`: Search engine for caching and rapidly matching object data.
*   `gbif.py`: GBIF API integration for taxonomic verification.
*   `mobile_server.py`: Flask-based local web server for the mobile companion app.
*   `mobile_scanner.py`: Archived mobile barcode scanner functionality.
*   `tunnel.py`: Pinggy tunnel management to expose the local mobile server online.

### `ui/` Directory (User Interface and Popups)
*   `__init__.py`: Package initialization.
*   `main_window.py`: The main workspace window layout (primary application UI).
*   `dialogs.py`: General dialogue popups (zoomable image, startup dialog, etc.).
*   `tutorial.py`: Interactive walkthrough overlays.
*   `bulk_edit.py`: Bulk Excel modification windows.
*   `group_editor.py`: Group taxonomy customization manager.
*   `historical_resolver.py`: Version discrepancy resolution UI.
*   `historical_suggestions.py`: Suggestions for autocomplete from historical data.
*   `new_database_wizard.py`: Layout setup wizard for new database sheets.
*   `add_objects.py`: Window for appending new objects to the database.
*   `advanced_settings.py`: Advanced technical and behavior settings UI.
*   `unified_settings.py`: The central hub for all settings menus.
*   `settings_old.py`: Archived legacy settings components.
*   `layout_settings.py`: UI layout preferences mixin.
*   `dashboard.py`: Statistics dashboard and overview logic.
*   `database_ops.py`: Mixin for handling database load/save UI interactions.
*   `autosave_handler.py`: Background autosave mechanisms.
*   `gbif_dialog.py`: Dialog for reviewing and applying GBIF updates.
*   `image_handler.py`: Image loading, caching, and gallery manipulation mixin.
*   `image_toolbar.py`: Design component for image controls (zoom/rotate tools).
*   `location_panel.py`: Standalone location panel UI layout.
*   `log_viewer.py`: Helper mixin to launch log viewing windows.
*   `recent_activity_dialog.py`: UI for viewing recent edits and application logs.
*   `mobile_dialog.py`: Toplevel dialog that wraps the mobile companion UI in-app.
*   `mobile_host_app.py`: Standalone window for the mobile companion without the main app.
*   `mobile_panel.py`: Shared UI panel for the mobile companion server controls.
*   `widgets.py`: Reusable, customized Tkinter widgets (e.g., ToggleSwitch, InfoButton).

---

## 2. Deep Dive: ui/main_window.py

This file builds the main user workspace. It is structured into multiple layers using Tkinter packing. Here is the visual breakdown of the layout layers:

```text
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
```

### Key UI Subsections inside ui/main_window.py:

*   **build_ui()** (around line 3637): Organizes the container frames, grid columns, status bar, and binds global keyboard shortcuts.
*   **build_sections()** (around line 1128): Dynamically creates input fields (Entry boxes, Multiline text boxes, and Dropdowns) based on the schemas defined in `config.py`.
*   **_toggle_reviewed_for_id()**: Toggles checkmark status of selected object IDs, triggering visual indicators.
*   **Keyboard Hotkeys**: Binds common physical navigation controls for review efficiency:
    *   Spacebar: Check/uncheck problem indicators.
    *   Ctrl + Return or Ctrl + R: Mark current object as Reviewed.
    *   Left Arrow / Right Arrow: Go to the previous/next museum object.

---

## 3. Dynamic Configuration (config.py)

All visual fields shown in the program are loaded dynamically from schemas. For example, if you look at DATABASE_CONFIGS in `config.py`, fields are categorized under sections:

1.  **registration**: General text labels, notes, comment textboxes, or admin metadata.
2.  **location**: Dropdowns or boxes specifying buildings, rooms, floor shelves, and loan status.
3.  **problems**: Checklist of issues mapping directly to fields (e.g., Genus_Problem maps to the Genus text field, highlighting it yellow when checked).

This allows you to add or modify data fields simply by updating lists in `config.py` without touching the Python UI source code.
