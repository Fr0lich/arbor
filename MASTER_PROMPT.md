# Master Refactoring Prompt for Arbor Desktop Application

Please execute the following step-by-step refactoring plan for the Arbor desktop application. The goal is to decouple data from the UI, improve responsiveness, and standardize UI components. Please tackle each step in the provided order, as subsequent steps build upon previous ones.

**For each step, you must carefully consider the risks involved, particularly regarding Tkinter thread safety, widget lifecycle (e.g., `winfo_exists()`), and data synchronization (e.g., autosave integrity). Validate all changes to ensure regressions are not introduced.**

---

### Step 1: Implement a Unified ObjectDataStore
**Goal:** Refactor data retrieval in `ui/main_window.py` to use a unified `ObjectDataStore` interface. Create a clean `ObjectDataStore` class (in `state.py` or `repository.py`) with a single method like `store.get_object_payload(oid)`. Replace scattered logic in `_extract_object_payload` and `load_object` with a call to this interface.
**Reason:** Currently, `_extract_object_payload` and `load_object` perform complex, repetitive checks to find object data (checking multiple caches, falling back to dataframes, coercing types). Centralizing this vastly simplifies the monolithic `ObjectProgramUI` class and ensures UI components receive guaranteed, safe dictionary payloads.
**Risk Consideration:** Consider the risk of data desynchronization if the store does not properly invalidate caches when the underlying Pandas dataframes (`df_reg`, `df_obs`) are updated. Ensure that saving/editing data reliably reflects back through this new interface.

### Step 2: Implement a Centralized State Manager (Pub/Sub Event Bus)
**Goal:** Implement a lightweight Event Bus / State Manager layer to handle data state and event dispatching. When a new object is loaded, the `ObjectDataStore` should dispatch a single atomic update event (e.g., "DATA_CHANGED" or "OBJECT_LOADED"). UI panels should subscribe to this store and redraw autonomously, rather than relying on `main_window.py` to manually trace and loop over `tk.StringVar` instances. Use `LocationPanel` as the initial proof-of-concept. Furthermore, instead of direct method calls like `main_window._toggle_reviewed_for_id`, widgets should emit an event like "OBJECT_REVIEW_TOGGLED".
**Reason:** Data synchronization currently relies on a tangled web of `tk.StringVar().trace_add` and live callback dictionaries deep down the UI tree. This tight coupling causes circular trace triggers, "bad window path name" TclErrors, and makes adding new UI panels difficult. A Pub/Sub architecture significantly reduces coupling and makes concurrent processing/autosaving much safer.
**Risk Consideration:** Consider the risk of memory leaks if UI components are destroyed but do not unsubscribe from the Event Bus. Ensure there is a robust mechanism to handle component lifecycle and cleanup, and that background thread events are safely pushed back to the main Tkinter thread.

### Step 3: Implement a TaskQueue for the Tkinter Mainloop
**Goal:** Create a standard TaskQueue for the Tkinter mainloop. Move heavy dataframe operations (like sorting large Pandas dataframes, generating Virtual Cards, or bulk applying GBIF suggestions) into a background thread. The thread places results in a thread-safe `queue.Queue()`, and a lightweight `root.after()` loop polls the queue to update the UI incrementally.
**Reason:** Many data-heavy UI operations currently happen directly on the main Tkinter thread, causing the UI to freeze or stutter (relying on `update_idletasks()` to mask blocking). A background TaskQueue ensures a buttery-smooth, responsive UX (preventing ANR lockups) and allows accurate, real-time loading spinners.
**Risk Consideration:** Tkinter is not thread-safe. Consider the risk of a background thread accidentally mutating Tkinter variables or widgets directly. Strictly enforce that background threads only operate on detached data and exclusively use the queue to communicate with the main thread.

### Step 4: Extract Reusable UI Components
**Goal:** Extract all generic form inputs (e.g., logic currently inside `_create_field_widget` in `LocationPanel` and `main_window.py`) into standalone, reusable classes in `ui/widgets.py` (e.g., `ArborTextField`, `ArborDropdown`).
**Reason:** Every panel currently manually defines how its text boxes behave (green focus lines, `tk.StringVar` syncing, keyboard navigation). If one panel forgets an event like `<<FocusOut>>`, autosave breaks. Centralizing these standardizes the UX and eliminates bug-prone boilerplate.
**Risk Consideration:** Consider the risk of breaking existing specific behaviors or focus traversals in complex forms. Ensure the new reusable widgets seamlessly integrate with the new Event Bus (Step 2) to dispatch changes safely.

### Step 5: Implement a LayoutStateManager
**Goal:** Abstract the logic for hiding/showing fields and panels (e.g., Focus Mode, location panel placement, problem checkboxes) into a dedicated `LayoutStateManager` class. Refactor `update_reg_fields_visibility` to delegate to this new manager.
**Reason:** Layout logic (calling `.pack()`, `.grid()`, `.pack_forget()`) is currently tangled inside data loading methods. A state manager dedicated purely to geometry simplifies the rendering phase of `load_object` to focus solely on data injection.
**Risk Consideration:** Consider the risk of `TclError: bad window path name` if the manager attempts to manipulate widgets that have been destroyed. The manager must safely check `winfo_exists()` before any geometry manipulation.

### Step 6: Implement a Dynamic SchemaFormBuilder
**Goal:** Create a `SchemaFormBuilder` that reads definitions from `config.py` to automatically instantiate the correct reusable components (from Step 4) and generate grid layouts dynamically.
**Reason:** The UI currently relies on imperative, hardcoded grid layout code (e.g., `_build_horizontal_1row_ui` explicitly defining columns for "Building", "Floor", "Cabinet"). A dynamic builder means adding a new field (like "Shelf Number") only requires editing `config.py`, preventing UI misalignment bugs and massive Tkinter code edits.
**Risk Consideration:** Consider the risk of losing fine-grained layout control (e.g., specific padding or column weights for certain special fields). Ensure the schema builder supports custom overrides or flexible grid weights so the generated UI remains aesthetically pleasing.