# codebase_guide.md

This document serves as a guide to help you understand the architecture of the **arbor** application, how the user interface (UI) is built up, and how you can easily edit it without losing any features.

---

## 1. System Architecture Map

The application is written in Python using the standard library **Tkinter** for UI layout, and **Pandas** + **Python-Calamine** / **Openpyxl** to read and write Excel databases. It consists of the following structure:

```
arbor/
├── main.py               # Application entry point, CLI framework selector & DPI config
├── config.py             # Global scaling, preferences, and database schemas
├── models.py             # Local database state (AppState) and thread locks (df_lock)
├── repository.py         # Read/write connector interfacing with Excel and SQLite files
├── utils.py              # Common visual, DDE sanitization, and error logger helper functions
├── backend/              # Core business engines (Search, Filter, GBIF, DwC, TaskQueue, MobileServer)
│   ├── search.py         # Rapid high-performance fuzzy search engine
│   ├── filter.py         # Multi-criteria filtering logic
│   ├── cross_validation.py # Taxonomy and ledger reconciliation rules
│   ├── gbif.py           # GBIF API client with LRU caching
│   ├── dwc_export.py     # Darwin Core Occurrence CSV exporter
│   ├── task_queue.py     # Centralized BackgroundWorker thread queue
│   ├── mobile_server.py  # Local Flask companion server with SSE and offline PWA
│   └── tunnel.py         # Secure local tunneling via Pinggy/Cloudflare
├── ui/                   # Active production Tkinter UI modules
│   ├── main_window.py    # Main workspace window layout coordinator
│   ├── command_palette.py# Universal Command Palette & Quick Switcher (Ctrl+K)
│   ├── toast.py          # Floating non-blocking status notifications
│   ├── unified_settings.py # Single settings dialog managing all configuration tabs
│   ├── image_panel.py    # High-resolution specimen image canvas, zoom, and rotation
│   ├── registry_panel.py # Botanical taxonomy input forms and ICEDIG context menus
│   ├── location_panel.py # Specimen physical location controls and storage format presets
│   ├── filter_dialog.py  # Advanced multi-criteria search and ledger query builder
│   ├── historical_resolver.py # Version and discrepancy resolution interface
│   ├── object_problem_resolver.py # Problem queue batch resolution workflow
│   ├── gbif_review.py    # GBIF backbone reconciliation dialog
│   ├── bulk_edit.py      # Batch object editing dialog
│   ├── group_editor.py   # Registration tab taxonomy customization manager
│   ├── new_database_wizard.py # Layout setup wizard for new databases
│   ├── keybindings.py    # Deduplicated, conflict-free keyboard shortcuts manager
│   ├── status_bar.py     # Compact telemetry strip (progress, count, autosave)
│   ├── navigation_bar.py # Top dropdown header menus
│   └── tutorials/        # Interactive walkthrough tutorial system in memory sandbox
└── archive/              # Preserved historical prototypes and deprecated exploratory code
```

---

## 2. Deep Dive: ui/main_window.py

This file coordinates the main user workspace. It is structured into multiple layers using Tkinter packing:

```
+-------------------------------------------------------------------------+
| Layer 1: App Header & Dropdown Navigation Bar (ui/navigation_bar.py)     |
| [FILE ▾] [SPECIMEN ▾] [🌿 AUDIT & TOOLS ▾] [VIEW ▾] [📱 MOBILE] [⚙] [❓] |
+-------------------------------------------------------------------------+
|                                                                         |
|  +---------------------+  +------------------------------------------+  |
|  | Layer 2: Left Pane  |  | Layer 3: Central Workspace Panel         |  |
|  | (Toggle via F6)     |  |                                          |  |
|  | - Fuzzy Search bar  |  |  +--------------------+---------------+  |  |
|  | - Object List tree  |  |  | Taxonomy Tabs Panel | Image Panel   |  |  |
|  |   (Rev | ID | Genus)|  |  | (Toggle via F7)    | (Toggle via   |  |  |
|  | - Filter presets    |  |  | - Genus / Species  |  F8)          |  |  |
|  |                     |  |  | - Collection dates | - Rotation &  |  |  |
|  |                     |  |  | - Comments / Notes |   Zoom tools  |  |  |
|  |                     |  |  +--------------------+---------------+  |  |
|  |                     |  |  | Stored Location & Checkbox Problems   |  |  |
|  |                     |  |  | Container Panel (bottom/center)       |  |  |
|  +---------------------+  +------------------------------------------+  |
|                                                                         |
+-------------------------------------------------------------------------+
| Layer 4: Compact Telemetry & Status Strip (ui/status_bar.py, 26px)       |
| [File: catalog.xlsx] [Record 42 of 1250] [Progress ■■■□□ 65%] [Saved]   |
+-------------------------------------------------------------------------+
```

