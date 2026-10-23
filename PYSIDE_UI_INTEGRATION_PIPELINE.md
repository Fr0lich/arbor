# PySide6 UI Logic Wiring & Integration Pipeline

This document is the **Master Handover & Tracking Registry** for Phase 2 (Logic Wiring & Controller Integration). As UI components are extracted and verified into PySide6 `.ui` files in Phase 1, they are registered here as **READY FOR WIRING**.

Parallel AI agents working on logic wiring must refer to this document for their target specifications, widget catalogs, and status tracking.

---

## 1. Workflow for Phase 2 Integration Agents

When an AI agent is assigned to wire a UI component:
1. **Locate Assignment**: Find your assigned component in Section 3 below.
2. **Mark In Progress**: Update its status from `🟡 READY FOR WIRING` to `🔵 IN PROGRESS` and specify the agent/session ID.
3. **Follow the Wiring Contract**: Read the original Tkinter source and wire all signals, slots, callbacks, and EventBus events using the listed Widget Object Names.
4. **Adhere to Performance Rules**:
   - Never use Pandas `.iterrows()`.
   - Never block the Qt GUI thread; use worker threads or Qt signals for long operations.
   - Clean up event listeners, timers, and canvas bindings on widget destruction.
5. **Verify & Mark Complete**: Run the standalone test or test suite, then update the status in this document to `🟢 WIRED & VERIFIED`.

---

## 2. Global Integration Status Summary

| Phase 1 Extraction Source | Target Controller (`ui_qt/`) | UI XML Path | Status |
|---|---|---|---|
| `mobile_conflict_resolver.py` | `ui_qt/mobile_conflict_resolver.py` | `pyside_new_uis/mobile_conflict_resolver.ui` | 🟡 READY FOR WIRING |
| `object_problem_resolver.py` (Queue) | `ui_qt/problem_queue_dialog.py` | `pyside_new_uis/problem_queue_dialog.ui` | 🟡 READY FOR WIRING |
| `dialogs.py` (LoadingWindow) | `ui_qt/loading_window.py` | `pyside_new_uis/loading_window.ui` | 🟡 READY FOR WIRING |
| `location_panel.py` (LocationEditor) | `ui_qt/location_editor_dialog.py` | `pyside_new_uis/location_editor_dialog.ui` | 🟡 READY FOR WIRING |
| `registry_panel.py` (ProblemFlags) | `ui_qt/problem_flags_dialog.py` | `pyside_new_uis/problem_flags_dialog.ui` | 🟡 READY FOR WIRING |
| `quick_peek.py` | `ui_qt/quick_peek_dialog.py` | `pyside_new_uis/quick_peek_dialog.ui` | 🟡 READY FOR WIRING |
| `bulk_edit.py` | `ui_qt/bulk_edit_dialog.py` | `pyside_new_uis/bulk_edit_dialog.ui` | 🟡 READY FOR WIRING |
| `historical_resolver.py` | `ui_qt/historical_resolver.py` | `pyside_new_uis/historical_resolver.ui` | 🟡 READY FOR WIRING |
| `object_problem_resolver.py` (Main) | `ui_qt/object_problem_resolver.py` | `pyside_new_uis/object_problem_resolver.ui` | 🟡 READY FOR WIRING |
| `dialogs.py` (StartupDialog) | `ui_qt/startup_dialog.py` | `pyside_new_uis/startup_dialog.ui` | 🟡 READY FOR WIRING |
| `main_window.py` | `ui_qt/main_window.py` | `pyside_new_uis/main_window.ui` | 🟡 READY FOR WIRING |
| `widgets.py` (Item Card Template) | `ui_qt/object_list_card_delegate.py` | `pyside_new_uis/object_list_card_template.ui` | 🟡 READY FOR WIRING |
| `ignored_words_dialog.py` | `ui_qt/ignored_words_dialog.py` | `pyside_new_uis/ignored_words_dialog.ui` | 🟡 READY FOR WIRING |
| `help_dialogs.py` (Shortcuts HUD) | `ui_qt/shortcuts_hud_dialog.py` | `pyside_new_uis/shortcuts_hud_dialog.ui` | 🟡 READY FOR WIRING |
| `help_dialogs.py` (Help Center) | `ui_qt/help_center_dialog.py` | `pyside_new_uis/help_center_dialog.ui` | 🟡 READY FOR WIRING |
| `main_window.py` (Error Traceback) | `ui_qt/error_traceback_dialog.py` | `pyside_new_uis/error_traceback_dialog.ui` | 🟡 READY FOR WIRING |
| `autosave_handler.py` (Autosave Manager) | `ui_qt/autosave_manager_dialog.py` | `pyside_new_uis/autosave_manager_dialog.ui` | 🟡 READY FOR WIRING |
| `filter_dialog.py` | `ui_qt/filter_dialog.py` | `pyside_new_uis/filter_dialog.ui` | 🟡 READY FOR WIRING |
| `recent_activity_dialog.py` | `ui_qt/recent_activity_dialog.py` | `pyside_new_uis/recent_activity_dialog.ui` | 🟡 READY FOR WIRING |
| `dashboard.py` (Dashboard Stats) | `ui_qt/dashboard_dialog.py` | `pyside_new_uis/dashboard_dialog.ui` | 🟡 READY FOR WIRING |
| `image_handler.py` (Image Settings) | `ui_qt/image_settings_dialog.py` | `pyside_new_uis/image_settings_dialog.ui` | 🟡 READY FOR WIRING |
| `gbif_dialog.py` (GBIF Quick Update) | `ui_qt/gbif_update_dialog.py` | `pyside_new_uis/gbif_update_dialog.ui` | 🟡 READY FOR WIRING |
| `gbif_batch_config.py` (GBIF Batch Config) | `ui_qt/gbif_batch_config_dialog.py` | `pyside_new_uis/gbif_batch_config_dialog.ui` | 🟡 READY FOR WIRING |
| `new_database_wizard.py` (Batch Add) | `ui_qt/batch_add_fields_dialog.py` | `pyside_new_uis/batch_add_fields_dialog.ui` | 🟡 READY FOR WIRING |
| `group_editor.py` (Move Field) | `ui_qt/move_field_dialog.py` | `pyside_new_uis/move_field_dialog.ui` | 🟡 READY FOR WIRING |
| `group_editor.py` (Group Editor) | `ui_qt/group_editor_window.py` | `pyside_new_uis/group_editor_window.ui` | 🟡 READY FOR WIRING |
| `advanced_settings.py` | `ui_qt/advanced_settings_window.py` | `pyside_new_uis/advanced_settings_window.ui` | 🟡 READY FOR WIRING |
| `unified_settings.py` | `ui_qt/unified_settings_window.py` | `pyside_new_uis/unified_settings_window.ui` | 🟡 READY FOR WIRING |
| `mobile_dialog.py` / `mobile_panel.py` | `ui_qt/mobile_companion_dialog.py` | `pyside_new_uis/mobile_companion_dialog.ui` | 🟡 READY FOR WIRING |
| `gbif_review.py` | `ui_qt/gbif_review_dialog.py` | `pyside_new_uis/gbif_review_dialog.ui` | 🟡 READY FOR WIRING |
| `add_objects.py` | `ui_qt/add_objects_wizard.py` | `pyside_new_uis/add_objects_wizard.ui` | 🟡 READY FOR WIRING |
| `new_database_wizard.py` | `ui_qt/new_database_wizard.py` | `pyside_new_uis/new_database_wizard.ui` | 🟡 READY FOR WIRING |

