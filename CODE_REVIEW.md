# Codebase Review: Arbor Museum Object Visualizer

Based on a thorough review of the codebase (particularly `ui/main_window.py`, `ui/advanced_settings.py`, `repository.py`, and `models.py`), I've identified several areas for high-impact improvements, focusing on performance, reliability, architecture, and maintainability in this Tkinter/Pandas application.

## 1. Top 10 Quick Wins (Low Effort, High/Medium Impact)

### 1. Fix `AdvancedSettingsWindow.save_settings` KeyError
* **Why it matters:** Tests are currently failing, and users cannot save advanced settings because `save_settings` crashes. It assumes every item in `ADVANCED_SETTINGS_SCHEMA` has a corresponding Tk variable, but "button" types (like `action_dark_mode`) do not.
* **Impact:** High
* **Effort:** Small
* **Recommended change:** In `ui/advanced_settings.py:558`, add an early return or skip in the loop: `if item["type"] == "button": continue`.

### 2. Optimize `_normalise_dataframes` dynamically added columns
* **Why it matters:** Adding columns in a loop `df_obs[col] = False` directly mutates the dataframe repeatedly, causing a `SettingWithCopyWarning` and severe memory fragmentation ("PerformanceWarning: DataFrame is highly fragmented").
* **Impact:** High
* **Effort:** Small
* **Recommended change:** In `repository.py`, create a dictionary or sub-dataframe of new columns and assign them all at once using `pd.concat` or `df.assign(**new_cols)`.

### 3. Eliminate Recursive Tkinter Event Bindings
* **Why it matters:** `_bind_mousewheel_recursive` walks the entire Tkinter widget tree and calls `.bind`. On large trees (like Treeviews or large canvases), this is extremely slow and memory-intensive, leading to lag when opening windows.
* **Impact:** Medium
* **Effort:** Small
* **Recommended change:** Use Tkinter `bindtags`. Insert a custom tag (e.g., `MouseWheelTag`) into the `bindtags` tuple of all widgets, and use `bind_class("MouseWheelTag", "<MouseWheel>", handler)`.

### 4. Robust Boolean Parsing in Settings
* **Why it matters:** The pattern `if isinstance(old_val, str): old_val = (old_val.lower() == "true")` is brittle and fails on unexpected types or numeric inputs.
* **Impact:** Medium
* **Effort:** Small
* **Recommended change:** Use a standardized config parsing function like `utils.parse_bool(val)` that handles `str`, `int`, and `bool` types consistently.

### 5. Consolidate Tooltip Implementations
* **Why it matters:** There is a well-implemented `ToolTipManager` in `ui/main_window.py`, but also duplicated scattered `add_tooltip` functions and inline label implementations.
* **Impact:** Low
* **Effort:** Small
* **Recommended change:** Refactor all code to exclusively instantiate and use `ToolTipManager` for consistent delays, theming, and memory cleanup.

### 6. [COMPLETED] Remove Misleading `.empty` Checks on Columns
* **Why it matters:** In `repository.py`, `if not df_reg.empty:` is used before populating columns. `.empty` checks if rows == 0. A new database has 0 rows but still needs column initialization! This breaks schemas on fresh databases.
* **Impact:** High
* **Effort:** Small
* **Recommended change:** Remove the `if not df_reg.empty:` guard when adding mandatory columns, or check `if df_reg.columns.empty`.

### 7. Optimize Pandas Vectorized Conditionals
* **Why it matters:** Operations like `df_obs[col].replace({"": "False"})` iterate slowly.
* **Impact:** Medium
* **Effort:** Small
* **Recommended change:** Use vectorized masking: `df_obs.loc[df_obs[col] == "", col] = "False"`. It executes strictly in C and avoids Series instantiation overhead.

### 8. Global Regex Pattern Instantiation
* **Why it matters:** Python regexes should be compiled once at the module level. Some are currently compiled inside loops or function calls.
* **Impact:** Low
* **Effort:** Small
* **Recommended change:** Move all `re.compile()` calls to the top of their respective modules and reuse them. (Several are correctly handled in `ui/main_window.py`, but ensure this is uniform everywhere).

### 9. Safely Handle `tk.TclError` in Callbacks
* **Why it matters:** Tkinter frequently raises `TclError: invalid command name` if an event fires (like `<Motion>`) right after a widget is destroyed. This creates log spam.
* **Impact:** Medium
* **Effort:** Small
* **Recommended change:** Create a `@safe_tk` decorator that suppresses specific harmless `TclError` exceptions to wrap event callbacks.

### 10. Update Deprecated Pandas `.append`
* **Why it matters:** Pandas 2.0+ removes `DataFrame.append()`. The codebase might rely on it implicitly in legacy logging code.
* **Impact:** High
* **Effort:** Small
* **Recommended change:** Run a codebase-wide regex for `\.append\(` on dataframes and replace with `pd.concat([df1, df2])`.

