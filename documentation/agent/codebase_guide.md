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
├── utils.py              # Common visual, DDE sanitization, and Loguru diagnostic engine (rotation, retention, async)
├── backend/              # Core business engines (Search, Filter, GBIF, TaskQueue, MobileServer, Updater)
│   ├── search.py         # Rapid high-performance fuzzy search engine
│   ├── filter.py         # Multi-criteria filtering logic
│   ├── cross_validation.py # Taxonomy and ledger reconciliation rules
│   ├── gbif.py           # GBIF API client with LRU caching
│   ├── task_queue.py     # Centralized BackgroundWorker thread queue
│   ├── mobile_server.py  # Local Flask companion server with SSE and offline PWA
│   ├── tunnel.py         # Secure local tunneling via Pinggy/Cloudflare
│   └── updater.py        # GitHub update engine, atomic PE swap, session preservation
├── data/                  # Packaged reference data and sample datasets
│   └── demo_collection.xlsx # Dedicated 220-specimen slice of the botanical collection for instant demo onboarding
├── ui/                   # Active production Tkinter UI modules
│   ├── main_window.py    # Main workspace window layout coordinator
│   ├── widgets.py        # Object list directory (TreeviewListboxWrapper) with dual view modes & O(1) diffing
│   ├── object_context_bar.py # Curatorial Command Strip (specimen context, botanical typography, status badge)
│   ├── action_rail.py    # Narrow collapsible sidebar rail and drawer toggle (◀ / ▶)
│   ├── dialogs.py        # Startup launcher dialog (StartupDialog) & splash loader (LoadingWindow)
│   ├── create_collection_dialog.py # Collection blueprint preview dialog & standard .xlsx creator
│   ├── image_popup.py    # Detached full-resolution image zoom and pan viewport
│   ├── update_dialog.py  # GitHub 1-click update dialog, progress telemetry, repo resilience
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
*   **Curatorial Command Strip (`ui/object_context_bar.py`)**: Sticky contextual specimen banner featuring monospace ID badge, real-time dataset counter (`42 of 1,250`), botanical name in *Lora* serif italics, clickable problem category badge launching resolvers, reactive amber `● Unsaved` dot, and archival action buttons.
*   **Specimen Directory & Virtual Cards (`ui/widgets.py`)**: `TreeviewListboxWrapper` supporting Compact Mode (4-column Treeview) and Detailed Mode (virtual cards). Implements single-badge discipline (`[ TAX ]`, `[ PROV ]`, `[ BOX ]`, etc.), inline bulleted metadata, and $O(1)$ targeted selection diffing (`last_highlighted ^ current_selected`).
*   **Virtual Card View Customization Lifecycle (`ui/widgets.py`, `ui/unified_settings.py`, `config.py`)**: Fully reactive presentation-layer preferences saved in `user_prefs["directory_card_display"]`. When altered via Unified Settings (Appearance tab), Command Palette (`Ctrl+K`), or Persona shortcuts, the coordinator invokes `wrapper.apply_directory_view_preferences(prefs)`. This clears cached card templates in `_card_pool`, flushes active windows, invalidates `_card_height = None`, triggers `_measure_card_height()`, and schedules an immediate viewport redraw. Zero backend schema, dataframe, or problem cache mutation occurs.
*   **Smooth Drawer Sashing & Easing**: 120ms cubic ease-out animation curve for sidebar collapse/expand, with width persistence (`prefs["sidebar_width"]`) and flicker-free post-transition unmapping.
*   **Universal Command Palette (`ui/command_palette.py`)**: Bound to `Ctrl+K`, provides fuzzy command execution and direct specimen jumping.
*   **Floating Toasts (`ui/toast.py`)**: Non-blocking toast feedback pills for status confirmation.
*   **Unified Settings (`ui/unified_settings.py`)**: Single dialog managing all preferences, layouts, and the embedded Botanical Spelling Whitelist (`ignored_words.json`).
*   **`_toggle_reviewed_for_id()`**: Toggles checkmark status of selected object IDs, triggering visual indicators and toast feedback.
*   **Keyboard Hotkeys**: Binds common physical navigation controls for review efficiency:
    *   `Ctrl + K`: Universal Command Palette & quick switcher.
    *   `Ctrl + F`: Jump to instant search bar.
    *   `Ctrl + G`: Multi-criteria filter dialog (`Ctrl+Shift+F` for Historical & Books tab).
    *   `Spacebar`: Check/uncheck problem indicators.
    *   `Ctrl + Return` or `Ctrl + R`: Mark current object as Reviewed.
    *   `Left Arrow` / `Right Arrow`: Go to the previous/next museum object.
    *   `Up Arrow` / `Down Arrow`: Step through directory with instant (0ms) context bar update and 50ms debounced media loading.
    *   `Ctrl + Up` / `Ctrl + Down`: Leap directly to previous/next specimen with active unresolved problem flags.
    *   `F6` / `F7` / `F8`: Toggle Left Directory / Right Registration / Middle Viewport panels.
    *   `Ctrl + O`: Toggle Left Directory drawer.
    *   *Note on Card Layout Profiles*: Card layouts (`Standard`, `Compact`, `Full Details`, `Minimalist`) are visual preferences configured via Settings (Appearance Tab with interactive Live Preview) or searchable through the Command Palette (`Ctrl+K`) without requiring dedicated physical shortcut keys.

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

