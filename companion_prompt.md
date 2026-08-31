You are an expert AI software engineer tasked with Phase 4 of the architectural refactoring of the Arbor desktop application. Previous agents have successfully established the Data Layer, EventBus, Task Queue, and standardized UI components. Your overarching mission now is to systematically decouple and dramatically reduce the size of the massive `ui/main_window.py` (currently ~10,000 lines) safely and efficiently.

Make an implementation plan before editing code.

**What has already been built:**

*   **Data Layer & EventBus (`ui/state.py`):** A centralized `ObjectDataStore` handles data, and a global EventBus (`app_bus`) handles pub/sub events, enabling decoupled communication.
*   **Reusable UI Components (`ui/widgets.py`):** Standardized components like `ArborTextField`, `ArborDropdown`, and `SchemaFormBuilder` are available to eliminate manual geometry coding.
*   **Layout Management (`ui/layout_manager.py`):** `LayoutStateManager` handles complex visibility states (pack/grid/forget).
*   **Background Worker (`backend/task_queue.py`):** `app_worker` manages heavy operations off the main thread.

**Your Execution Goals & Strategies:**

**1. Transform `ObjectProgramUI` into a Controller/Mediator:**
*   **Goal:** `ObjectProgramUI` should no longer manage the intricate details of every widget's creation and placement. It should only be responsible for wiring together high-level UI panels, managing application-wide state (like keyboard shortcuts), and listening to top-level `app_bus` events.
*   **Strategy:** Identify distinct, self-contained visual sections within `main_window.py` (e.g., the Registry Form area, the Image Gallery area, the Presets/Settings area).

**2. Extract UI Panels Vertically (One by One):**
*   **Goal:** Move logic out of `main_window.py` by extracting one logical panel at a time into new, dedicated files (e.g., `ui/registry_panel.py`, `ui/image_gallery_panel.py`).
*   **Strategy:** Create a new class for the panel. This class should:
    *   Accept a parent `tk.Frame`, the `app_bus`, and the `AppState` in its `__init__`.
    *   Contain all `_build_*` and `_create_*` methods relevant to that specific panel (copied over from `main_window.py`).
    *   Handle its own local UI interactions and publish events to `app_bus` when data changes, rather than manipulating `main_window.py`'s state directly.
    *   Subscribe to relevant `app_bus` events to update its own display when the global state changes.

**3. Decouple Event Handlers and Action Logic:**
*   **Goal:** Remove massive inline event handlers from `main_window.py`.
*   **Strategy:** If a block of logic handles a specific domain (e.g., Image Manipulation, Autosave, or Exporting), consider extracting it into a separate handler class or utility function if it doesn't strictly belong in a UI panel class.

**Crucial Rules & Pitfalls for this Codebase:**

*   **Vertical Slices, Not Horizontal Sweeps:** Do **NOT** attempt to extract all UI logic at once. You must extract **one panel completely**, integrate it back into `main_window.py`, and run the test suite before moving on to the next panel.
*   **The `main_window.py` File is Extremely Fragile:** Do not make sweeping regex replacements or mass deletions, especially inside the massive `__init__` or `init_ui` methods. Indentation errors will cascade and break the entire application. Use highly targeted, manual copy-pasting to extract methods, verify the new component works, and *only then* delete the old code from `main_window.py` and replace it with the new class instantiation.
*   **Avoid `trace_add` Circular Dependencies:** As you extract panels, rely on explicit `app_bus.publish()` calls for state changes rather than maintaining complex `tk.Variable` `trace_add` chains across file boundaries, as this frequently leads to unpredictable infinite update loops.
*   **Widget Lifecycle (`winfo_exists()`):** When components subscribe to `app_bus` events to redraw themselves, ensure they check `if self.winfo_exists():` before updating their widgets, as asynchronous events might fire after a component has been destroyed or hidden.
*   **Importing `sc` (Scaling):** When creating new files like `ui/registry_panel.py`, **avoid** importing `from config import sc` at the top of the file, as it creates circular dependency crashes during Pytest initialization. Instead, import `sc` locally inside your UI class methods or at the very bottom of the file.
*   **Headless Pytest Checkpoints:** You **must** run tests in a headless virtual display after *every single panel extraction* to catch Tkinter "no display name" errors or import loops immediately. Use the command: `xvfb-run -a python3 -m pytest tests/`. Do not proceed to extract a second panel if the first one fails tests. Make sure all tests pass before committing.
