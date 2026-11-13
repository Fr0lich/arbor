# Arbor Living Change Journal (User-Facing Delta Log)

This file tracks all user-facing changes made to Arbor. Whenever a feature, shortcut, setting, or workflow is updated in code, the authoring agent **MUST** record the change here so the documentation agent can synchronize all user guides, cheat sheets, and in-app touchpoints.

---

## 📌 Instructions for Coding Agents
1. Every time you change, add, or remove a user-facing feature (keyboard shortcut, status badge, setting toggle, panel layout, or dialog flow), append a new entry to the `[Unreleased / Recent Updates]` section below.
2. Use plain, non-technical language to describe the **User Impact** (what a trainee or museum assistant experiences at their desk).
3. Do not close a feature task until you have filled out the **Documentation Sync Checklist**.

---

## [Unreleased / Recent Updates]

### Entry 1: Startup Column Sashes & Proportional Auto-Layout
- **Date**: 2026-11-13
- **Feature Area**: Workspace Layout & Panel Sizing (`ui/main_window.py`, `ui/layout_settings.py`)
- **What Changed**: Implemented `apply_proper_sash_positions()` and smooth 120ms animated transitions for the 3-column workspace. Arbor now dynamically measures the user's screen resolution and positions the Specimen Directory (left column), Image Viewport (middle column), and Registration Form (right column) in balanced proportions on startup, while remembering user manual drags between sessions.
- **User Impact**: When trainees launch Arbor or toggle the sidebar (`Ctrl+O` or `F6`), the screen opens with clean, readable panel widths instead of cramped columns, and the image viewer never collapses into an invisible sliver.
- **Documentation Sync Checklist**:
  - [x] Master Documentation Map (`MASTER_DOCUMENTATION_MAP.md`) Touchpoint Matrix
  - [x] Trainee Manual (`USER_GUIDE.md`) Chapter 2: The Three Main Screen Areas
  - [x] Desk Cheat Sheet (`KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`) Panel Controls
  - [x] In-App Help Center (`ui/help_dialogs.py`) Panel Layout HUD

---

### Entry 2: Single-Badge Discipline for Specimen Directory Cards
- **Date**: 2026-11-13
- **Feature Area**: Specimen Directory & Visual Status Hierarchy (`ui/widgets.py`, `ui/unified_settings.py`)
- **What Changed**: Streamlined the card status display using `_resolve_card_badge_display()` to enforce a strict **single-badge discipline**. Each card now displays at most **one** high-contrast priority badge (`[ TAX ]`, `[ PROV ]`, `[ BOX ]`, `[ IMG ]`, `[ CFCT ]`, `[ REV+ERR ]`, `[ REV ]`, `[ UNREV ]`), ranked according to the active workflow priority preset (`default`, `taxonomist`, or `collections_manager`).
- **User Impact**: Trainees are never confused by a crowded row of multi-colored flags on a single card. A glance at the directory immediately highlights the single most important action required for each specimen.
- **Documentation Sync Checklist**:
  - [x] Master Documentation Map (`MASTER_DOCUMENTATION_MAP.md`) Canonical Badge Reference
  - [x] Trainee Manual (`USER_GUIDE.md`) Chapter 4: What the Status Badges Mean
  - [x] Desk Cheat Sheet (`KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`): Badge Color Legend with Excel Columns
  - [x] Dual-Perspective Excel Bridge: Mapped each badge to its `Observation` sheet column

---

### Entry 3: Non-Blocking GBIF Toast Alerts
- **Date**: 2026-11-13
- **Feature Area**: Online Taxonomic Verification & Notifications (`ui/toast.py`, `ui/gbif_review.py`, `ui/main_window.py`)
- **What Changed**: Replaced disruptive modal alert popups during GBIF taxonomic checks with sleek, non-blocking floating toast notifications (`ToastManager`). Toasts appear anchored at the top/bottom for 2.5 seconds with clear status icons (`✓ Valid exact match`, `ℹ Fuzzy match found`, `⚠️ Genus required`, `❌ Connection error`).
- **User Impact**: Trainees can verify plant names rapidly without having to repeatedly press Enter or click "OK" on modal popups. If the internet drops out or a name is not found, a soft alert appears without interrupting active typing.
- **Documentation Sync Checklist**:
  - [x] Master Documentation Map (`MASTER_DOCUMENTATION_MAP.md`) Touchpoint Matrix Feature 7
  - [x] Trainee Manual (`USER_GUIDE.md`) Chapter 4 & 6: GBIF Verification Workflow
  - [x] Desk Cheat Sheet (`KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`) Search & Verification

---

