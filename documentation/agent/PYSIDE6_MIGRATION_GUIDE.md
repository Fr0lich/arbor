# Master PySide6 / Qt Designer Migration Guide for Arbor

## Executive Summary & Mission
Arbor is undergoing a systematic UI modernization from **Tkinter** to **PySide6 (Qt 6)** using **Qt Designer (`.ui` files)**. 

To ensure stability, continuity, and zero regression for existing users and production workflows, this migration is strictly executed as a **Parallel Process**.

---

## 1. The Parallel Process Architecture

### 1.1 Dual-Stack Coexistence Rules
1. **Tkinter Remains Primary & Stable**:
   - `main.py` continues to launch the Tkinter interface by default until Phase 4 (Full Parity & Cutover).
   - **Never break, modify without reason, or deprecate Tkinter code** while developing Qt equivalents. All existing Tkinter tests and workflows must pass unconditionally.
2. **PySide6 is the Parallel Development Stack**:
   - `main_qt.py` is the entry point for the PySide6 application.
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

## 4. Phase-by-Phase Parallel Migration Roadmap

AI Agents implementing the migration must work according to these sequential phases:

### Phase 1: Startup & Main Shell (Current Phase)
- [x] Create `ui_qt/loader.py` and `ui_qt/qss_tokens.py`.
- [x] Design startup window UI (`qt designer/arbor.ui`).
- [x] Create basic `ui_qt/main_window.py` shell and `main_qt.py`.
- [ ] Implement complete `QtStartupDialog` controller (`ui_qt/startup_dialog.py`).
- [ ] Wire `main_qt.py` to run `QtStartupDialog`, load database into `AppState`, and pass state to `QtMainWindow`.

### Phase 2: Core Workspace Panes & Data Binding
- [ ] Left Pane: Object tree/list (`tree_objects` in `main_window_existing.ui`), search bar, status count.
- [ ] Center Pane: Dynamic observation and registry detail form fields (card container, field generators matching Arbor schema).
- [ ] Right Pane: High-performance image viewer (`QGraphicsView` replacing Tkinter `Canvas`), pan/zoom, thumbnail strip.

### Phase 3: Secondary Dialogs & Subsystems
- [ ] New Database Creation Wizard.
- [ ] Settings / Preferences dialog.
- [ ] Filter dialogs and export windows.
- [ ] Full Mobile Companion launcher integration.

### Phase 4: Verification & Parity Cutover
- [ ] Run full test suite against both Tkinter and PySide6 runtimes.
- [ ] Automated side-by-side behavioral verification.
- [ ] User approval for default cutover.

---

## 5. Agent Rules of Engagement

When working on any PySide6 migration task, all AI agents must follow these rules:

1. **Never edit Tkinter files to solve a Qt problem**:
   - If an issue arises in PySide6, solve it in `ui_qt/` or the `.ui` file. Do not touch `ui/` or `main.py` unless fixing a genuine shared backend bug.
2. **Always use `QApplication` for UI scripts**:
   - Any script or test loading a `.ui` file via `load_ui()` must ensure `QApplication.instance() or QApplication(sys.argv)` is initialized first.
3. **Preserve exact token values**:
   - Do not invent arbitrary colors or font sizes. Always reference `documentation/agent/AI_UI_GUIDE.md` and `ui_qt/qss_tokens.py`.
4. **Use Qt Designer for layout structure**:
   - Do not write monolithic 500-line Python UI construction code. Create or adjust `.ui` files in `qt designer/` and keep Python controllers thin, event-driven, and focused on domain models.
