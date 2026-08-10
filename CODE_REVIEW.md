# Codebase Review: Arbor Museum Object Visualizer

Based on a thorough review of the codebase (particularly `ui/main_window.py`, `ui/advanced_settings.py`, `repository.py`, and `models.py`), I've identified several areas for high-impact improvements, focusing on performance, reliability, architecture, and maintainability in this Tkinter/Pandas application.

## Detailed Findings

### Fix `AdvancedSettingsWindow.save_settings` KeyError
* **Why it matters:** Tests and runtime execution fail when trying to save advanced settings because `save_settings` assumes every item in `ADVANCED_SETTINGS_SCHEMA` has a corresponding Tk variable, but "button" types (like `action_dark_mode`) do not.
* **Impact:** High (Breaks core functionality and test suite)
* **Effort:** Small
* **Recommended change:** In `ui/advanced_settings.py`, add an early return or skip in the loop: `if item["type"] == "button": continue`.

### Optimize `_normalise_dataframes` dynamically added columns
* **Why it matters:** Iteratively assigning new columns (`df_obs[col] = False`) directly mutates the dataframe repeatedly, causing a `SettingWithCopyWarning` and severe memory fragmentation ("PerformanceWarning: DataFrame is highly fragmented").
* **Impact:** High (Performance and memory bottleneck during data load)
* **Effort:** Small
* **Recommended change:** In `repository.py`, create a dictionary of new columns and assign them all at once using `pd.DataFrame(...)` assigned to a list of columns.

### Eliminate Recursive Tkinter Event Bindings
* **Why it matters:** `_bind_mousewheel_recursive` walks the entire Tkinter widget tree and calls `.bind`. On large trees (like Treeviews or large canvases), this is extremely slow and memory-intensive, leading to lag when opening windows.
* **Impact:** Medium (UI responsiveness)
* **Effort:** Small
* **Recommended change:** Use Tkinter `bindtags`. Insert a custom tag (e.g., `MouseWheelTag`) into the `bindtags` tuple of widgets, and use `bind_class("MouseWheelTag", "<MouseWheel>", handler)`.

### Robust Boolean Parsing in Settings
* **Why it matters:** The pattern `if isinstance(old_val, str): old_val = (old_val.lower() == "true")` is brittle and fails on unexpected types or numeric inputs.
* **Impact:** Medium (Reliability)
* **Effort:** Small
* **Recommended change:** Use a standardized config parsing function like `utils.parse_bool(val)` that handles `str`, `int`, and `bool` types consistently.

### Consolidate Tooltip Implementations
* **Why it matters:** There is a well-implemented `ToolTipManager` in `ui/main_window.py`, but also duplicated scattered `add_tooltip` functions and inline label implementations.
* **Impact:** Low (Maintainability)
* **Effort:** Small
* **Recommended change:** Refactor all code to exclusively instantiate and use `ToolTipManager` for consistent delays, theming, and memory cleanup.

### [COMPLETED] Remove Misleading `.empty` Checks on Columns
* **Why it matters:** In `repository.py`, `if not df_reg.empty:` is used before populating columns. `.empty` checks if rows == 0. A new database has 0 rows but still needs column initialization! This breaks schemas on fresh databases.
* **Impact:** High (Data integrity)
* **Effort:** Small
* **Recommended change:** Remove the `if not df_reg.empty:` guard when adding mandatory columns, or check `if df_reg.columns.empty`.

### Optimize Pandas Vectorized Conditionals
* **Why it matters:** Operations like `df_obs[col].replace({"": "False"})` iterate slowly compared to vectorized assignment.
* **Impact:** Medium (Performance)
* **Effort:** Small
* **Recommended change:** Use vectorized masking: `df_obs.loc[df_obs[col] == "", col] = "False"`. It executes strictly in C and avoids Series instantiation overhead.

### Global Regex Pattern Instantiation
* **Why it matters:** Python regexes should be compiled once at the module level. Some are currently compiled inside loops or function calls.
* **Impact:** Low (Performance)
* **Effort:** Small
* **Recommended change:** Move all `re.compile()` calls to the top of their respective modules and reuse them.

### Safely Handle `tk.TclError` in Callbacks
* **Why it matters:** Tkinter frequently raises `TclError: invalid command name` if an event fires (like `<Motion>`) right after a widget is destroyed. This creates log spam.
* **Impact:** Medium (Reliability / DX)
* **Effort:** Small
* **Recommended change:** Create a `@safe_tk` decorator that suppresses specific harmless `TclError` exceptions to wrap event callbacks.