### Entry 4: Directory Card Layout Profiles & Interactive Live Preview
- **Date**: 2026-11-13
- **Feature Area**: Appearance Settings & Card Density (`ui/unified_settings.py`, `ui/command_palette.py`)
- **What Changed**: Added 4 one-click card layout profiles (`Standard` at 78px, `Compact` at 64px, `Full Details` at 92px, and `Minimalist`) selectable via Appearance Settings or Command Palette (`Ctrl+K`). Unified Settings now includes an interactive real-time card preview widget that renders exactly how cards will look before applying changes.
- **User Impact**: Trainees working on small 13-inch museum laptops can switch to "Compact" to see 15+ specimens at once without scrolling, while taxonomists working on wide monitors can choose "Full Details" to view botanical author citations and complete storage locations.
- **Documentation Sync Checklist**:
  - [x] Master Documentation Map (`MASTER_DOCUMENTATION_MAP.md`) Layout Profiles Section
  - [x] Trainee Manual (`USER_GUIDE.md`) Chapter 7: Changing the View (4 Card Profiles)
  - [x] Desk Cheat Sheet (`KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`): Card View Controls
  - [x] Command Palette Hints: Card View actions (`Standard`, `Compact`, `Full Details`, `Minimalist`)

---

### Entry 5: Non-Destructive Trackpad Zoom & Smooth Mousewheel Navigation
- **Date**: 2026-11-13
- **Feature Area**: Specimen Image Viewport & Canvases (`ui/scroll_helper.py`, `ui/image_panel.py`, `ui/image_popup.py`)
- **What Changed**: Centralized all scroll and zoom routing through `ui/scroll_helper.py` (`bind_mousewheel`), preventing event conflicts between the outer window and inner image viewport. High-resolution specimen scans now support smooth pinch/scroll zooming (`Ctrl+Mousewheel` or `+`/`-` buttons) and direct click-and-drag panning.
- **User Impact**: Trainees inspecting fine details on specimen labels (such as faded pencil handwriting or tiny pressed flowers) can zoom in and out smoothly using their laptop trackpad or mouse wheel without the whole window accidentally scrolling away.
- **Documentation Sync Checklist**:
  - [x] Master Documentation Map (`MASTER_DOCUMENTATION_MAP.md`) Touchpoint Matrix Feature 2
  - [x] Trainee Manual (`USER_GUIDE.md`) Chapter 8: Working with Specimen Photos
  - [x] Desk Cheat Sheet (`KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`): Photo Zoom & Rotation Gestures

---

### Entry 6: Trainee Work Manual & Printable Desk Cheat Sheet Release
- **Date**: 2026-11-13
- **Feature Area**: Full Documentation Suite Synchronization (`USER_GUIDE.md`, `documentation/curator/`)
- **What Changed**: Fully authored the comprehensive 10-chapter Trainee Work Manual (`CURATOR_USER_GUIDE.md` and `USER_GUIDE.md`) and the single-page printable Desk Cheat Sheet (`KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`). Strictly implemented the Dual-Perspective Excel Bridge rule across all chapters, dynamically aligned all status badge codes with `ui/widgets.py`, and completely removed barcode scanning references.
- **User Impact**: Trainees, interns, and museum assistants have a warm, zero-jargon handbook walking them through daily curation, explaining the exact Excel columns affected by every button, and providing a glanceable keycap cheat sheet beside their monitors.
- **Documentation Sync Checklist**:
  - [x] Trainee Manual (`documentation/curator/CURATOR_USER_GUIDE.md`)
  - [x] Root User Guide (`USER_GUIDE.md`)
  - [x] Desk Cheat Sheet (`documentation/curator/KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`)
  - [x] Master Documentation Map (`documentation/MASTER_DOCUMENTATION_MAP.md`)

---

### Entry 7: In-App User Assistance Hub & Dynamic Shortcuts HUD
- **Date**: 2026-11-13
- **Feature Area**: In-App User Assistance Hub & Dynamic Shortcuts HUD (`ui/help_dialogs.py`, `ui/unified_settings.py`, `ui/keybindings.py`, `ui/main_window.py`)
- **What Changed**: Upgraded `ui/help_dialogs.py` into a central 4-tile assistance hub (`open_help_window`), dynamic `show_about` displaying `config.APP_VERSION` and Tkinter runtime, and dynamic searchable `show_shortcuts` HUD populated directly from `CANONICAL_SHORTCUTS` in `ui/keybindings.py` displaying visual keycaps and Excel column impacts. Embedded markdown reader now provides a chapter jump dropdown. Rewrote all `SETTING_INFO_TEXTS` in `ui/unified_settings.py` into the Dual-Depth Learning Format (trainee explanation + Excel impact). Wired `F1` globally to launch the Help Hub seamlessly.
- **Trainee Impact**: Instant in-app access to manual, shortcuts, tutorials, and Excel translation bridge directly from the UI or by pressing `F1`, without leaving the desktop workspace or opening external browser windows.
- **Documentation Sync Checklist**:
  - [x] Master Documentation Map (`MASTER_DOCUMENTATION_MAP.md`) Tier 1-3 update
  - [x] Trainee Work Manual (`USER_GUIDE.md`) Chapter 6 & 7
  - [x] Desk Cheat Sheet (`documentation/curator/KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`)
  - [x] Zero barcode references verified across all dialogs and tooltips
  - [x] Test suite updated in `tests/test_navigation_and_dialogs.py`

