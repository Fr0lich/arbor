# Feature Catalog

This document catalogues all current features implemented in the **arbor** project so that they can be easily tracked, referenced, and restored if disabled.

---

## 1. Core Workflow Features
*   **Excel Sync & Repository Auto-Backup**: Keeps data loaded into local memory from Excel files, autosaves changes every 2 minutes (.autosave.json), and tracks file modifications.
*   **Checked/Reviewed Statusing**: Allows users to mark records as  Reviewed. Displays a checkbox column in the object list and records review times.
*   **High-DPI Compatibility**: Automatically checks system scaling settings upon launch to adapt font sizes and dimensions dynamically for clear laptop viewports.

---

## 2. Advanced Interactive Subsystems
*   **Doubt/Problem Highlighting**: If a checklist problem field is checked (e.g. Species_Problem), the corresponding registration field (e.g., Species entry) is visually highlighted in yellow to direct attention to discrepant or incomplete data.
*   **Historical Conflict Resolution**: Detects schema mismatch errors between older local save files and the active database schema, prompting the user with an interactive resolver.
*   **Interactive Tutorial Manager**: An onboarding component that overlays visual guide dialogs instructing the user how to configure, browse, edit, and search objects.
*   **Taxonomy Accordions/Tabs**: Group input controls under logical taxonomy dividers (e.g. taxonomy, collection meta, storage location, admin).
*   **Virtual Keyboard Bindings**: Binds shortcuts to space, arrow keys, and control modifiers for rapid editing without requiring a mouse.
*   **Image viewer canvas**: Implements gallery layouts, rotation angles, dynamic URL patterns, and image zoom configurations.
*   **Bulk Editor Window**: Allows users to search, query, and bulk update registration or location fields across multiple selected objects at once.
*   **Collection Blueprint & Standard Database Creator (`ui/create_collection_dialog.py`)**: Visual 4-sheet preview (`Registration`, `Observation`, `Log`, `Unvalidated_source`) with interactive `[?] Details` expanders tailored for both beginners and experienced curators, 1-click standard creation with sample record (*Welwitschia mirabilis*), and 6-step customization wizard integration.
*   **Dedicated 220-Specimen Demo Dataset (`data/demo_collection.xlsx`)**: 11% slice of the real botanical collection with live online Unimus photo URLs and verified reviews, launched via `[ 🌿 Explore Demo Project ]` in `StartupDialog`.
*   **Detached High-Resolution Image Viewport (`ui/image_popup.py`)**: Detached canvas popup supporting double-buffered panning, mousewheel zoom tracking, and asynchronous chunked remote image streaming.
*   **Ergonomic Specimen Directory (`ui/widgets.py`)**: Dual view modes (Compact 4-column Treeview vs. Detailed Virtual Cards) featuring single-badge category discipline (`[ TAX ]`, `[ PROV ]`, `[ BOX ]`, `[ IMG ]`, `[ REV+ERR ]`, `[ REV ]`, `[ UNREV ]`), bullet-separated inline metadata rows without geometry churn, and $O(1)$ targeted selection diffing (`last_highlighted ^ current_selected`).
*   **Specimen Directory Card Customization & View Ergonomics (`ui/widgets.py`, `ui/unified_settings.py`, `ui/command_palette.py`, `config.py`)**: Comprehensive presentation-layer customization for virtual cards. Curators can toggle single-badge pills, adjust card density (`compact` 64px, `standard` 78px, `expanded` 92px), toggle Row 3 physical storage locations with configurable granularity (`full`, `compact`, `none`), toggle author citations (*Quercus robur L.*), and filter secondary metadata tokens. Features an interactive Live Preview Card with sample record status switching (`Taxonomy`, `Provenance`, `Box`, `Reviewed`), an explicit Badge Reference & Priority Legend (`Taxonomy > Provenance > Box > Media > Conflicts`), 4 simplified layout profiles (`Standard`, `Compact`, `Full Details`, `Minimalist`), universal `Ctrl+K` command palette integration, persistent user preferences (`user_prefs.json`), and a fail-safe '↺ Return to Default Card Settings' button. All customization operates strictly in the UI presentation layer with zero backend schema or database alterations.
*   **Curatorial Command Strip (`ui/object_context_bar.py`)**: Sticky contextual summary bar with monospace ID pill, live specimen counter (`42 of 1,250`), botanical italic serif typography (*Lora* / *Georgia*), clickable category problem badges launching resolvers, reactive amber `● Unsaved` dot, and emoji-free archival action buttons.
*   **Smooth Drawer Sashing & Problem Jumping (`ui/main_window.py`, `ui/keybindings.py`)**: 120ms cubic ease-out collapsible sidebar drawer with width persistence in `prefs.json`, rapid keyboard stepping with debounced media loading, and `Ctrl+Up` / `Ctrl+Down` problem jumper shortcuts.

---

## 3. Data Export & Standards
*   **Filtered Subset Exporter (`export_filtered_list`)**: Exports active or filtered specimen datasets directly to local **Excel (`.xlsx`)** or **CSV (`.csv`)** spreadsheets. Sanitizes values and uses UTF-8 BOM encoding.
*   **Decommissioned Features (DO NOT RESTORE)**:
    *   **Darwin Core (DwC) Occurrence Exporter**: Permanently decommissioned and removed from Arbor. Standard data exchange formats are strictly Excel and CSV. Future AI agents must not re-introduce Darwin Core export files or menu entries.

---

## 4. Application Updates & Session Preservation
*   **1-Click In-App Updating (`backend/updater.py`, `ui/update_dialog.py`)**: Seamless check and update mechanism querying GitHub Releases for new Arbor binaries.
*   **Atomic Windows Executable Swap**: Solves the Windows NTFS running executable locking limitation by atomically renaming `arbor.exe` -> `arbor.old.{timestamp}.exe`, moving the staged update into place, and restarting.
*   **Zero Work-Loss Session Preservation**: Automatically flushes active entry focus, triggers autosaves, captures the active workbook path and selected specimen ID into `~/.arbor/session_restore.json`, and relaunches with `--restore-session` to immediately resume the user's workspace without presenting the startup modal.
*   **GitHub Outage & Migration Resilience**: Handles HTTP 301/307 redirects automatically when repositories are renamed or moved, classifies HTTP 404/403/timeouts cleanly, and provides an editable repository configuration in `UnifiedSettingsWindow` (Tools tab) and an interactive fallback dialog to change the target repository or open the browser.
*   **Offline-First & Protected Directory Detection**: Detects read-only directories (`Program Files`) without admin privileges and falls back gracefully to standard browser downloads. Fails completely silently during regular curation when internet is unavailable.
