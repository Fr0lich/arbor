# Arbor Interactive Tutorial System — Developer & AI Agent Guide

Welcome, Agent. This document defines the architecture, rules, and procedures for maintaining and extending the interactive tutorial system in Arbor.

---

## 1. Core Principles & Philosophy

When modifying or adding tutorials in Arbor, you **MUST** follow these mandatory rules:

1. **Strictly Operational Copy (No Domain Lectures):**
   * Do **NOT** explain what constitutes valid botanical data, taxonomic rules, or why a record needs curation.
   * Focus exclusively on software actions: *"Click the 'History' button"*, *"Press Ctrl+Enter to mark as reviewed"*, *"Type an ID in the search bar"*.
2. **Absolute Sandbox Isolation:**
   * Interactive tutorials must **NEVER** modify or write to real user Excel files on disk.
   * All tutorial actions run against ephemeral, in-memory mock datasets via `SandboxManager`.
   * The user's active session is snapshot on entry and cleanly restored upon tutorial exit or completion.
3. **Action-Driven Stepping with User Autonomy:**
   * Steps should use validator callbacks or UI signal listeners to advance automatically when the user performs the requested action.
   * **Never block the user:** Always provide persistent `"Skip Step"`, `"Back"`, and `"Exit Tutorial"` controls.
4. **Modular Architecture:**
   * Each distinct tutorial flow must reside in its own dedicated Python file inside `ui/tutorials/`.

---

## 2. Directory Structure

```
ui/tutorials/
├── __init__.py               # Package exports
├── sandbox_manager.py        # Snapshot, mock dataset factory, and state restore
├── tutorial_runner.py        # Floating HUD card, event gating, and target highlighting
├── review_tutorial.py        # Interactive flow: Reviewing & verifying objects
├── discrepancy_tutorial.py   # Interactive flow: Historical & GBIF conflict resolution
└── database_tutorial.py      # Interactive flow: Creating databases & new objects
```

---

## 3. How the Core Engine Works

### `SandboxManager` (`ui/tutorials/sandbox_manager.py`)
* `enter_sandbox(ui, mock_type)`:
  1. Deep-copies the active `AppState` (DataFrames, file paths, dirty flags, history caches).
  2. Generates in-memory synthetic DataFrames (`df_reg`, `df_obs`, `df_photo`, `df_log`) populated with sample specimens (e.g. `1001`, `1002`, `1003`).
  3. Re-initializes UI caches and refreshes the main visualizer via `ui._finish_open_excel("[Tutorial Sandbox]", ...)`.
* `exit_sandbox(ui)`:
  1. Restores the exact prior `AppState` and DataFrames.
  2. Rebuilds the UI back to the user's real open file. Zero disk operations occur.

### `TutorialRunner` & `ActionStep` (`ui/tutorials/tutorial_runner.py`)
* Manages a non-modal, top-level floating HUD displaying progress, step titles, action hints, and control buttons.
* Highlights targeted widgets using an animated glowing overlay (`TutorialHighlight`).
* Polls `validator(ui)` (every ~300ms) to detect when the required action has occurred and automatically advances to the next step.

---

## 4. How to Create or Modify a Tutorial

### Step 1: Define the Tutorial in a Modular File
Create a new file (e.g., `ui/tutorials/my_new_tutorial.py`):

```python
from .sandbox_manager import SandboxManager
from .tutorial_runner import TutorialRunner, ActionStep

def start_my_new_tutorial(ui, on_complete=None):
    # 1. Mount isolated sandbox
    SandboxManager().enter_sandbox(ui, mock_type="review")

    # 2. Define action-driven steps
    steps = [
        ActionStep(
            step_id="step_one",
            title="Locate the Action Button",
            instruction="Click the target button in the toolbar to begin.",
            target_id="my_button_tutorial_id",  # tutorial_id on widget or ui attribute name
            action_hint="Click the highlighted button.",
            validator=lambda u: getattr(u, "some_flag", False) is True
        ),
        ActionStep(
            step_id="step_two",
            title="Complete the Task",
            instruction="You have performed the action. Click Finish to exit sandbox mode.",
            action_hint="Click Finish below."
        )
    ]

    # 3. Launch the runner
    return TutorialRunner(ui, steps, tutorial_name="My New Feature", on_complete=on_complete)
```

### Step 2: Register in `ui/tutorials/__init__.py`
Export your new launcher function in `ui/tutorials/__init__.py`.

### Step 3: Wire into Help Menu & Shortcuts (`ui/help_dialogs.py`)
Add an entry in `ui/help_dialogs.py` `show_help_menu()` to make the tutorial launchable on demand.

---

## 5. Testing & Verification

Always write unit tests in `tests/test_sandbox_tutorials.py` when adding or modifying tutorials. Ensure tests verify:
1. `SandboxManager.enter_sandbox()` isolates state without altering `app.excel_path`.
2. Steps progress when `validator` evaluates to `True`.
3. `SandboxManager.exit_sandbox()` cleanly reinstates the original `df_reg` and `current_object_id`.

To run tests:
```powershell
python -m unittest tests/test_sandbox_tutorials.py
```