---

### Entry 8: Excel Data Engine, Safety & Atomic Save Hardening
- **Date**: 2026-11-13
- **Feature Area**: Excel Data Engine, Atomic File Persistence & Shortcuts HUD (`repository.py`, `utils.py`, `backend/data_store.py`, `ui/database_ops.py`, `ui/autosave_handler.py`, `ui/help_dialogs.py`, `ui/keybindings.py`)
- **What Changed**:
  1. **Atomic Save Pipeline**: Sibling temporary file writing (`filename.xlsx.tmp_xxxx`) followed by `os.replace` ensures destination workbooks are never corrupted if a crash or write error occurs midway. Orphan temporary files are cleanly removed in all failure branches.
  2. **Pre-Save Automatic Backups**: Implemented `create_presave_backup` which snapshots the active workbook to `.arbor_backups/` capped at a rolling limit of 5 copies prior to atomic replacement.
  3. **Excel Lock & PermissionError Detection**: Defined `ExcelFileLockedError` with transient lock retry loops. If desktop Microsoft Excel holds a Windows file lock on the `.xlsx` file, Arbor catches the error gracefully and surfaces a friendly dialog (*"The Excel file '[Filename]' is currently open in Microsoft Excel or another program. Please close Excel and click 'Retry Save'."*) with immediate "Retry Save" and "Save a Copy" options so trainee work is never lost.
  4. **Data Type Preservation**: Preserves string accession numbers and ObjectIDs with leading zeros (e.g., `"000142"`) across pandas/openpyxl read-write cycles using `dtype=str`. Boolean flags (`Reviewed = TRUE / FALSE`) and ISO timestamps are strictly preserved.
  5. **Dynamic Shortcuts HUD Alignment**: Synchronized `CANONICAL_SHORTCUTS` in `ui/keybindings.py` and `show_shortcuts` in `ui/help_dialogs.py` to match `documentation/curator/KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`. Formatted keys with visual keycaps (`[ CTRL ] + [ ENTER ]`, `[ SPACE ]`, `[ CTRL ] + [ S ]`, `[ CTRL ] + [ K ]`, `[ CTRL ] + [ F ]`, `[ CTRL ] + [ G ]`, `[ CTRL ] + [ 0 ]`, `[ F1 ]`) and ensured `Space` is explicitly documented as Toggle Problem Checkbox, never Mark Reviewed.
- **Trainee Impact**: Trainees will never lose museum collection edits or corrupt the primary `.xlsx` workbook if Excel is left open on the desktop or if power is suddenly interrupted. If a workbook is locked by Excel, a clear, friendly prompt explains exactly what to do and allows retrying or saving a copy.
- **Documentation Sync Checklist**:
  - [x] Master Documentation Map (`MASTER_DOCUMENTATION_MAP.md`) Data Persistence & Safety
  - [x] Trainee Work Manual (`USER_GUIDE.md`) Chapter 5: Saving Your Work Safely
  - [x] Desk Cheat Sheet (`documentation/curator/KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`) Don't Panic Safety Tip & Primary Work Keys
  - [x] In-App Shortcuts HUD (`ui/help_dialogs.py` & `ui/keybindings.py`)
  - [x] Zero barcode references verified across all dialogs and tooltips
  - [x] Test suite updated in `tests/test_repository.py`

---

