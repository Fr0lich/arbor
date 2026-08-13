# Summary of Changes - Narbor

This document records the recent improvements, bug fixes, and user interface changes implemented in the Narbor codebase.

---

## 1. Robust Excel Sheet Loading & Fallback
- **Files Modified**: [`repository.py`](file:///c:/Users/ijbrekke/Documents/non-git/Narbor/repository.py)
- **Change Details**:
  - Prevented a `ValueError` crash when opening Excel files that do not contain an `Observation` worksheet.
  - The repository now defaults to initializing an empty `Observation` DataFrame with a single `ObjectID` column if the sheet is missing.
  - Enhanced `_normalise_dataframes` to dynamically extract missing `ObjectID`s from `df_reg` (Registration sheet) and concat them to `df_obs`, keeping their original order.
  - Automatically populates missing location values as `""`, problems to `False`, and `Images_Missing` flags to `True`.

---

## 2. Logging for Historical Conflict Resolver
- **Files Modified**: [`ui/historical_resolver.py`](file:///c:/Users/ijbrekke/Documents/non-git/Narbor/ui/historical_resolver.py)
- **Change Details**:
  - Integrated full event tracking inside the Historical Database Conflict Resolver window.
  - **Single Conflict Resolution**: Modifying a conflict field triggers a `self.main_app.log_action("RESOLVE_HISTORICAL_CONFLICT", ...)` action logging the updated registration field name, value, and problem flags.
  - **Bulk Conflict Resolution**: Pressing "Apply All" accumulates all changes and logs them in a single batch log entry in the `Log` worksheet.

---

## 3. Startup Crash Prevention & GUI Tracebacks
- **Files Modified**: [`main.py`](file:///c:/Users/ijbrekke/Documents/non-git/Narbor/main.py)
- **Change Details**:
  - Deferred the imports of heavy packages (`pandas`, `PIL`, `openpyxl`, `requests`, and core app dependencies like `models`, `ui`, `config`) inside the `__main__` block's `try...except` wrapper.
  - Refactored global exception hooks and `atexit` handlers to import `utils` dynamically at runtime rather than on module load.
  - Updated the outer try-except startup handler to invoke a Tkinter `messagebox.showerror` dialog containing the exception stack trace. This ensures that dependency loading errors, runtime startup crashes, or directory access issues in packaged PyInstaller builds (`main.exe`) are displayed to the user rather than terminating silently.

---

## 4. Resizable Location Pane (Center Column Layout)
- **Files Modified**: [`ui/main_window.py`](file:///c:/Users/ijbrekke/Documents/non-git/Narbor/ui/main_window.py)
- **Change Details**:
  - Replaced the packing arrangement of the middle column (image viewer and center location) with a vertical `ttk.Panedwindow` named `self.middle_panes`.
  - Added the images pane (`right_frame`) and the horizontal Location panel (`loc_frame_horizontal`) to `self.middle_panes`. This displays a horizontal divider sash that the user can drag up and down to adjust their respective heights.
  - Set minimum sizing bounds (`minsize`) on both widgets (`100px` for images, `80px` for location inputs) to prevent either from being collapsed to 0 height accidentally.
  - Implemented `_sync_middle_panes` to seamlessly manage visibility and ordering of sashes, automatically removing the divider and expanding the images view to fill the screen when Location is configured to sit in the left column.

---

## 5. UI Spacing & Input Modernisation
- **Files Modified**: [`ui/main_window.py`](file:///c:/Users/ijbrekke/Documents/non-git/Narbor/ui/main_window.py)
- **Change Details**:
  - Added vertical padding (`ipady=sc(3)`) to all Location entry boxes and comboboxes in both vertical and horizontal layouts, improving alignment and making them look less crowded.

---

## 6. Dynamic Dark/Light Mode Theme Syncing
- **Files Modified**: [`ui/layout_settings.py`](file:///c:/Users/ijbrekke/Documents/non-git/Narbor/ui/layout_settings.py)
- **Change Details**:
  - Added theme synchronization for Tk-native widgets (standard Tk entries, labels, checkboxes, and frames) inside `apply_theme` using recursive widget traversal.
  - Standard Tk widgets inside `location_frame` and `loc_frame_horizontal` now instantly update their background, foreground, activebackground, and select colors when toggling dark mode.