---

## 3. Ready-for-Wiring Component Specifications

### 3.1 Mobile Conflict Resolver
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/mobile_conflict_resolver.py` (`MobileConflictResolverWindow`)
* **UI File**: `pyside_new_uis/mobile_conflict_resolver.ui`
* **Target Controller**: `ui_qt/mobile_conflict_resolver.py` (`QtMobileConflictResolver`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, main_app, oid: str, conflicts: list[dict], apply_callback)`
  - **Input Data**:
    ```python
    conflicts = [
        {"field": "species", "desktop_value": "Quercus robur", "mobile_value": "Pinus sylvestris"},
        ...
    ]
    ```
  - **Callback**: `apply_callback(oid, final_choices)` on Apply, where:
    ```python
    final_choices[field] = {
        "choice": "desktop" | "mobile",
        "desktop_value": c["desktop_value"],
        "mobile_value": c["mobile_value"]
    }
    ```
* **Widget Object Catalog**:
  - `MobileConflictResolver` (`QDialog` root window)
  - `header_frame` (`QFrame`)
  - `title_label` (`QLabel` — `"MOBILE CONFLICT RESOLVER"`)
  - `ctx_header` (`QFrame`)
  - `lbl_conflicts_count` (`QLabel` — `"CONFLICTS FOUND: X"`)
  - `lbl_conflicts_desc` (`QLabel` — context description)
  - `scroll_area` (`QScrollArea`), `scroll_contents` (`QWidget`), `scroll_layout` (`QVBoxLayout`)
  - `sample_card` (`QFrame` card template inside `scroll_layout`)
    - `card_header` (`QFrame` header, red `#c93a40`)
    - `card_field_title` (`QLabel` — `"FIELD: [FIELD]"`)
    - `card_badge` (`QLabel` — `"CFCT"`)
    - `card_content` (`QWidget`)
    - `desk_frame` (`QFrame` — desktop container, cursor `PointingHandCursor`)
      - `rb_desktop` (`QRadioButton` — `"Keep Desktop Value (Unsaved)"`)
      - `lbl_desk_val` (`QLabel` — desktop value or `"[BLANK]"`)
    - `mob_frame` (`QFrame` — mobile container, cursor `PointingHandCursor`)
      - `rb_mobile` (`QRadioButton` — `"Use Mobile Value"`)
      - `lbl_mob_val` (`QLabel` — mobile value or `"[BLANK]"`)
  - `footer_frame` (`QFrame`)
  - `btn_cancel` (`QPushButton` — Cancel action)
  - `btn_apply` (`QPushButton` — Apply selections action)

---