### Entry 9: Specimen Image Inspection Canvas, Zoom Ergonomics & Async Pre-Caching
- **Date**: 2026-11-13
- **Feature Area**: Specimen Image Viewport, Async Pre-Caching & Zoom Ergonomics (`ui/image_panel.py`, `ui/image_handler.py`, `ui/image_toolbar.py`, `ui/image_popup.py`)
- **What Changed**:
  1. **Asynchronous Adjacent Image Pre-Caching (`ui/image_handler.py`)**: Implemented `ImagePreCacher` backed by `cachetools.LRUCache(maxsize=10)` to asynchronously pre-load and pre-decode adjacent ($N-1$ and $N+1$) specimen scans in a background thread. Eliminates disk read and JPEG/TIFF decompression lag on the Tkinter UI thread during rapid sequential review.
  2. **High-Quality Zoom Ergonomics & Safe Presets (`ui/image_panel.py` & `ui/image_toolbar.py`)**:
     - `Ctrl + 1`: Fit Whole Sheet to Window (entire herbarium scan visible).
     - `Ctrl + 2`: Fit to Width (sheet fills viewport width, optimal for reading bottom botanical labels).
     - `Ctrl + 3`: 100% 1:1 Pixel Inspection (unscaled native resolution for examining fine botanical hairs, seeds, and veins).
     - Kept `Ctrl + 0` as existing reset view with zero shortcut conflicts with `ui/keybindings.py`.
     - Resampling Optimization: Uses `Image.Resampling.LANCZOS` for crisp resting renders and fast `NEAREST` during live drag-panning for 60 FPS fluidity.
  3. **Corrupted & Missing Image Resilience**: If a photo path listed in the Excel sheet is missing from disk, unreadable, or corrupted, Arbor renders an attractive visual placeholder canvas with an explanatory badge: *"Image not found on disk: [filename]"* or *"Corrupted image file: [filename]"*, preventing any Tkinter crash or unhandled `FileNotFoundError` / `PIL.UnidentifiedImageError`.
  4. **Image Toolbar Updates (`ui/image_toolbar.py`)**: Integrated `Fit Width` (`Ctrl+2`) and `100%` (`Ctrl+3`) buttons alongside existing zoom, rotate, and reset controls with full Light and Dark theme token support.
- **Trainee Impact**: Specimen review is instantaneous when pressing Left/Right arrow keys with zero decompression stutter. Interns and trainees can instantly jump to reading the label with `Ctrl+2` or inspecting fine microscopic plant structures at 1:1 resolution with `Ctrl+3`. If files are missing from storage, an informative placeholder explains the situation without interrupting work.
- **Documentation Sync Checklist**:
  - [x] Master Documentation Map (`MASTER_DOCUMENTATION_MAP.md`) Specimen Photos & View Controls
  - [x] Trainee Work Manual (`USER_GUIDE.md`) Chapter 8: Working with Specimen Photos
  - [x] Desk Cheat Sheet (`documentation/curator/KEYBOARD_SHORTCUTS_CHEAT_SHEET.md`) Photo Zoom & Rotation Gestures
  - [x] In-App Image Toolbar Tooltips & Status Badges
  - [x] Test suite updated in `tests/test_image_display.py` and `tests/test_navigation_and_dialogs.py`

---

### Entry 9: Mobile Companion Auditing & Offline Vault Sync
- **Date**: 2026-11-13
- **Feature Area**: Mobile Companion Auditing, Offline Sync, & Desktop Pairing (`backend/mobile_server.py`, `backend/mobile_schemas.py`, `ui/mobile_dialog.py`, `ui/mobile_panel.py`)
- **What Changed**:
  1. **Storage Location Vault Filtering**: Added quick Cabinet and Shelf dropdown selectors directly above the mobile specimen list in both V1 and V2, allowing trainees to filter expected physical sheets by cabinet and shelf.
  2. **Status Badge Discipline**: Standardized visual status badges on mobile cards to clearly display `Reviewed`, `Pending`, and `Taxon Issue`.
  3. **Prominent Mark Reviewed & Problem Flagging**: Added sticky one-tap "Mark Reviewed" button and "Flag Issue" modal in the mobile detail view. Trainees can quickly flag damaged physical sheets or misplaced specimens with custom problem notes, updating observation flags and writing to the audit log.
  4. **Offline-Resilient localStorage Change Queue**: In spotty vault Wi-Fi, pending mobile updates are automatically stored in browser `localStorage` (`arbor_offline_queue`). When connection resumes, edits flush to workstation via `/api/batch_update` without dropping data.
  5. **Desktop Pairing & Zero-Barcode Guarantee**: Desktop pairing dialog clearly displays local Wi-Fi IP and clean QR code for camera pairing. Strictly removed all barcode terms across mobile templates and server routes.
- **Trainee Impact**: Interns and trainees walking through physical collection vaults with a smartphone or tablet can filter sheets by cabinet/shelf, check physical sheets, tap "Mark Reviewed", and flag damage without fear of losing data when Wi-Fi drops out.
- **Documentation Sync Checklist**:
  - [x] Master Documentation Map (`MASTER_DOCUMENTATION_MAP.md`)
  - [x] Trainee Work Manual (`USER_GUIDE.md`) Chapter 9: Mobile Auditing & Companion Workflow
  - [x] Mobile Companion Guide (`documentation/agent/MOBILE_COMPANION_GUIDE.md`)
  - [x] Test suite updated in `tests/test_mobile_companion.py`