---

## 5. Dependency & Packaging Architecture (Zero-Friction Deployment)

Arbor adheres to a **Zero-Friction, Offline-First** architecture designed for museum and institutional deployments:

### 1. Zero End-User Installation Burden
* The desktop application is distributed as a self-contained, portable Windows binary frozen using **PyInstaller** (`build_exe.bat`).
* End users (curators, digitizers) must never be required to install system runtimes, compilers, background services, or databases (no PostgreSQL, MySQL, Redis, Docker, Node.js, or npm).

### 2. Standard Pip Libraries Are Allowed & Encouraged
* Rather than hand-rolling fragile custom implementations of complex problems (e.g. fast Excel parsing, fuzzy text matching, structured validation, robust caching), developers and AI agents are encouraged to use mature, battle-tested Python libraries installed via `pip` and tracked in `requirements.txt`.
* Requirements for adopting a pip dependency:
  1. Must have pre-compiled Windows wheels available (zero C++ compilation required on target machines).
  2. Must bundle cleanly into PyInstaller without bloat.
  3. Must operate 100% offline without mandatory external cloud connections.
  4. Must be checked against the **Approved vs. Prohibited Library Checklist** in `AGENTS.md`. If not explicitly listed, the agent must ask the user for approval first.

### 3. Mobile Companion Zero-Build Stack
* The mobile companion backend is served by Flask directly from the desktop Python process.
* The mobile frontend is embedded directly in `backend/mobile_server.py` using strictly Vanilla HTML, modern JavaScript, and Tailwind CSS (via CDN).
* No npm, yarn, webpack, Vite, React, or frontend compilation steps are permitted.

---

## 6. Logging, Telemetry & Crash Diagnostics Architecture

Arbor utilizes **Loguru** for unified, thread-safe, lockless asynchronous logging:
* **Session Log Destination**: Handled automatically in `utils.py:get_session_log_path()` (`logs/arbor_{timestamp}.log`).
* **Rotation & Retention**:
  * `rotation="10 MB"`: Log files are automatically rotated when reaching 10 MB.
  * `retention="7 days"`: Logs older than 7 days are automatically purged to prevent curator workstation disk exhaustion.
  * `compression="zip"`: Rotated logs are compressed into ZIP format.
  * `enqueue=True`: Asynchronous writes handled on a dedicated background worker, eliminating main-thread disk I/O latency.
* **Crash & Traceback Capture**:
  * Unhandled Tkinter callback exceptions (`root.report_callback_exception` in `main.py`) and main-thread exceptions (`sys.excepthook`) are captured via `utils.debug_error()`.
  * `backtrace=True` and `diagnose=True` dump local variable contexts on unhandled crashes to accelerate post-mortem debugging.
  * `atexit.register(logger.complete)` guarantees all pending log messages flush to disk even during abrupt termination or Task Manager closure.

---

## 7. In-Memory Caching & State Management Architecture

To prevent unbounded memory growth during high-throughput cataloging shifts, Arbor uses **cachetools.LRUCache** containers across ephemeral caches:
* **Historical Suggestions Cache**: Managed in `ui/historical_suggestions.py` via `cachetools.LRUCache(maxsize=100)`. Automatic O(1) eviction replaces manual length checks.
* **Secondary Index Invalidation**: Cache invalidation is routed through `invalidate_history_cache(oid)` to purge compound tuple keys `(oid, show_all)` and numeric/string type variants without scanning or locking iterations.
* **Row-Dict & Filter Caching**: Core tabular row caches (`_cached_reg_dict`, `_cached_obs_dict`) remain encapsulated in `AppState` and are lazily rebuilt on data mutation flags (`_row_cache_dirty`), ensuring sub-millisecond retrieval in Tkinter list virtualizations.

---

## 8. High-Resolution & Archival Imaging Architecture

* **Decoupled Architecture (`ui/image_panel.py`)**: All image handling (zooming, rotation, canvas pan dragging, asynchronous chunked network fetching, and local folder indexing) is hosted in `ImagePanel`. Legacy `ui/image_handler.py` acts as a thin compatibility proxy.
* **100MP+ Specimen Scans**: `Image.MAX_IMAGE_PIXELS = None` is set globally on process initialization to eliminate `PIL.Image.DecompressionBombError` on large museum scans.
* **Bounded RAM Footprint**: `MAX_PIL_CACHE = 3` bounds in-memory full-resolution bitmaps. For large `.tif` / `.tiff` files, `tifffile` is utilized to load 8-bit / 16-bit multichannel images efficiently into Pillow without exhausting laptop memory.

---

## 9. Mobile Companion API & Schema Validation Architecture

* **Declarative Schemas (`backend/mobile_schemas.py`)**: All inbound REST API payloads (`/api/update`, `/api/batch_update`, `/api/presence`) are validated through **Marshmallow** schemas.
* **Normalization & Sanitization**: Schemas normalize incoming identifier keys (`id` vs `oid`), observation updates (`updates` vs `observation`), and sanitize values to neutralize CSV/Excel formula injection attempts (`=`, `+`, `-`, `@`, `\t`, `\r`).
* **Dynamic Table Compatibility**: Schemas enforce contract shapes while leaving dictionary values dynamic, ensuring custom herbarium collection columns remain 100% supported without schema migrations.
