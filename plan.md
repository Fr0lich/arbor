1. **Identify Performance Bottleneck**: `sort_column` in `ui/main_window.py` uses `df.loc[oid]` for sorting operations which results in slow row-by-row lookups inside the sort key function (O(N) operations per sorting).
2. **Review CLAUDE_BUG_REVIEW_GUIDE.md**: The guide states: "Avoid `df.loc[oid]` lookups inside loops, especially when serializing or paginating data. Pre-convert slices to native Python dictionaries (e.g., `df.loc[index_list].to_dict('index')`) outside the loop and use `dict.get()` inside."
3. **Refactor `sort_column`**: We can use the existing `_get_reg_dict()` and `_get_obs_dict()` to perform fast dictionary lookups rather than `loc[oid]`.
4. **Target file**: `ui/main_window.py` in the `sort_column` method.
5. **Detailed Changes**:
   - Get the dict representation of `df_reg` and `df_obs` at the beginning of `sort_column`.
   - Update `get_genus`, `get_species`, `status_key` to use `.get(oid, {})` instead of `loc`.
   - Remove `iloc[0]` calls inside loops.
6. **Pre-commit checks**: Run `pytest tests/` and verify formatting/linting using instructions from `pre_commit_instructions`.
