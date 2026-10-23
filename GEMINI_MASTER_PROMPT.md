# Arbor Application Master Implementation Plan

You are an expert Python and JavaScript developer. This document contains a comprehensive, multi-step execution plan to implement several interconnected features in the Arbor museum object visualizer application (a Python/Tkinter desktop client and a Flask-based mobile web companion).

Please read through this entire plan carefully. Your goal is to implement all changes seamlessly across the Desktop and Mobile environments, ensuring no existing functionality is broken and that new UI elements fit naturally into the current architecture.

## Overview of Features to Implement

1.  **Taxonomic Mass Update via GBIF (Desktop Only):**
    *   Implement a background worker to query the GBIF API (`https://api.gbif.org/v1/species/match`) for a selected batch of objects.
    *   Build a "Review Updates" Tkinter dialog to show a diff of proposed taxonomy changes.
    *   Log the *old taxonomy* data securely into the existing `Log` worksheet (`df_log`) using a standard audit trail format (e.g., Action: `GBIF_UPDATE`, with `ChangedFields` and `ChangedValues`).
    *   Add a way in the Desktop UI to view this old taxonomy and optionally revert the GBIF changes if a mistake was made.
2.  **"Unvalidated Source" Flags (Desktop & Mobile):**
    *   Create a new data layer table/sheet called `Unvalidated_source` (loaded as `df_unvalidated`) to store metadata about specific fields that need double-checking. Columns: `ObjectID`, `Field_Name`, `Unvalidated_Comment`.
    *   Add a toggle button (using a suitable `pytablericons` icon, like a question mark) next to *every editable field* in both Desktop and Mobile forms. Clicking it reveals a comment box to explain why the source is unvalidated.
    *   Display a small unvalidated badge/icon on object list cards. This must appear *alongside* existing status badges (like the photo count or loaned badge), not overwrite them.
3.  **Unified REV+ERR Visual State (Desktop & Mobile):**
    *   Fix the UI inconsistency where objects that are both "Reviewed" and "Have a Problem" don't display their dual state correctly.
    *   Introduce a new 7th status tier (`REV+ERR`) across the board.
4.  **Expanded Filtering (Desktop):**
    *   Add new filter checkboxes in the search/filter dialog (`ui/filter_dialog.py`): "Has Unvalidated Source", "REV+ERR", and "Search for old taxonomy" (which queries `df_log` for previous values).

---

## Step-by-Step Execution Plan for Gemini

### Phase 1: Data Architecture Expansion (`df_unvalidated`)
**Goal & Intent:** Prepare the underlying data storage and state management systems so they can hold and persist the new 'Unvalidated Source' flags without breaking existing file formats. We are adding a new sheet/table that ties flags to specific ObjectIDs and fields.
Modify Arbor's data IO logic to support reading and writing the new `Unvalidated_source` sheet alongside existing data, and prepare the state management.
1.  **`models.py`:** Add `self.df_unvalidated: pd.DataFrame | None = None` to the `AppState` class.
2.  **`repository.py`:**
    *   Update `_normalise_dataframes`, `generate_empty_dataframes`, `load_sqlite`, `save_sqlite`, `load_excel`, `save_excel`, and `export_to_excel` to support `df_unvalidated`.
    *   Create a helper `_normalise_unvalidated_dataframe(df)` that ensures the DataFrame always has the columns `ObjectID`, `Field_Name`, and `Unvalidated_Comment`.

### Phase 2: Unified REV+ERR Visual State & Tests
**Goal & Intent:** Resolve the UI inconsistency across Desktop and Mobile by ensuring that objects which are both 'Reviewed' but still have unresolved 'Problems' clearly display a warning state, rather than a completely green 'OK' state.
Ensure the "Reviewed + Error" state is visually distinct on both platforms.
1.  **Desktop UI (`ui/main_window.py`):**
    *   Locate the `_update_row_appearance` or `refresh_list` logic. When an object is reviewed and `has_problem` is true, set the color to `"#ffb366"` (dark mode) or `"#f0ad4e"` (light mode).
    *   Update `update_list_item_color` so it checks `if reviewed and has_problem:` *first* before applying the standard green reviewed color.
2.  **Mobile UI (`backend/mobile_server.py`):**
    *   Locate the `renderStatusBadge(item)` function within the `INDEX_TEMPLATE` JavaScript.
    *   Before it checks `if (isRev)`, add a condition for `if (isRev && hasFlags)`. If true, return the badge: `label = 'REV+ERR'; bg = '#F57C00'; fg = '#ffffff'; border = '#F57C00'; icon = '⚠';`
3.  **Tests (`tests/test_mobile_companion.py`):**
    *   Expand `test_status_flags_and_six_tier_badge_parity`. Add a 9th mock object (Obj 9) where "Reviewed" is True and "MissingLabel" is True.
    *   Assert that `/api/objects` returns `total_matching == 9`. Add assertions ensuring Obj 9 has `review_status == "reviewed"`, `has_flags == True`, etc.
    *   Update assertions for `status=reviewed` and `status=flagged` filters to expect Obj 9.