### 3.2 Problem Queue Scope Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/object_problem_resolver.py` (`ProblemQueueDialog`)
* **UI File**: `pyside_new_uis/problem_queue_dialog.ui`
* **Target Controller**: `ui_qt/problem_queue_dialog.py` (`QtProblemQueueDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, main_app=None, on_open_queue=None)`
  - **Behavior**: Scans objects in `main_app` according to selected scope (`filtered` vs `selected`) and active category checkboxes (`chk_taxonomy`, `chk_collection`, `chk_physical`, `chk_notes`). Updates matching counter dynamically.
  - **Execution**: On `btn_open_queue`, calls `on_open_queue(filtered_indices)` or launches `QtObjectProblemResolver`.
* **Widget Object Catalog**:
  - `ProblemQueueDialog` (`QDialog` root)
  - `header_frame` (`QFrame`), `lbl_header_title` (`QLabel` — `"BATCH_PROBLEM_QUEUE"`)
  - `tag_scope` (`QLabel`), `box_scope` (`QFrame`), `rb_filtered` (`QRadioButton`), `rb_selected` (`QRadioButton`)
  - `tag_categories` (`QLabel`), `box_categories` (`QFrame`)
    - `chk_taxonomy` (`QCheckBox` — Taxonomy)
    - `chk_collection` (`QCheckBox` — Collection)
    - `chk_physical` (`QCheckBox` — Physical)
    - `chk_notes` (`QCheckBox` — Notes & Other)
  - `lbl_matching_count` (`QLabel` — dynamic count label)
  - `footer_frame` (`QFrame`), `btn_cancel` (`QPushButton`), `btn_open_queue` (`QPushButton`)

---

### 3.3 Loading / Splash Window
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/dialogs.py` (`LoadingWindow`)
* **UI File**: `pyside_new_uis/loading_window.ui`
* **Target Controller**: `ui_qt/loading_window.py` (`QtLoadingWindow`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, title="Initializing Application", initial_status="Loading...")`
  - **Methods**: `set_status(message: str)`, `set_progress(value: int, maximum: int = 100)`, `finish()`
* **Widget Object Catalog**:
  - `LoadingWindow` (`QDialog` root)
  - `card_frame` (`QFrame`)
  - `lbl_title` (`QLabel` — main title)
  - `lbl_status` (`QLabel` — dynamic status line)
  - `progress_bar` (`QProgressBar` — indeterminate or deterministic progress)

---

### 3.4 Location Editor Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/location_panel.py` (`LocationEditor`), `ui/main_window.py` (`open_location_window`)
* **UI File**: `pyside_new_uis/location_editor_dialog.ui`
* **Target Controller**: `ui_qt/location_editor_dialog.py` (`QtLocationEditorDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, initial_location: dict = None, save_callback = None)`
  - **Inputs**: Coordinates, room, cabinet, shelf, extra, stored_as container type.
  - **Outputs**: Emits or calls `save_callback(updated_location_dict)` on save.
* **Widget Object Catalog**:
  - `LocationEditorDialog` (`QDialog` root)
  - `card_frame`, `header_container`, `lbl_header_title`
  - `form_grid_container`, `form_grid`
    - Input fields: `input_building`, `input_floor`, `input_room`, `input_cabinet`, `input_shelf`, `combo_stored_as`, `input_extra`
  - `footer_container`, `btn_cancel`, `btn_done`

---

### 3.5 Problem Flags Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/registry_panel.py`, `ui/main_window.py` (`open_problems_window`)
* **UI File**: `pyside_new_uis/problem_flags_dialog.ui`
* **Target Controller**: `ui_qt/problem_flags_dialog.py` (`QtProblemFlagsDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, active_flags: list[str] = None, save_callback = None)`
  - **Outputs**: Returns list of checked flag tokens on confirmation.
* **Widget Object Catalog**:
  - `ProblemFlagsDialog` (`QDialog` root)
  - `card_frame`, `header_container`, `lbl_header_title`, `header_divider`
  - `grid_container`, `problems_grid`:
    - Checklist items: `chk_genus_problem`, `chk_species_problem`, `chk_subspecies_problem`, `chk_author_problem`, `chk_family_problem`, `chk_collector_problem`, `chk_date_problem`, `chk_location_problem`, `chk_coordinates_problem`, `chk_elevation_problem`, `chk_duplicate_problem`, `chk_other_problem`
  - `footer_divider`, `lbl_missing_warning`
  - `footer_container`, `btn_cancel`, `btn_done`

---

### 3.6 Quick Peek Inspection Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/quick_peek.py`
* **UI File**: `pyside_new_uis/quick_peek_dialog.ui`
* **Target Controller**: `ui_qt/quick_peek_dialog.py` (`QtQuickPeekDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, oid: str = "", object_data: dict = None)`
  - Non-modal inspector card displaying full specimen metadata and thumbnails.
* **Widget Object Catalog**:
  - `QuickPeekDialog` (`QDialog` root)
  - `header_frame`, `lbl_title` (title), `chk_show_image`, `btn_popout`
  - `main_splitter`, `left_pane`, `search_container`, `input_search`, `frame_advanced_filters`, `input_filter_genus`, `input_filter_species`, `input_filter_collection`, `list_results` (`QListWidget`)
  - `content_splitter`, `scroll_data_area`, `data_contents`, `data_grid` (`val_id`, `val_reviewed`, `val_sciname`, `val_family`, `val_collector`, `val_location`, `val_provenance`), `frame_image_preview`, `lbl_image_preview`
  - `footer_frame`, `btn_go_to_object` (`QPushButton`)

---

### 3.7 Bulk Edit Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/bulk_edit.py` (`BulkEditWindow`)
* **UI File**: `pyside_new_uis/bulk_edit_dialog.ui`
* **Target Controller**: `ui_qt/bulk_edit_dialog.py` (`QtBulkEditDialog`)
* **Wiring Contract**:
  - Multi-record batch editor.
  - Layout toggle (`btn_toggle_layout` switches between 1-column vertical and 2-column horizontal orientations).
  - Target list management: adds specimen IDs via `input_search_id` + `btn_add_object` into `list_targets`; double-click removes with Ctrl+Z undo stack.
  - Field selection: activates field updates via `chk_en_*` checkboxes, provides values via `input_bulk_*` or `combo_bulk_*`.
  - Actions: `btn_apply_targets` (applies changes to explicit target list), `btn_destructive` (guarded by `chk_understand` confirmation, applies to all active filtered objects).
* **Widget Object Catalog**:
  - `BulkEditDialog` (`QDialog` root)
  - `header_frame`, `lbl_title`, `btn_toggle_layout` (`QPushButton`)
  - `content_splitter` (`QSplitter`)
  - Target Card: `card_targets`, `hdr_targets`, `lbl_hdr_targets`, `targets_body`, `lbl_add_id`, `input_search_id` (`QLineEdit`), `btn_add_object` (`QPushButton`), `list_targets` (`QListWidget`), `lbl_hint`
  - Edit Card: `card_edit`, `hdr_edit`, `lbl_hdr_edit`, `scroll_edit_area` (`QScrollArea`), `edit_contents` (`QWidget`), `edit_grid` (`QGridLayout`)
    - Field widgets: `chk_en_sciname`, `input_bulk_sciname`, `chk_en_genus`, `input_bulk_genus`, `chk_en_species`, `input_bulk_species`, `chk_en_family`, `input_bulk_family`, `chk_en_building`, `input_bulk_building`, `chk_en_floor`, `input_bulk_floor`, `chk_en_cabinet`, `input_bulk_cabinet`, `chk_en_reviewed`, `combo_bulk_reviewed`, `chk_en_genus_prob`, `combo_bulk_genus_prob`
  - Action Container: `action_container`, `target_actions_row`, `btn_apply_targets` (`QPushButton`), `sep_destructive`, `destructive_row`, `chk_understand` (`QCheckBox`), `btn_destructive` (`QPushButton`)

---

### 3.8 Historical Conflict Resolver
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/historical_resolver.py` (`HistoricalConflictResolverWindow`)
* **UI File**: `pyside_new_uis/historical_resolver.ui`
* **Target Controller**: `ui_qt/historical_resolver.py` (`QtHistoricalConflictResolver`)
* **Wiring Contract**:
  - Dual-pane layout. Left list of discrepancy fields (`list_field_directory`); right scroll area with comparison cards (`cards_container`, `cards_vlayout`), suggestion chips, manual override entry, and confirmation buttons.
  - Toggles: `chk_show_all` (reloads suggestions including non-conflicting fields), `chk_sort_alpha` (toggles alphabetical vs. column-order field sorting).
  - Actions: `btn_apply_all` (applies all resolved suggestions or manual overrides, triggers undo push and dataframe updates), `btn_close`.
* **Widget Object Catalog**:
  - `HistoricalConflictResolver` (`QDialog` root)
  - `header_frame`, `lbl_main_title`
  - `main_splitter`
  - `sidebar_frame`, `dir_header_frame`, `lbl_dir_title`, `list_field_directory` (`QListWidget`), `sidebar_bottom_frame`, `chk_show_all` (`QCheckBox`), `chk_sort_alpha` (`QCheckBox`)
  - `right_area`, `context_header_frame`, `lbl_issue_count`, `lbl_issue_subtitle`
  - `scroll_cards_area` (`QScrollArea`), `cards_container` (`QWidget`), `cards_vlayout` (`QVBoxLayout`)
  - Card Item Template: `sample_card_genus`, `genus_header_bar`, `lbl_genus_card_title`, `lbl_genus_code`, `box_cur_val`, `lbl_val_genus`, `btn_sug_genus_1`, `input_manual_genus`, `btn_apply_single`
  - `footer_frame`, `lbl_stats`, `btn_close` (`QPushButton`), `btn_apply_all` (`QPushButton`)

---

### 3.9 Object Problem Resolver (Single / Queue Mode)
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/object_problem_resolver.py` (`ObjectProblemResolver`)
* **UI File**: `pyside_new_uis/object_problem_resolver.ui`
* **Target Controller**: `ui_qt/object_problem_resolver.py` (`QtObjectProblemResolver`)
* **Wiring Contract**:
  - Dual-mode resolver (Single object or multi-object queue).
  - Queue Navigation (when in queue mode): `queue_nav_bar`, `btn_queue_prev`, `lbl_queue_info`, `btn_queue_next`, `btn_skip_object`.
  - Left Sidebar: `list_field_directory` (`QListWidget`), `chk_show_all`, `chk_sort_alpha`.
  - Right Cards Area: `scroll_cards_area`, `cards_container`, `cards_vlayout`.
  - Dynamic Card Schema: `sample_problem_card`, `prob_header_bar`, `lbl_prob_card_title`, `lbl_prob_code`, `box_cur_val`, `lbl_val_species`, `box_gbif_match`, `btn_gbif_match`, `lbl_gbif_tag`, `input_manual_species`, `btn_apply_single`.
  - Footer Actions: `lbl_stats`, `btn_skip_object`, `btn_close`, `btn_apply_all`.
* **Widget Object Catalog**:
  - `ObjectProblemResolver` (`QDialog` root)
  - `header_frame`, `lbl_main_title`
  - `queue_nav_bar`, `btn_queue_prev` (`QPushButton`), `lbl_queue_info` (`QLabel`), `btn_queue_next` (`QPushButton`)
  - `main_splitter`
  - `sidebar_frame`, `dir_header_frame`, `lbl_dir_title`, `list_field_directory` (`QListWidget`), `sidebar_bottom_frame`, `chk_show_all` (`QCheckBox`), `chk_sort_alpha` (`QCheckBox`)
  - `right_area`, `context_header_frame`, `lbl_issue_count`, `lbl_issue_subtitle`
  - `scroll_cards_area` (`QScrollArea`), `cards_container` (`QWidget`), `cards_vlayout` (`QVBoxLayout`)
  - Problem Card Template: `sample_problem_card`, `prob_header_bar`, `lbl_prob_card_title`, `lbl_prob_code`, `box_cur_val`, `lbl_val_species`, `box_gbif_match`, `btn_gbif_match`, `lbl_gbif_tag`, `input_manual_species`, `btn_apply_single`
  - `footer_frame`, `lbl_stats`, `btn_skip_object` (`QPushButton`), `btn_close` (`QPushButton`), `btn_apply_all` (`QPushButton`)

---

### 3.10 Ignored Words Configuration Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/ignored_words_dialog.py` (`open_ignored_words_editor`)
* **UI File**: `pyside_new_uis/ignored_words_dialog.ui`
* **Target Controller**: `ui_qt/ignored_words_dialog.py` (`QtIgnoredWordsDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, ignored_words: list[str] = None, include_variations: bool = True, save_callback = None)`
  - Reads line-separated words from `text_ignored_words`, checkbox state `chk_variations`.
  - On `btn_save`, invokes `save_callback(words, include_variations)` and persists configuration.
* **Widget Object Catalog**:
  - `IgnoredWordsDialog` (`QDialog` root)
  - `header_frame`, `lbl_header_title`, `lbl_header_desc`
  - `text_ignored_words` (`QPlainTextEdit`)
  - `chk_variations` (`QCheckBox`)
  - `footer_frame`, `btn_cancel` (`QPushButton`), `btn_save` (`QPushButton`)

---

### 3.11 Keyboard Shortcuts HUD Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/help_dialogs.py` (`show_shortcuts`)
* **UI File**: `pyside_new_uis/shortcuts_hud_dialog.ui`
* **Target Controller**: `ui_qt/shortcuts_hud_dialog.py` (`QtShortcutsHUDDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None)`
  - Real-time filtering: Typing into `entry_search` dynamically filters visible shortcut rows inside `scroll_contents` matching text in `key-*` or `desc-*`.
  - Pressing Escape or clicking `btn_close` dismisses the HUD.
* **Widget Object Catalog**:
  - `ShortcutsHUDDialog` (`QDialog` root)
  - `title_frame`, `lbl_hud_title`, `lbl_hud_subtitle`
  - `search_card`, `lbl_search_icon`, `entry_search` (`QLineEdit`)
  - `scroll_area` (`QScrollArea`), `scroll_contents` (`QWidget`), `scroll_layout` (`QVBoxLayout`)
  - Shortcut row frames: `row_nav_prevnext`, `row_nav_history`, `row_focus_search`, `row_focus_mode`, `row_edit_save`, `row_edit_reviewed`
  - `footer_frame`, `lbl_footer_hint`, `btn_close` (`QPushButton`)

---

### 3.12 Arbor Help Center Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/help_dialogs.py` (`open_help_window`)
* **UI File**: `pyside_new_uis/help_center_dialog.ui`
* **Target Controller**: `ui_qt/help_center_dialog.py` (`QtHelpCenterDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None)`
  - Launches interactive tutorial controllers or opens external documentation / User Guide / shortcuts dialogs.
* **Widget Object Catalog**:
  - `HelpCenterDialog` (`QDialog` root)
  - `lbl_header`, `sep_line`
  - Action buttons: `btn_tut_review`, `btn_tut_conflicts`, `btn_tut_databases`, `btn_user_guide`, `btn_shortcuts`, `btn_quick_start`, `btn_about`
  - `btn_close` (`QPushButton`)

---

### 3.13 Error Traceback & Crash Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/main_window.py` (`show_traceback_dialog`)
* **UI File**: `pyside_new_uis/error_traceback_dialog.ui`
* **Target Controller**: `ui_qt/error_traceback_dialog.py` (`QtErrorTracebackDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, title: str = "Application Error", message: str = "", traceback_text: str = "", is_crash: bool = False)`
  - `btn_copy`: Copies `traceback_text` to system clipboard and temporarily changes label to "Copied!".
  - `btn_close`: Closes dialog.
* **Widget Object Catalog**:
  - `ErrorTracebackDialog` (`QDialog` root)
  - `lbl_error_message` (`QLabel`)
  - `text_traceback` (`QPlainTextEdit` read-only)
  - `btn_copy` (`QPushButton`), `btn_close` (`QPushButton`)

---

### 3.14 Autosave Archive Manager Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/autosave_handler.py` (`open_autosave_manager`)
* **UI File**: `pyside_new_uis/autosave_manager_dialog.ui`
* **Target Controller**: `ui_qt/autosave_manager_dialog.py` (`QtAutosaveManagerDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, autosave_dir: str = "", on_restore_callback = None)`
  - Lists archived files in `list_archives`.
  - `btn_restore`: Confirms and invokes `on_restore_callback(selected_path)`.
  - `btn_delete`: Deletes selected archive file from disk and list.
  - `btn_delete_all`: Clears all archive files with confirmation prompt.
  - `btn_close`: Closes dialog.
* **Widget Object Catalog**:
  - `AutosaveManagerDialog` (`QDialog` root)
  - `lbl_title`, `lbl_subtitle`
  - `list_archives` (`QListWidget`)
  - `btn_restore`, `btn_delete`, `btn_delete_all`, `btn_close`

---

### 3.15 Filter Builder Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/filter_dialog.py` (`FilterDialogController`)
* **UI File**: `pyside_new_uis/filter_dialog.ui`
* **Target Controller**: `ui_qt/filter_dialog.py` (`QtFilterDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None, on_apply_callback=None)`
  - **Tristate Checkbox Behavior**: All filter criteria checkboxes are configured with `tristate=True` and cycle through all 3 states:
    - `Qt.CheckState.Unchecked` (0): **Blank / Ignore** (filter omitted)
    - `Qt.CheckState.PartiallyChecked` (1): **Minus `−` / Not** (filter matches objects *without* this property / False)
    - `Qt.CheckState.Checked` (2): **Checkmark `✓` / Has** (filter matches objects *with* this property / True)
  - Controls: `tab_widget` containing tabs for `Status & General`, `Problems & History`, `Images`, and `Location`.
  - `entry_search`: Real-time highlight filter search.
  - `btn_reset_all`: Resets all filter inputs to defaults (Unchecked / Blank).
  - `btn_apply`: Compiles active filter dictionary, emits or calls `on_apply_callback(filter_dict)`, and closes.
* **Widget Object Catalog**:
  - `FilterDialog` (`QDialog` root)
  - `header_frame`, `lbl_title`, `search_frame`, `entry_search`, `btn_load_preset`, `btn_save_preset`
  - `tab_widget`:
    - `tab_status`: `chk_reviewed`, `chk_has_history`, `chk_has_unvalidated`, `chk_has_comment`, `chk_has_location_comment`, `chk_search_old_taxonomy`, `entry_old_taxonomy`
    - `tab_problems`: `chk_prob_species`, `chk_prob_genus`, `chk_prob_family`, `chk_prob_collector`, `chk_prob_country`, `chk_any_problem`, `chk_historical_data`
    - `tab_images`: `chk_has_images`, `chk_prob_image`
    - `tab_location`: `combo_loc_stored_as`, `entry_loc_building`, `entry_loc_room`, `entry_loc_cabinet`
  - `footer_frame`, `btn_reset_all`, `btn_cancel`, `btn_apply`

---

### 3.16 Recent Activity & Audit Log Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/recent_activity_dialog.py` (`RecentActivityDialog`)
* **UI File**: `pyside_new_uis/recent_activity_dialog.ui`
* **Target Controller**: `ui_qt/recent_activity_dialog.py` (`QtRecentActivityDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None, on_select_object=None, on_revert_callback=None)`
  - `entry_search`: Filter tree items dynamically.
  - Action chips: Filter by action type (`btn_chip_all`, `btn_chip_manual`, `btn_chip_mobile`, `btn_chip_conflict`, `btn_chip_gbif`).
  - `tab_widget`:
    - `tree_visited`: Displays visited object history.
    - `tree_edits`: Displays mutation log (`OBJECT ID`, `TIME`, `ACTION`, `CHANGES`).
  - `btn_open_selected`: Invokes `on_select_object(oid)`.
  - `btn_revert`: Invokes `on_revert_callback(log_entry_id)`.
* **Widget Object Catalog**:
  - `RecentActivityDialog` (`QDialog` root)
  - `header_frame`, `lbl_title`, `btn_refresh`, `lbl_desc`
  - `toolbar_frame`, `entry_search`, `btn_clear`, `btn_chip_all`, `btn_chip_manual`, `btn_chip_mobile`, `btn_chip_conflict`, `btn_chip_gbif`
  - `tab_widget`, `tree_visited`, `tree_edits`
  - `footer_frame`, `btn_open_selected`, `btn_revert`, `btn_close`

---

### 3.17 Database Statistics & Dashboard Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/dashboard.py` (`DashboardMixin.show_statistics`)
* **UI File**: `pyside_new_uis/dashboard_dialog.ui`
* **Target Controller**: `ui_qt/dashboard_dialog.py` (`QtDashboardDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None)`
  - Reads data from `app_state` (total objects, reviewed count, problem count, actionable count).
  - Populates metric rows and updates `prog_reviewed` progress bar.
  - `btn_save_stats`: Exports session statistics to report/file.
  - `btn_close`: Closes dialog.
* **Widget Object Catalog**:
  - `DashboardDialog` (`QDialog` root)
  - `header_frame`, `lbl_title`
  - `scroll_area`, `card_overall`, `card_session`
  - Metric labels: `lbl_total_val`, `lbl_reviewed_val`, `lbl_not_reviewed_val`, `lbl_probs_val`, `lbl_actionable_val`, `lbl_image_probs_val`, `lbl_unknown_val`, `lbl_filtered_val`, `lbl_sess_reviewed_val`, `lbl_sess_solved_val`, `lbl_sess_observed_val`
  - `prog_reviewed` (`QProgressBar`)
  - `footer_frame`, `btn_save_stats`, `btn_close`

---

### 3.18 Image Source Settings Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/image_handler.py` (`open_image_menu`)
* **UI File**: `pyside_new_uis/image_settings_dialog.ui`
* **Target Controller**: `ui_qt/image_settings_dialog.py` (`QtImageSettingsDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, current_mode: str = "folder", on_mode_change=None)`
  - Displays current mode in `lbl_active_mode_badge`.
  - Buttons invoke folder selectors or toggle online/offline repository modes.
* **Widget Object Catalog**:
  - `ImageSettingsDialog` (`QDialog` root)
  - `lbl_header`, `status_card`, `lbl_active_mode_label`, `lbl_active_mode_badge`
  - Action buttons: `btn_select_folder`, `btn_add_folder`, `btn_online_repo`, `btn_disable_images`
  - `btn_close` (`QPushButton`)

---

### 3.19 GBIF Record Update Reconciliation Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/gbif_dialog.py` (`GBIFUpdateDialog`)
* **UI File**: `pyside_new_uis/gbif_update_dialog.ui`
* **Target Controller**: `ui_qt/gbif_update_dialog.py` (`QtGBIFUpdateDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, updates: list[dict] = None, apply_callback=None)`
  - Dynamically populates comparative diff cards (`sample_update_card` template).
  - Quick actions: `btn_select_all`, `btn_deselect_all`.
  - `btn_reject_all`: Discards proposed updates.
  - `btn_apply`: Collects approved fields and triggers `apply_callback(selected_updates)`.
* **Widget Object Catalog**:
  - `GBIFUpdateDialog` (`QDialog` root)
  - `header_frame`, `lbl_title`
  - `ctx_header`, `lbl_review_count`, `lbl_review_desc`, `btn_select_all`, `btn_deselect_all`
  - `scroll_area`, `scroll_contents`, `scroll_layout`, `sample_update_card`, `card_chk_apply`, `lbl_val_current`, `lbl_val_gbif`
  - `footer_frame`, `lbl_stats`, `btn_reject_all`, `btn_cancel`, `btn_apply`

---

### 3.20 GBIF Batch Analysis Configuration Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/gbif_batch_config.py` (`GBIFBatchConfigDialog`)
* **UI File**: `pyside_new_uis/gbif_batch_config_dialog.ui`
* **Target Controller**: `ui_qt/gbif_batch_config_dialog.py` (`QtGBIFBatchConfigDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, main_app=None, on_start_batch=None)`
  - Scope selection: `rb_scope_filtered`, `rb_scope_selected`, `rb_scope_all`.
  - Mode selection: `rb_undet_safe`, `rb_undet_exclude`.
  - Configuration flags: `chk_fuzzy_matching`, `chk_author_reconcile`, `chk_higher_rank`.
  - `btn_start`: Emits/invokes `on_start_batch(scope, options_dict)`.
* **Widget Object Catalog**:
  - `GBIFBatchConfigDialog` (`QDialog` root)
  - `header_frame`, `lbl_title`
  - `safety_card`, `lbl_safety_title`, `lbl_safety_desc`
  - `scope_card`, `rb_scope_filtered`, `rb_scope_selected`, `rb_scope_all`
  - `mode_card`, `rb_undet_safe`, `rb_undet_exclude`
  - `options_card`, `chk_fuzzy_matching`, `chk_author_reconcile`, `chk_higher_rank`
  - `progress_frame`, `lbl_progress_status`, `lbl_progress_pct`, `prog_bar`, `lbl_progress_detail`
  - `footer_frame`, `lbl_summary`, `btn_cancel`, `btn_start`

---

### 3.21 Batch Add Fields Sub-Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/new_database_wizard.py` (`_prompt_batch_add_fields`)
* **UI File**: `pyside_new_uis/batch_add_fields_dialog.ui`
* **Target Controller**: `ui_qt/batch_add_fields_dialog.py` (`QtBatchAddFieldsDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, on_fields_added_callback=None)`
  - Parses field names separated by comma or newlines from `text_field_names`.
  - Reads selected default data type from `combo_default_type`.
  - Invokes `on_fields_added_callback(field_list, default_type)` and closes.
* **Widget Object Catalog**:
  - `BatchAddFieldsDialog` (`QDialog` root)
  - `lbl_header_title`, `lbl_header_subtitle`
  - `text_field_names` (`QPlainTextEdit`)
  - `lbl_default_type`, `combo_default_type` (`QComboBox`)
  - `btn_cancel` (`QPushButton`), `btn_add_fields` (`QPushButton`)

---

### 3.22 Move Field Sub-Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/group_editor.py` (`_open_move_dialog`)
* **UI File**: `pyside_new_uis/move_field_dialog.ui`
* **Target Controller**: `ui_qt/move_field_dialog.py` (`QtMoveFieldDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, fields_to_move: list[str]=None, available_tabs: list[str]=None, on_move_callback=None)`
  - Reorders fields with `btn_move_up` and `btn_move_down`.
  - On `btn_confirm`, invokes `on_move_callback(target_tab, working_fields)` and closes.
* **Widget Object Catalog**:
  - `MoveFieldDialog` (`QDialog` root)
  - `lbl_header_title`, `lbl_dest`, `combo_destination` (`QComboBox`)
  - `card_list`, `hdr_list`, `lbl_list_title`, `list_fields` (`QListWidget`)
  - `btn_move_up` (`QPushButton`), `btn_move_down` (`QPushButton`)
  - `btn_cancel` (`QPushButton`), `btn_confirm` (`QPushButton`)

---

### 3.23 Registration Tabs & Field Group Editor Window
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/group_editor.py` (`GroupEditorWindow`)
* **UI File**: `pyside_new_uis/group_editor_window.ui`
* **Target Controller**: `ui_qt/group_editor_window.py` (`QtGroupEditorWindow`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None, on_save_callback=None)`
  - Manages tab groups on the left (`tabs_listbox`) and fields on the right (`fields_listbox`).
  - Supports reordering (`btn_move_up`, `btn_move_down`), renaming, adding, deleting, and moving to tab.
  - On `btn_save`, invokes `on_save_callback(groups)` and triggers layout updates.
* **Widget Object Catalog**:
  - `GroupEditorWindow` (`QDialog` root)
  - `header_frame`, `lbl_header_title`, `main_splitter`
  - `card_tabs`, `tabs_listbox`, `btn_add_tab`, `btn_rename_tab`, `btn_del_tab`
  - `card_fields`, `fields_listbox`, `btn_move_up`, `btn_move_down`, `btn_move_to_tab`, `btn_add_field`, `btn_rename_field`, `btn_del_field`
  - `btn_cancel`, `btn_save`

---

### 3.24 Advanced System Settings & Engine Flags Window
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/advanced_settings.py` (`AdvancedSettingsWindow`)
* **UI File**: `pyside_new_uis/advanced_settings_window.ui`
* **Target Controller**: `ui_qt/advanced_settings_window.py` (`QtAdvancedSettingsWindow`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None, on_save_callback=None)`
  - Controls: `tab_widget` containing `tab_system`, `tab_graphics`, `tab_ux`, `tab_tools`.
  - Persists flags to user preferences and emits `SETTINGS_CHANGED`.
* **Widget Object Catalog**:
  - `AdvancedSettingsWindow` (`QDialog` root)
  - `header_frame`, `lbl_header_title`, `tab_widget`
  - `chk_excel_backup`, `combo_archive_limit`, `combo_log_verbosity`, `combo_resampling`, `entry_url_override`, `chk_bulk_editor`, `chk_focus_toggle`
  - `btn_reset_defaults`, `btn_cancel`, `btn_save`

---

### 3.25 Unified Application Settings Window
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/unified_settings.py` (`UnifiedSettingsWindow`)
* **UI File**: `pyside_new_uis/unified_settings_window.ui`
* **Target Controller**: `ui_qt/unified_settings_window.py` (`QtUnifiedSettingsWindow`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None, initial_tab="general", on_save_callback=None)`
  - Left vertical navigation: `btn_tab_general`, `btn_tab_layout`, `btn_tab_system`, `btn_tab_images`, `btn_tab_taxonomy`, `btn_tab_tools`.
  - Right scrollable card area with workflow switches (`chk_auto_advance_history`, `chk_strict_validation`, `chk_focus_fallback`, `chk_snap_lock`).
  - On `btn_save`, commits preferences and notifies `app_bus`.
* **Widget Object Catalog**:
  - `UnifiedSettingsWindow` (`QDialog` root)
  - `header_frame`, `lbl_header_title`, `lbl_header_subtitle`
  - `sidebar_frame`, `btn_tab_general`, `btn_tab_layout`, `btn_tab_system`, `btn_tab_images`, `btn_tab_taxonomy`, `btn_tab_tools`
  - `scroll_area`, `card_review_workflow`, `chk_auto_advance_history`, `chk_strict_validation`
  - `card_focus_mode`, `chk_focus_fallback`, `chk_snap_lock`
  - `footer_frame`, `btn_reset_defaults`, `btn_cancel`, `btn_save`

---

### 3.26 Mobile Companion Host Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/mobile_dialog.py` & `ui/mobile_panel.py` (`MobileDialog`, `MobilePanel`)
* **UI File**: `pyside_new_uis/mobile_companion_dialog.ui`
* **Target Controller**: `ui_qt/mobile_companion_dialog.py` (`QtMobileCompanionDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None, port: int = 5055, on_end_session=None, on_edit=None, reuse_server=None)`
  - Controls: `stacked_pages` containing `page_setup` (index 0) and `page_active` (index 1).
  - On setup: `btn_net_public` vs `btn_net_local`, `btn_prov_cf` vs `btn_prov_pinggy`, `btn_ver_v2` vs `btn_ver_v1`, `btn_start_session`.
  - On active: `lbl_qr_image` (renders QPixmap of QR code), `edit_url`, `lbl_pin_badge`, `lbl_tunnel_status`, `list_feed` (event activity), `btn_end_session`.
* **Widget Object Catalog**:
  - `MobileCompanionDialog` (`QDialog` root)
  - `lbl_header_title`, `lbl_header_subtitle`, `lbl_db_info`
  - `stacked_pages`, `page_setup`, `page_active`
  - Page Setup: `frame_setup_status`, `frame_setup_card`, `btn_net_public`, `btn_net_local`, `btn_prov_cf`, `btn_prov_pinggy`, `btn_ver_v2`, `btn_ver_v1`, `btn_start_session`
  - Page Active: `frame_status_bar`, `lbl_status_dot`, `lbl_status_text`, `lbl_client_badge`, `lbl_qr_image`, `btn_qr_public`, `btn_qr_local`, `edit_url`, `lbl_pin_badge`, `lbl_tunnel_status`, `btn_active_ver_v2`, `btn_active_ver_v1`, `chk_simultaneous_edit`, `group_recent_activity`, `list_feed`, `btn_end_session`

---

### 3.27 GBIF Taxonomic Reconciliation & Review Dialog
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/gbif_review.py` (`GBIFReviewDialog`)
* **UI File**: `pyside_new_uis/gbif_review_dialog.ui`
* **Target Controller**: `ui_qt/gbif_review_dialog.py` (`QtGBIFReviewDialog`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None, diff_results: list[dict] = None, on_applied_callback=None)`
  - Triage category buttons: `btn_tab_pending`, `btn_tab_rank_discrepancy`, `btn_tab_verified`, `btn_tab_accepted`, `btn_tab_missing_metadata`, `btn_tab_undetermined`, `btn_tab_synonym`, `btn_tab_applied`.
  - Specimen Directory (left): `scroll_dir_content` populated with specimen item widgets.
  - Diff Cards Container (right): `scroll_cards_content` populated with taxonomic comparison diff cards.
  - Pagination: `btn_first`, `btn_prev`, `lbl_page_num`, `btn_next`, `btn_last`, `combo_page_size`.
  - Batch Actions: `btn_select_all`, `btn_deselect_all`, `btn_select_page`, `btn_select_verified`, `btn_close`, `btn_apply`.
* **Widget Object Catalog**:
  - `GBIFReviewDialog` (`QDialog` root)
  - `frame_header`, `lbl_header_title`, `btn_fullscreen`, `edit_search`
  - `frame_tabs`, `btn_tab_pending`, `btn_tab_rank_discrepancy`, `btn_tab_verified`, `btn_tab_accepted`, `btn_tab_missing_metadata`, `btn_tab_undetermined`, `btn_tab_synonym`, `btn_tab_applied`
  - `frame_tip`, `lbl_tip`
  - `splitter_main`, `frame_sidebar`, `scroll_dir`, `scroll_dir_content`, `frame_right`
  - `frame_pagination`, `lbl_page_info`, `btn_first`, `btn_prev`, `lbl_page_num`, `btn_next`, `btn_last`, `combo_page_size`
  - `scroll_cards`, `scroll_cards_content`
  - `frame_bottom`, `btn_select_all`, `btn_deselect_all`, `btn_select_page`, `btn_select_verified`, `lbl_summary`, `btn_close`, `btn_apply`

---

### 3.28 Add Objects Wizard
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/add_objects.py` (`AddObjectsWizard`)
* **UI File**: `pyside_new_uis/add_objects_wizard.ui`
* **Target Controller**: `ui_qt/add_objects_wizard.py` (`QtAddObjectsWizard`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app_state=None, main_window=None)`
  - 3-step sequence navigated via `stacked_steps`:
    - Step 1 (IDs): `spin_count`, `btn_generate_auto`, `edit_manual_ids`, `btn_add_manual`, `list_target_ids`, `btn_remove_id`.
    - Step 2 (Metadata): `list_edit_objects`, dynamic fields in `scroll_form_content`.
    - Step 3 (Review): `lbl_summary_count`.
  - Navigation: `btn_cancel`, `btn_back`, `btn_next` ("Next →" / "Create Objects").
  - On create: Commits staged rows into `app_state.df_reg`, `df_obs`, publishes `DATABASE_UPDATED`.
* **Widget Object Catalog**:
  - `AddObjectsWizard` (`QDialog` root)
  - `frame_header`, `lbl_wizard_title`, `lbl_step_subtitle`, `frame_stepper`, `lbl_step_1`, `lbl_step_2`, `lbl_step_3`
  - `stacked_steps`, `page_step1`, `page_step2`, `page_step3`
  - Step 1: `group_auto_gen`, `spin_count`, `btn_generate_auto`, `group_manual_entry`, `edit_manual_ids`, `btn_add_manual`, `list_target_ids`, `btn_remove_id`
  - Step 2: `list_edit_objects`, `scroll_form`, `scroll_form_content`
  - Step 3: `frame_step3_center`, `lbl_ready_title`, `lbl_summary_count`, `lbl_commit_hint`
  - Footer: `frame_footer`, `btn_cancel`, `btn_back`, `btn_next`

---

### 3.29 New Database Setup Wizard
* **Status**: `🟡 READY FOR WIRING`
* **Original Tkinter**: `ui/new_database_wizard.py` (`NewDatabaseWizard`)
* **UI File**: `pyside_new_uis/new_database_wizard.ui`
* **Target Controller**: `ui_qt/new_database_wizard.py` (`QtNewDatabaseWizard`)
* **Wiring Contract**:
  - **Constructor**: `__init__(self, parent=None, app=None, on_complete=None, edit_config=None, edit_mode=False)`
  - 6-step wizard using `stacked_steps`:
    - Step 1: `radio_template_botany`, `radio_template_loans`, `radio_template_paleo`, `radio_template_minimal`, `radio_template_import`, `edit_import_path`, `btn_browse_import`.
    - Step 2: `edit_new_field`, `combo_new_field_type`, `btn_add_field`, `btn_batch_add_fields`, `btn_restore_template`, `btn_clear_fields`, `table_fields`.
    - Step 3: `list_categories`, `btn_add_category`, `btn_rename_category`, `btn_delete_category`, `list_assigned_fields`, `btn_move_field_up`, `btn_move_field_down`, `btn_remove_from_cat`.
    - Step 4: `table_flags`, `edit_custom_flag_name`, `combo_flag_maps_to`, `btn_add_custom_flag`, `list_custom_flags`, `btn_remove_custom_flag`.
    - Step 5: `chk_enable_images`, `edit_image_url_pattern`, `edit_test_id`, `lbl_url_preview`, `chk_module_location`, `chk_module_loans`, `chk_module_condition`.
    - Step 6: `edit_profile_name`, `edit_start_id`, `spin_initial_rows`, `edit_output_path`, `btn_browse_output`.
  - Navigation: `btn_cancel`, `btn_back`, `btn_next` ("Next Step →" / "Create Database").
* **Widget Object Catalog**:
  - `NewDatabaseWizard` (`QDialog` root)
  - `frame_header`, `lbl_wizard_title`, `lbl_step_indicator`, `frame_stepper`, `btn_step_1`, `btn_step_2`, `btn_step_3`, `btn_step_4`, `btn_step_5`, `btn_step_6`
  - `stacked_steps`, `page_step1`, `page_step2`, `page_step3`, `page_step4`, `page_step5`, `page_step6`
  - Step 1: `radio_template_botany`, `radio_template_loans`, `radio_template_paleo`, `radio_template_minimal`, `radio_template_import`, `edit_import_path`, `btn_browse_import`
  - Step 2: `edit_new_field`, `combo_new_field_type`, `btn_add_field`, `btn_batch_add_fields`, `btn_restore_template`, `btn_clear_fields`, `table_fields`
  - Step 3: `list_categories`, `btn_add_category`, `btn_rename_category`, `btn_delete_category`, `list_assigned_fields`, `btn_move_field_up`, `btn_move_field_down`, `btn_remove_from_cat`
  - Step 4: `table_flags`, `edit_custom_flag_name`, `combo_flag_maps_to`, `btn_add_custom_flag`, `list_custom_flags`, `btn_remove_custom_flag`
  - Step 5: `chk_enable_images`, `edit_image_url_pattern`, `edit_test_id`, `lbl_url_preview`, `chk_module_location`, `chk_module_loans`, `chk_module_condition`
  - Step 6: `lbl_summary_template`, `lbl_summary_fields`, `lbl_summary_groups`, `lbl_summary_flags`, `lbl_summary_modules`, `edit_profile_name`, `edit_start_id`, `spin_initial_rows`, `edit_output_path`, `btn_browse_output`
  - Footer: `frame_bottom`, `btn_cancel`, `btn_back`, `btn_next`

---

## 4. Updates & Maintenance Rule for Agents

Whenever a Phase 1 Extraction agent finishes verifying a `.ui` file:
1. Append or update the entry in **Section 2 (Summary Table)** to `🟡 READY FOR WIRING`.
2. Add a detailed subsection under **Section 3** specifying the exact Widget Object Names, constructor arguments, and signal/callback signatures.
3. Commit or preserve this document so parallel Phase 2 agents have uninterrupted, self-documenting assignments.
