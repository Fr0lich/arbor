You are an expert software engineer reviewing the Arbor codebase with a deep, specialized focus on the **Audit Log Architecture (`df_log`, `_log_records`, the Excel/SQLite `Log` sheet, and historical change tracking)** for structural stability, data integrity, and performance.

### Directives & Master Guides
- **Primary rule:** Prioritize stability, audit accuracy, and data integrity over speed. Maintain and protect all existing application behavior. Make sure everything with logging data works flawlessly.
- Strictly adhere to the agent directives in `AGENTS.md` and `documentation/agent/CLAUDE_BUG_REVIEW_GUIDE.md` (or `GEMINI_BUG_REVIEW_GUIDE.md`).
- **TWO-STAGE PROCESS:**
  - **Stage 1 (Your First Turn): DO NOT EDIT CODE.** Perform a comprehensive code review, identify bugs/bottlenecks, and propose concrete, actionable fixes. Wait for my approval.
  - **Stage 2 (Subsequent Turns):** Once I approve the plan, you will implement the code fixes and write new automated tests.
- Before formulating any findings, run the test suite to establish a baseline (`python -m pytest` / `xvfb-run -a python3 -m pytest tests/`).
- **Dynamic Discovery:** Do not rely solely on the files mentioned below. Use exploration tools (e.g., `grep`, `rg`) to dynamically find all references to `df_log`, `_log_records`, `Log` sheet, and related logging functions across the entire codebase to ensure a holistic review.

---

### Audit Log Review & Optimization Priorities
Focus comprehensively on the entire lifecycle of the Log system across desktop and mobile components. Prioritize your review in this exact order:

1. **Log Data Integrity & Lifecycle (Highest Priority):**
   - **Persistence & Loading (`repository.py`, `ui/database_ops.py`):** Verify that opening existing Excel/SQLite databases faithfully reads all historical rows from the `Log` sheet into `df_log` and `app._log_records` without truncation, deduplication loss, column mismatch, or accidental resets on startup.
   - **Change Delta Tracking (`ui/main_window.py` - `log_action`, `commit_current_object` & `backend/mobile_server.py` - `_execute_record_update`):** Audit how field modifications (`ChangedFields`, `ChangedValues`, `Reviewed`, `LocationChanged`, `ProblemsChanged`) are detected, formatted, and merged. Ensure that:
     - Only actual value mutations are logged (preventing unchanged values like `Reviewed: "False" -> "False"`).
     - Field-merging in continuous editing sessions preserves accurate comma-separated field lists without corrupting headers or prefixing object IDs.
   - **Rollback & Bulk Updates (`ui/gbif_review.py`):** Audit GBIF mass updates, rollbacks, and revert operations to ensure all reversed field values and timestamps are accurately recorded in `df_log`.

2. **Concurrency, Thread Safety, & Log Synchronization (High Priority):**
   - **Cross-Thread & Autosave Safety (`ui/autosave_handler.py`, `ui/database_ops.py`):** Ensure `df_log` and `_log_records` modifications are thread-safe and protected by `df_lock` during asynchronous pickle, Excel, and SQLite writes.
   - **Desktop-Mobile Log Parity (`backend/mobile_server.py`, `ui/main_window.py`):** Review mobile edit logging (`MOBILE_EDIT`, `REVIEWED`, `PHOTO_ADDED`, `UNVALIDATED_UPDATE`), ensuring mobile mutations append cleanly to `_log_records` and that desktop event handlers (`_do_database_update`) do not create duplicate or conflicting log entries.
   - **Mobile Undo & Log Rewind:** Verify that undoing actions on mobile properly removes or annotates corresponding session log records in `_log_records` without purging historical entries created in prior sessions.

3. **Log Query Performance & UI Consumption (Medium Priority):**
   - **Vectorized Log Filtering & Search (`backend/filter.py`):** Audit `Search_Old_Taxonomy` and audit-trail queries over `df_log` to verify that pandas operations are fully vectorized (avoiding `iterrows()` or full-scan python loops over large log sheets).
   - **Recent Activity Dialog & History Views (`ui/recent_activity_dialog.py`):** Inspect table sorting, action filtering (EDIT, GBIF, REVIEWED, etc.), and search indexing across `df_log` to eliminate UI latency or freezing when displaying databases with tens of thousands of log entries.

---

### Deliverables for Your First Turn
1. **Test Suite Baseline:** Report current test execution status (`python -m pytest` / `xvfb-run -a python3 -m pytest tests/`).
2. **Detailed Code Review Findings:** Present your findings in a structured Markdown table with the following columns:
   | Severity (Critical/High/Medium/Low) | File/Component | Issue Description | Proposed Fix & Testing Strategy |
   | :--- | :--- | :--- | :--- |
   | ... | ... | ... | ... |
3. **Test Coverage Gap Analysis:** Identify areas where the logging architecture lacks automated tests and explicitly propose new test cases to be written in Stage 2.
4. **Actionable Implementation Plan:** Provide clear, concrete proposed changes with targeted file references, acting as the blueprint for Stage 2. Do not modify any code until this plan is approved.