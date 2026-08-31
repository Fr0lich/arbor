## YYYY-MM-DD - Fast Pandas Pre-binding and Closure Compilation
**Learning:** In tight, high-volume filtering loops spanning thousands of Pandas rows passed as dictionaries, standard string-based conditionals (e.g. `if condition == "TypeA"`) and internal function abstractions create severe Python evaluation overhead.
**Action:** When filtering across large datasets, use the factory pattern to build lists of closures (`lambdas`) that pre-compile the condition branching *before* entering the loop. Furthermore, always pre-bind dictionary `.get` methods (`obs_get = obs_dict.get`) and extract the Pandas index to a native list (`.tolist()`) to sidestep overhead.
## $(date +%Y-%m-%d) - Pagination API Loop Pandas Lookups
**Learning:** In API handlers returning large lists of items from Pandas DataFrames (like `get_objects` pagination), accessing data row-by-row inside the loop using `df.loc[oid]` creates individual Pandas Series objects. This incurs massive function call overhead and drastically degrades performance when returning hundreds of rows.
**Action:** Always slice the DataFrame *outside* the loop using the list of requested indices and pre-convert it to a Python dictionary using `df.loc[indices_list].to_dict('index')`. Inside the loop, use standard Python `dict.get(oid)` for lightning-fast native lookups.
## $(date +%Y-%m-%d) - In-place Pandas Update vs Combine First
**Learning:** Combining Pandas Series using `.combine_first()` involves copying the data and checking both indexes. When merging updates from multiple DataFrames (e.g. `df_obs` overriding `df_reg`), this introduces unnecessary overhead.
**Action:** Use `.update()` to overwrite values in-place when dealing with Series that already share an index or when projecting a subset.

## $(date +%Y-%m-%d) - Loop Invariants in Batch Updates
**Learning:** In batch API endpoints (e.g., `/api/batch_update`), re-evaluating configuration schemas (like `app_state.config`) for every single item inside the update loop causes severe dictionary traversal overhead.
**Action:** Extract and compute all invariant state (such as allowed column sets) exactly once before entering the batch processing loop.

## 2023-10-25 - Reliable Mobile SSE Resync
**Learning:** Browser native `EventSource` reconnection logic frequently stalls when mobile devices enter sleep mode or lock screens, leaving the client disconnected from the server despite reporting network availability.
**Action:** When implementing SSE in mobile contexts, maintain a global reference to the `EventSource` instance and bind a `visibilitychange` listener. When the page becomes visible, explicitly call `.close()` on the old instance and instantiate a new one to force an immediate data refresh and network reconnect.
## 2024-05-17 - Pandas loc[] vs dict lookup in Tkinter Sorts
**Learning:** Using `df.loc[oid]` inside tight loops like Python's `sorted()` key functions in Tkinter (`ui/main_window.py`) causes significant lag due to Pandas' $O(N)$ row lookup overhead.
**Action:** When sorting or filtering, always pre-convert necessary Pandas DataFrames to native Python dictionaries outside the loop (e.g., via `self._get_reg_dict()` or `df.to_dict('index')`) and use `dict.get(oid, {})` inside the lambda/key function to achieve $O(1)$ lookups.
## $(date +%Y-%m-%d) - Component-Based Extraction of Large UI Classes
**Learning:** Extracting code from massive Tkinter files like `ui/main_window.py` (which has over 9000 lines) is very dangerous and error-prone if done with automated regex or mass deletions. It can cascade indentation errors that break the codebase.
**Action:** When extracting large UI classes, always extract one self-contained component vertically (like a panel). Copy the methods over, test the new component thoroughly by instantiating it inside the original class, and only after tests pass, delete the old code. Run tests sequentially after *every* single extraction.
