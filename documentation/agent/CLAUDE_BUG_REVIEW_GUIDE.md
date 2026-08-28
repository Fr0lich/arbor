# Claude Bug Review Guide

This document is designed to help Claude (or other AI agents) efficiently review the Arbor codebase, identify bugs, and suggest improvements without consuming unnecessary tokens. When requested to review the codebase for issues, use the strategies and focus areas outlined below.

**Note:** You do not need to focus on UI or UX issues (e.g., padding, colors, fonts). Focus strictly on performance, structure, and concurrency.

---

## 1. Performance Bottlenecks

Arbor relies heavily on Pandas for data manipulation and Tkinter for its desktop UI. Performance issues often stem from inefficient loops or excessive UI recalculations.

**Key areas to review for performance:**

*   **Pandas & DataFrame Operations:**
    *   **Row-by-Row Operations:** Avoid `df.loc[oid]` lookups inside loops, especially when serializing or paginating data. Pre-convert slices to native Python dictionaries (e.g., `df.loc[index_list].to_dict('index')`) outside the loop and use `dict.get()` inside.
    *   **Combining DataFrames:** When filtering or querying combined data from `df_reg` (registry) and `df_obs` (observations), avoid boolean OR (`|=`) operations across both dataframes. Explicitly combine columns using `.update()` to establish a unified Series before applying boolean masks (avoiding `.combine_first()` due to overhead).
    *   **Tight Loops & Closures:** In high-volume filtering loops across Pandas rows passed as dictionaries, use a factory pattern to pre-compile lists of closures (lambdas) for conditional branching before entering the loop. Pre-bind dictionary methods (e.g., `obs_get = obs_dict.get`) and extract Pandas indexes to native lists (`.tolist()`) to bypass Python evaluation overhead.
    *   **Invariant State:** In API batch endpoints or processing loops, extract and compute all invariant state (allowed columns, config parsing) *exactly once* before entering the loop.

*   **Tkinter UI Performance:**
    *   **Layout Recalculations:** Explicitly check a widget's current layout state using `widget.winfo_manager()` before calling `.grid()`, `.pack()`, `.grid_remove()`, or `.pack_forget()` to prevent redundant Tkinter layout recalculations and UI thread stuttering.
    *   **Icon Rendering:** Arbor uses `pytablericons`. To prevent performance overhead and Tkinter garbage collection issues during window resizes, pre-render `ImageTk.PhotoImage` icons using `TablerIcons.load()` and store strong references in a dictionary cache during UI initialization. Do not load images dynamically on the fly within resize loops.

---

## 2. Structural Issues

Look for issues related to how the application state is managed and how components interact.

**Key areas to review for structural integrity:**

*   **State Management vs. UI Updates:**
    *   When updating the desktop application's data from a background process (e.g., the mobile server's `<<MobileEdit>>` event handler in `ui/main_window.py`), **do not** call `self.commit_current_object()`. This will mistakenly overwrite newly synced in-memory DataFrames with stale data currently displayed in Tkinter widgets. Instead, reload the UI and explicitly invalidate memory caches (like `_invalidate_row_cache()`).
*   **Initialization Sequence:**
    *   `StartupDialog` is instantiated strictly *before* `ObjectProgramUI`. Any logic in `StartupDialog` requiring UI updates must safely check if `self.ui` exists (`hasattr(self, 'ui')`) or defer the UI state modifications via `self.app` flags to be processed after `ObjectProgramUI` is created.
*   **Event Leaks:**
    *   To prevent global event leaks during Tkinter scrolling, avoid dynamically binding and unbinding scroll events globally (e.g., `bind_all` and `unbind_all`) inside `<Enter>` and `<Leave>` handlers. Use `bind_class` to attach scroll events to a custom bindtag (e.g., `"TabScroll"`) and apply this tag to the relevant widget hierarchy.

---

## 3. Concurrency & Threading Issues

Arbor runs a Tkinter UI on the main thread alongside a Flask mobile companion server and background synchronization tasks. Threading issues can cause hard crashes, hangs, or silent failures.

**Key areas to review for concurrency bugs:**

*   **Flask Mobile Server:**
    *   **Persistent Singleton:** To safely manage a background Flask server in a Tkinter app and avoid Werkzeug context restart issues, run the Flask app as a persistent singleton thread. Only toggle the external tunnel or regenerate access credentials (like a PIN) on subsequent starts and stops, rather than shutting down the Flask server entirely.
*   **Background Tasks & UI Updates:**
    *   **Daemon Threads:** Background tasks (like periodic internet connectivity checks) must use daemon threads.
    *   **Safe UI Updates:** Tkinter is not thread-safe. Any UI updates originating from background threads must be safely scheduled on the main thread using `root.after()`.
*   **Subprocesses & Tunnels:**
    *   When running a long-lived background subprocess (e.g., an SSH tunnel using `subprocess.Popen`) where output is continually monitored via a blocking call like `readline()`, ensure the read operation does not indefinitely prevent checking for shutdown events. Wrap the subprocess loop in a `try...finally` block that explicitly calls `process.kill()` or `process.terminate()` to guarantee clean termination and prevent orphaned processes.
*   **Server-Sent Events (SSE):**
    *   The `MobileServer` uses SSE at `/api/events`. The implementation uses a generator yielding from a `queue.Queue`. Ensure a `finally` block is used (instead of catching `GeneratorExit`) to reliably handle disconnects, and that a `threading.Lock` is used to safely manage the active client list.
