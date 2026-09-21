"""
ui/tutorials/discrepancy_tutorial.py

Action-driven interactive tutorial for resolving historical database and GBIF discrepancies.
Operates strictly in an isolated in-memory sandbox without mutating real user files.
"""

from .sandbox_manager import SandboxManager
from .tutorial_runner import TutorialRunner, ActionStep


def start_discrepancy_tutorial(ui, on_complete=None):
    """Initializes sandbox and starts the Historical & GBIF Discrepancy tutorial."""
    SandboxManager().enter_sandbox(ui, mock_type="discrepancy")

    # Ensure specimen 1001 is active
    if hasattr(ui, "load_object"):
        try:
            ui.load_object("1001")
        except Exception:
            pass

    steps = [
        ActionStep(
            step_id="open_resolver",
            title="Open Historical Conflict Resolver",
            instruction="Click the 'History' button in the Registration header (or press Ctrl+H) to open the Conflict Resolver.",
            target_id="history_btn",
            action_hint="Click the 'History' button.",
            validator=lambda u: bool(
                getattr(u, "_current_resolver_win", None) or
                any(getattr(w, "tutorial_id", "") == "hr_sidebar" for w in u.root.winfo_children() if hasattr(w, "winfo_children"))
            )
        ),
        ActionStep(
            step_id="field_directory",
            title="Navigate Conflicting Fields",
            instruction="The left sidebar lists fields containing differences between the active record, historical ledgers, and GBIF data. Click any field to jump to its card.",
            target_id="hr_sidebar",
            action_hint="Inspect the field directory sidebar."
        ),
        ActionStep(
            step_id="select_resolution",
            title="Select a Resolution Value",
            instruction="Issue cards display current values alongside historical suggestions. Click on a historical/suggested value card to select it for resolution.",
            target_id="hr_cards",
            action_hint="Click on a value card to select it."
        ),
        ActionStep(
            step_id="apply_changes",
            title="Apply Selected Resolutions",
            instruction="Click the 'Apply Changes' button to update the record with your selected resolutions.",
            target_id="hr_apply_all",
            action_hint="Click 'Apply Changes' to commit."
        ),
        ActionStep(
            step_id="discrepancy_complete",
            title="Tutorial Complete",
            instruction="You have completed the discrepancy resolution walkthrough. Click Finish to exit sandbox mode and return to your workspace.",
            action_hint="Click 'Finish' below to exit sandbox."
        )
    ]

    return TutorialRunner(ui, steps, tutorial_name="Historical & GBIF Conflicts", on_complete=on_complete)