### Key UI Subsections inside ui/main_window.py:

*   **`build_ui()`**: Organizes the container frames, grid columns, compact telemetry status bar, and binds global keyboard shortcuts via `KeybindingManager`.
*   **`build_sections()`**: Dynamically creates input fields (Entry boxes, Multiline text boxes, and Dropdowns) based on the schemas defined in `config.py`.
*   **Universal Command Palette (`ui/command_palette.py`)**: Bound to `Ctrl+K`, provides fuzzy command execution and direct specimen jumping.
*   **Floating Toasts (`ui/toast.py`)**: Non-blocking toast feedback pills for status confirmation.
*   **Darwin Core Exporter (`backend/dwc_export.py`)**: Exports datasets to standard Darwin Core occurrence files (`FILE ▾` -> `Export Darwin Core (CSV)...`).
*   **Unified Settings (`ui/unified_settings.py`)**: Single dialog managing all preferences, layouts, and the embedded Botanical Spelling Whitelist (`ignored_words.json`).
*   **`_toggle_reviewed_for_id()`**: Toggles checkmark status of selected object IDs, triggering visual indicators and toast feedback.
*   **Keyboard Hotkeys**: Binds common physical navigation controls for review efficiency:
    *   `Ctrl + K`: Universal Command Palette & quick switcher.
    *   `Ctrl + F`: Jump to instant search bar.
    *   `Ctrl + G`: Multi-criteria filter dialog (`Ctrl+Shift+F` for Historical & Books tab).
    *   `Spacebar`: Check/uncheck problem indicators.
    *   `Ctrl + Return` or `Ctrl + R`: Mark current object as Reviewed.
    *   `Left Arrow` / `Right Arrow`: Go to the previous/next museum object.
    *   `F6` / `F7` / `F8`: Toggle Left Directory / Right Registration / Middle Viewport panels.

---

## 3. Dynamic Configuration (config.py)

All visual fields shown in the program are loaded dynamically from schemas. For example, in `DATABASE_CONFIGS` in `config.py`, fields are categorized under sections:

1.  **registration**: General text labels, notes, comment textboxes, or admin metadata.
2.  **location**: Dropdowns or boxes specifying buildings, rooms, floor shelves, and loan status.
3.  **problems**: Checklist of issues mapping directly to fields (e.g., `Genus_Problem` maps to the `Genus` text field, highlighting it yellow when checked).

This allows curators to add or modify data fields simply by updating lists in `config.py` without modifying the core Python UI source code.

---

## 4. UI Directory & Architecture Roles

Arbor contains several UI directories from its development history. Future developers and AI assistants should understand their distinct roles:

### 1. ui/ (ACTIVE PRODUCTION)
* **Status**: Primary production interface.
* **Technology**: Python standard library **Tkinter** styled with Arbor design tokens (`documentation/agent/AI_UI_GUIDE.md`).
* **Entry Point**: `python main.py`.
* **Contents**: 43 active Python modules building the entire curatorial inspection system.

### 2. archive/ (PRESERVED ARCHIVE)
* **Status**: Preserved prototypes and retired test suites.
* **Contents**: `ui/mobile_conflict_resolver.py`, `ui/advanced_search.py`, `ui/advanced_settings.py`, `backend/mobile_scanner.py`, `stitch designs/`, and specialized unit tests (`test_advanced_settings.py`, `test_qt_advanced_search.py`). Documented in `archive/README.md`.

### 3. pyside_new_uis/ (COMPLETED PHASE 1 ASSET - 32 UI FILES)
* **Status**: Completed Phase 1 blueprint / future migration asset.
* **Technology**: Pure declarative Qt Designer XML (.ui files, Qt 4.0 schema).
* **Contents**: 32 files capturing 100% of Arbor's Tkinter windows with exact 1:1 layout, spatial padding, and visual tokens.
* **Validation**: All 32 files are validated by running `python scripts/verify_all_uis.py`.
* **Specification Registry**: Full widget object catalogs and constructor contracts are documented in `PYSIDE_UI_INTEGRATION_PIPELINE.md`.

### 4. ui_qt/ (EXPERIMENTAL / PROTOTYPE CONTROLLERS)
* **Status**: Early exploratory prototype controllers.
* **Contents**: Early PySide6 controllers created during initial tests. Kept as optional reference only.

### 5. qt designer/ (DEPRECATED / SUPERSEDED)
* **Status**: Superseded historical drafts. Completely superseded by `pyside_new_uis/`. Do not use for new work.
