# Implement Offline-First Architecture for Mobile Companion

## Context & Reasoning

The Arbor Mobile Companion (`backend/mobile_server.py` -> `INDEX_TEMPLATE`) currently uses a standard online-first saving mechanism. When a user modifies a field or clicks "Mark Reviewed", the app attempts to send the data directly to the desktop server over the network. If the fetch fails, it falls back to queueing the mutation in IndexedDB (`queued_mutations`).

Because museum environments (vaults, storage rooms) have highly unpredictable Wi-Fi, this network-first approach is fragile. A network request might hang indefinitely before failing, causing UI unresponsiveness, race conditions with user navigation, and potential data loss.

**Your task is to refactor the saving logic into a true "Offline-First" (Local-First) architecture.**

Instead of reacting to connection drops, the app should assume the network is inherently unreliable:
1. **Always Local First:** Every edit must be immediately saved to the local offline queue (IndexedDB) and the UI optimistically updated. This guarantees 1 millisecond response times and zero blocking.
2. **Background Sync (Time-In):** The app already maintains a connection status via SSE and a heartbeat ping. The background sync loop (`flushQueuedMutations`) should act as a drain. Whenever the connection is confirmed active ("time-in"), it should quietly empty the local queue to the desktop server without interrupting the user.

*Note: Do NOT modify the UI layout for navigation. Leave the "Next" and "Previous" buttons at the top of the detail view. The user navigates primarily by finding physical objects, not by iterating sequentially through a list.*

## Specific Files and Functions to Edit

All frontend code for the mobile companion is located inside the `INDEX_TEMPLATE` string block within `backend/mobile_server.py`. You must not create external HTML/JS files.

Focus your edits on these JavaScript functions within the template:

1. **`saveCurrentEdits()`**
   - **Current Behavior:** Attempts `apiFetch('/api/update')` and falls back to `queueMutation()` on failure.
   - **Required Changes:** Remove the direct network request. Make this function instantly build the payload, update the local UI optimistically (e.g., set `currentRecord.review_status` to match the change), and call `queueMutation(payload)`. Finally, trigger a background sync attempt by calling `flushQueuedMutations()` asynchronously.

2. **`flushQueuedMutations()`**
   - **Current Behavior:** Fetches queued items, displays a large blocking banner, sends a `/api/batch_update`, and clears the queue.
   - **Required Changes:** Make this a silent background worker.
     - Check `navigator.onLine` and the custom ping badge status. If disconnected, silently abort.
     - If connected, attempt the `/api/batch_update`.
     - Do not show the large blocking `offlineBanner` spinning loader during background syncs unless the queue is exceptionally large or the user explicitly tapped a "Sync Now" button.
     - Only show the subtle bottom footer toast/ticker to indicate "Syncing..." and "✓ Edit saved".
     - Ensure thread safety/mutex: prevent concurrent executions of `flushQueuedMutations()` from sending duplicate payloads.

3. **`queueMutation(payload)`**
   - **Current Behavior:** Puts the payload into IndexedDB.
   - **Required Changes:** Ensure that multiple rapid saves for the *same object* (e.g., typing a character, then checking a box) do not create bloated duplicate entries in the queue if a sync hasn't happened yet. Consider using the object ID as the primary key in the queue (or merging payloads) rather than appending new timestamps, to prevent race conditions during batch updates.

4. **`triggerAutoSave()`**
   - **Current Behavior:** Sets a timeout for `saveCurrentEdits`.
   - **Required Changes:** The debounce logic (800ms) is still valuable to avoid hammering IndexedDB on every keystroke, but ensure it interacts cleanly with the new instantaneous offline-first `saveCurrentEdits()`.

## Rules to Remember
- Comply with all rules in `documentation/agent/MOBILE_COMPANION_GUIDE.md`.
- Do not introduce external libraries. Use the existing Vanilla JS structure.
- Do not use `setTimeout` or `setInterval` for the core saving logic, rely on the existing UI events (blur, change) and the background sync trigger.
