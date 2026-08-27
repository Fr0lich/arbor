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
