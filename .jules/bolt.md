# Bolt's Performance Journal - Critical Learnings

## 2025-02-12 - [Pandas Loop Overhead in List Insertion & Index Building]
**Learning:** In Tkinter list population loops, calling pandas `.loc[]` index or series access queries on every iteration introduces massive CPU overhead due to pandas object creation. Pre-converting DataFrame columns to standard Python dictionaries using `.to_dict()` and querying with `.get()` bypasses pandas entirely and runs ~41x faster. Similarly, iterating over rows with `.itertuples()` instead of `.iterrows()` runs ~15x faster because it avoids creating a full pandas Series for every single row.
**Action:** Always pre-calculate lookup dictionaries before starting collection loops, and use `.itertuples()` instead of `.iterrows()` for any required row iteration.
