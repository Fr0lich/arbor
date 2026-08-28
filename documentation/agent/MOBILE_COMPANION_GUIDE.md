# Mobile Companion Guide for AI Agents

This document serves as a strict instruction manual for any AI agent tasked with modifying or adding features to the Arbor project's Mobile Companion component. Read these rules carefully before making any code changes to the mobile architecture.

## 1. The Single Source of Truth
The frontend HTML/JS/CSS for the mobile companion lives entirely inside the `INDEX_TEMPLATE` string within `backend/mobile_server.py`.
- **CRITICAL RULE:** Agents must **never** create or modify an external `mobile_frontend.html` file or similar. Adding external HTML files causes fallback conflicts and overwrites the internal template.

## 2. Replicating Desktop Behavior
The Mobile Companion must function as a true companion to the desktop experience. When tasked to "check how the desktop program does it, and make the mobile companion do that":
- You must trace the original logic used in the main Tkinter application (`ui/` files) or its backend logic (`models.py`, `backend/search.py`, `backend/filter.py`, etc.).
- Replicate that exact behavior (rules, logic, filtering hierarchy, etc.) in the `backend/mobile_server.py` API endpoints and the Vanilla JS frontend.

## 3. No External Build Systems
The user prefers keeping the Python server self-contained without external build dependencies.
- The frontend must remain strictly Vanilla HTML, JavaScript, and Tailwind CSS (via CDN script).
- **DO NOT** introduce React, Vue, Node.js, npm, or any external build steps.

## 4. Disabling Features
When disabling unused or deprecated frontend features in the mobile application (e.g., the barcode scanner):
- Prioritize runtime efficiency by entirely removing the unused HTML/JS from the main `INDEX_TEMPLATE` string.
- Do not simply hide the code via CSS or inject it dynamically.
- Archive the removed code as string constants in a separate Python file (e.g., `backend/mobile_scanner.py`).

## 5. Smart and Efficient Rules

When building or modifying backend endpoints and mobile frontends, adhere to these performance and reliability guidelines:

### A. Auto-Saving Strategy
- Auto-save implementations in the mobile UI should use a **hybrid approach**: debounce input changes (e.g., 800ms) for continuous typing, and trigger an immediate force-save on field blur (focus lost) to prevent data loss.

### B. Robust SSE Connections
- When using Server-Sent Events (SSE) via `EventSource` in the mobile web app, do not rely solely on the browser's native auto-reconnect mechanism (which often stalls when mobile screens sleep).
- Explicitly bind a `visibilitychange` event listener to close the stale connection and instantiate a new one when `document.visibilityState === 'visible'`.

### C. Backend API Optimization
- In API batch endpoints or processing loops handling large payloads, extract and compute all invariant state (such as allowed column sets and configuration parsing) exactly **once** before entering the loop to prevent severe evaluation overhead.
- When serializing or paginating a subset of Pandas DataFrame records, **avoid** using row-by-row lookups like `df.loc[oid]` inside a loop. Instead, pre-convert the sliced DataFrame to a native Python dictionary using `df.loc[index_list].to_dict('index')` outside the loop, and use `dict.get()` inside for faster lookups.
- When updating records via `/api/update`, dynamically append any unrecognized fields to the `df_reg` or `df_obs` DataFrames by initializing them as `pd.Series(dtype="object")` to prevent data loss from new metadata fields sent from the frontend.

### D. Syncing with Tkinter
- When updating the desktop application's data from a background process (like the mobile server's sync event), avoid calling `self.commit_current_object()` in the Tkinter UI. Doing so mistakenly overwrites newly synced in-memory DataFrames with stale data currently in the widgets. Instead, reload the UI and explicitly invalidate memory caches.