### Phase 3: "Unvalidated Source" UI & Mobile Sync
**Goal & Intent:** Create the user interface for marking fields as unvalidated and capturing comments explaining why. Ensure these flags are smoothly synchronized between the Desktop app and the Mobile companion, including offline support via IndexedDB.
Implement the field-level flagging system.
1.  **Desktop Entry Toggles (`ui/registry_panel.py`):**
    *   When building the entry fields, add a small toggle button (using a `pytablericons` icon) next to every editable field.
    *   Clicking the toggle should dynamically show/hide a small text box directly below or beside the field for the `Unvalidated_Comment`.
    *   Wire these toggles to update `app_state.df_unvalidated` for the active object.
2.  **Desktop Badges (`ui/widgets.py` & `ui/main_window.py`):**
    *   In the list cards (e.g., `_create_badge` logic in `ui/widgets.py`), add a new visual badge for "Unvalidated" that appears alongside existing status badges (similar to how the 'Loaned' badge is handled). Do not overwrite the main `ERR/OK` badges.
3.  **Mobile Backend & Sync (`backend/mobile_server.py`):**
    *   Update `_apply_dataframe_updates` and `_execute_record_update` to process incoming changes to unvalidated source flags.
    *   Ensure the active unvalidated flags are embedded in the `/api/objects` and `/api/object/<id>` payloads.
4.  **Mobile Frontend (`INDEX_TEMPLATE`):**
    *   Add similar toggle buttons and hidden comment boxes to the mobile HTML form fields.
    *   Ensure modifications to unvalidated flags trigger `markDirty()` and sync correctly via `saveCurrentEdits` and `/api/batch_update` to the local IndexedDB queue.
    *   Update the mobile list view to display the unvalidated badge adjacent to the primary status badge.

### Phase 4: Taxonomic Mass Update via GBIF (Desktop Only)
**Goal & Intent:** Provide a bulk-update mechanism for taxonomic data by querying the GBIF API. This will save curators significant time while ensuring that all original taxonomic data is preserved securely in the `Log` sheet for easy auditing and potential rollback.
Implement the batch lookup and review workflow, strictly reusing the `Log` sheet for history.
1.  **GBIF Background Worker (`backend/task_queue.py` or new module):**
    *   Create a task that accepts a list of ObjectIDs, retrieves their current taxonomy (Genus, Species, Family), and queries the GBIF API (`https://api.gbif.org/v1/species/match`).
    *   Compare local vs GBIF data to generate a list of proposed diffs. Ensure this runs without blocking the Tkinter main loop.
2.  **Review UI (`ui/gbif_review.py` or similar):**
    *   Build a new Tkinter dialog to present the proposed updates (Old vs. New) in a Treeview. Include checkboxes to selectively approve/reject changes, and an "Approve All" button.
3.  **Update & Logging Logic:**
    *   Upon approval, update `df_reg` with the new GBIF taxonomy.
    *   Crucially, capture the *old taxonomy* values and append them to `app_state.df_log` (using `app_state._log_records` or direct concat with `df_lock`). Set `Action: GBIF_UPDATE`, and populate `ChangedFields` (e.g., "Genus, Species") and `ChangedValues` (e.g., "OldGenus -> NewGenus").
4.  **Old Taxonomy Revert UI (Desktop):**
    *   In the main Registry UI or a dedicated dialog, parse `df_log` for `GBIF_UPDATE` actions related to the current object.
    *   Display a button or section indicating "Old Taxonomy Available" and provide a 1-click mechanism to restore those old values from the log back into `df_reg`.

### Phase 5: Expanded Filtering Options
**Goal & Intent:** Make the newly added data states actionable by allowing users to easily find objects that have 'Unvalidated' sources, are in the 'REV+ERR' state, or have historical taxonomic changes logged in the database.
1.  **Desktop Filter UI (`ui/filter_dialog.py`):**
    *   Add checkboxes for "Has Unvalidated Source" and "REV+ERR" status.
    *   Add an input field or checkbox for "Search for old taxonomy" (which should search through `df_log` `ChangedValues` for historical taxonomic names).
2.  **Filter Logic (`ui/main_window.py`):**
    *   Update `filter_vars` and `apply_filter` logic to respect the new Unvalidated and REV+ERR states, as well as the historical log search.

### Phase 6: Final Verification
**Goal & Intent:** Guarantee stability and correctness by running the full test suite and adhering to the project's quality standards before finalizing the implementation.
*   Run all relevant tests (e.g., `xvfb-run -a python3 -m pytest tests/`) to ensure no regressions.
*   Ensure that pre-commit checks and formatting guidelines in Arbor are followed.