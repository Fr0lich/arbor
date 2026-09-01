# Arbor Bug Review: Concurrency & Threading

This document outlines the top 3 bottlenecks, top 3 risks for a poor user experience, and top 3 hidden problems related to concurrency and threading within the Arbor application, specifically focusing on background tasks, the mobile server, and their interaction with the Tkinter UI.

## Top 3 Bottlenecks

1.  **Mobile Server SSE Generator Blocking (`backend/mobile_server.py`)**
    *   **Description:** The Server-Sent Events (SSE) generator at `/api/events` uses `msg = client_queue.get(timeout=15)` within a `while True` loop. This is a blocking call within a Flask route.
    *   **Impact:** Because standard Flask threads block on `queue.get()`, a high number of connected mobile clients (or dangling disconnected clients) will rapidly exhaust the WSGI server's worker thread pool, preventing any new connections or API requests from being processed until timeouts occur.

2.  **Global DataFrame Lock Contention (`backend/mobile_server.py`)**
    *   **Description:** In `update_object()`, the entire record update process (including snapshotting, validation, conflict checking, and history cache invalidation) is wrapped in `with self.app_state.df_lock:`.
    *   **Impact:** If multiple mobile edits arrive simultaneously or during a heavy data sync, the global `df_lock` is held for the duration of the Pandas row operations. This blocks the main Tkinter UI from reading the DataFrame for rendering, and blocks other mobile clients from even querying basic `/api/status` read operations.

3.  **Synchronous Event Bus Publishing (`ui/state.py` & `backend/mobile_server.py`)**
    *   **Description:** When the background `MobileServer` finishes an edit, it calls `app_bus.publish(DATABASE_UPDATED, mobile_edit=True)`. The `EventBus.publish` method iterates through all subscribers synchronously while holding its own `threading.RLock()`.
    *   **Impact:** If any subscribed callback performs a heavy operation before delegating to `root.after`, it stalls the background Flask thread from returning the HTTP response to the mobile client, causing UI lag on the mobile device.

## Top 3 Risks for Poor User Experience

1.  **UI Data Synchronization Race Condition (`ui/main_window.py`)**
    *   **Description:** When a mobile edit occurs, the desktop app fires `DATABASE_UPDATED`. The `_on_database_updated_event` handler calls `self.load_object(oid)` if the user is currently viewing the edited object.
    *   **Risk:** If the desktop user is *actively typing* into Tkinter Entry fields for that same object when the mobile edit arrives, `load_object(oid)` will wipe out their uncommitted local Tkinter variable state and replace it with the mobile data. The user will silently lose their current, unsaved desktop keystrokes.

2.  **Orphaned / Zombie SSH Tunnel Processes (`backend/tunnel.py`)**
    *   **Description:** The background thread managing the Pinggy/Serveo SSH tunnel uses `self.process.stdout.readline()`. This is a blocking I/O call. The shutdown flag `self._stop_event.is_set()` is *not* checked while the thread is blocked waiting for output.
    *   **Risk:** If the SSH connection stalls but doesn't close (producing no stdout), the thread hangs indefinitely on `readline()`. Clicking "Stop Server" will set the stop event, but the thread won't exit, and the `subprocess` won't be killed until the OS forcefully reclaims it. The user will be unable to restart the server on the same port, causing a "port already in use" error.

3.  **Application Freeze on Flask Startup / Port Binding (`backend/mobile_server.py`)**
    *   **Description:** Although `_run` is in a background thread, the initial port binding test in `start()` (`with socket.socket... s.bind`) runs synchronously on the main Tkinter thread to find an available port.
    *   **Risk:** If the OS network stack is slow to respond, or if multiple port increments are required due to zombie processes holding ports, the main Tkinter thread will freeze during this `while` loop, causing the desktop app to become unresponsive to clicks ("Not Responding" state) when launching the mobile companion.

## Top 3 Hidden Problems

1.  **Event Bus Memory Leaks (`ui/state.py`)**
    *   **Description:** The `EventBus` stores strong references to callback functions (`self._subscribers[event_type].append(callback)`). Many UI components (like `status_bar.py`, `database_ops.py`, or dynamically created dialogs like `mobile_dialog.py`) subscribe to events but lack explicit `unsubscribe()` calls upon being destroyed (`destroy()`).
    *   **Problem:** If a widget is closed or destroyed, the EventBus retains a strong reference to its callback, preventing Python's garbage collector from freeing the memory of the entire Tkinter widget (and potentially the entire parent Frame), leading to a silent memory leak over prolonged sessions.

2.  **Exception Swallowing in Threaded Tasks (`backend/task_queue.py`)**
    *   **Description:** In `BackgroundWorker.run_in_background()`, if an error occurs in the background thread, it prints to `stdout` (`print(f"Background task error: {e}")`) and passes it to `error_callback`. However, if no `error_callback` is provided (which is common for fire-and-forget tasks), the exception is silently swallowed.
    *   **Problem:** If a critical background sync or save operation fails, the UI will never be notified. The user will assume the operation succeeded, leading to silent data loss or corrupted state without any visible error dialogs.

3.  **Missing `root.after` in Subscribed Event Handlers**
    *   **Description:** `app_bus.publish` is often called from background threads (like `MobileServer`). While `ui/main_window.py` correctly wraps its `DATABASE_UPDATED` handler in `root.after(0, ...)`, other parts of the codebase might not.
    *   **Problem:** If a secondary UI component subscribes to `DATABASE_UPDATED` (e.g., `autosave_handler.py` triggering a list refresh, or `bulk_edit.py`) and does *not* wrap its Tkinter manipulations in `root.after`, it will execute UI updates directly from the Flask background thread. Tkinter is strictly not thread-safe, and doing this can cause silent, intermittent segmentation faults or `TclError`s that crash the entire application without a traceback.

## Alternative Review Areas Considered
As requested, here are other specific areas of the codebase I could have chosen to review, but didn't, in order to focus deeply on concurrency and threading:
1. **Tkinter UI Rendering & Responsiveness:** Focusing strictly on how the desktop application draws its widgets, manages layouts, and handles large amounts of data visually.
2. **Pandas Data Processing & State Management:** Focusing on how data is loaded from Excel, manipulated in memory, synchronized, and saved back to disk.
3. **Mobile Companion Frontend:** Focusing strictly on the web app's JavaScript, offline capabilities, service workers, and IndexedDB caching.
