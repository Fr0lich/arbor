# Master PySide6 / Qt Designer Migration Guide for Arbor

## Executive Summary & Mission
Arbor is undergoing a systematic UI modernization from **Tkinter** to **PySide6 (Qt 6)** using **Qt Designer (`.ui` files)**. 

### Core Visual Directive: Exact Tkinter Parity
> **CRITICAL DESIGN GOAL**: The `.ui` files must look as **accurate to the original Tkinter designs as possible**.
> The Tkinter interface is the **gold standard** for visual layout, styling, and ergonomics:
> * Every `.ui` file must replicate the exact colors, paddings, margins, card outlines, and typography of its corresponding Tkinter window in `ui/`.
> * Do not introduce arbitrary new UI styles, round bubble buttons, or mismatched colors.
> * Maintain the distinct Arbor aesthetic: flat, high-contrast, clean 1px borders, monospace technical data fields, and card-encapsulated sections.

To ensure stability, continuity, and zero regression for existing users and production workflows, this migration is strictly executed as a **Parallel Process**.

---

## 1. The Parallel Process Architecture

### 1.1 Dual-Stack Coexistence Rules
1. **Tkinter Remains Primary & Stable**:
   - `main.py` continues to launch the Tkinter interface by default until Phase 4 (Full Parity & Cutover).
   - **Unified Selection Mechanism**: Users can explicitly launch either UI via:
     - CLI flags: `python main.py --ui qt` (or `--ui tk`, `--qt`, `--tk`)
     - Environment variable: `ARBOR_UI=qt python main.py`
     - Interactive terminal prompt: Selecting `[1] Tkinter` (default) or `[2] PySide6` when run interactively without flags.
   - **Never break, modify without reason, or deprecate Tkinter code** while developing Qt equivalents. All existing Tkinter tests and workflows must pass unconditionally.
2. **PySide6 is the Parallel Development Stack**:
   - `main_qt.py` remains the dedicated direct entry point for the PySide6 application.
   - All Qt controllers, helpers, and custom widgets live in the `ui_qt/` package.
   - All visual layouts are created in Qt Designer and stored as `.ui` files in `qt designer/`.
3. **Single Shared Backend & Data Layer**:
   - Both Tkinter and PySide6 share the exact same models and backend services:
     - State management: `models.AppState`
     - Database persistence and Excel parsing: `ui/database_ops.py`, `config.py`
     - Search & filtering engine: `backend/search.py`, `backend/filter.py`
     - Mobile Companion server: `backend/mobile_server.py`, `ui/mobile_host_app.py`
   - **Zero Domain Duplication**: Qt controllers must never reimplement database logic or data transformations. Controllers only bind Qt signals to the existing backend and update views based on state.

```
arbor/
├── main.py                     <-- Tkinter Entry Point (Production Default)
├── main_qt.py                  <-- PySide6 Entry Point (Parallel Migration)
├── qt designer/                <-- Pure declarative Qt Designer .ui files
│   ├── arbor.ui                <-- Startup / Project Setup Dialog (QDialog)
│   ├── main_window_existing.ui <-- Main Review Workspace (QMainWindow)
│   └── main_window_v2.ui       <-- Alternative / Refined Workspace Design
├── ui/                         <-- Legacy Tkinter UI components & dialogs
├── ui_qt/                      <-- PySide6 Controllers & Qt-specific helpers
│   ├── loader.py               <-- QUiLoader helper for loading .ui files
│   ├── qss_tokens.py           <-- Arbor Design System tokens & repolish helper
│   ├── startup_dialog.py       <-- QtStartupDialog controller (arbor.ui)
│   └── main_window.py          <-- QtMainWindow controller
└── models.py, config.py, ...   <-- SHARED CORE (Single source of truth)
```

---

## 2. In-Depth Analysis of `qt designer/arbor.ui`

The file `qt designer/arbor.ui` is the PySide6 implementation of Arbor's startup window ([`StartupDialog`](file:///c:/Users/ijbrekke/Documents/arbor/ui/dialogs.py#L380)). It defines the complete Project Setup workflow where the user configures the database, profile, image source, and historical books before launching the main workspace.

### 2.1 Technical Specs
- **Qt Version**: Qt 4.0 UI schema (fully supported by PySide6 `QUiLoader`).
- **Root Class**: `QDialog` named `StartupDialog`.
- **Dimensions**: Geometry `660x740`, Minimum size `520x640`.
- **Title**: `arbor — Project Setup`.
- **Layout Architecture**: 
  - Outer `QVBoxLayout` (`root_layout`, 12px margin, 0px spacing).
  - Encapsulated in a single styled card `card_frame` (1px outline, 2px border radius).
  - Pinned Header (`header_frame`, top).
  - Central Scroll Area (`body_scroll_area` containing `scrollAreaWidgetContents`).
  - Pinned Footer (`footer_frame`, bottom).