### Update Deprecated Pandas `.append`
* **Why it matters:** Pandas 2.0+ removes `DataFrame.append()`. The codebase might rely on it implicitly in legacy logging code.
* **Impact:** High (Future-proofing / Reliability)
* **Effort:** Small
* **Recommended change:** Run a codebase-wide regex for `\.append\(` on dataframes and replace with `pd.concat([df1, df2])`.

### Decouple Business Logic from `ObjectProgramUI`
* **Why it matters:** `ui/main_window.py` is nearly 9,000 lines long! It handles search indexing, data normalisation, UI, event dispatching, and file I/O. It is a "God Object."
* **Impact:** High (Architecture / Maintainability)
* **Effort:** Large
* **Recommended change:** Extract search into a pure Python `SearchEngine` class. Extract filter logic into a `FilterManager`. The `ObjectProgramUI` should only handle connecting events to these backend engines.

### Move Database Loading to an Async Worker Thread
* **Why it matters:** Calling `ExcelRepository.load_excel` blocks the main Tkinter UI thread (`mainloop`). Even with `calamine`, loading large files freezes the app, making the OS flag it as "Not Responding."
* **Impact:** High (UX / Performance)
* **Effort:** Medium
* **Recommended change:** Use Python `threading` and a `queue.Queue`. Start the load in a thread, and use `root.after(100, check_queue)` to poll for completion, allowing the Loading Window animation to play smoothly.

### [COMPLETED] Implement Virtualized Treeview/Canvas for Images
* **Why it matters:** Creating Tkinter widgets for *every* image at once destroys performance on datasets with 1,000+ images.
* **Impact:** High (Performance)
* **Effort:** Medium
* **Recommended change:** Only instantiate and pack Tkinter image cards that intersect with the canvas `yview`. Destroy or cache them when they scroll off-screen.

### Unify Application State Architecture
* **Why it matters:** The state is spread out. `self.app.df_reg`, `self.vars`, and `self.advanced_prefs` are mutated directly by UI code across 15 different files. Debugging state bugs is a nightmare.
* **Impact:** High (Architecture / Maintainability)
* **Effort:** Large
* **Recommended change:** Use `models.AppState` as a strict "Single Source of Truth." UI should dispatch events to update the state, and the state should trigger UI redraws (similar to an MVC or Flux architecture).

### [COMPLETED] Pre-compute Global Search Index
* **Why it matters:** Filtering across a massive Pandas dataframe for every keystroke in the search bar is laggy.
* **Impact:** Medium (Performance)
* **Effort:** Medium
* **Recommended change:** On load, create an inverted index (or just a flattened text column `" ".join(row.astype(str))`) in a background thread to make search operations O(1).

### Refactor Tkinter UI Mixins to Composition
* **Why it matters:** `ObjectProgramUI` inherits from `AutosaveMixin`, `ImageHandlerMixin`, `DatabaseOpsMixin`, etc. This leads to massive namespace pollution (`self` has hundreds of methods).
* **Impact:** Medium (Architecture / Maintainability)
* **Effort:** Large
* **Recommended change:** Favor composition. Pass the main window as a delegate. E.g., `self.image_handler = ImageHandler(self)` instead of inheritance.

### Extract Form Generation into a Schema Builder
* **Why it matters:** `build_sections()` dynamically builds the UI from `config.py` but is hardcoded inside `main_window.py`.
* **Impact:** Medium (Architecture / Maintainability)
* **Effort:** Medium
* **Recommended change:** Create an independent `FormBuilder` module that takes a parent Tkinter frame and a schema section, and returns the packed frame and a dictionary of connected Tk variables.

### Isolate Testing Logic (Headless vs. GUI)
* **Why it matters:** Running UI tests requires `xvfb-run` and Tk mocking, making them slow and fragile.
* **Impact:** High (Testing / Developer Experience)
* **Effort:** Medium
* **Recommended change:** Completely decouple the pandas manipulation from Tkinter. The business logic (`_normalise_dataframes`, historical discrepancies) should be 100% covered by pure, headless unit tests.

### Make `calamine` a Hard Dependency
* **Why it matters:** The `calamine` Excel parser is 5-10x faster than `openpyxl`. It is currently wrapped in a `try-except` fallback, meaning users who don't know about it suffer terrible performance.
* **Impact:** High (Performance)
* **Effort:** Small
* **Recommended change:** Add `python-calamine` to `requirements.txt` and remove the fallback to guarantee the speed boost for everyone.

