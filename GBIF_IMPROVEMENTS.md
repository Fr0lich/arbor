# GBIF Feature Improvement Suggestions

After reviewing the current implementation of the GBIF integration (`backend/gbif.py`, `ui/main_window.py`, `ui/gbif_dialog.py`, `ui/gbif_review.py`), here are several areas for improvement, focusing on error handling, performance, UI/UX, and data validation.

## 1. Better Error Handling and Feedback
**Issue:** When checking a single object or running a batch, a failed network request or timeout results in a generic empty result being returned from `backend.gbif.check_gbif`. The UI then displays a generic warning: "Could not find a match for this scientific name or an error occurred." It does not differentiate between a network failure and a genuine "no match found".
**Files to Edit:**
- `backend/gbif.py`: Suggest modifying `check_gbif` and `get_accepted_name` to raise specific exceptions or return a dictionary indicating an error state instead of catching all exceptions and returning `None`.
- `ui/main_window.py`: Suggest updating `check_gbif_action` and `_on_gbif_result` to inspect the error state and show a more informative messagebox (e.g., "Network error, please check your connection" vs "No match found in GBIF").

## 2. Parallelizing Batch Updates
**Issue:** The batch update feature calls `backend.gbif.batch_gbif_match`, which iterates sequentially over every selected object. For a large dataset, this is extremely slow and blocks progress.
**Files to Edit:**
- `backend/gbif.py`: Suggest refactoring `batch_gbif_match` to use a thread pool (like `concurrent.futures.ThreadPoolExecutor`). This will allow multiple GBIF API requests to be fired concurrently.
- Ensure that the `progress_callback` and `cancel_event` are handled in a thread-safe manner so the UI progress bar still updates correctly as results arrive.

## 3. UI Button Disabling During Load (Spam Prevention)
**Issue:** The "Check GBIF" button in the registry panel can be clicked multiple times before the asynchronous request completes, potentially triggering overlapping requests and dialogs.
**Files to Edit:**
- `ui/main_window.py`: Suggest disabling the "Check GBIF" button (or modifying its text to "Loading...") at the start of `check_gbif_action`. Ensure it is re-enabled inside `_process_gbif_updates` (or whenever the flow finishes, including error branches).
- `ui/registry_panel.py`: Ensure the button widget reference is accessible so it can be updated by the main window logic.

## 4. Validating Genus Requirements
**Issue:** If the user only inputs a `species` but leaves `genus` blank, the query is still sent to GBIF. This often yields inaccurate or noisy matches since a genus is almost always required for a proper taxonomic match.
**Files to Edit:**
- `ui/main_window.py`: Suggest adding validation inside `check_gbif_action` to warn the user and abort the check if the `genus` field is empty.
- `backend/gbif.py`: Suggest updating `batch_gbif_match` to skip processing objects that are missing a genus, rather than only skipping if both genus and species are missing.

## 5. Improving Synonym Handling Edge Cases
**Issue:** In `backend.gbif.batch_gbif_match`, if an item is a synonym, it fetches the accepted name. However, it blindly overwrites the `author`, `family`, and `higherClassification` with the accepted name's data even if the accepted name query failed to retrieve them.
**Files to Edit:**
- `backend/gbif.py`: Suggest modifying the synonym fallback block to only overwrite fields if they are actually present and non-empty in the accepted data response.

## 6. Higher Classification Formatting
**Issue:** The higher classification is created by joining `[kingdom, phylum, class, order]`. If the API returns empty strings rather than `None`, the resulting string might have hanging separators or weird formatting.
**Files to Edit:**
- `backend/gbif.py`: Suggest ensuring that empty strings are explicitly stripped or filtered out before joining the classification levels.
