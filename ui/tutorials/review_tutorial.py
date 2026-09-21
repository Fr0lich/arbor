"""
ui/tutorials/review_tutorial.py

Action-driven interactive tutorial for reviewing and verifying specimen records.
Operates strictly in an isolated in-memory sandbox without mutating real user files.
"""

from .sandbox_manager import SandboxManager
from .tutorial_runner import TutorialRunner, ActionStep


def start_review_tutorial(ui, on_complete=None):
    """Initializes sandbox and starts the Object Review interactive tutorial."""
    SandboxManager().enter_sandbox(ui, mock_type="review")

    steps = [
        ActionStep(
            step_id="select_object",
            title="Locate & Select a Specimen",
            instruction="Type an ID or genus in the search bar, or click directly on specimen 1001 or 1002 in the listbox.",
            target_id="search_entry",
            action_hint="Click on record 1001 in the list.",
            validator=lambda u: getattr(u, "current_id", None) == "1001"
        ),
        ActionStep(
            step_id="inspect_editor",
            title="Inspect Registration Data",
            instruction="The Registration Data panel displays the properties of the active specimen. Verify the taxon, collector, and locality values.",
            target_id="object_editor_frame",
            action_hint="Inspect fields in the registration editor."
        ),
        ActionStep(
            step_id="check_flags",
            title="Validation & Problem Flags",
            instruction="Specimens with potential discrepancies display problem flags. You can modify field values or toggle flags in the Problems tab.",
            target_id="object_editor_frame",
            action_hint="Review or adjust any field value."
        ),
        ActionStep(
            step_id="mark_reviewed",
            title="Mark as Reviewed",
            instruction="Click the '✓ MARK AS REVIEWED' button (or press Ctrl+Enter) to mark the record as verified.",
            target_id="reviewed_button",
            action_hint="Click '✓ MARK AS REVIEWED' or press Ctrl+Enter.",
            validator=lambda u: bool(
                getattr(u, "reviewed_var", None) and u.reviewed_var.get()
            ) or (
                getattr(u, "current_id", None) and
                u.app.df_reg is not None and
                u.current_id in u.app.df_reg.index and
                bool(u.app.df_reg.loc[u.current_id].get("Reviewed", False))
            )
        ),
        ActionStep(
            step_id="review_complete",
            title="Tutorial Complete",
            instruction="You have completed the specimen review walkthrough. Click Finish to exit sandbox mode and return to your workspace.",
            action_hint="Click 'Finish' below to exit sandbox."
        )
    ]

    return TutorialRunner(ui, steps, tutorial_name="Reviewing Objects", on_complete=on_complete)
