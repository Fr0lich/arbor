# Gemini Bug Review Guide

This document is designed to help Gemini (or other AI agents) efficiently review the core desktop and backend (non-mobile) architecture of the Arbor codebase. Your primary goal is to ensure the program functions correctly and reliably, followed by identifying areas for performance improvements.

When reviewing the codebase, prioritize these top 3 areas in order:

## 1. Data Integrity & State Management (Ensure it Works as Expected)

The most critical aspect of the desktop application is ensuring that botanical data is handled, saved, and synced correctly without data loss or corruption.

**Key areas to review:**
*   **Repository & File Operations (`repository.py`, `models.py`):**
    *   Ensure the application uses the `.autosave.json` format (configured via `AUTOSAVE_SUFFIX`) as the primary autosave format, completely replacing the legacy `.autosave.xlsx` format.
    *   Verify that object photos are physically stored in a `photos` subdirectory alongside the active Excel database file (`app_state.excel_path`), and metadata is correctly tracked in the `app_state.df_photo` DataFrame indexed by `ObjectID`.
*   **DataFrame Handling (`df_reg` and `df_obs`):**
    *   When filtering or querying combined data from the registry and observations, look for incorrect boolean OR (`|=`) operations. Explicitly combine the columns using `.update()` to establish a single unified Series prioritizing `df_obs` before applying boolean masks, avoiding `.combine_first()` due to overhead.
*   **UI State Syncing:**
    *   When updating the desktop application's data from a background process (like `<<MobileEdit>>`), ensure the UI is reloaded and memory caches (like `_invalidate_row_cache()`) are explicitly invalidated instead of calling `self.commit_current_object()`, which would overwrite new data with stale UI data.

## 2. Concurrency, Thread Safety, & Reliability (Ensure it Doesn't Crash)

Arbor runs a Tkinter UI on the main thread alongside background tasks (like internet checks and mobile server threads). Threading issues can cause hard crashes, hangs, or silent failures.

**Key areas to review:**
*   **Safe UI Updates:**
    *   Tkinter is not thread-safe. Verify that any UI updates originating from background threads (like daemon threads handling network checks) are safely scheduled on the main thread using `root.after()`.
*   **Subprocess Management:**
    *   When running a long-lived background subprocess (e.g., an SSH tunnel using `subprocess.Popen`) where output is continually monitored via a blocking call like `readline()`, ensure the read operation does not indefinitely prevent checking for shutdown events. Look for `try...finally` blocks that explicitly call `process.kill()` or `process.terminate()` to guarantee clean termination.
*   **Data Protection During Sync:**
    *   Verify that the desktop UI is made entirely modal and read-only (using `grab_set()` on dialogs like `MobileDialog`) while the mobile companion is active. This ensures no concurrent desktop typing conflicts with incoming mobile data edits.

## 3. Core UI & Pandas Performance (Improve Things)

Once data integrity and stability are confirmed, look for structural and performance bottlenecks, specifically avoiding UI/UX design choices (like colors or padding) and focusing on computational efficiency.

**Key areas to review:**
*   **Pandas Tight Loops & Lookups:**
    *   **Avoid Row-by-Row Lookups:** When serializing or paginating a subset of Pandas DataFrame records, flag any use of row-by-row lookups like `df.loc[oid]` inside a loop. Instead, pre-convert the sliced DataFrame to a native Python dictionary using `df.loc[index_list].to_dict('index')` outside the loop, and use `dict.get()` inside.
    *   **Pre-compiling Closures:** To optimize high-volume filtering loops across Pandas rows passed as dictionaries, use a factory pattern to pre-compile lists of closures for conditional branching before entering the loop.
*   **Tkinter Layout Efficiency:**
    *   **Prevent Redundant Layouts:** Explicitly check a widget's current layout state using `widget.winfo_manager()` before calling `.grid()`, `.pack()`, `.grid_remove()`, or `.pack_forget()` to prevent redundant Tkinter layout recalculations and UI thread stuttering.
    *   **Icon Caching:** Arbor uses `pytablericons`. Ensure `ImageTk.PhotoImage` icons are pre-rendered using `TablerIcons.load()` and strongly referenced/cached during UI initialization to prevent Tkinter garbage collection issues and performance overhead during window resizes.
    *   **Event Binding:** To prevent global event leaks during scrolling, avoid dynamically binding and unbinding scroll events globally inside `<Enter>` and `<Leave>` handlers. Use `bind_class` to attach scroll events to a custom bindtag (e.g., `"TabScroll"`).
