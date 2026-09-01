# Claude Bug Review Guide

This document is designed to help Claude (or other AI agents) efficiently review the Arbor codebase, identify bugs, and suggest improvements without consuming unnecessary tokens. When requested to review the codebase for issues, use the strategies and focus areas outlined below.

**Note:** You do not need to focus on UI or UX issues (e.g., padding, colors, fonts). Focus strictly on performance, structure, and concurrency.

---

## Agent Safety & Workflow Directives
Before executing any refactoring or bug-fixing tasks, all AI agents must strictly adhere to the following workflow rules:

1. **Prioritize Stability Over Speed:** Always optimize for maintaining and protecting existing application behavior. Do not sacrifice safety or correctness for execution speed.
2. **Plan Before Execution:** Do not write code or implement fixes immediately upon receiving a prompt. First, formulate a plan: explain your understanding of the issue, outline the safest path forward, and explicitly list the exact files you intend to touch.
3. **Capture and Automate Learnings:** Whenever you resolve a complex issue or discover a necessary workflow after trial and error, you MUST document the solution in your memory. Additionally, if the solution involves specific build, test, or execution steps, add those commands to a `Makefile` (or the relevant script) and explicitly instruct yourself to use that script for similar future tasks.

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
    *   **DataFrame Lock TOCTOU:**
        *   Never check `if df_reg is None:` outside a `with app_state.df_lock:` block. Checking outside and acquiring the lock later creates a time-of-check/time-of-use race: the DataFrame can become `None` between the check and the lock acquisition. Always move null-guards to be the **first statement inside** the `with df_lock:` block.
* **Background Tasks & UI Updates (Task Queue & EventBus):**
    *   **BackgroundWorker:** Heavy Python operations (file I/O, large pandas calculations) should be offloaded to the centralized `BackgroundWorker` (in `backend/task_queue.py`) via `app_worker.run_in_background(func, callback)`. Avoid spawning raw daemon threads unless strictly necessary for long-lived processes.
    *   **EventBus Integration:** Background threads and external modules (e.g., `MobileServer`, Background Workers) must **never** call UI update methods (like `self.main_window.update_ui()`) directly, and should avoid cross-thread Tkinter event generation. Instead, use the global `EventBus` (`app_bus.publish('EVENT_NAME')` from `ui/state.py`). The Tkinter UI components will subscribe to these events and schedule their own safe redraws via `self.root.after(0, ...)`.
    *   **EventBus Thread Safety — Publish Must Be on the Main Thread:**
        *   `app_bus.publish()` is NOT thread-safe from a Tkinter perspective. Even though it uses a lock internally, it invokes subscriber callbacks synchronously on whatever thread calls it. If a subscriber touches a Tkinter widget, calling `app_bus.publish()` from a background thread will corrupt UI state.
        *   **Rule:** Background threads (Flask routes, worker threads) must **never** call `app_bus.publish()` directly. Always marshal the publish call to the main thread first:
            ```python
            # Correct — called from a background thread:
            self.root_tk.after(0, lambda: app_bus.publish(EVENT_NAME, **kwargs))
            ```
        *   The subscriber itself does NOT need to wrap with `root.after()` if the publish is already marshaled, but wrapping defensively is always acceptable.
    *   **EventBus Subscriber Cleanup — Always Use `subscribe_managed()`:**
        *   The `EventBus` stores callbacks as strong references. A widget that subscribes but is destroyed without calling `unsubscribe()` will permanently hold a reference and may receive callbacks on a destroyed widget, causing `TclError`.
        *   **Rule:** Always use `app_bus.subscribe_managed(widget, event_type, callback)` instead of `app_bus.subscribe()`. This automatically wires up `<Destroy>` cleanup on the widget. Only use bare `subscribe()` for objects that are never destroyed (e.g., module-level singletons).
*   **Subprocesses & Tunnels:**
    *   When running a long-lived background subprocess (e.g., an SSH tunnel using `subprocess.Popen`) where output is continually monitored via a blocking call like `readline()`, ensure the read operation does not indefinitely prevent checking for shutdown events. Wrap the subprocess loop in a `try...finally` block that explicitly calls `process.kill()` or `process.terminate()` to guarantee clean termination and prevent orphaned processes.
*   **Server-Sent Events (SSE):**
    *   The `MobileServer` uses SSE at `/api/events`. The implementation uses a generator yielding from a `queue.Queue`. Ensure a `finally` block is used (instead of catching `GeneratorExit`) to reliably handle disconnects, and that a `threading.Lock` is used to safely manage the active client list.
