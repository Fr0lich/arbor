# Bug Hunt Report

## 1. Advanced Settings `KeyError` on Save
*   **Severity:** High
*   **Location:** `ui/advanced_settings.py` (~line 551 in `save_settings`)
*   **The Bug:** The `save_settings` function iterates through `ADVANCED_SETTINGS_SCHEMA` and attempts to retrieve Tk variables from `self.vars[item_id]`. However, "button" types (e.g., `action_dark_mode`) do not have associated Tk variables initialized in `self.vars`. This causes a `KeyError` when saving settings, crashing the settings window.
*   **Proposed Fix:** Add an early skip condition in the loop inside `save_settings`: `if item["type"] == "button": continue`.

## 2. Hardcode `calamine` Engine for Excel Loading
*   **Severity:** High
*   **Location:** `repository.py` (~lines 198-203 in `ExcelRepository.load_excel`)
*   **The Bug:** The application uses `calamine` for a 5-10x parsing speedup when loading Excel files, but handles it as an optional dependency via a `try-except ImportError` block that falls back to `openpyxl`. If `calamine` is missing, users experience severe performance degradation without knowing why.
*   **Proposed Fix:** Add `python-calamine` as a required dependency in `requirements.txt`. Remove the fallback block in `repository.py` and hardcode `engine="calamine"` when calling `pd.ExcelFile()`.

## 3. Recursive Tkinter Event Bindings Overhead
*   **Severity:** Medium
*   **Location:** `ui/dialogs.py` (~line 342) and `ui/main_window.py` (~line 8316)
*   **The Bug:** The application binds the `<MouseWheel>` event recursively by manually iterating over the entire widget tree using `widget.winfo_children()` in `_bind_mousewheel_recursive`. This leads to performance issues (e.g., lag when rendering large UIs) and potential memory leaks when child widgets are destroyed or created dynamically.
*   **Proposed Fix:** Use Tkinter `bindtags`. Assign a custom tag (e.g., `MouseWheelTag`) to the `bindtags` of the parent/children and use `bind_class("MouseWheelTag", "<MouseWheel>", handler)` to handle scrolling efficiently in a single place.

## 4. Unsafe Boolean Parsing in Settings
*   **Severity:** Low / Medium
*   **Location:** `ui/advanced_settings.py` (~line 555)
*   **The Bug:** When toggling boolean settings, the code does a rudimentary string check: `if isinstance(old_val, str): old_val = (old_val.lower() == "true")`. This fails for types like integers or unexpected formats (e.g., `"1"`, `0`), which can lead to state desynchronisation.
*   **Proposed Fix:** Implement a robust `parse_bool` utility in `utils.py` that handles various falsy/truthy values consistently, and use it across the settings logic instead of manual parsing.

## 5. Bare `except:` Exception Handlers
*   **Severity:** Medium
*   **Location:** Across codebase, notably `config.py` (~line 43, 63, 70, 74, 102), `main.py` (~line 21, 48, 67, 116, 169, 192), `utils.py` (~line 93, 140)
*   **The Bug:** Numerous error handlers catch exceptions using a bare `except:`, which also catches vital system-level exceptions like `KeyboardInterrupt` and `SystemExit`, complicating graceful termination and process management.
*   **Proposed Fix:** Replace bare `except:` clauses with `except Exception:` to only catch standard program errors while allowing system-level interrupts to propagate normally.