### [COMPLETED] Implement Robust Crash Recovery / Error Boundaries
* **Why it matters:** Unhandled exceptions in Tkinter print to stderr, leaving the UI in an undefined, broken state without the user knowing.
* **Impact:** High (Reliability)
* **Effort:** Medium
* **Recommended change:** Extend `utils.debug_error` and `_install_exception_hooks` to intercept mainloop errors, pause the app, and throw a "Something went wrong" Tkinter dialog offering a safe Autosave before closing.

---

## 1. Top 10 Quick Wins (Low Effort, High/Medium Impact)

1. **Fix `AdvancedSettingsWindow.save_settings` KeyError** (High Impact)
2. **Optimize `_normalise_dataframes` dynamically added columns** (High Impact)
3. **Remove Misleading `.empty` Checks on Columns** (High Impact) [COMPLETED]
4. **Make `calamine` a Hard Dependency** (High Impact)
5. **Update Deprecated Pandas `.append`** (High Impact)
6. **Eliminate Recursive Tkinter Event Bindings** (Medium Impact)
7. **Robust Boolean Parsing in Settings** (Medium Impact)
8. **Optimize Pandas Vectorized Conditionals** (Medium Impact)
9. **Safely Handle `tk.TclError` in Callbacks** (Medium Impact)
10. **Global Regex Pattern Instantiation** (Low Impact)

## 2. Prompt for Quick Wins

```text
Please implement the following low-effort, high-impact fixes in the codebase:
1. In `ui/advanced_settings.py`, modify `AdvancedSettingsWindow.save_settings` to skip processing if `item["type"] == "button"` to prevent KeyErrors.
2. In `repository.py`, update `_normalise_dataframes` to avoid iterative DataFrame column assignments. Instead, construct a dictionary of new columns and assign them all at once using `df_obs[list(new_cols.keys())] = pd.DataFrame(new_cols, index=df_obs.index)` to fix memory fragmentation.
3. In `repository.py`, remove the `if not df_reg.empty:` condition guarding the generation of missing UIDs, as it wrongly skips execution on 0-row DataFrames.
4. Add `calamine` (or `python-calamine`) to `requirements.txt` and remove the `try-except` fallback in `ExcelRepository.load_excel` to force its usage for improved performance.
5. Search the codebase for deprecated `.append()` usage on DataFrames and replace them with `pd.concat()`.
6. Refactor the `_bind_mousewheel_recursive` method (found in `ui/main_window.py` and `ui/dialogs.py`) to use `bind_class` with a custom bindtag instead of walking the entire widget tree to bind events.
```

## 3. Top 10 High-Impact Improvements (Medium/High Effort, High Impact)

1. **Decouple Business Logic from `ObjectProgramUI`** (Large Effort)
2. **Unify Application State Architecture** (Large Effort)
3. **Move Database Loading to an Async Worker Thread** (Medium Effort)
4. **Implement Virtualized Treeview/Canvas for Images** (Medium Effort) [COMPLETED]
5. **Isolate Testing Logic (Headless vs. GUI)** (Medium Effort)
6. **Pre-compute Global Search Index** (Medium Effort) [COMPLETED]
7. **Implement Robust Crash Recovery / Error Boundaries** (Medium Effort) [COMPLETED]
8. **Refactor Tkinter UI Mixins to Composition** (Large Effort)
9. **Extract Form Generation into a Schema Builder** (Medium Effort)
10. **Refactor UI Theme Handling to use ttk Themes/Styles universally** (Medium Effort)

## 4. The Single Most Important Improvement to Make Next

**Decouple Business Logic from `ObjectProgramUI`**

* **Why it matters:** The `ObjectProgramUI` class in `ui/main_window.py` is currently a monolithic "God Object." It mixes UI rendering, event handling, data parsing, global state management, and file I/O into a single tightly coupled component.
* **Impact:** This architectural flaw is the root cause of many other issues in the application (like difficulty in headless testing, poor state management, and laggy UI interactions).
* **Action:** By extracting non-UI concerns into dedicated managers (e.g., `SearchEngine`, `FilterManager`, `StateStore`), the codebase will become significantly easier to maintain, test, and optimize. This refactoring will unblock subsequent improvements like async loading and unified state management.