---

## 2. Top 10 High-Impact Improvements (Medium/High Effort, High Impact)

### 1. Decouple Business Logic from `ObjectProgramUI`
* **Why it matters:** `ui/main_window.py` is nearly 9,000 lines long! It handles search indexing, data normalisation, UI, event dispatching, and file I/O. It is a "God Object."
* **Impact:** High
* **Effort:** Large
* **Recommended change:** Extract search into a pure Python `SearchEngine` class. Extract filter logic into a `FilterManager`. The `ObjectProgramUI` should only handle connecting events to these backend engines.

### 2. Move Database Loading to an Async Worker Thread
* **Why it matters:** Calling `ExcelRepository.load_excel` blocks the main Tkinter UI thread (`mainloop`). Even with `calamine`, loading large files freezes the app, making the OS flag it as "Not Responding."
* **Impact:** High
* **Effort:** Medium
* **Recommended change:** Use Python `threading` and a `queue.Queue`. Start the load in a thread, and use `root.after(100, check_queue)` to poll for completion, allowing the Loading Window animation to play smoothly.

### 3. Implement Virtualized Treeview/Canvas for Images
* **Why it matters:** While `TreeviewListboxWrapper` uses virtualization for text cards, `ImageHandlerMixin._render_image_gallery` creates Tkinter widgets for *every* image at once. This destroys performance on datasets with 1,000+ images.
* **Impact:** High
* **Effort:** Medium
* **Recommended change:** Only instantiate and pack Tkinter image cards that intersect with the canvas `yview`. Destroy or cache them when they scroll off-screen.

### 4. Unify Application State Architecture
* **Why it matters:** The state is spread out. `self.app.df_reg`, `self.vars`, and `self.advanced_prefs` are mutated directly by UI code across 15 different files. Debugging state bugs is a nightmare.
* **Impact:** High
* **Effort:** Large
* **Recommended change:** Use `models.AppState` as a strict "Single Source of Truth." UI should dispatch events to update the state, and the state should trigger UI redraws (similar to an MVC or Flux architecture).

### 5. Pre-compute Global Search Index
* **Why it matters:** Filtering across a massive Pandas dataframe for every keystroke in the search bar is laggy.
* **Impact:** Medium
* **Effort:** Medium
* **Recommended change:** On load, create an inverted index (or just a flattened text column `" ".join(row.astype(str))`) in a background thread to make search operations $O(1)$ instead of $O(N \times M)$.

### 6. Refactor Tkinter UI Mixins to Composition
* **Why it matters:** `ObjectProgramUI` inherits from `AutosaveMixin`, `ImageHandlerMixin`, `DatabaseOpsMixin`, etc. This leads to massive namespace pollution (`self` has hundreds of methods).
* **Impact:** Medium
* **Effort:** Large
* **Recommended change:** Favor composition. Pass the main window as a delegate. E.g., `self.image_handler = ImageHandler(self)` instead of inheritance.

### 7. Extract Form Generation into a Schema Builder
* **Why it matters:** `build_sections()` dynamically builds the UI from `config.py` but is hardcoded inside `main_window.py`.
* **Impact:** Medium
* **Effort:** Medium
* **Recommended change:** Create an independent `FormBuilder` module that takes a parent Tkinter frame and a schema section, and returns the packed frame and a dictionary of connected Tk variables.

### 8. Isolate Testing Logic (Headless vs. GUI)
* **Why it matters:** Running UI tests requires `xvfb-run` and Tk mocking, making them slow and fragile.
* **Impact:** High
* **Effort:** Medium
* **Recommended change:** Completely decouple the pandas manipulation from Tkinter. The business logic (`_normalise_dataframes`, historical discrepancies) should be 100% covered by pure, headless unit tests.

### 9. Make `calamine` a Hard Dependency
* **Why it matters:** The `calamine` Excel parser is 5-10x faster than `openpyxl`. It is currently wrapped in a `try-except` fallback, meaning users who don't know about it suffer terrible performance.
* **Impact:** High
* **Effort:** Small
* **Recommended change:** Add `python-calamine` to `requirements.txt` and remove the fallback to guarantee the speed boost for everyone.

### 10. Implement Robust Crash Recovery / Error Boundaries
* **Why it matters:** Unhandled exceptions in Tkinter print to stderr, leaving the UI in an undefined, broken state without the user knowing.
* **Impact:** High
* **Effort:** Medium
* **Recommended change:** Extend `utils.debug_error` and `_install_exception_hooks` to intercept mainloop errors, pause the app, and throw a "Something went wrong" Tkinter dialog offering a safe Autosave before closing.
*after making a fix, update this file.*