### 2.2 Design System & Embedded QSS
`arbor.ui` embeds the Arbor design tokens (defined in [`documentation/agent/AI_UI_GUIDE.md`](file:///c:/Users/ijbrekke/Documents/arbor/documentation/agent/AI_UI_GUIDE.md) and [`ui_qt/qss_tokens.py`](file:///c:/Users/ijbrekke/Documents/arbor/ui_qt/qss_tokens.py)) directly into the dialog's `styleSheet` property:

| Token Name | Hex Code | UI Usage in `arbor.ui` |
| :--- | :--- | :--- |
| `SURFACE` | `#fbfaf8` | Window background (`StartupDialog`), Pinned header background |
| `CARD` | `#ffffff` | Inner card background (`card_frame`), input fields on focus |
| `HEADER_ROW` / `LOW` | `#f2f5f1` | Pinned footer background (`footer_frame`), recent table header, input base |
| `CONTAINER` | `#e9ece5` | Button hover state, active table row selection |
| `TEXT` | `#2c302e` | Primary text, titles, text box contents |
| `SUBTEXT` / `OUTLINE` | `#747878` | Borders (1px solid), placeholder text, optional badges |
| `DIVIDER` | `#c4c7c7` | Header bottom divider, footer top divider |
| `BLACK` / `PRIMARY` | `#000000` | Launch button (`btn_launch`), active segmented mode button |
| `GREEN` / `SECONDARY` | `#3a7d44` | Recommended badge (`badge_img_recommended`) |
| `MOBILE GREEN` | `#2d6a4f` | Mobile Companion button (`btn_mobile`) |
| `RED` / `ERROR` | `#c93a40` | Required badge (`badge_db_required`), error status label |

### 2.3 Component & Object Catalog

```mermaid
graph TD
    StartupDialog[QDialog: StartupDialog] --> root_layout[QVBoxLayout: root_layout]
    root_layout --> card_frame[QFrame: card_frame]
    card_frame --> header_frame[QFrame: header_frame (Pinned Top)]
    card_frame --> body_scroll_area[QScrollArea: body_scroll_area (Middle)]
    card_frame --> footer_frame[QFrame: footer_frame (Pinned Bottom)]
    
    header_frame --> lbl_app_tag[QLabel: lbl_app_tag 'arbor']
    header_frame --> lbl_title[QLabel: lbl_title 'Project Setup']
    
    body_scroll_area --> section_db[QWidget: section_db]
    body_scroll_area --> section_images[QWidget: section_images]
    body_scroll_area --> section_books[QWidget: section_books]
    body_scroll_area --> section_recent[QWidget: section_recent]
    
    footer_frame --> btn_help[QPushButton: btn_help 'Help']
    footer_frame --> lbl_status[QLabel: lbl_status]
    footer_frame --> btn_mobile[QPushButton: btn_mobile 'Launch Mobile Companion']
    footer_frame --> btn_launch[QPushButton: btn_launch 'LAUNCH SYSTEM']
```

#### Detailed Widget Breakdown
1. **Pinned Header (`header_frame`)**:
   - `lbl_app_tag` (`QLabel`): Displays `arbor` in bold monospace (`Courier New`, 11px).
   - `lbl_title` (`QLabel`): Displays `Project Setup` in 20px bold sans-serif (`Segoe UI`).

2. **Section 1: Database (`section_db`)**:
   - `badge_db_required` (`QLabel`): Crimson badge `#c93a40` displaying ` REQUIRED `.
   - `lbl_db_title` (`QLabel`): `Select Database`.
   - `input_db_path` (`QLineEdit`): Read-only path box (placeholder `No database file selected...`).
   - `btn_browse_db` (`QPushButton`): `…` button to launch `QFileDialog`.
   - `btn_create_db` (`QPushButton`): `+ Create New Database` button (triggers wizard).
   - `lbl_profile` (`QLabel`): `Profile:` label.
   - `combo_profile` (`QComboBox`): Dropdown populated with database configs (from `config.DATABASE_CONFIGS`).

3. **Section 2: Image Source (`section_images`)**:
   - `badge_img_recommended` (`QLabel`): Forest green badge `#3a7d44` displaying ` RECOMMENDED `.
   - `lbl_img_title` (`QLabel`): `Image Source`.
   - `frame_image_modes` (`QFrame`): Contiguous 3-way segmented toolbar containing:
     - `btn_mode_online` (`QPushButton`): `Online Repository`
     - `line_seg_1` (`QFrame`): Vertical divider line
     - `btn_mode_local` (`QPushButton`): `Local Directory`
     - `line_seg_2` (`QFrame`): Vertical divider line
     - `btn_mode_offline` (`QPushButton`): `Offline (No Images)`
   - `folder_picker_container` (`QWidget`): Container holding the local directory picker:
     - `input_image_path` (`QLineEdit`): Read-only folder path.
     - `btn_browse_images` (`QPushButton`): `…` directory browse button.

4. **Section 3: Historical Books (`section_books`)**:
   - `badge_books_optional` (`QLabel`): Subtle gray badge `#747878` displaying ` OPTIONAL `.
   - `lbl_books_title` (`QLabel`): `Historical Data (Books)`.
   - `input_books_path` (`QLineEdit`): Read-only path box (placeholder `No books file selected...`).
   - `btn_browse_books` (`QPushButton`): `…` file browse button.

5. **Section 4: Recent Projects (`section_recent`)**:
   - `lbl_recent_title` (`QLabel`): `Recent Projects`.
   - `frame_recent_table` (`QFrame`): Outer border container.
   - `frame_recent_header` (`QFrame`): Table header row containing `lbl_hdr_filepath` (`FILE PATH`).
   - `list_recent_projects` (`QListWidget`): Clickable recent project file paths.

6. **Pinned Footer (`footer_frame`)**:
   - `btn_help` (`QPushButton`): Secondary button opening help options.
   - `lbl_status` (`QLabel`): Dynamic validation message (e.g. `Please select a database file.` or `Ready to launch!`).
   - `spacer_footer` (`QSpacerItem`): Pushes primary action buttons to the right.
   - `btn_mobile` (`QPushButton`): Emerald green `#2d6a4f` button launching mobile companion mode directly.
   - `btn_launch` (`QPushButton`): High-contrast black `#000000` button launching the full desktop workspace.

---

## 3. Controller Contract: Connecting `arbor.ui` to PySide6

The controller class (e.g. `QtStartupDialog` in `ui_qt/startup_dialog.py`) wraps the loaded widget and orchestrates state:

### 3.1 Signal / Slot Wiring Specification

| Widget | Signal | Controller Slot / Handler | Functionality |
| :--- | :--- | :--- | :--- |
| `btn_browse_db` | `.clicked` | `browse_database()` | Opens `QFileDialog.getOpenFileName` (`*.xlsx;*.db;*.sqlite`), updates `input_db_path`, auto-detects profile, checks for autosave, refreshes launch state. |
| `btn_create_db` | `.clicked` | `create_new_database()` | Opens Qt version of New Database Wizard. |
| `combo_profile` | `.currentTextChanged` | `on_profile_changed(text)` | Updates active config profile. |
| `btn_mode_online` | `.clicked` | `set_image_mode("online")` | Sets active mode, updates segmented button styles, hides/disables `folder_picker_container`. |
| `btn_mode_local` | `.clicked` | `set_image_mode("folder")` | Sets active mode, updates segmented button styles, reveals `folder_picker_container`. |
| `btn_mode_offline` | `.clicked` | `set_image_mode("offline")` | Sets active mode, updates segmented button styles, hides/disables `folder_picker_container`. |
| `btn_browse_images` | `.clicked` | `browse_image_folder()` | Opens `QFileDialog.getExistingDirectory`, updates `input_image_path`. |
| `btn_browse_books` | `.clicked` | `browse_books_file()` | Opens `QFileDialog.getOpenFileName` for Excel books. |
| `list_recent_projects` | `.itemClicked` | `on_recent_selected(item)` | Populates `input_db_path` with clicked path, auto-detects profile, refreshes launch state. |
| `btn_help` | `.clicked` | `show_help()` | Displays popup menu or help dialog. |
| `btn_mobile` | `.clicked` | `launch_mobile_mode()` | Sets `mobile_mode=True`, accepts dialog, hands off to `MobileHostApp`. |
| `btn_launch` | `.clicked` | `launch_desktop_mode()` | Validates inputs, saves recent file, updates `app.config`, accepts dialog. |

### 3.2 Dynamic Styling for Segmented Mode Strip
In Qt Designer, the segmented buttons are styled statically with `btn_mode_local` active. The controller must dynamically toggle the active button style when clicked:
```python
ACTIVE_SEG_STYLE = "background-color: #000000; color: #ffffff; border: none; font-family: 'Courier New', monospace; font-size: 12px; font-weight: bold; padding: 7px 10px;"
INACTIVE_SEG_STYLE = "background-color: #ffffff; color: #444748; border: none; font-family: 'Courier New', monospace; font-size: 12px; font-weight: bold; padding: 7px 10px;"

def set_image_mode(self, mode: str):
    self.image_mode = mode
    self.ui.btn_mode_online.setStyleSheet(ACTIVE_SEG_STYLE if mode == "online" else INACTIVE_SEG_STYLE)
    self.ui.btn_mode_local.setStyleSheet(ACTIVE_SEG_STYLE if mode == "folder" else INACTIVE_SEG_STYLE)
    self.ui.btn_mode_offline.setStyleSheet(ACTIVE_SEG_STYLE if mode == "offline" else INACTIVE_SEG_STYLE)
    self.ui.folder_picker_container.setVisible(mode == "folder")
```

---

## 4. Codebase Map: Where to Find Existing Menus, Panels & Windows

Arbor's Tkinter interface does not use a traditional OS top menubar; instead, it uses a custom action bar with popup menus, alongside modular secondary dialogs. AI agents must use this directory to locate original Tkinter components when porting them to Qt:

### 4.1 Main Review Workspace Orchestrator
* **`ui/main_window.py` (`ObjectProgramUI`)**:
  * `build_ui()`: Constructs the entire main layout (Header action bar, 3-column split, Footer).
  * Splitter proportions: Left column (`weight 0` / fixed ~380px), Center column (`weight 3` / ~640px), Right column (`weight 3` / ~420px).

### 4.2 Header Action Bar & Dropdown Menus
Located inside `ui/main_window.py`:
* **File Menu** (`show_file_dropdown`): *New Database, Open Excel, Save, Save As...*
* **Data Menu** (`show_data_dropdown`): *Load Books, Load earlier databases, Process Objects with Problems...*
* **GBIF Menu** (`show_gbif_dropdown`): *Validate Current Specimen, Run GBIF Taxonomy Check...*
* **Images Menu** (`show_images_dropdown`): *Image Source selection, Toggle image view...*
* **Create Menu** (`show_create_dropdown`): *New Object, New Database...*
* **Context Menus** (`ui/context_menu.py`): Right-click menus for the object list/tree and image canvas.
* **Presets Menu** (`ui/presets_panel.py` & `self.data_presets_menu`): Save/load field display presets.

### 4.3 The Three Core Workspace Panes
1. **Left Pane (Navigation & Search)**:
   * **Object Tree / List**: `ui/main_window.py` (`_build_treeview`, `object_list_box`).
   * **Search & Filters**: `ui/filter_panel.py` (`FilterPanel`) and `backend/search.py`.
   * **Context Status Bar**: `ui/object_context_bar.py` (total count, active index, problems indicator).
2. **Center Pane (Data Entry & Forms)**:
   * **Registry Panel**: `ui/registry_panel.py` (`RegistryPanel`).
   * **Location Panel**: `ui/location_panel.py` (`LocationPanel`).
   * **Dynamic Form Fields & Checkboxes**: `ui/widgets.py` and `ui/object_problem_resolver.py`.
3. **Right Pane (Image Viewer)**:
   * **Image Canvas**: `ui/image_panel.py` (`ImagePanel`).
   * **Zoom/Pan & Toolbar**: `ui/image_toolbar.py` and `ui/image_handler.py`.

### 4.4 Catalog of Secondary Dialogs & Subwindows
When wiring menu triggers, reference and port from these modular dialogs in `ui/`:

| Subsystem / Dialog | Tkinter Source File & Class | Purpose |
| :--- | :--- | :--- |
| **Startup / Launcher** | `ui/dialogs.py` (`StartupDialog`) | Project setup, DB & image source selection (migrated to `qt designer/arbor.ui`). |
| **Unified Settings** | `ui/unified_settings.py` (`UnifiedSettingsDialog`) | General, Appearance, Database, GBIF, Mobile, Advanced tabs. |
| **New Database Wizard** | `ui/new_database_wizard.py` (`NewDatabaseWizard`) | Multi-step database creation and schema configuration. |
| **Object Additions** | `ui/add_objects.py` (`AddObjectsDialog`) | Batch or single object creation modal. |
| **Bulk Edit** | `ui/bulk_edit.py` (`BulkEditDialog`) | Batch editing fields across multiple records. |
| **Group Editor** | `ui/group_editor.py` (`GroupEditorDialog`) | Specimen/object group association. |
| **Problem Resolver** | `ui/object_problem_resolver.py` (`ObjectProblemResolver`) | Queue for reviewing and resolving validation errors. |
| **Filter Query Builder** | `ui/filter_dialog.py` (`FilterDialog`) | Advanced multi-condition query and filter builder. |
| **GBIF Validation** | `ui/gbif_dialog.py`, `ui/gbif_review.py` | Taxonomy verification dialog and review workspace. |
| **GBIF Batch Config** | `ui/gbif_batch_config.py` (`GbifBatchConfig`) | Configuration for batch taxonomy updates. |
| **Historical Resolver** | `ui/historical_resolver.py`, `historical_suggestions.py` | Match records against historical book archives. |
| **Mobile Companion** | `ui/mobile_dialog.py`, `ui/mobile_host_app.py` | Mobile sync server launcher and QR connection modal. |
| **Mobile Conflict** | `ui/mobile_conflict_resolver.py` | Resolution modal for desktop/mobile edit conflicts. |
| **Recent Activity** | `ui/recent_activity_dialog.py` (`RecentActivityDialog`) | Audit log of edits and session operations. |
| **Log Viewer** | `ui/log_viewer.py` (`LogViewerDialog`) | View application session and error logs. |
| **Help & Guide** | `ui/help_dialogs.py` (`show_main_help`) | User guide and contextual help dialogs. |
| **Layout Manager** | `ui/layout_settings.py`, `ui/layout_manager.py` | Pane layout and sizing customizations. |
| **Status Bar** | `ui/status_bar.py` (`StatusBar`) | Bottom workspace status and save indicator. |

### 4.5 Qt Designer Files Catalog
All visual UI layouts are stored as pure declarative `.ui` XML files in `qt designer/`. Every file is verified to open cleanly in Qt Designer and load via PySide6 `QUiLoader`:

| File Name in `qt designer/` | Root Class | Purpose |
| :--- | :--- | :--- |
| **`arbor.ui`** | `QDialog` (`StartupDialog`) | Startup launcher & project setup. |
| **`loading_dialog.ui`** | `QDialog` (`LoadingDialog`) | Database indexing & loading splash card. |
| **`shortcuts_hud.ui`** | `QDialog` (`ShortcutsDialog`) | Searchable keyboard shortcuts HUD cheat sheet. |
| **`user_guide.ui`** | `QDialog` (`UserGuideDialog`) | Searchable markdown documentation browser. |
| **`log_viewer.ui`** | `QDialog` (`LogViewerDialog`) | Monospace error & session log viewer with live search. |
| **`ignored_words.ui`** | `QDialog` (`IgnoredWordsDialog`) | Custom dictionary whitelist editor. |
| **`database_statistics.ui`** | `QDialog` (`DatabaseStatisticsDialog`) | Dashboard statistics, progress bars, and problem breakdown. |
| **`recent_activity.ui`** | `QDialog` (`RecentActivityDialog`) | Audit log of visited objects and session edits. |
| **`quick_peek.ui`** | `QDialog` (`QuickPeekDialog`) | Lightweight inspector overlay card with thumbnail preview. |
| **`filter_dialog.ui`** | `QDialog` (`FilterDialog`) | 4-tab query builder with tri-state toggles and presets. |
| **`bulk_edit.ui`** | `QDialog` (`BulkEditDialog`) | Batch find-and-replace across multiple records. |
| **`group_editor.ui`** | `QDialog` (`GroupEditorDialog`) | Specimen group creator, member manager, and association. |
| **`add_objects.ui`** | `QDialog` (`AddObjectsDialog`) | Sequential ID range generator and batch object creator. |
| **`unified_settings.ui`** | `QDialog` (`UnifiedSettingsDialog`) | General, Appearance, Database profiles, and Advanced preferences. |
| **`gbif_dialog.ui`** | `QDialog` (`GBIFUpdateDialog`) | Single-record taxonomy validator and side-by-side diff. |
| **`gbif_review.ui`** | `QDialog` (`GBIFReviewDialog`) | Batch GBIF reconciliation review table. |
| **`historical_resolver.ui`** | `QDialog` (`HistoricalResolverDialog`) | Historical books discrepancy table and resolver. |
| **`problem_queue.ui`** | `QDialog` (`ProblemQueueDialog`) | Interactive queue for navigating and fixing flagged validation issues. |
| **`new_database_wizard.ui`** | `QWizard` (`NewDatabaseWizard`) | Multi-step database creation wizard. |
| **`main_window_existing.ui`** | `QMainWindow` (`MainWindow`) | Full 3-pane main workstation shell (in `qt designer/qt designer (old or flawed)/`). |

---

## 5. Phase-by-Phase Parallel Migration Roadmap (Easiest First)

> **Scope Boundary**: Per project specifications, the **Mobile Companion UI** (`ui/mobile_dialog.py`, `ui/mobile_conflict_resolver.py`, `ui/mobile_host_app.py`) is **strictly excluded** from the PySide6 migration scope.

AI agents must execute migrations following this complexity-ordered roadmap, unlocking self-contained quick wins first before tackling complex workstations:

### Phase 1: Quick Wins (Self-Contained & Low Complexity)
* **Goal**: Establish standard dialog controller patterns, closing behaviors, and styling conventions without touching mutable application state.
- [x] **Startup Dialog**: Implemented in `ui_qt/startup_dialog.py` wrapping verified `qt designer/arbor.ui`.
- [x] **Help & Guide Modals**: `QtUserGuideDialog`, `QtKeyboardShortcutsDialog`, `show_about`, `show_quick_help` (`ui_qt/help_dialogs.py`).
- [x] **Log Viewer Dialog**: `QtErrorLogDialog` with line filtering, clipboard copy, and explorer opening (`ui_qt/log_viewer.py`).
- [x] **Ignored Words Dialog**: `QtIgnoredWordsDialog` custom dictionary editor (`ui_qt/ignored_words_dialog.py`).
- [x] **Loading Splash**: `QtLoadingDialog` progress bar card with determinate/indeterminate modes (`ui_qt/loading_dialog.py`).

### Phase 2: Read-Only Displays, Menus & Action Bars
* **Goal**: Wire up user action menus, summary dashboards, and tabular audit logs.
- [x] **Header Action Bar & Context Menus**: File, Data, GBIF, Images, Create, and Presets menus (`ui_qt/main_window.py`, `main_qt.py`).
- [x] **Database Statistics Dashboard**: Aggregated metric counts, completion ratios, progress bars (`ui_qt/dashboard.py` wrapping `qt designer/database_statistics.ui`).
- [x] **Recent Activity Dialog**: Tabular audit trail of session operations (`ui_qt/recent_activity_dialog.py` wrapping `qt designer/recent_activity.ui`).
- [x] **Quick Peek Dialog**: Fast record metadata & thumbnail inspector card (`ui_qt/quick_peek.py` wrapping `qt designer/quick_peek.ui`).

### Phase 3: Focused Editing Dialogs & Settings
* **Goal**: Allow modal configuration and batch field manipulations.
- [x] **Unified Settings Window**: Tabbed preferences (General, Appearance, Database profiles, Advanced) (`ui_qt/unified_settings.py` wrapping `qt designer/unified_settings.ui`).
- [x] **Group Editor**: Specimen group assignment and management (`ui_qt/group_editor.py` wrapping `qt designer/group_editor.ui`).
- [x] **Bulk Edit Dialog**: Column find/replace and regex operations (`ui_qt/bulk_edit.py` wrapping `qt designer/bulk_edit.ui`).
- [x] **Add Objects Wizard**: Range generator and sequential record creation (`ui_qt/add_objects.py` wrapping `qt designer/add_objects.ui`).

### Phase 4: Query Builder & Single-Item Verification
* **Goal**: Multi-tab filtering and live scientific verification.
- [x] **Filter Dialog & Panel**: 4-tab query builder with tri-state toggles and preset management (`ui_qt/filter_dialog.py` wrapping `qt designer/filter_dialog.ui`).
- [x] **GBIF Specimen Validator**: Single-record live taxonomy match and side-by-side diff (`ui_qt/gbif_dialog.py` wrapping `qt designer/gbif_dialog.ui`).

### Phase 5: High-Complexity Workspaces & Deep Resolvers
* **Goal**: Core application workstation and complex multi-dataframe reconciliation.
- [x] **Main Review Workspace**: 3-pane `QSplitter` (Left: Object Tree, Center: Dynamic Form Cards, Right: `QGraphicsView` Image Viewer).
- [x] **New Database Wizard**: Multi-step `QWizard` for schema creation and Excel initialization (`ui/new_database_wizard.py` -> `ui_qt/new_database_wizard.py`).
- [x] **GBIF Batch Review**: Multi-row batch taxonomy review table and thread workers (`ui/gbif_batch_config.py`, `ui/gbif_review.py` -> `ui_qt/gbif_review.py`).
- [x] **Historical Books Conflict Resolver**: Side-by-side book diff table and merge tools (`ui/historical_resolver.py` -> `ui_qt/historical_resolver.py`).
- [x] **Problem Queue Resolver**: Interactive error queue navigation and inline validation (`ui/object_problem_resolver.py` -> `ui_qt/problem_queue.py`).

### Phase 6: Parity Verification & Audit (Completed)
- [x] **Automated Test Suite**: Ran test suite against PySide6 runtime (57/57 unit and integration tests passing).
- [x] **Live Mock Data Synthesis**: Generated realistic botanical (`scratch/mock_current_db.xlsx`) and archival ledger (`scratch/mock_historical_books.xlsx`) datasets with deliberate taxonomy errors and provenance conflicts.
- [x] **Side-by-Side Live Data Parity Audit**: Conducted exhaustive runtime audit comparing Tkinter and PySide6 across 23 features, layout geometry, data binding, and interactions.
- [x] **Audit Deliverable**: Published comprehensive audit report at [`documentation/agent/PYSIDE6_PARITY_AUDIT_REPORT.md`](file:///c:/Users/ijbrekke/Documents/arbor/documentation/agent/PYSIDE6_PARITY_AUDIT_REPORT.md) (Overall Parity: **78.5%**; Secondary Dialogs: **94.0%**; Main Workspace: **58.0%**).

### Phase 6.5: Main Desktop Workstation Migration (Active Focus)
* **Goal**: Recreate all Tkinter main desktop workspace functionality in PySide6 as closely as possible, prioritizing **Functionality and UI Design**.
* **Scope Clarifications & Exclusions (Per Direct User Instruction)**:
  - ⛔ **Mobile Companion UI**: Strictly excluded (lives in HTML / `mobile_server.py`).
  - ⛔ **Object List "Card Widgets"**: Excluded/Deferred. The left object list (`tree_objects`) strictly uses the compact `QTreeWidget` mode (`[Rev, ID, Taxon]`). Do NOT build the virtualized canvas list cards at this time.
  - ⛔ **Keyboard Shortcuts / Accelerators**: Excluded/Deferred from Round 1. Focus is 100% on **interactive UI design, layout parity, data-binding, and core desktop functionality**. Keybindings will be restored in a subsequent refinement pass.
  - ✅ **Registration Form Sections**: Fully in scope and **must strictly match Tkinter's UI design**. The registration form in `tab_general` will render 3 distinct styled card sections with headers, borders, and margins matching `ui/registry_panel.py`:
    1. *Taxonomy & Scientific Name* (`Genus`, `Species`, `Author`, `Family`, `Higher Classification`)
    2. *Collection & Specimen Metadata* (`Collector`, `Innsammling Nr.`, `Collection Date`, `Collection Place`, `Variant`, `(N) Plant Part`, `Plant Part`, `Box Label`, `Conservation Status`, `Online photo 1-3`, `UID`, etc.)
    3. *Audit Notes & Descriptions* (`Observation`, `Comment`, `ProblemDescription`)
  - ✅ **Dual-Docking Location Panel (Default: Middle Column)**: Fully in scope. The Location Panel defaults to the **Middle Column horizontally** (below the image panel in a 1-row or 2-row layout), with the ability to be toggled to the **Left Column vertically** (under the object tree) via view settings / preferences.

---

#### Milestone 1: Core Data Pipeline & Immediate End-to-End Visibility (Completed)
* **Purpose**: Solve the root data binding contracts immediately so the user can visually verify live data flowing across all three columns when clicking items in the object tree.
- [x] **1.1 Fix DataFrame Indexing in `QtMainWindow.open_excel()`**: Enforce string `ObjectID` indexing on `df_reg` and `df_obs` (via `_normalize_object_id_series` and `set_index("ObjectID")`), fixing the tree to display actual IDs (`1001`, `1002`...) instead of integer row offsets (`0`, `1`...).
- [x] **1.2 Middle Column Active Specimen Context Updates**: When selection changes in `tree_objects`:
  - Update `lbl_id_badge` with formatted ID (e.g. `ID: 1001`).
  - Update `lbl_specimen_name` with scientific name (e.g. `Pinus sylvestris (L.)`).
  - Update `lbl_status_badge` with problem status or reviewed status.
- [x] **1.3 Right Column Registration Form Population (`tab_general`)**:
  - Dynamically instantiate input controls (`QLineEdit`, `QComboBox`, `QTextEdit`) inside `scroll_general_contents` partitioned into the 3 Tkinter card sections (`Taxonomy & Scientific Name`, `Collection & Specimen Metadata`, `Audit Notes & Descriptions`).
  - Replicate Tkinter styling: 1px border cards, header background `#f5f5f5` / `#252538`, monospace font for technical values, and Segoe UI for labels.
  - When selecting an item in `tree_objects`, populate all fields with live values from `df_reg.loc[oid]`.
  - *Milestone 1 Verification*: Load database -> Click any specimen in tree -> Tree displays real ID -> Middle column displays ID and Taxon -> Right column displays all specimen registration values (Verified with `scratch/test_milestone1_data_binding.py`).

#### Milestone 2: Middle Column (Image Viewer Canvas & Default Middle Location Panel) (Completed)
- [x] **2.1 Image Viewer Canvas & Loading Pipeline**:
  - Implement photo resolution in `image_view` (`QGraphicsView` / `QGraphicsScene`): load image from URL (`Photo` sheet / online fields) or local image directory; display a clear `"No image available"` placeholder when none exist.
  - Update `lbl_images_count` (e.g. `1 / 2`) and `lbl_images_missing`.
  - Wire image toolbar buttons: `btn_zoom_in`, `btn_zoom_out`, `btn_rotate_ccw`, `btn_rotate_cw`, `btn_reset_view`, `btn_fit_view`, and update `lbl_zoom_status`.
- [x] **2.2 Middle Column Horizontal Location Panel (Default Placement)**:
  - Implement `QtLocationPanel` docked horizontally by default in the Middle Column (below `image_view`), supporting 1-row and 2-row layout modes.
  - Support toggle / reparenting to the Left Column (`location_container`) on user command.
  - Populate with active values from `df_obs` on record change and commit field edits to `df_obs` (Verified with `scratch/test_milestone2_middle_column.py`).

#### Milestone 3: Problems Tab Checklist, Problem Tints & Status Bar Metrics (Completed)
- [x] **3.1 Problems Tab Checklist & Problem Tints**:
  - In `tab_problems`, dynamically render checkboxes for all flags in `config["ui_sections"]["problems"]`.
  - Populate states from `df_obs` on specimen change; toggling updates `df_obs` and refreshes amber problem highlight tints (`#fef9e7`) on corresponding registration fields.
  - Bi-directional synchronization between `tab_problems` checkboxes and `tab_general` inline checkboxes.
  - Dynamic update of Problems tab title with active count (`Problems (N)`) and problem summary list (`✔ No active problems flagged` / `⚠ ...`).
- [x] **3.2 Status Bar & Problem Queue Detection Scope**:
  - Exclude `Images_Missing` from `_detect_problem_queue()` in `ui_qt/problem_queue.py` so only curatorial/scientific errors populate the queue.
  - Update status bar total/reviewed/problem counters and active position index (`ID: 1001 (1 of 25)`).
  - *Milestone 3 Verification*: Verified with `scratch/test_milestone3_problems_tab.py` (5 of 5 tests passing). All 67 Qt test suite cases passing.

#### Milestone 4: Workstation Actions, Review Bar, State Mutations & Dialog Integration (Completed)
- [x] **4.1 Inline State Mutation, Dirty Tracking & Undo**:
  - Wire field edits (`textEdited` / `currentTextChanged`) to update in-memory `df_reg`, trigger `app.dirty = True`, record undo snapshots to `app.undo_stacks[oid]`, append edit entries to `df_log`, and update the status bar save indicator.
- [x] **4.2 Review Action Bar & Workflow Toggles**:
  - Wire `btn_mark_reviewed`: toggle `Reviewed` in `df_obs`, timestamp `ReviewedAt`, update `lbl_reviewed_time`, update tree mark (`✓`), and refresh status bar metrics.
  - Wire `chk_clear_problems`: clear active problem flags when reviewed is checked.
  - Wire `chk_auto_next`: automatically advance to the next specimen upon marking reviewed.
  - Wire `chk_auto_hist`: auto-inspect historical books if archival data is present.
- [x] **4.3 Dialog Integration & Navigation Controls**:
  - Wire `btn_gbif` (open single-specimen `QtGbifUpdateDialog`).
  - Wire `btn_check_books` (open `QtHistoricalResolverDialog`).
  - Wire `btn_peek` (open `QtQuickPeekDialog`).
  - Wire `combo_sort` (Sort by ID, Genus/Species, Reviewed Status).
  - Wire navigation buttons (`btn_prev`, `btn_next`, `btn_last`, `btn_next_problem`, `btn_next_hist`).
- [x] **4.4 Unsaved Changes Exit Guard**: Implement `closeEvent` on `QtMainWindow` to prompt user to save, discard, or cancel when closing with unsaved changes (`app.dirty == True`).
  - *Milestone 4 Verification*: Verified with `scratch/test_milestone4_workstation_actions.py` (6 of 6 tests passing). Full Qt regression suite passing (67 of 67 tests).

---

#### Phase 7: Polish, Interactions & Parity Hardening (Completed)
- [x] **7.1 Mouse-Free Focus & Keyboard Shortcut Subsystem**: Focus jumping (`Ctrl+F`, `Ctrl+O`, `Ctrl+E`/`Ctrl+I`, `Shift+E`, `Ctrl+L`/`F4`, `Ctrl+P`/`F3`, `Ctrl+PageUp`/`PageDown`, `Space`) and workflow shortcuts (`Ctrl+S`, `Ctrl+R`, `Ctrl+Z`, `Ctrl+Y`, `Ctrl+G`, `Ctrl+B`, `Ctrl+J`, `Ctrl+H`, `Ctrl+N`, `Ctrl+Shift+N`, `Ctrl+Shift+D`, `Ctrl+Delete`, `Left`/`Right`, `Alt+Left`, `F1`, `Ctrl+K`).
- [x] **7.2 Canvas Interactions & Multi-Photo Gallery**: Wheel zoom centered on cursor, drag-to-pan (`ScrollHandDrag`), multi-image pagination (`Shift+Left`/`Shift+Right`/`Ctrl+B`), double-click launch in OS default viewer, and right-click canvas context menu.
- [x] **7.3 Tree Context Menu & Specimen Lifecycle Parity**: Right-click actions on `tree_objects`: Mark Reviewed/Unreviewed, Copy Accession ID, Duplicate Specimen, Delete Specimen, Add to Group.
- [x] **7.4 Presets, Session Persistence & View Toggles**: Laptop layout toggles (`F6` Left, `F7` Right, `F8` Center), Presets menu (`Ctrl+K`), and window splitter/geometry persistence to `user_prefs.json`.
- [x] **7.5 Dual-Launcher Support Contract**: Preserved `python main.py` strictly defaulting to Tkinter as requested; PySide6 launched independently via `python main_qt.py`.
- [x] **7.6 Automated Test Suite**: Comprehensive test suite `tests/test_qt_phase7_polish.py` (6 of 6 tests passing). Full test suite passing 73 of 73 tests.

---

## 6. Agent Rules of Engagement

When working on any PySide6 migration task, all AI agents must follow these rules:

1. **Never edit Tkinter files to solve a Qt problem**:
   - If an issue arises in PySide6, solve it in `ui_qt/` or the `.ui` file. Do not touch `ui/` or `main.py` unless fixing a genuine shared backend bug.
2. **Always use `QApplication` for UI scripts**:
   - Any script or test loading a `.ui` file via `load_ui()` must ensure `QApplication.instance() or QApplication(sys.argv)` is initialized first.
3. **Preserve exact token values**:
   - Do not invent arbitrary colors or font sizes. Always reference `documentation/agent/AI_UI_GUIDE.md` and `ui_qt/qss_tokens.py`.
4. **Use Qt Designer for layout structure**:
   - Do not write monolithic 500-line Python UI construction code. Create or adjust `.ui` files in `qt designer/` and keep Python controllers thin, event-driven, and focused on domain models.
5. **Match Tkinter visual design strictly**:
   - When creating or modifying `.ui` files in `qt designer/`, inspect the corresponding Tkinter implementation in `ui/`. Replicate its window dimensions, margins, paddings, card container outlines (`#747878`), button palettes, and typography (`Courier New` monospace for data, `Segoe UI` sans-serif for UI labels). Tkinter is the gold standard for design parity.
