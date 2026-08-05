# Bolt's Performance Journal - Critical Learnings

## 2025-02-12 - [Pandas Loop Overhead in List Insertion & Index Building]
**Learning:** In Tkinter list population loops, calling pandas `.loc[]` index or series access queries on every iteration introduces massive CPU overhead due to pandas object creation. Pre-converting DataFrame columns to standard Python dictionaries using `.to_dict()` and querying with `.get()` bypasses pandas entirely and runs ~41x faster. Similarly, iterating over rows with `.itertuples()` instead of `.iterrows()` runs ~15x faster because it avoids creating a full pandas Series for every single row.
**Action:** Always pre-calculate lookup dictionaries before starting collection loops, and use `.itertuples()` instead of `.iterrows()` for any required row iteration.

## 2025-02-13 - [Useless Pandas Groupby Computation on DB Load]
**Learning:** Loading and indexing database files in `_get_reg_by_id` executed `df.groupby("ObjectID").first()` to build a dictionary named `value_cache` which was completely unused in the entire codebase. Pandas `.groupby()` and `.first()` are computationally expensive operations for large dataframes, causing significant load-time lag.
**Action:** Always verify that cached or indexed pandas data-structures are actually consumed before committing CPU and memory overhead to construct them.
