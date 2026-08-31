# Arbor Refactoring Master Prompt

You are an expert AI software engineer tasked with refactoring the Arbor desktop application to improve its architecture, performance, and maintainability. You will implement a series of architectural improvements by merging multiple suggestions into a cohesive refactoring plan.

Below is a step-by-step guide detailing the required implementation order, goals, reasoning, and risks to consider for each phase.

Please review each suggestion. For some steps, a specific approach is suggested based on an initial analysis of the codebase, but you must independently evaluate if it is the optimal approach and decide the best path forward.

---

## Phase 1: Data Layer Refactoring

### Step 1: Implement `ObjectDataStore` for Data Retrieval
**Goal:** Create a clean, unified `ObjectDataStore` interface that encapsulates the logic for retrieving object data.
**Reasoning:** Currently, `ui/main_window.py` contains complex and repetitive data retrieval logic in methods like `_extract_object_payload` and `load_object` (e.g., checking caches, falling back to dataframes, and type coercion). Centralizing this vastly simplifies the UI class by providing a single call (e.g., `store.get_object_payload(oid)`) that returns a guaranteed dictionary payload safe for UI consumption.
**Agent Suggestion to Consider:** Consider whether this logic should live in a newly created `store.py` or `data_store.py`, or if it should be integrated directly into the existing `repository.py`. Evaluate the codebase and decide what makes the most architectural sense.
**Focus Files:** `ui/main_window.py` (`_extract_object_payload`, `load_object`), `repository.py`, or a new `data_store.py`.
**Risks/Pitfalls:** Ensure that cache invalidation and data fallbacks are correctly maintained so that missing or newly added items are fetched accurately without causing `KeyError` or staleness issues.

### Step 2: Centralized Reactive State Layer (Pub/Sub Event Bus)
**Goal:** Implement a centralized reactive state layer (a Pub/Sub or Observer pattern) to decouple UI rendering, event handling, and data state.
**Reasoning:** `ObjectProgramUI` is currently a monolithic class that relies heavily on hardcoded `tk.StringVar().trace_add` bindings and manual cache invalidations. This tight coupling causes "bad window path name" `TclError`s and circular trace triggers. By using an event bus (e.g., `ObjectStore` emitting `DATA_CHANGED`), widgets can subscribe to changes and redraw autonomously.
**Agent Suggestion to Consider:** An initial analysis suggests implementing a simple lightweight Event Bus (Pub/Sub) with an `ObjectStore` in a new `state.py` file, testing it first on `LocationPanel`. Consider if this simple Pub/Sub pattern is sufficient or if a more structured state manager (like Redux) is necessary. Independently verify the best approach.
**Focus Files:** Create a new `state.py` file, `ui/main_window.py`, `ui/location_panel.py` (as a proof-of-concept).
**Risks/Pitfalls:** Beware of memory leaks if UI widgets subscribe but are destroyed without unsubscribing. Handle `TclError` crashes by ensuring the UI components check `winfo_exists()` before updating, especially if background threads trigger state changes. Watch out for circular updates where a widget updating the state triggers an event that updates the widget again.

---

## Phase 2: UI Component & Layout Refactoring

### Step 3: Extract Generic Form Inputs into Reusable Components
**Goal:** Extract repetitive UI form element logic into standalone reusable classes (e.g., `ArborTextField`, `ArborDropdown`).
**Reasoning:** Currently, every panel manually defines text box behaviors, green focus lines, `tk.StringVar` syncing, and keyboard navigation. Consolidating this into `ui/widgets.py` standardizes the UI, removes boilerplate, and ensures consistent behavior across the application.
**Focus Files:** `ui/widgets.py`, `ui/location_panel.py` (e.g., `_create_field_widget`), `ui/main_window.py`.
**Risks/Pitfalls:** Ensure extracted widgets properly handle Tkinter variable scopes and memory management. Make sure not to break existing bindings and focus traversal when migrating to the abstracted classes.

### Step 4: Implement `SchemaFormBuilder` for Dynamic Layouts
**Goal:** Replace imperative, hardcoded grid layout code with a dynamic `SchemaFormBuilder` that generates layouts based on configurations.
**Reasoning:** Hardcoding UI columns in methods like `_build_horizontal_1row_ui` makes adding new fields tedious and bug-prone. A builder that reads from `config.py` allows dynamic instantiation of correct components and layouts, preventing UI misalignment bugs.
**Agent Suggestion to Consider:** Consider applying the `SchemaFormBuilder` specifically to dynamic sections defined in `config.py` (like registry fields) rather than attempting to replace all static UI layouts. Evaluate the codebase to see where dynamic generation provides the most value versus where it overcomplicates things.
**Focus Files:** `ui/main_window.py`, `ui/location_panel.py` (e.g., `_build_horizontal_1row_ui`, `_build_horizontal_2row_ui`), `config.py`.
**Risks/Pitfalls:** Dynamic layouts can sometimes lead to unexpected widget resizing or clipping if weights/configurations aren't perfectly defined. Ensure scrolling and resizing behavior remains consistent.

### Step 5: Implement `LayoutStateManager`
**Goal:** Abstract UI visibility logic (hiding/showing fields and panels) into a dedicated `LayoutStateManager` class.
**Reasoning:** Logic for handling Focus Mode, location panel placement, and problem checkboxes is tangled within data loading methods like `update_reg_fields_visibility`. A dedicated manager that purely handles `.pack()`, `.grid()`, `.pack_forget()`, and `.grid_remove()` will make rendering much cleaner.
**Focus Files:** `ui/main_window.py` (e.g., `update_reg_fields_visibility`).
**Risks/Pitfalls:** The primary risk is `TclError`s from manipulating widgets that no longer exist or have been destroyed. The manager must safely check widget existence (e.g., `winfo_exists()`) before attempting to change geometry.

---

## Phase 3: Threading & Performance

### Step 6: Task Queue for Heavy Tkinter Operations
**Goal:** Implement a standard `TaskQueue` for the Tkinter mainloop to run heavy dataframe operations in a background thread.
**Reasoning:** Data-heavy operations (e.g., sorting large dataframes, bulk applying suggestions) currently block the main Tkinter thread, causing the UI to freeze (ANR). Moving these to a background thread that communicates via a Thread-Safe Queue (`queue.Queue()`) and is polled by a lightweight `root.after()` loop ensures the UI remains smooth (60fps) and allows for real-time loading spinners.
**Focus Files:** `ui/main_window.py` (main Tkinter loop), integration of standard `queue.Queue()`.
**Risks/Pitfalls:** Thread safety is paramount. Background threads must never directly manipulate Tkinter UI elements or `tk.StringVar` instances. Always pass data back to the main thread via the queue for UI updates. Also, consider race conditions where the user triggers a new action while a background task is still computing.
